/**************************************************************************/
/*  TestCameraMatrices.cpp                                                */
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
#include "engine_next/include/EngineNext/Rendering/CameraMatrices.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace
{

using EngineNext::Rendering::CameraMatrices;
using EngineNext::Rendering::CameraSettings;
using Matrix = std::array<double, 16>;
using Point = std::array<double, 4>;

Point Transform(const Matrix &arrMatrix, const Point &arrPoint)
{
	Point arrResult{};
	for (std::size_t nRow = 0; nRow < 4; ++nRow)
	{
		for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
		{
			arrResult[nRow] += arrMatrix[nColumn * 4 + nRow] * arrPoint[nColumn];
		}
	}
	return arrResult;
}

void CheckNear(double dActual, double dExpected, double dTolerance = 1.0e-11)
{
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) <= dTolerance * (std::max)(1.0, std::abs(dExpected)));
}

void CheckInverse(const CameraMatrices &stMatrices)
{
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			double dValue = 0;
			double dOther = 0;
			for (std::size_t nInner = 0; nInner < 4; ++nInner)
			{
				dValue += stMatrices.arrViewProjection[nInner * 4 + nRow] * stMatrices.arrInverseViewProjection[nColumn * 4 + nInner];
				dOther += stMatrices.arrInverseViewProjection[nInner * 4 + nRow] * stMatrices.arrViewProjection[nColumn * 4 + nInner];
			}
			CheckNear(dValue, nColumn == nRow ? 1.0 : 0.0);
			CheckNear(dOther, nColumn == nRow ? 1.0 : 0.0);
		}
	}
}

bool Build(const CameraSettings &stSettings, CameraMatrices &out_stMatrices, const std::array<double, 2> &arrJitter = { 0, 0 })
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::BuildCameraMatrices(stSettings, 1920, 1080, arrJitter, out_stMatrices, arrDiagnostics);
}

void CheckFailure(const CameraSettings &stSettings, std::uint32_t nWidth = 1920, std::uint32_t nHeight = 1080, const std::array<double, 2> &arrJitter = { 0, 0 })
{
	CameraMatrices stMatrices;
	stMatrices.arrView.fill(17);
	stMatrices.arrProjection.fill(18);
	stMatrices.arrViewProjection.fill(19);
	stMatrices.arrInverseViewProjection.fill(20);
	const CameraMatrices stOriginal = stMatrices;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildCameraMatrices(stSettings, nWidth, nHeight, arrJitter, stMatrices, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stMatrices.arrView, stOriginal.arrView);
	ENGINE_NEXT_CHECK_EQ(stMatrices.arrProjection, stOriginal.arrProjection);
	ENGINE_NEXT_CHECK_EQ(stMatrices.arrViewProjection, stOriginal.arrViewProjection);
	ENGINE_NEXT_CHECK_EQ(stMatrices.arrInverseViewProjection, stOriginal.arrInverseViewProjection);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

} // namespace

ENGINE_NEXT_TEST("Camera matrices map finite near to one and far to zero in right handed space")
{
	CameraSettings stSettings;
	stSettings.arrPosition = { 0, 0, 0 };
	stSettings.arrTarget = { 0, 0, -1 };
	stSettings.dNearPlane = 0.25;
	stSettings.dFarPlane = 100;
	stSettings.dVerticalFovDegrees = 90;
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
	const Point arrNear = Transform(stMatrices.arrViewProjection, { 0, 0, -0.25, 1 });
	const Point arrFar = Transform(stMatrices.arrViewProjection, { 0, 0, -100, 1 });
	CheckNear(arrNear[2] / arrNear[3], 1.0);
	CheckNear(arrFar[2] / arrFar[3], 0.0);
	ENGINE_NEXT_CHECK(arrNear[3] > 0);
	ENGINE_NEXT_CHECK(arrFar[3] > 0);
	const Point arrUp = Transform(stMatrices.arrViewProjection, { 0, 1, -1, 1 });
	const Point arrRight = Transform(stMatrices.arrViewProjection, { 16.0 / 9.0, 0, -1, 1 });
	CheckNear(arrUp[1] / arrUp[3], 1.0);
	CheckNear(arrRight[0] / arrRight[3], 1.0);
	CheckInverse(stMatrices);
}

ENGINE_NEXT_TEST("Camera view applies translation and reorthogonalizes a rotated up axis")
{
	CameraSettings stSettings;
	stSettings.arrPosition = { 10, 4, -2 };
	stSettings.arrTarget = { 11, 4, -2 };
	stSettings.arrUp = { 1, 2, 0 };
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
	const Point arrOrigin = Transform(stMatrices.arrView, { 10, 4, -2, 1 });
	const Point arrTarget = Transform(stMatrices.arrView, { 11, 4, -2, 1 });
	const Point arrRight = Transform(stMatrices.arrView, { 10, 4, -1, 1 });
	const Point arrUp = Transform(stMatrices.arrView, { 10, 5, -2, 1 });
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		CheckNear(arrOrigin[nAxis], 0.0);
	}
	CheckNear(arrTarget[0], 0.0);
	CheckNear(arrTarget[1], 0.0);
	CheckNear(arrTarget[2], -1.0);
	CheckNear(arrRight[0], 1.0);
	CheckNear(arrUp[1], 1.0);
	CheckInverse(stMatrices);
}

ENGINE_NEXT_TEST("Camera pixel jitter moves raster positions right and down at any depth")
{
	const CameraSettings stSettings;
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices, { 0.75, -0.25 }));
	const Point arrPoint = Transform(stMatrices.arrViewProjection, { 0, 0, 0, 1 });
	const double dPixelX = (arrPoint[0] / arrPoint[3] + 1.0) * 1920.0 / 2.0;
	const double dPixelY = (1.0 - arrPoint[1] / arrPoint[3]) * 1080.0 / 2.0;
	CheckNear(dPixelX, 960.75);
	CheckNear(dPixelY, 539.75);
	const Point arrDistant = Transform(stMatrices.arrViewProjection, { 0, 0, -100, 1 });
	CheckNear(arrDistant[0] / arrDistant[3], 2.0 * 0.75 / 1920.0);
	CheckNear(arrDistant[1] / arrDistant[3], 2.0 * 0.25 / 1080.0);
	CheckInverse(stMatrices);
}

ENGINE_NEXT_TEST("Camera inverse reconstructs rotated translated positions from jittered NDC")
{
	CameraSettings stSettings;
	stSettings.arrPosition = { 5, -3, 7 };
	stSettings.arrTarget = { -2, 2, 0 };
	stSettings.arrUp = { 0.2, 1, 0.3 };
	stSettings.dNearPlane = 0.001;
	stSettings.dFarPlane = 1.0e7;
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices, { -0.5, 0.5 }));
	for (const Point &arrPoint : { Point{ -2, 2, 0, 1 }, Point{ 3, 0, -4, 1 }, Point{ -5, 1, 8, 1 } })
	{
		Point arrClip = Transform(stMatrices.arrViewProjection, arrPoint);
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrClip[nAxis] /= arrClip[3];
		}
		arrClip[3] = 1;
		const Point arrReconstructed = Transform(stMatrices.arrInverseViewProjection, arrClip);
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			CheckNear(arrReconstructed[nAxis] / arrReconstructed[3], arrPoint[nAxis]);
		}
	}
	CheckInverse(stMatrices);
}

ENGINE_NEXT_TEST("Camera construction validates clip ranges axes viewport and finite jitter transactionally")
{
	const CameraSettings stValid;
	CameraSettings stInvalid = stValid;
	stInvalid.arrTarget = stInvalid.arrPosition;
	CheckFailure(stInvalid);
	stInvalid = stValid;
	stInvalid.arrUp = { 0, 0, -1 };
	CheckFailure(stInvalid);
	stInvalid.arrUp = { 0, 0, 0 };
	CheckFailure(stInvalid);
	stInvalid.arrUp = { 0, 1.0e-13, -1 };
	CheckFailure(stInvalid);
	for (double dFov : { 0.0, 0.5, 170.01, 180.0, std::numeric_limits<double>::quiet_NaN() })
	{
		stInvalid = stValid;
		stInvalid.dVerticalFovDegrees = dFov;
		CheckFailure(stInvalid);
	}
	for (double dNear : { 0.0, 0.0001, 100.1, std::numeric_limits<double>::infinity() })
	{
		stInvalid = stValid;
		stInvalid.dNearPlane = dNear;
		CheckFailure(stInvalid);
	}
	for (double dFar : { 0.0, 0.05, 10000001.0, std::numeric_limits<double>::infinity() })
	{
		stInvalid = stValid;
		stInvalid.dFarPlane = dFar;
		CheckFailure(stInvalid);
	}
	stInvalid = stValid;
	stInvalid.arrPosition[1] = std::numeric_limits<double>::quiet_NaN();
	CheckFailure(stInvalid);
	stInvalid = stValid;
	stInvalid.arrTarget[0] = std::numeric_limits<double>::infinity();
	CheckFailure(stInvalid);
	stInvalid = stValid;
	stInvalid.arrUp[2] = -std::numeric_limits<double>::infinity();
	CheckFailure(stInvalid);
	CheckFailure(stValid, 0, 1080);
	CheckFailure(stValid, 1920, 0);
	CheckFailure(stValid, 1920, 1080, { std::numeric_limits<double>::infinity(), 0 });
	CheckFailure(stValid, 1920, 1080, { 0, std::numeric_limits<double>::quiet_NaN() });
}

ENGINE_NEXT_TEST("Camera normalization supports tiny and large axes while rejecting GPU matrix overflow")
{
	CameraSettings stSettings;
	stSettings.arrPosition = { 0, 0, 0 };
	stSettings.arrTarget = { 0, 0, -std::numeric_limits<double>::denorm_min() };
	stSettings.arrUp = { 0, std::numeric_limits<double>::max(), 0 };
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
	CheckInverse(stMatrices);
	stSettings.arrTarget = { std::numeric_limits<double>::max(), 0, -std::numeric_limits<double>::max() };
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
	CheckInverse(stMatrices);
	stSettings.arrPosition = { 0, 0, std::numeric_limits<double>::max() };
	stSettings.arrTarget = { 0, 0, -std::numeric_limits<double>::max() };
	CheckFailure(stSettings);
	CheckFailure(CameraSettings{}, 1, 1, { std::numeric_limits<double>::max(), 0 });
	stSettings = CameraSettings{};
	stSettings.arrPosition = { 0, 0, static_cast<double>(std::numeric_limits<float>::max()) };
	stSettings.arrTarget = { 0, 0, 0 };
	CheckFailure(stSettings);
}

ENGINE_NEXT_TEST("Camera projection honors endpoint ranges and rejects binary32 coincident planes")
{
	CameraSettings stSettings;
	stSettings.arrPosition = { 0, 0, 0 };
	stSettings.arrTarget = { 0, 0, -1 };
	stSettings.dNearPlane = 100;
	stSettings.dFarPlane = 10000000;
	for (double dFov : { 1.0, 170.0 })
	{
		stSettings.dVerticalFovDegrees = dFov;
		CameraMatrices stMatrices;
		ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
		const Point arrNear = Transform(stMatrices.arrProjection, { 0, 0, -stSettings.dNearPlane, 1 });
		const Point arrFar = Transform(stMatrices.arrProjection, { 0, 0, -stSettings.dFarPlane, 1 });
		CheckNear(arrNear[2] / arrNear[3], 1.0);
		CheckNear(arrFar[2] / arrFar[3], 0.0);
		CheckInverse(stMatrices);
	}
	stSettings.dFarPlane = std::nextafter(100.0, 101.0);
	CheckFailure(stSettings);
	stSettings.dFarPlane = static_cast<double>(std::nextafter(100.0F, 101.0F));
	CameraMatrices stMatrices;
	ENGINE_NEXT_CHECK(Build(stSettings, stMatrices));
}

ENGINE_NEXT_TEST("Camera matrices produce deterministic jittered output for rectangular viewports")
{
	const CameraSettings stSettings;
	CameraMatrices stFirst;
	CameraMatrices stSecond;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildCameraMatrices(stSettings, 1080, 1920, { -0.25, 0.75 }, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildCameraMatrices(stSettings, 1080, 1920, { -0.25, 0.75 }, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFirst.arrView, stSecond.arrView);
	ENGINE_NEXT_CHECK_EQ(stFirst.arrProjection, stSecond.arrProjection);
	ENGINE_NEXT_CHECK_EQ(stFirst.arrViewProjection, stSecond.arrViewProjection);
	ENGINE_NEXT_CHECK_EQ(stFirst.arrInverseViewProjection, stSecond.arrInverseViewProjection);
	const Point arrPoint = Transform(stFirst.arrViewProjection, { 0, 0, 0, 1 });
	CheckNear((arrPoint[0] / arrPoint[3] + 1.0) * 1080.0 / 2.0, 539.75);
	CheckNear((1.0 - arrPoint[1] / arrPoint[3]) * 1920.0 / 2.0, 960.75);
	CheckNear(stFirst.arrProjection[5] / stFirst.arrProjection[0], 1080.0 / 1920.0);
	CheckInverse(stFirst);
}
