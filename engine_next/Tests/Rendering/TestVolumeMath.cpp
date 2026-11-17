/**************************************************************************/
/*  TestVolumeMath.cpp                                                    */
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

#include "engine_next/include/EngineNext/Rendering/VolumeGrid.h"
#include "engine_next/Tests/TestFramework.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <initializer_list>
#include <limits>

namespace
{

struct Bool3
{
	bool x;
	bool y;
	bool z;
};

struct Float3
{
	float x;
	float y;
	float z;
	Float3(float fX, float fY, float fZ) : x(fX), y(fY), z(fZ)
	{
	}
};

Float3 operator-(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x - stRight.x, stLeft.y - stRight.y, stLeft.z - stRight.z };
}
Float3 operator/(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x / stRight.x, stLeft.y / stRight.y, stLeft.z / stRight.z };
}
Bool3 operator>(Float3 stLeft, Float3 stRight)
{
	return { stLeft.x > stRight.x, stLeft.y > stRight.y, stLeft.z > stRight.z };
}
Bool3 operator<(Float3 stLeft, float fValue)
{
	return { stLeft.x < fValue, stLeft.y < fValue, stLeft.z < fValue };
}
bool all(Bool3 stValue)
{
	return stValue.x && stValue.y && stValue.z;
}
bool any(Bool3 stValue)
{
	return stValue.x || stValue.y || stValue.z;
}
bool isfinite(float fValue)
{
	return std::isfinite(fValue);
}
Bool3 isfinite(Float3 stValue)
{
	return { std::isfinite(stValue.x), std::isfinite(stValue.y), std::isfinite(stValue.z) };
}
float abs(float fValue)
{
	return std::abs(fValue);
}
Float3 abs(Float3 stValue)
{
	return { std::abs(stValue.x), std::abs(stValue.y), std::abs(stValue.z) };
}
float min(float fLeft, float fRight)
{
	return (std::min)(fLeft, fRight);
}
float max(float fLeft, float fRight)
{
	return (std::max)(fLeft, fRight);
}
float saturate(float fValue)
{
	return std::clamp(fValue, 0.0f, 1.0f);
}
float exp(float fValue)
{
	return std::exp(fValue);
}
float log(float fValue)
{
	return std::log(fValue);
}
float sqrt(float fValue)
{
	return std::sqrt(fValue);
}
float dot(Float3 stLeft, Float3 stRight)
{
	return stLeft.x * stRight.x + stLeft.y * stRight.y + stLeft.z * stRight.z;
}
using uint = std::uint32_t;
using float3 = Float3;

#include "engine_next/Rendering/Shaders/VolumeMath.hlsli"

void Near(float fActual, double dExpected, double dTolerance = 1e-5)
{
	ENGINE_NEXT_CHECK(std::isfinite(fActual));
	ENGINE_NEXT_CHECK(std::abs(static_cast<double>(fActual) - dExpected) <= dTolerance * (1 + std::abs(dExpected)));
}

} // namespace

ENGINE_NEXT_TEST("Volume HG is normalized isotropic and respects forward scattering")
{
	float fValue = 0;
	ENGINE_NEXT_CHECK(VolumeHenyeyGreenstein(0, .3f, fValue));
	Near(fValue, 1 / (4 * 3.14159265358979323846));
	float fForward = 0;
	float fBackward = 0;
	ENGINE_NEXT_CHECK(VolumeHenyeyGreenstein(.8f, 1, fForward));
	ENGINE_NEXT_CHECK(VolumeHenyeyGreenstein(.8f, -1, fBackward));
	ENGINE_NEXT_CHECK(fForward > fBackward);
	float fNegative = 0;
	ENGINE_NEXT_CHECK(VolumeHenyeyGreenstein(-.8f, -1, fNegative));
	Near(fNegative, fForward);
	for (float fPhase : { -.95f, -.8f, 0.0f, .8f, .95f })
	{
		double dIntegral = 0;
		constexpr int SAMPLE_COUNT = 20000;
		for (int nIndex = 0; nIndex < SAMPLE_COUNT; ++nIndex)
		{
			const float fMu = -1 + (static_cast<float>(nIndex) + .5f) * (2.0f / SAMPLE_COUNT);
			ENGINE_NEXT_CHECK(VolumeHenyeyGreenstein(fPhase, fMu, fValue));
			dIntegral += fValue;
		}
		dIntegral *= 4 * 3.14159265358979323846 / SAMPLE_COUNT;
		ENGINE_NEXT_CHECK(std::abs(dIntegral - 1) < .001);
	}
}

ENGINE_NEXT_TEST("Volume HG invalid inputs leave the output unchanged")
{
	float fValue = 123;
	for (float fInvalid : { -1.0f, 1.0f, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK(!VolumeHenyeyGreenstein(fInvalid, 0, fValue));
		ENGINE_NEXT_CHECK_EQ(fValue, 123);
	}
	ENGINE_NEXT_CHECK(!VolumeHenyeyGreenstein(0, 1.01f, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 123);
}

ENGINE_NEXT_TEST("Volume integration follows analytic Beer Lambert including tiny depth")
{
	for (float fSigma : { 0.0f, 1e-8f, 1e-4f, .1f, 1.0f, 10.0f, 65504.0f })
	{
		for (float fDistance : { 0.0f, .001f, .1f, 1.0f, 100.0f })
		{
			VolumeIntegral stValue{};
			ENGINE_NEXT_CHECK(VolumeIntegrateSegment(2, fSigma, fDistance, stValue));
			const double dOpticalDepth = static_cast<double>(fSigma) * fDistance;
			const double dExpectedWeight = fSigma == 0 ? fDistance : -std::expm1(-dOpticalDepth) / fSigma;
			Near(stValue.Scatter, (std::min)(65504.0, 2 * dExpectedWeight), 2e-5);
			Near(stValue.Transmittance, std::exp(-dOpticalDepth));
		}
	}
}

ENGINE_NEXT_TEST("Volume segmented accumulation matches one homogeneous segment")
{
	VolumeIntegral stSegment{};
	VolumeIntegral stWhole{};
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(3, .2f, .25f, stSegment));
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(3, .2f, 4, stWhole));
	VolumeIntegral stTotal{ 0, 1 };
	for (int nIndex = 0; nIndex < 16; ++nIndex)
	{
		VolumeIntegral stNext{};
		ENGINE_NEXT_CHECK(VolumeAccumulate(stTotal, stSegment, stNext));
		stTotal = stNext;
	}
	Near(stTotal.Scatter, stWhole.Scatter);
	Near(stTotal.Transmittance, stWhole.Transmittance);
}

ENGINE_NEXT_TEST("Volume integration handles finite extreme inputs and explicit half saturation")
{
	VolumeIntegral stValue{};
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(65504, 0, std::numeric_limits<float>::max(), stValue));
	ENGINE_NEXT_CHECK_EQ(stValue.Scatter, 65504);
	ENGINE_NEXT_CHECK_EQ(stValue.Transmittance, 1);
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(0, 0, std::numeric_limits<float>::max(), stValue));
	ENGINE_NEXT_CHECK_EQ(stValue.Scatter, 0);
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(2, 65504, std::numeric_limits<float>::max(), stValue));
	Near(stValue.Scatter, 2.0 / 65504);
	ENGINE_NEXT_CHECK_EQ(stValue.Transmittance, 0);
	const float fMinimum = std::numeric_limits<float>::min();
	const float fMaximum = std::numeric_limits<float>::max();
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(fMinimum, 0, fMaximum, stValue));
	Near(stValue.Scatter, static_cast<double>(fMinimum) * fMaximum);
	VolumeIntegral stResult{};
	ENGINE_NEXT_CHECK(VolumeAccumulate({ 65504, 1 }, { 65504, 1 }, stResult));
	ENGINE_NEXT_CHECK_EQ(stResult.Scatter, 65504);
	ENGINE_NEXT_CHECK_EQ(stResult.Transmittance, 1);
}

ENGINE_NEXT_TEST("Volume invalid integration is transactional")
{
	VolumeIntegral stValue{ 123, .4f };
	for (float fInvalid : { -1.0f, 65505.0f, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN() })
	{
		ENGINE_NEXT_CHECK(!VolumeIntegrateSegment(fInvalid, 1, 1, stValue));
		ENGINE_NEXT_CHECK_EQ(stValue.Scatter, 123);
		ENGINE_NEXT_CHECK_EQ(stValue.Transmittance, .4f);
		ENGINE_NEXT_CHECK(!VolumeIntegrateSegment(1, fInvalid, 1, stValue));
	}
	ENGINE_NEXT_CHECK(!VolumeIntegrateSegment(1, 1, -1, stValue));
	ENGINE_NEXT_CHECK(!VolumeIntegrateSegment(std::numeric_limits<float>::denorm_min(), 0, 1, stValue));
	ENGINE_NEXT_CHECK(!VolumeIntegrateSegment(1, std::numeric_limits<float>::denorm_min(), 1, stValue));
	ENGINE_NEXT_CHECK(!VolumeAccumulate({ 0, 1.1f }, { 0, 1 }, stValue));
	ENGINE_NEXT_CHECK_EQ(stValue.Scatter, 123);
}

ENGINE_NEXT_TEST("Volume height density remains finite at extreme heights")
{
	float fValue = 0;
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, 0, 0, .1f, fValue));
	Near(fValue, .01);
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, 10, 0, .1f, fValue));
	Near(fValue, .01 * std::exp(-1.0));
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, 1000000064.0f, 1000000000.0f, .01f, fValue));
	Near(fValue, .01 * std::exp(-64.0 * static_cast<double>(.01f)));
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, 80, 0, 1, fValue));
	const double dSmallDensity = .01 * std::exp(-80.0);
	ENGINE_NEXT_CHECK(fValue >= std::numeric_limits<float>::min());
	ENGINE_NEXT_CHECK(std::abs(static_cast<double>(fValue) / dSmallDensity - 1) < .0001);
	ENGINE_NEXT_CHECK(VolumeHeightDensity(std::numeric_limits<float>::min(), 1, 0, 1, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 0);
	ENGINE_NEXT_CHECK(VolumeHeightDensity(0, -std::numeric_limits<float>::max(), std::numeric_limits<float>::max(), 65504, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 0);
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, -std::numeric_limits<float>::max(), std::numeric_limits<float>::max(), 65504, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 65504);
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, std::numeric_limits<float>::max(), -std::numeric_limits<float>::max(), 65504, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 0);
	const float fTinyFalloff = std::numeric_limits<float>::min();
	ENGINE_NEXT_CHECK(VolumeHeightDensity(.01f, std::numeric_limits<float>::max(), -std::numeric_limits<float>::max(), fTinyFalloff, fValue));
	Near(fValue, .01 * std::exp(-2.0 * static_cast<double>(std::numeric_limits<float>::max()) * fTinyFalloff));
	fValue = 123;
	ENGINE_NEXT_CHECK(!VolumeHeightDensity(-1, 0, 0, 1, fValue));
	ENGINE_NEXT_CHECK(!VolumeHeightDensity(.01f, 0, 0, std::numeric_limits<float>::denorm_min(), fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 123);
}

ENGINE_NEXT_TEST("Volume local box and sphere weights use bounded world coordinates")
{
	float fValue = 0;
	for (std::uint32_t nShape : { 0U, 1U })
	{
		ENGINE_NEXT_CHECK(VolumeLocalWeight(nShape, { -10, -5, -3 }, { -10, -5, -3 }, { 2, 2, 2 }, .25f, fValue));
		ENGINE_NEXT_CHECK_EQ(fValue, 1);
		ENGINE_NEXT_CHECK(VolumeLocalWeight(nShape, { -8.25f, -5, -3 }, { -10, -5, -3 }, { 2, 2, 2 }, .25f, fValue));
		Near(fValue, .5);
		ENGINE_NEXT_CHECK(VolumeLocalWeight(nShape, { -8, -5, -3 }, { -10, -5, -3 }, { 2, 2, 2 }, 0, fValue));
		ENGINE_NEXT_CHECK_EQ(fValue, 1);
		ENGINE_NEXT_CHECK(
				VolumeLocalWeight(nShape, { std::numeric_limits<float>::max(), 0, 0 }, { -std::numeric_limits<float>::max(), 0, 0 }, { 2, 2, 2 }, .25f, fValue));
		ENGINE_NEXT_CHECK_EQ(fValue, 0);
	}
	ENGINE_NEXT_CHECK(VolumeLocalWeight(0, { 1, 1, 1 }, { 0, 0, 0 }, { 1, 1, 1 }, 0, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 1);
	ENGINE_NEXT_CHECK(VolumeLocalWeight(1, { 1, 1, 1 }, { 0, 0, 0 }, { 1, 1, 1 }, 0, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 0);
	fValue = 123;
	ENGINE_NEXT_CHECK(!VolumeLocalWeight(3, { 0, 0, 0 }, { 0, 0, 0 }, { 1, 1, 1 }, 0, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 123);
	ENGINE_NEXT_CHECK(!VolumeLocalWeight(1, { 0, 0, 0 }, { 0, 0, 0 }, { 1, 2, 1 }, 0, fValue));
}

ENGINE_NEXT_TEST("Volume logarithmic slice mapping round trips across camera ranges")
{
	for (const std::array<float, 2> &arrDepthRange : { std::array<float, 2>{ .001f, 1e7f }, { .05f, 100 }, { 100, 100.01f } })
	{
		for (std::uint32_t nSlices : { 32U, 64U, 96U, 128U })
		{
			for (std::uint32_t nSlice = 0; nSlice <= nSlices; ++nSlice)
			{
				float fDepth = 0;
				float fSlice = 0;
				ENGINE_NEXT_CHECK(VolumeDepthAtSlice(arrDepthRange[0], arrDepthRange[1], nSlices, static_cast<float>(nSlice), fDepth));
				ENGINE_NEXT_CHECK(VolumeSliceAtDepth(arrDepthRange[0], arrDepthRange[1], nSlices, fDepth, fSlice));
				// One binary32 depth step bounds inverse-map uncertainty when
				// the camera clipping range is narrow.
				const double dDepthStep = std::nextafter(fDepth, std::numeric_limits<float>::infinity()) - fDepth;
				const double dSliceError = dDepthStep * nSlices / (static_cast<double>(fDepth) * std::log(static_cast<double>(arrDepthRange[1]) / arrDepthRange[0]));
				ENGINE_NEXT_CHECK(std::abs(static_cast<double>(fSlice) - nSlice) <= dSliceError + .001);
			}
		}
	}
	float fValue = 0;
	ENGINE_NEXT_CHECK(VolumeSliceAtDepth(.05f, 100, 64, 0, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 0);
	ENGINE_NEXT_CHECK(VolumeSliceAtDepth(.05f, 100, 64, 1000, fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 64);
}

ENGINE_NEXT_TEST("Volume invalid depth mappings preserve output")
{
	float fValue = 123;
	ENGINE_NEXT_CHECK(!VolumeDepthAtSlice(1, 1, 64, 1, fValue));
	ENGINE_NEXT_CHECK(!VolumeDepthAtSlice(1, 100, 0, 1, fValue));
	ENGINE_NEXT_CHECK(!VolumeDepthAtSlice(1, 100, 64, 65, fValue));
	ENGINE_NEXT_CHECK(!VolumeSliceAtDepth(1, 100, 64, -1, fValue));
	ENGINE_NEXT_CHECK(!VolumeSliceAtDepth(1, 100, 64, std::numeric_limits<float>::quiet_NaN(), fValue));
	ENGINE_NEXT_CHECK_EQ(fValue, 123);
}

ENGINE_NEXT_TEST("Volume accepted close grids retain distinct GPU depth boundaries")
{
	EngineNext::Rendering::CameraSettings stCamera;
	stCamera.dNearPlane = 100;
	stCamera.dFarPlane = 1000;
	EngineNext::Rendering::VolumeSettings stSettings;
	stSettings.nDepthSlices = 128;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	for (double dDistance : { 100.001, 100.002, 100.01, 100.1, 101.0, 1000.0 })
	{
		stSettings.dDistance = dDistance;
		EngineNext::Rendering::VolumeGrid stGrid;
		if (!EngineNext::Rendering::BuildVolumeGrid(stCamera, 16, 16, stSettings, stGrid, arrDiagnostics))
		{
			continue;
		}
		float fPrevious = static_cast<float>(stGrid.dNear);
		for (std::uint32_t nSlice = 1; nSlice <= stGrid.nDepth; ++nSlice)
		{
			float fDepth = 0;
			ENGINE_NEXT_CHECK(
					VolumeDepthAtSlice(static_cast<float>(stGrid.dNear), static_cast<float>(stGrid.dFar), stGrid.nDepth, static_cast<float>(nSlice), fDepth));
			ENGINE_NEXT_CHECK(fDepth > fPrevious);
			fPrevious = fDepth;
		}
	}
}

ENGINE_NEXT_TEST("Volume partial segment uses oblique ray length and camera near interval")
{
	Near(VolumePartialSegmentLength(.05f, 0, .1f, 2), .1);
	Near(VolumePartialSegmentLength(0, 0, .1f, 2), 0);
	Near(VolumePartialSegmentLength(.4f, 1, 2, 3), 0);
	Near(VolumePartialSegmentLength(4, 1, 2, 3), 3);
	Near(VolumePartialSegmentLength(1.5f, 1, 2, 3), 1.5);
	Near(VolumePartialSegmentLength(-1, 0, 1, 1), 0);
	Near(VolumePartialSegmentLength(1, 2, 1, 1), 0);
	Near(VolumePartialSegmentLength(1, 0, 1, std::numeric_limits<float>::quiet_NaN()), 0);
}

ENGINE_NEXT_TEST("Volume partial integrals meet continuously at layer boundaries")
{
	const float fRayScale = 1.7f;
	VolumeIntegral stWhole{};
	ENGINE_NEXT_CHECK(VolumeIntegrateSegment(2, .4f, fRayScale * 2, stWhole));
	for (float fDepth : { 1.9999f, 2.0f, 2.0001f })
	{
		VolumeIntegral stBefore{};
		VolumeIntegral stPartial{};
		VolumeIntegral stTotal{};
		ENGINE_NEXT_CHECK(VolumeIntegrateSegment(2, .4f, VolumePartialSegmentLength(fDepth, 0, 2, fRayScale), stBefore));
		ENGINE_NEXT_CHECK(VolumeIntegrateSegment(2, .4f, VolumePartialSegmentLength(fDepth, 2, 4, fRayScale), stPartial));
		ENGINE_NEXT_CHECK(VolumeAccumulate(stBefore, stPartial, stTotal));
		const double dLength = static_cast<double>(fDepth) * fRayScale;
		Near(stTotal.Transmittance, std::exp(-.4 * dLength), 1e-4);
		Near(stTotal.Scatter, 2 * -std::expm1(-.4 * dLength) / .4, 1e-4);
		if (fDepth == 2)
		{
			Near(stTotal.Scatter, stWhole.Scatter);
			Near(stTotal.Transmittance, stWhole.Transmittance);
		}
	}
}

ENGINE_NEXT_TEST("Volume four column composition integrates before nonlinear interpolation")
{
	const float arrExtinction[] = { 0, .5f, 1, 2 };
	const float arrRayScale[] = { 1, 1.25f, 1.5f, 2 };
	const float arrWeight[] = { .12f, .28f, .18f, .42f };
	double dTransmittance = 0;
	double dExpected = 0;
	double dAveragedOpticalDepth = 0;
	for (int nColumn = 0; nColumn < 4; ++nColumn)
	{
		const float fLength = VolumePartialSegmentLength(.75f, 0, 1, arrRayScale[nColumn]);
		VolumeIntegral stValue{};
		ENGINE_NEXT_CHECK(VolumeIntegrateSegment(1, arrExtinction[nColumn], fLength, stValue));
		dTransmittance += arrWeight[nColumn] * stValue.Transmittance;
		dExpected += arrWeight[nColumn] * std::exp(-static_cast<double>(arrExtinction[nColumn]) * fLength);
		dAveragedOpticalDepth += arrWeight[nColumn] * arrExtinction[nColumn] * fLength;
	}
	ENGINE_NEXT_CHECK(std::abs(dTransmittance - dExpected) < 1e-6);
	ENGINE_NEXT_CHECK(std::abs(dTransmittance - std::exp(-dAveragedOpticalDepth)) > .05);
}
