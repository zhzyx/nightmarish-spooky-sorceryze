/**************************************************************************/
/*  VolumeGrid.h                                                          */
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

#include "engine_next/include/EngineNext/Rendering/VolumeSettings.h"

#include <array>
#include <cstdint>

namespace EngineNext::Rendering
{

struct CameraSettings;

struct VolumeGrid
{
	std::uint32_t nWidth = 0;
	std::uint32_t nHeight = 0;
	std::uint32_t nDepth = 0;
	std::uint64_t nFroxelCount = 0;
	double dNear = 0;
	double dFar = 0;
	double dLogDepthRatio = 0;
	double dInverseLogDepthRatio = 0;
	std::array<double, 129> arrDepthBoundaries{};
	std::uint64_t nCoefficientTextureBytes = 0;
	std::uint64_t nIntegralTextureBytes = 0;
	std::uint64_t nCurrentFrameBytes = 0;
	std::uint64_t nHistoryBytes = 0;
	// Three independent current-frame sets and two shared history textures.
	std::uint64_t nResidentVolumeBytes = 0;
};

// Builds a value snapshot transactionally. Only the camera clipping distances
// are consumed. Width/height are [1,16384], cells obey VolumeSettings, and the
// grid has at most MAX_VOLUME_FROXELS. The far boundary is min(camera far,fog
// distance); all adjacent Z boundaries must remain distinct in binary32.
// Coefficient/current-source/history use RGBA32F; integrated S/T uses RGBA16F.
// Byte counts describe payloads before device allocation alignment.
// Full-screen composite targets and descriptors are reported by the runtime.
[[nodiscard]] bool BuildVolumeGrid(const CameraSettings &stCamera, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight,
								   const VolumeSettings &stSettings, VolumeGrid &out_stGrid, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
