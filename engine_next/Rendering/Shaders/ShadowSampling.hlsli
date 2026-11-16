// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_SHADOW_SAMPLING_HLSLI
#define ENGINE_NEXT_SHADOW_SAMPLING_HLSLI

#ifdef __cplusplus
#define ENGINE_NEXT_SHADOW_UNROLL
#else
#define ENGINE_NEXT_SHADOW_UNROLL [unroll]
#endif

// Positive light-view distances. Reverse-Z maps NearFar.x to one and .y to zero.
float ShadowViewDistance(float Depth, float2 NearFar, bool Orthographic)
{
    if (Depth <= 0)
    {
        return NearFar.y;
    }
    if (Depth >= 1)
    {
        return NearFar.x;
    }
    if (Orthographic)
    {
        return NearFar.y - Depth * (NearFar.y - NearFar.x);
    }
    return NearFar.x / (Depth + (NearFar.x / NearFar.y) * (1 - Depth));
}

uint ShadowCubeFace(float3 Direction)
{
    float3 Absolute = abs(Direction);
    if (Absolute.x >= Absolute.y && Absolute.x >= Absolute.z)
    {
        return Direction.x >= 0 ? 0 : 1;
    }
    if (Absolute.y >= Absolute.z)
    {
        return Direction.y >= 0 ? 2 : 3;
    }
    return Direction.z >= 0 ? 4 : 5;
}

float3 ShadowCubeDirection(float2 Projected, uint Face)
{
    if (Face == 0) return float3(1, Projected.y, Projected.x);
    if (Face == 1) return float3(-1, Projected.y, -Projected.x);
    if (Face == 2) return float3(-Projected.x, 1, -Projected.y);
    if (Face == 3) return float3(-Projected.x, -1, Projected.y);
    if (Face == 4) return float3(-Projected.x, Projected.y, 1);
    return float3(Projected.x, Projected.y, -1);
}

float2 ShadowCubeProjection(float3 Direction, uint Face)
{
    float Major = Face < 2 ? abs(Direction.x) : (Face < 4 ? abs(Direction.y) : abs(Direction.z));
    if (Face == 0) return float2(Direction.z, Direction.y) / Major;
    if (Face == 1) return float2(-Direction.z, Direction.y) / Major;
    if (Face == 2) return float2(-Direction.x, -Direction.z) / Major;
    if (Face == 3) return float2(-Direction.x, Direction.z) / Major;
    if (Face == 4) return float2(-Direction.x, Direction.y) / Major;
    return float2(Direction.x, Direction.y) / Major;
}

// Returns radial blocker and receiver distances on the actual fetched texel ray.
float2 PointShadowDistances(Texture2DArray<float> ShadowMap, float3 Ray, uint FirstSlice,
    int Resolution, float2 NearFar, float3 CenterVector, float3 ReceiverNormal)
{
    uint Face = ShadowCubeFace(Ray);
    float2 Uv = ShadowCubeProjection(Ray, Face) * float2(0.5, -0.5) + 0.5;
    int2 Pixel = clamp(int2(Uv * Resolution), int2(0, 0), int2(Resolution - 1, Resolution - 1));
    float2 PixelClip = (float2(Pixel.x, Pixel.y) + 0.5) * (2.0 / Resolution) - 1;
    PixelClip.y = -PixelClip.y;
    float3 TexelVector = ShadowCubeDirection(PixelClip, Face);
    float TexelLength = length(TexelVector);
    float3 TexelRay = TexelVector / TexelLength;
    float ReceiverDistance = length(CenterVector);
    if (dot(ReceiverNormal, ReceiverNormal) > 0)
    {
        float Denominator = dot(ReceiverNormal, TexelRay);
        if (abs(Denominator) < 0.000001)
        {
            return float2(0, 0);
        }
        ReceiverDistance = dot(ReceiverNormal, CenterVector) / Denominator;
        if (ReceiverDistance <= 0)
        {
            return float2(0, 0);
        }
    }
    float Depth = ShadowMap.Load(int4(Pixel, FirstSlice + Face, 0));
    float BlockerDistance = Depth > 0 ? ShadowViewDistance(Depth, NearFar, false) * TexelLength : 0;
    return float2(BlockerDistance, ReceiverDistance);
}

float SamplePointShadow(Texture2DArray<float> ShadowMap, float3 Projected, uint Slice,
    int Resolution, float DepthBias, float LightRadius, float2 NearFar, bool Pcss, uint Face, float3 ReceiverNormal)
{
    float3 CenterDirection = ShadowCubeDirection(Projected.xy, Face);
    float DirectionLength = length(CenterDirection);
    float CenterDistance = ShadowViewDistance(Projected.z, NearFar, false) * DirectionLength;
    float BiasedDistance = ShadowViewDistance(saturate(Projected.z + max(DepthBias, 0)), NearFar, false) * DirectionLength;
    float BiasDistance = max(CenterDistance - BiasedDistance, 0);
    float3 CenterVector = CenterDirection * (CenterDistance / DirectionLength);
    float3 Forward = CenterDirection / DirectionLength;
    // Reflect the basis toward the nearer Z pole, keeping the denominator >= 1.
    float Pole = Forward.z >= 0 ? 1.0f : -1.0f;
    float A = -1 / (Pole + Forward.z);
    float B = Forward.x * Forward.y * A;
    float3 Tangent = float3(1 + Pole * Forward.x * Forward.x * A, Pole * B, -Pole * Forward.x);
    float3 Bitangent = float3(B, Pole + Forward.y * Forward.y * A, -Forward.y);
    float TexelAngle = 2.0f / Resolution;
    uint FirstSlice = Slice - Face;
    if (!Pcss)
    {
        float Visibility = 0;
        ENGINE_NEXT_SHADOW_UNROLL for (int Y = -1; Y <= 1; ++Y)
        {
            ENGINE_NEXT_SHADOW_UNROLL for (int X = -1; X <= 1; ++X)
            {
                float3 Ray = Forward + Tangent * (X * TexelAngle) + Bitangent * (Y * TexelAngle);
                float2 Distances = PointShadowDistances(ShadowMap, Ray, FirstSlice, Resolution, NearFar, CenterVector, ReceiverNormal);
                Visibility += Distances.x == 0 || Distances.x + BiasDistance >= Distances.y ? 1 : 0;
            }
        }
        return Visibility / 9;
    }
    float EmitterRadius = LightRadius * (2.0f * NearFar.x / Resolution);
    float SearchAngle = clamp(EmitterRadius * (1 / NearFar.x - 1 / CenterDistance), TexelAngle, 32 * TexelAngle);
    float MeanBlockerDistance = 0;
    float BlockerCount = 0;
    ENGINE_NEXT_SHADOW_UNROLL for (int Y = -2; Y <= 2; ++Y)
    {
        ENGINE_NEXT_SHADOW_UNROLL for (int X = -2; X <= 2; ++X)
        {
            float3 Ray = Forward + Tangent * (X * SearchAngle * 0.5) + Bitangent * (Y * SearchAngle * 0.5);
            float2 Distances = PointShadowDistances(ShadowMap, Ray, FirstSlice, Resolution, NearFar, CenterVector, ReceiverNormal);
            if (Distances.x > 0 && Distances.y > 0 && Distances.x + BiasDistance < Distances.y)
            {
                BlockerCount += 1;
                MeanBlockerDistance += (Distances.x - MeanBlockerDistance) / BlockerCount;
            }
        }
    }
    if (BlockerCount == 0)
    {
        return 1;
    }
    float FilterAngle = clamp(EmitterRadius * max(1 / MeanBlockerDistance - 1 / CenterDistance, 0), TexelAngle, 32 * TexelAngle);
    float Visibility = 0;
    ENGINE_NEXT_SHADOW_UNROLL for (int Y = -2; Y <= 2; ++Y)
    {
        ENGINE_NEXT_SHADOW_UNROLL for (int X = -2; X <= 2; ++X)
        {
            float3 Ray = Forward + Tangent * (X * FilterAngle * 0.5) + Bitangent * (Y * FilterAngle * 0.5);
            float2 Distances = PointShadowDistances(ShadowMap, Ray, FirstSlice, Resolution, NearFar, CenterVector, ReceiverNormal);
            Visibility += Distances.x == 0 || Distances.x + BiasDistance >= Distances.y ? 1 : 0;
        }
    }
    return Visibility / 25;
}

// LightRadius is an emitter radius in shadow-map texels at the near plane.
// Perspective callers project a world radius R as R * abs(P[0][0]) * Resolution / (2 * NearFar.x).
// Orthographic callers project R as R * abs(P[0][0]) * Resolution / 2.
// PCSS models a finite disc emitter at light-view distance zero. Directional PCF
// does not use LightRadius or NearFar. Radius saturation bounds all reads to 32 texels.
float SampleShadowMap(Texture2DArray<float> ShadowMap, float3 Projected, uint Slice,
    float Resolution, float DepthBias, float LightRadius, float2 NearFar, bool Orthographic, bool Pcss, uint PointFace = 6, float3 ReceiverNormal = float3(0, 0, 0))
{
    if (!all(isfinite(Projected)) || !isfinite(Resolution) || !isfinite(DepthBias) ||
        Resolution < 1 || any(abs(Projected.xy) > 1) || Projected.z < 0 || Projected.z > 1)
    {
        return 1;
    }
    uint Width, Height, Layers;
    ShadowMap.GetDimensions(Width, Height, Layers);
    if (Width == 0 || Height == 0 || Slice >= Layers || Resolution != (float)Width || Width != Height)
    {
        return 1;
    }
    if (PointFace < 6 && (Slice < PointFace || Layers < 6 || Slice - PointFace > Layers - 6 || Orthographic ||
        !all(isfinite(NearFar)) || NearFar.x <= 0 || NearFar.y <= NearFar.x))
    {
        return 1;
    }
    if (PointFace < 6)
    {
        if (!isfinite(LightRadius) || LightRadius < 0 || !all(isfinite(ReceiverNormal)))
        {
            return 1;
        }
        return SamplePointShadow(ShadowMap, Projected, Slice, (int)Width, DepthBias, LightRadius, NearFar, Pcss, PointFace, ReceiverNormal);
    }
    float2 Uv = Projected.xy * float2(0.5, -0.5) + 0.5;
    int2 Center = int2(Uv * Resolution);
    float ReceiverDepth = saturate(Projected.z + max(DepthBias, 0));
    if (!Pcss)
    {
        float Visibility = 0;
        ENGINE_NEXT_SHADOW_UNROLL for (int Y = -1; Y <= 1; ++Y)
        {
            ENGINE_NEXT_SHADOW_UNROLL for (int X = -1; X <= 1; ++X)
            {
                float Depth = ShadowMap.Load(int4(clamp(Center + int2(X, Y), int2(0, 0), int2((int)Width - 1, (int)Height - 1)), Slice, 0));
                Visibility += ReceiverDepth >= Depth ? 1 : 0;
            }
        }
        return Visibility / 9;
    }
    if (!isfinite(LightRadius) || LightRadius < 0 || !all(isfinite(NearFar)) ||
        NearFar.x <= 0 || NearFar.y <= NearFar.x)
    {
        return 1;
    }
    float ReceiverDistance = ShadowViewDistance(Projected.z, NearFar, Orthographic);
    float SearchRadius = clamp(LightRadius * (1 - NearFar.x / ReceiverDistance), 1, 32);
    float MeanBlockerDistance = 0;
    float BlockerCount = 0;
    ENGINE_NEXT_SHADOW_UNROLL for (int Y = -2; Y <= 2; ++Y)
    {
        ENGINE_NEXT_SHADOW_UNROLL for (int X = -2; X <= 2; ++X)
        {
            int2 Offset = int2(round(float2(X, Y) * (SearchRadius * 0.5)));
            float Depth = ShadowMap.Load(int4(clamp(Center + Offset, int2(0, 0), int2((int)Width - 1, (int)Height - 1)), Slice, 0));
            if (Depth > ReceiverDepth)
            {
                float Distance = ShadowViewDistance(Depth, NearFar, Orthographic);
                BlockerCount += 1;
                MeanBlockerDistance += (Distance - MeanBlockerDistance) / BlockerCount;
            }
        }
    }
    if (BlockerCount == 0)
    {
        return 1;
    }
    float SeparationRatio = max(ReceiverDistance / MeanBlockerDistance - 1, 0);
    float FilterRadius = LightRadius == 0 ? 1 : clamp(Orthographic
        ? LightRadius * SeparationRatio
        : LightRadius * max(1 - MeanBlockerDistance / ReceiverDistance, 0) * (NearFar.x / MeanBlockerDistance), 1, 32);
    float Visibility = 0;
    ENGINE_NEXT_SHADOW_UNROLL for (int Y = -2; Y <= 2; ++Y)
    {
        ENGINE_NEXT_SHADOW_UNROLL for (int X = -2; X <= 2; ++X)
        {
            int2 Offset = int2(round(float2(X, Y) * (FilterRadius * 0.5)));
            float Depth = ShadowMap.Load(int4(clamp(Center + Offset, int2(0, 0), int2((int)Width - 1, (int)Height - 1)), Slice, 0));
            Visibility += ReceiverDepth >= Depth ? 1 : 0;
        }
    }
    return Visibility / 25;
}

#undef ENGINE_NEXT_SHADOW_UNROLL
#endif
