/**************************************************************************/
/*  MaterialEnvironment.hlsli                                             */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#ifndef ENGINE_NEXT_MATERIAL_ENVIRONMENT
#define ENGINE_NEXT_MATERIAL_ENVIRONMENT

#include "MaterialLobes.hlsli"

struct MaterialEnvironmentSample
{
	float3 Direction;
	float3 Weight;
	float Pdf;
};

bool MaterialEnvironmentUsesLegacy(bool OverrideEnabled, float Anisotropy, float Clearcoat)
{
	return !OverrideEnabled || (Anisotropy == 0 && Clearcoat == 0);
}

// Index is in [0, Count). The midpoint avoids the singular NDF boundary at one.
float2 MaterialHammersley(uint Index, uint Count)
{
	uint Bits = (Index << 16u) | (Index >> 16u);
	Bits = ((Bits & 0x55555555u) << 1u) | ((Bits & 0xAAAAAAAAu) >> 1u);
	Bits = ((Bits & 0x33333333u) << 2u) | ((Bits & 0xCCCCCCCCu) >> 2u);
	Bits = ((Bits & 0x0F0F0F0Fu) << 4u) | ((Bits & 0xF0F0F0F0u) >> 4u);
	Bits = ((Bits & 0x00FF00FFu) << 8u) | ((Bits & 0xFF00FF00u) >> 8u);
	float Divisor = Count > 0 ? float(Count) : 1.0f;
	return float2((float(Index) + 0.5f) / Divisor, float(Bits) * 2.3283064365386963e-10f);
}

MaterialEnvironmentSample MaterialEnvironmentEmpty(MaterialFrame Frame)
{
	MaterialEnvironmentSample Result;
	Result.Direction = Frame.Normal;
	Result.Weight = float3(0, 0, 0);
	Result.Pdf = 0;
	return Result;
}

float3 MaterialEnvironmentHalfVector(MaterialFrame Frame, float2 Alpha, float2 Xi)
{
	float Phi = 2 * MATERIAL_PI * saturate(Xi.y);
	float U = clamp(Xi.x, 0, 0.9999999403953552f);
	float Radius = sqrt(U / (1 - U));
	float3 Half = Frame.Normal + Frame.Tangent * (Alpha.x * Radius * cos(Phi)) +
			Frame.Bitangent * (Alpha.y * Radius * sin(Phi));
	return MaterialDirection(Half, Frame.Normal);
}

MaterialEnvironmentSample MaterialEnvironmentReflection(float3 V, MaterialFrame Frame, float2 Alpha, float2 Xi)
{
	MaterialEnvironmentSample Result = MaterialEnvironmentEmpty(Frame);
	if (!MaterialFinite(V) || dot(V, V) == 0 || !isfinite(Xi.x) || !isfinite(Xi.y))
	{
		return Result;
	}
	V = MaterialDirection(V, Frame.Normal);
	if (dot(Frame.Normal, V) <= 0)
	{
		return Result;
	}
	float3 Half = MaterialEnvironmentHalfVector(Frame, Alpha, Xi);
	float VoH = dot(V, Half);
	float NoH = dot(Frame.Normal, Half);
	if (VoH <= 0 || NoH <= 0)
	{
		return Result;
	}
	float3 L = MaterialDirection(2 * VoH * Half - V, Frame.Normal);
	if (dot(Frame.Normal, L) <= 0)
	{
		return Result;
	}
	float Pdf = MaterialGGXD(Half, Frame, Alpha) * NoH / (4 * VoH);
	if (!isfinite(Pdf) || Pdf <= 0)
	{
		return Result;
	}
	Result.Direction = L;
	Result.Pdf = Pdf;
	return Result;
}

// Weight is BRDF * NoL / Pdf. Callers average all Count samples, including zeros.
MaterialEnvironmentSample MaterialEnvironmentBaseSample(float3 Base, float Metallic, float Roughness,
		float Anisotropy, float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float2 Xi)
{
	MaterialEnvironmentSample Result = MaterialEnvironmentReflection(V, Frame, MaterialRoughnessAxes(Roughness, Anisotropy), Xi);
	if (Result.Pdf > 0)
	{
		MaterialLobes Lobes = MaterialEvaluateLobes(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, Result.Direction);
		Result.Weight = Lobes.Specular * (saturate(dot(Frame.Normal, Result.Direction)) / Result.Pdf);
		if (!MaterialFinite(Result.Weight))
		{
			return MaterialEnvironmentEmpty(Frame);
		}
	}
	return Result;
}

MaterialEnvironmentSample MaterialEnvironmentCoatSample(float3 Base, float Metallic, float Roughness,
		float Anisotropy, float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float2 Xi)
{
	MaterialEnvironmentSample Result = MaterialEnvironmentEmpty(Frame);
	if (!isfinite(Clearcoat) || Clearcoat <= 0)
	{
		return Result;
	}
	Result = MaterialEnvironmentReflection(V, Frame, MaterialRoughnessAxes(CoatRoughness, 0), Xi);
	if (Result.Pdf > 0)
	{
		MaterialLobes Lobes = MaterialEvaluateLobes(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, Result.Direction);
		Result.Weight = Lobes.Clearcoat * (saturate(dot(Frame.Normal, Result.Direction)) / Result.Pdf);
		if (!MaterialFinite(Result.Weight))
		{
			return MaterialEnvironmentEmpty(Frame);
		}
	}
	return Result;
}

MaterialEnvironmentSample MaterialEnvironmentDiffuseSample(float3 Base, float Metallic, float Roughness,
		float Anisotropy, float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float2 Xi)
{
	MaterialEnvironmentSample Result = MaterialEnvironmentEmpty(Frame);
	if (!MaterialFinite(V) || dot(V, V) == 0 || !isfinite(Xi.x) || !isfinite(Xi.y))
	{
		return Result;
	}
	float U = clamp(Xi.x, 0, 0.9999999403953552f);
	float Phi = 2 * MATERIAL_PI * saturate(Xi.y);
	float Radius = sqrt(U);
	Result.Direction = MaterialDirection(Frame.Tangent * (Radius * cos(Phi)) +
			Frame.Bitangent * (Radius * sin(Phi)) + Frame.Normal * sqrt(1 - U), Frame.Normal);
	Result.Pdf = saturate(dot(Frame.Normal, Result.Direction)) / MATERIAL_PI;
	MaterialLobes Lobes = MaterialEvaluateLobes(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, Result.Direction);
	Result.Weight = Lobes.Diffuse * MATERIAL_PI;
	if (!MaterialFinite(Result.Weight))
	{
		return MaterialEnvironmentEmpty(Frame);
	}
	return Result;
}

#endif
