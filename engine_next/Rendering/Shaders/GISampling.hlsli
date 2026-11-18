// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_GI_SAMPLING
#define ENGINE_NEXT_GI_SAMPLING
#include "GISamplingMath.hlsli"

struct GiGridParameters
{
	float4 Minimum[3];
	float4 InverseSpacing[3];
	uint4 GridInfo;
	uint4 WorkInfo;
	float4 Sampling;
	float4 History;
	uint4 Counts;
};

uint GiStateIndex(uint Probe, GiGridParameters Grid)
{
	return Probe * (Grid.Counts.w != 0 ? 3u : 1u);
}

float3 GiPlacementOffset(uint Probe, GiGridParameters Grid, StructuredBuffer<uint4> States)
{
	return Grid.Counts.w != 0 ? asfloat(States[GiStateIndex(Probe, Grid) + 1].xyz) : float3(0, 0, 0);
}

float2 GiReadDistanceMoments(uint Probe, float3 Direction, StructuredBuffer<float2> Moments)
{
	float2 Uv = GiOctEncode(Direction);
	uint2 Pixel = min(uint2(Uv * 8), uint2(7, 7));
	return Moments[Probe * 64 + Pixel.y * 8 + Pixel.x];
}

// Returns irradiance and valid interpolation coverage. The caller retains its
// existing environment fallback wherever coverage is incomplete.
float4 GiSampleIrradianceBands(float3 Position, float3 Normal, float3 ViewDirection, GiGridParameters Grid,
							   StructuredBuffer<float4> Coefficients, StructuredBuffer<float2> Moments, StructuredBuffer<uint4> States, float3 Bands)
{
	if (!GiFinite(Position) || !GiFinite(Normal) || !GiFinite(ViewDirection) || Grid.GridInfo.w == 0)
	{
		return 0;
	}
	float3 N = GiDirection(Normal);
	float3 Biased = Position + N * Grid.Sampling.z + GiDirection(ViewDirection) * Grid.Sampling.w;
	float3 Maximum = float3(Grid.GridInfo.xyz - 1);
	uint LevelSize = Grid.GridInfo.x * Grid.GridInfo.y * Grid.GridInfo.z;
	float3 Sum = 0;
	float Coverage = 0;
	[loop] for (uint Level = 0; Level < min(Grid.GridInfo.w, 3u); ++Level)
	{
		float3 Coordinate = (Biased - Grid.Minimum[Level].xyz) * Grid.InverseSpacing[Level].xyz;
		if (!GiFinite(Coordinate) || any(Coordinate < 0) || any(Coordinate > Maximum))
		{
			continue;
		}
		uint3 Base = min(uint3(floor(Coordinate)), Grid.GridInfo.xyz - 2);
		float3 Fraction = Coordinate - float3(Base);
		float3 LevelSum = 0;
		float ValidWeight = 0;
		float TotalWeight = 0;
		[unroll] for (uint Corner = 0; Corner < 8; ++Corner)
		{
			uint3 Offset = uint3(Corner & 1, (Corner >> 1) & 1, (Corner >> 2) & 1);
			uint3 Cell = Base + Offset;
			uint Probe = Level * LevelSize + (Cell.z * Grid.GridInfo.y + Cell.y) * Grid.GridInfo.x + Cell.x;
			float3 ProbePosition = Grid.Minimum[Level].xyz + float3(Cell) / Grid.InverseSpacing[Level].xyz;
			ProbePosition += GiPlacementOffset(Probe, Grid, States);
			float3 ToProbe = ProbePosition - Biased;
			float Weight = GiTrilinearWeight(Fraction, Corner) * GiProbeNormalWeight(ToProbe, N);
			TotalWeight += Weight;
			if (Probe >= Grid.WorkInfo.x || States[GiStateIndex(Probe, Grid)].x == 0 ||
				(Grid.Counts.w != 0 && States[GiStateIndex(Probe, Grid) + 2].x != 1))
			{
				continue;
			}
			float RelativeDistance = GiRelativeDistance(-ToProbe, Grid.Sampling.x);
			float Visibility = GiVisibility(RelativeDistance, GiReadDistanceMoments(Probe, -ToProbe, Moments), 0, 0);
			GiSh9 Sh;
			[unroll] for (uint Term = 0; Term < 9; ++Term)
			{
				Sh.Coefficients[Term] = Coefficients[Probe * 9 + Term].rgb;
			}
			float Contribution = Weight * Visibility;
			LevelSum += GiIrradianceBands(Sh, N, Bands) * Contribution;
			ValidWeight += Contribution;
		}
		if (ValidWeight <= 0 || TotalWeight <= 0)
		{
			continue;
		}
		float Edge = Level + 1 < Grid.GridInfo.w ? GiClipmapEdgeWeight(Coordinate, Maximum) : 1;
		float Contribution = (1 - Coverage) * Edge * saturate(ValidWeight / TotalWeight);
		Sum += (LevelSum / ValidWeight) * Contribution;
		Coverage += Contribution;
		if (Coverage >= 0.9999)
		{
			break;
		}
	}
	return Coverage > 0 && GiFinite(Sum) ? float4(Sum / Coverage, saturate(Coverage)) : float4(0, 0, 0, 0);
}
float4 GiSampleIrradiance(float3 Position, float3 Normal, float3 ViewDirection, GiGridParameters Grid,
						  StructuredBuffer<float4> Coefficients, StructuredBuffer<float2> Moments, StructuredBuffer<uint4> States)
{
	return GiSampleIrradianceBands(Position, Normal, ViewDirection, Grid, Coefficients, Moments, States,
								   float3(GI_PI, 2 * GI_PI / 3, GI_PI / 4));
}
#endif
