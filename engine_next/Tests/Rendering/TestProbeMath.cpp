/**************************************************************************/
/*  TestProbeMath.cpp                                                     */
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
using float2 = Float2;
using float3 = Float3;
using uint = std::uint32_t;
#include "engine_next/Rendering/Shaders/ProbeMath.hlsli"

void Near(float fActual, double dExpected, double dTolerance = 0.00001)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual) && std::abs(fActual - dExpected) <= dTolerance * (std::max)(1.0, std::abs(dExpected)));
}
void Near(Float3 stValue, Float3 stExpected)
{
	Near(stValue.x, stExpected.x);
	Near(stValue.y, stExpected.y);
	Near(stValue.z, stExpected.z);
}
constexpr std::array<std::array<float, 3>, 6> DIRECTIONS{ { { 1, 0, 0 }, { -1, 0, 0 }, { 0, 1, 0 }, { 0, -1, 0 }, { 0, 0, 1 }, { 0, 0, -1 } } };
} //namespace

ENGINE_NEXT_TEST("SH constant radiance decodes to pi times radiance on every cardinal normal")
{
	GiSh9 stSh = GiZeroSh();
	for (const std::array<float, 3> &arrDirection : DIRECTIONS)
	{
		stSh = GiAccumulateRay(stSh, { arrDirection[0], arrDirection[1], arrDirection[2] }, { 0.2F, 0.7F, 1.3F }, 4 * GI_PI / 6);
	}
	for (const std::array<float, 3> &arrNormal : DIRECTIONS)
	{
		Near(GiIrradiance(stSh, { arrNormal[0], arrNormal[1], arrNormal[2] }), Float3(0.2F, 0.7F, 1.3F) * GI_PI);
	}
}
ENGINE_NEXT_TEST("SH linear directional radiance follows analytic cosine convolution")
{
	GiSh9 stSh = GiZeroSh();
	for (const std::array<float, 3> &arrDirection : DIRECTIONS)
	{
		const float fRadiance = 0.6F + 0.3F * arrDirection[2];
		stSh = GiAccumulateRay(stSh, { arrDirection[0], arrDirection[1], arrDirection[2] }, { fRadiance, fRadiance, fRadiance }, 4 * GI_PI / 6);
	}
	for (const std::array<float, 3> &arrNormal : DIRECTIONS)
	{
		const float fExpected = GI_PI * 0.6F + 2 * GI_PI / 3 * 0.3F * arrNormal[2];
		Near(GiIrradiance(stSh, { arrNormal[0], arrNormal[1], arrNormal[2] }), { fExpected, fExpected, fExpected });
	}
}
ENGINE_NEXT_TEST("Probe distance moments and visibility bound suppress occluded samples")
{
	Float2 stMoments = GiUpdateMoments({ 0, 0 }, 2, 0, false);
	stMoments = GiUpdateMoments(stMoments, 4, 0.5F, true);
	Near(stMoments.x, 3);
	Near(stMoments.y, 10);
	Near(GiVisibility(3, stMoments, 0, 0), 1);
	Near(GiVisibility(4, stMoments, 0, 0), 0.125);
	Near(GiVisibility(5, stMoments, 0, 0), 0.008);
	Near(GiVisibility(4, stMoments, 0.5F, 0), 0.512);
	Near(GiVisibility(4, { 3, 9 }, 0, 0), 0);
	float fPrevious = 1;
	for (int nStep = 0; nStep < 100; ++nStep)
	{
		const float fVisibility = GiVisibility(nStep * 0.1F, stMoments, 0, 0.0001F);
		ENGINE_NEXT_CHECK(fVisibility >= 0 && fVisibility <= fPrevious);
		fPrevious = fVisibility;
	}
}
ENGINE_NEXT_TEST("Trilinear probe weights sum to one at boundaries and interior")
{
	for (float fX : { 0.0F, 0.1F, 0.8F, 1.0F })
	{
		for (float fY : { 0.0F, 0.3F, 1.0F })
		{
			float fSum = 0;
			for (uint nCorner = 0; nCorner < 8; ++nCorner)
			{
				const float fWeight = GiTrilinearWeight({ fX, fY, 0.6F }, nCorner);
				ENGINE_NEXT_CHECK(fWeight >= 0 && fWeight <= 1);
				fSum += fWeight;
			}
			Near(fSum, 1);
		}
	}
}
ENGINE_NEXT_TEST("Probe history rejects resets and lighting changes before filtering")
{
	Near(GiHistoryWeight(1, 1, 0.95F, 0.2F, true), 0.95);
	Near(GiHistoryWeight(1, 10, 0.95F, 0.2F, true), 0);
	Near(GiHistoryWeight(10, 1, 0.95F, 0.2F, true), 0);
	Near(GiHistoryWeight(1, 1, 0.95F, 0.2F, false), 0);
	GiSh9 stOld = GiZeroSh();
	GiSh9 stNew = GiZeroSh();
	stNew.Coefficients[0] = { 1, 2, 3 };
	Near(GiBlendSh(stOld, stNew, 0.8F).Coefficients[0], { 0.2F, 0.4F, 0.6F });
	stOld.Coefficients[0].x = std::numeric_limits<float>::quiet_NaN();
	Near(GiBlendSh(stOld, stNew, 0.8F).Coefficients[0], { 1, 2, 3 });
}
ENGINE_NEXT_TEST("Previous-generation diffuse bounce converges under bounded albedo")
{
	Float3 stRadiance{ 0, 0, 0 };
	for (int nBounce = 0; nBounce < 64; ++nBounce)
	{
		const Float3 stNext = GiBounceRadiance({ 1, 1, 1 }, stRadiance * GI_PI, { 0.8F, 0.8F, 0.8F }, 1);
		ENGINE_NEXT_CHECK(stNext.x >= stRadiance.x && stNext.x <= 5.00001F);
		stRadiance = stNext;
	}
	Near(stRadiance, { 5, 5, 5 });
	Near(GiBounceRadiance({ 1, 2, 3 }, { 100, 100, 100 }, { 1, 1, 1 }, 0), { 1, 2, 3 });
}
ENGINE_NEXT_TEST("SH direction scaling and invalid ray handling remain finite")
{
	const GiBasis9 stBasis = GiBasis({ std::numeric_limits<float>::max(), 0, 0 });
	Near(stBasis.Values[3], 0.4886025119);
	GiSh9 stSh = GiZeroSh();
	stSh = GiAccumulateRay(stSh, { 0, 0, 1 }, { std::numeric_limits<float>::quiet_NaN(), 0, 0 }, 1);
	Near(stSh.Coefficients[0], { 0, 0, 0 });
	Near(GiVisibility(std::numeric_limits<float>::infinity(), { 1, 1 }, 0, 0), 0);
	Near(GiHistoryWeight(1, std::numeric_limits<float>::quiet_NaN(), 0.9F, 0.2F, true), 0);
	stSh.Coefficients[0] = { -1, -1, -1 };
	Near(GiIrradiance(stSh, { 0, 0, 1 }), { 0, 0, 0 });
}

ENGINE_NEXT_TEST("GI distance visibility is invariant for weak and large world scales")
{
	for (float fScale : { 1e-15F, 1.0F, 1e15F })
	{
		Near(GiVisibility(4 * fScale, { 3 * fScale, 10 * fScale * fScale }, 0, 0), 0.125);
		Near(GiVisibility(5 * fScale, { 3 * fScale, 10 * fScale * fScale }, 0, 0), 0.008);
		Near(GiVisibility(4 * fScale, { 3 * fScale, 10 * fScale * fScale }, 0.5F * fScale, 0), 0.512);
	}
	Near(GiVisibility(4, { 3, 10 }, -1, 0), 0);
	Near(GiVisibility(4, { 3, 10 }, 0, -1), 0);
}

ENGINE_NEXT_TEST("GI history responds to weak lighting and defines zero threshold")
{
	Near(GiHistoryWeight(1e-20F, 1e-18F, 0.95F, 0.2F, true), 0);
	Near(GiHistoryWeight(0, 1e-20F, 0.95F, 0.2F, true), 0);
	Near(GiHistoryWeight(1e-20F, 1e-20F, 0.95F, 0, true), 0.95);
	Near(GiHistoryWeight(0, 0, 0.95F, 0, true), 0.95);
	Near(GiHistoryWeight(1, 2, 0.95F, 0, true), 0);
	Near(GiHistoryWeight(1, 1, 0.95F, -1, true), 0);
	Near(GiHistoryWeight(-1, -1, 0.95F, 0.2F, true), 0);
}

ENGINE_NEXT_TEST("GI moment and radiance guards keep finite extreme output")
{
	const float fMaximum = std::numeric_limits<float>::max();
	const Float2 stInvalid = GiUpdateMoments({ 1, 1 }, fMaximum, 0.5F, true);
	Near(stInvalid.x, 0);
	Near(stInvalid.y, 0);
	GiSh9 stSh = GiZeroSh();
	for (int nRay = 0; nRay < 64; ++nRay)
	{
		stSh = GiAccumulateRay(stSh, { 0, 0, 1 }, { fMaximum, fMaximum, fMaximum }, 1);
	}
	for (std::uint32_t nIndex = 0; nIndex < 9; ++nIndex)
	{
		ENGINE_NEXT_CHECK(GiFinite(stSh.Coefficients[nIndex]));
	}
	ENGINE_NEXT_CHECK(GiFinite(GiIrradiance(stSh, { 0, 0, 1 })));
	const Float3 stBounce = GiBounceRadiance({ fMaximum, fMaximum, fMaximum }, { fMaximum, fMaximum, fMaximum }, { 1, 1, 1 }, 1);
	ENGINE_NEXT_CHECK(GiFinite(stBounce));
	ENGINE_NEXT_CHECK_EQ(stBounce.x, fMaximum);
	Near(GiBlendScalar(-fMaximum, fMaximum, 0.5F), 0);
	ENGINE_NEXT_CHECK(std::isfinite(GiBlendScalar(fMaximum, fMaximum, 0.99F)));
}

ENGINE_NEXT_TEST("GI invalid interpolation and zero direction cannot inject a contribution")
{
	Near(GiTrilinearWeight({ 0.5F, 0.5F, 0.5F }, 8), 0);
	Near(GiTrilinearWeight({ std::numeric_limits<float>::quiet_NaN(), 0, 0 }, 0), 0);
	GiSh9 stEmpty = GiZeroSh();
	stEmpty = GiAccumulateRay(stEmpty, { 0, 0, 0 }, { 1, 1, 1 }, 1);
	Near(stEmpty.Coefficients[0], { 0, 0, 0 });
	stEmpty.Coefficients[0].x = std::numeric_limits<float>::infinity();
	stEmpty = GiAccumulateRay(stEmpty, { 0, 0, 1 }, { 1, 1, 1 }, 1);
	ENGINE_NEXT_CHECK(GiFinite(stEmpty.Coefficients[0]));
}

ENGINE_NEXT_TEST("SH quadratic radiance follows the analytic second band convolution")
{
	const std::array<float, 4> arrZ{ -0.8611363116F, -0.3399810436F, 0.3399810436F, 0.8611363116F };
	const std::array<float, 4> arrWeight{ 0.3478548451F, 0.6521451549F, 0.6521451549F, 0.3478548451F };
	GiSh9 stSh = GiZeroSh();
	for (std::size_t nZ = 0; nZ < arrZ.size(); ++nZ)
	{
		const float fZ = arrZ[nZ];
		const float fRadius = std::sqrt(1 - fZ * fZ);
		const float fRadiance = 0.6F + 0.2F * (3 * fZ * fZ - 1) * 0.5F;
		for (int nAzimuth = 0; nAzimuth < 8; ++nAzimuth)
		{
			const float fPhi = 2 * GI_PI * nAzimuth / 8;
			stSh = GiAccumulateRay(stSh, { fRadius * std::cos(fPhi), fRadius * std::sin(fPhi), fZ }, { fRadiance, fRadiance, fRadiance }, arrWeight[nZ] * 2 * GI_PI / 8);
		}
	}
	for (const std::array<float, 3> &arrNormal : DIRECTIONS)
	{
		const float fP2 = (3 * arrNormal[2] * arrNormal[2] - 1) * 0.5F;
		const float fExpected = GI_PI * 0.6F + (GI_PI / 4) * 0.2F * fP2;
		Near(GiIrradiance(stSh, { arrNormal[0], arrNormal[1], arrNormal[2] }), { fExpected, fExpected, fExpected });
	}
}
