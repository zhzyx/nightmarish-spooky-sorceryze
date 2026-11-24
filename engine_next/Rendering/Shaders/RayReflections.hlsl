// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "RayReflectionSampling.hlsli"

// All stages share one 128-byte root-constant layout. Histories contain
// physical, unexposed radiance on an unjittered grid.
cbuffer RayReflectionConstants : register(b0)
{
    float4 RtViewport;   // full width/height, ray width/height
    float4 RtProjection;
    float4 RtRay;        // near, far, maximum distance, normal bias
    float4 RtSettings;   // samples/lobe, submitted epoch, valid history, SSR
    float4 RtHistory;    // weight, relative depth, normal cosine, roughness
    uint4 RtCounts;      // draw, material, texture, maximum history
    float4 RtFilter;     // spatial step, GI enabled, maximum roughness, unused
    float4 RtJitter;     // current raster jitter in full-resolution pixels; SSR thickness in z
};

int2 RtCurrentPixel(uint2 Pixel)
{
    float2 Raster = (float2(Pixel) + 0.5f) * RtViewport.xy / RtViewport.zw + RtJitter.xy;
    return clamp(int2(floor(Raster)), int2(0, 0), int2(RtViewport.xy) - 1);
}

float RtViewDepth(float Depth)
{
    return Depth > 0 ? RtRay.x * RtRay.y / (RtRay.x + Depth * (RtRay.y - RtRay.x)) : 0;
}

float3 RtColor(float3 Color)
{
    return max(float3(RtFiniteValue(Color.x), RtFiniteValue(Color.y), RtFiniteValue(Color.z)), 0);
}

RtHistoryParameters RtParameters()
{
    RtHistoryParameters Parameters;
    Parameters.Weight = RtHistory.x;
    Parameters.DepthThreshold = RtHistory.y;
    Parameters.NormalThreshold = RtHistory.z;
    Parameters.RoughnessThreshold = RtHistory.w;
    Parameters.Maximum = RtCounts.w;
    return Parameters;
}

RtHit RtDecodeHit(uint4 Packed, bool Coat)
{
    RtHit Hit;
    Hit.Object = Coat ? Packed.z : Packed.x;
    Hit.Distance = asfloat(Coat ? Packed.w : Packed.y);
    return Hit;
}

#if defined(RAY_REFLECTION_TRACE)
#include "GISampling.hlsli"
#include "RayTracingScene.hlsli"
#include "GILighting.hlsli"
#include "GiReceiver.hlsli"
#define ENVIRONMENT_IMPORTANCE_STAGE 1
#include "MaterialEnvironmentLighting.hlsli"
#include "ReflectionTrace.hlsli"
#include "ReflectionSampling.hlsli"

struct RtVertex
{
    float3 Position;
    float3 Normal;
    float4 Tangent;
    float2 Texcoord;
};
RaytracingAccelerationStructure Scene : register(t0);
StructuredBuffer<RtVertex> Vertices : register(t1);
StructuredBuffer<uint> Indices : register(t2);
StructuredBuffer<RayTracingDraw> Draws : register(t3);
StructuredBuffer<RayTracingMaterial> Materials : register(t4);
Texture2D<float4> BaseBuffer : register(t5);
Texture2D<float4> NormalBuffer : register(t6);
Texture2D<float4> SurfaceBuffer : register(t7);
Texture2D<float> DepthBuffer : register(t8);
Texture2D<float4> MotionBuffer : register(t9);
Texture2D<uint> ObjectBuffer : register(t10);
Texture2D<float4> ExtensionBuffer : register(t11);
Texture2D<float4> TangentBuffer : register(t12);
TextureCube<float4> Environment : register(t13);
TextureCube<float4> Irradiance : register(t14);
// t15: environment alias, t16..18: probe receiver, declared by includes.
StructuredBuffer<float4> Extensions : register(t21);
StructuredBuffer<float4> Exposure : register(t22);
Texture2D<float4> ScreenRadiance : register(t23);
StructuredBuffer<float4> DirectionalTint : register(t30);
Texture2D<float4> MaterialTextures[2045] : register(t0, space1);
SamplerState MaterialSamplers[2045] : register(s0, space1);
SamplerState EnvironmentSampler : register(s0);
RWTexture2D<float4> RawBase : register(u0);
RWTexture2D<float4> RawCoat : register(u1);
RWTexture2D<uint4> RawHit : register(u2);
// primary, screen hit, DXR hit, miss, rejected/invalid, shadow, witness rays.
RWStructuredBuffer<uint> Counters : register(u3);

float4 RtTexture(uint Material, uint Slot, float2 Uv)
{
    uint Index = Material * 5 + Slot;
    if (Index >= RtCounts.z || Index >= 2045)
    {
        return Slot == 2 ? float4(0.5f, 0.5f, 1, 1) : float4(1, 1, 1, 1);
    }
    uint Descriptor = NonUniformResourceIndex(Index);
    return MaterialTextures[Descriptor].SampleLevel(MaterialSamplers[Descriptor], Uv, 0);
}

bool RtTriangle(uint Instance, uint Triangle, out RayTracingDraw Draw, out uint3 Vertex)
{
    Draw = (RayTracingDraw)0;
    Vertex = 0;
    uint DrawCount, Stride, VertexCount, IndexCount;
    Draws.GetDimensions(DrawCount, Stride);
    Vertices.GetDimensions(VertexCount, Stride);
    Indices.GetDimensions(IndexCount, Stride);
    if (Instance >= min(DrawCount, RtCounts.x))
    {
        return false;
    }
    Draw = Draws[Instance];
    if (Draw.Material >= RtCounts.y || Triangle >= Draw.IndexCount / 3 ||
        Draw.FirstIndex > IndexCount || Draw.IndexCount > IndexCount - Draw.FirstIndex)
    {
        return false;
    }
    uint First = Draw.FirstIndex + Triangle * 3;
    Vertex = uint3(Indices[First], Indices[First + 1], Indices[First + 2]);
    if (Draw.BaseVertex >= VertexCount || any(Vertex >= VertexCount - Draw.BaseVertex))
    {
        return false;
    }
    Vertex += Draw.BaseVertex;
    return true;
}

struct RtIntersection
{
    uint Instance;
    uint Material;
    float Distance;
    float2 Uv;
    float3 Position;
    float3 Normal;
    float3 Geometric;
    float3 Tangent;
    float Handedness;
};

// Alpha testing uses the same material/UV data as rasterization. BLEND uses
// stochastic coverage; no fixed alpha threshold turns glass into an opaque wall.
bool RtAccept(uint Instance, uint Triangle, float2 Bary, uint Seed)
{
    RayTracingDraw Draw;
    uint3 Vertex;
    if (!RtTriangle(Instance, Triangle, Draw, Vertex))
    {
        return false;
    }
    float2 Uv = Vertices[Vertex.x].Texcoord * (1 - Bary.x - Bary.y) +
        Vertices[Vertex.y].Texcoord * Bary.x + Vertices[Vertex.z].Texcoord * Bary.y;
    RayTracingMaterial Material = Materials[Draw.Material];
    float Alpha = RtTexture(Draw.Material, 0, Uv).a;
    if (Material.AlphaMode == 2)
    {
        return isfinite(Alpha) && RtRandom(Seed ^ RtHash(Instance) ^ RtHash(Triangle)) < saturate(Alpha * Material.BaseColor.a);
    }
    return RayTracingAlphaAccept(Material, Alpha);
}

bool RtIntersect(RayDesc Ray, uint Seed, out RtIntersection Hit, out bool Valid)
{
    Hit = (RtIntersection)0;
    Hit.Instance = RT_MISS_ID;
    Valid = true;
    RayQuery<RAY_FLAG_SKIP_PROCEDURAL_PRIMITIVES | RAY_FLAG_CULL_BACK_FACING_TRIANGLES> Query;
    Query.TraceRayInline(Scene, RAY_FLAG_NONE, 255, Ray);
    uint Candidates = 0;
    [loop] while (Query.Proceed())
    {
        if (++Candidates > 4096)
        {
            Valid = false;
            Query.Abort();
            break;
        }
        if (Query.CandidateType() == CANDIDATE_NON_OPAQUE_TRIANGLE &&
            RtAccept(Query.CandidateInstanceID(), Query.CandidatePrimitiveIndex(), Query.CandidateTriangleBarycentrics(), Seed))
        {
            Query.CommitNonOpaqueTriangleHit();
        }
    }
    if (!Valid || Query.CommittedStatus() != COMMITTED_TRIANGLE_HIT)
    {
        return false;
    }
    RayTracingDraw Draw;
    uint3 Vertex;
    if (!RtTriangle(Query.CommittedInstanceID(), Query.CommittedPrimitiveIndex(), Draw, Vertex))
    {
        Valid = false;
        return false;
    }
    float2 Bary = Query.CommittedTriangleBarycentrics();
    float3 Weight = float3(1 - Bary.x - Bary.y, Bary.x, Bary.y);
    RtVertex A = Vertices[Vertex.x];
    RtVertex B = Vertices[Vertex.y];
    RtVertex C = Vertices[Vertex.z];
    float3x3 WorldToObject = (float3x3)Query.CommittedWorldToObject3x4();
    float3x3 ObjectToWorld = (float3x3)Query.CommittedObjectToWorld3x4();
    float Face = Query.CommittedTriangleFrontFace() ? 1 : -1;
    Hit.Instance = Query.CommittedInstanceID();
    Hit.Material = Draw.Material;
    Hit.Distance = Query.CommittedRayT();
    Hit.Position = Ray.Origin + Ray.Direction * Hit.Distance;
    Hit.Uv = A.Texcoord * Weight.x + B.Texcoord * Weight.y + C.Texcoord * Weight.z;
    Hit.Geometric = RtUnit(mul(cross(B.Position - A.Position, C.Position - A.Position), WorldToObject)) * Face;
    Hit.Normal = RtUnit(mul(A.Normal * Weight.x + B.Normal * Weight.y + C.Normal * Weight.z, WorldToObject)) * Face;
    float4 Tangent = A.Tangent * Weight.x + B.Tangent * Weight.y + C.Tangent * Weight.z;
    float3 T = mul(ObjectToWorld, Tangent.xyz);
    MaterialFrame Frame = MaterialBuildFrame(Hit.Normal, T, Tangent.w, 0);
    Hit.Tangent = Frame.Tangent;
    float3x3 NormalizedWorld = float3x3(RtUnit(ObjectToWorld[0]), RtUnit(ObjectToWorld[1]), RtUnit(ObjectToWorld[2]));
    Hit.Handedness = Tangent.w * (determinant(NormalizedWorld) < 0 ? -1 : 1);
    float3 Mapped = RayTracingDecodeNormal(RtTexture(Draw.Material, 2, Hit.Uv).xyz, Materials[Draw.Material]);
    float Scale = Materials[Draw.Material].Surface.z;
    float Maximum = max(abs(Scale), 1);
    Mapped = RtUnit(float3(Mapped.xy * (Scale / Maximum), Mapped.z / Maximum));
    Hit.Normal = RtUnit(Hit.Tangent * Mapped.x + cross(Hit.Normal, Hit.Tangent) * Hit.Handedness * Mapped.y + Hit.Normal * Mapped.z);
    return true;
}

float RtVisibility(float3 Position, float3 Normal, float3 Direction, float Distance, uint Seed)
{
    InterlockedAdd(Counters[5], 1);
    RayDesc Ray;
    Ray.Origin = Position + Normal * RtRay.w;
    Ray.Direction = Direction;
    Ray.TMin = max(RtRay.w * 0.25f, 0.0001f);
    Ray.TMax = max(Distance - RtRay.w, Ray.TMin);
    RtIntersection Hit;
    bool Valid;
    bool Blocked = RtIntersect(Ray, Seed, Hit, Valid);
    if (!Valid)
    {
        InterlockedAdd(Counters[4], 1);
    }
    return Valid && !Blocked ? 1 : 0;
}

float3 RtHitLighting(RtIntersection Hit, float3 V, uint Seed)
{
    RayTracingMaterial Material = Materials[Hit.Material];
    float3 Base = saturate(Material.BaseColor.rgb * RtTexture(Hit.Material, 0, Hit.Uv).rgb);
    float4 Mr = RtTexture(Hit.Material, 1, Hit.Uv);
    float Roughness = saturate(Material.Surface.x * Mr.g);
    float Metallic = saturate(Material.Surface.y * Mr.b);
    float Ao = saturate(lerp(1, RtTexture(Hit.Material, 3, Hit.Uv).r, Material.Surface.w));
    float4 Extension = Extensions[Hit.Material];
    MaterialFrame Frame = MaterialBuildFrame(Hit.Normal, Hit.Tangent, Hit.Handedness, Extension.w);
    float Visibility = 1;
    if (ShadowParameters.x > 0.5f)
    {
        Visibility = RtVisibility(Hit.Position, Hit.Geometric, LightDirection.xyz, RtRay.z, Seed);
    }
    float3 Color = MaterialShadeLight(Base, Metallic, Roughness, Extension.z, Extension.x, Extension.y,
        true, Frame, V, LightDirection.xyz, LightColor.rgb * DirectionalTint[0].rgb) * Visibility;
    [loop] for (uint Index = 0; Index < min(uint(LocalCounts.x), 8u); ++Index)
    {
        GiLocalLightConstants Light = LocalLights[Index];
        float3 Vector = Light.PositionRange.xyz - Hit.Position;
        float Distance = length(Vector);
        if (!isfinite(Distance) || Distance <= 0 || Distance >= Light.PositionRange.w)
        {
            continue;
        }
        float3 L = Vector / Distance;
        float Attenuation = pow(saturate(1 - pow(Distance / Light.PositionRange.w, 4)), 2) / max(Distance * Distance, 0.0001f);
        if (Light.DirectionType.w > 0.5f)
        {
            float3 Cone = -L - Light.DirectionType.xyz;
            Attenuation *= 1 - smoothstep(Light.ConeShadow.x, Light.ConeShadow.y, dot(Cone, Cone));
        }
        Visibility = 1;
        if (ShadowParameters.x > 0.5f && Light.ConeShadow.z >= 0)
        {
            Visibility = RtVisibility(Hit.Position, Hit.Geometric, L, Distance, Seed ^ RtHash(Index + 1));
        }
        Color += MaterialShadeLight(Base, Metallic, Roughness, Extension.z, Extension.x, Extension.y, true,
            Frame, V, L, min(Light.ColorIntensity.rgb, 1.0e20f) * Attenuation) * Visibility;
    }
    MaterialEnvironmentLighting Ambient = SampleMaterialEnvironment(Environment, EnvironmentSampler, Base,
        Metallic, Roughness, Extension, Frame, V);
    float3 Diffuse = Ambient.Diffuse;
    if (RtFilter.y > 0.5f)
    {
        Diffuse = GiReceiverDiffuse(Diffuse, Hit.Position, Hit.Normal, V, Base, Metallic, Roughness, Extension, true);
    }
    Color += (Diffuse + Ambient.BaseSpecular + Ambient.CoatSpecular) * Ao;
    Color += Material.Emissive.rgb * RtTexture(Hit.Material, 4, Hit.Uv).rgb;
    return RtColor(Color);
}

float3 RtIncoming(float3 Position, float3 Normal, float3 Direction, float Roughness, uint Seed, out RtHit Result)
{
    Result.Object = RT_MISS_ID;
    Result.Distance = RtRay.z;
    InterlockedAdd(Counters[0], 1);
    // Screen tracing is only a shortcut for a confident front-facing hit.
    // A miss/edge/rough ray always has access to the complete DXR scene.
    if (RtSettings.w > 0.5f && Roughness < RtFilter.z)
    {
        SsrTraceParameters Parameters;
        Parameters.Viewport = RtViewport.xy;
        Parameters.Projection = RtProjection;
        Parameters.NearFar = RtRay.xy;
        Parameters.MaxDistance = RtRay.z;
        Parameters.Thickness = RtJitter.z;
        Parameters.MinDistance = max(RtRay.w * 2, 0.001f);
        Parameters.EdgeFadePixels = 8;
        Parameters.MaxSteps = uint(RtFilter.w);
        float3 ViewDirection = RtUnit(mul((float3x3)View, Direction));
        SsrTraceResult Screen = TraceScreenRay(DepthBuffer,
            mul(View, float4(Position + Normal * RtRay.w, 1)).xyz, ViewDirection, Parameters);
        if (Screen.Reason == SSR_HIT && Screen.Confidence > 0.99f &&
            ReflectionHitConfidence(mul((float3x3)View, NormalBuffer.Load(int3(Screen.Pixel, 0)).xyz), ViewDirection) > 0.99f)
        {
            float PreExposure = Exposure[0].x;
            if (isfinite(PreExposure) && PreExposure > 0)
            {
                Result.Object = ObjectBuffer.Load(int3(Screen.Pixel, 0));
                Result.Distance = Screen.RayDistance;
                InterlockedAdd(Counters[1], 1);
                return RtColor(ScreenRadiance.Load(int3(Screen.Pixel, 0)).rgb / PreExposure);
            }
        }
    }
    RayDesc Ray;
    Ray.Origin = Position + Normal * RtRay.w;
    Ray.Direction = Direction;
    Ray.TMax = RtRay.z;
    Ray.TMin = min(max(RtRay.w * 0.25f, 0.0001f), Ray.TMax * 0.25f);
    RtIntersection Hit;
    bool Valid;
    if (RtIntersect(Ray, Seed, Hit, Valid))
    {
        Result.Object = Hit.Instance + 1;
        Result.Distance = Hit.Distance;
        InterlockedAdd(Counters[2], 1);
        return RtHitLighting(Hit, -Direction, Seed);
    }
    if (!Valid)
    {
        Result.Object = RT_INVALID_ID;
        InterlockedAdd(Counters[4], 1);
        return 0;
    }
    InterlockedAdd(Counters[3], 1);
    return RtColor(Environment.SampleLevel(EnvironmentSampler, Direction, 0).rgb);
}

RtHit RtWitness(float3 Position, float3 Normal, float3 V, uint Seed)
{
    InterlockedAdd(Counters[6], 1);
    RayDesc Ray;
    Ray.Origin = Position + Normal * RtRay.w;
    Ray.Direction = RtUnit(reflect(-V, Normal));
    Ray.TMax = RtRay.z;
    Ray.TMin = min(max(RtRay.w * 0.25f, 0.0001f), Ray.TMax * 0.25f);
    RtIntersection Intersection;
    bool Valid;
    bool HasHit = RtIntersect(Ray, Seed, Intersection, Valid);
    RtHit Hit;
    Hit.Object = HasHit ? Intersection.Instance + 1 : RT_MISS_ID;
    Hit.Distance = HasHit ? Intersection.Distance : RtRay.z;
    if (!Valid)
    {
        Hit.Object = RT_INVALID_ID;
        InterlockedAdd(Counters[4], 1);
    }
    return Hit;
}

float3 RtLobe(float3 Position, float3 Base, float3 Surface, float4 Extension, MaterialFrame Frame,
    float3 V, bool Coat, uint Seed)
{
    float3 Sum = 0;
    uint Samples = clamp(uint(RtSettings.x), 1u, 4u);
    EnvironmentTableInfo Table = ReadEnvironmentTableInfo(EnvironmentAlias);
    MaterialMisCounts Counts;
    Counts.Base = Coat ? 0 : Samples;
    Counts.Coat = Coat ? Samples : 0;
    Counts.Diffuse = 0;
    Counts.Environment = Table.Valid ? Samples : 0;
    // Stratify the two proposals. Each contributes (1/2)/q where
    // q=(pBrdf+pEnvironment)/2, including the 1/Samples normalization.
    // A Bernoulli choice would leave half of a sharp mirror's frames with a
    // near-zero environment sample and unnecessarily reset sampled-hit history.
    [loop] for (uint Index = 0; Index < Samples + Counts.Environment; ++Index)
    {
        uint SampleSeed = RtHash(Seed ^ RtHash(Index));
        float2 Xi = float2(RtRandom(SampleSeed), RtRandom(SampleSeed ^ 0x71a32e21u));
        float3 Direction;
        if (Index >= Samples)
        {
            EnvironmentDirectionSample Sample = SampleEnvironmentDirection(EnvironmentAlias, Table.FaceSize,
                Table.UniformFallback, float3(Xi, RtRandom(SampleSeed ^ 0xab182c91u)));
            Direction = Sample.Direction;
        }
        else
        {
            MaterialEnvironmentSample Sample;
            if (Coat)
            {
                Sample = MaterialEnvironmentCoatSample(Base, Surface.y, Surface.x, Extension.z, Extension.x, Extension.y, Frame, V, Xi);
            }
            else
            {
                Sample = MaterialEnvironmentBaseSample(Base, Surface.y, Surface.x, Extension.z, Extension.x, Extension.y, Frame, V, Xi);
            }
            Direction = Sample.Direction;
        }
        float Pdf = Table.Valid ? EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Direction) : 0;
        MaterialMisWeights Weights = MaterialImportanceWeights(Base, Surface.y, Surface.x, Extension.z,
            Extension.x, Extension.y, Frame, V, Direction, Pdf, Counts);
        float3 Weight = Coat ? Weights.Coat : Weights.Base;
        if (!all(isfinite(Weight)) || all(Weight <= 0))
        {
            continue;
        }
        RtHit Hit;
        float3 Incoming = RtIncoming(Position, Frame.Normal, Direction, Coat ? Extension.y : Surface.x, SampleSeed, Hit);
        Sum += RtColor(Incoming * Weight);
    }
    return RtColor(Sum * saturate(Surface.z));
}

[numthreads(8, 8, 1)] void TraceCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= uint2(RtViewport.zw)))
    {
        return;
    }
    int2 Pixel = RtCurrentPixel(Thread.xy);
    float Depth = DepthBuffer.Load(int3(Pixel, 0));
    uint Object = ObjectBuffer.Load(int3(Pixel, 0));
    RawBase[Thread.xy] = 0;
    RawCoat[Thread.xy] = 0;
    RawHit[Thread.xy] = uint4(RT_INVALID_ID, 0, RT_INVALID_ID, 0);
    if (Object == 0 || Depth <= 0 || !isfinite(Depth))
    {
        return;
    }
    float2 Uv = (float2(Pixel) + 0.5f) / RtViewport.xy;
    float4 World = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    if (!all(isfinite(World)) || World.w == 0)
    {
        InterlockedAdd(Counters[4], 1);
        return;
    }
    float3 Position = World.xyz / World.w;
    float3 N = RtUnit(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    float3 V = RtUnit(Camera.xyz - Position);
    float4 Tangent = TangentBuffer.Load(int3(Pixel, 0));
    float4 Extension = ExtensionBuffer.Load(int3(Pixel, 0));
    MaterialFrame Frame = MaterialBuildFrame(N, Tangent.xyz, Tangent.w, Extension.w);
    float3 Surface = SurfaceBuffer.Load(int3(Pixel, 0)).rgb;
    float3 Base = BaseBuffer.Load(int3(Pixel, 0)).rgb;
    uint PixelSeed = RtHash(Thread.x + Thread.y * uint(RtViewport.z));
    uint Seed = PixelSeed ^ RtHash(uint(RtSettings.y));
    // Denoiser metadata describes a stable geometric direction, independent
    // of the stochastic radiance proposal. This also follows moving occluders.
    RtHit Witness = RtWitness(Position, N, V, PixelSeed);
    float3 BaseColor = RtLobe(Position, Base, Surface, Extension, Frame, V, false, Seed);
    float3 CoatColor = 0;
    if (Extension.x > 0)
    {
        CoatColor = RtLobe(Position, Base, Surface, Extension, Frame, V, true, Seed ^ 0x812b7731u);
    }
    RawBase[Thread.xy] = float4(BaseColor, 1);
    RawCoat[Thread.xy] = float4(CoatColor, 1);
    RawHit[Thread.xy] = uint4(Witness.Object, asuint(Witness.Distance), Witness.Object, asuint(Witness.Distance));
}

#elif defined(RAY_REFLECTION_TEMPORAL)
Texture2D<float4> RawBase : register(t0);
Texture2D<float4> RawCoat : register(t1);
Texture2D<uint4> RawHit : register(t2);
Texture2D<float4> OldBase : register(t3);
Texture2D<float4> OldCoat : register(t4);
Texture2D<float4> OldMoments : register(t5);
Texture2D<float4> OldSurface : register(t6);
Texture2D<float2> OldDepth : register(t7);
Texture2D<uint> OldObject : register(t8);
Texture2D<uint4> OldHit : register(t9);
Texture2D<float4> NormalBuffer : register(t10);
Texture2D<float4> SurfaceBuffer : register(t11);
Texture2D<float> DepthBuffer : register(t12);
Texture2D<float4> MotionBuffer : register(t13);
Texture2D<uint> ObjectBuffer : register(t14);
Texture2D<float4> ExtensionBuffer : register(t15);
RWTexture2D<float4> NewBase : register(u0);
RWTexture2D<float4> NewCoat : register(u1);
RWTexture2D<float4> NewMoments : register(u2);
RWTexture2D<float4> NewSurface : register(u3);
RWTexture2D<float2> NewDepth : register(u4);
RWTexture2D<uint> NewObject : register(u5);
RWTexture2D<uint4> NewHit : register(u6);

RtSurface RtOldSurface(int2 Pixel, bool Coat)
{
    float4 Surface = OldSurface.Load(int3(Pixel, 0));
    float2 Depth = OldDepth.Load(int3(Pixel, 0));
    RtSurface Value;
    Value.Depth = Depth.x;
    Value.Normal = Surface.xyz;
    Value.Roughness = Coat ? Depth.y : Surface.w;
    Value.Object = OldObject.Load(int3(Pixel, 0));
    return Value;
}

float4 RtTemporalLobe(uint2 Pixel, RtSurface Surface, float ExpectedDepth, float2 Previous,
    bool Valid, bool Coat, out float2 Moments)
{
    float4 Current = Coat ? RawCoat.Load(int3(Pixel, 0)) : RawBase.Load(int3(Pixel, 0));
    Current.rgb = RtColor(Current.rgb);
    float3 Minimum = Current.rgb;
    float3 Maximum = Current.rgb;
    uint4 Hit = RawHit.Load(int3(Pixel, 0));
    [unroll] for (int Y = -1; Y <= 1; ++Y)
    {
        [unroll] for (int X = -1; X <= 1; ++X)
        {
            int2 Neighbor = clamp(int2(Pixel) + int2(X, Y), 0, int2(RtViewport.zw) - 1);
            int2 Full = RtCurrentPixel(uint2(Neighbor));
            if (ObjectBuffer.Load(int3(Full, 0)) == Surface.Object)
            {
                float3 Color = Coat ? RawCoat.Load(int3(Neighbor, 0)).rgb : RawBase.Load(int3(Neighbor, 0)).rgb;
                Minimum = min(Minimum, RtColor(Color));
                Maximum = max(Maximum, RtColor(Color));
            }
        }
    }
    float4 History = 0;
    float2 HistoryMoments = 0;
    float Total = 0;
    float Confidence = 0;
    int2 First = int2(floor(Previous));
    float2 Fraction = frac(Previous);
    if (Valid)
    {
        [unroll] for (int Y = 0; Y < 2; ++Y)
        {
            [unroll] for (int X = 0; X < 2; ++X)
            {
                int2 Tap = First + int2(X, Y);
                float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) * (Y == 0 ? 1 - Fraction.y : Fraction.y);
                if (any(Tap < 0) || any(Tap >= int2(RtViewport.zw)) || Weight <= 0)
                {
                    continue;
                }
                if (!RtSurfaceMatches(Surface, RtOldSurface(Tap, Coat), ExpectedDepth, RtParameters()))
                {
                    continue;
                }
                float4 Prior = Coat ? OldCoat.Load(int3(Tap, 0)) : OldBase.Load(int3(Tap, 0));
                float HitConfidence = RtHitConfidence(RtDecodeHit(Hit, Coat), RtDecodeHit(OldHit.Load(int3(Tap, 0)), Coat), Surface.Roughness);
                float4 PriorMoments = OldMoments.Load(int3(Tap, 0));
                if (!all(isfinite(Prior)) || !all(isfinite(PriorMoments)))
                {
                    continue;
                }
                float AcceptedWeight = RtHistoryTapWeight(Weight, HitConfidence);
                History += Prior * AcceptedWeight;
                HistoryMoments += (Coat ? PriorMoments.zw : PriorMoments.xy) * AcceptedWeight;
                Confidence += AcceptedWeight;
                Total += Weight;
            }
        }
    }
    float Blend = 0;
    if (Total >= 0.5f && Confidence > 0)
    {
        // Reject incompatible reflected surfaces before filtering their color.
        // Scaling only the final blend would still mix rejected tap colors.
        History /= Confidence;
        HistoryMoments /= Confidence;
        Blend = RtHistoryWeight(History.w, Confidence, RtParameters());
        // Keep a small variance-aware interval on stochastic samples; a single
        // zero current sample must not erase a converged small light immediately.
        float Expand = sqrt(RtVariance(HistoryMoments)) * 0.1f;
        History.rgb = clamp(History.rgb, max(Minimum * (1 - Expand), 0), Maximum * (1 + Expand) + 0.0001f);
    }
    Moments = RtUpdateMoments(HistoryMoments, Current.rgb, Blend);
    return float4(RtColor(lerp(Current.rgb, History.rgb, Blend)), Blend > 0 ? min(History.w + 1, float(RtCounts.w)) : 1);
}

[numthreads(8, 8, 1)] void TemporalCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= uint2(RtViewport.zw)))
    {
        return;
    }
    int2 Pixel = RtCurrentPixel(Thread.xy);
    RtSurface Surface;
    Surface.Depth = RtViewDepth(DepthBuffer.Load(int3(Pixel, 0)));
    Surface.Object = ObjectBuffer.Load(int3(Pixel, 0));
    Surface.Normal = RtUnit(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    Surface.Roughness = SurfaceBuffer.Load(int3(Pixel, 0)).x;
    float CoatRoughness = ExtensionBuffer.Load(int3(Pixel, 0)).y;
    float4 Motion = MotionBuffer.Load(int3(Pixel, 0));
    bool Valid = RtSettings.z > 0.5f && Motion.w > 0.5f && all(isfinite(Motion)) &&
        Surface.Object != 0 && Surface.Depth > 0;
    float2 Previous = RtPreviousGridCoordinate(float2(Thread.xy), Motion.xy, RtViewport.zw);
    float2 BaseMoments;
    float2 CoatMoments;
    NewBase[Thread.xy] = RtTemporalLobe(Thread.xy, Surface, Motion.z, Previous, Valid, false, BaseMoments);
    NewSurface[Thread.xy] = float4(Surface.Normal, Surface.Roughness);
    NewDepth[Thread.xy] = float2(Surface.Depth, CoatRoughness);
    NewObject[Thread.xy] = Surface.Object;
    NewHit[Thread.xy] = RawHit.Load(int3(Thread.xy, 0));
    Surface.Roughness = CoatRoughness;
    NewCoat[Thread.xy] = RtTemporalLobe(Thread.xy, Surface, Motion.z, Previous, Valid, true, CoatMoments);
    NewMoments[Thread.xy] = float4(BaseMoments, CoatMoments);
}

#elif defined(RAY_REFLECTION_SPATIAL)
Texture2D<float4> InputBase : register(t0);
Texture2D<float4> InputCoat : register(t1);
Texture2D<float4> Moments : register(t2);
Texture2D<float4> Surface : register(t3);
Texture2D<float2> Depth : register(t4);
Texture2D<uint> Object : register(t5);
Texture2D<uint4> Hit : register(t6);
RWTexture2D<float4> OutputBase : register(u0);
RWTexture2D<float4> OutputCoat : register(u1);

float4 RtFilterLobe(int2 Pixel, bool Coat)
{
    float4 Center = Coat ? InputCoat.Load(int3(Pixel, 0)) : InputBase.Load(int3(Pixel, 0));
    float4 CenterSurface = Surface.Load(int3(Pixel, 0));
    float2 CenterDepth = Depth.Load(int3(Pixel, 0));
    uint CenterObject = Object.Load(int3(Pixel, 0));
    float4 CenterMoments = Moments.Load(int3(Pixel, 0));
    float Roughness = Coat ? CenterDepth.y : CenterSurface.w;
    float Variance = RtVariance(Coat ? CenterMoments.zw : CenterMoments.xy);
    float3 Sum = Center.rgb;
    float Total = 1;
    // A perfect mirror retains its exact ray rather than mixing adjacent hits.
    if (Roughness > 0.04f && CenterObject != 0 && CenterDepth.x > 0)
    {
        [unroll] for (int Y = -1; Y <= 1; ++Y)
        {
            [unroll] for (int X = -1; X <= 1; ++X)
            {
                if (X == 0 && Y == 0)
                {
                    continue;
                }
                int2 Tap = Pixel + int2(X, Y) * int(RtFilter.x);
                if (any(Tap < 0) || any(Tap >= int2(RtViewport.zw)))
                {
                    continue;
                }
                float4 TapSurface = Surface.Load(int3(Tap, 0));
                float2 TapDepth = Depth.Load(int3(Tap, 0));
                float4 Color = Coat ? InputCoat.Load(int3(Tap, 0)) : InputBase.Load(int3(Tap, 0));
                float Weight = RtSpatialWeight(dot(CenterSurface.xyz, TapSurface.xyz),
                    (TapDepth.x - CenterDepth.x) / max(CenterDepth.x, 0.0001f),
                    (Coat ? TapDepth.y : TapSurface.w) - Roughness,
                    RtSignedLogLuminance(Color.rgb) - RtSignedLogLuminance(Center.rgb), Variance,
                    RtHitConfidence(RtDecodeHit(Hit.Load(int3(Pixel, 0)), Coat), RtDecodeHit(Hit.Load(int3(Tap, 0)), Coat), Roughness),
                    CenterObject == Object.Load(int3(Tap, 0)));
                Weight *= (X == 0 ? 2 : 1) * (Y == 0 ? 2 : 1) * 0.25f;
                Sum += RtColor(Color.rgb) * Weight;
                Total += Weight;
            }
        }
    }
    return float4(RtColor(Sum / Total), Center.w);
}

[numthreads(8, 8, 1)] void SpatialCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= uint2(RtViewport.zw)))
    {
        return;
    }
    OutputBase[Thread.xy] = RtFilterLobe(int2(Thread.xy), false);
    OutputCoat[Thread.xy] = RtFilterLobe(int2(Thread.xy), true);
}

#elif defined(RAY_REFLECTION_COMPOSITE)
Texture2D<float4> BaseColor : register(t0);
Texture2D<float4> EnvironmentSpecular : register(t1);
Texture2D<float4> FilteredBase : register(t2);
Texture2D<float4> FilteredCoat : register(t3);
Texture2D<float4> RaySurface : register(t4);
Texture2D<float2> RayDepth : register(t5);
Texture2D<uint> RayObject : register(t6);
Texture2D<float4> NormalBuffer : register(t7);
Texture2D<float> DepthBuffer : register(t8);
Texture2D<uint> ObjectBuffer : register(t9);
StructuredBuffer<float4> Exposure : register(t10);
RWTexture2D<float4> Output : register(u0);

[numthreads(8, 8, 1)] void CompositeCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= uint2(RtViewport.xy)))
    {
        return;
    }
    int2 Pixel = int2(Thread.xy);
    float Depth = RtViewDepth(DepthBuffer.Load(int3(Pixel, 0)));
    float3 Normal = RtUnit(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    uint Object = ObjectBuffer.Load(int3(Pixel, 0));
    float2 Coordinate = (float2(Pixel) + 0.5f - RtJitter.xy) * RtViewport.zw / RtViewport.xy - 0.5f;
    int2 First = int2(floor(Coordinate));
    float2 Fraction = frac(Coordinate);
    float3 Sum = 0;
    float Total = 0;
    [unroll] for (int Y = 0; Y < 2; ++Y)
    {
        [unroll] for (int X = 0; X < 2; ++X)
        {
            int2 Tap = First + int2(X, Y);
            if (Object == 0 || any(Tap < 0) || any(Tap >= int2(RtViewport.zw)) || RayObject.Load(int3(Tap, 0)) != Object)
            {
                continue;
            }
            float4 Surface = RaySurface.Load(int3(Tap, 0));
            float TapDepth = RayDepth.Load(int3(Tap, 0)).x;
            if (Depth <= 0 || abs(TapDepth - Depth) > RtHistory.y * Depth || dot(Normal, Surface.xyz) < RtHistory.z)
            {
                continue;
            }
            float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) * (Y == 0 ? 1 - Fraction.y : Fraction.y);
            Sum += (FilteredBase.Load(int3(Tap, 0)).rgb + FilteredCoat.Load(int3(Tap, 0)).rgb) * Weight;
            Total += Weight;
        }
    }
    float3 Specular = EnvironmentSpecular.Load(int3(Pixel, 0)).rgb;
    if (Total > 0.0001f)
    {
        Specular = RtColor(Sum / Total) * Exposure[0].x;
    }
    // BaseColor excludes environment specular in the reflection permutation.
    // Replace that one term; direct, diffuse GI and emissive are preserved.
    Output[Thread.xy] = float4(clamp(RtColor(BaseColor.Load(int3(Pixel, 0)).rgb + Specular), 0, 65504), 1);
}
#endif
