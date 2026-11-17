/**************************************************************************/
/*  MaterialLobes.hlsli                                                   */
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

#ifndef ENGINE_NEXT_MATERIAL_LOBES
#define ENGINE_NEXT_MATERIAL_LOBES

static const float MATERIAL_PI = 3.14159265f;

struct MaterialFrame
{
	float3 Normal;
	float3 Tangent;
	float3 Bitangent;
};

struct MaterialLobes
{
	float3 Diffuse;
	float3 Specular;
	float3 Clearcoat;
};

bool MaterialFinite(float3 Value)
{
	return isfinite(Value.x) && isfinite(Value.y) && isfinite(Value.z);
}

float3 MaterialDirection(float3 Value, float3 Fallback)
{
	float Maximum = max(abs(Value.x), max(abs(Value.y), abs(Value.z)));
	if (!MaterialFinite(Value) || Maximum <= 0)
	{
		return Fallback;
	}
	float3 Scaled = Value / Maximum;
	return Scaled * rsqrt(dot(Scaled, Scaled));
}

MaterialFrame MaterialBuildFrame(float3 Normal, float3 Tangent, float Handedness, float Rotation)
{
	MaterialFrame Frame;
	Frame.Normal = MaterialDirection(Normal, float3(0, 0, 1));
	float3 Axis = abs(Frame.Normal.y) < 0.9f ? float3(0, 1, 0) : float3(1, 0, 0);
	float3 Fallback = MaterialDirection(cross(Axis, Frame.Normal), float3(1, 0, 0));
	float3 UnitTangent = MaterialDirection(Tangent, Fallback);
	float3 Projected = UnitTangent - Frame.Normal * dot(UnitTangent, Frame.Normal);
	Frame.Tangent = MaterialDirection(Projected, Fallback);
	float Sign = Handedness < 0 ? -1.0f : 1.0f;
	Frame.Bitangent = cross(Frame.Normal, Frame.Tangent) * Sign;
	float Angle = isfinite(Rotation) ? Rotation : 0;
	float Sine = sin(Angle);
	float Cosine = cos(Angle);
	float3 Rotated = Frame.Tangent * Cosine + Frame.Bitangent * Sine;
	Frame.Bitangent = Frame.Bitangent * Cosine - Frame.Tangent * Sine;
	Frame.Tangent = Rotated;
	return Frame;
}

float2 MaterialRoughnessAxes(float Roughness, float Anisotropy)
{
	float Alpha = max(saturate(Roughness) * saturate(Roughness), 0.0025f);
	float Strength = clamp(Anisotropy, -1, 1);
	float Aspect = sqrt(1 - 0.9f * abs(Strength));
	float2 Axes = float2(max(Alpha / Aspect, 0.0025f), max(Alpha * Aspect, 0.0025f));
	return Strength < 0 ? float2(Axes.y, Axes.x) : Axes;
}

// Full GGX NDF. AlphaX/Y are positive slope widths, not perceptual roughness.
float MaterialGGXD(float3 H, MaterialFrame Frame, float2 Alpha)
{
	float NoH = dot(Frame.Normal, H);
	if (NoH <= 0)
	{
		return 0;
	}
	float ToH = dot(Frame.Tangent, H) / Alpha.x;
	float BoH = dot(Frame.Bitangent, H) / Alpha.y;
	float Sum = ToH * ToH + BoH * BoH + NoH * NoH;
	return 1 / (MATERIAL_PI * Alpha.x * Alpha.y * Sum * Sum);
}

// Height-correlated Smith G2 divided by 4 * NoV * NoL.
float MaterialSmithV(float3 V, float3 L, MaterialFrame Frame, float2 Alpha)
{
	float NoV = dot(Frame.Normal, V);
	float NoL = dot(Frame.Normal, L);
	if (NoV <= 0 || NoL <= 0)
	{
		return 0;
	}
	float ToV = Alpha.x * dot(Frame.Tangent, V);
	float BoV = Alpha.y * dot(Frame.Bitangent, V);
	float ToL = Alpha.x * dot(Frame.Tangent, L);
	float BoL = Alpha.y * dot(Frame.Bitangent, L);
	float LambdaV = sqrt(ToV * ToV + BoV * BoV + NoV * NoV);
	float LambdaL = sqrt(ToL * ToL + BoL * BoL + NoL * NoL);
	return 0.5f / max(NoL * LambdaV + NoV * LambdaL, 1.0e-20f);
}

float3 MaterialFresnel(float Cosine, float3 F0)
{
	return F0 + (1 - F0) * pow(saturate(1 - Cosine), 5);
}

float MaterialCoatFresnel(float Cosine)
{
	return 0.04f + 0.96f * pow(saturate(1 - Cosine), 5);
}

MaterialLobes MaterialEvaluateLobes(float3 Base, float Metallic, float Roughness, float Anisotropy,
	float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float3 L)
{
	MaterialLobes Result;
	Result.Diffuse = float3(0, 0, 0);
	Result.Specular = float3(0, 0, 0);
	Result.Clearcoat = float3(0, 0, 0);
	if (!MaterialFinite(Base) || !MaterialFinite(V) || !MaterialFinite(L) ||
		!isfinite(Metallic) || !isfinite(Roughness) || !isfinite(Anisotropy) ||
		!isfinite(Clearcoat) || !isfinite(CoatRoughness) || dot(V, V) == 0 || dot(L, L) == 0)
	{
		return Result;
	}
	V = MaterialDirection(V, Frame.Normal);
	L = MaterialDirection(L, Frame.Normal);
	float NoV = saturate(dot(Frame.Normal, V));
	float NoL = saturate(dot(Frame.Normal, L));
	if (NoV <= 0 || NoL <= 0)
	{
		return Result;
	}
	Base = saturate(Base);
	Metallic = saturate(Metallic);
	float3 H = MaterialDirection(V + L, Frame.Normal);
	float VoH = saturate(dot(V, H));
	float2 Alpha = MaterialRoughnessAxes(Roughness, Anisotropy);
	float3 F0 = lerp(float3(0.04f, 0.04f, 0.04f), Base, Metallic);
	float3 F = MaterialFresnel(VoH, F0);
	float3 DiffuseTransmission = (1 - MaterialFresnel(NoV, F0)) * (1 - MaterialFresnel(NoL, F0));
	float CoatWeight = saturate(Clearcoat);
	float Transmission = (1 - CoatWeight * MaterialCoatFresnel(NoV)) * (1 - CoatWeight * MaterialCoatFresnel(NoL));
	Result.Diffuse = DiffuseTransmission * (1 - Metallic) * Base * (Transmission / MATERIAL_PI);
	Result.Specular = F * (MaterialGGXD(H, Frame, Alpha) * MaterialSmithV(V, L, Frame, Alpha) * Transmission);
	float2 CoatAlpha = MaterialRoughnessAxes(CoatRoughness, 0);
	float Coat = CoatWeight * MaterialCoatFresnel(VoH) * MaterialGGXD(H, Frame, CoatAlpha) * MaterialSmithV(V, L, Frame, CoatAlpha);
	Result.Clearcoat = float3(Coat, Coat, Coat);
	return Result;
}

float3 MaterialEvaluateLight(float3 Base, float Metallic, float Roughness, float Anisotropy,
	float Clearcoat, float CoatRoughness, MaterialFrame Frame, float3 V, float3 L, float3 Radiance)
{
	if (!MaterialFinite(Radiance))
	{
		return float3(0, 0, 0);
	}
	MaterialLobes Lobes = MaterialEvaluateLobes(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, L);
	float NoL = saturate(dot(Frame.Normal, MaterialDirection(L, Frame.Normal)));
	return (Lobes.Diffuse + Lobes.Specular + Lobes.Clearcoat) * max(Radiance, float3(0, 0, 0)) * NoL;
}

// Compatibility entry for existing material draws. Preserve the current
// denominator floors and Schlick geometry approximation until explicitly overridden.
float3 MaterialLegacyLight(float3 Base, float Metallic, float Roughness, float3 N, float3 V, float3 L, float3 Radiance)
{
	float3 H = MaterialDirection(V + L, float3(0, 0, 1));
	float NoL = saturate(dot(N, L));
	float NoV = max(saturate(dot(N, V)), 0.001f);
	float NoH = saturate(dot(N, H));
	float VoH = saturate(dot(V, H));
	float Alpha = max(Roughness * Roughness, 0.0025f);
	float A2 = Alpha * Alpha;
	float D = A2 / max(MATERIAL_PI * pow(NoH * NoH * (A2 - 1) + 1, 2), 0.00001f);
	float K = pow(Roughness + 1, 2) / 8;
	float G = NoV / (NoV * (1 - K) + K) * NoL / max(NoL * (1 - K) + K, 0.0001f);
	float3 F = MaterialFresnel(VoH, lerp(float3(0.04f, 0.04f, 0.04f), Base, Metallic));
	float3 Specular = D * G * F / max(4 * NoV * NoL, 0.0001f);
	return ((1 - F) * (1 - Metallic) * Base / MATERIAL_PI + Specular) * Radiance * NoL;
}

float3 MaterialShadeLight(float3 Base, float Metallic, float Roughness, float Anisotropy,
	float Clearcoat, float CoatRoughness, bool OverrideEnabled, MaterialFrame Frame,
	float3 V, float3 L, float3 Radiance)
{
	if (!OverrideEnabled || (Anisotropy == 0 && Clearcoat == 0))
	{
		return MaterialLegacyLight(Base, Metallic, Roughness, Frame.Normal, V, L, Radiance);
	}
	return MaterialEvaluateLight(Base, Metallic, Roughness, Anisotropy, Clearcoat, CoatRoughness, Frame, V, L, Radiance);
}

#endif
