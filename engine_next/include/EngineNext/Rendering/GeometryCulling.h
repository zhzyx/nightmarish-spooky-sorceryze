/**************************************************************************/
/*  GeometryCulling.h                                                     */
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
#include "engine_next/include/EngineNext/Rendering/MeshData.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace EngineNext::Rendering
{

struct alignas(16) GpuClusterInput
{
	std::array<float, 4> arrMinimum{};
	std::array<float, 4> arrMaximum{};
	std::array<std::uint32_t, 4> arrDraw{};
};

struct alignas(16) GpuCullingConstants
{
	std::array<float, 16> arrViewProjection{};
	std::array<std::array<float, 4>, 6> arrPlanes{};
	std::array<std::uint32_t, 4> arrViewport{};
	std::array<std::uint32_t, 4> arrCounts{};
	std::array<float, 4> arrParameters{};
};

static_assert(sizeof(GpuClusterInput) == 48);
static_assert(offsetof(GpuClusterInput, arrMaximum) == 16);
static_assert(offsetof(GpuClusterInput, arrDraw) == 32);
static_assert(sizeof(GpuCullingConstants) == 208);
static_assert(offsetof(GpuCullingConstants, arrPlanes) == 64);
static_assert(offsetof(GpuCullingConstants, arrViewport) == 160);
static_assert(offsetof(GpuCullingConstants, arrCounts) == 176);
static_assert(offsetof(GpuCullingConstants, arrParameters) == 192);

// Extracts the six closed D3D clip half-spaces from the GPU's column-major
// view-projection matrix. Planes whose normalized coefficients would flush to
// zero are disabled conservatively. Failure preserves the previous output.
[[nodiscard]] bool BuildCullingFrustum(const std::array<float, 16> &arrViewProjection,
									   std::array<std::array<float, 4>, 6> &out_arrPlanes, Assets::Diagnostics &out_arrDiagnostics);

// Adapts an already source-verified MeshCluster to a conservative world AABB.
// Affine column-major transforms and all bounds must be finite. Floating-point
// conversion rounds bounds outward. The caller maps cluster-local triangles to
// its packed index buffer and supplies that range and the draw instance index.
[[nodiscard]] bool BuildClusterInput(const MeshCluster &stCluster, const std::array<double, 16> &arrWorld, std::uint32_t nStartIndex, std::int32_t nBaseVertex,
									 std::uint32_t nInstance, GpuClusterInput &out_stInput, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
