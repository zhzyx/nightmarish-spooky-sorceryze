// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_CLUSTER_CULLING_MATH_HLSLI
#define ENGINE_NEXT_CLUSTER_CULLING_MATH_HLSLI
#ifdef __cplusplus
#define CULL_INOUT(Type, Name) Type &Name
#else
#define CULL_INOUT(Type, Name) inout Type Name
#endif

struct ClusterScreenBounds
{
	uint MinimumX;
	uint MinimumY;
	uint MaximumX;
	uint MaximumY;
	float ClosestDepth;
};

struct ClusterHiZFootprint
{
	uint Mip;
	uint MinimumX;
	uint MinimumY;
	uint MaximumX;
	uint MaximumY;
};

bool ClusterBoundsValid(float3 Minimum, float3 Maximum)
{
	return all(isfinite(Minimum)) && all(isfinite(Maximum)) && all(Minimum <= Maximum);
}

bool ClusterBoxOutsidePlane(float3 Minimum, float3 Maximum, float4 Plane)
{
	float3 Positive = float3(Plane.x >= 0 ? Maximum.x : Minimum.x,
							 Plane.y >= 0 ? Maximum.y : Minimum.y, Plane.z >= 0 ? Maximum.z : Minimum.z);
	float Distance = dot(Positive, Plane.xyz) + Plane.w;
	return isfinite(Distance) && Distance < 0;
}

// Each plane describes a closed inside half-space, dot(P,xyz)+w >= 0.
bool ClusterInFrustum(float3 Minimum, float3 Maximum, float4 Planes[6])
{
	for (uint Index = 0; Index < 6; ++Index)
	{
		if (ClusterBoxOutsidePlane(Minimum, Maximum, Planes[Index]))
		{
			return false;
		}
	}
	return true;
}

// Projection is eligible for occlusion only when every corner is inside the
// finite depth interval. Near-plane and camera crossings stay conservatively visible.
bool ClusterProjectBounds(float4 Corners[8], uint Width, uint Height, CULL_INOUT(ClusterScreenBounds, Bounds))
{
	if (Width == 0 || Height == 0 || Width > 16384 || Height > 16384)
	{
		return false;
	}
	float MinimumX = 1;
	float MinimumY = 1;
	float MaximumX = 0;
	float MaximumY = 0;
	float ClosestDepth = 0;
	for (uint Index = 0; Index < 8; ++Index)
	{
		float4 Clip = Corners[Index];
		if (!all(isfinite(Clip)) || Clip.w <= 0 || Clip.z < 0 || Clip.z > Clip.w)
		{
			return false;
		}
		float X = saturate(Clip.x / Clip.w * 0.5f + 0.5f);
		float Y = saturate(0.5f - Clip.y / Clip.w * 0.5f);
		MinimumX = min(MinimumX, X);
		MinimumY = min(MinimumY, Y);
		MaximumX = max(MaximumX, X);
		MaximumY = max(MaximumY, Y);
		ClosestDepth = max(ClosestDepth, Clip.z / Clip.w);
	}
	Bounds.MinimumX = min(uint(floor(MinimumX * Width)), Width - 1);
	Bounds.MinimumY = min(uint(floor(MinimumY * Height)), Height - 1);
	Bounds.MaximumX = max(Bounds.MinimumX, min(uint(max(0, ceil(MaximumX * Width) - 1)), Width - 1));
	Bounds.MaximumY = max(Bounds.MinimumY, min(uint(max(0, ceil(MaximumY * Height) - 1)), Height - 1));
	Bounds.ClosestDepth = ClosestDepth;
	return true;
}

// Hi-Z uses a power-of-two padded surface. Clear padding is reverse-depth zero.
// The chosen footprint covers at most four full minimum-reduction tiles.
bool ClusterChooseHiZ(ClusterScreenBounds Bounds, uint MipCount, CULL_INOUT(ClusterHiZFootprint, Footprint))
{
	if (MipCount == 0 || MipCount > 15 || Bounds.MaximumX < Bounds.MinimumX || Bounds.MaximumY < Bounds.MinimumY)
	{
		return false;
	}
	uint Span = max(Bounds.MaximumX - Bounds.MinimumX + 1, Bounds.MaximumY - Bounds.MinimumY + 1);
	uint Mip = 0;
	while ((1u << Mip) < Span && Mip + 1 < MipCount)
	{
		++Mip;
	}
	Footprint.Mip = Mip;
	Footprint.MinimumX = Bounds.MinimumX >> Mip;
	Footprint.MinimumY = Bounds.MinimumY >> Mip;
	Footprint.MaximumX = Bounds.MaximumX >> Mip;
	Footprint.MaximumY = Bounds.MaximumY >> Mip;
	return Footprint.MaximumX - Footprint.MinimumX <= 1 && Footprint.MaximumY - Footprint.MinimumY <= 1;
}

bool ClusterDepthOccluded(float ClosestDepth, float MinimumHiZ, float Bias)
{
	return isfinite(ClosestDepth) && isfinite(MinimumHiZ) && isfinite(Bias) &&
			ClosestDepth >= 0 && ClosestDepth <= 1 && MinimumHiZ > 0 && MinimumHiZ <= 1 && Bias >= 0 &&
			ClosestDepth < MinimumHiZ - Bias;
}

bool ClusterOutputSlot(uint Slot, uint Capacity)
{
	return Slot < Capacity;
}

float ClusterReduceReverseDepth(float A, float B, float C, float D)
{
	if (!isfinite(A) || !isfinite(B) || !isfinite(C) || !isfinite(D) ||
		A < 0 || B < 0 || C < 0 || D < 0 || A > 1 || B > 1 || C > 1 || D > 1)
	{
		return 0;
	}
	return min(min(A, B), min(C, D));
}
#undef CULL_INOUT
#endif
