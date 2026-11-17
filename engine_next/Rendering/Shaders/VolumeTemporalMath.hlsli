// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_VOLUME_TEMPORAL_MATH_HLSLI
#define ENGINE_NEXT_VOLUME_TEMPORAL_MATH_HLSLI

// Positive normal coefficients are compared proportionally. A disappearing
// medium cannot retain history through an absolute density tolerance.
bool VolumeDensityMatches(float Current, float Previous, float Tolerance)
{
    if (!isfinite(Current) || !isfinite(Previous) || !isfinite(Tolerance) ||
        Current < 0 || Previous < 0 || Tolerance < 0 || Tolerance > 1)
    {
        return false;
    }
    if (Current == 0 || Previous == 0)
    {
        return Current == Previous;
    }
    if (Current < 1.175494351e-38f || Previous < 1.175494351e-38f)
    {
        return false;
    }
    float Scale = max(Current, Previous);
    return abs(Current / Scale - Previous / Scale) <= Tolerance;
}

// Evaluate before clipping history to the current neighborhood. Component
// scaling keeps the length ratio meaningful for both weak and bright sources.
// Invalid or negative source radiance rejects history with difference one.
float VolumeRelativeSignalDifference(float3 Current, float3 Previous)
{
    if (!all(isfinite(Current)) || !all(isfinite(Previous)) || any(Current < 0) || any(Previous < 0))
    {
        return 1;
    }
    float Scale = max(max(Current.x, max(Current.y, Current.z)), max(Previous.x, max(Previous.y, Previous.z)));
    if (Scale == 0)
    {
        return 0;
    }
    if (Scale < 1.175494351e-38f)
    {
        return 1;
    }
    float3 CurrentScaled = Current / Scale;
    float3 PreviousScaled = Previous / Scale;
    float Denominator = max(length(CurrentScaled), length(PreviousScaled));
    return length(CurrentScaled - PreviousScaled) / Denominator;
}

#endif
