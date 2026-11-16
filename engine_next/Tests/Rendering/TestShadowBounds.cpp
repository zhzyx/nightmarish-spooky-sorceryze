/**************************************************************************/
/*  TestShadowBounds.cpp                                                  */
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

#include "engine_next/Rendering/ShadowBounds.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <limits>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::MeshPrimitive;
using EngineNext::Rendering::MeshVertex;
using EngineNext::Rendering::TransformShadowBounds;
using EngineNext::Rendering::WorldBounds;

constexpr std::array<double, 16> IDENTITY{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };

MeshPrimitive MakePrimitive()
{
	MeshPrimitive stPrimitive;
	MeshVertex stFirst;
	stFirst.arrPosition = { -1.0F, -2.0F, -3.0F };
	MeshVertex stSecond;
	stSecond.arrPosition = { 4.0F, 5.0F, 6.0F };
	stPrimitive.arrVertices = { stFirst, stSecond };
	return stPrimitive;
}

void CheckEncloses(const WorldBounds &stBounds, const std::array<double, 3> &arrPoint)
{
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		ENGINE_NEXT_CHECK(stBounds.arrMinimum[nAxis] <= arrPoint[nAxis]);
		ENGINE_NEXT_CHECK(stBounds.arrMaximum[nAxis] >= arrPoint[nAxis]);
	}
}

void CheckNear(const std::array<double, 3> &arrActual, const std::array<double, 3> &arrExpected)
{
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		ENGINE_NEXT_CHECK(std::abs(arrActual[nAxis] - arrExpected[nAxis]) < 1.0e-12);
	}
}

} // namespace

ENGINE_NEXT_TEST("ShadowBounds transforms all vertex bounds with negative scale and translation")
{
	const MeshPrimitive stPrimitive = MakePrimitive();
	Diagnostics arrDiagnostics;
	WorldBounds stBounds;
	std::array<double, 16> arrWorld = IDENTITY;
	arrWorld[0] = -2.0;
	arrWorld[5] = 3.0;
	arrWorld[10] = 0.5;
	arrWorld[12] = 10.0;
	arrWorld[13] = -7.0;
	arrWorld[14] = 4.0;
	ENGINE_NEXT_CHECK(TransformShadowBounds(stPrimitive, arrWorld, stBounds, arrDiagnostics));
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
	CheckNear(stBounds.arrMinimum, { 2.0, -13.0, 2.5 });
	CheckNear(stBounds.arrMaximum, { 12.0, 8.0, 7.0 });
	CheckEncloses(stBounds, { 2.0, -13.0, 2.5 });
	CheckEncloses(stBounds, { 12.0, 8.0, 7.0 });
}

ENGINE_NEXT_TEST("ShadowBounds uses all AABB corners under shear and rotation")
{
	const MeshPrimitive stPrimitive = MakePrimitive();
	const std::array<double, 16> arrWorld{ 0, 1, 0, 0, -1, 0, 0, 0, 2, -0.5, 1, 0, 3, 8, -2, 1 };
	Diagnostics arrDiagnostics;
	WorldBounds stBounds;
	ENGINE_NEXT_CHECK(TransformShadowBounds(stPrimitive, arrWorld, stBounds, arrDiagnostics));
	CheckNear(stBounds.arrMinimum, { -8.0, 4.0, -5.0 });
	CheckNear(stBounds.arrMaximum, { 17.0, 13.5, 4.0 });
	for (std::size_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		const double dX = (nCorner & 1U) == 0 ? -1.0 : 4.0;
		const double dY = (nCorner & 2U) == 0 ? -2.0 : 5.0;
		const double dZ = (nCorner & 4U) == 0 ? -3.0 : 6.0;
		CheckEncloses(stBounds, { -dY + 2 * dZ + 3, dX - 0.5 * dZ + 8, dZ - 2 });
	}
}

ENGINE_NEXT_TEST("ShadowBounds accepts singular transforms and one-vertex geometry")
{
	MeshPrimitive stPrimitive;
	stPrimitive.arrVertices.push_back(MeshVertex{});
	stPrimitive.arrVertices[0].arrPosition = { 1.0F, 2.0F, 3.0F };
	std::array<double, 16> arrWorld{};
	arrWorld[12] = 7.0;
	arrWorld[13] = 8.0;
	arrWorld[14] = 9.0;
	arrWorld[15] = 1.0;
	Diagnostics arrDiagnostics;
	WorldBounds stBounds;
	ENGINE_NEXT_CHECK(TransformShadowBounds(stPrimitive, arrWorld, stBounds, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMinimum, (std::array<double, 3>{ 7.0, 8.0, 9.0 }));
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMaximum, stBounds.arrMinimum);
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("ShadowBounds rejects invalid inputs without replacing prior output")
{
	const WorldBounds stSentinel{ { -7.0, -8.0, -9.0 }, { 7.0, 8.0, 9.0 } };
	WorldBounds stBounds = stSentinel;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!TransformShadowBounds(MeshPrimitive{}, IDENTITY, stBounds, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMinimum, stSentinel.arrMinimum);
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMaximum, stSentinel.arrMaximum);
	for (std::size_t nIndex : { 3U, 7U, 11U, 15U })
	{
		std::array<double, 16> arrWorld = IDENTITY;
		arrWorld[nIndex] += 0.01;
		ENGINE_NEXT_CHECK(!TransformShadowBounds(MakePrimitive(), arrWorld, stBounds, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stBounds.arrMinimum, stSentinel.arrMinimum);
	}
	std::array<double, 16> arrWorld = IDENTITY;
	arrWorld[0] = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!TransformShadowBounds(MakePrimitive(), arrWorld, stBounds, arrDiagnostics));
	arrWorld[0] = std::numeric_limits<double>::infinity();
	ENGINE_NEXT_CHECK(!TransformShadowBounds(MakePrimitive(), arrWorld, stBounds, arrDiagnostics));
	arrWorld[0] = std::numeric_limits<double>::max();
	ENGINE_NEXT_CHECK(!TransformShadowBounds(MakePrimitive(), arrWorld, stBounds, arrDiagnostics));
	MeshPrimitive stPrimitive = MakePrimitive();
	stPrimitive.arrVertices[1].arrPosition[2] = std::numeric_limits<float>::infinity();
	ENGINE_NEXT_CHECK(!TransformShadowBounds(stPrimitive, IDENTITY, stBounds, arrDiagnostics));
	stPrimitive.arrVertices[1].arrPosition[2] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(!TransformShadowBounds(stPrimitive, IDENTITY, stBounds, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMinimum, stSentinel.arrMinimum);
	ENGINE_NEXT_CHECK_EQ(stBounds.arrMaximum, stSentinel.arrMaximum);
}

ENGINE_NEXT_TEST("ShadowBounds conservatively encloses tiny and mixed affine coordinates")
{
	const MeshPrimitive stPrimitive = MakePrimitive();
	Diagnostics arrDiagnostics;
	WorldBounds stBounds;
	for (std::size_t nSample = 0; nSample < 64; ++nSample)
	{
		std::array<double, 16> arrWorld = IDENTITY;
		const double dScale = static_cast<double>(nSample + 1) / 64.0;
		arrWorld[0] = 0.1 * dScale;
		arrWorld[1] = -0.2 * dScale;
		arrWorld[2] = 0.3 * dScale;
		arrWorld[4] = -0.4 * dScale;
		arrWorld[5] = 0.5 * dScale;
		arrWorld[6] = 0.6 * dScale;
		arrWorld[8] = 0.7 * dScale;
		arrWorld[9] = -0.8 * dScale;
		arrWorld[10] = 0.9 * dScale;
		arrWorld[12] = 1000.0 + dScale;
		ENGINE_NEXT_CHECK(TransformShadowBounds(stPrimitive, arrWorld, stBounds, arrDiagnostics));
		for (std::size_t nCorner = 0; nCorner < 8; ++nCorner)
		{
			const std::array<double, 3> arrPosition{ (nCorner & 1U) == 0 ? -1.0 : 4.0, (nCorner & 2U) == 0 ? -2.0 : 5.0, (nCorner & 4U) == 0 ? -3.0 : 6.0 };
			std::array<double, 3> arrPoint{};
			for (std::size_t nRow = 0; nRow < 3; ++nRow)
			{
				arrPoint[nRow] = arrWorld[12 + nRow];
				for (std::size_t nColumn = 0; nColumn < 3; ++nColumn)
				{
					arrPoint[nRow] = std::fma(arrWorld[nColumn * 4 + nRow], arrPosition[nColumn], arrPoint[nRow]);
				}
			}
			CheckEncloses(stBounds, arrPoint);
		}
	}
	std::array<double, 16> arrTiny = IDENTITY;
	arrTiny[0] = std::numeric_limits<double>::denorm_min();
	ENGINE_NEXT_CHECK(TransformShadowBounds(stPrimitive, arrTiny, stBounds, arrDiagnostics));
	CheckEncloses(stBounds, { -std::numeric_limits<double>::denorm_min(), -2.0, -3.0 });
	CheckEncloses(stBounds, { 4 * std::numeric_limits<double>::denorm_min(), 5.0, 6.0 });
	ENGINE_NEXT_CHECK(arrDiagnostics.empty());
}
