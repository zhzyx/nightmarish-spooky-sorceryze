// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_VOLUME_COMMON_HLSLI
#define ENGINE_NEXT_VOLUME_COMMON_HLSLI
#include "VolumeMath.hlsli"
#include "VolumeColor.hlsli"

cbuffer VolumeConstants : register(b0)
{
    float4 Grid;
    float4 DepthRange;
    float4 Viewport;
    float4 Parameters;
};

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

float3 VolumeSafeDirection(float3 Vector)
{
    float Scale = max(abs(Vector.x), max(abs(Vector.y), abs(Vector.z)));
    if (!all(isfinite(Vector)) || Scale <= 0)
    {
        return float3(0, 0, 0);
    }
    Vector /= Scale;
    return Vector / sqrt(dot(Vector, Vector));
}

// This works with the frame's asymmetric/jittered perspective projection.
float3 VolumeWorldPosition(float2 Cell, float Boundary)
{
    float Distance = DepthRange.x;
    VolumeDepthAtSlice(DepthRange.x, DepthRange.y, uint(Grid.z), Boundary, Distance);
    float2 Uv = (Cell + 0.5f) / Grid.xy;
    float4 World = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), 1, 1));
    if (!all(isfinite(World)) || abs(World.w) < 1.0e-12f)
    {
        return Camera.xyz;
    }
    float3 Ray = World.xyz / World.w - Camera.xyz;
    float ViewDepth = -mul((float3x3)View, Ray).z;
    return ViewDepth > 0 ? Camera.xyz + Ray * (Distance / ViewDepth) : Camera.xyz;
}


#endif
