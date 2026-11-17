// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "ExposureMath.hlsli"

cbuffer ExposureConstants : register(b0)
{
    float4 Viewport;
    float4 Adaptation;
    float4 Metering;
    float4 Exposure;
};

#ifdef HISTOGRAM_STAGE
Texture2D<float4> HdrColor : register(t0);
StructuredBuffer<float4> ExposureRead : register(t1);
RWStructuredBuffer<uint> Histogram : register(u0);
groupshared uint GroupHistogram[256];
groupshared uint GroupInvalid;
groupshared uint GroupFinite;

// Caller clears all 258 global counters before this dispatch, with a UAV barrier.
// Viewport pixel count must fit uint32. Edge groups retain uniform sync control.
[numthreads(16, 16, 1)]
void HistogramBuildCS(uint3 DispatchId : SV_DispatchThreadID, uint GroupIndex : SV_GroupIndex)
{
    GroupHistogram[GroupIndex] = 0;
    if (GroupIndex == 0)
    {
        GroupInvalid = 0;
        GroupFinite = 0;
    }
    GroupMemoryBarrierWithGroupSync();
    if (DispatchId.x < uint(Viewport.x) && DispatchId.y < uint(Viewport.y))
    {
        uint Bin = ExposureHistogramBin(HdrColor.Load(int3(DispatchId.xy, 0)).rgb, ExposureRead[0].x);
        if (Bin < EXPOSURE_BIN_COUNT)
        {
            InterlockedAdd(GroupHistogram[Bin], 1);
            InterlockedAdd(GroupFinite, 1);
        }
        else
        {
            InterlockedAdd(GroupInvalid, 1);
        }
    }
    GroupMemoryBarrierWithGroupSync();
    InterlockedAdd(Histogram[GroupIndex], GroupHistogram[GroupIndex]);
    if (GroupIndex == 0)
    {
        InterlockedAdd(Histogram[256], GroupInvalid);
        InterlockedAdd(Histogram[257], GroupFinite);
    }
}
#else
StructuredBuffer<uint> Histogram : register(t0);
StructuredBuffer<float4> ExposureRead : register(t1);
RWStructuredBuffer<float4> ExposureWrite : register(u0);

// A single invocation scans exactly 256 counters and writes one persistent record.
[numthreads(1, 1, 1)]
void ExposureAdaptCS(uint3 DispatchId : SV_DispatchThreadID)
{
    if (any(DispatchId != 0))
    {
        return;
    }
    ExposureWrite[0] = ResolveExposure(Histogram, ExposureRead[0], Adaptation, Metering, Exposure);
}
#endif
