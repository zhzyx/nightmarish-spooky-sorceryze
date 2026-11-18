// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_GI_MATERIAL_SAMPLING
#define ENGINE_NEXT_GI_MATERIAL_SAMPLING

#include "MaterialLobes.hlsli"

// Exact l=0..2 convolution of the material's incoming diffuse transmission.
// The colour-dependent (1-F0) term is applied by GiMaterialDiffuseFactor.
float3 GiMaterialDiffuseBands(float Clearcoat)
{
	float Coat = saturate(Clearcoat);
	float A = 1 - 0.04f * Coat;
	float B = 0.96f * Coat;
	float C = 1 + 0.92f * Coat;
	float3 J0 = float3(0.5f, 1.0f / 3.0f, 0.125f);
	float3 J5 = float3(1.0f / 42.0f, 1.0f / 168.0f, -1.0f / 112.0f);
	float3 J10 = float3(1.0f / 132.0f, 1.0f / 858.0f, -41.0f / 12012.0f);
	return 2 * MATERIAL_PI * (A * J0 - C * J5 + B * J10);
}

float3 GiMaterialDiffuseFactor(float3 Base, float Metallic, float Clearcoat, float NoV)
{
	Base = saturate(Base);
	Metallic = saturate(Metallic);
	float3 F0 = lerp(float3(0.04f, 0.04f, 0.04f), Base, Metallic);
	float3 ViewTransmission = 1 - MaterialFresnel(saturate(NoV), F0);
	float CoatTransmission = 1 - saturate(Clearcoat) * MaterialCoatFresnel(saturate(NoV));
	return ViewTransmission * CoatTransmission * (1 - F0) * (1 - Metallic) * Base / MATERIAL_PI;
}

#endif
