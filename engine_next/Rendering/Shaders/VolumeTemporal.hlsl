// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#include "VolumeCommon.hlsli"
#include "VolumeTemporalMath.hlsli"

cbuffer VolumeHistoryConstants : register(b2)
{
    column_major float4x4 PreviousView;
    column_major float4x4 PreviousVolumeViewProjection;
    float4 PreviousGrid;
    float4 PreviousDepthRange;
    // History weight, previous-to-current pre-exposure, history valid, density tolerance.
    float4 HistorySettings;
};

Texture3D<float4> CurrentSource : register(t0);
Texture3D<float4> PreviousSource : register(t1);
StructuredBuffer<float4> ExposureState : register(t4);
RWTexture3D<float4> FilteredSource : register(u0);
SamplerState LinearClamp : register(s0);

bool SampleVolumeHistory(float3 Uvw, float Density, out float3 Color)
{
    float3 Coordinate = Uvw * PreviousGrid.xyz - 0.5f;
    int3 First = int3(floor(Coordinate));
    float3 Fraction = frac(Coordinate);
    float3 Sum = 0;
    float Total = 0;
    [unroll] for (int Z = 0; Z < 2; ++Z)
    {
        [unroll] for (int Y = 0; Y < 2; ++Y)
        {
            [unroll] for (int X = 0; X < 2; ++X)
            {
                int3 Index = clamp(First + int3(X, Y, Z), int3(0, 0, 0), int3(PreviousGrid.xyz) - 1);
                float4 Sample = PreviousSource.Load(int4(Index, 0));
                float Weight = (X == 0 ? 1 - Fraction.x : Fraction.x) *
                    (Y == 0 ? 1 - Fraction.y : Fraction.y) * (Z == 0 ? 1 - Fraction.z : Fraction.z);
                bool DensityMatches = VolumeDensityMatches(Density, Sample.a, HistorySettings.w);
                if (all(isfinite(Sample)) && Sample.a >= 0 && DensityMatches)
                {
                    Sum += VolumeColor(Sample.rgb * (ExposureState[0].x / ExposureState[0].y)) * Weight;
                    Total += Weight;
                }
            }
        }
    }
    Color = Total > 0 ? Sum / Total : 0;
    return Total >= 0.5f;
}

[numthreads(4, 4, 4)]
void TemporalCS(uint3 Cell : SV_DispatchThreadID)
{
    if (any(Cell >= uint3(Grid.xyz)))
    {
        return;
    }
    float4 Current = CurrentSource.Load(int4(Cell, 0));
    if (!all(isfinite(Current)) || Current.a < 0)
    {
        FilteredSource[Cell] = 0;
        return;
    }
    float3 Position = VolumeWorldPosition(float2(Cell.xy), float(Cell.z) + 0.5f);
    float4 PreviousClip = mul(PreviousVolumeViewProjection, float4(Position, 1));
    float PreviousDistance = -mul(PreviousView, float4(Position, 1)).z;
    float Slice = 0;
    float Weight = 0;
    float3 History = Current.rgb;
    if (HistorySettings.z > 0.5f && all(isfinite(PreviousClip)) && PreviousClip.w > 0 &&
        all(isfinite(ExposureState[0].xy)) && all(ExposureState[0].xy >= 1.175494351e-38f) &&
        PreviousDistance >= PreviousDepthRange.x && PreviousDistance <= PreviousDepthRange.y &&
        VolumeSliceAtDepth(PreviousDepthRange.x, PreviousDepthRange.y, uint(PreviousGrid.z), PreviousDistance, Slice))
    {
        float3 Uvw = float3(PreviousClip.xy / PreviousClip.w * float2(0.5f, -0.5f) + 0.5f, Slice / PreviousGrid.z);
        if (all(Uvw >= 0) && all(Uvw <= 1))
        {
            float3 Sample;
            if (SampleVolumeHistory(Uvw, Current.a, Sample))
            {
                History = Sample;
                float Difference = VolumeRelativeSignalDifference(Current.rgb, History);
                float3 Minimum = Current.rgb;
                float3 Maximum = Current.rgb;
                [unroll] for (int Axis = 0; Axis < 3; ++Axis)
                {
                    [unroll] for (int Side = -1; Side <= 1; Side += 2)
                    {
                        int3 Neighbor = int3(Cell);
                        Neighbor[Axis] += Side;
                        Neighbor = clamp(Neighbor, int3(0, 0, 0), int3(Grid.xyz) - 1);
                        float3 Color = VolumeColor(CurrentSource.Load(int4(Neighbor, 0)).rgb);
                        Minimum = min(Minimum, Color);
                        Maximum = max(Maximum, Color);
                    }
                }
                History = clamp(History, Minimum, Maximum);
                Weight = saturate(HistorySettings.x) * (1 - smoothstep(0.25f, 1.0f, Difference));
            }
        }
    }
    FilteredSource[Cell] = float4(VolumeColor(lerp(Current.rgb, History, Weight)), Current.a);
}
