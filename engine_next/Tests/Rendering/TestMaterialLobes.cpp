/**************************************************************************/
/*  TestMaterialLobes.cpp                                                 */
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

#include "engine_next/Tests/TestFramework.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace
{

// Minimal HLSL value adapters. The formulas under test are included unchanged.
struct Float2
{
	float x;
	float y;
	Float2(float fX, float fY) : x(fX), y(fY)
	{
	}
};

struct Float3
{
	float x;
	float y;
	float z;
	Float3() : x(0), y(0), z(0)
	{
	}
	Float3(float fValue) : x(fValue), y(fValue), z(fValue)
	{
	}
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};

Float3 operator+(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x + stRight.x, stLeft.y + stRight.y, stLeft.z + stRight.z };
}
Float3 operator-(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y, stLeft.z - stRight.z };
}
Float3 operator*(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y, stLeft.z * stRight.z };
}
Float3 operator*(Float3 stLeft, float fRight)
{
	return { stLeft.x * fRight, stLeft.y * fRight, stLeft.z * fRight };
}
Float3 operator*(float fLeft, Float3 stRight)
{
	return stRight * fLeft;
}
Float3 operator/(Float3 stLeft, float fRight)
{
	return { stLeft.x / fRight, stLeft.y / fRight, stLeft.z / fRight };
}
float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}
Float3 cross(Float3 stLeft, Float3 stRight)
{
	return { stLeft.y * stRight.z - stLeft.z * stRight.y, stLeft.z * stRight.x - stLeft.x * stRight.z, stLeft.x * stRight.y - stLeft.y * stRight.x };
}
float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}
Float3 max(Float3 stLeft, Float3 stRight)
{
	return { max(stLeft.x, stRight.x), max(stLeft.y, stRight.y), max(stLeft.z, stRight.z) };
}
float abs(float fValue)
{
	return std::abs(fValue);
}
float sqrt(float fValue)
{
	return std::sqrt(fValue);
}
float rsqrt(float fValue)
{
	return 1 / std::sqrt(fValue);
}
float sin(float fValue)
{
	return std::sin(fValue);
}
float cos(float fValue)
{
	return std::cos(fValue);
}
float pow(float fValue, float fPower)
{
	return std::pow(fValue, fPower);
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}
float saturate(float fValue)
{
	return clamp(fValue, 0, 1);
}
Float3 saturate(Float3 stValue)
{
	return { saturate(stValue.x), saturate(stValue.y), saturate(stValue.z) };
}
Float3 lerp(Float3 stLeft, Float3 stRight, float fFactor)
{
	return stLeft * (1 - fFactor) + stRight * fFactor;
}

using float2 = Float2;
using float3 = Float3;
// Compatibility reference captured from the existing Deferred light helpers.
// BEGIN MATERIAL LEGACY REFERENCE
float3 CurrentUnitDirection(float3 Direction, float3 Fallback)
{
	float Maximum = max(abs(Direction.x), max(abs(Direction.y), abs(Direction.z)));
	float3 Scaled = Direction / max(Maximum, 1.0e-38f);
	return Maximum > 0 ? Scaled * rsqrt(max(dot(Scaled, Scaled), 1.0e-38f)) : Fallback;
}

float3 CurrentSafeDirection(float3 Direction)
{
	return CurrentUnitDirection(Direction, float3(0, 0, 1));
}

float3 CurrentFresnel(float Cosine, float3 F0)
{
	return F0 + (1 - F0) * pow(saturate(1 - Cosine), 5);
}

float3 CurrentEvaluateLight(float3 Base, float Metallic, float Roughness, float3 N, float3 V, float3 L, float3 Radiance)
{
	float3 H = CurrentSafeDirection(V + L);
	float NoL = saturate(dot(N, L));
	float NoV = max(saturate(dot(N, V)), 0.001f);
	float NoH = saturate(dot(N, H));
	float VoH = saturate(dot(V, H));
	float Alpha = max(Roughness * Roughness, 0.0025f);
	float A2 = Alpha * Alpha;
	float D = A2 / max(3.14159265f * pow(NoH * NoH * (A2 - 1) + 1, 2), 0.00001f);
	float K = pow(Roughness + 1, 2) / 8;
	float G = NoV / (NoV * (1 - K) + K) * NoL / max(NoL * (1 - K) + K, 0.0001f);
	float3 F = CurrentFresnel(VoH, lerp(0.04f, Base, Metallic));
	float3 Specular = D * G * F / max(4 * NoV * NoL, 0.0001f);
	return ((1 - F) * (1 - Metallic) * Base / 3.14159265f + Specular) * Radiance * NoL;
}

// END MATERIAL LEGACY REFERENCE
#include "engine_next/Rendering/Shaders/MaterialLobes.hlsli"

void Near(float fValue, double dExpected, double dTolerance = 0.00002)
{
	ENGINE_NEXT_CHECK(std::abs(fValue - dExpected) <= dTolerance * (std::max)(1.0, std::abs(dExpected)));
}

void Near(Float3 stValue, Float3 stExpected, double dTolerance = 0.00002)
{
	Near(stValue.x, stExpected.x, dTolerance);
	Near(stValue.y, stExpected.y, dTolerance);
	Near(stValue.z, stExpected.z, dTolerance);
}

Float3 Sum(MaterialLobes stValue)
{
	return stValue.Diffuse + stValue.Specular + stValue.Clearcoat;
}

MaterialFrame Frame(float fHandedness = 1, float fRotation = 0)
{
	return MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, fHandedness, fRotation);
}

Float3 Direction(float fZ, float fPhi)
{
	const float fRadius = std::sqrt((std::max)(0.0F, 1 - fZ * fZ));
	return { fRadius * std::cos(fPhi), fRadius * std::sin(fPhi), fZ };
}

} // namespace

ENGINE_NEXT_TEST("Material compatibility entry reproduces the current Deferred light formula")
{
	for (float fRoughness : { 0.0F, 0.01F, 0.05F, 0.2F, 0.7F, 1.0F })
	{
		for (float fMetallic : { 0.0F, 0.5F, 1.0F })
		{
			for (float fViewZ : { 0.01F, 0.3F, 1.0F })
			{
				for (float fLightZ : { 0.01F, 0.6F, 1.0F })
				{
					const Float3 stV = Direction(fViewZ, 0.3F);
					const Float3 stL = Direction(fLightZ, 1.4F);
					const Float3 stActual = MaterialLegacyLight({ 0.7F, 0.2F, 0.1F }, fMetallic, fRoughness, { 0, 0, 1 }, stV, stL, { 1, 2, 3 });
					const Float3 stExpected = CurrentEvaluateLight({ 0.7F, 0.2F, 0.1F }, fMetallic, fRoughness, { 0, 0, 1 }, stV, stL, { 1, 2, 3 });
					Near(stActual, stExpected, 0.0000001);
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("Material override routing preserves absent and zero-valued legacy materials")
{
	const Float3 stV = Direction(0.6F, 0.1F);
	const Float3 stL = Direction(0.8F, 1.1F);
	const Float3 stLegacy = MaterialLegacyLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, Frame().Normal, stV, stL, { 1, 2, 3 });
	Near(MaterialShadeLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0.7F, 1, 0.2F, false, Frame(), stV, stL, { 1, 2, 3 }), stLegacy, 0);
	Near(MaterialShadeLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0, 0, 0.2F, true, Frame(), stV, stL, { 1, 2, 3 }), stLegacy, 0);
	Near(MaterialShadeLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0.7F, 1, 0.2F, true, Frame(), stV, stL, { 1, 2, 3 }), MaterialEvaluateLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0.7F, 1, 0.2F, Frame(), stV, stL, { 1, 2, 3 }), 0);
}

ENGINE_NEXT_TEST("Zero anisotropy reduces to isotropic GGX D and correlated Smith visibility")
{
	for (float fRoughness : { 0.0F, 0.05F, 0.2F, 0.7F, 1.0F })
	{
		const Float2 stAxes = MaterialRoughnessAxes(fRoughness, 0);
		ENGINE_NEXT_CHECK_EQ(stAxes.x, stAxes.y);
		const double dAlpha = stAxes.x;
		for (float fZ : { 0.01F, 0.3F, 0.8F, 1.0F })
		{
			const Float3 stH = Direction(fZ, 0);
			const double dTerm = 1 + (dAlpha * dAlpha - 1) * fZ * fZ;
			Near(MaterialGGXD(stH, Frame(), stAxes), dAlpha * dAlpha / (3.14159265 * dTerm * dTerm), 0.0001);
			const Float3 stV = Direction(fZ, 0.5F);
			const Float3 stL = Direction(0.4F, 1.2F);
			const double dV = std::sqrt(dAlpha * dAlpha * (1 - fZ * fZ) + fZ * fZ);
			const double dL = std::sqrt(dAlpha * dAlpha * (1 - 0.16) + 0.16);
			Near(MaterialSmithV(stV, stL, Frame(), stAxes), 0.5 / (0.4 * dV + fZ * dL));
		}
	}
}

ENGINE_NEXT_TEST("Material tangent frame remains orthonormal under mirror fallback and rotation")
{
	for (float fHandedness : { -1.0F, 1.0F })
	{
		for (float fAngle : { 0.0F, 0.4F, 1.570796326F })
		{
			const MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 5 }, { 3, 0, 7 }, fHandedness, fAngle);
			Near(dot(stFrame.Normal, stFrame.Tangent), 0);
			Near(dot(stFrame.Normal, stFrame.Bitangent), 0);
			Near(dot(stFrame.Tangent, stFrame.Bitangent), 0);
			Near(dot(stFrame.Tangent, stFrame.Tangent), 1);
			Near(dot(stFrame.Bitangent, stFrame.Bitangent), 1);
			Near(dot(cross(stFrame.Normal, stFrame.Tangent), stFrame.Bitangent), fHandedness);
		}
	}
	const MaterialFrame stFallback = MaterialBuildFrame({ 0, 0, 0 }, { 0, 0, 0 }, 1, 0);
	Near(stFallback.Normal, { 0, 0, 1 });
	Near(stFallback.Tangent, { 1, 0, 0 });
}

ENGINE_NEXT_TEST("Anisotropy sign swaps axes and isotropic material ignores tangent rotation")
{
	const Float3 stV = Direction(0.8F, 0.3F);
	const Float3 stL = Direction(0.6F, 1.1F);
	const Float3 stPositive = Sum(MaterialEvaluateLobes({ 0.8F, 0.6F, 0.3F }, 1, 0.4F, 0.8F, 0, 0.1F, Frame(), stV, stL));
	const Float3 stNegative = Sum(MaterialEvaluateLobes({ 0.8F, 0.6F, 0.3F }, 1, 0.4F, -0.8F, 0, 0.1F, Frame(1, 1.570796326F), stV, stL));
	Near(stPositive, stNegative);
	const Float3 stIsotropic = Sum(MaterialEvaluateLobes({ 0.3F, 0.6F, 0.8F }, 0, 0.6F, 0, 1, 0.2F, Frame(), stV, stL));
	Near(stIsotropic, Sum(MaterialEvaluateLobes({ 0.3F, 0.6F, 0.8F }, 0, 0.6F, 0, 1, 0.2F, Frame(1, 0.923F), stV, stL)));
}

ENGINE_NEXT_TEST("Clearcoat attenuates base lobes on both interface crossings and is reciprocal")
{
	const Float3 stV = Direction(0.3F, 0.7F);
	const Float3 stL = Direction(0.7F, 1.7F);
	const MaterialLobes stBase = MaterialEvaluateLobes({ 0.7F, 0.3F, 0.1F }, 0.2F, 0.5F, 0.7F, 0, 0.2F, Frame(), stV, stL);
	const MaterialLobes stCoat = MaterialEvaluateLobes({ 0.7F, 0.3F, 0.1F }, 0.2F, 0.5F, 0.7F, 1, 0.2F, Frame(), stV, stL);
	const float fTransmission = (1 - MaterialCoatFresnel(0.3F)) * (1 - MaterialCoatFresnel(0.7F));
	Near(stCoat.Diffuse, stBase.Diffuse * fTransmission);
	Near(stCoat.Specular, stBase.Specular * fTransmission);
	Near(stBase.Clearcoat, { 0, 0, 0 });
	ENGINE_NEXT_CHECK(stCoat.Clearcoat.x > 0);
	Near(Sum(stCoat), Sum(MaterialEvaluateLobes({ 0.7F, 0.3F, 0.1F }, 0.2F, 0.5F, 0.7F, 1, 0.2F, Frame(), stL, stV)));
}

ENGINE_NEXT_TEST("Material extreme roughness and anisotropy remain finite and nonnegative")
{
	for (float fRoughness : { 0.0F, 1.0F })
	{
		for (float fAnisotropy : { -1.0F, 0.0F, 1.0F })
		{
			for (float fView : { 0.0001F, 0.2F, 1.0F })
			{
				const Float3 stValue = Sum(MaterialEvaluateLobes({ 1, 1, 1 }, 1, fRoughness, fAnisotropy, 1, fRoughness, Frame(-1), Direction(fView, 1.2F), Direction(0.0001F, 1.3F)));
				ENGINE_NEXT_CHECK(MaterialFinite(stValue));
				ENGINE_NEXT_CHECK(stValue.x >= 0 && stValue.y >= 0 && stValue.z >= 0);
			}
		}
	}
	const float fNaN = std::numeric_limits<float>::quiet_NaN();
	Near(Sum(MaterialEvaluateLobes({ fNaN, 0, 0 }, 0, 0.4F, 0, 1, 0.1F, Frame(), { 0, 0, 1 }, { 0, 0, 1 })), { 0, 0, 0 });
	Near(Sum(MaterialEvaluateLobes({ 1, 1, 1 }, 0, 0.4F, fNaN, 1, 0.1F, Frame(), { 0, 0, 1 }, { 0, 0, 1 })), { 0, 0, 0 });
	Near(Sum(MaterialEvaluateLobes({ 1, 1, 1 }, 0, 0.4F, 0, 1, 0.1F, Frame(), { 0, 0, -1 }, { 0, 0, 1 })), { 0, 0, 0 });
}

ENGINE_NEXT_TEST("Material light entry applies cosine and radiance and rejects nonfinite light")
{
	const Float3 stV = Direction(0.6F, 0.1F);
	const Float3 stL = Direction(0.8F, 1.1F);
	const Float3 stBrdf = Sum(MaterialEvaluateLobes({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0.7F, 1, 0.2F, Frame(), stV, stL));
	const Float3 stLight = MaterialEvaluateLight({ 0.8F, 0.4F, 0.2F }, 0.5F, 0.3F, 0.7F, 1, 0.2F, Frame(), stV, stL, { 1, 2, 3 });
	Near(stLight, stBrdf * Float3(1, 2, 3) * 0.8F);
	Near(MaterialEvaluateLight({ 1, 1, 1 }, 0, 0.3F, 0, 0, 0.2F, Frame(), stV, stL, { -1, -2, -3 }), { 0, 0, 0 });
	Near(MaterialEvaluateLight({ 1, 1, 1 }, 0, 0.3F, 0, 0, 0.2F, Frame(), stV, stL, { std::numeric_limits<float>::infinity(), 0, 0 }), { 0, 0, 0 });
}

ENGINE_NEXT_TEST("Layered GGX basic hemispherical energy stays bounded for white dielectric and metal")
{
	constexpr int MU_STEPS = 256;
	constexpr int PHI_STEPS = 256;
	double dMinimumEnergy = 10;
	double dMaximumEnergy = 0;
	int nCases = 0;
	for (float fRoughness : { 0.2F, 0.5F, 1.0F })
	{
		for (float fMetallic : { 0.0F, 1.0F })
		{
			for (float fAnisotropy : { -0.9F, 0.0F, 0.9F })
			{
				for (float fCoat : { 0.0F, 1.0F })
				{
					for (float fViewZ : { 0.3F, 1.0F })
					{
						double dEnergy = 0;
						const Float3 stV = Direction(fViewZ, 0.4F);
						for (int nMu = 0; nMu < MU_STEPS; ++nMu)
						{
							const float fMu = (nMu + 0.5F) / MU_STEPS;
							for (int nPhi = 0; nPhi < PHI_STEPS; ++nPhi)
							{
								const Float3 stL = Direction(fMu, (nPhi + 0.5F) * (2 * MATERIAL_PI / PHI_STEPS));
								const Float3 stBrdf = Sum(MaterialEvaluateLobes({ 1, 1, 1 }, fMetallic, fRoughness, fAnisotropy, fCoat, 0.2F, Frame(), stV, stL));
								dEnergy += stBrdf.x * fMu;
							}
						}
						dEnergy *= 2 * MATERIAL_PI / (MU_STEPS * PHI_STEPS);
						dMinimumEnergy = (std::min)(dMinimumEnergy, dEnergy);
						dMaximumEnergy = (std::max)(dMaximumEnergy, dEnergy);
						++nCases;
						if (dEnergy > 1.03)
						{
							std::cout << "MATERIAL_ENERGY roughness=" << fRoughness << " metallic=" << fMetallic << " anisotropy=" << fAnisotropy << " coat=" << fCoat << " view=" << fViewZ << " integral=" << dEnergy << '\n';
						}
						ENGINE_NEXT_CHECK(std::isfinite(dEnergy) && dEnergy >= 0 && dEnergy <= 1.03);
					}
				}
			}
		}
	}
	std::cout << "MATERIAL_HEMISPHERE cases=" << nCases << " minimum=" << dMinimumEnergy << " maximum=" << dMaximumEnergy << '\n';
}

ENGINE_NEXT_TEST("Material tangent projection handles large finite coordinates")
{
	const float fLarge = std::numeric_limits<float>::max();
	const MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 1 }, { fLarge, fLarge, fLarge }, -1, 0);
	const float fDiagonal = std::sqrt(0.5F);
	Near(stFrame.Tangent, { fDiagonal, fDiagonal, 0 });
	Near(stFrame.Bitangent, { fDiagonal, -fDiagonal, 0 });
	Near(dot(stFrame.Tangent, stFrame.Normal), 0);
	Near(dot(stFrame.Tangent, stFrame.Bitangent), 0);
	ENGINE_NEXT_CHECK(MaterialFinite(stFrame.Tangent));
	ENGINE_NEXT_CHECK(MaterialFinite(stFrame.Bitangent));
}
