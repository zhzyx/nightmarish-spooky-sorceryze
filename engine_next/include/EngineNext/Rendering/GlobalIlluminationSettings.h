/**************************************************************************/
/*  GlobalIlluminationSettings.h                                          */
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

#include "engine_next/include/EngineNext/Assets/Types.h"
#include "engine_next/include/EngineNext/Rendering/ProbePlacement.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <array>
#include <cstdint>

namespace EngineNext::Rendering
{

constexpr std::uint32_t MAX_GI_PROBES = 65536;
constexpr std::uint32_t MAX_GI_CLIPMAP_LEVELS = 3;
constexpr std::uint32_t GI_DISTANCE_RESOLUTION = 8;
constexpr std::uint32_t GI_SH_STRIDE = 144;
constexpr std::uint32_t GI_MOMENTS_STRIDE = 8;
constexpr std::uint32_t GI_STATE_STRIDE = 16;
constexpr std::uint32_t GI_POSITION_STRIDE = 16;
constexpr std::uint32_t GI_RAY_RESULT_STRIDE = 16;
constexpr std::uint32_t GI_RAY_STATUS_STRIDE = 16;
constexpr std::uint32_t GI_PENDING_FRAMES = 3;
constexpr std::uint64_t MAX_GI_GPU_BYTES = 512ULL * 1024 * 1024;

struct GlobalIlluminationSettings
{
	bool bEnabled = false;
	std::array<double, 3> arrBoundsMinimum{ -12, -4, -12 };
	std::array<double, 3> arrBoundsMaximum{ 12, 20, 12 };
	std::array<std::uint32_t, 3> arrProbeCounts{ 24, 24, 24 };
	std::uint32_t nClipmapLevels = 3;
	std::uint32_t nUpdatesPerFrame = 128;
	std::uint32_t nRaysPerProbe = 32;
	double dTraceDistance = 50;
	double dHysteresis = 0.95;
	double dNormalBias = 0.05;
	double dViewBias = 0.1;
	double dBounceStrength = 1;
	double dHistoryChangeThreshold = 0.2;
	std::uint64_t nMaxGpuBytes = 128ULL * 1024 * 1024;
	ProbeRelocationSettings stPlacement;
};

struct GlobalIlluminationBudget
{
	std::uint32_t nProbeCount = 0;
	std::uint32_t nUpdateCount = 0;
	std::uint32_t nRayCount = 0;
	std::uint32_t nStateStride = GI_STATE_STRIDE;
	std::uint64_t nHistoryBytes = 0;
	std::uint64_t nPositionBytes = 0;
	std::uint64_t nRayBytes = 0;
	std::uint64_t nUpdateBytes = 0;
	std::uint64_t nTotalBytes = 0;
};

// All settings are checked even while disabled. Bounds and every expanded
// clipmap coordinate must fit distinct binary32 positions. Trace distance and
// its square must survive finite binary32 arithmetic. The budget covers two
// persistent histories and three frame-local ray/update buffers. BLAS/TLAS,
// allocator alignment and the renderer's other resources require separate
// accounting. Failure preserves the output. Pure CPU, immutable input.
[[nodiscard]] bool BuildGlobalIlluminationBudget(const GlobalIlluminationSettings &stSettings, GlobalIlluminationBudget &out_stBudget, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool ValidateGlobalIlluminationSettings(const GlobalIlluminationSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);

// Optional object fields use the defaults above. Unknown keys are rejected.
// World bounds are {minimum:[x,y,z],maximum:[x,y,z]}; count axes include both
// endpoints. Every outer clipmap doubles the level-zero span about its center.
// Parsing is transactional and does not change the M3 scene/asset contract.
[[nodiscard]] bool ParseGlobalIlluminationSettings(const Serialization::JsonValue &stValue, GlobalIlluminationSettings &out_stSettings, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
