/**************************************************************************/
/*  RayReflectionSettings.h                                               */
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

#include <cstdint>

namespace EngineNext::Rendering
{

struct RayReflectionSettings
{
	bool bEnabled = false;
	std::uint32_t nResolutionDivisor = 2;
	std::uint32_t nSamplesPerLobe = 1;
	std::uint32_t nSpatialPasses = 2;
	std::uint32_t nMaxHistory = 16;
	double dHistoryWeight = 0.9;
	double dDepthThreshold = 0.02;
	double dNormalThreshold = 0.9;
	double dRoughnessThreshold = 0.15;
	std::uint64_t nMaxGpuBytes = 768ULL * 1024 * 1024;
};

struct RayReflectionBudget
{
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint64_t nPixels = 0;
	std::uint64_t nPayloadBytes = 0;
	std::uint64_t nPrimaryRays = 0;
};

// Images use unexposed binary32 radiance. The bounded image payload includes
// separate base/coat histories, shared surface metadata and spatial scratch.
// D3D12 allocation alignment and an owned ray scene are additionally checked
// by the backend against the configured budget before initialization commits.
[[nodiscard]] bool ValidateRayReflectionSettings(const RayReflectionSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool BuildRayReflectionBudget(const RayReflectionSettings &stSettings, std::uint32_t nWidth, std::uint32_t nHeight,
											RayReflectionBudget &out_stBudget, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
