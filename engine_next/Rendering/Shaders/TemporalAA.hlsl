// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
cbuffer TemporalConstants : register(b0)
{
    float4 Viewport;
    float4 Jitter;
    float4 Settings;
    float4 Planes;
};
Texture2D<float4> CurrentHdr : register(t0);
Texture2D<float> CurrentDepth : register(t1);
Texture2D<float4> CurrentNormal : register(t2);
Texture2D<float4> CurrentMotion : register(t3);
Texture2D<uint> CurrentObjectId : register(t4);
Texture2D<float4> HistoryColor : register(t5);
Texture2D<float> HistoryDepth : register(t6);
Texture2D<float4> HistoryNormal : register(t7);
Texture2D<uint> HistoryObjectId : register(t8);
StructuredBuffer<float4> ExposureState : register(t9);
RWTexture2D<float4> OutputColor : register(u0);
RWTexture2D<float> OutputDepth : register(u1);
RWTexture2D<float4> OutputNormal : register(u2);
RWTexture2D<uint> OutputObjectId : register(u3);
#include "TemporalSampling.hlsli"

[numthreads(8, 8, 1)]
void CSMain(uint3 Thread : SV_DispatchThreadID)
{
    if (!all(isfinite(Viewport)) || any(Viewport.xy < 1) || any(Thread.xy >= (uint2)Viewport.xy))
    {
        return;
    }
    uint2 Pixel = Thread.xy;
    int2 MaximumPixel = (int2)Viewport.xy - 1;
    float2 OutputUv = (float2(Pixel) + 0.5) * Viewport.zw;
    // Positive projection jitter moves geometry right/down on the raster.
    float2 CurrentJitter = all(isfinite(Jitter.xy)) ? Jitter.xy : float2(0, 0);
    float2 CurrentUv = saturate(OutputUv + CurrentJitter * Viewport.zw);
    int2 CurrentPixel = clamp((int2)floor(CurrentUv * Viewport.xy), int2(0, 0), MaximumPixel);
    float3 Color = FiniteColor(CurrentHdr.Load(int3(CurrentPixel, 0)).rgb);
    float Depth = CurrentDepth.Load(int3(CurrentPixel, 0));
    uint ObjectId = CurrentObjectId.Load(int3(CurrentPixel, 0));
    float3 Normal = CurrentNormal.Load(int3(CurrentPixel, 0)).xyz;
    float LinearDepth = 0;
    float Coverage = 0;
    bool GeometryValid = isfinite(Depth) && Depth > 0 && Depth <= 1 && ObjectId != 0 && ValidNormal(Normal) &&
        all(isfinite(Planes.xy)) && Planes.x > 0 && Planes.y > Planes.x;
    if (GeometryValid)
    {
        LinearDepth = ViewDepth(Depth);
        GeometryValid = isfinite(LinearDepth) && LinearDepth > 0;
        if (GeometryValid)
        {
            Normal = normalize(Normal);
        }
    }
    if (!GeometryValid)
    {
        LinearDepth = 0;
        ObjectId = 0;
        Normal = float3(0, 0, 0);
    }
    if (GeometryValid || (ObjectId == 0 && isfinite(Depth) && Depth <= 0))
    {
        float4 Reconstructed = ReconstructCurrentColor(CurrentUv, CurrentPixel, ObjectId, LinearDepth, Normal);
        Color = Reconstructed.rgb;
        Coverage = Reconstructed.a;
    }
    // The reconstruction blends all finite current samples for edge coverage.
    // Alpha records the selected surface's fraction so temporal feedback can
    // reject changing coverage without treating this legitimate blend as opaque.
    OutputDepth[Pixel] = LinearDepth;
    OutputNormal[Pixel] = float4(Normal, 0);
    OutputObjectId[Pixel] = ObjectId;
    OutputColor[Pixel] = float4(Color, Coverage);
    if (!GeometryValid || !isfinite(LinearDepth) || !all(isfinite(Settings.xyz)) || Settings.x < 0.5 ||
        Settings.y <= 0 || Settings.z < 0 || !all(isfinite(Jitter.xy)))
    {
        return;
    }
    float4 Motion = CurrentMotion.Load(int3(CurrentPixel, 0));
    // Both history coordinates and the stored velocity use the unjittered grid.
    float2 PreviousUv = OutputUv + Motion.xy;
    if (!all(isfinite(Motion)) || Motion.w < 0.5 || Motion.z <= 0 ||
        any(PreviousUv < 0) || any(PreviousUv >= 1))
    {
        return;
    }
    float2 HistoryPixel = PreviousUv * Viewport.xy - 0.5;
    int2 HistoryBase = (int2)floor(HistoryPixel);
    float2 Fraction = frac(HistoryPixel);
    float4 HistorySum = float4(0, 0, 0, 0);
    [unroll] for (int Y = 0; Y < 2; ++Y)
    {
        [unroll] for (int X = 0; X < 2; ++X)
        {
            float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) * (Y == 0 ? 1 - Fraction.y : Fraction.y);
            int2 HistorySample = clamp(HistoryBase + int2(X, Y), int2(0, 0), MaximumPixel);
            HistorySum += ValidHistoryTap(HistorySample, ObjectId, Motion.z, Normal, Coverage, Weight);
        }
    }
    if (HistorySum.w <= 0.000001)
    {
        return;
    }
    float3 PreviousColor = HistorySum.rgb / HistorySum.w;
    float3 NeighborhoodMinimum = ToYCoCg(Color);
    float3 NeighborhoodMaximum = NeighborhoodMinimum;
    [unroll] for (int Y = -1; Y <= 1; ++Y)
    {
        [unroll] for (int X = -1; X <= 1; ++X)
        {
            int2 SamplePixel = clamp(CurrentPixel + int2(X, Y), int2(0, 0), MaximumPixel);
            float3 SampleColor = ToYCoCg(FiniteColor(CurrentHdr.Load(int3(SamplePixel, 0)).rgb));
            NeighborhoodMinimum = min(NeighborhoodMinimum, SampleColor);
            NeighborhoodMaximum = max(NeighborhoodMaximum, SampleColor);
        }
    }
    float3 ClippedHistory = clamp(ToYCoCg(FiniteColor(PreviousColor)), NeighborhoodMinimum, NeighborhoodMaximum);
    float HistoryWeight = ResolveHistoryWeight(Settings.y, Coverage, HistorySum.w);
    float3 Resolved = lerp(Color, FromYCoCg(ClippedHistory), HistoryWeight);
    OutputColor[Pixel] = float4(FiniteColor(Resolved), Coverage);
}
