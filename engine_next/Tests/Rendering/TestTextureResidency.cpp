/**************************************************************************/
/*  TestTextureResidency.cpp                                                 */
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
#include "engine_next/include/EngineNext/Rendering/TextureResidency.h"

#include <limits>
#include <map>
#include <set>
#include <vector>

namespace
{
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::EstimateTextureMip;
using EngineNext::Rendering::TextureLoadState;
using EngineNext::Rendering::TextureLoadTicket;
using EngineNext::Rendering::TextureMipDemand;
using EngineNext::Rendering::TextureResidency;
using EngineNext::Rendering::TextureResidencyConfig;
using EngineNext::Rendering::TextureResidencyDescription;
using EngineNext::Rendering::TextureResidencyStatus;
using EngineNext::Rendering::TextureResidentHandle;
using EngineNext::Rendering::TextureResourceRelease;
using EngineNext::Rendering::TextureScheduleResult;

TextureResidencyDescription Description(std::uint64_t nId)
{
	return { nId, { { 1024, 256, 180 }, { 512, 128, 96 }, { 128, 64, 16 } } };
}

TextureResidencyConfig Config(std::uint64_t nBudget = 4096)
{
	TextureResidencyConfig stConfig;
	stConfig.nGpuBudget = nBudget;
	stConfig.nUploadBudget = 1024;
	stConfig.nMaximumPending = 4;
	stConfig.nMaximumVersions = 16;
	return stConfig;
}

struct Fixture
{
	TextureResidency stCache;
	Diagnostics arrDiagnostics;
	std::uint64_t nToken = 0;
	std::uint64_t nCopyFence = 0;
	std::vector<TextureResourceRelease> arrReleased;

	explicit Fixture(std::uint64_t nBudget = 4096)
	{
		ENGINE_NEXT_CHECK(stCache.Initialize(Config(nBudget), { Description(1) }, arrDiagnostics));
	}

	TextureLoadTicket Begin(std::uint64_t nTick = 0)
	{
		TextureLoadTicket stTicket;
		TextureScheduleResult eResult = TextureScheduleResult::NoWork;
		ENGINE_NEXT_CHECK(stCache.BeginNextLoad(nTick, eResult, stTicket, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::Started);
		return stTicket;
	}

	void Install(TextureLoadTicket stTicket, std::uint64_t nTick = 0, std::uint64_t nRender = 0)
	{
		ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, true, nTick, arrDiagnostics));
		ENGINE_NEXT_CHECK(stCache.SubmitUpload(stTicket, ++nToken, ++nCopyFence, arrDiagnostics));
		ENGINE_NEXT_CHECK(stCache.AdvanceFences(nCopyFence, nRender, nTick, arrReleased, arrDiagnostics));
	}
};
} // namespace

ENGINE_NEXT_TEST("Texture mip demand follows coverage UV scale and bounded bias")
{
	std::uint32_t nMip = 99;
	ENGINE_NEXT_CHECK(EstimateTextureMip(1024, 1024, 1024, 1024, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 0U);
	ENGINE_NEXT_CHECK(EstimateTextureMip(1024, 512, 128, 128, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 3U);
	ENGINE_NEXT_CHECK(EstimateTextureMip(1024, 512, 128, 128, -2, -1, 0, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 4U);
	ENGINE_NEXT_CHECK(EstimateTextureMip(1024, 512, 128, 128, 1, 1, -1, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 2U);
	ENGINE_NEXT_CHECK(EstimateTextureMip(300, 100, 0, 128, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 8U);
	ENGINE_NEXT_CHECK(EstimateTextureMip(1, 1, 1, 1, 1, 1, 16, nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 0U);
	nMip = 99;
	ENGINE_NEXT_CHECK(!EstimateTextureMip(0, 512, 1, 1, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK(!EstimateTextureMip(8193, 512, 1, 1, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK(!EstimateTextureMip(16, 16, -1, 1, 1, 1, 0, nMip));
	ENGINE_NEXT_CHECK(!EstimateTextureMip(16, 16, 1, 1, 1, 1, std::numeric_limits<double>::quiet_NaN(), nMip));
	ENGINE_NEXT_CHECK_EQ(nMip, 99U);
}

ENGINE_NEXT_TEST("Texture allocation catalogs reject invalid budgets and remain reusable after failure")
{
	TextureResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stCache.Initialize(Config(127), { Description(1) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Initialize(Config(), { Description(1), Description(1) }, arrDiagnostics));
	TextureResidencyDescription stBad = Description(1);
	stBad.arrMips[1].nGpuBytes = 2048;
	ENGINE_NEXT_CHECK(!stCache.Initialize(Config(), { stBad }, arrDiagnostics));
	stBad = Description(1);
	stBad.arrMips[0].nUploadBytes = 0;
	ENGINE_NEXT_CHECK(!stCache.Initialize(Config(), { stBad }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Initialize(Config(), { Description(1) }, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nGpuReservedBytes, 128U);
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nResidentBytes, 0U);
	ENGINE_NEXT_CHECK(!stCache.Initialize(Config(), { Description(2) }, arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture fallback becomes available only after copy retirement")
{
	Fixture stFixture;
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 5 } }, 1, stFixture.arrDiagnostics));
	const TextureLoadTicket stTicket = stFixture.Begin(1);
	ENGINE_NEXT_CHECK_EQ(stTicket.nFirstMip, 2U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nPendingGpuBytes, 128U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 128U);
	TextureResidentHandle stHandle;
	ENGINE_NEXT_CHECK(!stFixture.stCache.GetResident(1, stHandle));
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 1, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SubmitUpload(stTicket, 1, 2, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(1, 0, 1, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.GetResident(1, stHandle));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 64U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(2, 0, 2, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stHandle));
	ENGINE_NEXT_CHECK_EQ(stHandle.nFirstMip, 2U);
	ENGINE_NEXT_CHECK_EQ(stHandle.nResourceToken, 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 0U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nResidentBytes, 128U);
}

ENGINE_NEXT_TEST("Texture downshift retains submitted old allocation until its render fence")
{
	Fixture stFixture(1152);
	stFixture.Install(stFixture.Begin());
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 1 } }, 0, stFixture.arrDiagnostics));
	stFixture.Install(stFixture.Begin());
	TextureResidentHandle stFine;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stFine));
	ENGINE_NEXT_CHECK_EQ(stFine.nFirstMip, 0U);
	ENGINE_NEXT_CHECK(stFixture.stCache.MarkUsed(stFine, 20, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 1, 1 } }, 1, stFixture.arrDiagnostics));
	TextureResidentHandle stFallback;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stFallback));
	ENGINE_NEXT_CHECK_EQ(stFallback.nFirstMip, 2U);
	ENGINE_NEXT_CHECK(!stFixture.stCache.MarkUsed(stFine, 21, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nRetiredBytes, 1024U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 1152U);
	TextureLoadTicket stTicket;
	TextureScheduleResult eResult;
	ENGINE_NEXT_CHECK(stFixture.stCache.BeginNextLoad(1, eResult, stTicket, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::BudgetBlocked);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(2, 19, 1, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.arrReleased.empty());
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(2, 20, 1, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased[0].nResourceToken, stFine.nResourceToken);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 128U);
	stFixture.Install(stFixture.Begin(1), 1, 20);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nResidentBytes, 640U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(3, 20, 2, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.arrReleased.empty());
}

ENGINE_NEXT_TEST("Texture IO cancellation retains reservations until the worker returns")
{
	Fixture stFixture;
	const TextureLoadTicket stOld = stFixture.Begin();
	ENGINE_NEXT_CHECK(stFixture.stCache.Cancel(stOld, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 64U);
	ENGINE_NEXT_CHECK(!stFixture.stCache.ReleaseAll(0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	TextureLoadTicket stOther;
	TextureScheduleResult eResult;
	ENGINE_NEXT_CHECK(stFixture.stCache.BeginNextLoad(0, eResult, stOther, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::NoWork);
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stOld, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 0U);
	const TextureLoadTicket stNew = stFixture.Begin();
	ENGINE_NEXT_CHECK(stNew.nGeneration > stOld.nGeneration);
	ENGINE_NEXT_CHECK(!stFixture.stCache.FinishLoad(stOld, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stNew, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.Cancel(stNew, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nTrackedVersions, 0U);
}

ENGINE_NEXT_TEST("Texture submitted cancellation waits for its copy fence and releases exactly once")
{
	Fixture stFixture;
	TextureLoadTicket stTicket = stFixture.Begin();
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SubmitUpload(stTicket, 1, 3, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.Cancel(stTicket, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(2, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.arrReleased.empty());
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 64U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(3, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased[0].nResourceToken, 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nTrackedVersions, 0U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 128U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(3, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.arrReleased.empty());
}

ENGINE_NEXT_TEST("Texture batched uploads share one copy fence without allowing duplicate tickets")
{
	TextureResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize(Config(), { Description(2), Description(1) }, arrDiagnostics));
	TextureScheduleResult eResult;
	TextureLoadTicket stFirst;
	TextureLoadTicket stSecond;
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFirst.nTextureId, 1U);
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSecond.nTextureId, 2U);
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stFirst, true, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stSecond, true, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stFirst, 1, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stSecond, 2, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.SubmitUpload(stFirst, 3, 2, arrDiagnostics));
	std::vector<TextureResourceRelease> arrReleased;
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 0, arrReleased, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nResidentBytes, 256U);
}

ENGINE_NEXT_TEST("Texture demand coalesces priority and rejects invalid snapshots transactionally")
{
	TextureResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize(Config(), { Description(1), Description(2) }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SetDemand({ { 1, 1, 1 }, { 1, 0, 10 }, { 2, 0, 5 } }, 2, arrDiagnostics));
	TextureResidencyStatus stStatus;
	ENGINE_NEXT_CHECK(stCache.GetStatus(1, stStatus));
	ENGINE_NEXT_CHECK_EQ(stStatus.nWantedFirstMip, 0U);
	ENGINE_NEXT_CHECK(!stCache.SetDemand({ { 1, 2, 1 }, { 3, 0, 1 } }, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.GetStatus(1, stStatus));
	ENGINE_NEXT_CHECK_EQ(stStatus.nWantedFirstMip, 0U);
	ENGINE_NEXT_CHECK(!stCache.SetDemand({ { 1, 9, 1 } }, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.SetDemand({ { 1, 0, std::numeric_limits<double>::infinity() } }, 3, arrDiagnostics));
	TextureScheduleResult eResult;
	TextureLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(2, eResult, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stTicket.nTextureId, 1U);
}

ENGINE_NEXT_TEST("Texture fence sentinels backwards values and resource token reuse are rejected")
{
	Fixture stFixture;
	TextureLoadTicket stTicket = stFixture.Begin();
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.SubmitUpload(stTicket, 0, 1, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.SubmitUpload(stTicket, UINT64_MAX, 1, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.SubmitUpload(stTicket, 1, UINT64_MAX, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SubmitUpload(stTicket, 1, 1, stFixture.arrDiagnostics));
	stFixture.arrReleased = { { 99, 99 } };
	ENGINE_NEXT_CHECK(!stFixture.stCache.AdvanceFences(UINT64_MAX, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.AdvanceFences(1, UINT64_MAX, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased[0].nResourceToken, 99U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(1, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	TextureResidentHandle stHandle;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stHandle));
	ENGINE_NEXT_CHECK(!stFixture.stCache.MarkUsed(stHandle, UINT64_MAX, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.MarkUsed(stHandle, 5, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.MarkUsed(stHandle, 4, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.ReleaseAll(1, 4, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.ReleaseAll(1, 5, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 1U);
}

ENGINE_NEXT_TEST("Texture retry and generation cancellation remain independent of newer demand")
{
	Fixture stFixture;
	TextureLoadTicket stTicket = stFixture.Begin(1);
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, false, 1, stFixture.arrDiagnostics));
	TextureScheduleResult eResult;
	ENGINE_NEXT_CHECK(stFixture.stCache.BeginNextLoad(2, eResult, stTicket, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::NoWork);
	stFixture.Install(stFixture.Begin(3), 3);
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 1 } }, 3, stFixture.arrDiagnostics));
	stTicket = stFixture.Begin(3);
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({}, 4, stFixture.arrDiagnostics));
	TextureResidencyStatus stStatus;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetStatus(1, stStatus));
	ENGINE_NEXT_CHECK(stStatus.bCancellationRequested);
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 1 } }, 4, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 4, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nPendingCount, 0U);
	const TextureLoadTicket stNext = stFixture.Begin(4);
	ENGINE_NEXT_CHECK(stNext.nGeneration > stTicket.nGeneration);
	ENGINE_NEXT_CHECK(!stFixture.stCache.Cancel(stTicket, 4, stFixture.arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture staging and version budgets include cancelled outstanding workers")
{
	TextureResidency stCache;
	TextureResidencyConfig stConfig = Config();
	stConfig.nUploadBudget = 64;
	stConfig.nMaximumVersions = 2;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize(stConfig, { Description(1), Description(2) }, arrDiagnostics));
	TextureScheduleResult eResult;
	TextureLoadTicket stFirst;
	TextureLoadTicket stSecond;
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Cancel(stFirst, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::BudgetBlocked);
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stFirst, false, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::Started);
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nPeakUploadReservedBytes, 64U);
}

ENGINE_NEXT_TEST("Texture finer replacement keeps the old submitted version alive")
{
	Fixture stFixture(2048);
	stFixture.Install(stFixture.Begin());
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 1, 1 } }, 0, stFixture.arrDiagnostics));
	stFixture.Install(stFixture.Begin());
	TextureResidentHandle stOld;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stOld));
	ENGINE_NEXT_CHECK(stFixture.stCache.MarkUsed(stOld, 10, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 1 } }, 0, stFixture.arrDiagnostics));
	const TextureLoadTicket stNew = stFixture.Begin();
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 1664U);
	stFixture.Install(stNew);
	ENGINE_NEXT_CHECK(stFixture.arrReleased.empty());
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nRetiredBytes, 512U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nResidentBytes, 1152U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(3, 10, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased[0].nResourceToken, stOld.nResourceToken);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 1152U);
	ENGINE_NEXT_CHECK(stFixture.stCache.ReleaseAll(3, 10, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 0U);
}

ENGINE_NEXT_TEST("Texture cancelled dynamic upload releases its allocation only after copy retirement")
{
	Fixture stFixture(1152);
	stFixture.Install(stFixture.Begin());
	ENGINE_NEXT_CHECK(stFixture.stCache.SetDemand({ { 1, 0, 1 } }, 0, stFixture.arrDiagnostics));
	TextureLoadTicket stTicket = stFixture.Begin();
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nIoReservedBytes, 180U);
	ENGINE_NEXT_CHECK(stFixture.stCache.SubmitUpload(stTicket, 2, 3, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nIoReservedBytes, 0U);
	ENGINE_NEXT_CHECK(stFixture.stCache.Cancel(stTicket, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(2, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 1152U);
	ENGINE_NEXT_CHECK(stFixture.stCache.AdvanceFences(3, 0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.arrReleased.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 128U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 0U);
	TextureResidentHandle stResident;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetResident(1, stResident));
	ENGINE_NEXT_CHECK_EQ(stResident.nFirstMip, 2U);
	stTicket = stFixture.Begin();
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.SubmitUpload(stTicket, 2, 4, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.SubmitUpload(stTicket, 3, 2, stFixture.arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture IO budget is distinct from GPU and upload allocations")
{
	TextureResidency stCache;
	TextureResidencyConfig stConfig = Config();
	stConfig.nIoBudget = 16;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize(stConfig, { Description(1), Description(2) }, arrDiagnostics));
	TextureScheduleResult eResult;
	TextureLoadTicket stFirst;
	TextureLoadTicket stSecond;
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nIoReservedBytes, 16U);
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::BudgetBlocked);
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stFirst, true, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nIoReservedBytes, 16U);
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stFirst, 1, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nIoReservedBytes, 0U);
	ENGINE_NEXT_CHECK(stCache.BeginNextLoad(0, eResult, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::Started);
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nUploadReservedBytes, 128U);
}

ENGINE_NEXT_TEST("Texture retry overflow does not wrap into an immediate retry")
{
	Fixture stFixture;
	const TextureLoadTicket stTicket = stFixture.Begin(UINT64_MAX - 1);
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, false, UINT64_MAX - 1, stFixture.arrDiagnostics));
	TextureResidencyStatus stStatus;
	ENGINE_NEXT_CHECK(stFixture.stCache.GetStatus(1, stStatus));
	ENGINE_NEXT_CHECK_EQ(stStatus.nRetryAfterTick, UINT64_MAX);
	TextureLoadTicket stNext;
	TextureScheduleResult eResult;
	ENGINE_NEXT_CHECK(stFixture.stCache.BeginNextLoad(UINT64_MAX, eResult, stNext, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, TextureScheduleResult::NoWork);
	ENGINE_NEXT_CHECK(!stFixture.stCache.SetDemand({}, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.ReleaseAll(0, 0, stFixture.arrReleased, stFixture.arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture snapshot failure leaves caller output and budget unchanged")
{
	Fixture stFixture;
	TextureResidencyStatus stStatus;
	stStatus.nWantedFirstMip = 99;
	ENGINE_NEXT_CHECK(!stFixture.stCache.GetStatus(999, stStatus));
	ENGINE_NEXT_CHECK_EQ(stStatus.nWantedFirstMip, 99U);
	TextureResidentHandle stHandle;
	stHandle.nResourceToken = 99;
	ENGINE_NEXT_CHECK(!stFixture.stCache.GetResident(1, stHandle));
	ENGINE_NEXT_CHECK_EQ(stHandle.nResourceToken, 99U);
	ENGINE_NEXT_CHECK(!stFixture.stCache.SetDemand({ { 1, 0, -1 } }, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nGpuReservedBytes, 128U);
}

ENGINE_NEXT_TEST("Texture simulated asynchronous lifetime never releases a live copy or draw")
{
	TextureResidency stCache;
	TextureResidencyConfig stConfig = Config(2048);
	stConfig.nMaximumVersions = 5;
	stConfig.nIoBudget = 256;
	stConfig.nUploadBudget = 512;
	Diagnostics arrDiagnostics;
	const TextureResidencyDescription stDescription = Description(1);
	ENGINE_NEXT_CHECK(stCache.Initialize(stConfig, { stDescription }, arrDiagnostics));
	std::uint32_t nRandom = 0x1849U;
	const auto fnRandom = [&nRandom]()
	{
		nRandom = nRandom * 1664525U + 1013904223U;
		return nRandom;
	};
	std::uint64_t nCopyIssued = 0;
	std::uint64_t nRenderIssued = 0;
	std::uint64_t nCopyDone = 0;
	std::uint64_t nRenderDone = 0;
	std::uint64_t nToken = 0;
	std::map<std::uint64_t, std::uint64_t> mapCopies;
	std::map<std::uint64_t, std::uint64_t> mapDraws;
	std::map<std::uint64_t, std::uint64_t> mapBytes;
	std::set<std::uint64_t> setReleased;
	std::vector<TextureResourceRelease> arrReleased;
	const auto fnCheckRelease = [&mapCopies, &mapDraws, &mapBytes, &setReleased](const std::vector<TextureResourceRelease> &arrValues, std::uint64_t nCopy, std::uint64_t nRender)
	{
		for (const TextureResourceRelease &stRelease : arrValues)
		{
			ENGINE_NEXT_CHECK(mapCopies.count(stRelease.nResourceToken) == 1);
			ENGINE_NEXT_CHECK(mapCopies.at(stRelease.nResourceToken) <= nCopy);
			ENGINE_NEXT_CHECK(mapDraws[stRelease.nResourceToken] <= nRender);
			ENGINE_NEXT_CHECK_EQ(stRelease.nGpuBytes, mapBytes.at(stRelease.nResourceToken));
			ENGINE_NEXT_CHECK(setReleased.insert(stRelease.nResourceToken).second);
		}
	};
	for (std::uint64_t nTick = 1; nTick <= 1000; ++nTick)
	{
		ENGINE_NEXT_CHECK(stCache.SetDemand({ { 1, fnRandom() % 3, 1 } }, nTick, arrDiagnostics));
		TextureResidencyStatus stStatus;
		ENGINE_NEXT_CHECK(stCache.GetStatus(1, stStatus));
		if (stStatus.eLoadState == TextureLoadState::Loading)
		{
			if (fnRandom() % 7 == 0)
			{
				ENGINE_NEXT_CHECK(stCache.Cancel(stStatus.stPending, nTick, arrDiagnostics));
			}
			if (fnRandom() % 3 != 0)
			{
				ENGINE_NEXT_CHECK(stCache.FinishLoad(stStatus.stPending, fnRandom() % 11 != 0, nTick, arrDiagnostics));
			}
		}
		ENGINE_NEXT_CHECK(stCache.GetStatus(1, stStatus));
		if (stStatus.eLoadState == TextureLoadState::UploadReady)
		{
			if (fnRandom() % 7 == 0)
			{
				ENGINE_NEXT_CHECK(stCache.Cancel(stStatus.stPending, nTick, arrDiagnostics));
			}
			else
			{
				ENGINE_NEXT_CHECK(stCache.SubmitUpload(stStatus.stPending, ++nToken, ++nCopyIssued, arrDiagnostics));
				mapCopies[nToken] = nCopyIssued;
				mapBytes[nToken] = stDescription.arrMips[stStatus.stPending.nFirstMip].nGpuBytes;
			}
		}
		if (fnRandom() % 3 == 0)
		{
			nCopyDone = nCopyIssued;
		}
		if (fnRandom() % 5 == 0)
		{
			nRenderDone = nRenderIssued;
		}
		ENGINE_NEXT_CHECK(stCache.AdvanceFences(nCopyDone, nRenderDone, nTick, arrReleased, arrDiagnostics));
		fnCheckRelease(arrReleased, nCopyDone, nRenderDone);
		TextureResidentHandle stResident;
		if (stCache.GetResident(1, stResident))
		{
			ENGINE_NEXT_CHECK(mapCopies.count(stResident.nResourceToken) == 1);
			ENGINE_NEXT_CHECK(setReleased.count(stResident.nResourceToken) == 0);
			ENGINE_NEXT_CHECK(stCache.MarkUsed(stResident, ++nRenderIssued, arrDiagnostics));
			mapDraws[stResident.nResourceToken] = nRenderIssued;
		}
		TextureScheduleResult eResult;
		TextureLoadTicket stNext;
		ENGINE_NEXT_CHECK(stCache.BeginNextLoad(nTick, eResult, stNext, arrDiagnostics));
		const EngineNext::Rendering::TextureResidencyTelemetry &stTelemetry = stCache.Telemetry();
		ENGINE_NEXT_CHECK(stTelemetry.nGpuReservedBytes <= stConfig.nGpuBudget);
		ENGINE_NEXT_CHECK(stTelemetry.nIoReservedBytes <= stConfig.nIoBudget);
		ENGINE_NEXT_CHECK(stTelemetry.nUploadReservedBytes <= stConfig.nUploadBudget);
		ENGINE_NEXT_CHECK(stTelemetry.nTrackedVersions <= stConfig.nMaximumVersions);
		ENGINE_NEXT_CHECK(stTelemetry.nResidentBytes + stTelemetry.nRetiredBytes + stTelemetry.nPendingGpuBytes <= stTelemetry.nGpuReservedBytes);
	}
	TextureResidencyStatus stStatus;
	ENGINE_NEXT_CHECK(stCache.GetStatus(1, stStatus));
	if (stStatus.stPending.nGeneration != 0)
	{
		ENGINE_NEXT_CHECK(stCache.Cancel(stStatus.stPending, 1001, arrDiagnostics));
		if (stStatus.eLoadState == TextureLoadState::Loading)
		{
			ENGINE_NEXT_CHECK(stCache.FinishLoad(stStatus.stPending, false, 1001, arrDiagnostics));
		}
	}
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(nCopyIssued, nRenderIssued, 1001, arrReleased, arrDiagnostics));
	fnCheckRelease(arrReleased, nCopyIssued, nRenderIssued);
	ENGINE_NEXT_CHECK(stCache.ReleaseAll(nCopyIssued, nRenderIssued, arrReleased, arrDiagnostics));
	fnCheckRelease(arrReleased, nCopyIssued, nRenderIssued);
	ENGINE_NEXT_CHECK_EQ(setReleased.size(), mapCopies.size());
	ENGINE_NEXT_CHECK_EQ(stCache.Telemetry().nGpuReservedBytes, 0U);
}

ENGINE_NEXT_TEST("Texture coverage includes shadow casters and omnidirectional ray hits outside the primary view")
{
	const EngineNext::Rendering::WorldBounds stCaster{ { 2, -0.25, 0.25 }, { 2.5, 0.25, 0.75 } };
	std::array<double, 16> arrMatrix{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	ENGINE_NEXT_CHECK_EQ(EngineNext::Rendering::ProjectTextureBounds(stCaster, arrMatrix, 1024, 1024)[0], 0.0);
	arrMatrix[12] = -2;
	const std::array<double, 2> arrShadow = EngineNext::Rendering::ProjectTextureBounds(stCaster, arrMatrix, 1024, 1024);
	ENGINE_NEXT_CHECK_EQ(arrShadow[0], 256.0);
	ENGINE_NEXT_CHECK_EQ(arrShadow[1], 256.0);
	const EngineNext::Rendering::WorldBounds stReceiver{};
	ENGINE_NEXT_CHECK(EngineNext::Rendering::RayTextureFootprint(stCaster, stReceiver, 10, 128) > 0);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Rendering::RayTextureFootprint(stCaster, stReceiver, 1, 128), 0.0);
}

ENGINE_NEXT_TEST("Texture upload allocation failure releases reservations and retries only before submission")
{
	Fixture stFixture;
	const TextureLoadTicket stTicket = stFixture.Begin();
	ENGINE_NEXT_CHECK(!stFixture.stCache.FailUpload(stTicket, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stTicket, true, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.FailUpload(stTicket, 0, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nFailures, 1U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nPendingCount, 0U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nUploadReservedBytes, 0U);
	ENGINE_NEXT_CHECK_EQ(stFixture.stCache.Telemetry().nIoReservedBytes, 0U);
	const TextureLoadTicket stRetry = stFixture.Begin(2);
	ENGINE_NEXT_CHECK(stRetry.nGeneration > stTicket.nGeneration);
	ENGINE_NEXT_CHECK(stFixture.stCache.FinishLoad(stRetry, true, 2, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(stFixture.stCache.SubmitUpload(stRetry, 1, 1, stFixture.arrDiagnostics));
	ENGINE_NEXT_CHECK(!stFixture.stCache.FailUpload(stRetry, 2, stFixture.arrDiagnostics));
}
