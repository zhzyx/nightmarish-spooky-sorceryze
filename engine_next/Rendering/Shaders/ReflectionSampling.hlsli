// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_REFLECTION_SAMPLING_HLSLI
#define ENGINE_NEXT_REFLECTION_SAMPLING_HLSLI

#ifdef __cplusplus
#define REFLECTION_UNROLL
#else
#define REFLECTION_UNROLL [unroll]
#endif

float3 ReflectionFiniteColor(float3 Color)
{
    return all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0);
}

float3 ReflectionUnitDirection(float3 Direction)
{
    if (!all(isfinite(Direction)))
    {
        return float3(0, 0, 0);
    }
    float Scale = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
    if (Scale <= 0)
    {
        return float3(0, 0, 0);
    }
    Direction = Direction / Scale;
    return Direction / sqrt(dot(Direction, Direction));
}

float ReflectionRoughnessConfidence(float Roughness, float MaximumRoughness)
{
    if (!isfinite(Roughness) || !isfinite(MaximumRoughness) || MaximumRoughness <= 0)
    {
        return 0;
    }
    MaximumRoughness = min(MaximumRoughness, 1.0f);
    // Keep the smoothstep interval normal even at the smallest supported
    // binary32 roughness. GPUs can flush a scaled interval to zero.
    return 1 - smoothstep(0.8f, 1.0f, max(Roughness, 0.0f) / MaximumRoughness);
}

float ReflectionMipLevel(float Roughness, float MaximumMip)
{
    if (!isfinite(Roughness) || !isfinite(MaximumMip))
    {
        return 0;
    }
    return saturate(Roughness) * clamp(MaximumMip, 0, 5);
}

// Both the SSR term and the environment term use the same split-sum weight.
// Radiance already carries the current frame's pre-exposure.
float3 ReflectionBrdfWeight(float3 BaseColor, float Metallic, float Occlusion, float2 Brdf)
{
    if (!all(isfinite(BaseColor)) || !isfinite(Metallic) || !isfinite(Occlusion) ||
        !isfinite(Brdf.x) || !isfinite(Brdf.y))
    {
        return float3(0, 0, 0);
    }
    float3 F0 = lerp(float3(0.04f, 0.04f, 0.04f), clamp(BaseColor, 0, 1), saturate(Metallic));
    return (F0 * saturate(Brdf.x) + saturate(Brdf.y)) * saturate(Occlusion);
}

float ReflectionHitConfidence(float3 HitNormal, float3 RayDirection)
{
    float3 N = ReflectionUnitDirection(HitNormal);
    float3 D = ReflectionUnitDirection(RayDirection);
    // Suppress back faces and fade grazing intersections without accepting a
    // missing or nonfinite normal as a valid surface.
    return saturate(-dot(N, D) * 10);
}

float3 CombineReflectionRadiance(float3 BaseColor, float3 EnvironmentSpecular)
{
    return ReflectionFiniteColor(ReflectionFiniteColor(BaseColor) + ReflectionFiniteColor(EnvironmentSpecular));
}

float3 CompositeReflection(float3 BaseColor, float3 EnvironmentSpecular, float4 Reflection)
{
    BaseColor = ReflectionFiniteColor(BaseColor);
    EnvironmentSpecular = ReflectionFiniteColor(EnvironmentSpecular);
    if (!all(isfinite(Reflection.rgb)) || !isfinite(Reflection.w))
    {
        return CombineReflectionRadiance(BaseColor, EnvironmentSpecular);
    }
    float Confidence = saturate(Reflection.w);
    // BaseColor contains direct, diffuse IBL and emissive lighting. The separate
    // specular IBL term remains visible wherever a screen-space hit is missing.
    return ReflectionFiniteColor(BaseColor + lerp(EnvironmentSpecular, ReflectionFiniteColor(Reflection.rgb), Confidence));
}

// Each ceil-half texel integrates the source texels in its footprint exactly
// once. The last row/column can have a smaller footprint at odd dimensions.
float3 DownsampleReflection(Texture2D<float4> InputColor, int2 OutputPixel)
{
    uint Width;
    uint Height;
    InputColor.GetDimensions(Width, Height);
    int2 First = OutputPixel * 2;
    float3 Sum = float3(0, 0, 0);
    float Count = 0;
    REFLECTION_UNROLL for (int Y = 0; Y < 2; ++Y)
    {
        REFLECTION_UNROLL for (int X = 0; X < 2; ++X)
        {
            int2 Pixel = First + int2(X, Y);
            if (Pixel.x >= 0 && Pixel.y >= 0 && Pixel.x < int(Width) && Pixel.y < int(Height))
            {
                Sum += ReflectionFiniteColor(InputColor.Load(int3(Pixel, 0)).rgb) * 0.25f;
                Count += 0.25f;
            }
        }
    }
    return ReflectionFiniteColor(Sum / max(Count, 0.25f));
}

float3 SampleReflectionColor(Texture2D<float4> InputColor, float2 Uv)
{
    if (!isfinite(Uv.x) || !isfinite(Uv.y))
    {
        return float3(0, 0, 0);
    }
    uint Width;
    uint Height;
    InputColor.GetDimensions(Width, Height);
    float2 Pixel = clamp(Uv, 0, 1) * float2(float(Width), float(Height)) - 0.5f;
    int2 First = int2(floor(Pixel));
    float2 Fraction = frac(Pixel);
    float3 Sum = float3(0, 0, 0);
    REFLECTION_UNROLL for (int Y = 0; Y < 2; ++Y)
    {
        REFLECTION_UNROLL for (int X = 0; X < 2; ++X)
        {
            int2 Index = clamp(First + int2(X, Y), int2(0, 0), int2(Width, Height) - 1);
            float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) * (Y == 0 ? 1 - Fraction.y : Fraction.y);
            Sum += ReflectionFiniteColor(InputColor.Load(int3(Index, 0)).rgb) * Weight;
        }
    }
    return ReflectionFiniteColor(Sum);
}

#undef REFLECTION_UNROLL
#endif
