// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_TRANSPARENT_MATH_HLSLI
#define ENGINE_NEXT_TRANSPARENT_MATH_HLSLI

float TransparentLinearDepth(float DeviceDepth, float2 NearFar)
{
    if (!isfinite(DeviceDepth) || DeviceDepth < 0 || DeviceDepth > 1 ||
        !isfinite(NearFar.x) || !isfinite(NearFar.y) || NearFar.x <= 0 || NearFar.y <= NearFar.x)
    {
        return -1;
    }
    if (DeviceDepth == 0 || DeviceDepth == 1)
    {
        return DeviceDepth == 0 ? NearFar.y : NearFar.x;
    }
    float Distance = NearFar.x / (DeviceDepth + (NearFar.x / NearFar.y) * (1 - DeviceDepth));
    return isfinite(Distance) ? Distance : -1;
}

float TransparentDepthFade(float OpaqueDepth, float SurfaceDepth, float2 NearFar, float SoftDistance, bool Enabled)
{
    if (!isfinite(SoftDistance) || SoftDistance < 0 ||
        TransparentLinearDepth(SurfaceDepth, NearFar) < 0 || TransparentLinearDepth(OpaqueDepth, NearFar) < 0)
    {
        return 0;
    }
    if (!Enabled || SoftDistance == 0 || OpaqueDepth == 0)
    {
        return 1;
    }
    float Gap = TransparentLinearDepth(OpaqueDepth, NearFar) - TransparentLinearDepth(SurfaceDepth, NearFar);
    return saturate(Gap / SoftDistance);
}

float TransparentEffectiveAlpha(float Alpha, float Fade)
{
    return isfinite(Alpha) && isfinite(Fade) ? saturate(Alpha) * saturate(Fade) : 0;
}

float4 TransparentPremultiply(float3 Color, float EffectiveAlpha)
{
    float Alpha = TransparentEffectiveAlpha(EffectiveAlpha, 1);
    Color = all(isfinite(Color)) ? clamp(Color, 0, 65504) : float3(0, 0, 0);
    return float4(Color * Alpha, Alpha);
}

#endif
