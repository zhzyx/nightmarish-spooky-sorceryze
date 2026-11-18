/**************************************************************************/
/*  GeometryLod.h                                                         */
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
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{
// Caller-supplied geometric bounds must conservatively enclose the represented
// subtree. Building approximation geometry and certified errors is separate.
struct LodNode
{
	std::array<double, 3> arrMinimum{};
	std::array<double, 3> arrMaximum{};
	double dGeometricErrorBound = 0;
	std::uint32_t nFirstChild = 0;
	std::uint32_t nChildCount = 0;
	std::uint32_t nPage = 0;
};
struct LodView
{
	std::array<double, 3> arrPosition{};
	std::array<double, 3> arrForward{ 0, 0, -1 };
	// Maximum absolute X/Y perspective projection scale in pixels.
	double dProjectionPixels = 1;
	double dNearDistance = .001;
	double dMaximumErrorPixels = 1;
};
struct LodSelection
{
	std::vector<std::uint32_t> arrNodes;
	std::vector<std::uint32_t> arrRequestedPages;
	double dMaximumSelectedErrorPixels = 0;
	bool bResidencyLimited = false;
	bool bCapacityLimited = false;
};
// Pure, immutable-input selection. Roots must be resident. A node is replaced
// only by its complete resident child set, keeping a closed cut at every step.
// Missing pages are deduplicated. Failure leaves prior output intact.
// Metadata is capped at 1,048,576 nodes/pages for bounded work.
[[nodiscard]] bool SelectLodCut(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
								const std::vector<std::uint8_t> &arrResident, const LodView &stView, std::uint32_t nMaximumSelected,
								LodSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics);
// Previous selection is committed only after successful frame submission.
// Refinement uses (1+hysteresis), coarsening uses (1-hysteresis); an empty
// previous cut starts without history. The fraction must be finite in [0,1).
[[nodiscard]] bool SelectLodCutWithHistory(const std::vector<LodNode> &arrNodes, const std::vector<std::uint32_t> &arrRoots,
										   const std::vector<std::uint8_t> &arrResident, const LodView &stView, std::uint32_t nMaximumSelected,
										   const std::vector<std::uint32_t> &arrPrevious, double dHysteresis,
										   LodSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics);

struct LodCookSettings
{
	std::uint32_t nGroupSize = 4;
	std::uint32_t nMaximumNodes = 65536;
	std::uint32_t nVerificationDepth = 1;
	std::uint64_t nMaximumDistanceTests = 2000000;
	std::uint64_t nMaximumOutputIndices = 16000000;
	double dTargetTriangleRatio = .5;
	double dVerificationCellRadius = .05;
};

struct LodGeometry
{
	std::vector<std::uint32_t> arrIndices;
	std::uint32_t nFirstSourceTriangle = 0;
	std::uint32_t nSourceTriangleCount = 0;
};

struct CookedLodHierarchy
{
	std::vector<LodNode> arrNodes;
	std::vector<LodGeometry> arrGeometry;
	std::vector<std::uint32_t> arrRoots;
	std::uint64_t nDistanceTests = 0;
	std::uint64_t nOutputIndices = 0;
	std::uint32_t nSimplifiedNodes = 0;
	std::uint32_t nVerificationFallbacks = 0;
	std::uint32_t nTopologyFallbacks = 0;
};

// Both index sets address the same immutable primitive. The counter includes
// exact target-point tests spent on an exhausted attempt. A balanced target BVH
// uses at most 64 MiB of scratch and a fixed traversal stack; larger inputs use
// the bounded linear query. Pruned targets can only enlarge the upper bound.
// The bound changes only after completing
// both directed surface checks. Zero work budget supports deterministic fallback.
[[nodiscard]] bool ComputeLodDeviationBound(const MeshPrimitive &stPrimitive,
											const std::vector<std::uint32_t> &arrSource, const std::vector<std::uint32_t> &arrTarget,
											const LodCookSettings &stSettings, std::uint64_t &out_nDistanceTests, double &out_dBound);

// Bounded synchronous hierarchy Cook. Each call processes one material
// primitive. Vertices remain immutable and all indices address its original
// MeshVertex array. Complete source triangle intervals define child coverage.
// Root and parent payloads remain complete when verification exhausts its
// distance-query budget. Failure leaves the previous output unchanged.
// Reported double errors include conservative sample covering radii and a
// coordinate-rounding allowance, then the maximum descendant error.
[[nodiscard]] bool CookLodHierarchy(const MeshPrimitive &stPrimitive, const LodCookSettings &stSettings,
									CookedLodHierarchy &out_stHierarchy, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
