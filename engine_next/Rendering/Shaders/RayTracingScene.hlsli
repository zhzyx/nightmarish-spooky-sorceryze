// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_RAY_TRACING_SCENE
#define ENGINE_NEXT_RAY_TRACING_SCENE

struct RayTracingDraw
{
	uint FirstIndex;
	uint BaseVertex;
	uint Material;
	uint IndexCount;
};
struct RayTracingMaterial
{
	float4 BaseColor;
	float4 Emissive;
	// Roughness, metallic, effective normal scale, occlusion strength.
	float4 Surface;
	uint BaseTexture;
	uint BaseSampler;
	uint AlphaMode;
	float AlphaCutoff;
};

// Opaque geometry normally commits in hardware. MASK uses the same base-alpha
// product and cutoff as raster. BLEND is transparent to this GI ray policy.
bool RayTracingAlphaAccept(RayTracingMaterial Material, float SampleAlpha)
{
	if (!isfinite(Material.BaseColor.a) || !isfinite(SampleAlpha) || !isfinite(Material.AlphaCutoff))
	{
		return false;
	}
	if (Material.AlphaMode == 0)
	{
		return true;
	}
	return Material.AlphaMode == 1 && Material.BaseColor.a * SampleAlpha >= Material.AlphaCutoff;
}

#endif
