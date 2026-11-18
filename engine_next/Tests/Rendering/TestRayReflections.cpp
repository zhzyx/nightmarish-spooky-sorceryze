/**************************************************************************/
/*  TestRayReflections.cpp                                                */
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
#include "engine_next/include/EngineNext/Rendering/RayReflectionSettings.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace
{
namespace Math
{
struct Float2
{
	float x;
	float y;
	Float2(float fX, float fY);
};
struct Float3
{
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ);
};
Float2::Float2(float fX, float fY)
{
	x = fX;
	y = fY;
}
Float3::Float3(float fX, float fY, float fZ)
{
	x = fX;
	y = fY;
	z = fZ;
}
Float3 operator/(Float3 stA, float fB)
{
	return { stA.x / fB, stA.y / fB, stA.z / fB };
}
float dot(Float3 stA, Float3 stB)
{
	return stA.x * stB.x + stA.y * stB.y + stA.z * stB.z;
}
float min(float fA, float fB)
{
	return std::min(fA, fB);
}
float max(float fA, float fB)
{
	return std::max(fA, fB);
}
float clamp(float fValue, float fLow, float fHigh)
{
	return std::clamp(fValue, fLow, fHigh);
}
float saturate(float fValue)
{
	return clamp(fValue, 0, 1);
}
float lerp(float fA, float fB, float fWeight)
{
	return fA + (fB - fA) * fWeight;
}
using std::abs;
using std::exp2;
using std::isfinite;
using std::isnan;
using std::log2;
using std::pow;
using std::sqrt;
using uint = std::uint32_t;
using float2 = Float2;
using float3 = Float3;
#include "engine_next/Rendering/Shaders/RayReflectionSampling.hlsli"
} // namespace Math
} // namespace

ENGINE_NEXT_TEST("Ray reflection budget rounds odd dimensions and rejects oversized resources transactionally")
{
	using namespace EngineNext::Rendering;
	RayReflectionSettings stSettings;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	RayReflectionBudget stBudget;
	ENGINE_NEXT_CHECK(BuildRayReflectionBudget(stSettings, 641, 479, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nWidth, 321U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nHeight, 240U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nPixels, 77040ULL);
	ENGINE_NEXT_CHECK(BuildRayReflectionBudget(stSettings, 3840, 2160, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nWidth, 1920U);
	ENGINE_NEXT_CHECK_EQ(stBudget.nPayloadBytes, 514253184ULL);
	ENGINE_NEXT_CHECK(BuildRayReflectionBudget(stSettings, 1, 1, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nPayloadBytes, 632ULL);
	stBudget.nWidth = 99;
	stSettings.nMaxGpuBytes = 631;
	ENGINE_NEXT_CHECK(!BuildRayReflectionBudget(stSettings, 1, 1, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nWidth, 99U);
	stSettings = {};
	ENGINE_NEXT_CHECK(!BuildRayReflectionBudget(stSettings, 32767, 32767, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK(!BuildRayReflectionBudget(stSettings, 0, 480, stBudget, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBudget.nWidth, 99U);
}

ENGINE_NEXT_TEST("Ray reflection settings reject invalid values even when disabled")
{
	using namespace EngineNext::Rendering;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	RayReflectionSettings stSettings;
	ENGINE_NEXT_CHECK(ValidateRayReflectionSettings(stSettings, arrDiagnostics));
	stSettings.nResolutionDivisor = 3;
	ENGINE_NEXT_CHECK(!ValidateRayReflectionSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.nSamplesPerLobe = 0;
	ENGINE_NEXT_CHECK(!ValidateRayReflectionSettings(stSettings, arrDiagnostics));
	stSettings.nSamplesPerLobe = 5;
	ENGINE_NEXT_CHECK(!ValidateRayReflectionSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.dHistoryWeight = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!ValidateRayReflectionSettings(stSettings, arrDiagnostics));
	stSettings = {};
	stSettings.dDepthThreshold = std::numeric_limits<double>::infinity();
	ENGINE_NEXT_CHECK(!ValidateRayReflectionSettings(stSettings, arrDiagnostics));
}

ENGINE_NEXT_TEST("Ray reflection history rejects disocclusion and invalid surface metadata")
{
	Math::RtHistoryParameters stParameters{ .02F, .9F, .15F, .9F, 16 };
	Math::RtSurface stCurrent{ 2, { 0, 0, 1 }, .3F, 7 };
	Math::RtSurface stPrevious = stCurrent;
	ENGINE_NEXT_CHECK(Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stPrevious.Object = 8;
	ENGINE_NEXT_CHECK(!Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stPrevious = stCurrent;
	stPrevious.Depth = 2.1F;
	ENGINE_NEXT_CHECK(!Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stPrevious.Depth = 2.01F;
	ENGINE_NEXT_CHECK(Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stPrevious.Normal = { 0, 0, 0 };
	ENGINE_NEXT_CHECK(!Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stPrevious = stCurrent;
	stPrevious.Roughness = .7F;
	ENGINE_NEXT_CHECK(!Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
	stCurrent.Object = 0;
	ENGINE_NEXT_CHECK(!Math::RtSurfaceMatches(stCurrent, stPrevious, 2, stParameters));
}

ENGINE_NEXT_TEST("Ray reflection hit confidence distinguishes sharp object changes from rough mixtures")
{
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ 1, 2 }, { 1, 2 }, .1F), 1.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ 1, 2 }, { 2, 2 }, .1F), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ 1, 2 }, { 2, 2 }, .8F), .25F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ 1, 2 }, { Math::RT_MISS_ID, 0 }, .8F), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ Math::RT_MISS_ID, 0 }, { Math::RT_MISS_ID, 0 }, .1F), 1.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ Math::RT_INVALID_ID, 0 }, { Math::RT_INVALID_ID, 0 }, .8F), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHitConfidence({ 1, 2 }, { 1, 20 }, .1F), 0.0F);
}

ENGINE_NEXT_TEST("Ray reflection random values stay inside the open unit interval")
{
	double dSum = 0;
	for (std::uint32_t nIndex = 0; nIndex < 65536; ++nIndex)
	{
		const float fValue = Math::RtRandom(nIndex);
		ENGINE_NEXT_CHECK(fValue > 0 && fValue < 1);
		ENGINE_NEXT_CHECK_EQ(fValue, Math::RtRandom(nIndex));
		dSum += fValue;
	}
	ENGINE_NEXT_CHECK(std::abs(dSum / 65536 - .5) < .01);
}

ENGINE_NEXT_TEST("Ray reflection signed moments remain finite for HDR and reset invalid history")
{
	const Math::Float2 stPositive = Math::RtUpdateMoments({ 0, 0 }, { 1, 1, 1 }, 0);
	const Math::Float2 stMixed = Math::RtUpdateMoments(stPositive, { -1, -1, -1 }, .5F);
	ENGINE_NEXT_CHECK(std::abs(stMixed.x) < 1e-6F);
	ENGINE_NEXT_CHECK(std::abs(stMixed.y - 1) < 1e-6F);
	ENGINE_NEXT_CHECK(std::abs(Math::RtVariance(stMixed) - 1) < 1e-6F);
	const Math::Float2 stLarge = Math::RtUpdateMoments({ 0, 0 }, { 1e20F, 1e20F, 1e20F }, 0);
	ENGINE_NEXT_CHECK(std::isfinite(stLarge.x) && std::isfinite(stLarge.y));
	ENGINE_NEXT_CHECK(stLarge.x < 67 && stLarge.y < 4489);
	const float fNan = std::numeric_limits<float>::quiet_NaN();
	const Math::Float2 stReset = Math::RtUpdateMoments({ fNan, 0 }, { 0, 0, 0 }, 1);
	ENGINE_NEXT_CHECK_EQ(stReset.x, 0.0F);
	ENGINE_NEXT_CHECK_EQ(stReset.y, 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtClipHistory(10, -2, 3), 3.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtClipHistory(-10, -2, 3), -2.0F);
}

ENGINE_NEXT_TEST("Ray reflection spatial filter respects geometric and luminance boundaries")
{
	ENGINE_NEXT_CHECK_EQ(Math::RtSpatialWeight(1, 0, 0, 0, 0, 1, true), 1.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtSpatialWeight(1, 0, 0, 0, 0, 1, false), 0.0F);
	ENGINE_NEXT_CHECK(Math::RtSpatialWeight(1, .1F, 0, 0, 0, 1, true) < .02F);
	ENGINE_NEXT_CHECK(Math::RtSpatialWeight(.5F, 0, 0, 0, 0, 1, true) < 1e-6F);
	ENGINE_NEXT_CHECK(Math::RtSpatialWeight(1, 0, 0, 1, 0, 1, true) < .02F);
	Math::RtHistoryParameters stParameters{ .02F, .9F, .15F, .9F, 16 };
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryWeight(16, 0, stParameters), 0.0F);
	ENGINE_NEXT_CHECK(Math::RtHistoryWeight(1, 1, stParameters) == .5F);
	ENGINE_NEXT_CHECK(Math::RtHistoryWeight(1000, 1, stParameters) <= .9F);
}

ENGINE_NEXT_TEST("Ray reflection reprojection preserves static full and half grid cells")
{
	for (const float fDimension : { 1.0F, 160.0F, 321.0F, 1920.0F })
	{
		for (int nPixel = 0; nPixel < static_cast<int>(fDimension); ++nPixel)
		{
			const Math::Float2 stPixel(static_cast<float>(nPixel), static_cast<float>(nPixel));
			const Math::Float2 stDimensions(fDimension, fDimension);
			const Math::Float2 stStatic = Math::RtPreviousGridCoordinate(stPixel, Math::Float2(0, 0), stDimensions);
			ENGINE_NEXT_CHECK_EQ(stStatic.x, stPixel.x);
			ENGINE_NEXT_CHECK_EQ(stStatic.y, stPixel.y);
			const Math::Float2 stMoved = Math::RtPreviousGridCoordinate(stPixel, Math::Float2(1 / fDimension, -1 / fDimension), stDimensions);
			ENGINE_NEXT_CHECK(std::abs(stMoved.x - (stPixel.x + 1)) < 0.0002F);
			ENGINE_NEXT_CHECK(std::abs(stMoved.y - (stPixel.y - 1)) < 0.0002F);
		}
	}
}

ENGINE_NEXT_TEST("Ray reflection footprint rejects wrong hit color moments and count before filtering")
{
	const float fAccepted = Math::RtHistoryTapWeight(.5F, Math::RtHitConfidence({ 1, 2 }, { 1, 2 }, .04F));
	const float fRejected = Math::RtHistoryTapWeight(.5F, Math::RtHitConfidence({ 1, 2 }, { 2, 2 }, .04F));
	const float fTotal = fAccepted + fRejected;
	ENGINE_NEXT_CHECK_EQ(fAccepted, .5F);
	ENGINE_NEXT_CHECK_EQ(fRejected, 0.0F);
	ENGINE_NEXT_CHECK_EQ(fAccepted / fTotal, 1.0F);
	ENGINE_NEXT_CHECK_EQ(fRejected / fTotal, 0.0F);
	ENGINE_NEXT_CHECK_EQ((4 * fAccepted + 100 * fRejected) / fTotal, 4.0F);
	ENGINE_NEXT_CHECK_EQ((16 * fAccepted + 10000 * fRejected) / fTotal, 16.0F);
	ENGINE_NEXT_CHECK_EQ((16 * fAccepted + 64 * fRejected) / fTotal, 16.0F);
	const Math::RtHistoryParameters stParameters{ .02F, .9F, .15F, .9F, 16 };
	const float fBlend = Math::RtHistoryWeight(16, fTotal, stParameters);
	const float fCorrectBlue = fBlend * fRejected / fTotal;
	const float fOldBlue = fBlend * .5F;
	ENGINE_NEXT_CHECK_EQ(fCorrectBlue, 0.0F);
	// Negative control: applying rejection only after bilinear filtering leaks blue.
	ENGINE_NEXT_CHECK(std::abs(fOldBlue - .225F) < .000001F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(.5F, .25F), .125F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(.5F, 0), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(-1, 1), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(2, 2), 1.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(std::numeric_limits<float>::quiet_NaN(), 1), 0.0F);
	ENGINE_NEXT_CHECK_EQ(Math::RtHistoryTapWeight(1, std::numeric_limits<float>::infinity()), 0.0F);
}
