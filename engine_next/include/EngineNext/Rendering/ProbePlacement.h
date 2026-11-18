/**************************************************************************/
/*  ProbePlacement.h                                                      */
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

#include "engine_next/include/EngineNext/Rendering/ShadowData.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{
enum class ProbeClassification : std::uint32_t
{
	Pending = 0,
	Active = 1,
	Inactive = 2
};
enum class ProbeHitKind : std::uint32_t
{
	Miss = 0,
	Front = 1,
	Back = 2,
	FrontProximity = 3,
	BackProximity = 4,
	ProximityMiss = 5
};
struct ProbeRelocationSettings
{
	bool bEnabled = false;
	float fMinimumClearance = 0.08F;
	float fMaximumOffsetFraction = 0.45F;
	float fBackfaceThreshold = 0.25F;
	std::uint32_t nMinimumRays = 32;
	std::uint32_t nRequiredStableUpdates = 2;
};
struct alignas(16) ProbePlacement
{
	std::array<float, 3> arrOffset{};
	float fClearance = 0;
	ProbeClassification eClassification = ProbeClassification::Pending;
	std::uint32_t nSceneRevision = 0;
	std::uint32_t nStableUpdates = 0;
	std::uint32_t nOffsetRevision = 0;
};
struct ProbeCollisionRay
{
	std::array<float, 3> arrDirection{};
	float fDistance = 0;
	std::array<float, 3> arrNormal{};
	ProbeHitKind eKind = ProbeHitKind::Miss;
};
struct ProbePlacementCandidate
{
	ProbePlacement stPlacement;
	bool bResetHistory = true;
	bool bMoved = false;
};

// Explicit deformation changes use already conservative world-space boxes.
// Draw identities match the RayTracingScene instance order. The caller emits
// an entry only when local vertices or their world-space bounds changed.
struct GiGeometryChange
{
	std::uint32_t nDraw = 0;
	WorldBounds stPreviousWorldBounds;
	WorldBounds stCurrentWorldBounds;
};
static_assert(sizeof(ProbePlacement) == 32);
static_assert(sizeof(ProbeCollisionRay) == 32);

[[nodiscard]] bool ValidateProbeRelocationSettings(const ProbeRelocationSettings &stSettings);

// Affine transform of a conservative local box. Negative scales and singular
// transforms are supported. The box includes binary32 matrix conversion and
// arithmetic roundoff used by the GPU. Failure preserves the output.
[[nodiscard]] bool TransformProbeGeometryBounds(const WorldBounds &stLocal, const std::array<double, 16> &arrWorld,
												WorldBounds &out_stBounds);

// Requires a nonempty list with unique, in-range draw identities. Failure
// preserves the output so a malformed deformation cannot partially dirty GI.
[[nodiscard]] bool BuildProbeGeometryChangeBounds(const std::vector<GiGeometryChange> &arrChanges, std::uint32_t nDrawCount,
												  WorldBounds &out_stBounds);

// Pure, transactional CPU adapter around the exact shared HLSLI reduction.
// Rays originate at anchor + previous.offset and include both triangle sides.
// A moved candidate stays Pending until new geometry rays validate that point.
[[nodiscard]] bool EvaluateProbeRelocation(const ProbeRelocationSettings &stSettings, const std::array<float, 3> &arrSpacing,
										   const ProbePlacement &stPrevious, const std::vector<ProbeCollisionRay> &arrCollisionRays, std::uint32_t nSceneRevision,
										   ProbePlacementCandidate &out_stCandidate, float fTraceDistance = 24);
[[nodiscard]] bool CommitProbeRelocation(const ProbePlacementCandidate &stCandidate, std::uint32_t nCurrentSceneRevision, ProbePlacement &out_stPlacement);
[[nodiscard]] bool BuildProbeRelocationDirections(std::uint32_t nCount, std::vector<std::array<float, 3>> &out_arrDirections);
[[nodiscard]] bool ProbeTouchesChangedGeometry(const ProbeRelocationSettings &stSettings, const std::array<float, 3> &arrAnchor,
											   const std::array<float, 3> &arrSpacing, const WorldBounds &stChangedBounds, bool &out_bAffected);
} // namespace EngineNext::Rendering
