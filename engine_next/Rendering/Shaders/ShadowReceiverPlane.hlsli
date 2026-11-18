// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_SHADOW_RECEIVER_PLANE_HLSLI
#define ENGINE_NEXT_SHADOW_RECEIVER_PLANE_HLSLI

// Orthographic world-to-shadow rows transform a geometric receiver plane by
// their cofactor matrix. Its common determinant cancels in dz / d(x,y), even
// when a light axis is reflected. Shading normals must not define this plane.
float2 ShadowReceiverGradient(float3 vRowX, float3 vRowY, float3 vRowZ, float3 vGeometricNormal)
{
	if (!all(isfinite(vRowX)) || !all(isfinite(vRowY)) || !all(isfinite(vRowZ)) ||
			!all(isfinite(vGeometricNormal)))
	{
		return float2(0, 0);
	}
	float fDeterminant = dot(vRowX, cross(vRowY, vRowZ));
	if (!isfinite(fDeterminant) || fDeterminant == 0)
	{
		return float2(0, 0);
	}
	float3 vProjectedNormal = float3(dot(cross(vRowY, vRowZ), vGeometricNormal),
			dot(cross(vRowZ, vRowX), vGeometricNormal), dot(cross(vRowX, vRowY), vGeometricNormal));
	if (!all(isfinite(vProjectedNormal)))
	{
		return float2(0, 0);
	}
	float fScale = abs(vProjectedNormal.x);
	if (abs(vProjectedNormal.y) > fScale)
	{
		fScale = abs(vProjectedNormal.y);
	}
	if (abs(vProjectedNormal.z) > fScale)
	{
		fScale = abs(vProjectedNormal.z);
	}
	if (fScale <= 0)
	{
		return float2(0, 0);
	}
	vProjectedNormal = vProjectedNormal / fScale;
	// A nearly edge-on or degenerate plane cannot predict a finite neighbouring
	// intersection reliably. Preserve the existing depth comparison in that case.
	if (abs(vProjectedNormal.z) <= 0.000001f)
	{
		return float2(0, 0);
	}
	return float2(-vProjectedNormal.x / vProjectedNormal.z, -vProjectedNormal.y / vProjectedNormal.z);
}

float ShadowReceiverDepth(float3 vProjected, float2 vTexelClip, float2 vGradient, float fDepthBias)
{
	float fDepth = vProjected.z + vGradient.x * (vTexelClip.x - vProjected.x) +
			vGradient.y * (vTexelClip.y - vProjected.y);
	if (!isfinite(fDepth))
	{
		fDepth = vProjected.z;
	}
	return saturate(fDepth + max(fDepthBias, 0));
}

#endif
