// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "ReflectionSampling.hlsli"

cbuffer ReflectionConstants : register(b0)
{
    float4 Viewport;
    float4 Projection;
    float4 Ray;
    float4 Settings;
};

#if defined(RADIANCE_STAGE)
Texture2D<float4> BaseColor : register(t0);
Texture2D<float4> EnvironmentSpecular : register(t1);
RWTexture2D<float4> OutputColor : register(u0);

[numthreads(8, 8, 1)]
void RadianceCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width;
    uint Height;
    OutputColor.GetDimensions(Width, Height);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
    int3 Pixel = int3(Thread.xy, 0);
    OutputColor[Thread.xy] = float4(CombineReflectionRadiance(BaseColor.Load(Pixel).rgb, EnvironmentSpecular.Load(Pixel).rgb), 1);
}

#elif defined(COLOR_MIP_STAGE)
Texture2D<float4> SourceColor : register(t0);
RWTexture2D<float4> OutputColor : register(u0);

[numthreads(8, 8, 1)]
void ColorMipCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width;
    uint Height;
    OutputColor.GetDimensions(Width, Height);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
    OutputColor[Thread.xy] = float4(DownsampleReflection(SourceColor, int2(Thread.xy)), 1);
}

#elif defined(COMPOSITE_STAGE)
Texture2D<float4> BaseColor : register(t0);
Texture2D<float4> EnvironmentSpecular : register(t1);
Texture2D<float4> ReflectionColor : register(t2);
RWTexture2D<float4> OutputColor : register(u0);

[numthreads(8, 8, 1)]
void CompositeCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width;
    uint Height;
    OutputColor.GetDimensions(Width, Height);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
    int3 Pixel = int3(Thread.xy, 0);
    OutputColor[Thread.xy] = float4(CompositeReflection(BaseColor.Load(Pixel).rgb,
        EnvironmentSpecular.Load(Pixel).rgb, ReflectionColor.Load(Pixel)), 1);
}

#elif defined(REFLECTION_TRACE_STAGE)
#include "ReflectionTrace.hlsli"
#if defined(MATERIAL_EXTENSION_STAGE)
#if defined(ENVIRONMENT_IMPORTANCE_STAGE)
#include "MaterialEnvironmentLighting.hlsli"
#else
#include "MaterialEnvironment.hlsli"
#endif
#endif

struct LocalLightConstants
{
    float4 PositionRange;
    float4 ColorIntensity;
    float4 DirectionType;
    float4 ConeShadow;
    float4 ShadowParameters;
};
cbuffer FrameConstants : register(b1)
{
    column_major float4x4 ViewProjection;
    column_major float4x4 InverseViewProjection;
    float4 Camera;
    float4 Lighting;
    column_major float4x4 View;
    column_major float4x4 ShadowViewProjection[4];
    float4 CascadeSplits;
    float4 LightDirection;
    float4 LightColor;
    float4 ShadowParameters;
    column_major float4x4 LocalShadowMatrices[28];
    LocalLightConstants LocalLights[8];
    float4 LocalCounts;
    column_major float4x4 UnjitteredViewProjection;
    column_major float4x4 PreviousViewProjection;
};

Texture2D<float4> BaseBuffer : register(t0);
Texture2D<float4> NormalBuffer : register(t1);
Texture2D<float4> SurfaceBuffer : register(t2);
Texture2D<float> DepthBuffer : register(t3);
Texture2D<float4> Radiance0 : register(t4);
Texture2D<float4> Radiance1 : register(t5);
Texture2D<float4> Radiance2 : register(t6);
Texture2D<float4> Radiance3 : register(t7);
Texture2D<float4> Radiance4 : register(t8);
Texture2D<float4> Radiance5 : register(t9);
Texture2D<float4> BrdfLut : register(t10);
#if defined(MATERIAL_EXTENSION_STAGE)
Texture2D<float4> MaterialBuffer : register(t11);
Texture2D<float4> TangentBuffer : register(t12);
TextureCube<float4> EnvironmentMap : register(t13);
StructuredBuffer<float4> ExposureState : register(t14);
SamplerState EnvironmentSampler : register(s0);
#endif
RWTexture2D<float4> OutputReflection : register(u0);

float3 SampleRadianceLevel(uint Level, float2 Uv)
{
    switch (Level)
    {
        case 0: return SampleReflectionColor(Radiance0, Uv);
        case 1: return SampleReflectionColor(Radiance1, Uv);
        case 2: return SampleReflectionColor(Radiance2, Uv);
        case 3: return SampleReflectionColor(Radiance3, Uv);
        case 4: return SampleReflectionColor(Radiance4, Uv);
        default: return SampleReflectionColor(Radiance5, Uv);
    }
}

float4 TraceReflection(int2 Pixel)
{
    float Depth = DepthBuffer.Load(int3(Pixel, 0));
    float3 Material = SurfaceBuffer.Load(int3(Pixel, 0)).rgb;
    if (!isfinite(Depth) || Depth <= 0 || Depth > 1 || !all(isfinite(Material)))
    {
        return 0;
    }
    float RoughnessConfidence = ReflectionRoughnessConfidence(Material.x, Settings.z);
    if (RoughnessConfidence <= 0)
    {
        return 0;
    }
    float2 Uv = (float2(Pixel) + 0.5f) / Viewport.xy;
    float4 World = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    if (!all(isfinite(World)) || abs(World.w) < 1.0e-8f)
    {
        return 0;
    }
    float3 Position = mul(View, float4(World.xyz / World.w, 1)).xyz;
    float3 Normal = ReflectionUnitDirection(mul((float3x3)View, NormalBuffer.Load(int3(Pixel, 0)).xyz));
    float3 ToCamera = ReflectionUnitDirection(-Position);
    float NoV = saturate(dot(Normal, ToCamera));
    if (!all(isfinite(Position)) || NoV <= 0)
    {
        return 0;
    }
    float3 Direction = reflect(-ToCamera, Normal);
    SsrTraceParameters Parameters;
    Parameters.Viewport = Viewport.xy;
    Parameters.Projection = Projection;
    Parameters.NearFar = Ray.xy;
    Parameters.MaxDistance = Ray.z;
    Parameters.Thickness = Ray.w;
    Parameters.MinDistance = min(max(Settings.x * 2, 0.001f), Ray.z * 0.25f);
    Parameters.EdgeFadePixels = 8;
    Parameters.MaxSteps = uint(clamp(Settings.y, 1, 256));
    SsrTraceResult Hit = TraceScreenRay(DepthBuffer, Position + Normal * Settings.x, Direction, Parameters);
    if (Hit.Reason != SSR_HIT)
    {
        return 0;
    }
    float3 HitNormal = mul((float3x3)View, NormalBuffer.Load(int3(Hit.Pixel, 0)).xyz);
    float Confidence = Hit.Confidence * RoughnessConfidence * ReflectionHitConfidence(HitNormal, Direction);
    if (Confidence <= 0)
    {
        return 0;
    }
    float Mip = ReflectionMipLevel(Material.x, Settings.w);
    uint LowerMip = uint(floor(Mip));
    uint UpperMip = min(LowerMip + 1, uint(clamp(Settings.w, 0, 5)));
    float3 Radiance = lerp(SampleRadianceLevel(LowerMip, Hit.Uv), SampleRadianceLevel(UpperMip, Hit.Uv), frac(Mip));
    float2 Brdf = SampleReflectionColor(BrdfLut, float2(NoV, saturate(Material.x))).xy;
    float3 Weight = ReflectionBrdfWeight(BaseBuffer.Load(int3(Pixel, 0)).rgb, Material.y, Material.z, Brdf);
    return float4(ReflectionFiniteColor(Radiance * Weight), saturate(Confidence));
}

#if defined(MATERIAL_EXTENSION_STAGE)
#if defined(ENVIRONMENT_IMPORTANCE_STAGE)
float3 TraceMaterialMisSample(float3 Position, float3 Normal, float3 Direction,
    float3 BaseWeight, float3 CoatWeight, float BaseRoughness, float CoatRoughness, SsrTraceParameters Parameters)
{
    if (all(BaseWeight == 0) && all(CoatWeight == 0))
    {
        return 0;
    }
    float3 Environment = EnvironmentMap.SampleLevel(EnvironmentSampler, Direction, 0).rgb * ExposureState[0].x;
    float3 Surface = Environment;
    float HitConfidence = 0;
    float BaseConfidence = ReflectionRoughnessConfidence(BaseRoughness, Settings.z);
    float CoatConfidence = ReflectionRoughnessConfidence(CoatRoughness, Settings.z);
    if (max(BaseConfidence, CoatConfidence) > 0)
    {
        float3 ViewDirection = ReflectionUnitDirection(mul((float3x3)View, Direction));
        SsrTraceResult Hit = TraceScreenRay(DepthBuffer, Position + Normal * Settings.x, ViewDirection, Parameters);
        if (Hit.Reason == SSR_HIT)
        {
            float3 HitNormal = mul((float3x3)View, NormalBuffer.Load(int3(Hit.Pixel, 0)).xyz);
            HitConfidence = Hit.Confidence * ReflectionHitConfidence(HitNormal, ViewDirection);
            Surface = SampleRadianceLevel(0, Hit.Uv);
        }
    }
    return lerp(Environment, Surface, saturate(HitConfidence * BaseConfidence)) * BaseWeight +
        lerp(Environment, Surface, saturate(HitConfidence * CoatConfidence)) * CoatWeight;
}
#endif

float3 TraceMaterialSample(float3 Position, float3 Normal, MaterialEnvironmentSample Sample,
    float Roughness, SsrTraceParameters Parameters)
{
    if (Sample.Pdf <= 0 || all(Sample.Weight == 0))
    {
        return 0;
    }
    float3 Radiance = EnvironmentMap.SampleLevel(EnvironmentSampler, Sample.Direction, 0).rgb * ExposureState[0].x;
    float Confidence = ReflectionRoughnessConfidence(Roughness, Settings.z);
    if (Confidence > 0)
    {
        float3 Direction = ReflectionUnitDirection(mul((float3x3)View, Sample.Direction));
        SsrTraceResult Hit = TraceScreenRay(DepthBuffer, Position + Normal * Settings.x, Direction, Parameters);
        if (Hit.Reason == SSR_HIT)
        {
            float3 HitNormal = mul((float3x3)View, NormalBuffer.Load(int3(Hit.Pixel, 0)).xyz);
            Confidence *= Hit.Confidence * ReflectionHitConfidence(HitNormal, Direction);
            Radiance = lerp(Radiance, SampleRadianceLevel(0, Hit.Uv), saturate(Confidence));
        }
    }
    return Radiance * Sample.Weight;
}

float4 TraceMaterialReflection(int2 Pixel, float4 Extension)
{
    float Depth = DepthBuffer.Load(int3(Pixel, 0));
    float3 Surface = SurfaceBuffer.Load(int3(Pixel, 0)).rgb;
    if (!isfinite(Depth) || Depth <= 0 || Depth > 1 || !all(isfinite(Surface)))
    {
        return 0;
    }
    float2 Uv = (float2(Pixel) + 0.5f) / Viewport.xy;
    float4 World = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    if (!all(isfinite(World)) || abs(World.w) < 1.0e-8f)
    {
        return 0;
    }
    float3 WorldPosition = World.xyz / World.w;
    float3 Position = mul(View, float4(WorldPosition, 1)).xyz;
    float3 N = ReflectionUnitDirection(NormalBuffer.Load(int3(Pixel, 0)).xyz);
    float3 V = ReflectionUnitDirection(Camera.xyz - WorldPosition);
    if (!all(isfinite(Position)) || dot(N, V) <= 0)
    {
        return 0;
    }
    float4 Tangent = TangentBuffer.Load(int3(Pixel, 0));
    MaterialFrame Frame = MaterialBuildFrame(N, Tangent.xyz, Tangent.w, Extension.w);
    float3 Base = BaseBuffer.Load(int3(Pixel, 0)).rgb;
    float3 ViewNormal = ReflectionUnitDirection(mul((float3x3)View, N));
    SsrTraceParameters Parameters;
    Parameters.Viewport = Viewport.xy;
    Parameters.Projection = Projection;
    Parameters.NearFar = Ray.xy;
    Parameters.MaxDistance = Ray.z;
    Parameters.Thickness = Ray.w;
    Parameters.MinDistance = min(max(Settings.x * 2, 0.001f), Ray.z * 0.25f);
    Parameters.EdgeFadePixels = 8;
    Parameters.MaxSteps = uint(clamp(Settings.y, 1, 256));
    float3 Color = 0;
#if defined(ENVIRONMENT_IMPORTANCE_STAGE)
    EnvironmentTableInfo Table = ReadEnvironmentTableInfo(EnvironmentAlias);
    MaterialMisCounts Counts;
    Counts.Base = 16;
    Counts.Coat = Extension.x > 0 ? 8 : 0;
    Counts.Diffuse = 0;
    Counts.Environment = Table.Valid ? 24 : 0;
    [loop] for (uint Index = 0; Index < Counts.Base; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentBaseSample(Base, Surface.y, Surface.x,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, Counts.Base));
        if (Sample.Pdf > 0)
        {
            float Pdf = EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Sample.Direction);
            MaterialMisWeights Weights = MaterialImportanceWeights(Base, Surface.y, Surface.x, Extension.z, Extension.x,
                Extension.y, Frame, V, Sample.Direction, Pdf, Counts);
            Color += TraceMaterialMisSample(Position, ViewNormal, Sample.Direction, Weights.Base, 0, Surface.x, Extension.y, Parameters);
        }
    }
    [loop] for (uint Index = 0; Index < Counts.Coat; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentCoatSample(Base, Surface.y, Surface.x,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, Counts.Coat));
        if (Sample.Pdf > 0)
        {
            float Pdf = EnvironmentDirectionPdf(EnvironmentAlias, Table.FaceSize, Table.UniformFallback, Sample.Direction);
            MaterialMisWeights Weights = MaterialImportanceWeights(Base, Surface.y, Surface.x, Extension.z, Extension.x,
                Extension.y, Frame, V, Sample.Direction, Pdf, Counts);
            Color += TraceMaterialMisSample(Position, ViewNormal, Sample.Direction, 0, Weights.Coat, Surface.x, Extension.y, Parameters);
        }
    }
    [loop] for (uint Index = 0; Index < Counts.Environment; ++Index)
    {
        EnvironmentDirectionSample Sample = SampleEnvironmentDirection(EnvironmentAlias, Table.FaceSize, Table.UniformFallback,
            MaterialEnvironmentCoordinates(Index, Counts.Environment));
        MaterialMisWeights Weights = MaterialImportanceWeights(Base, Surface.y, Surface.x, Extension.z, Extension.x,
            Extension.y, Frame, V, Sample.Direction, Sample.Pdf, Counts);
        Color += TraceMaterialMisSample(Position, ViewNormal, Sample.Direction, Weights.Base, Weights.Coat, Surface.x, Extension.y, Parameters);
    }
#else
    [loop] for (uint Index = 0; Index < 32; ++Index)
    {
        MaterialEnvironmentSample Sample = MaterialEnvironmentBaseSample(Base, Surface.y, Surface.x,
            Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, 32));
        Color += TraceMaterialSample(Position, ViewNormal, Sample, Surface.x, Parameters) / 32;
    }
    [branch] if (Extension.x > 0)
    {
        [loop] for (uint Index = 0; Index < 16; ++Index)
        {
            MaterialEnvironmentSample Sample = MaterialEnvironmentCoatSample(Base, Surface.y, Surface.x,
                Extension.z, Extension.x, Extension.y, Frame, V, MaterialHammersley(Index, 16));
            Color += TraceMaterialSample(Position, ViewNormal, Sample, Extension.y, Parameters) / 16;
        }
    }
#endif
    return float4(ReflectionFiniteColor(Color * Surface.z), 1);
}
#endif

[numthreads(8, 8, 1)]
void TraceCS(uint3 Thread : SV_DispatchThreadID)
{
    uint Width;
    uint Height;
    OutputReflection.GetDimensions(Width, Height);
    if (Thread.x >= Width || Thread.y >= Height)
    {
        return;
    }
#if defined(MATERIAL_EXTENSION_STAGE)
    float4 Extension = MaterialBuffer.Load(int3(Thread.xy, 0));
    if (!MaterialEnvironmentUsesLegacy(true, Extension.z, Extension.x))
    {
        OutputReflection[Thread.xy] = TraceMaterialReflection(int2(Thread.xy), Extension);
        return;
    }
#endif
    OutputReflection[Thread.xy] = TraceReflection(int2(Thread.xy));
}
#endif
