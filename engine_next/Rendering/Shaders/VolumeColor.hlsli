// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_VOLUME_COLOR_HLSLI
#define ENGINE_NEXT_VOLUME_COLOR_HLSLI

float VolumeColorChannel(float Value)
{
    // Finite physical factors can overflow their final product. Preserve the
    // saturation limit independently in each channel while rejecting NaNs.
    return isnan(Value) ? 0 : clamp(Value, 0, 65504);
}

float3 VolumeColor(float3 Color)
{
    return float3(VolumeColorChannel(Color.x), VolumeColorChannel(Color.y), VolumeColorChannel(Color.z));
}

#endif
