// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "ShadowPageGpu.hlsli"

Texture2D<float> ReceiverDepth : register(t0);
StructuredBuffer<ShadowPageEntry> PageTable : register(t1);
// Header: valid receivers, mapped center receivers, missing center receivers,
// rejected world reconstruction. Coverage words follow the four-word header.
RWStructuredBuffer<uint> Requests : register(u0);

void RequestCascade(float3 Position, uint Cascade, bool Primary)
{
    float4 Clip = mul(PageShadowProjection[Cascade], float4(Position, 1));
    if (!all(isfinite(Clip)) || Clip.w == 0)
    {
        return;
    }
    float2 Uv = Clip.xy / Clip.w * float2(0.5, -0.5) + 0.5;
    if (any(Uv < 0) || any(Uv >= 1))
    {
        return;
    }
    uint Axis = PageDimensions.y;
    int2 Page = int2(floor(Uv * Axis));
    uint Center = Cascade * Axis * Axis + uint(Page.y) * Axis + uint(Page.x);
    if (Primary)
    {
        InterlockedAdd(Requests[PageTable[Center].PhysicalPlusOne == 0 ? 2 : 1], 1);
    }
    [unroll] for (int Y = -1; Y <= 1; ++Y)
    {
        [unroll] for (int X = -1; X <= 1; ++X)
        {
            int2 Neighbor = Page + int2(X, Y);
            if (all(Neighbor >= 0) && all(Neighbor < int(Axis)))
            {
                uint Address = 4 + Cascade * Axis * Axis + uint(Neighbor.y) * Axis + uint(Neighbor.x);
                InterlockedAdd(Requests[Address], 1);
            }
        }
    }
}

[numthreads(8, 8, 1)]
void FeedbackCS(uint3 Thread : SV_DispatchThreadID)
{
    if (any(Thread.xy >= uint2(PageViewport.xy)))
    {
        return;
    }
    float Depth = ReceiverDepth.Load(int3(Thread.xy, 0));
    if (!isfinite(Depth) || Depth <= 0)
    {
        return;
    }
    float2 Uv = (float2(Thread.xy) + 0.5) / PageViewport.xy;
    float4 World = mul(PageInverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), Depth, 1));
    if (!all(isfinite(World)) || World.w == 0)
    {
        InterlockedAdd(Requests[3], 1);
        return;
    }
    float3 Position = World.xyz / World.w;
    float Distance = -mul(PageView, float4(Position, 1)).z;
    if (!isfinite(Distance) || Distance <= 0 || Distance > PageSplits.w)
    {
        return;
    }
    uint Cascade = Distance > PageSplits.x ? 1 : 0;
    Cascade = Distance > PageSplits.y ? 2 : Cascade;
    Cascade = Distance > PageSplits.z ? 3 : Cascade;
    InterlockedAdd(Requests[0], 1);
    RequestCascade(Position, Cascade, true);
    if (Cascade < 3)
    {
        float Start = Cascade == 0 ? 0 : PageSplits[Cascade - 1];
        float Width = (PageSplits[Cascade] - Start) * PageViewport.z;
        if (Distance >= PageSplits[Cascade] - Width)
        {
            RequestCascade(Position, Cascade + 1, false);
        }
    }
}
