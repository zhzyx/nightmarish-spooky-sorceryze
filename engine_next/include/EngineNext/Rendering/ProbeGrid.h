/**************************************************************************/
/*  ProbeGrid.h                                                           */
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

#pragma once

#include "engine_next/include/EngineNext/Rendering/GlobalIlluminationSettings.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

struct alignas(16) ProbeSphericalHarmonics
{
	std::array<std::array<float, 4>, 9> arrCoefficients{};
};
struct ProbeDistanceMoments
{
	float fMean = 0;
	float fSecondMoment = 0;
};
struct alignas(16) ProbeGpuState
{
	std::array<std::uint32_t, 4> arrValues{};
};
struct alignas(16) ProbeRayResult
{
	std::array<float, 4> arrRadianceDistance{};
};
struct alignas(16) ProbeRayStatus
{
	std::array<std::uint32_t, 4> arrValues{};
};
static_assert(sizeof(ProbeSphericalHarmonics) == GI_SH_STRIDE);
static_assert(sizeof(ProbeDistanceMoments) == GI_MOMENTS_STRIDE);
static_assert(sizeof(ProbeGpuState) == GI_STATE_STRIDE);
static_assert(sizeof(ProbeRayResult) == GI_RAY_RESULT_STRIDE);
static_assert(sizeof(ProbeRayStatus) == GI_RAY_STATUS_STRIDE);
static_assert(sizeof(std::array<float, 4>) == GI_POSITION_STRIDE);

struct ProbeGridLevel
{
	std::array<double, 3> arrMinimum{};
	std::array<double, 3> arrMaximum{};
	std::array<double, 3> arrSpacing{};
	std::uint32_t nFirstProbe = 0;
};
struct ProbeGrid
{
	std::array<std::uint32_t, 3> arrCounts{};
	std::uint32_t nLevelCount = 0;
	std::array<ProbeGridLevel, MAX_GI_CLIPMAP_LEVELS> arrLevels{};
	GlobalIlluminationBudget stBudget;
	// xyz is world position, w is an exactly representable clipmap level.
	// Subnormal coordinate components are explicitly normalized to zero.
	// x varies fastest, followed by y, z, and then clipmap level.
	std::vector<std::array<float, 4>> arrPositions;
};

// Build keeps the configured center. Snap selects the nearest integral cell
// center independently per level, with halfway cases rounded away from zero.
// A snapped layout is a new immutable snapshot. History remapping/invalidating
// newly exposed cells belongs to the runtime's successful-submit transaction.
// Both calls are pure CPU and preserve output on failure.
[[nodiscard]] bool BuildProbeGrid(const GlobalIlluminationSettings &stSettings, ProbeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool SnapProbeGrid(const GlobalIlluminationSettings &stSettings, const std::array<double, 3> &arrCenter, ProbeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics);

// Epoch counts successful GPU submissions. The function is stateless, wraps
// safely even at UINT64_MAX and emits unique indices in a bounded rolling batch.
// The grid must be an unchanged result of BuildProbeGrid/SnapProbeGrid.
[[nodiscard]] bool BuildProbeUpdateIndices(const ProbeGrid &stGrid, std::uint64_t nSubmissionEpoch, std::vector<std::uint32_t> &out_arrIndices, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
