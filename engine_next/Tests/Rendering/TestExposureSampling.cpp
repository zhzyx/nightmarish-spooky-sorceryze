/**************************************************************************/
/*  TestExposureSampling.cpp                                              */
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
#include "engine_next/include/EngineNext/Rendering/PostProcessSettings.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>

namespace
{

// The algorithm is included from the production HLSLI. These adapters implement
// only the scalar/vector/resource syntax used by those production functions.
struct Float3
{
	float x;
	float y;
	float z;

	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};

struct Float4
{
	float x;
	float y;
	float z;
	float w;

	Float4(float fX, float fY, float fZ, float fW) : x(fX), y(fY), z(fZ), w(fW)
	{
	}
};

template <typename T>
struct StructuredBuffer
{
	const std::array<T, 258> *pValues;

	const T &operator[](std::uint32_t nIndex) const
	{
		return (*pValues)[nIndex];
	}
};

using uint = std::uint32_t;
using float3 = Float3;
using float4 = Float4;

float min(float fLeft, float fRight)
{
	return (std::min)(fLeft, fRight);
}

uint min(uint nLeft, uint nRight)
{
	return (std::min)(nLeft, nRight);
}

float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}

float clamp(float fValue, float fMinimum, float fMaximum)
{
	return std::clamp(fValue, fMinimum, fMaximum);
}

float saturate(float fValue)
{
	return clamp(fValue, 0, 1);
}

float lerp(float fFirst, float fSecond, float fAmount)
{
	return fFirst + (fSecond - fFirst) * fAmount;
}

bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}

float log2(float fValue)
{
	return std::log2(fValue);
}

float exp2(float fValue)
{
	return std::exp2(fValue);
}

#include "engine_next/Rendering/Shaders/ExposureMath.hlsli"

using Histogram = std::array<std::uint32_t, 258>;

Float4 Resolve(const Histogram &arrHistogram, Float4 stPrevious, Float4 stAdaptation,
			   Float4 stMetering = { 0.1f, 0.9f, -16, 24 }, Float4 stControl = { 2, 1, 0, 1 })
{
	return ResolveExposure(StructuredBuffer<uint>{ &arrHistogram }, stPrevious, stAdaptation, stMetering, stControl);
}

void CheckNear(float fActual, double dExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(static_cast<double>(fActual) - dExpected) <= 2e-5 * (std::max)(1.0, std::abs(dExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Exposure shader bins finite HDR in physical luminance units")
{
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 0, 0, 0 }, 1), 0U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, 1 }, 1), 102U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 16, 16, 16 }, 16), 102U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 65504, 65504, 65504 }, std::numeric_limits<float>::min()), 255U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, 1 }, std::numeric_limits<float>::max()), 0U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 16777216, 16777216, 16777216 }, 1), 255U);
	for (float fInvalid : { -1.0f, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ fInvalid, 1, 1 }, 1), 256U);
		ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, fInvalid, 1 }, 1), 256U);
		ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, fInvalid }, 1), 256U);
		ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, 1 }, fInvalid), 256U);
	}
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, 1 }, 0), 256U);
	ENGINE_NEXT_CHECK_EQ(ExposureHistogramBin({ 1, 1, 1 }, std::numeric_limits<float>::denorm_min()), 256U);
}

ENGINE_NEXT_TEST("Exposure shader reduces fractional percentile bins against CPU reference")
{
	Histogram arrHistogram{};
	arrHistogram[0] = 25;
	arrHistogram[128] = 50;
	arrHistogram[255] = 25;
	arrHistogram[256] = 1000;
	arrHistogram[257] = 100;
	float fLog = 0;
	ENGINE_NEXT_CHECK(ReduceExposureHistogram(StructuredBuffer<uint>{ &arrHistogram }, 0.2f, 0.6f, fLog));
	EngineNext::Rendering::ExposureSettings stSettings;
	stSettings.dLowPercentile = 0.2;
	stSettings.dHighPercentile = 0.6;
	std::array<std::uint32_t, 256> arrCpuHistogram{};
	std::copy_n(arrHistogram.begin(), arrCpuHistogram.size(), arrCpuHistogram.begin());
	double dLuminance = 0;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::MeterExposureHistogram(arrCpuHistogram, stSettings, dLuminance, arrDiagnostics));
	CheckNear(std::exp2(fLog), dLuminance);
	CheckNear(fLog, (5 * ExposureBinLogLuminance(0) + 35 * ExposureBinLogLuminance(128)) / 40);
	arrHistogram.fill(0);
	arrHistogram[200] = 3;
	arrHistogram[257] = 3;
	ENGINE_NEXT_CHECK(ReduceExposureHistogram(StructuredBuffer<uint>{ &arrHistogram }, 0.70878744f, 0.70878744f, fLog));
	ENGINE_NEXT_CHECK_EQ(fLog, ExposureBinLogLuminance(200));
	arrHistogram[257] = 0;
	fLog = 42;
	ENGINE_NEXT_CHECK(!ReduceExposureHistogram(StructuredBuffer<uint>{ &arrHistogram }, 0, 1, fLog));
	ENGINE_NEXT_CHECK_EQ(fLog, 42);
}

ENGINE_NEXT_TEST("Exposure shader manual and legacy modes preserve explicit multiplier")
{
	Histogram arrHistogram{};
	for (float fMode : { 0.0f, 1.0f })
	{
		const Float4 stResult = Resolve(arrHistogram, { 2, 0.5f, 0, 0 }, { 0, 0.25f, 0.75f, 0 },
										{ 0.1f, 0.9f, -16, 24 }, { fMode, 4, 0, 1 });
		ENGINE_NEXT_CHECK_EQ(stResult.x, 4);
		ENGINE_NEXT_CHECK_EQ(stResult.y, 2);
		CheckNear(stResult.z, -std::log2(4 * 1.2));
		ENGINE_NEXT_CHECK_EQ(stResult.w, 0);
	}
}

ENGINE_NEXT_TEST("Exposure shader automatic reset meters target without temporal lag")
{
	Histogram arrHistogram{};
	arrHistogram[80] = 100;
	arrHistogram[257] = 100;
	const Float4 stResult = Resolve(arrHistogram, { 1, 0.5f, 0, 0 }, { 0, 0.25f, 0.75f, 1 });
	const double dMeter = std::exp2(static_cast<double>(ExposureBinLogLuminance(80)));
	EngineNext::Rendering::ExposureSettings stSettings;
	stSettings.eMode = EngineNext::Rendering::ExposureMode::Automatic;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	double dTarget = 0;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ComputeExposureMultiplier(stSettings, 1, dMeter, dTarget, arrDiagnostics));
	CheckNear(stResult.x, dTarget);
	ENGINE_NEXT_CHECK_EQ(stResult.y, 1);
	CheckNear(stResult.w, dMeter);
	const Float4 stCompensated = Resolve(arrHistogram, { 1, 1, 0, 0 }, { 0.1f, 0.25f, 0.75f, 1 },
										 { 0.1f, 0.9f, -16, 24 }, { 2, 1, 1, 1 });
	CheckNear(stCompensated.x, 2 * stResult.x);
}

ENGINE_NEXT_TEST("Exposure shader adaptation follows CPU half lives and bounded time")
{
	EngineNext::Rendering::ExposureSettings stSettings;
	stSettings.eMode = EngineNext::Rendering::ExposureMode::Automatic;
	stSettings.dLightHalfLife = 0.1;
	stSettings.dDarkHalfLife = 0.2;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	for (float fPrevious : { 0.001f, 1.0f, 1000.0f })
	{
		for (float fTarget : { 0.001f, 1.0f, 1000.0f })
		{
			for (float fSeconds : { 0.0f, 0.05f, 0.1f, 100.0f })
			{
				double dExpected = 0;
				ENGINE_NEXT_CHECK(EngineNext::Rendering::AdaptExposureMultiplier(stSettings, fPrevious, fTarget, fSeconds, dExpected, arrDiagnostics));
				const float fActual = AdaptExposure(fPrevious, fTarget, fSeconds, 0.1f, 0.2f);
				CheckNear(fActual, dExpected);
				ENGINE_NEXT_CHECK(fActual >= (std::min)(fPrevious, fTarget));
				ENGINE_NEXT_CHECK(fActual <= (std::max)(fPrevious, fTarget));
			}
		}
	}
	ENGINE_NEXT_CHECK_EQ(AdaptExposure(1, 4, 0.1f, 0, 0), 4);
	ENGINE_NEXT_CHECK_EQ(AdaptExposure(1, 4, 0, 0, 0), 1);
}

ENGINE_NEXT_TEST("Exposure shader validates meter controls and retains finite fallback")
{
	Histogram arrHistogram{};
	arrHistogram[255] = 100;
	arrHistogram[257] = 100;
	const Float4 stClamped = Resolve(arrHistogram, { 2, 1, 0, 0 }, { 0.1f, 0.25f, 0.75f, 1 }, { 0, 1, 3, 3 });
	CheckNear(stClamped.x, std::exp2(-3) / 1.2);
	ENGINE_NEXT_CHECK_EQ(stClamped.z, 3);
	for (const Float4 &stBadMeter : { Float4{ -0.1f, 1, -16, 24 }, Float4{ 0.9f, 0.1f, -16, 24 }, Float4{ 0, 1, 4, 3 }, Float4{ 0, 1, -17, 24 } })
	{
		const Float4 stResult = Resolve(arrHistogram, { 2, 1, 0, 0 }, { 0.1f, 0.25f, 0.75f, 1 }, stBadMeter);
		ENGINE_NEXT_CHECK_EQ(stResult.x, 2);
		ENGINE_NEXT_CHECK_EQ(stResult.y, 2);
		ENGINE_NEXT_CHECK_EQ(stResult.w, 0);
	}
	arrHistogram.fill(0);
	arrHistogram[256] = 100;
	const Float4 stEmpty = Resolve(arrHistogram, { 2, 1, 0, 0 }, { 0.1f, 0.25f, 0.75f, 1 });
	ENGINE_NEXT_CHECK_EQ(stEmpty.x, 2);
	const Float4 stBadPrevious = Resolve(arrHistogram, { std::numeric_limits<float>::quiet_NaN(), 0, 0, 0 }, { 0, 0, 0, 0 },
										 { 0, 1, -16, 24 }, { 2, 1, 0, 4 });
	ENGINE_NEXT_CHECK_EQ(stBadPrevious.x, 4);
	ENGINE_NEXT_CHECK_EQ(stBadPrevious.y, 4);
}

ENGINE_NEXT_TEST("Exposure shader histogram reduction matches deterministic CPU distributions")
{
	std::uint32_t nRandom = 0x12345678;
	for (std::uint32_t nCase = 0; nCase < 64; ++nCase)
	{
		Histogram arrHistogram{};
		std::array<std::uint32_t, 256> arrCpuHistogram{};
		for (std::size_t nBin = 0; nBin < arrCpuHistogram.size(); ++nBin)
		{
			nRandom = nRandom * 1664525U + 1013904223U;
			const std::uint32_t nCount = nRandom % 1001;
			arrCpuHistogram[nBin] = nCount;
			arrHistogram[nBin] = nCount;
			arrHistogram[257] += nCount;
		}
		EngineNext::Rendering::ExposureSettings stSettings;
		const float fLow = static_cast<float>(nCase % 10) * 0.02f;
		const float fHigh = 0.75f + static_cast<float>(nCase % 11) * 0.02f;
		stSettings.dLowPercentile = fLow;
		stSettings.dHighPercentile = fHigh;
		EngineNext::Assets::Diagnostics arrDiagnostics;
		double dLuminance = 0;
		ENGINE_NEXT_CHECK(EngineNext::Rendering::MeterExposureHistogram(arrCpuHistogram, stSettings, dLuminance, arrDiagnostics));
		float fLog = 0;
		ENGINE_NEXT_CHECK(ReduceExposureHistogram(StructuredBuffer<uint>{ &arrHistogram }, fLow, fHigh, fLog));
		CheckNear(fLog, std::log2(dLuminance));
	}
}
