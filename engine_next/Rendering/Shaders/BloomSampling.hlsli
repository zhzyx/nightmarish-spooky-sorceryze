// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_BLOOM_SAMPLING_HLSLI
#define ENGINE_NEXT_BLOOM_SAMPLING_HLSLI

#ifdef __cplusplus
#define BLOOM_UNROLL
#else
#define BLOOM_UNROLL [unroll]
#endif

float3 SanitizeBloom(float3 Color)
{
    return all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0);
}

float3 ExtractBloom(float3 Color)
{
    Color = SanitizeBloom(Color);
    float PreExposure = ExposureRead[0].x;
    float DisplayExposure = ExposureWrite[0].x;
    if (!isfinite(PreExposure) || PreExposure <= 0 || !isfinite(DisplayExposure) || DisplayExposure <= 0 ||
        !isfinite(Parameters.y) || !isfinite(Parameters.z))
    {
        return float3(0, 0, 0);
    }
    float ExposureRatio = DisplayExposure / PreExposure;
    float Luminance = dot(Color, float3(0.2126f, 0.7152f, 0.0722f)) * ExposureRatio;
    if (!isfinite(ExposureRatio) || !isfinite(Luminance))
    {
        return float3(0, 0, 0);
    }
    float Threshold = max(Parameters.y, 0.0f);
    float Knee = max(Threshold * saturate(Parameters.z), 0.00001f);
    float Soft = clamp(Luminance - Threshold + Knee, 0, 2 * Knee);
    Soft = (Soft / Knee) * Soft * 0.25f;
    float Contribution = saturate(max(Luminance - Threshold, Soft) / max(Luminance, 0.00001f));
    return SanitizeBloom(Color * Contribution);
}

// Threshold individual source texels before interpolation so a subpixel bright
// highlight keeps its extracted energy as it moves through the sample footprint.
float3 SampleBloom(Texture2D<float4> InputColor, float2 Uv, bool Extract)
{
    uint Width;
    uint Height;
    InputColor.GetDimensions(Width, Height);
    float2 Pixel = Uv * float2(float(Width), float(Height)) - 0.5;
    int2 Base = (int2)floor(Pixel);
    float2 Fraction = frac(Pixel);
    int2 Maximum = int2(Width, Height) - 1;
    float3 Sum = float3(0, 0, 0);
    BLOOM_UNROLL for (int Y = 0; Y < 2; ++Y)
    {
        BLOOM_UNROLL for (int X = 0; X < 2; ++X)
        {
            int2 PixelIndex = clamp(Base + int2(X, Y), int2(0, 0), Maximum);
            float3 Color = SanitizeBloom(InputColor.Load(int3(PixelIndex, 0)).rgb);
            if (Extract)
            {
                Color = ExtractBloom(Color);
            }
            float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) *
                (Y == 0 ? 1 - Fraction.y : Fraction.y);
            Sum += Color * Weight;
        }
    }
    return SanitizeBloom(Sum);
}

float3 FilterBloom(Texture2D<float4> InputColor, float2 Uv, float2 TexelSize, bool Extract)
{
    float3 Sum = float3(0, 0, 0);
    BLOOM_UNROLL for (int Y = -1; Y <= 1; ++Y)
    {
        BLOOM_UNROLL for (int X = -1; X <= 1; ++X)
        {
            float Weight = (X == 0 ? 2.0f : 1.0f) * (Y == 0 ? 2.0f : 1.0f);
            Sum += SampleBloom(InputColor, Uv + float2(float(X), float(Y)) * TexelSize, Extract) * (Weight / 16);
        }
    }
    return SanitizeBloom(Sum);
}

float3 DownsampleBloom(float2 Uv)
{
    return FilterBloom(SourceColor, Uv, Source.zw, Modes.x > 0.5);
}

float3 UpsampleBloom(int2 Pixel, float2 Uv)
{
    uint Width;
    uint Height;
    LowerColor.GetDimensions(Width, Height);
    float3 Local = SanitizeBloom(SourceColor.Load(int3(Pixel, 0)).rgb);
    float3 Coarse = FilterBloom(LowerColor, Uv, 1.0f / float2(float(Width), float(Height)), false);
    return SanitizeBloom(lerp(Local, Coarse, saturate(Parameters.w)));
}

#undef BLOOM_UNROLL
#endif
