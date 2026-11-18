// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_GI_SAMPLING_MATH
#define ENGINE_NEXT_GI_SAMPLING_MATH
#include "ProbeMath.hlsli"

uint GiRayLinearIndex(uint X, uint Y, uint RowThreads)
{
	return X + Y * RowThreads;
}

uint GiHash(uint Value)
{
	Value ^= Value >> 16;
	Value *= 0x7feb352du;
	Value ^= Value >> 15;
	Value *= 0x846ca68bu;
	return Value ^ (Value >> 16);
}
float GiRandom(uint Value)
{
	return float(GiHash(Value) >> 8) * (1.0f / 16777216.0f);
}
float3 GiRayDirection(uint Ray, uint RayCount, uint Probe, uint Epoch)
{
	uint Seed = GiHash(Probe) ^ GiHash(Epoch + 0x9e3779b9u);
	float Vertical = (float(Ray) + 0.5f) / float(max(RayCount, 1u)) + GiRandom(Seed);
	Vertical -= floor(Vertical);
	float Y = 1 - 2 * Vertical;
	float Phi = 2.39996322972865332f * float(Ray) + 2 * GI_PI * GiRandom(Seed ^ 0x68bc21ebu);
	float Radius = sqrt(max(1 - Y * Y, 0));
	return float3(cos(Phi) * Radius, Y, sin(Phi) * Radius);
}
float GiSignNotZero(float Value)
{
	return Value < 0 ? -1.0f : 1.0f;
}
float2 GiOctEncode(float3 Direction)
{
	float3 D = GiDirection(Direction);
	float Sum = abs(D.x) + abs(D.y) + abs(D.z);
	float X = D.x / Sum;
	float Y = D.y / Sum;
	if (D.z < 0)
	{
		float OldX = X;
		X = (1 - abs(Y)) * GiSignNotZero(OldX);
		Y = (1 - abs(OldX)) * GiSignNotZero(Y);
	}
	return float2(X * 0.5f + 0.5f, Y * 0.5f + 0.5f);
}
float3 GiOctDecode(float2 Uv)
{
	float X = Uv.x * 2 - 1;
	float Y = Uv.y * 2 - 1;
	float Z = 1 - abs(X) - abs(Y);
	float Fold = max(-Z, 0);
	X += X >= 0 ? -Fold : Fold;
	Y += Y >= 0 ? -Fold : Fold;
	return GiDirection(float3(X, Y, Z));
}
float GiDistanceWeight(float3 Ray, float3 MomentDirection)
{
	float Cosine = max(dot(Ray, MomentDirection), 0);
	float Squared = Cosine * Cosine;
	float Fourth = Squared * Squared;
	return Fourth * Fourth;
}
float GiClipmapEdgeWeight(float3 Coordinate, float3 Maximum)
{
	float Distance = min(min(Coordinate.x, Maximum.x - Coordinate.x),
						 min(min(Coordinate.y, Maximum.y - Coordinate.y), min(Coordinate.z, Maximum.z - Coordinate.z)));
	return saturate(Distance * 0.5f);
}
float GiRelativeDistance(float3 Delta, float TraceDistance)
{
	float Scale = max(abs(Delta.x), max(abs(Delta.y), abs(Delta.z)));
	if (!GiFinite(Delta) || !isfinite(TraceDistance) || TraceDistance <= 0)
	{
		return GI_FLOAT_MAX;
	}
	if (Scale == 0)
	{
		return 0;
	}
	float3 UnitScale = Delta / Scale;
	return GiFiniteProduct(Scale / TraceDistance, sqrt(dot(UnitScale, UnitScale)));
}
float GiProbeNormalWeight(float3 ToProbe, float3 Normal)
{
	float Cosine = dot(GiDirection(ToProbe), GiDirection(Normal));
	float Wrapped = saturate(Cosine * 0.5f + 0.5f);
	return max(Wrapped * Wrapped, 0.0001f);
}
float3 GiIrradianceBands(GiSh9 Radiance, float3 Normal, float3 Bands)
{
	if (!GiFinite(Bands))
	{
		return float3(0, 0, 0);
	}
	GiBasis9 Basis = GiBasis(Normal);
	float3 Result = float3(0, 0, 0);
	for (uint Index = 0; Index < 9; ++Index)
	{
		float Convolution = Index == 0 ? Bands.x : (Index < 4 ? Bands.y : Bands.z);
		float Weight = Basis.Values[Index] * Convolution;
		float3 Coefficient = Radiance.Coefficients[Index];
		if (!GiFinite(Coefficient))
		{
			return float3(0, 0, 0);
		}
		Result = float3(GiFiniteSum(Result.x, GiFiniteProduct(Coefficient.x, Weight)),
						GiFiniteSum(Result.y, GiFiniteProduct(Coefficient.y, Weight)), GiFiniteSum(Result.z, GiFiniteProduct(Coefficient.z, Weight)));
	}
	return GiFinite(Result) ? max(Result, float3(0, 0, 0)) : float3(0, 0, 0);
}
#endif
