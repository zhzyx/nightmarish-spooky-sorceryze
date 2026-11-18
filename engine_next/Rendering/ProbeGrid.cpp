/**************************************************************************/
/*  ProbeGrid.cpp                                                         */
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

#include "engine_next/include/EngineNext/Rendering/ProbeGrid.h"

#include <cmath>
#include <cstddef>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
bool FloatPosition(double dValue)
{
	return std::isfinite(dValue) && std::abs(dValue) <= std::numeric_limits<float>::max();
}

bool Build(const GlobalIlluminationSettings &stSettings, const std::array<double, 3> *pCenter, ProbeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics)
{
	ProbeGrid stGrid;
	if (!BuildGlobalIlluminationBudget(stSettings, stGrid.stBudget, out_arrDiagnostics))
	{
		return false;
	}
	stGrid.arrCounts = stSettings.arrProbeCounts;
	stGrid.nLevelCount = stSettings.nClipmapLevels;
	const std::uint32_t nPerLevel = stGrid.stBudget.nProbeCount / stGrid.nLevelCount;
	for (std::uint32_t nLevel = 0; nLevel < stGrid.nLevelCount; ++nLevel)
	{
		ProbeGridLevel &stLevel = stGrid.arrLevels[nLevel];
		stLevel.nFirstProbe = nLevel * nPerLevel;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const double dSpan = std::ldexp(stSettings.arrBoundsMaximum[nAxis] - stSettings.arrBoundsMinimum[nAxis], static_cast<int>(nLevel));
			stLevel.arrSpacing[nAxis] = dSpan / (stGrid.arrCounts[nAxis] - 1);
			double dCenter = (stSettings.arrBoundsMinimum[nAxis] + stSettings.arrBoundsMaximum[nAxis]) * 0.5;
			if (pCenter != nullptr)
			{
				if (!FloatPosition((*pCenter)[nAxis]))
				{
					Assets::AddDiagnostic(out_arrDiagnostics, "probe_center", "$.global_illumination", "Probe center must fit finite binary32 coordinates.");
					return false;
				}
				dCenter = std::round((*pCenter)[nAxis] / stLevel.arrSpacing[nAxis]) * stLevel.arrSpacing[nAxis];
			}
			stLevel.arrMinimum[nAxis] = dCenter - dSpan * 0.5;
			stLevel.arrMaximum[nAxis] = dCenter + dSpan * 0.5;
			double dPrevious = -std::numeric_limits<double>::infinity();
			for (std::uint32_t nIndex = 0; nIndex < stGrid.arrCounts[nAxis]; ++nIndex)
			{
				const double dPosition = stLevel.arrMinimum[nAxis] + nIndex * stLevel.arrSpacing[nAxis];
				if (!FloatPosition(dPosition))
				{
					Assets::AddDiagnostic(out_arrDiagnostics, "probe_precision", "$.global_illumination", "Snapped probe coordinates must remain distinct finite binary32 values.");
					return false;
				}
				const float fPosition = static_cast<float>(dPosition);
				const float fGpuPosition = std::abs(fPosition) < std::numeric_limits<float>::min() ? 0 : fPosition;
				if (fGpuPosition <= dPrevious)
				{
					Assets::AddDiagnostic(out_arrDiagnostics, "probe_precision", "$.global_illumination", "GPU-normalized snapped coordinates must remain distinct.");
					return false;
				}
				dPrevious = fGpuPosition;
			}
		}
	}
	stGrid.arrPositions.resize(stGrid.stBudget.nProbeCount);
	for (std::uint32_t nLevel = 0; nLevel < stGrid.nLevelCount; ++nLevel)
	{
		const ProbeGridLevel &stLevel = stGrid.arrLevels[nLevel];
		for (std::uint32_t nLocal = 0; nLocal < nPerLevel; ++nLocal)
		{
			const std::array<std::uint32_t, 3> arrCell{ nLocal % stGrid.arrCounts[0], (nLocal / stGrid.arrCounts[0]) % stGrid.arrCounts[1], nLocal / (stGrid.arrCounts[0] * stGrid.arrCounts[1]) };
			std::array<float, 4> &arrPosition = stGrid.arrPositions[stLevel.nFirstProbe + nLocal];
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const float fPosition = static_cast<float>(stLevel.arrMinimum[nAxis] + arrCell[nAxis] * stLevel.arrSpacing[nAxis]);
				arrPosition[nAxis] = std::abs(fPosition) < std::numeric_limits<float>::min() ? 0 : fPosition;
			}
			arrPosition[3] = static_cast<float>(nLevel);
		}
	}
	out_stGrid = std::move(stGrid);
	return true;
}
} // namespace

bool BuildProbeGrid(const GlobalIlluminationSettings &stSettings, ProbeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics)
{
	return Build(stSettings, nullptr, out_stGrid, out_arrDiagnostics);
}

bool SnapProbeGrid(const GlobalIlluminationSettings &stSettings, const std::array<double, 3> &arrCenter, ProbeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics)
{
	return Build(stSettings, &arrCenter, out_stGrid, out_arrDiagnostics);
}

bool BuildProbeUpdateIndices(const ProbeGrid &stGrid, std::uint64_t nSubmissionEpoch, std::vector<std::uint32_t> &out_arrIndices, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nCount = stGrid.stBudget.nProbeCount;
	const std::uint32_t nUpdates = stGrid.stBudget.nUpdateCount;
	if (nCount == 0 || nCount > MAX_GI_PROBES || nUpdates == 0 || nUpdates > nCount || stGrid.arrPositions.size() != nCount || stGrid.nLevelCount == 0 || stGrid.nLevelCount > MAX_GI_CLIPMAP_LEVELS)
	{
		Assets::AddDiagnostic(out_arrDiagnostics, "probe_grid", "$.global_illumination", "Expected an unchanged validated probe grid.");
		return false;
	}
	const std::uint32_t nFirst = static_cast<std::uint32_t>(((nSubmissionEpoch % nCount) * nUpdates) % nCount);
	std::vector<std::uint32_t> arrIndices(nUpdates);
	for (std::uint32_t nIndex = 0; nIndex < nUpdates; ++nIndex)
	{
		arrIndices[nIndex] = (nFirst + nIndex) % nCount;
	}
	out_arrIndices = std::move(arrIndices);
	return true;
}

} // namespace EngineNext::Rendering
