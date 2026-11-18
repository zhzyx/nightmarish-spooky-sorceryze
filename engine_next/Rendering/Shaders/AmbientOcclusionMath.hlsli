// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_AMBIENT_OCCLUSION_MATH_HLSLI
#define ENGINE_NEXT_AMBIENT_OCCLUSION_MATH_HLSLI

float AmbientOccludedWeight(float Visibility, float Weight)
{
    return (1 - Visibility) * Weight;
}

float AmbientFilteredVisibility(float OccludedWeight, float WeightSum)
{
    // A fully visible neighborhood has exactly zero occluded weight.
    return saturate(1 - OccludedWeight / max(WeightSum, 1.0e-20f));
}

#endif
