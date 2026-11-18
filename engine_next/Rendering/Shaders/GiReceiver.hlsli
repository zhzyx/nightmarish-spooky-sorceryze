// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_GI_RECEIVER
#define ENGINE_NEXT_GI_RECEIVER

#include "GISampling.hlsli"
#include "GiMaterialSampling.hlsli"

StructuredBuffer<float4> GiCoefficients : register(t16);
StructuredBuffer<float2> GiDistanceMoments : register(t17);
StructuredBuffer<uint4> GiProbeStates : register(t18);
cbuffer GiReceiverConstants : register(b4)
{
	GiGridParameters GiGrid;
};

float3 GiReceiverDiffuse(float3 EnvironmentDiffuse, float3 Position, float3 Normal, float3 ViewDirection,
		float3 Base, float Metallic, float Roughness, float4 Extension, bool ExtensionsEnabled)
{
	float NoV = saturate(dot(Normal, ViewDirection));
	float3 Bands = float3(GI_PI, 2 * GI_PI / 3, GI_PI / 4);
	float3 F0 = lerp(float3(0.04f, 0.04f, 0.04f), Base, Metallic);
	float3 F = F0 + (max(1 - Roughness, F0) - F0) * pow(1 - NoV, 5);
	float3 Factor = (1 - F) * (1 - Metallic) * Base / GI_PI;
	if (ExtensionsEnabled && (Extension.x != 0 || Extension.z != 0))
	{
		Bands = GiMaterialDiffuseBands(Extension.x);
		Factor = GiMaterialDiffuseFactor(Base, Metallic, Extension.x, NoV);
	}
	float4 Indirect = GiSampleIrradianceBands(Position, Normal, ViewDirection, GiGrid,
			GiCoefficients, GiDistanceMoments, GiProbeStates, Bands);
	return lerp(EnvironmentDiffuse, Indirect.rgb * Factor, Indirect.a);
}

#endif
