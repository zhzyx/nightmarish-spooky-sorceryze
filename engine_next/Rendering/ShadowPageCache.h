/**************************************************************************/
/*  ShadowPageCache.h                                                     */
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
#include "engine_next/include/EngineNext/Rendering/VirtualShadowSettings.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

inline constexpr std::uint32_t SHADOW_PAGE_TEXELS = 128;
inline constexpr std::uint32_t SHADOW_PAGE_BORDER = 2;
inline constexpr std::uint32_t SHADOW_PAGE_PHYSICAL_TEXELS = SHADOW_PAGE_TEXELS + 2 * SHADOW_PAGE_BORDER;
inline constexpr std::uint32_t INVALID_SHADOW_PAGE = UINT32_MAX;

// The depth plane belongs to the rasterized page, not the current cascade.
// A changed scene depth span can therefore retain an unchanged caster page.
struct alignas(16) ShadowPageTableEntry
{
	std::uint32_t nPhysicalPlusOne = 0;
	std::array<std::uint32_t, 3> arrReserved{};
	std::array<float, 4> arrDepthPlane{};
};
static_assert(sizeof(ShadowPageTableEntry) == 32);

struct ShadowPageRender
{
	std::uint32_t nLogical = 0;
	std::uint32_t nPhysical = 0;
	std::array<float, 16> arrViewProjection{};
};

struct ShadowPageStatistics
{
	std::uint32_t nRequested = 0;
	std::uint32_t nResident = 0;
	std::uint32_t nReused = 0;
	std::uint32_t nRendered = 0;
	std::uint32_t nInvalidated = 0;
	std::uint32_t nEvicted = 0;
	std::uint32_t nDeferred = 0;
	std::uint32_t nRejectedFeedback = 0;
};

struct ShadowPageFeedback
{
	ShadowData stProjection;
	std::vector<std::uint32_t> arrCoverage;
};

struct ShadowPagePlan
{
	std::uint64_t nEpoch = 0;
	std::uint64_t nSceneRevision = 0;
	ShadowPageStatistics stStatistics;
	std::vector<ShadowPageTableEntry> arrTable;
	std::vector<ShadowPageRender> arrRender;
};

[[nodiscard]] bool BuildShadowPageProjection(const ShadowCascade &stCascade, std::uint32_t nResolution,
											 std::uint32_t nPageX, std::uint32_t nPageY, std::array<float, 16> &out_arrProjection) noexcept;

// Conservative orthographic page-frustum test. Bounds must already enclose
// GPU world-transform roundoff. Invalid inputs fail open (remain visible).
bool IntersectsShadowPage(const WorldBounds &stBounds, const std::array<float, 16> &arrProjection) noexcept;

// Single owner thread; CPU only. Prepare is transactional. Its plan is valid
// until Commit or Cancel and may be uploaded only to a retired frame slot.
// Commit follows successful queue submission. GPU pool contents are serialized
// on that queue; a failed submission must not resume with an assumed valid pool.
class ShadowPageCache final
{
public:
	[[nodiscard]] bool Initialize(const VirtualShadowSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Prepare(const ShadowData &stProjection, const std::vector<WorldBounds> &arrCasters,
							   const std::vector<std::uint32_t> &arrChangedDraws, const std::vector<ShadowPageFeedback> &arrFeedback,
							   Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Commit() noexcept;
	void Cancel() noexcept;
	const ShadowPagePlan &Plan() const noexcept;
	std::uint32_t LogicalPages() const noexcept;
	std::uint64_t Epoch() const noexcept;

private:
	struct PhysicalPage
	{
		std::uint32_t nLogical = INVALID_SHADOW_PAGE;
		std::uint64_t nLastRequest = 0;
	};
	struct State
	{
		ShadowData stProjection;
		std::vector<WorldBounds> arrCasters;
		std::vector<ShadowPageTableEntry> arrTable;
		std::vector<PhysicalPage> arrPhysical;
		std::uint64_t nEpoch = 0;
		std::uint64_t nSceneRevision = 0;
	};
	VirtualShadowSettings stSettings;
	State stCommitted;
	State stPending;
	ShadowPagePlan stPlan;
	bool bInitialized = false;
	bool bPending = false;
};

} // namespace EngineNext::Rendering
