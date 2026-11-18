/**************************************************************************/
/*  TestGiMaterialSampling.cpp                                            */
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
#include <cstdint>
#include <limits>
namespace GiMaterialTests
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
#include "engine_next/Rendering/Shaders/GiMaterialSampling.hlsli"

ENGINE_NEXT_TEST("GI diffuse bands equal the angular transmission integral")
{
	constexpr std::uint32_t SAMPLES = 65536;
	constexpr double PI = 3.14159265358979323846;
	for (float fCoat : { 0.0F, .3F, 1.0F })
	{
		std::array<double, 3> arrIntegral{};
		for (std::uint32_t nIndex = 0; nIndex < SAMPLES; ++nIndex)
		{
			const double dMu = (nIndex + .5) / SAMPLES;
			const double dTransmission = (1 - std::pow(1 - dMu, 5)) * (1 - fCoat * (.04 + .96 * std::pow(1 - dMu, 5)));
			arrIntegral[0] += dMu * dTransmission;
			arrIntegral[1] += dMu * dMu * dTransmission;
			arrIntegral[2] += dMu * (.5 * (3 * dMu * dMu - 1)) * dTransmission;
		}
		const Float3 vBands = GiMaterialDiffuseBands(fCoat);
		const float arrActual[] = { vBands.x, vBands.y, vBands.z };
		for (std::uint32_t nBand = 0; nBand < 3; ++nBand)
		{
			const double dExpected = arrIntegral[nBand] * 2 * PI / SAMPLES;
			ENGINE_NEXT_CHECK(std::abs(arrActual[nBand] - dExpected) < 4e-7);
		}
	}
}

ENGINE_NEXT_TEST("GI material diffuse matches a white environment integrated through the production lobe")
{
	constexpr std::uint32_t SAMPLES = 32768;
	constexpr double PI = 3.14159265358979323846;
	const MaterialFrame stFrame = MaterialBuildFrame({ 0, 0, 1 }, { 1, 0, 0 }, -1, .7F);
	for (float fMetallic : { 0.0F, .4F, 1.0F })
	{
		for (float fCoat : { 0.0F, .5F, 1.0F })
		{
			for (float fNoV : { .01F, .3F, 1.0F })
			{
				const Float3 vBase{ 1, .4F, .1F };
				const Float3 vView{ std::sqrt(1 - fNoV * fNoV), 0, fNoV };
				std::array<double, 3> arrIntegral{};
				for (std::uint32_t nIndex = 0; nIndex < SAMPLES; ++nIndex)
				{
					const float fMu = (nIndex + .5F) / SAMPLES;
					const Float3 vLight{ std::sqrt(1 - fMu * fMu), 0, fMu };
					const MaterialLobes stLobes = MaterialEvaluateLobes(vBase, fMetallic, .5F, -.7F, fCoat, .2F, stFrame, vView, vLight);
					arrIntegral[0] += stLobes.Diffuse.x * fMu;
					arrIntegral[1] += stLobes.Diffuse.y * fMu;
					arrIntegral[2] += stLobes.Diffuse.z * fMu;
				}
				const Float3 vActual = GiMaterialDiffuseFactor(vBase, fMetallic, fCoat, fNoV) * GiMaterialDiffuseBands(fCoat).x;
				const float arrActual[] = { vActual.x, vActual.y, vActual.z };
				for (std::uint32_t nChannel = 0; nChannel < 3; ++nChannel)
				{
					const double dExpected = arrIntegral[nChannel] * 2 * PI / SAMPLES;
					ENGINE_NEXT_CHECK(std::abs(arrActual[nChannel] - dExpected) < 3e-6);
					ENGINE_NEXT_CHECK(arrActual[nChannel] >= 0 && arrActual[nChannel] <= 1);
					if (fMetallic == 1)
					{
						ENGINE_NEXT_CHECK_EQ(arrActual[nChannel], 0.0F);
					}
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("GI material bands reproduce each retained SH band")
{
	constexpr std::uint32_t SAMPLES = 65536;
	constexpr double PI = 3.14159265358979323846;
	for (float fCoat : { 0.0F, 1.0F })
	{
		const Float3 vBands = GiMaterialDiffuseBands(fCoat);
		const double arrExpected[] = { vBands.x * .2820947918, vBands.y * .4886025119, vBands.z * .6307831306 };
		std::array<double, 3> arrActual{};
		for (std::uint32_t nIndex = 0; nIndex < SAMPLES; ++nIndex)
		{
			const double dMu = (nIndex + .5) / SAMPLES;
			const double dT = dMu * (1 - std::pow(1 - dMu, 5)) * (1 - fCoat * (.04 + .96 * std::pow(1 - dMu, 5)));
			arrActual[0] += .2820947918 * dT;
			arrActual[1] += .4886025119 * dMu * dT;
			arrActual[2] += .3153915653 * (3 * dMu * dMu - 1) * dT;
		}
		for (std::uint32_t nBand = 0; nBand < 3; ++nBand)
		{
			ENGINE_NEXT_CHECK(std::abs(arrActual[nBand] * 2 * PI / SAMPLES - arrExpected[nBand]) < 3e-7);
		}
	}
}

} // namespace GiMaterialTests
