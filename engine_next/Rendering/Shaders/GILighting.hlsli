// Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
#ifndef ENGINE_NEXT_GI_LIGHTING
#define ENGINE_NEXT_GI_LIGHTING
#include "MaterialLobes.hlsli"

float3 UnitDirection(float3 Direction, float3 Fallback)
{
	float Maximum = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
	if (!GiFinite(Direction) || Maximum == 0)
	{
		return Fallback;
	}
	return GiDirection(Direction);
}
#include "ShadowSampling.hlsli"

struct GiLocalLightConstants
{
	float4 PositionRange;
	float4 ColorIntensity;
	float4 DirectionType;
	float4 ConeShadow;
	float4 ShadowParameters;
};
// Exact 3120-byte FrameConstants layout shared with the raster caller.
cbuffer GiFrameConstants : register(b1)
{
	column_major float4x4 ViewProjection;
	column_major float4x4 InverseViewProjection;
	float4 Camera;
	float4 Lighting;
	column_major float4x4 View;
	column_major float4x4 ShadowViewProjection[4];
	float4 CascadeSplits;
	float4 LightDirection;
	float4 LightColor;
	float4 ShadowParameters;
	column_major float4x4 LocalShadowMatrices[28];
	GiLocalLightConstants LocalLights[8];
	float4 LocalCounts;
	column_major float4x4 UnjitteredViewProjection;
	column_major float4x4 PreviousViewProjection;
}

float GiCascadeVisibility(float3 Position, float3 Normal, uint Cascade, Texture2DArray<float> Shadow)
{
	float4 Projected = mul(ShadowViewProjection[Cascade], float4(Position + Normal * ShadowParameters.w, 1));
	if (Projected.w == 0 || !all(isfinite(Projected)))
	{
		return 1;
	}
	Projected.xyz /= Projected.w;
	float2 Uv = Projected.xy * float2(0.5, -0.5) + 0.5;
	if (any(Uv < 0) || any(Uv > 1) || Projected.z < 0 || Projected.z > 1)
	{
		return 1;
	}
	int Resolution = (int)round(1 / ShadowParameters.y);
	int2 Center = int2(Uv * Resolution);
	float Sum = 0;
	[unroll] for (int Y = -1; Y <= 1; ++Y)
	{
		[unroll] for (int X = -1; X <= 1; ++X)
		{
			int2 Pixel = clamp(Center + int2(X, Y), 0, Resolution - 1);
			Sum += Projected.z + ShadowParameters.z >= Shadow.Load(int4(Pixel, Cascade, 0)) ? 1 : 0;
		}
	}
	return Sum / 9;
}
float GiDirectionalVisibility(float3 Position, float3 Normal, Texture2DArray<float> Shadow)
{
	float Distance = -mul(View, float4(Position, 1)).z;
	if (ShadowParameters.x < 0.5 || Distance > CascadeSplits.w)
	{
		return 1;
	}
	uint Cascade = Distance > CascadeSplits.x ? 1 : 0;
	Cascade = Distance > CascadeSplits.y ? 2 : Cascade;
	Cascade = Distance > CascadeSplits.z ? 3 : Cascade;
	float Visibility = GiCascadeVisibility(Position, Normal, Cascade, Shadow);
	if (Cascade < 3)
	{
		float Start = Cascade == 0 ? 0 : CascadeSplits[Cascade - 1];
		float Width = (CascadeSplits[Cascade] - Start) * Lighting.z;
		float Blend = saturate((Distance - (CascadeSplits[Cascade] - Width)) / max(Width, 0.001));
		if (Blend > 0)
		{
			Visibility = lerp(Visibility, GiCascadeVisibility(Position, Normal, Cascade + 1, Shadow), Blend);
		}
	}
	return Visibility;
}
float GiLocalVisibility(GiLocalLightConstants Light, float3 Position, float3 Normal, float3 GeometricNormal, Texture2DArray<float> Shadow)
{
	if (ShadowParameters.x < 0.5 || Light.ConeShadow.z < 0)
	{
		return 1;
	}
	float3 Biased = Position + Normal * ShadowParameters.w;
	uint Slice = uint(Light.ConeShadow.z);
	uint Face = 6;
	if (Light.DirectionType.w < 0.5)
	{
		Face = ShadowCubeFace(Biased - Light.PositionRange.xyz);
		Slice += Face;
	}
	float4 Projected = mul(LocalShadowMatrices[Slice], float4(Biased, 1));
	if (Projected.w <= 0 || !all(isfinite(Projected)))
	{
		return 1;
	}
	return SampleShadowMap(Shadow, Projected.xyz / Projected.w, Slice,
						   LocalCounts.z, ShadowParameters.z, Light.ShadowParameters.z,
						   Light.ShadowParameters.xy, false, LocalCounts.w > 0.5, Face, GeometricNormal);
}
float3 GiDirectLighting(float3 Base, float Metallic, float Roughness, float3 Position, float3 N, float3 V,
						float3 GeometricNormal, float3 Tangent, float Handedness, float4 Extension,
						Texture2DArray<float> DirectionalShadow, Texture2DArray<float> LocalShadow, float3 DirectionalTint)
{
	MaterialFrame Frame = MaterialBuildFrame(N, Tangent, Handedness, Extension.w);
	float3 Sum = MaterialShadeLight(Base, Metallic, Roughness, Extension.z, Extension.x, Extension.y,
									true, Frame, V, LightDirection.xyz, LightColor.rgb * DirectionalTint) *
			GiDirectionalVisibility(Position, N, DirectionalShadow);
	[loop] for (uint Index = 0; Index < min(uint(LocalCounts.x), 8u); ++Index)
	{
		GiLocalLightConstants Light = LocalLights[Index];
		float3 Vector = Light.PositionRange.xyz - Position;
		float Distance = length(Vector);
		if (!isfinite(Distance) || Distance >= Light.PositionRange.w)
		{
			continue;
		}
		float3 L = GiDirection(Vector);
		float Attenuation = pow(saturate(1 - pow(Distance / Light.PositionRange.w, 4)), 2) / max(Distance * Distance, 0.0001);
		if (Light.DirectionType.w > 0.5)
		{
			float3 Cone = -L - Light.DirectionType.xyz;
			Attenuation *= 1 - smoothstep(Light.ConeShadow.x, Light.ConeShadow.y, dot(Cone, Cone));
		}
		float3 Radiance = min(Light.ColorIntensity.rgb, 1.0e20) * Attenuation;
		Sum += MaterialShadeLight(Base, Metallic, Roughness, Extension.z, Extension.x, Extension.y, true, Frame, V, L, Radiance) *
				GiLocalVisibility(Light, Position, N, GeometricNormal, LocalShadow);
	}
	return GiFinite(Sum) ? max(Sum, 0) : float3(0, 0, 0);
}
#endif
