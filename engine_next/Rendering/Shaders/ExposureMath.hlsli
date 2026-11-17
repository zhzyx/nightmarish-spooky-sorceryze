// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_EXPOSURE_MATH_HLSLI
#define ENGINE_NEXT_EXPOSURE_MATH_HLSLI

#ifdef __cplusplus
#define ENGINE_NEXT_EXPOSURE_INOUT(Type, Name) Type &Name
#else
#define ENGINE_NEXT_EXPOSURE_INOUT(Type, Name) inout Type Name
#endif

static const uint EXPOSURE_BIN_COUNT = 256;
static const float EXPOSURE_LOG_MIN = -16.0f;
static const float EXPOSURE_LOG_MAX = 24.0f;
static const float EXPOSURE_CALIBRATION_FACTOR = 1.2f;

bool ValidExposureMultiplier(float Value)
{
    return isfinite(Value) && Value >= 1.175494351e-38f && Value <= 3.402823466e38f;
}

float ExposureBinLogLuminance(uint Bin)
{
    return EXPOSURE_LOG_MIN + (float(Bin) + 0.5f) * ((EXPOSURE_LOG_MAX - EXPOSURE_LOG_MIN) / float(EXPOSURE_BIN_COUNT));
}

// Returns 256 for invalid HDR or pre-exposure, for a separate diagnostic count.
// Subtracting logarithms avoids overflow when undoing a very small pre-exposure.
uint ExposureHistogramBin(float3 Color, float PreExposure)
{
    if (!isfinite(Color.x) || !isfinite(Color.y) || !isfinite(Color.z) ||
        Color.x < 0 || Color.y < 0 || Color.z < 0 || !ValidExposureMultiplier(PreExposure))
    {
        return EXPOSURE_BIN_COUNT;
    }
    float Luminance = Color.x * 0.2126f + Color.y * 0.7152f + Color.z * 0.0722f;
    if (!isfinite(Luminance))
    {
        return EXPOSURE_BIN_COUNT;
    }
    if (Luminance <= 0)
    {
        return 0;
    }
    float LogLuminance = log2(Luminance) - log2(PreExposure);
    float UnitLuminance = saturate((LogLuminance - EXPOSURE_LOG_MIN) / (EXPOSURE_LOG_MAX - EXPOSURE_LOG_MIN));
    return min(uint(UnitLuminance * float(EXPOSURE_BIN_COUNT)), EXPOSURE_BIN_COUNT - 1);
}

// The last two uints contain invalid and finite pixel counts, respectively.
// Only finite pixels contribute to cumulative ranks and the logarithmic mean.
bool ReduceExposureHistogram(StructuredBuffer<uint> Histogram, float Low, float High,
    ENGINE_NEXT_EXPOSURE_INOUT(float, LogLuminance))
{
    uint Total = Histogram[EXPOSURE_BIN_COUNT + 1];
    if (Total == 0 || !isfinite(Low) || !isfinite(High) || Low < 0 || High > 1 || Low > High)
    {
        return false;
    }
    float LowRank = Low * float(Total);
    float HighRank = High * float(Total);
    bool Collapsed = LowRank >= HighRank;
    uint Before = 0;
    float WeightedLog = 0;
    float Weight = 0;
    float FallbackLog = EXPOSURE_LOG_MIN;
    bool FoundFallback = false;
    for (uint Bin = 0; Bin < EXPOSURE_BIN_COUNT; ++Bin)
    {
        uint Count = Histogram[Bin];
        uint After = Before + Count;
        float BinLog = ExposureBinLogLuminance(Bin);
        if (Count != 0 && !FoundFallback)
        {
            FallbackLog = BinLog;
            FoundFallback = float(After) > LowRank;
        }
        float Included = max(0.0f, min(float(After), HighRank) - max(float(Before), LowRank));
        WeightedLog += Included * BinLog;
        Weight += Included;
        Before = After;
    }
    if (Collapsed)
    {
        LogLuminance = FallbackLog;
        return true;
    }
    if (Weight <= 0 || !isfinite(WeightedLog))
    {
        return false;
    }
    LogLuminance = clamp(WeightedLog / Weight, EXPOSURE_LOG_MIN, EXPOSURE_LOG_MAX);
    return true;
}

float AdaptExposure(float Previous, float Target, float DeltaSeconds, float LightHalfLife, float DarkHalfLife)
{
    if (DeltaSeconds <= 0)
    {
        return Previous;
    }
    float HalfLife = Target < Previous ? LightHalfLife : DarkHalfLife;
    if (HalfLife <= 0)
    {
        return Target;
    }
    float Alpha = saturate(1 - exp2(-min(DeltaSeconds, 0.1f) / HalfLife));
    float Result = exp2(lerp(log2(Previous), log2(Target), Alpha));
    return clamp(Result, min(Previous, Target), max(Previous, Target));
}

// Output is {display exposure En, this frame's pre-exposure Pn, target EV, meter L}.
// Pn is always the previous record's En. Empty/invalid metering preserves En.
float4 ResolveExposure(StructuredBuffer<uint> Histogram, float4 Previous, float4 Adaptation,
    float4 Metering, float4 Control)
{
    float Seed = ValidExposureMultiplier(Control.w) ? Control.w : 1.0f;
    float PreExposure = ValidExposureMultiplier(Previous.x) ? Previous.x : Seed;
    float PreviousEv = -log2(PreExposure) - log2(EXPOSURE_CALIBRATION_FACTOR);
    float4 Result = float4(PreExposure, PreExposure, PreviousEv, 0);
    if (Control.x == 0 || Control.x == 1)
    {
        if (ValidExposureMultiplier(Control.y))
        {
            Result.x = Control.y;
            Result.z = -log2(Control.y) - log2(EXPOSURE_CALIBRATION_FACTOR);
        }
        return Result;
    }
    if (Control.x != 2 || !isfinite(Control.z) || Control.z < -10 || Control.z > 10 ||
        !isfinite(Metering.z) || !isfinite(Metering.w) || Metering.z < -16 || Metering.w > 24 || Metering.z > Metering.w ||
        !isfinite(Adaptation.x) || Adaptation.x < 0 || !isfinite(Adaptation.y) || Adaptation.y < 0 || Adaptation.y > 10 ||
        !isfinite(Adaptation.z) || Adaptation.z < 0 || Adaptation.z > 10)
    {
        return Result;
    }
    float LogLuminance = 0;
    if (!ReduceExposureHistogram(Histogram, Metering.x, Metering.y, LogLuminance))
    {
        return Result;
    }
    float TargetEv = clamp(LogLuminance - log2(0.18f * EXPOSURE_CALIBRATION_FACTOR) - Control.z, Metering.z, Metering.w);
    float Target = exp2(-TargetEv) / EXPOSURE_CALIBRATION_FACTOR;
    Result.x = Adaptation.w > 0.5f ? Target : AdaptExposure(PreExposure, Target, Adaptation.x, Adaptation.y, Adaptation.z);
    Result.z = TargetEv;
    Result.w = exp2(LogLuminance);
    return Result;
}

#undef ENGINE_NEXT_EXPOSURE_INOUT
#endif
