// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_RAY_REFLECTION_SAMPLING
#define ENGINE_NEXT_RAY_REFLECTION_SAMPLING

static const uint RT_MISS_ID = 0xffffffffu;
static const uint RT_INVALID_ID = 0xfffffffeu;

struct RtSurface
{
    float Depth;
    float3 Normal;
    float Roughness;
    uint Object;
};

struct RtHit
{
    uint Object;
    float Distance;
};

struct RtHistoryParameters
{
    float DepthThreshold;
    float NormalThreshold;
    float RoughnessThreshold;
    float Weight;
    uint Maximum;
};

uint RtHash(uint Value)
{
    Value ^= Value >> 16u;
    Value *= 0x7feb352du;
    Value ^= Value >> 15u;
    Value *= 0x846ca68bu;
    return Value ^ (Value >> 16u);
}

// Midpoints of binary32-exact 23-bit bins avoid singular zero/one samples.
float RtRandom(uint Seed)
{
    return (float(RtHash(Seed) >> 9u) + 0.5f) * (1.0f / 8388608.0f);
}

float3 RtUnit(float3 Direction)
{
    if (!isfinite(Direction.x) || !isfinite(Direction.y) || !isfinite(Direction.z))
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

bool RtSurfaceMatches(RtSurface Current, RtSurface Previous, float ExpectedDepth, RtHistoryParameters Parameters)
{
    if (Current.Object == 0 || Current.Object != Previous.Object ||
        !isfinite(Current.Depth) || Current.Depth <= 0 || !isfinite(ExpectedDepth) || ExpectedDepth <= 0 ||
        !isfinite(Previous.Depth) || Previous.Depth <= 0 || !isfinite(Current.Roughness) || !isfinite(Previous.Roughness))
    {
        return false;
    }
    float3 N = RtUnit(Current.Normal);
    float3 PreviousN = RtUnit(Previous.Normal);
    return dot(N, PreviousN) >= Parameters.NormalThreshold && dot(N, N) > 0 && dot(PreviousN, PreviousN) > 0 &&
        abs(ExpectedDepth - Previous.Depth) <= Parameters.DepthThreshold * max(ExpectedDepth, Previous.Depth) &&
        abs(Current.Roughness - Previous.Roughness) <= Parameters.RoughnessThreshold;
}

float RtHitConfidence(RtHit Current, RtHit Previous, float Roughness)
{
    if (Current.Object == RT_INVALID_ID || Previous.Object == RT_INVALID_ID || !isfinite(Roughness))
    {
        return 0;
    }
    if (Current.Object == RT_MISS_ID || Previous.Object == RT_MISS_ID)
    {
        return Current.Object == Previous.Object ? 1.0f : 0.0f;
    }
    if (!isfinite(Current.Distance) || Current.Distance <= 0 || !isfinite(Previous.Distance) || Previous.Distance <= 0)
    {
        return 0;
    }
    if (Current.Object != Previous.Object)
    {
        return Roughness >= 0.4f ? 0.25f : 0.0f;
    }
    float Relative = abs(Current.Distance - Previous.Distance) / max(Current.Distance, Previous.Distance);
    float Limit = 0.02f + saturate(Roughness) * saturate(Roughness);
    return saturate(1 - Relative / Limit);
}

float RtHistoryWeight(float PreviousCount, float Confidence, RtHistoryParameters Parameters)
{
    if (!isfinite(PreviousCount) || !isfinite(Confidence) || !isfinite(Parameters.Weight) ||
        PreviousCount <= 0 || Parameters.Maximum == 0)
    {
        return 0;
    }
    float Count = min(PreviousCount, float(Parameters.Maximum));
    return min(saturate(Parameters.Weight), Count / (Count + 1)) * saturate(Confidence);
}

float RtHistoryTapWeight(float FilterWeight, float HitConfidence)
{
    if (!isfinite(FilterWeight) || !isfinite(HitConfidence))
    {
        return 0;
    }
    return saturate(FilterWeight) * saturate(HitConfidence);
}

float2 RtPreviousGridCoordinate(float2 CurrentPixel, float2 Motion, float2 Dimensions)
{
    // The ray result belongs to the unjittered output grid cell, although its
    // surface metadata is sampled from the nearest full-resolution texel.
    // Reprojecting that texel's center instead introduces a quarter-cell drift
    // at half resolution, even when both geometry and camera are stationary.
    return float2(CurrentPixel.x + Motion.x * Dimensions.x, CurrentPixel.y + Motion.y * Dimensions.y);
}

float RtFiniteValue(float Value)
{
    // Keep signed values for history clipping and all intermediate arithmetic
    // finite. Physical radiance is clamped nonnegative only at its producer.
    return isnan(Value) ? 0.0f : clamp(Value, -1.0e20f, 1.0e20f);
}

float RtSignedLogLuminance(float3 Color)
{
    float Luminance = RtFiniteValue(Color.x) * 0.2126f + RtFiniteValue(Color.y) * 0.7152f + RtFiniteValue(Color.z) * 0.0722f;
    return (Luminance < 0 ? -1.0f : 1.0f) * log2(1 + abs(Luminance));
}

float2 RtUpdateMoments(float2 Previous, float3 Color, float Weight)
{
    float Value = RtSignedLogLuminance(Color);
    if (!isfinite(Weight) || !isfinite(Previous.x) || !isfinite(Previous.y))
    {
        return float2(Value, Value * Value);
    }
    Weight = saturate(Weight);
    return float2(lerp(Value, Previous.x, Weight), lerp(Value * Value, Previous.y, Weight));
}

float RtVariance(float2 Moments)
{
    return isfinite(Moments.x) && isfinite(Moments.y) ? max(Moments.y - Moments.x * Moments.x, 0.0f) : 0.0f;
}

float RtClipHistory(float History, float Minimum, float Maximum)
{
    Minimum = RtFiniteValue(Minimum);
    Maximum = RtFiniteValue(Maximum);
    float Lower = min(Minimum, Maximum);
    float Upper = max(Minimum, Maximum);
    return clamp(RtFiniteValue(History), Lower, Upper);
}

float RtSpatialWeight(float NormalDot, float RelativeDepth, float RoughnessDifference,
    float LuminanceDifference, float Variance, float HitConfidence, bool SameObject)
{
    if (!SameObject || !isfinite(NormalDot) || !isfinite(RelativeDepth) || !isfinite(RoughnessDifference) ||
        !isfinite(LuminanceDifference) || !isfinite(Variance) || !isfinite(HitConfidence) || NormalDot <= 0)
    {
        return 0;
    }
    float Sigma = max(sqrt(max(Variance, 0.0f)), 0.05f);
    return pow(saturate(NormalDot), 32.0f) *
        exp2(-64 * abs(RelativeDepth) - 16 * abs(RoughnessDifference) - abs(LuminanceDifference) / (3 * Sigma)) * saturate(HitConfidence);
}

#endif
