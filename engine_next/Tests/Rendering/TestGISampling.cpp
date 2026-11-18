/**************************************************************************/
/*  TestGISampling.cpp                                                    */
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

namespace
{
struct Float2
{
	float x;
	float y;
	Float2(float fX, float fY);
};
Float2::Float2(float fX, float fY) : x(fX), y(fY)
{
}
struct Float3
{
	float x = 0;
	float y = 0;
	float z = 0;
	Float3() = default;
	Float3(float fX, float fY, float fZ);
};
Float3::Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
{
}
Float3 operator*(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x * stRight.x, stLeft.y * stRight.y, stLeft.z * stRight.z };
}
Float3 operator*(Float3 stValue, float fScale)
{
	return { stValue.x * fScale, stValue.y * fScale, stValue.z * fScale };
}
Float3 operator/(Float3 stValue, float fScale)
{
	return { stValue.x / fScale, stValue.y / fScale, stValue.z / fScale };
}
float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
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
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
float clamp(float fValue, float fLow, float fHigh)
{
	return std::clamp(fValue, fLow, fHigh);
}
float saturate(float fValue)
{
	return clamp(fValue, 0, 1);
}
Float3 saturate(Float3 stValue)
{
	return { saturate(stValue.x), saturate(stValue.y), saturate(stValue.z) };
}
float floor(float fValue)
{
	return std::floor(fValue);
}
float cos(float fValue)
{
	return std::cos(fValue);
}
float sin(float fValue)
{
	return std::sin(fValue);
}
float min(float fLeft, float fRight)
{
	return (std::min)(fLeft, fRight);
}
std::uint32_t max(std::uint32_t nLeft, std::uint32_t nRight)
{
	return (std::max)(nLeft, nRight);
}
using float2 = Float2;
using float3 = Float3;
using uint = std::uint32_t;
#include "engine_next/Rendering/Shaders/GISamplingMath.hlsli"

void Near(float fActual, float fExpected, float fTolerance = 0.00001F)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual) && std::abs(fActual - fExpected) <= fTolerance);
}
} // namespace

ENGINE_NEXT_TEST("GI equal-area ray sets remain unit length and reproducible")
{
	for (uint nRays : { 16U, 32U, 128U, 1024U })
	{
		for (uint nEpoch : { 0U, 1U, 33U, UINT32_MAX })
		{
			float fMeanY = 0;
			for (uint nRay = 0; nRay < nRays; ++nRay)
			{
				const Float3 stDirection = GiRayDirection(nRay, nRays, 11, nEpoch);
				const Float3 stAgain = GiRayDirection(nRay, nRays, 11, nEpoch);
				Near(dot(stDirection, stDirection), 1);
				ENGINE_NEXT_CHECK(stDirection.x == stAgain.x && stDirection.y == stAgain.y && stDirection.z == stAgain.z);
				fMeanY += stDirection.y;
			}
			ENGINE_NEXT_CHECK(std::abs(fMeanY / nRays) <= 1.0F / nRays + 0.00001F);
		}
	}
	const Float3 stFirst = GiRayDirection(0, 32, 11, 0);
	const Float3 stNext = GiRayDirection(0, 32, 11, 1);
	ENGINE_NEXT_CHECK(stFirst.x != stNext.x || stFirst.y != stNext.y || stFirst.z != stNext.z);
}
ENGINE_NEXT_TEST("GI ray dispatch covers D3D12 row limits and the maximum supported budget")
{
	constexpr uint ROW_THREADS = 65535U * 64U;
	for (uint nRays : { 1U, 64U, ROW_THREADS, ROW_THREADS + 1, 65536U * 64U, 65536U * 1024U })
	{
		const uint nGroups = (nRays + 63U) / 64U;
		const uint nGroupsX = (std::min)(nGroups, 65535U);
		const uint nGroupsY = (nGroups + 65534U) / 65535U;
		ENGINE_NEXT_CHECK(nGroupsX <= 65535U && nGroupsY <= 65535U);
		const uint nLast = nRays - 1;
		ENGINE_NEXT_CHECK_EQ(GiRayLinearIndex(nLast % ROW_THREADS, nLast / ROW_THREADS, ROW_THREADS), nLast);
		const uint nLastDispatched = GiRayLinearIndex(nGroupsX * 64U - 1, nGroupsY - 1, ROW_THREADS);
		ENGINE_NEXT_CHECK(nLastDispatched >= nLast && nLastDispatched - nLast < ROW_THREADS);
	}
	ENGINE_NEXT_CHECK_EQ(GiRayLinearIndex(ROW_THREADS - 1, 0, ROW_THREADS), ROW_THREADS - 1);
	ENGINE_NEXT_CHECK_EQ(GiRayLinearIndex(0, 1, ROW_THREADS), ROW_THREADS);
}
ENGINE_NEXT_TEST("GI octahedral directions round trip including axes and folds")
{
	for (int nX = -5; nX <= 5; ++nX)
	{
		for (int nY = -5; nY <= 5; ++nY)
		{
			for (int nZ = -5; nZ <= 5; ++nZ)
			{
				if (nX == 0 && nY == 0 && nZ == 0)
				{
					continue;
				}
				const Float3 stDirection = GiDirection({ static_cast<float>(nX), static_cast<float>(nY), static_cast<float>(nZ) });
				const Float2 stUv = GiOctEncode(stDirection);
				const Float3 stRestored = GiOctDecode(stUv);
				ENGINE_NEXT_CHECK(stUv.x >= 0 && stUv.x <= 1 && stUv.y >= 0 && stUv.y <= 1);
				Near(dot(stDirection, stRestored), 1);
			}
		}
	}
}
ENGINE_NEXT_TEST("GI directional moment kernels preserve constant distance")
{
	for (uint nRays : { 16U, 32U, 128U })
	{
		for (uint nTexel = 0; nTexel < 64; ++nTexel)
		{
			const Float3 stDirection = GiOctDecode({ (static_cast<float>(nTexel % 8) + 0.5F) / 8, (static_cast<float>(nTexel / 8) + 0.5F) / 8 });
			float fWeightSum = 0;
			float fDistanceSum = 0;
			float fSquareSum = 0;
			for (uint nRay = 0; nRay < nRays; ++nRay)
			{
				const float fWeight = GiDistanceWeight(GiRayDirection(nRay, nRays, 7, 3), stDirection);
				ENGINE_NEXT_CHECK(fWeight >= 0 && fWeight <= 1.00001F);
				fWeightSum += fWeight;
				fDistanceSum += fWeight * 0.25F;
				fSquareSum += fWeight * 0.0625F;
			}
			ENGINE_NEXT_CHECK(fWeightSum > 0);
			Near(fDistanceSum / fWeightSum, 0.25F);
			Near(fSquareSum / fWeightSum, 0.0625F);
		}
	}
}
ENGINE_NEXT_TEST("GI clipmap handover spans exactly two cells")
{
	for (int nStep = 0; nStep <= 20; ++nStep)
	{
		const float fDistance = static_cast<float>(nStep) * 0.1F;
		Near(GiClipmapEdgeWeight({ fDistance, 8, 8 }, { 23, 23, 23 }), fDistance / 2);
		Near(GiClipmapEdgeWeight({ 23 - fDistance, 8, 8 }, { 23, 23, 23 }), fDistance / 2);
	}
	Near(GiClipmapEdgeWeight({ -1, 8, 8 }, { 23, 23, 23 }), 0);
	Near(GiClipmapEdgeWeight({ 4, 8, 8 }, { 23, 23, 23 }), 1);
}
ENGINE_NEXT_TEST("GI normalized distances preserve weak scale and bound overflow")
{
	const float fMin = std::numeric_limits<float>::min();
	const float fMax = std::numeric_limits<float>::max();
	Near(GiRelativeDistance({ fMin, 0, 0 }, fMin), 1);
	Near(GiRelativeDistance({ fMax, 0, 0 }, fMax), 1);
	ENGINE_NEXT_CHECK(GiRelativeDistance({ fMax, fMax, fMax }, fMin) == fMax);
	ENGINE_NEXT_CHECK(GiRelativeDistance({ 0, 0, 0 }, fMin) == 0);
	ENGINE_NEXT_CHECK(GiRelativeDistance({ std::numeric_limits<float>::infinity(), 0, 0 }, 1) == fMax);
	ENGINE_NEXT_CHECK(GiRelativeDistance({ 1, 0, 0 }, 0) == fMax);
}
ENGINE_NEXT_TEST("GI surface-normal weights prefer probes above the surface")
{
	Near(GiProbeNormalWeight({ 0, 0, 1 }, { 0, 0, 1 }), 1);
	Near(GiProbeNormalWeight({ 0, 0, -1 }, { 0, 0, 1 }), 0.0001F);
	Near(GiProbeNormalWeight({ 1, 0, 0 }, { 0, 0, 1 }), 0.25F);
}
ENGINE_NEXT_TEST("GI ray basis reconstructs constant irradiance through history and visibility")
{
	GiSh9 stCurrent = GiZeroSh();
	for (uint nRay = 0; nRay < 1024; ++nRay)
	{
		stCurrent = GiAccumulateRay(stCurrent, GiRayDirection(nRay, 1024, 1, 1), { 1, 1, 1 }, 4 * GI_PI / 1024);
	}
	const float fWeight = GiHistoryWeight(1, 1, 0.9F, 0.2F, true);
	const GiSh9 stBlended = GiBlendSh(stCurrent, stCurrent, fWeight);
	const Float3 stIrradiance = GiIrradiance(stBlended, { 0, 0, 1 });
	// The finite 1024-ray quadrature has a small nonzero SH projection error.
	Near(stIrradiance.x, GI_PI, 0.003F);
	const Float2 stMoments = GiUpdateMoments({ 1, 1 }, 1, fWeight, true);
	Near(GiVisibility(0.5F, stMoments, 0, 0), 1);
	const Float3 stBounced = GiBounceRadiance({ 0, 0, 0 }, stIrradiance, { 0.5F, 0.5F, 0.5F }, 1);
	Near(stBounced.x, 0.5F, 0.001F);
	float fSum = 0;
	for (uint nCorner = 0; nCorner < 8; ++nCorner)
	{
		fSum += GiTrilinearWeight({ 0.3F, 0.4F, 0.8F }, nCorner);
	}
	Near(fSum, 1);
}
ENGINE_NEXT_TEST("GI custom SH convolution preserves default bands and scales each order")
{
	GiSh9 stSh = GiZeroSh();
	for (uint nTerm = 0; nTerm < 9; ++nTerm)
	{
		stSh.Coefficients[nTerm] = { 0.1F * (nTerm + 1), 0.03F * (nTerm + 1), 0.07F * (nTerm + 1) };
	}
	for (Float3 stNormal : { Float3(1, 0, 0), Float3(0, 1, 0), Float3(0, 0, 1), Float3(0, 0, -1) })
	{
		const Float3 stDefault = GiIrradiance(stSh, stNormal);
		const Float3 stCustom = GiIrradianceBands(stSh, stNormal, { GI_PI, 2 * GI_PI / 3, GI_PI / 4 });
		Near(stCustom.x, stDefault.x);
		Near(stCustom.y, stDefault.y);
		Near(stCustom.z, stDefault.z);
		const Float3 stDouble = GiIrradianceBands(stSh, stNormal, { 2 * GI_PI, 4 * GI_PI / 3, GI_PI / 2 });
		Near(stDouble.x, stDefault.x * 2);
		Near(stDouble.y, stDefault.y * 2);
		Near(stDouble.z, stDefault.z * 2);
	}
	GiSh9 stSingle = GiZeroSh();
	stSingle.Coefficients[2] = { 1, 1, 1 };
	const Float3 stLinear = GiIrradianceBands(stSingle, { 0, 0, 1 }, { 0, 3, 0 });
	Near(stLinear.x, 3 * 0.4886025119F);
	const Float3 stInvalid = GiIrradianceBands(stSh, { 0, 0, 1 }, { std::numeric_limits<float>::quiet_NaN(), 1, 1 });
	Near(stInvalid.x, 0);
}
