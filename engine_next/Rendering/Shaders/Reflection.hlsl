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
    OutputReflection[Thread.xy] = TraceReflection(int2(Thread.xy));
}
#endif
