/**************************************************************************/
/*  PagedGeometry.h                                                       */
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
#include "engine_next/Rendering/Cook/GpuPagedPackage.h"
#include "engine_next/include/EngineNext/Rendering/GeometrySettings.h"
#include <array>
#include <cstdint>
#include <string>
#include <vector>
namespace EngineNext::Rendering
{
struct PagedDrawSelection
{
	std::uint32_t nTree = UINT32_MAX;
	LodSelection stCut;
};
struct PagedFrameSelection
{
	std::vector<PagedDrawSelection> arrDraws;
	std::vector<std::uint32_t> arrRequestedPages;
	bool bRootsReady = false;
};
// Derived data only: bounded to 64 MiB, including entry storage. Source/index
// identity and exact world-matrix bits determine reuse; camera/cut state does
// not. The owner serializes use. Failure may populate derived cache entries but
// never publishes a partial frame selection.
class PagedWorldCache
{
public:
	[[nodiscard]] std::uint64_t CachedBytes() const noexcept;
	[[nodiscard]] std::uint64_t Hits() const noexcept;
	[[nodiscard]] std::uint64_t Misses() const noexcept;

private:
	struct Entry
	{
		std::uint32_t nTree = UINT32_MAX;
		std::array<float, 16> arrWorld{};
		std::vector<LodNode> arrNodes;
	};
	std::string strIdentity;
	std::vector<Entry> arrEntries;
	std::uint64_t nBytes = 0;
	std::uint64_t nHits = 0;
	std::uint64_t nMisses = 0;
	friend bool
	BuildPagedFrameSelection(const GpuPageIndex &, const RenderScene &,
							 const std::vector<std::array<float, 16>> &,
							 const std::vector<std::uint8_t> &, const LodView &,
							 const GeometrySettings &,
							 const PagedFrameSelection &, PagedFrameSelection &,
							 Assets::Diagnostics &, PagedWorldCache *);
};
// The matrix is the exact binary32 matrix used for rasterization. Conservative
// transformed bounds include the error of its four float multiply/add terms.
[[nodiscard]] bool TransformLodTree(const GpuLodTree &stTree, const std::array<float, 16> &arrWorld,
									std::vector<LodNode> &out_arrNodes, Assets::Diagnostics &out_arrDiagnostics);
// The caller owns source validation and the residency snapshot. Only complete
// cuts backed by resident pages are returned. Missing roots request their pages
// and keep the conventional source draw path. Previous cuts are immutable and
// become current only after successful queue submission.
[[nodiscard]] bool BuildPagedFrameSelection(const GpuPageIndex &stIndex, const RenderScene &stSource,
											const std::vector<std::array<float, 16>> &arrWorlds,
											const std::vector<std::uint8_t> &arrResident, const LodView &stView,
											const GeometrySettings &stSettings, const PagedFrameSelection &stPrevious,
											PagedFrameSelection &out_stSelection, Assets::Diagnostics &out_arrDiagnostics, PagedWorldCache *pCache = nullptr);
} // namespace EngineNext::Rendering
