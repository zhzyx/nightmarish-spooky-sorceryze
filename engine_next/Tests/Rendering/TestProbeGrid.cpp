/**************************************************************************/
/*  TestProbeGrid.cpp                                                     */
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
#include "engine_next/include/EngineNext/Rendering/ProbeGrid.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace
{
using namespace EngineNext::Rendering;
using EngineNext::Assets::Diagnostics;
} //namespace

ENGINE_NEXT_TEST("Probe grid stores three expanded levels with explicit linear identity")
{
	GlobalIlluminationSettings stSettings;
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.nLevelCount, 3U);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrPositions.size(), 41472U);
	const std::uint32_t nPerLevel = 24 * 24 * 24;
	for (std::uint32_t nLevel = 0; nLevel < 3; ++nLevel)
	{
		const ProbeGridLevel &stLevel = stGrid.arrLevels[nLevel];
		ENGINE_NEXT_CHECK_EQ(stLevel.nFirstProbe, nPerLevel * nLevel);
		const std::array<float, 4> &arrFirst = stGrid.arrPositions[stLevel.nFirstProbe];
		const std::array<float, 4> &arrLast = stGrid.arrPositions[stLevel.nFirstProbe + nPerLevel - 1];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			ENGINE_NEXT_CHECK_EQ(arrFirst[nAxis], static_cast<float>(stLevel.arrMinimum[nAxis]));
			ENGINE_NEXT_CHECK_EQ(arrLast[nAxis], static_cast<float>(stLevel.arrMaximum[nAxis]));
		}
		ENGINE_NEXT_CHECK_EQ(arrFirst[3], static_cast<float>(nLevel));
		ENGINE_NEXT_CHECK_EQ(arrLast[3], static_cast<float>(nLevel));
	}
	ENGINE_NEXT_CHECK(stGrid.arrPositions[1][0] > stGrid.arrPositions[0][0]);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrPositions[1][1], stGrid.arrPositions[0][1]);
	ENGINE_NEXT_CHECK(stGrid.arrPositions[24][1] > stGrid.arrPositions[0][1]);
	ENGINE_NEXT_CHECK(stGrid.arrPositions[24 * 24][2] > stGrid.arrPositions[0][2]);
}

ENGINE_NEXT_TEST("Probe snapping is stable below cell boundary and symmetric at negative coordinates")
{
	GlobalIlluminationSettings stSettings;
	stSettings.arrBoundsMinimum = { -1, -1, -1 };
	stSettings.arrBoundsMaximum = { 1, 1, 1 };
	stSettings.arrProbeCounts = { 3, 3, 3 };
	ProbeGrid stGrid;
	ProbeGrid stSame;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(SnapProbeGrid(stSettings, { -0.6, 0.6, -1.5 }, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK(SnapProbeGrid(stSettings, { -0.7, 0.7, -1.6 }, stSame, arrDiagnostics));
	ENGINE_NEXT_CHECK(stGrid.arrPositions == stSame.arrPositions);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[0].arrMinimum[0], -2);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[0].arrMinimum[1], 0);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[0].arrMinimum[2], -3);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[1].arrMinimum[0], -2);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[1].arrMinimum[2], -4);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[2].arrMinimum[2], -4);
	ENGINE_NEXT_CHECK(SnapProbeGrid(stSettings, { -0.5, 0.5, 0 }, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[0].arrMinimum[0], -2);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrLevels[0].arrMinimum[1], 0);
}

ENGINE_NEXT_TEST("Probe default clipmaps cover the same center through moving level boundaries")
{
	GlobalIlluminationSettings stSettings;
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	for (double dCenter : { -100.0, -0.001, 0.0, 0.001, 100.0 })
	{
		ENGINE_NEXT_CHECK(SnapProbeGrid(stSettings, { dCenter, dCenter, dCenter }, stGrid, arrDiagnostics));
		for (std::uint32_t nLevel = 0; nLevel < 3; ++nLevel)
		{
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				ENGINE_NEXT_CHECK(stGrid.arrLevels[nLevel].arrMinimum[nAxis] <= dCenter);
				ENGINE_NEXT_CHECK(stGrid.arrLevels[nLevel].arrMaximum[nAxis] >= dCenter);
				if (nLevel > 0)
				{
					ENGINE_NEXT_CHECK(stGrid.arrLevels[nLevel].arrMinimum[nAxis] <= stGrid.arrLevels[nLevel - 1].arrMinimum[nAxis]);
					ENGINE_NEXT_CHECK(stGrid.arrLevels[nLevel].arrMaximum[nAxis] >= stGrid.arrLevels[nLevel - 1].arrMaximum[nAxis]);
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("Probe rolling update batches wrap without epoch overflow")
{
	GlobalIlluminationSettings stSettings;
	stSettings.nClipmapLevels = 1;
	stSettings.arrProbeCounts = { 2, 2, 2 };
	stSettings.nUpdatesPerFrame = 3;
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	std::vector<std::uint32_t> arrIndices;
	ENGINE_NEXT_CHECK(BuildProbeUpdateIndices(stGrid, 0, arrIndices, arrDiagnostics));
	ENGINE_NEXT_CHECK((arrIndices == std::vector<std::uint32_t>{ 0, 1, 2 }));
	ENGINE_NEXT_CHECK(BuildProbeUpdateIndices(stGrid, 2, arrIndices, arrDiagnostics));
	ENGINE_NEXT_CHECK((arrIndices == std::vector<std::uint32_t>{ 6, 7, 0 }));
	ENGINE_NEXT_CHECK(BuildProbeUpdateIndices(stGrid, std::numeric_limits<std::uint64_t>::max(), arrIndices, arrDiagnostics));
	ENGINE_NEXT_CHECK((arrIndices == std::vector<std::uint32_t>{ 5, 6, 7 }));
	std::array<bool, 8> arrSeen{};
	for (std::uint64_t nFrame = 0; nFrame < 8; ++nFrame)
	{
		ENGINE_NEXT_CHECK(BuildProbeUpdateIndices(stGrid, nFrame, arrIndices, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(arrIndices.size(), 3U);
		ENGINE_NEXT_CHECK(arrIndices[0] != arrIndices[1] && arrIndices[1] != arrIndices[2] && arrIndices[0] != arrIndices[2]);
		for (std::uint32_t nIndex : arrIndices)
		{
			arrSeen[nIndex] = true;
		}
	}
	for (bool bSeen : arrSeen)
	{
		ENGINE_NEXT_CHECK(bSeen);
	}
}

ENGINE_NEXT_TEST("Probe grid failures preserve previous immutable snapshot and batch")
{
	GlobalIlluminationSettings stSettings;
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	const std::vector<std::array<float, 4>> arrBefore = stGrid.arrPositions;
	ENGINE_NEXT_CHECK(!SnapProbeGrid(stSettings, { std::numeric_limits<double>::infinity(), 0, 0 }, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK(stGrid.arrPositions == arrBefore);
	ENGINE_NEXT_CHECK(!SnapProbeGrid(stSettings, { 1e30, 0, 0 }, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK(stGrid.arrPositions == arrBefore);
	stSettings.arrProbeCounts[0] = 0;
	ENGINE_NEXT_CHECK(!BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK(stGrid.arrPositions == arrBefore);
	std::vector<std::uint32_t> arrIndices{ 88 };
	stGrid.arrPositions.clear();
	ENGINE_NEXT_CHECK(!BuildProbeUpdateIndices(stGrid, 0, arrIndices, arrDiagnostics));
	ENGINE_NEXT_CHECK((arrIndices == std::vector<std::uint32_t>{ 88 }));
}

ENGINE_NEXT_TEST("Probe maximum grid retains finite ordered positions and bounded update indices")
{
	GlobalIlluminationSettings stSettings;
	stSettings.arrProbeCounts = { 16, 64, 64 };
	stSettings.nClipmapLevels = 1;
	stSettings.nUpdatesPerFrame = 1024;
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stGrid.arrPositions.size(), 65536U);
	for (std::size_t nIndex = 0; nIndex < stGrid.arrPositions.size(); nIndex += 257)
	{
		const std::array<float, 4> &arrPosition = stGrid.arrPositions[nIndex];
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			ENGINE_NEXT_CHECK(std::isfinite(arrPosition[nAxis]));
			ENGINE_NEXT_CHECK(arrPosition[nAxis] >= stGrid.arrLevels[0].arrMinimum[nAxis]);
			ENGINE_NEXT_CHECK(arrPosition[nAxis] <= stGrid.arrLevels[0].arrMaximum[nAxis]);
		}
		ENGINE_NEXT_CHECK_EQ(arrPosition[3], 0);
	}
	std::vector<std::uint32_t> arrIndices;
	ENGINE_NEXT_CHECK(BuildProbeUpdateIndices(stGrid, std::numeric_limits<std::uint64_t>::max(), arrIndices, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(arrIndices.size(), 1024U);
	for (std::size_t nIndex = 1; nIndex < arrIndices.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK(arrIndices[nIndex] < 65536);
		ENGINE_NEXT_CHECK_EQ(arrIndices[nIndex], (arrIndices[nIndex - 1] + 1) % 65536);
	}
}

ENGINE_NEXT_TEST("Probe GPU coordinate normalization preserves distinct normal spacing")
{
	GlobalIlluminationSettings stSettings;
	stSettings.nClipmapLevels = 1;
	stSettings.arrProbeCounts = { 3, 3, 3 };
	const double dTiny = std::numeric_limits<float>::denorm_min();
	const double dNormal = std::numeric_limits<float>::min();
	stSettings.arrBoundsMinimum = { dTiny, 0, 0 };
	stSettings.arrBoundsMaximum = { 2 * dNormal + dTiny, 2, 2 };
	ProbeGrid stGrid;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSettings.arrBoundsMinimum[0], dTiny);
	ENGINE_NEXT_CHECK_EQ(stGrid.arrPositions[0][0], 0);
	ENGINE_NEXT_CHECK(stGrid.arrPositions[1][0] >= dNormal);
	ENGINE_NEXT_CHECK(stGrid.arrPositions[2][0] > stGrid.arrPositions[1][0]);
	stSettings.arrBoundsMinimum[0] = -dTiny;
	stSettings.arrBoundsMaximum[0] = dTiny;
	ENGINE_NEXT_CHECK(!BuildProbeGrid(stSettings, stGrid, arrDiagnostics));
}
