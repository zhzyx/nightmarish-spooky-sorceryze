/**************************************************************************/
/*  GeometryScene.h                                                       */
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

#include "engine_next/include/EngineNext/Rendering/GeometryCulling.h"
#include "engine_next/include/EngineNext/Rendering/GeometrySettings.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{
struct alignas(16) GeometryCluster
{
	GpuClusterInput stInput;
	std::array<std::uint32_t, 4> arrMetadata{};
};
static_assert(sizeof(GeometryCluster) == 64);
static_assert(offsetof(GeometryCluster, arrMetadata) == 48);

struct GeometryBucket
{
	std::uint32_t nMaterial = 0;
	std::uint32_t nFlags = 0;
	std::uint32_t nFirstCommand = 0;
	std::uint32_t nCommandCapacity = 0;
};
struct GeometryClusterSet
{
	std::vector<GeometryCluster> arrClusters;
	std::vector<GeometryBucket> arrBuckets;
	std::uint32_t nDrawCount = 0;
	std::uint64_t nCandidateCount = 0;
	std::uint64_t nTriangleCount = 0;
	bool bCapacityFallback = false;
};

// Static source adaptation. v1 primitives without cooked clusters are cooked
// through the same deterministic helper as v2. Vertex/index offsets follow the
// existing asset/primitive upload order. BLEND stays on the forward draw path.
// A capacity shortfall succeeds with bCapacityFallback and empty command data;
// the caller must retain the complete conventional draw path in that case.
// Other failures preserve output. This CPU function owns no GPU resources.
[[nodiscard]] bool BuildGeometryClusterSet(const RenderScene &stScene, const GeometrySettings &stSettings,
										   GeometryClusterSet &out_stClusters, Assets::Diagnostics &out_arrDiagnostics);
} // namespace EngineNext::Rendering
