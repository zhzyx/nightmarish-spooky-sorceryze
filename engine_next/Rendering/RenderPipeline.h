/**************************************************************************/
/*  RenderPipeline.h                                                      */
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

#include "engine_next/include/EngineNext/Rendering/FrameGraph.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

enum class PassWork : std::uint8_t
{
	ComputeTint = 0,
	FixedMesh = 1,
	GBuffer = 2,
	DeferredLighting = 3,
	ToneMap = 4,
	CopyToBackbuffer = 5,
	Present = 6,
};

struct RenderPipeline
{
	CompiledGraph stGraph;
	// Indexed by the stable PassId, independently of the compiled execution order.
	std::vector<PassWork> arrWorkByPass;
	ResourceId nTint = INVALID_RESOURCE;
	ResourceId nColor = INVALID_RESOURCE;
	ResourceId nDepth = INVALID_RESOURCE;
	ResourceId nBackbuffer = INVALID_RESOURCE;
	ResourceId nHdr = INVALID_RESOURCE;
	std::array<ResourceId, 4> arrGbuffer{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	std::uint32_t nGraphicsPassCount = 0;
	std::uint32_t nComputePassCount = 0;
};

// Builds an owned fixed-mesh or HDR deferred plan on the caller's thread.
// Failure preserves the previous output and reports the graph diagnostic.
[[nodiscard]] bool BuildRenderPipeline(bool bSceneMode, RenderPipeline &out_stPipeline, GraphDiagnostic &out_stDiagnostic);

} // namespace EngineNext::Rendering
