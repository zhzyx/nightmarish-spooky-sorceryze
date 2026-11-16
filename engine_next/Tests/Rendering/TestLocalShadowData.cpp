/**************************************************************************/
/*  TestLocalShadowData.cpp                                               */
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
#include "engine_next/include/EngineNext/Rendering/LocalShadowData.h"
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{

using EngineNext::Rendering::LocalShadowData;
using EngineNext::Rendering::LocalShadowView;
using EngineNext::Rendering::PointLightSettings;
using EngineNext::Rendering::SpotLightSettings;
using Vector = std::array<double, 3>;

constexpr std::array<Vector, 6> FACE_DIRECTIONS{ {
		{ 1, 0, 0 },
		{ -1, 0, 0 },
		{ 0, 1, 0 },
		{ 0, -1, 0 },
		{ 0, 0, 1 },
		{ 0, 0, -1 },
} };
constexpr std::array<Vector, 6> FACE_UP{ {
		{ 0, 1, 0 },
		{ 0, 1, 0 },
		{ 0, 0, -1 },
		{ 0, 0, 1 },
		{ 0, 1, 0 },
		{ 0, 1, 0 },
} };

Vector Cross(const Vector &arrLeft, const Vector &arrRight)
{
	return { arrLeft[1] * arrRight[2] - arrLeft[2] * arrRight[1], arrLeft[2] * arrRight[0] - arrLeft[0] * arrRight[2], arrLeft[0] * arrRight[1] - arrLeft[1] * arrRight[0] };
}

Vector Project(const LocalShadowView &stView, const Vector &arrPosition)
{
	std::array<double, 4> arrClip{};
	for (std::size_t nRow = 0; nRow < 4; ++nRow)
	{
		arrClip[nRow] = stView.arrViewProjection[12 + nRow];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrClip[nRow] += stView.arrViewProjection[nAxis * 4 + nRow] * arrPosition[nAxis];
		}
	}
	return { arrClip[0] / arrClip[3], arrClip[1] / arrClip[3], arrClip[2] / arrClip[3] };
}

Vector Position(const Vector &arrOrigin, const Vector &arrDirection, double dDepth, const Vector &arrOffset = { 0, 0, 0 })
{
	return { arrOrigin[0] + arrDirection[0] * dDepth + arrOffset[0], arrOrigin[1] + arrDirection[1] * dDepth + arrOffset[1], arrOrigin[2] + arrDirection[2] * dDepth + arrOffset[2] };
}

void CheckNear(double dActual, double dExpected, double dTolerance = 1.0e-10)
{
	ENGINE_NEXT_CHECK(std::isfinite(dActual));
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) <= dTolerance * (std::max)(1.0, std::abs(dExpected)));
}

bool Build(const std::vector<PointLightSettings> &arrPoints, const std::vector<SpotLightSettings> &arrSpots, LocalShadowData &out_stData)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return EngineNext::Rendering::BuildLocalShadows(arrPoints, arrSpots, out_stData, arrDiagnostics);
}

void CheckFailure(const std::vector<PointLightSettings> &arrPoints, const std::vector<SpotLightSettings> &arrSpots)
{
	LocalShadowData stData;
	LocalShadowView stSentinel;
	stSentinel.arrViewProjection.fill(42.0);
	stSentinel.nLightId = 9;
	stSentinel.nFace = 5;
	stData.arrViews.push_back(stSentinel);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildLocalShadows(arrPoints, arrSpots, stData, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stData.arrViews.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stData.arrViews[0].arrViewProjection, stSentinel.arrViewProjection);
	ENGINE_NEXT_CHECK_EQ(stData.arrViews[0].nLightId, 9U);
	ENGINE_NEXT_CHECK_EQ(stData.arrViews[0].nFace, 5U);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

} // namespace

ENGINE_NEXT_TEST("Local point shadows produce ordered cube face centers and reverse depth")
{
	PointLightSettings stLight;
	stLight.arrPosition = { 4, -3, 2 };
	stLight.nId = 77;
	stLight.dRange = 20;
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build({ stLight }, {}, stData));
	ENGINE_NEXT_CHECK_EQ(stData.arrViews.size(), 6U);
	if (stData.arrViews.size() != 6)
	{
		return;
	}
	for (std::size_t nFace = 0; nFace < 6; ++nFace)
	{
		const LocalShadowView &stView = stData.arrViews[nFace];
		ENGINE_NEXT_CHECK_EQ(stView.nLightId, 77U);
		ENGINE_NEXT_CHECK_EQ(stView.nFace, nFace);
		const Vector arrCenter = Project(stView, Position(stLight.arrPosition, FACE_DIRECTIONS[nFace], 1));
		CheckNear(arrCenter[0], 0);
		CheckNear(arrCenter[1], 0);
		CheckNear(Project(stView, Position(stLight.arrPosition, FACE_DIRECTIONS[nFace], 0.05))[2], 1);
		CheckNear(Project(stView, Position(stLight.arrPosition, FACE_DIRECTIONS[nFace], stLight.dRange))[2], 0);
		ENGINE_NEXT_CHECK(Project(stView, Position(stLight.arrPosition, FACE_DIRECTIONS[nFace], 0.025))[2] > 1);
		ENGINE_NEXT_CHECK(Project(stView, Position(stLight.arrPosition, FACE_DIRECTIONS[nFace], stLight.dRange * 2))[2] < 0);
	}
}

ENGINE_NEXT_TEST("Local point cube edges and corners meet without face coverage gaps")
{
	PointLightSettings stLight;
	stLight.arrPosition = { 0, 0, 0 };
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build({ stLight }, {}, stData));
	if (stData.arrViews.size() != 6)
	{
		return;
	}
	for (std::size_t nFace = 0; nFace < 6; ++nFace)
	{
		const Vector arrRight = Cross(FACE_DIRECTIONS[nFace], FACE_UP[nFace]);
		for (double dHorizontal : { -1.0, 1.0 })
		{
			for (double dVertical : { -1.0, 1.0 })
			{
				const Vector arrCorner{ FACE_DIRECTIONS[nFace][0] + dHorizontal * arrRight[0] + dVertical * FACE_UP[nFace][0],
										FACE_DIRECTIONS[nFace][1] + dHorizontal * arrRight[1] + dVertical * FACE_UP[nFace][1],
										FACE_DIRECTIONS[nFace][2] + dHorizontal * arrRight[2] + dVertical * FACE_UP[nFace][2] };
				const Vector arrClip = Project(stData.arrViews[nFace], arrCorner);
				CheckNear(arrClip[0], dHorizontal);
				CheckNear(arrClip[1], dVertical);
				ENGINE_NEXT_CHECK(arrClip[2] >= 0 && arrClip[2] <= 1);
			}
		}
	}
}

ENGINE_NEXT_TEST("Local shadows preserve input slots and omit unshadowed lights")
{
	std::vector<PointLightSettings> arrPoints(4);
	std::vector<SpotLightSettings> arrSpots(4);
	for (std::size_t nIndex = 0; nIndex < 4; ++nIndex)
	{
		arrPoints[nIndex].nId = static_cast<std::uint32_t>(40 - nIndex);
		arrSpots[nIndex].nId = static_cast<std::uint32_t>(80 - nIndex);
	}
	arrPoints[1].bCastsShadow = false;
	arrSpots[2].bCastsShadow = false;
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build(arrPoints, arrSpots, stData));
	ENGINE_NEXT_CHECK_EQ(stData.arrViews.size(), 21U);
	const std::array<std::uint32_t, 6> arrExpected{ 40, 38, 37, 80, 79, 77 };
	std::size_t nView = 0;
	for (std::size_t nLight = 0; nLight < arrExpected.size(); ++nLight)
	{
		const std::size_t nFaces = nLight < 3 ? 6 : 1;
		for (std::size_t nFace = 0; nFace < nFaces; ++nFace)
		{
			ENGINE_NEXT_CHECK_EQ(stData.arrViews[nView].nLightId, arrExpected[nLight]);
			ENGINE_NEXT_CHECK_EQ(stData.arrViews[nView].nFace, nFace);
			++nView;
		}
	}
	LocalShadowData stRepeated;
	ENGINE_NEXT_CHECK(Build(arrPoints, arrSpots, stRepeated));
	for (std::size_t nIndex = 0; nIndex < stData.arrViews.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK_EQ(stData.arrViews[nIndex].arrViewProjection, stRepeated.arrViews[nIndex].arrViewProjection);
	}
	ENGINE_NEXT_CHECK(Build({}, {}, stData));
	ENGINE_NEXT_CHECK(stData.arrViews.empty());
}

ENGINE_NEXT_TEST("Local spot shadows aim along normalized rays and fit cone boundaries")
{
	SpotLightSettings stLight;
	stLight.arrPosition = { -4, 5, 2 };
	stLight.arrDirection = { 0, -8, 0 };
	stLight.nId = 9;
	stLight.dRange = 10;
	stLight.dInnerAngleDegrees = 10;
	stLight.dOuterAngleDegrees = 30;
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build({}, { stLight }, stData));
	ENGINE_NEXT_CHECK_EQ(stData.arrViews.size(), 1U);
	if (stData.arrViews.empty())
	{
		return;
	}
	const Vector arrDirection{ 0, -1, 0 };
	const Vector arrRight = Cross(arrDirection, { 1, 0, 0 });
	const double dEdge = std::tan(30 * 3.14159265358979323846 / 180);
	Vector arrOffset{ arrRight[0] * dEdge, arrRight[1] * dEdge, arrRight[2] * dEdge };
	const Vector arrClip = Project(stData.arrViews[0], Position(stLight.arrPosition, arrDirection, 1, arrOffset));
	CheckNear(arrClip[0], 1);
	CheckNear(arrClip[1], 0);
	CheckNear(Project(stData.arrViews[0], Position(stLight.arrPosition, arrDirection, 0.05))[2], 1);
	CheckNear(Project(stData.arrViews[0], Position(stLight.arrPosition, arrDirection, 10))[2], 0);
}

ENGINE_NEXT_TEST("Local spot shadows accept supported narrow and wide cones and minimum range")
{
	SpotLightSettings stLight;
	stLight.arrPosition = { 0, 0, 0 };
	stLight.arrDirection = { 0, 0, -std::numeric_limits<double>::max() };
	stLight.dRange = 0.1;
	stLight.dInnerAngleDegrees = 0;
	LocalShadowData stData;
	for (double dOuter : { 0.01, 89.0 })
	{
		stLight.dOuterAngleDegrees = dOuter;
		ENGINE_NEXT_CHECK(Build({}, { stLight }, stData));
		const double dEdge = std::tan(dOuter * 3.14159265358979323846 / 180.0);
		CheckNear(Project(stData.arrViews[0], { dEdge * 0.01, 0, -0.01 })[0], 1);
		CheckNear(Project(stData.arrViews[0], { 0, 0, -0.001 })[2], 1);
		CheckNear(Project(stData.arrViews[0], { 0, 0, -0.1 })[2], 0);
	}
	stLight.arrDirection = { 0, 0, -std::numeric_limits<double>::denorm_min() };
	ENGINE_NEXT_CHECK(Build({}, { stLight }, stData));
}

ENGINE_NEXT_TEST("Local spot oblique views preserve a complete orthonormal cone basis")
{
	SpotLightSettings stLight;
	stLight.arrPosition = { -7, 4, 3 };
	stLight.arrDirection = { 2, -3, -6 };
	stLight.dRange = 10000;
	const Vector arrDirection{ 2.0 / 7.0, -3.0 / 7.0, -6.0 / 7.0 };
	Vector arrRight = Cross(arrDirection, { 0, 1, 0 });
	const double dRightLength = std::sqrt(arrRight[0] * arrRight[0] + arrRight[1] * arrRight[1] + arrRight[2] * arrRight[2]);
	for (double &dValue : arrRight)
	{
		dValue /= dRightLength;
	}
	const Vector arrUp = Cross(arrRight, arrDirection);
	const double dEdge = std::tan(stLight.dOuterAngleDegrees * 3.14159265358979323846 / 180.0);
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build({}, { stLight }, stData));
	if (stData.arrViews.size() != 1)
	{
		return;
	}
	const LocalShadowView &stView = stData.arrViews[0];
	for (double dHorizontal : { -1.0, 1.0 })
	{
		for (double dVertical : { -1.0, 1.0 })
		{
			Vector arrOffset{};
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				arrOffset[nAxis] = 10 * dEdge * (dHorizontal * arrRight[nAxis] + dVertical * arrUp[nAxis]);
			}
			const Vector arrProjected = Project(stView, Position(stLight.arrPosition, arrDirection, 10, arrOffset));
			CheckNear(arrProjected[0], dHorizontal);
			CheckNear(arrProjected[1], dVertical);
		}
	}
	CheckNear(Project(stView, Position(stLight.arrPosition, arrDirection, 0.05))[2], 1);
	CheckNear(Project(stView, Position(stLight.arrPosition, arrDirection, 10000))[2], 0);
}

ENGINE_NEXT_TEST("Local shadows fill all 28 bounded view slots and preserve prior output on a late failure")
{
	std::vector<PointLightSettings> arrPoints(4);
	std::vector<SpotLightSettings> arrSpots(4);
	for (std::size_t nIndex = 0; nIndex < 4; ++nIndex)
	{
		arrPoints[nIndex].nId = static_cast<std::uint32_t>(nIndex + 1);
		arrSpots[nIndex].nId = static_cast<std::uint32_t>(nIndex + 5);
	}
	arrSpots[3].nId = std::numeric_limits<std::uint32_t>::max();
	LocalShadowData stData;
	ENGINE_NEXT_CHECK(Build(arrPoints, arrSpots, stData));
	ENGINE_NEXT_CHECK_EQ(stData.arrViews.size(), 28U);
	if (stData.arrViews.size() == 28)
	{
		ENGINE_NEXT_CHECK_EQ(stData.arrViews[27].nLightId, std::numeric_limits<std::uint32_t>::max());
		ENGINE_NEXT_CHECK_EQ(stData.arrViews[27].nFace, 0U);
	}
	arrSpots[3].arrDirection = { 0, 0, 0 };
	CheckFailure(arrPoints, arrSpots);
}

ENGINE_NEXT_TEST("Local shadow validation rejects duplicate IDs and malformed bounded inputs transactionally")
{
	PointLightSettings stPoint;
	SpotLightSettings stSpot;
	stSpot.nId = 2;
	PointLightSettings stInvalid = stPoint;
	stInvalid.nId = 0;
	CheckFailure({ stInvalid }, {});
	CheckFailure({ stPoint, stPoint }, {});
	stSpot.nId = stPoint.nId;
	CheckFailure({ stPoint }, { stSpot });
	CheckFailure(std::vector<PointLightSettings>(5), {});
	CheckFailure({}, std::vector<SpotLightSettings>(5));
	stInvalid = stPoint;
	stInvalid.arrPosition[0] = std::numeric_limits<double>::infinity();
	CheckFailure({ stInvalid }, {});
	stInvalid.arrPosition[0] = std::numeric_limits<double>::max();
	CheckFailure({ stInvalid }, {});
	stInvalid = stPoint;
	stInvalid.arrColor[1] = -0.01;
	CheckFailure({ stInvalid }, {});
	stInvalid = stPoint;
	stInvalid.dLumens = 1.0e8 + 1;
	CheckFailure({ stInvalid }, {});
	for (double dRange : { 0.01, 10001.0, std::numeric_limits<double>::quiet_NaN() })
	{
		stInvalid = stPoint;
		stInvalid.dRange = dRange;
		CheckFailure({ stInvalid }, {});
	}
	stSpot = SpotLightSettings{};
	stSpot.arrDirection = { 0, 0, 0 };
	CheckFailure({}, { stSpot });
	stSpot.arrDirection = { 0, std::numeric_limits<double>::quiet_NaN(), 0 };
	CheckFailure({}, { stSpot });
	stSpot = SpotLightSettings{};
	stSpot.dOuterAngleDegrees = stSpot.dInnerAngleDegrees;
	CheckFailure({}, { stSpot });
	stSpot.dOuterAngleDegrees = 89.01;
	CheckFailure({}, { stSpot });
	stSpot = SpotLightSettings{};
	stSpot.dInnerAngleDegrees = -1;
	CheckFailure({}, { stSpot });
	stSpot.bCastsShadow = false;
	CheckFailure({}, { stSpot });
	stSpot.dInnerAngleDegrees = 0;
	stSpot.dOuterAngleDegrees = std::numeric_limits<double>::denorm_min();
	stSpot.bCastsShadow = true;
	CheckFailure({}, { stSpot });
}
