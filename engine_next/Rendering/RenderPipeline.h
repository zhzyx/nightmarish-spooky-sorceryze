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
	DirectionalShadow = 7,
	LocalShadow = 8,
	TemporalResolve = 9,
	PrepareExposure = 10,
	HistogramBuild = 11,
	ExposureAdapt = 12,
	BloomDownsample = 13,
	BloomUpsample = 14,
	PostProcessReadback = 15,
	ReflectionColorMip = 16,
	ReflectionTrace = 17,
	ReflectionComposite = 18,
	ReflectionRadiance = 19,
	VolumeInject = 20,
	VolumeLight = 21,
	VolumeTemporal = 22,
	VolumeIntegrate = 23,
	VolumeComposite = 24,
	ForwardCopy = 25,
	Transparency = 26,
	VolumePrepare = 27,
	GiBuildScene = 28,
	GiUpload = 29,
	GiPrepare = 30,
	GiRemap = 31,
	GiTrace = 32,
	GiUpdate = 33,
	GiReadback = 34,
};

struct ForwardEffects
{
	bool bVolume = false;
	bool bTransparency = false;
};

struct RenderPipeline
{
	CompiledGraph stGraph;
	// Indexed by the stable PassId, independently of the compiled execution order.
	std::vector<PassWork> arrWorkByPass;
	// Indexed by PassId. Bloom and reflection color-mip passes have valid indices.
	std::vector<std::uint32_t> arrPassMipIndex;
	ResourceId nTint = INVALID_RESOURCE;
	ResourceId nColor = INVALID_RESOURCE;
	ResourceId nDepth = INVALID_RESOURCE;
	ResourceId nBackbuffer = INVALID_RESOURCE;
	ResourceId nHdr = INVALID_RESOURCE;
	ResourceId nDirectionalShadow = INVALID_RESOURCE;
	ResourceId nLocalShadow = INVALID_RESOURCE;
	ResourceId nMotion = INVALID_RESOURCE;
	ResourceId nObjectId = INVALID_RESOURCE;
	ResourceId nHistogram = INVALID_RESOURCE;
	ResourceId nExposureRead = INVALID_RESOURCE;
	ResourceId nExposureWrite = INVALID_RESOURCE;
	ResourceId nPostReadback = INVALID_RESOURCE;
	ResourceId nEnvironmentSpecular = INVALID_RESOURCE;
	ResourceId nReflection = INVALID_RESOURCE;
	ResourceId nReflectedHdr = INVALID_RESOURCE;
	ResourceId nVolumeMedium = INVALID_RESOURCE;
	ResourceId nVolumeEmission = INVALID_RESOURCE;
	ResourceId nVolumeSource = INVALID_RESOURCE;
	ResourceId nVolumeHistoryRead = INVALID_RESOURCE;
	ResourceId nVolumeHistoryWrite = INVALID_RESOURCE;
	ResourceId nVolumeIntegral = INVALID_RESOURCE;
	ResourceId nForwardHdr = INVALID_RESOURCE;
	ResourceId nReactiveMask = INVALID_RESOURCE;
	ResourceId nGiScene = INVALID_RESOURCE;
	ResourceId nGiPositions = INVALID_RESOURCE;
	ResourceId nGiUpload = INVALID_RESOURCE;
	ResourceId nGiRays = INVALID_RESOURCE;
	ResourceId nGiRayStatus = INVALID_RESOURCE;
	ResourceId nGiReadback = INVALID_RESOURCE;
	std::array<ResourceId, 3> arrGiRead{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	std::array<ResourceId, 3> arrGiWrite{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	// Additional reflection color levels 1..N-1. Before tracing, level zero is
	// nReflectedHdr containing full lighting without screen-space reflections.
	std::vector<ResourceId> arrReflectionMips;
	std::vector<ResourceId> arrBloomDown;
	std::vector<ResourceId> arrBloomUp;
	std::array<ResourceId, 4> arrGbuffer{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	std::array<ResourceId, 2> arrMaterialBuffers{ INVALID_RESOURCE, INVALID_RESOURCE };
	// Color, linear depth, world normal, and object ID in matching read/write slots.
	std::array<ResourceId, 4> arrHistoryRead{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	std::array<ResourceId, 4> arrHistoryWrite{ INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE, INVALID_RESOURCE };
	std::uint32_t nGraphicsPassCount = 0;
	std::uint32_t nComputePassCount = 0;
};

// Builds an owned fixed-mesh or HDR deferred plan on the caller's thread.
// Temporal resolve applies to scene mode. History resources are imported in Common
// and must be mapped to disjoint, initialized read and write allocations by the caller.
// Exposure is optional. PrepareExposure clears its histogram each frame and seeds
// the read record on its first use. Bloom requires exposure and supports 1..6 mips.
// The last downsample is the last upsample input, so arrBloomUp has mips minus one
// entries. Exposure readback remains CopyDestination. Other post-process imported
// resources finish in Common for reuse.
// Reflection color levels include their full-lighting base and are [1,6] when enabled.
// Zero disables reflections. Fixed-mesh mode ignores valid reflection options.
// Volume history is independent of scene TAA. VolumePrepare initializes the
// imported read history when required. ForwardCopy preserves opaque HDR before
// transparency when volume compositing is disabled. Transparency loads its HDR
// target and clears the reactive mask before its draws. All forward resources
// finish in Common. Fixed-mesh mode ignores these optional forward effects.
// Optional material attributes add two geometry targets used by lighting and
// reflection tracing, then returned to Common. Fixed-mesh mode ignores them.
// GI builds the frame-owned acceleration structure, remaps probe history,
// traces a bounded update batch and integrates it before lighting receivers.
// The host maps the read/write probe groups to disjoint allocations. Their
// roles change only after successful submission. Acceleration structures and
// upload buffers retain their immutable native states across frame boundaries.
// Failure preserves the previous output and reports the graph diagnostic.
[[nodiscard]] bool BuildRenderPipeline(bool bSceneMode, RenderPipeline &out_stPipeline, GraphDiagnostic &out_stDiagnostic, std::uint32_t nLocalShadowViews = 0,
									   bool bTemporal = true, bool bExposure = false, std::uint32_t nBloomMips = 0, std::uint32_t nReflectionMips = 0,
									   ForwardEffects stForwardEffects = {}, bool bMaterialExtensions = false, bool bGlobalIllumination = false);

} // namespace EngineNext::Rendering
