// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_SHADOW_PAGE_RECEIVER_HLSLI
#define ENGINE_NEXT_SHADOW_PAGE_RECEIVER_HLSLI

#include "ShadowPageGpu.hlsli"
#include "ShadowReceiverPlane.hlsli"

Texture2DArray<float> ShadowPhysicalPages : register(t32);
StructuredBuffer<ShadowPageEntry> ShadowPageTable : register(t33);

bool SampleVirtualShadow(float3 Position, float3 Normal, float3 GeometricNormal, uint Cascade,
    float NormalBias, float DepthBias, out float Visibility)
{
    Visibility = 1;
    float3 Biased = Position + Normal * NormalBias;
    float4 Clip = mul(PageShadowProjection[Cascade], float4(Biased, 1));
    if (PageViewport.w < 0.5f || !all(isfinite(Clip)) || Clip.w == 0)
    {
        return false;
    }
    float2 Projected = Clip.xy / Clip.w;
    float2 Uv = Projected * float2(0.5, -0.5) + 0.5;
    if (any(Uv < 0) || any(Uv >= 1))
    {
        return false;
    }
    uint2 Page = uint2(floor(Uv * PageDimensions.y));
    uint Address = Cascade * PageDimensions.y * PageDimensions.y + Page.y * PageDimensions.y + Page.x;
    ShadowPageEntry Entry = ShadowPageTable[Address];
    if (Entry.PhysicalPlusOne == 0)
    {
        return false;
    }
    float StoredDepth = dot(Entry.DepthPlane, float4(Biased, 1));
    if (!isfinite(StoredDepth) || StoredDepth < 0 || StoredDepth > 1)
    {
        return false;
    }
    float3 CurrentDepthRow = PageShadowProjection[Cascade][2].xyz;
    float CurrentDepthScale = length(CurrentDepthRow);
    float StoredBias = CurrentDepthScale > 0 ? DepthBias * length(Entry.DepthPlane.xyz) / CurrentDepthScale : DepthBias;
    float2 Gradient = ShadowReceiverGradient(PageShadowProjection[Cascade][0].xyz,
        PageShadowProjection[Cascade][1].xyz, Entry.DepthPlane.xyz, GeometricNormal);
    int2 GlobalPixel = int2(floor(Uv * PageDimensions.x));
    int2 LocalPixel = GlobalPixel - int2(Page) * 128 + int(PageDimensions.w);
    float Sum = 0;
    [unroll] for (int Y = -1; Y <= 1; ++Y)
    {
        [unroll] for (int X = -1; X <= 1; ++X)
        {
            int2 Offset = int2(X, Y);
            float2 PixelClip = (float2(GlobalPixel + Offset) + 0.5) * (2.0f / PageDimensions.x) - 1;
            PixelClip.y = -PixelClip.y;
            float Reference = ShadowReceiverDepth(float3(Projected, StoredDepth), PixelClip, Gradient, StoredBias);
            float Sample = ShadowPhysicalPages.Load(int4(LocalPixel + Offset, Entry.PhysicalPlusOne - 1, 0));
            Sum += Reference >= Sample ? 1 : 0;
        }
    }
    Visibility = Sum / 9;
    return true;
}

#endif
