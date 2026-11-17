/**************************************************************************/
/*  TestMaterialEnvironment.cpp                                           */
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
#include <cstdint>
#include <iostream>

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
using uint = std::uint32_t;
#include "engine_next/Rendering/Shaders/MaterialEnvironment.hlsli"

MaterialFrame Frame(float fSign = 1, float fRotation = 0)
{
	return MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, fSign, fRotation);
}

Float3 Direction(float fZ, float fPhi)
{
	const float fRadius = std::sqrt((std::max)(0.0F, 1 - fZ * fZ));
	return { fRadius * std::cos(fPhi), fRadius * std::sin(fPhi), fZ };
}

std::array<double, 3> WhiteEnvironment(float fRoughness, float fAnisotropy, float fCoat, float fMetallic, Float3 stView, MaterialFrame stFrame, uint nCount)
{
	std::array<double, 3> arrSum{};
	for (uint nIndex = 0; nIndex < nCount; ++nIndex)
	{
		const Float2 stXi = MaterialHammersley(nIndex, nCount);
		const MaterialEnvironmentSample stBase = MaterialEnvironmentBaseSample({ 1, 1, 1 }, fMetallic, fRoughness, fAnisotropy, fCoat, .2F, stFrame, stView, stXi);
		const MaterialEnvironmentSample stCoat = MaterialEnvironmentCoatSample({ 1, 1, 1 }, fMetallic, fRoughness, fAnisotropy, fCoat, .2F, stFrame, stView, stXi);
		const MaterialEnvironmentSample stDiffuse = MaterialEnvironmentDiffuseSample({ 1, 1, 1 }, fMetallic, fRoughness, fAnisotropy, fCoat, .2F, stFrame, stView, stXi);
		const Float3 stWeight = stBase.Weight + stCoat.Weight + stDiffuse.Weight;
		arrSum[0] += stWeight.x;
		arrSum[1] += stWeight.y;
		arrSum[2] += stWeight.z;
	}
	for (double &dSum : arrSum)
	{
		dSum /= nCount;
	}
	return arrSum;
}

std::array<double, 3> DirectIntegral(float fRoughness, float fAnisotropy, float fCoat, float fMetallic, Float3 stView)
{
	std::array<double, 3> arrSum{};
	constexpr uint SAMPLE_SIDE = 256;
	for (uint nY = 0; nY < SAMPLE_SIDE; ++nY)
	{
		const float fZ = (nY + .5F) / SAMPLE_SIDE;
		for (uint nX = 0; nX < SAMPLE_SIDE; ++nX)
		{
			const Float3 stLight = Direction(fZ, 2 * MATERIAL_PI * (nX + .5F) / SAMPLE_SIDE);
			const MaterialLobes stLobes = MaterialEvaluateLobes({ 1, 1, 1 }, fMetallic, fRoughness, fAnisotropy, fCoat, .2F, Frame(), stView, stLight);
			const Float3 stValue = (stLobes.Diffuse + stLobes.Specular + stLobes.Clearcoat) * fZ;
			arrSum[0] += stValue.x;
			arrSum[1] += stValue.y;
			arrSum[2] += stValue.z;
		}
	}
	for (double &dSum : arrSum)
	{
		dSum *= 2 * 3.14159265358979323846 / (SAMPLE_SIDE * SAMPLE_SIDE);
	}
	return arrSum;
}

} // namespace

ENGINE_NEXT_TEST("Material environment sequence is deterministic")
{
	const Float2 stFirst = MaterialHammersley(0, 4);
	const Float2 stSecond = MaterialHammersley(1, 4);
	const Float2 stThird = MaterialHammersley(2, 4);
	ENGINE_NEXT_CHECK_EQ(stFirst.x, .125F);
	ENGINE_NEXT_CHECK_EQ(stFirst.y, 0.0F);
	ENGINE_NEXT_CHECK_EQ(stSecond.x, .375F);
	ENGINE_NEXT_CHECK_EQ(stSecond.y, .5F);
	ENGINE_NEXT_CHECK_EQ(stThird.y, .25F);
	ENGINE_NEXT_CHECK_EQ(MaterialHammersley(3, 4).y, .75F);
	ENGINE_NEXT_CHECK(MaterialEnvironmentUsesLegacy(false, 1, 1));
	ENGINE_NEXT_CHECK(MaterialEnvironmentUsesLegacy(true, 0, 0));
	ENGINE_NEXT_CHECK(!MaterialEnvironmentUsesLegacy(true, -.5F, 0));
	ENGINE_NEXT_CHECK(!MaterialEnvironmentUsesLegacy(true, 0, 1));
	const Float3 stLegacy = MaterialLegacyLight({ .7F, .3F, .2F }, .5F, .4F, Frame().Normal, { 0, 0, 1 }, { 0, 0, 1 }, { 1, 1, 1 });
	const Float3 stRouted = MaterialShadeLight({ .7F, .3F, .2F }, .5F, .4F, 0, 0, .1F, true, Frame(), { 0, 0, 1 }, { 0, 0, 1 }, { 1, 1, 1 });
	ENGINE_NEXT_CHECK_EQ(stRouted.x, stLegacy.x);
	ENGINE_NEXT_CHECK_EQ(stRouted.y, stLegacy.y);
	ENGINE_NEXT_CHECK_EQ(stRouted.z, stLegacy.z);
}

ENGINE_NEXT_TEST("Material environment samples are finite at poles and extreme lobe widths")
{
	for (float fView : { .0001F, .3F, 1.0F })
	{
		for (float fRoughness : { 0.0F, .5F, 1.0F })
		{
			for (float fAnisotropy : { -1.0F, 0.0F, 1.0F })
			{
				for (float fCoat : { 0.0F, 1.0F })
				{
					for (uint nIndex = 0; nIndex < 32; ++nIndex)
					{
						const Float2 stXi = MaterialHammersley(nIndex, 32);
						const Float3 stV = Direction(fView, .7F);
						const MaterialEnvironmentSample arrSamples[] = {
							MaterialEnvironmentBaseSample({ 1, .2F, .5F }, .5F, fRoughness, fAnisotropy, fCoat, fRoughness, Frame(-1), stV, stXi),
							MaterialEnvironmentCoatSample({ 1, .2F, .5F }, .5F, fRoughness, fAnisotropy, fCoat, fRoughness, Frame(-1), stV, stXi),
							MaterialEnvironmentDiffuseSample({ 1, .2F, .5F }, .5F, fRoughness, fAnisotropy, fCoat, fRoughness, Frame(-1), stV, stXi)
						};
						for (const MaterialEnvironmentSample &stSample : arrSamples)
						{
							ENGINE_NEXT_CHECK(MaterialFinite(stSample.Direction));
							ENGINE_NEXT_CHECK(MaterialFinite(stSample.Weight));
							ENGINE_NEXT_CHECK(std::isfinite(stSample.Pdf) && stSample.Pdf >= 0);
							ENGINE_NEXT_CHECK(stSample.Weight.x >= 0 && stSample.Weight.y >= 0 && stSample.Weight.z >= 0);
							if (stSample.Pdf > 0)
							{
								ENGINE_NEXT_CHECK(stSample.Direction.z > 0);
								ENGINE_NEXT_CHECK(std::abs(dot(stSample.Direction, stSample.Direction) - 1) < .00001F);
							}
						}
					}
				}
			}
		}
	}
	const Float2 stInvalid(std::numeric_limits<float>::quiet_NaN(), 0);
	const MaterialEnvironmentSample stRejected = MaterialEnvironmentBaseSample({ 1, 1, 1 }, 0, .5F, 0, 1, .2F, Frame(), { 0, 0, 1 }, stInvalid);
	ENGINE_NEXT_CHECK_EQ(stRejected.Pdf, 0.0F);
	ENGINE_NEXT_CHECK_EQ(stRejected.Weight.x, 0.0F);
}

ENGINE_NEXT_TEST("Material environment importance sampling matches direct white integration")
{
	for (float fAnisotropy : { -.8F, .8F })
	{
		for (float fCoat : { 0.0F, 1.0F })
		{
			const Float3 stView = Direction(.6F, .4F);
			const std::array<double, 3> arrExpected = DirectIntegral(.6F, fAnisotropy, fCoat, .25F, stView);
			const std::array<double, 3> arrActual = WhiteEnvironment(.6F, fAnisotropy, fCoat, .25F, stView, Frame(), 32768);
			for (uint nChannel = 0; nChannel < 3; ++nChannel)
			{
				ENGINE_NEXT_CHECK(std::abs(arrActual[nChannel] - arrExpected[nChannel]) < .006);
			}
		}
	}
}

ENGINE_NEXT_TEST("Material environment white furnace bounds all tested lobe combinations")
{
	double dMinimum = 100;
	double dMaximum = 0;
	uint nCases = 0;
	for (float fRoughness : { .2F, .5F, 1.0F })
	{
		for (float fAnisotropy : { -.9F, 0.0F, .9F })
		{
			for (float fCoat : { 0.0F, 1.0F })
			{
				for (float fMetallic : { 0.0F, 1.0F })
				{
					for (float fView : { .3F, 1.0F })
					{
						const std::array<double, 3> arrValue = WhiteEnvironment(fRoughness, fAnisotropy, fCoat, fMetallic, Direction(fView, .4F), Frame(), 8192);
						for (double dValue : arrValue)
						{
							ENGINE_NEXT_CHECK(std::isfinite(dValue) && dValue >= 0 && dValue <= 1.03);
							dMinimum = (std::min)(dMinimum, dValue);
							dMaximum = (std::max)(dMaximum, dValue);
						}
						++nCases;
					}
				}
			}
		}
	}
	std::cout << "MATERIAL_ENVIRONMENT_FURNACE cases=" << nCases << " minimum=" << dMinimum << " maximum=" << dMaximum << '\n';
}

ENGINE_NEXT_TEST("Material environment weights preserve mirror and axis symmetries")
{
	const Float3 stView = Direction(.6F, .4F);
	const std::array<double, 3> arrPositive = WhiteEnvironment(.5F, .8F, 1, .5F, stView, Frame(), 16384);
	const std::array<double, 3> arrNegative = WhiteEnvironment(.5F, -.8F, 1, .5F, stView, Frame(1, MATERIAL_PI * .5F), 16384);
	const std::array<double, 3> arrMirror = WhiteEnvironment(.5F, .8F, 1, .5F, { stView.x, -stView.y, stView.z }, Frame(-1), 16384);
	for (uint nChannel = 0; nChannel < 3; ++nChannel)
	{
		ENGINE_NEXT_CHECK(std::abs(arrPositive[nChannel] - arrNegative[nChannel]) < .001);
		ENGINE_NEXT_CHECK(std::abs(arrPositive[nChannel] - arrMirror[nChannel]) < .00001);
	}
}

ENGINE_NEXT_TEST("Material environment sampling changes direction with anisotropy")
{
	const Float3 stView(0, 0, 1);
	const Float2 stXi(.5F, 0);
	const MaterialEnvironmentSample stWide = MaterialEnvironmentBaseSample({ 1, 1, 1 }, 1, .4F, .9F, 0, .2F, Frame(), stView, stXi);
	const MaterialEnvironmentSample stNarrow = MaterialEnvironmentBaseSample({ 1, 1, 1 }, 1, .4F, -.9F, 0, .2F, Frame(), stView, stXi);
	const MaterialEnvironmentSample stRotated = MaterialEnvironmentBaseSample({ 1, 1, 1 }, 1, .4F, .9F, 0, .2F, Frame(1, MATERIAL_PI * .5F), stView, stXi);
	ENGINE_NEXT_CHECK(stWide.Direction.x > stNarrow.Direction.x);
	ENGINE_NEXT_CHECK(stWide.Pdf > 0 && stNarrow.Pdf > 0 && stRotated.Pdf > 0);
	ENGINE_NEXT_CHECK(std::abs(stRotated.Direction.x) < .00001F);
	ENGINE_NEXT_CHECK(std::abs(stRotated.Direction.y - stWide.Direction.x) < .00001F);
	const Float3 stHalf = MaterialDirection(stView + stWide.Direction, Frame().Normal);
	const float fExpectedPdf = MaterialGGXD(stHalf, Frame(), MaterialRoughnessAxes(.4F, .9F)) * stHalf.z / (4 * dot(stView, stHalf));
	ENGINE_NEXT_CHECK(std::abs(stWide.Pdf - fExpectedPdf) < .0001F);
}
