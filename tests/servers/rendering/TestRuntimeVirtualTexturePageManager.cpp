/**************************************************************************/
/*  TestRuntimeVirtualTexturePageManager.cpp                             */
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

#include "tests/test_macros.h"

TEST_FORCE_LINK(TestRuntimeVirtualTexturePageManager)

#include "servers/rendering/RuntimeVirtualTexturePageManager.h"

namespace TestRVTPageManager
{

static RVTPageManager MakeManager(uint32_t nLog2, uint32_t nPool, uint32_t nResident = 1)
{
	RVTPageManager::Config stCfg;
	stCfg.nLog2Pages = nLog2;
	stCfg.nPoolPagesX = nPool;
	stCfg.nPoolPagesY = nPool;
	stCfg.nResidentLevels = nResident;
	RVTPageManager stM;
	stM.Configure(stCfg);
	return stM;
}

static void RenderAll(RVTPageManager &out_stM, uint32_t nBudget = 1000)
{
	LocalVector<RVTPageManager::PageRender> arrPending;
	out_stM.TakePending(nBudget, arrPending);
	for (const RVTPageManager::PageRender &stP : arrPending)
	{
		out_stM.MarkRendered(stP.stKey);
	}
}

TEST_CASE("[RVTPageManager] Resident top level, unresident pages fall back to ancestor")
{
	RVTPageManager stM = MakeManager(3, 8);
	CHECK(stM.GetLevelCount() == 4);

	stM.BeginFrame();
	stM.RequestPage(3, 0, 0, 0.0f);
	RenderAll(stM);
	CHECK(stM.IsResident(3, 0, 0));

	// Every level-0 texel resolves to the root page.
	RVTPageManager::PageTableEntry stE = stM.Lookup(0, 5, 6);
	CHECK(stE.nValid == 255);
	CHECK(stE.nLevel == 3);

	stM.BeginFrame();
	stM.RequestPage(3, 0, 0, 0.0f);
	stM.RequestPage(1, 1, 1, 1.0f);
	RenderAll(stM);

	// Level 1 page (1,1) covers level 0 pages x,y in [2,3]; others keep the root.
	stE = stM.Lookup(0, 3, 2);
	CHECK(stE.nLevel == 1);
	stE = stM.Lookup(0, 4, 2);
	CHECK(stE.nLevel == 3);
	stE = stM.Lookup(1, 1, 1);
	CHECK(stE.nLevel == 1);
	stE = stM.Lookup(1, 0, 1);
	CHECK(stE.nLevel == 3);
}

TEST_CASE("[RVTPageManager] Coarsest pages are rendered first and budget is respected")
{
	RVTPageManager stM = MakeManager(3, 8);
	stM.BeginFrame();
	stM.RequestPage(0, 1, 1, 0.0f);
	stM.RequestPage(2, 0, 1, 5.0f);
	stM.RequestPage(3, 0, 0, 9.0f);
	LocalVector<RVTPageManager::PageRender> arrPending;
	stM.TakePending(2, arrPending);
	REQUIRE(arrPending.size() == 2);
	CHECK(arrPending[0].stKey.nLevel == 3);
	CHECK(arrPending[1].stKey.nLevel == 2);
}

TEST_CASE("[RVTPageManager] LRU eviction never removes pages requested this frame")
{
	RVTPageManager stM = MakeManager(3, 2); // 4 slots.
	for (uint32_t nI = 0; nI < 4; nI++)
	{
		stM.BeginFrame();
		stM.RequestPage(3, 0, 0, 0.0f);
		stM.RequestPage(0, nI, 0, 1.0f);
		RenderAll(stM, 1000);
	}
	// Root + 3 level 0 pages fit in the pool of four; the oldest one (0,0) was evicted.
	CHECK(stM.GetStats().nResidentPages == 4);
	CHECK(stM.IsResident(3, 0, 0));
	CHECK(!stM.IsResident(0, 0, 0));
	CHECK(stM.IsResident(0, 1, 0));
	CHECK(stM.IsResident(0, 3, 0));
	CHECK(stM.GetStats().nEvictedTotal == 1);
	CHECK(stM.Lookup(0, 0, 0).nLevel == 3); // Evicted page resolves back to the root.

	stM.BeginFrame();
	stM.RequestPage(3, 0, 0, 0.0f);
	stM.RequestPage(0, 5, 5, 1.0f);
	RenderAll(stM);
	CHECK(stM.IsResident(0, 5, 5));
	CHECK(stM.IsResident(3, 0, 0));
	CHECK(!stM.IsResident(0, 1, 0)); // Least recently used, evicted.
	CHECK(stM.IsResident(0, 3, 0));
	CHECK(stM.GetStats().nEvictedTotal == 2);
}

TEST_CASE("[RVTPageManager] Invalidated pages are re-rendered in place")
{
	RVTPageManager stM = MakeManager(2, 4);
	stM.BeginFrame();
	stM.RequestPage(2, 0, 0, 0.0f);
	stM.RequestPage(1, 0, 0, 0.0f);
	RenderAll(stM);

	uint32_t nPx, stPy;
	REQUIRE(stM.GetSlot({ 1, 0, 0 }, nPx, stPy));

	stM.BeginFrame();
	stM.RequestPage(2, 0, 0, 0.0f);
	stM.RequestPage(1, 0, 0, 0.0f);
	LocalVector<RVTPageManager::PageRender> arrPending;
	stM.TakePending(10, arrPending);
	CHECK(arrPending.is_empty());

	stM.InvalidateRect(Rect2(0.0f, 0.0f, 0.1f, 0.1f));
	stM.BeginFrame();
	stM.RequestPage(2, 0, 0, 0.0f);
	stM.RequestPage(1, 0, 0, 0.0f);
	stM.TakePending(10, arrPending);
	REQUIRE(arrPending.size() == 2);
	for (const RVTPageManager::PageRender &stP : arrPending)
	{
		stM.MarkRendered(stP.stKey);
	}
	uint32_t nPx2, stPy2;
	REQUIRE(stM.GetSlot({ 1, 0, 0 }, nPx2, stPy2));
	CHECK(nPx == nPx2);
	CHECK(stPy == stPy2);
}

TEST_CASE("[RVTPageManager] View requests refine near the viewer")
{
	RVTPageManager stM = MakeManager(5, 64, 2); // 32x32 pages at level 0.
	RVTPageManager::View stView;
	stView.vViewer = Vector3(0, 2, 0);
	stView.vSize = Vector3(1024, 64, 1024);
	stView.fPixelPerDistance = 0.002f;
	stView.fTexelSizeLevel0 = 1024.0f / (32 * 128);

	stM.BeginFrame();
	stM.RequestView(stView);
	RenderAll(stM);

	// Texel under the viewer is better than the far corner.
	const uint32_t nNearLevel = stM.Lookup(0, 16, 16).nLevel;
	const uint32_t nFarLevel = stM.Lookup(0, 0, 0).nLevel;
	CHECK(nNearLevel < nFarLevel);
	// Always-resident levels guarantee a valid entry everywhere.
	CHECK(stM.Lookup(0, 31, 31).nValid == 255);
	CHECK(stM.GetStats().nResidentPages <= 64u * 64u);
}

TEST_CASE("[RVTPageManager] Frustum culling skips pages behind the viewer")
{
	RVTPageManager stM = MakeManager(4, 64, 1);
	RVTPageManager::View stView;
	stView.vViewer = Vector3(0, 2, 0);
	stView.vSize = Vector3(1024, 64, 1024);
	stView.fPixelPerDistance = 0.002f;
	stView.fTexelSizeLevel0 = 1024.0f / (16 * 128);
	// A single plane that rejects everything with x > 10 (outward normal +x).
	stView.arrFrustum.push_back(Plane(Vector3(1, 0, 0), 10.0f));

	stM.BeginFrame();
	stM.RequestView(stView);
	RenderAll(stM);
	CHECK(stM.IsResident(0, 7, 8)); // x just left of the viewer.
	CHECK(!stM.IsResident(0, 12, 8));
}

TEST_CASE("[RVTPageManager] Blocked pages free their slot and stay unrequested")
{
	RVTPageManager stM = MakeManager(3, 8);
	stM.BeginFrame();
	stM.RequestPage(3, 0, 0, 0.0f);
	RenderAll(stM);

	stM.BeginFrame();
	stM.RequestPage(1, 1, 1, 1.0f);
	LocalVector<RVTPageManager::PageRender> arrPending;
	stM.TakePending(10, arrPending);
	REQUIRE(arrPending.size() == 1);
	CHECK(!stM.IsResident(1, 1, 1)); // Slot reserved, content not produced yet.

	uint32_t nPx = 0;
	uint32_t nPy = 0;
	REQUIRE(stM.GetSlot({ 1, 1, 1 }, nPx, nPy));
	stM.BlockPage(1, 1, 1);
	CHECK(!stM.GetSlot({ 1, 1, 1 }, nPx, nPy));

	stM.BeginFrame();
	stM.RequestPage(1, 1, 1, 1.0f);
	stM.TakePending(10, arrPending);
	CHECK(arrPending.is_empty());
	CHECK(stM.Lookup(1, 1, 1).nLevel == 3); // Served by the ancestor.
}

TEST_CASE("[RVTPageManager] Height page transitions, apron invalidation and root residency")
{
	RVTPageManager stM;
	RVTPageManager::Config stConfig;
	stConfig.nLog2Pages = 2;
	stConfig.nPoolPagesX = 2;
	stConfig.nPoolPagesY = 2;
	stConfig.nResidentLevels = 1;
	stConfig.bFadeIn = true;
	stM.Configure(stConfig);
	stM.BeginFrame();
	stM.RequestResidentLevels();
	stM.RequestPage(1, 0, 0, 0.f);
	stM.RequestPage(0, 0, 0, 0.f);
	RenderAll(stM);
	CHECK(stM.Lookup(0, 3, 3).nLevel == 2);
	CHECK(stM.Lookup(0, 3, 3).nValid == 255);
	CHECK(stM.Lookup(0, 0, 0).nValid == 1);
	CHECK(stM.Lookup(0, 1, 0).nLevel == 1);
	CHECK(stM.Lookup(0, 1, 0).nValid == 1);
	for (int nI = 0; nI < 8; ++nI)
	{
		stM.BeginFrame();
	}
	CHECK(stM.Lookup(0, 0, 0).nValid == 255);
	CHECK(stM.Lookup(0, 1, 0).nValid == 255);
	stM.InvalidateRect(Rect2(0.251f, 0.125f, 0.001f, 0.001f), 1.f / 16.f);
	CHECK(stM.GetPageStatus(0, 0, 0).bDirty);
	stM.BeginFrame();
	stM.RequestResidentLevels();
	for (uint32_t nX = 0; nX < 4; ++nX)
	{
		stM.RequestPage(0, nX, 3, float(nX));
	}
	RenderAll(stM);
	CHECK(stM.IsResident(2, 0, 0));
	CHECK(stM.IsResident(0, 0, 3));
}

TEST_CASE("[RVTPageManager] Material page fades retain provenance on a live replacement")
{
	RVTPageManager stM;
	RVTPageManager::Config stConfig;
	stConfig.nLog2Pages = 2;
	stConfig.nPoolPagesX = stConfig.nPoolPagesY = 2;
	stConfig.bPrioritizeCoverage = true;
	stConfig.nResidentLevels = 1;
	stM.Configure(stConfig);
	stM.BeginFrame();
	stM.RequestResidentLevels();
	stM.RequestPage(1, 0, 0, 1.0f);
	LocalVector<RVTPageManager::PageRender> arrPending;
	stM.TakePending(4, arrPending);
	REQUIRE(arrPending.size() == 2);
	for (const RVTPageManager::PageRender &stPage : arrPending)
	{
		stM.MarkRendered(stPage.stKey, true);
	}
	CHECK(stM.Lookup(0, 3, 3).nValid == 254);
	CHECK(stM.Lookup(0, 0, 0).nValid == 2);
	for (int nI = 0; nI < 8; nI++)
	{
		stM.BeginFrame();
	}
	CHECK(stM.Lookup(0, 0, 0).nValid == 254);
	stM.InvalidatePage(1, 0, 0);
	stM.MarkRendered({ 1, 0, 0 });
	CHECK(stM.Lookup(0, 0, 0).nValid == 3);
	for (int nI = 0; nI < 8; nI++)
	{
		stM.BeginFrame();
	}
	CHECK(stM.Lookup(0, 0, 0).nValid == 255);
}

TEST_CASE("[RVTPageManager] Moving a terrain window preserves aligned world pages and their physical contents")
{
	RVTPageManager stManager = MakeManager(3, 4);
	const Basis stRotation(Vector3(0, 1, 0), 0.37f);
	const Transform3D stInitial(stRotation * Basis::from_scale(Vector3(16, 10, 8)), Vector3(-64, 0, -32));
	const Transform3D stMoved(stInitial.basis, stInitial.origin + stRotation.xform(Vector3(4, 0, -2)));
	stManager.BeginFrame();
	stManager.RequestResidentLevels();
	stManager.RequestPage(2, 0, 0, 1);
	stManager.RequestPage(1, 1, 1, 1);
	stManager.RequestPage(0, 3, 2, 1);
	stManager.RequestPage(0, 0, 7, 1);
	RenderAll(stManager);
	const RVTPageManager::PageStatus stFine = stManager.GetPageStatus(0, 3, 2);
	const RVTPageManager::PageStatus stParent = stManager.GetPageStatus(1, 1, 1);
	REQUIRE(stFine.bResident);
	REQUIRE(stParent.bResident);
	const uint64_t nInitialEpoch = stManager.GetMappingRevision();

	// An edit at the world-space edge of the old fine page remains dirty in its new slot.
	stManager.InvalidateRect(Rect2(0.501, 0.31, 0.001, 0.001), 1.f / 16.f);
	REQUIRE(stManager.GetPageStatus(0, 3, 2).bDirty);
	stManager.ClearPageTableDirty();
	stManager.MoveWindow(stInitial, stMoved);
	CHECK(stManager.IsPageTableDirty());
	CHECK_FALSE(stManager.IsFeedbackCurrent(nInitialEpoch));
	CHECK(stManager.IsFeedbackCurrent(stManager.GetMappingRevision()));
	const RVTPageManager::PageStatus stMovedFine = stManager.GetPageStatus(0, 1, 4);
	const RVTPageManager::PageStatus stMovedParent = stManager.GetPageStatus(1, 0, 2);
	CHECK(stMovedFine.bDirty);
	CHECK(stMovedFine.nContentSerial == stFine.nContentSerial);
	CHECK(stMovedFine.nPoolX == stFine.nPoolX);
	CHECK(stMovedFine.nPoolY == stFine.nPoolY);
	CHECK(stMovedParent.nContentSerial == stParent.nContentSerial);
	CHECK(stMovedParent.nPoolX == stParent.nPoolX);
	CHECK(stMovedParent.nPoolY == stParent.nPoolY);
	const RVTPageManager::PageTableEntry stFallback = stManager.Lookup(0, 0, 5);
	CHECK(stFallback.nValid > 0);
	CHECK(stFallback.nLevel == 1);
	CHECK(stFallback.nPoolX == stParent.nPoolX);
	CHECK(stFallback.nPoolY == stParent.nPoolY);
	CHECK(stManager.Lookup(0, 7, 0).nValid == 0);
	CHECK(stManager.GetStats().nRetainedOnMove == 2);
	CHECK_FALSE(stManager.IsResident(2, 0, 0));
	CHECK_FALSE(stManager.IsResident(3, 0, 0));
	CHECK_FALSE(stManager.IsResident(0, 0, 7));

	stManager.MoveWindow(stMoved, stInitial);
	CHECK_FALSE(stManager.IsFeedbackCurrent(nInitialEpoch)); // Old readback after an A -> B -> A move.
	CHECK(stManager.GetPageStatus(0, 3, 2).nContentSerial == stFine.nContentSerial);
	CHECK(stManager.Lookup(0, 0, 7).nValid == 0);
}

TEST_CASE("[RVTPageManager] Fractional moves, scale changes and teleports drop incompatible pages")
{
	const Transform3D stOriginal(Basis::from_scale(Vector3(8, 10, 8)), Vector3());
	const Transform3D arrTransforms[] = {
		Transform3D(stOriginal.basis, Vector3(0.25, 0, 0)),
		Transform3D(stOriginal.basis, Vector3(-65536, 0, 32000)),
		Transform3D(Basis::from_scale(Vector3(16, 10, 8)), Vector3()),
	};
	for (const Transform3D &stTarget : arrTransforms)
	{
		RVTPageManager stManager = MakeManager(3, 2);
		stManager.BeginFrame();
		stManager.RequestPage(0, 2, 2, 0);
		RenderAll(stManager);
		stManager.RequestPage(0, 3, 2, 0);
		LocalVector<RVTPageManager::PageRender> arrPending;
		stManager.TakePending(1, arrPending);
		REQUIRE(arrPending.size() == 1);
		stManager.MoveWindow(stOriginal, stTarget);
		CHECK(stManager.GetStats().nResidentPages == 0);
		CHECK(stManager.GetStats().nDiscardedOnMove == 2);
		CHECK(stManager.Lookup(0, 2, 2).nValid == 0);
		CHECK_FALSE(stManager.GetPageStatus(0, 3, 2).bExists);
		stManager.BeginFrame();
		for (uint32_t nX = 0; nX < 4; ++nX)
		{
			stManager.RequestPage(0, nX, 2, 0);
		}
		RenderAll(stManager);
		HashSet<uint32_t> setSlots;
		for (uint32_t nX = 0; nX < 4; ++nX)
		{
			const RVTPageManager::PageStatus stPage = stManager.GetPageStatus(0, nX, 2);
			REQUIRE(stPage.bResident);
			setSlots.insert(stPage.nPoolX + 2 * stPage.nPoolY);
		}
		CHECK(setSlots.size() == 4);
	}
}

TEST_CASE("[RVTPageManager] Moving feedback covers the camera path and trilinear parents in the remapped window")
{
	RVTPageManager stManager = MakeManager(5, 8);
	stManager.BeginFrame();
	// The camera advanced five pages since capture and the window snapped eight pages right.
	stManager.RequestMovingFootprint({ 0, 12, 3 }, Vector2(-3, 0) / 32, Vector2(1, 0) / 32, 0.05f);
	RenderAll(stManager);
	for (uint32_t nX = 9; nX <= 17; ++nX)
	{
		CHECK(stManager.IsResident(0, nX, 3));
		CHECK(stManager.IsResident(1, nX >> 1, 1));
	}
	CHECK_FALSE(stManager.IsResident(0, 8, 3));
	CHECK_FALSE(stManager.IsResident(0, 18, 3));
	CHECK(stManager.GetStats().nRequestedPages == 14);

	// Near the negative window boundary clip the footprint rather than clamping it.
	stManager.BeginFrame();
	stManager.RequestMovingFootprint({ 0, 0, 10 }, Vector2(-0.5f, 0.25f) / 32, Vector2(-1, 0) / 32, 0.05f);
	RenderAll(stManager);
	CHECK(stManager.IsResident(0, 0, 10));
	CHECK(stManager.IsResident(0, 0, 11));
	CHECK_FALSE(stManager.IsResident(0, 31, 10));
	CHECK(stManager.GetStats().nRequestedPages == 3);
}

TEST_CASE("[RVTPageManager] A bounded moving pool favors current coverage and its leading edge")
{
	RVTPageManager stManager;
	RVTPageManager::Config stConfig;
	stConfig.nLog2Pages = 5;
	stConfig.nPoolPagesX = 3;
	stConfig.nPoolPagesY = 2;
	stConfig.nResidentLevels = 1;
	stConfig.bPrioritizeCoverage = true;
	stManager.Configure(stConfig);
	for (int32_t nFrame = 0; nFrame < 12; ++nFrame)
	{
		stManager.BeginFrame();
		stManager.RequestResidentLevels();
		stManager.RequestMovingFootprint({ 0, 0, 0 }, Vector2(nFrame, 0) / 32, Vector2(1, 0) / 32, 0.01f);
		stManager.RequestMovingFootprint({ 0, 0, 5 }, Vector2(nFrame, 0) / 32, Vector2(1, 0) / 32, 1.0f);
		RenderAll(stManager);
		CHECK(stManager.IsResident(0, nFrame, 0));
		CHECK(stManager.IsResident(0, nFrame + 1, 0));
		CHECK(stManager.IsResident(1, nFrame >> 1, 0));
		CHECK_FALSE(stManager.IsResident(0, nFrame, 5));
	}
}

} // namespace TestRVTPageManager
