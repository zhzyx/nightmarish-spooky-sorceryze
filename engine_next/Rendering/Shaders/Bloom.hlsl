// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer BloomConstants : register(b0)
{
    float4 Destination;
    float4 Source;
    float4 Parameters;
    float4 Modes;
};
Texture2D<float4> SourceColor : register(t0);
Texture2D<float4> LowerColor : register(t1);
StructuredBuffer<float4> ExposureRead : register(t2);
StructuredBuffer<float4> ExposureWrite : register(t3);
RWTexture2D<float4> OutputColor : register(u0);
SamplerState LinearClamp : register(s0);

#include "BloomSampling.hlsli"

[numthreads(8, 8, 1)]
void DownsampleCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= (uint2)Destination.xy))
    {
        return;
    }
    float2 Uv = (float2(Thread.xy) + 0.5) * Destination.zw;
    OutputColor[Thread.xy] = float4(DownsampleBloom(Uv), 0);
}

[numthreads(8, 8, 1)]
void UpsampleCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= (uint2)Destination.xy))
    {
        return;
    }
    float2 Uv = (float2(Thread.xy) + 0.5) * Destination.zw;
    OutputColor[Thread.xy] = float4(UpsampleBloom(int2(Thread.xy), Uv), 0);
}
