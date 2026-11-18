// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "AmbientOcclusionMath.hlsli"
cbuffer AmbientConstants : register(b0)
{
    column_major float4x4 ViewProjection;
    column_major float4x4 InverseViewProjection;
    float4 Camera;
    float4 Parameters;
    uint4 Counts;
    float4 Kernel[64];
};
cbuffer FilterConstants : register(b1)
{
    uint2 FilterAxis;
};
Texture2D<float> SceneDepth : register(t0);
Texture2D<float4> SceneNormal : register(t1);
Texture2D<float> SourceOcclusion : register(t2);
RWTexture2D<float> Destination : register(u0);

float3 Unit(float3 Value)
{
    float Maximum = max(abs(Value.x), max(abs(Value.y), abs(Value.z)));
    float3 Scaled = Value / max(Maximum, 1.0e-30);
    return Scaled * rsqrt(max(dot(Scaled, Scaled), 1.0e-20));
}

float3 PositionAt(uint2 Pixel, float Depth)
{
    float2 Uv = (float2(Pixel) + 0.5) / float2(Counts.xy);
    float4 Position = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    return Position.xyz / Position.w;
}

float3 NormalAt(uint2 Pixel)
{
    // The GBuffer stores signed world-space normals in a floating-point target.
    return Unit(SceneNormal.Load(int3(Pixel, 0)).xyz);
}

uint PixelHash(uint2 Pixel)
{
    uint Value = Pixel.x * 73856093u ^ Pixel.y * 19349663u ^ Counts.w * 83492791u;
    Value ^= Value >> 16;
    Value *= 2246822519u;
    Value ^= Value >> 13;
    return Value;
}

[numthreads(8, 8, 1)]
void AmbientOcclusionCS(uint3 Dispatch : SV_DispatchThreadID)
{
    uint2 Pixel = Dispatch.xy;
    if (any(Pixel >= Counts.xy))
    {
        return;
    }
    float Depth = SceneDepth.Load(int3(Pixel, 0));
    if (Depth <= 0 || Parameters.z <= 0)
    {
        Destination[Pixel] = 1;
        return;
    }
    float3 Position = PositionAt(Pixel, Depth);
    float3 Normal = NormalAt(Pixel);
    if (!all(isfinite(Position)) || dot(Normal, Normal) < 0.5)
    {
        Destination[Pixel] = 1;
        return;
    }
    float3 Up = abs(Normal.z) < 0.9 ? float3(0, 0, 1) : float3(0, 1, 0);
    float3 Tangent = Unit(cross(Up, Normal));
    float3 Bitangent = cross(Normal, Tangent);
    float Angle = (float(PixelHash(Pixel)) + 0.5) * (6.28318530718 / 4294967296.0);
    float Sine, Cosine;
    sincos(Angle, Sine, Cosine);
    float3 RotatedTangent = Tangent * Cosine + Bitangent * Sine;
    float3 RotatedBitangent = Bitangent * Cosine - Tangent * Sine;
    float Occlusion = 0;
    [loop] for (uint Index = 0; Index < Counts.z; ++Index)
    {
        float4 Sample = Kernel[Index];
        float3 Direction = RotatedTangent * Sample.x + RotatedBitangent * Sample.y + Normal * Sample.z;
        float3 Query = Position + Normal * Parameters.y + Direction * (Parameters.x * Sample.w);
        float4 Clip = mul(ViewProjection, float4(Query, 1));
        if (Clip.w <= 0 || !all(isfinite(Clip)))
        {
            continue;
        }
        float2 Uv = Clip.xy / Clip.w * float2(0.5, -0.5) + 0.5;
        if (any(Uv < 0) || any(Uv >= 1))
        {
            continue;
        }
        uint2 SamplePixel = min(uint2(Uv * Counts.xy), Counts.xy - 1);
        float SampleDepth = SceneDepth.Load(int3(SamplePixel, 0));
        if (SampleDepth <= 0)
        {
            continue;
        }
        float3 Surface = PositionAt(SamplePixel, SampleDepth);
        float Distance = length(Surface - Position);
        float Weight = saturate((Parameters.x - Distance) / max(Parameters.x * 0.5, 1.0e-20));
        float Separation = dot(Query - Surface, Unit(Query - Camera.xyz));
        float Hemisphere = dot(Surface - Position, Normal);
        Occlusion += Separation > Parameters.y && Hemisphere > Parameters.y * 0.25 && all(isfinite(Surface)) ? Weight : 0;
    }
    Destination[Pixel] = saturate(1 - Parameters.z * Occlusion / max(Counts.z, 1u));
}

[numthreads(8, 8, 1)]
void AmbientBlurCS(uint3 Dispatch : SV_DispatchThreadID)
{
    uint2 Pixel = Dispatch.xy;
    if (any(Pixel >= Counts.xy))
    {
        return;
    }
    float Depth = SceneDepth.Load(int3(Pixel, 0));
    if (Depth <= 0)
    {
        Destination[Pixel] = 1;
        return;
    }
    float3 Normal = NormalAt(Pixel);
    float Distance = length(PositionAt(Pixel, Depth) - Camera.xyz);
    if (!isfinite(Distance) || dot(Normal, Normal) < 0.5)
    {
        Destination[Pixel] = 1;
        return;
    }
    float OccludedWeight = 0;
    float WeightSum = 0;
    [unroll] for (int Offset = -2; Offset <= 2; ++Offset)
    {
        int2 SamplePixel = clamp(int2(Pixel) + Offset * int2(FilterAxis), int2(0, 0), int2(Counts.xy) - 1);
        float SampleDepth = SceneDepth.Load(int3(SamplePixel, 0));
        if (SampleDepth <= 0)
        {
            continue;
        }
        float SampleDistance = length(PositionAt(uint2(SamplePixel), SampleDepth) - Camera.xyz);
        float Weight = exp(-0.5 * Offset * Offset) * pow(saturate(dot(Normal, NormalAt(uint2(SamplePixel)))), 16);
        Weight *= exp(-abs(SampleDistance - Distance) / max(Parameters.x * 0.05, 0.001));
        OccludedWeight += AmbientOccludedWeight(SourceOcclusion.Load(int3(SamplePixel, 0)), Weight);
        WeightSum += Weight;
    }
    // Filtering occlusion preserves fully visible pixels exactly through R16 stores.
    Destination[Pixel] = AmbientFilteredVisibility(OccludedWeight, WeightSum);
}
