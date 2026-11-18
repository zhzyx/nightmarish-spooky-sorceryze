/**************************************************************************/
/*  TestShadowPageCache.cpp                                               */
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

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Rendering/ShadowPageCache.h"

#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::BuildShadowPageProjection;
using EngineNext::Rendering::ShadowCascade;
using EngineNext::Rendering::ShadowData;
using EngineNext::Rendering::ShadowPageCache;
using EngineNext::Rendering::ShadowPageFeedback;
using EngineNext::Rendering::ShadowPagePlan;
using EngineNext::Rendering::ValidateVirtualShadowSettings;
using EngineNext::Rendering::VirtualShadowSettings;
using EngineNext::Rendering::WorldBounds;

ShadowData Projection()
{
	ShadowData stResult;
	for (ShadowCascade &stCascade : stResult.arrCascades)
	{
		stCascade.arrViewProjection = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	}
	return stResult;
}

VirtualShadowSettings SmallSettings()
{
	VirtualShadowSettings stSettings;
	stSettings.nResolution = 2048;
	stSettings.nPhysicalPages = 16;
	stSettings.nUpdatesPerFrame = 16;
	return stSettings;
}

ShadowPageFeedback Request(const ShadowData &stProjection, std::uint32_t nFirst, std::uint32_t nCount)
{
	ShadowPageFeedback stFeedback;
	stFeedback.stProjection = stProjection;
	stFeedback.arrCoverage.resize(4 * 16 * 16);
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		stFeedback.arrCoverage[nFirst + nIndex] = nCount - nIndex;
	}
	return stFeedback;
}

WorldBounds Caster(double dX)
{
	return { { dX - 0.01, -0.0725, 0.2 }, { dX + 0.01, -0.0525, 0.4 } };
}

void CheckMapping(const ShadowPagePlan &stPlan, std::uint32_t nLimit)
{
	std::vector<bool> arrUsed(nLimit, false);
	std::uint32_t nResident = 0;
	for (const EngineNext::Rendering::ShadowPageTableEntry &stEntry : stPlan.arrTable)
	{
		if (stEntry.nPhysicalPlusOne != 0)
		{
			ENGINE_NEXT_CHECK(stEntry.nPhysicalPlusOne <= nLimit);
			if (stEntry.nPhysicalPlusOne <= nLimit)
			{
				ENGINE_NEXT_CHECK(!arrUsed[stEntry.nPhysicalPlusOne - 1]);
				arrUsed[stEntry.nPhysicalPlusOne - 1] = true;
			}
			++nResident;
		}
	}
	ENGINE_NEXT_CHECK(nResident == stPlan.stStatistics.nResident);
}

} // namespace

ENGINE_NEXT_TEST("ShadowPageCache static pages are reused and cancellation is transactional")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	const ShadowPageFeedback stFeedback = Request(stProjection, 8, 3);
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 3);
	ENGINE_NEXT_CHECK(stCache.Epoch() == 0);
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, {}, {}, {}, arrDiagnostics));
	stCache.Cancel();
	ENGINE_NEXT_CHECK(stCache.Epoch() == 0);
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Epoch() == 1);
	ENGINE_NEXT_CHECK(!stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 0);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nReused == 3);
	CheckMapping(stCache.Plan(), 16);
}

ENGINE_NEXT_TEST("ShadowPageCache evicts only unrequested least-recent pages")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 0, 16) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 16, 16) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nEvicted == 16);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 16);
	for (std::uint32_t nIndex = 0; nIndex < 16; ++nIndex)
	{
		ENGINE_NEXT_CHECK(stCache.Plan().arrTable[nIndex].nPhysicalPlusOne == 0);
		ENGINE_NEXT_CHECK(stCache.Plan().arrTable[nIndex + 16].nPhysicalPlusOne != 0);
	}
	CheckMapping(stCache.Plan(), 16);
}

ENGINE_NEXT_TEST("ShadowPageCache pinned overflow leaves explicit fallback entries")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 0, 16) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 0, 32) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nEvicted == 0);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nDeferred == 16);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 0);
	CheckMapping(stCache.Plan(), 16);
}

ENGINE_NEXT_TEST("ShadowPageCache update budget is bounded and deterministic")
{
	VirtualShadowSettings stSettings = SmallSettings();
	stSettings.nUpdatesPerFrame = 2;
	ShadowPageCache stFirst;
	ShadowPageCache stSecond;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stFirst.Initialize(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSecond.Initialize(stSettings, arrDiagnostics));
	const ShadowData stProjection = Projection();
	const std::vector<ShadowPageFeedback> arrFeedback{ Request(stProjection, 4, 8) };
	ENGINE_NEXT_CHECK(stFirst.Prepare(stProjection, {}, {}, arrFeedback, arrDiagnostics));
	ENGINE_NEXT_CHECK(stSecond.Prepare(stProjection, {}, {}, arrFeedback, arrDiagnostics));
	ENGINE_NEXT_CHECK(stFirst.Plan().stStatistics.nRendered == 2);
	ENGINE_NEXT_CHECK(stFirst.Plan().stStatistics.nDeferred == 6);
	for (std::size_t nIndex = 0; nIndex < stFirst.Plan().arrRender.size(); ++nIndex)
	{
		ENGINE_NEXT_CHECK(stFirst.Plan().arrRender[nIndex].nLogical == stSecond.Plan().arrRender[nIndex].nLogical);
		ENGINE_NEXT_CHECK(stFirst.Plan().arrRender[nIndex].nPhysical == stSecond.Plan().arrRender[nIndex].nPhysical);
	}
}

ENGINE_NEXT_TEST("ShadowPageCache moving caster invalidates old and new covered regions")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	ShadowPageFeedback stFeedback = Request(stProjection, 0, 1);
	stFeedback.arrCoverage[8 * 16 + 3] = 1;
	stFeedback.arrCoverage[8 * 16 + 12] = 1;
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, { Caster(-0.5625) }, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, { Caster(0.5625) }, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 2);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nReused == 1);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 2);
	ENGINE_NEXT_CHECK(stCache.Plan().nSceneRevision == 2);
}

ENGINE_NEXT_TEST("ShadowPageCache unchanged bounds still invalidate explicit deformation")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	const ShadowPageFeedback stFeedback = Request(stProjection, 8 * 16 + 3, 1);
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, { Caster(-0.5625) }, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, { Caster(-0.5625) }, { 0 }, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 1);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 1);
}

ENGINE_NEXT_TEST("ShadowPageCache depth-only changes preserve the stored page depth transform")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stOriginal = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stOriginal, {}, {}, { Request(stOriginal, 2, 1) }, arrDiagnostics));
	const std::array<float, 4> arrDepth = stCache.Plan().arrTable[2].arrDepthPlane;
	ENGINE_NEXT_CHECK(stCache.Commit());
	ShadowData stChanged = stOriginal;
	for (ShadowCascade &stCascade : stChanged.arrCascades)
	{
		stCascade.arrViewProjection[10] = 0.5;
		stCascade.arrViewProjection[14] = 0.1;
	}
	ENGINE_NEXT_CHECK(stCache.Prepare(stChanged, {}, {}, { Request(stOriginal, 2, 1) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 0);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nReused == 1);
	ENGINE_NEXT_CHECK(stCache.Plan().arrTable[2].arrDepthPlane == arrDepth);
	ENGINE_NEXT_CHECK(stCache.Plan().nSceneRevision == 2);
}

ENGINE_NEXT_TEST("ShadowPageCache camera translation remaps feedback and invalidates projection")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stOriginal = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	const ShadowPageFeedback stFeedback = Request(stOriginal, 8 * 16 + 8, 1);
	ENGINE_NEXT_CHECK(stCache.Prepare(stOriginal, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ShadowData stChanged = stOriginal;
	for (ShadowCascade &stCascade : stChanged.arrCascades)
	{
		stCascade.arrViewProjection[12] = 0.25;
	}
	ENGINE_NEXT_CHECK(stCache.Prepare(stChanged, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 1);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRejectedFeedback == 0);
	ENGINE_NEXT_CHECK(stCache.Plan().arrTable[8 * 16 + 10].nPhysicalPlusOne != 0);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRequested <= 9);
}

ENGINE_NEXT_TEST("ShadowPageCache changed light rejects stale basis and zeroes mappings")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stOriginal = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	const ShadowPageFeedback stFeedback = Request(stOriginal, 8, 2);
	ENGINE_NEXT_CHECK(stCache.Prepare(stOriginal, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ShadowData stChanged = stOriginal;
	for (ShadowCascade &stCascade : stChanged.arrCascades)
	{
		stCascade.arrViewProjection = { 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	}
	ENGINE_NEXT_CHECK(stCache.Prepare(stChanged, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 2);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRejectedFeedback == 4);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nResident == 0);
}

ENGINE_NEXT_TEST("ShadowPageCache invalid input leaves committed state reusable")
{
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 4, 1) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Commit());
	ShadowData stInvalid = stProjection;
	stInvalid.arrCascades[0].arrViewProjection[0] = std::numeric_limits<double>::quiet_NaN();
	ENGINE_NEXT_CHECK(!stCache.Prepare(stInvalid, {}, {}, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, { Caster(0) }, { 0, 0 }, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, {}, { 0 }, {}, arrDiagnostics));
	ShadowPageFeedback stWrong = Request(stProjection, 0, 1);
	stWrong.arrCoverage.pop_back();
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, {}, {}, { stWrong }, arrDiagnostics));
	WorldBounds stBad = Caster(0);
	stBad.arrMinimum[0] = 1;
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, { stBad }, {}, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Epoch() == 1);
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { Request(stProjection, 4, 1) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nReused == 1);
}

ENGINE_NEXT_TEST("ShadowPageCache page crop includes borders and reversed axes")
{
	const ShadowData stProjection = Projection();
	std::array<float, 16> arrMatrix{};
	ENGINE_NEXT_CHECK(BuildShadowPageProjection(stProjection.arrCascades[0], 2048, 3, 8, arrMatrix));
	const double dX = -0.5625;
	const double dY = -0.0625;
	ENGINE_NEXT_CHECK(std::abs(arrMatrix[0] * dX + arrMatrix[12]) < 1.0e-6);
	ENGINE_NEXT_CHECK(std::abs(arrMatrix[5] * dY + arrMatrix[13]) < 1.0e-6);
	ENGINE_NEXT_CHECK(std::abs(arrMatrix[0] * (dX - 0.0625) + arrMatrix[12] + 128.0 / 132.0) < 1.0e-6);
	ShadowCascade stReversed = stProjection.arrCascades[0];
	stReversed.arrViewProjection[0] = -1;
	stReversed.arrViewProjection[5] = -1;
	ENGINE_NEXT_CHECK(BuildShadowPageProjection(stReversed, 2048, 3, 8, arrMatrix));
	ENGINE_NEXT_CHECK(std::abs(arrMatrix[0] * -dX + arrMatrix[12]) < 1.0e-6);
	ENGINE_NEXT_CHECK(std::abs(arrMatrix[5] * -dY + arrMatrix[13]) < 1.0e-6);
	const std::array<float, 16> arrBefore = arrMatrix;
	ENGINE_NEXT_CHECK(!BuildShadowPageProjection(stReversed, 2048, 16, 0, arrMatrix));
	ENGINE_NEXT_CHECK(arrMatrix == arrBefore);
}

ENGINE_NEXT_TEST("ShadowPageCache validates payload bounds and rejects degenerate projections")
{
	Diagnostics arrDiagnostics;
	VirtualShadowSettings stSettings = SmallSettings();
	ENGINE_NEXT_CHECK(ValidateVirtualShadowSettings(stSettings, arrDiagnostics));
	stSettings.nPhysicalPages = 2048;
	stSettings.nMemoryBudget = 8ULL * 1024 * 1024;
	ENGINE_NEXT_CHECK(!ValidateVirtualShadowSettings(stSettings, arrDiagnostics));
	stSettings = SmallSettings();
	stSettings.nResolution = 3000;
	ENGINE_NEXT_CHECK(!ValidateVirtualShadowSettings(stSettings, arrDiagnostics));
	ShadowPageCache stCache;
	ENGINE_NEXT_CHECK(stCache.Initialize(SmallSettings(), arrDiagnostics));
	ShadowData stProjection = Projection();
	stProjection.arrCascades[0].arrViewProjection[0] = 0;
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, {}, {}, {}, arrDiagnostics));
	stProjection = Projection();
	stProjection.arrCascades[0].arrViewProjection[4] = 1;
	ENGINE_NEXT_CHECK(!stCache.Prepare(stProjection, {}, {}, {}, arrDiagnostics));
}

ENGINE_NEXT_TEST("ShadowPageCache uncached reference rerenders the same physical mappings")
{
	VirtualShadowSettings stSettings = SmallSettings();
	stSettings.bCache = false;
	ShadowPageCache stCache;
	Diagnostics arrDiagnostics;
	const ShadowData stProjection = Projection();
	const ShadowPageFeedback stFeedback = Request(stProjection, 8, 4);
	ENGINE_NEXT_CHECK(stCache.Initialize(stSettings, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { stFeedback }, arrDiagnostics));
	const ShadowPagePlan stFirst = stCache.Plan();
	ENGINE_NEXT_CHECK(stCache.Commit());
	ENGINE_NEXT_CHECK(stCache.Prepare(stProjection, {}, {}, { stFeedback }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nInvalidated == 4);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nRendered == 4);
	ENGINE_NEXT_CHECK(stCache.Plan().stStatistics.nReused == 0);
	for (std::uint32_t nPage = 8; nPage < 12; ++nPage)
	{
		ENGINE_NEXT_CHECK(stCache.Plan().arrTable[nPage].nPhysicalPlusOne == stFirst.arrTable[nPage].nPhysicalPlusOne);
	}
}

ENGINE_NEXT_TEST("ShadowPageCache frustum rejection retains border and cancellation uncertainty")
{
	using EngineNext::Rendering::IntersectsShadowPage;
	std::array<float, 16> arrProjection{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	ENGINE_NEXT_CHECK(!IntersectsShadowPage({ { 2, -0.5, 0.2 }, { 3, 0.5, 0.8 } }, arrProjection));
	ENGINE_NEXT_CHECK(IntersectsShadowPage({ { 0.99, -0.5, 0.2 }, { 1.1, 0.5, 0.8 } }, arrProjection));
	arrProjection[0] = -1;
	ENGINE_NEXT_CHECK(IntersectsShadowPage({ { -1.1, -0.5, 0.2 }, { -0.99, 0.5, 0.8 } }, arrProjection));
	arrProjection[0] = 1;
	arrProjection[12] = -100000000;
	ENGINE_NEXT_CHECK(IntersectsShadowPage({ { 100000004, -0.5, 0.2 }, { 100000005, 0.5, 0.8 } }, arrProjection));
	arrProjection[0] = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK(IntersectsShadowPage({ { 2, -0.5, 0.2 }, { 3, 0.5, 0.8 } }, arrProjection));
}
