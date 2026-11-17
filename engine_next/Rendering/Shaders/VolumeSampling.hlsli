// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_VOLUME_SAMPLING_HLSLI
#define ENGINE_NEXT_VOLUME_SAMPLING_HLSLI
#include "VolumeMath.hlsli"

// The caller declares the shared frame InverseViewProjection, View and Camera.
// Integrate each spatial column before interpolation so the nonlinear segment
// attenuation agrees with that column's stored cumulative integral.
float4 SampleVolumeColumn(Texture3D<float4> Integrated, Texture3D<float4> Source,
    int2 Column, float Distance, float3 GridSize, float2 NearFar)
{
    float Slice = 0;
    if (!VolumeSliceAtDepth(NearFar.x, NearFar.y, uint(GridSize.z), Distance, Slice))
    {
        return float4(0, 0, 0, 1);
    }
    uint Level = min(uint(floor(Slice)), uint(GridSize.z) - 1);
    Column = clamp(Column, int2(0, 0), int2(GridSize.xy) - 1);
    float4 Before = Level == 0 ? float4(0, 0, 0, 1) : Integrated.Load(int4(Column, Level - 1, 0));
    float StartDepth = NearFar.x;
    float EndDepth = NearFar.y;
    VolumeDepthAtSlice(NearFar.x, NearFar.y, uint(GridSize.z), float(Level), StartDepth);
    VolumeDepthAtSlice(NearFar.x, NearFar.y, uint(GridSize.z), float(Level + 1), EndDepth);
    StartDepth = Level == 0 ? 0 : StartDepth;
    float2 Uv = (float2(Column) + 0.5f) / GridSize.xy;
    float4 NearPoint = mul(InverseViewProjection, float4(Uv * float2(2, -2) + float2(-1, 1), 1, 1));
    if (!all(isfinite(NearPoint)) || abs(NearPoint.w) < 1.0e-12f)
    {
        return float4(0, 0, 0, 1);
    }
    float3 Ray = NearPoint.xyz / NearPoint.w - Camera.xyz;
    float ViewDepth = -mul((float3x3)View, Ray).z;
    float RayScale = ViewDepth > 0 ? length(Ray) / ViewDepth : 0;
    float SegmentLength = VolumePartialSegmentLength(Distance, StartDepth, EndDepth, RayScale);
    float4 Coefficients = Source.Load(int4(Column, Level, 0));
    VolumeIntegral R;
    VolumeIntegral G;
    VolumeIntegral B;
    R.Scatter = G.Scatter = B.Scatter = 0;
    R.Transmittance = G.Transmittance = B.Transmittance = 1;
    VolumeIntegrateSegment(Coefficients.r, Coefficients.a, SegmentLength, R);
    VolumeIntegrateSegment(Coefficients.g, Coefficients.a, SegmentLength, G);
    VolumeIntegrateSegment(Coefficients.b, Coefficients.a, SegmentLength, B);
    float3 Color = Before.rgb + Before.a * float3(R.Scatter, G.Scatter, B.Scatter);
    return float4(all(isfinite(Color)) ? clamp(Color, 0, VOLUME_HALF_MAX) : float3(0, 0, 0),
        saturate(Before.a * R.Transmittance));
}

float4 SampleIntegratedFog(Texture3D<float4> Integrated, Texture3D<float4> Source,
    float2 Uv, float Distance, float3 GridSize, float2 NearFar)
{
    float2 Cell = Uv * GridSize.xy - 0.5f;
    int2 First = int2(floor(Cell));
    float2 Fraction = frac(Cell);
    float4 Top = lerp(SampleVolumeColumn(Integrated, Source, First, Distance, GridSize, NearFar),
        SampleVolumeColumn(Integrated, Source, First + int2(1, 0), Distance, GridSize, NearFar), Fraction.x);
    float4 Bottom = lerp(SampleVolumeColumn(Integrated, Source, First + int2(0, 1), Distance, GridSize, NearFar),
        SampleVolumeColumn(Integrated, Source, First + int2(1, 1), Distance, GridSize, NearFar), Fraction.x);
    return lerp(Top, Bottom, Fraction.y);
}

#endif
