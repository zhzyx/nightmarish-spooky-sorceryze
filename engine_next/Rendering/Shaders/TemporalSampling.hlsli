// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_TEMPORAL_SAMPLING_HLSLI
#define ENGINE_NEXT_TEMPORAL_SAMPLING_HLSLI

#ifdef __cplusplus
#define TEMPORAL_UNROLL
#else
#define TEMPORAL_UNROLL [unroll]
#endif

float3 FiniteColor(float3 Color)
{
    return all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0);
}

float3 ToYCoCg(float3 Color)
{
    return float3(dot(Color, float3(0.25, 0.5, 0.25)),
        0.5f * (Color.r - Color.b), dot(Color, float3(-0.25, 0.5, -0.25)));
}

float3 FromYCoCg(float3 Color)
{
    return float3(Color.x + Color.y - Color.z, Color.x + Color.z, Color.x - Color.y - Color.z);
}

bool ValidNormal(float3 Normal)
{
    return all(isfinite(Normal)) && dot(Normal, Normal) > 0.000001;
}

float ViewDepth(float Depth)
{
    return Planes.x / (Depth + (Planes.x / Planes.y) * (1 - Depth));
}

float4 CurrentColorTap(int2 Pixel, uint ObjectId, float LinearDepth, float3 Normal, float Weight)
{
    if (Weight <= 0 || CurrentObjectId.Load(int3(Pixel, 0)) != ObjectId)
    {
        return float4(0, 0, 0, 0);
    }
    float Depth = CurrentDepth.Load(int3(Pixel, 0));
    if (ObjectId == 0)
    {
        if (!isfinite(Depth) || Depth > 0)
        {
            return float4(0, 0, 0, 0);
        }
    }
    else
    {
        float3 TapNormal = CurrentNormal.Load(int3(Pixel, 0)).xyz;
        float TapDepth = ViewDepth(Depth);
        float AllowedDepthError = max(Settings.z, 0.0001) * max(LinearDepth, TapDepth);
        if (!isfinite(Depth) || Depth <= 0 || Depth > 1 || !isfinite(TapDepth) || TapDepth <= 0 ||
            !ValidNormal(TapNormal) || abs(TapDepth - LinearDepth) > AllowedDepthError ||
            dot(Normal, normalize(TapNormal)) < 0.85)
        {
            return float4(0, 0, 0, 0);
        }
    }
    float3 Color = CurrentHdr.Load(int3(Pixel, 0)).rgb;
    return all(isfinite(Color)) ? float4(FiniteColor(Color) * Weight, Weight) : float4(0, 0, 0, 0);
}

float4 ReconstructCurrentColor(float2 CurrentUv, int2 CurrentPixel, uint ObjectId, float LinearDepth, float3 Normal)
{
    int2 MaximumPixel = (int2)Viewport.xy - 1;
    float2 CurrentSample = CurrentUv * Viewport.xy - 0.5;
    int2 CurrentBase = (int2)floor(CurrentSample);
    float2 CurrentFraction = frac(CurrentSample);
    float4 CurrentSum = float4(0, 0, 0, 0);
    float SameSurfaceWeight = 0;
    TEMPORAL_UNROLL for (int Y = 0; Y < 2; ++Y)
    {
        TEMPORAL_UNROLL for (int X = 0; X < 2; ++X)
        {
            float Weight = (X == 0 ? 1 - CurrentFraction.x : CurrentFraction.x) *
                (Y == 0 ? 1 - CurrentFraction.y : CurrentFraction.y);
            int2 SamplePixel = clamp(CurrentBase + int2(X, Y), int2(0, 0), MaximumPixel);
            float3 SampleColor = CurrentHdr.Load(int3(SamplePixel, 0)).rgb;
            if (all(isfinite(SampleColor)))
            {
                CurrentSum += float4(FiniteColor(SampleColor) * Weight, Weight);
                SameSurfaceWeight += CurrentColorTap(SamplePixel, ObjectId, LinearDepth, Normal, Weight).w;
            }
        }
    }
    if (CurrentSum.w > 0.000001)
    {
        return float4(FiniteColor(CurrentSum.rgb / CurrentSum.w), saturate(SameSurfaceWeight / CurrentSum.w));
    }
    return float4(FiniteColor(CurrentHdr.Load(int3(CurrentPixel, 0)).rgb), 0);
}

float4 ValidHistoryTap(int2 Pixel, uint ObjectId, float ExpectedDepth, float3 Normal, float Coverage, float Weight)
{
    if (Weight <= 0 || HistoryObjectId.Load(int3(Pixel, 0)) != ObjectId)
    {
        return float4(0, 0, 0, 0);
    }
    float Depth = HistoryDepth.Load(int3(Pixel, 0));
    float3 PreviousNormal = HistoryNormal.Load(int3(Pixel, 0)).xyz;
    float AllowedDepthError = Settings.z * max(ExpectedDepth, Depth);
    if (!isfinite(Depth) || Depth <= 0 || !ValidNormal(PreviousNormal) ||
        abs(Depth - ExpectedDepth) > AllowedDepthError || dot(Normal, normalize(PreviousNormal)) < 0.85)
    {
        return float4(0, 0, 0, 0);
    }
    float4 Color = HistoryColor.Load(int3(Pixel, 0));
    float4 Exposure = ExposureState[0];
    float Ratio = Exposure.x / Exposure.y;
    if (!isfinite(Exposure.x) || !isfinite(Exposure.y) || Exposure.x <= 0 || Exposure.y <= 0 || !isfinite(Ratio) || Ratio <= 0)
    {
        return float4(0, 0, 0, 0);
    }
    if (!all(isfinite(Color)))
    {
        return float4(0, 0, 0, 0);
    }
    Weight *= saturate(1 - abs(Color.a - Coverage) * 4);
    return float4(FiniteColor(Color.rgb * Ratio) * Weight, Weight);
}

float ResolveHistoryWeight(float HistorySetting, float Coverage, float ValidWeight)
{
    return saturate(HistorySetting) * Coverage * saturate(ValidWeight);
}

#undef TEMPORAL_UNROLL
#endif
