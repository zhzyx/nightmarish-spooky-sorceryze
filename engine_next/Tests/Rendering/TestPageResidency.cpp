/**************************************************************************/
/*  TestPageResidency.cpp                                                 */
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

#include "engine_next/include/EngineNext/Rendering/PageResidency.h"
#include "engine_next/Tests/TestFramework.h"

#include <cstdint>
#include <limits>
#include <vector>

namespace
{

using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::PageDescription;
using EngineNext::Rendering::PageLoadTicket;
using EngineNext::Rendering::PageRequestResult;
using EngineNext::Rendering::PageResidency;
using EngineNext::Rendering::PageState;
using EngineNext::Rendering::ResidencyConfig;

PageLoadTicket Load(PageResidency &stCache, std::uint64_t nId, std::uint64_t nTick, std::uint64_t nFence)
{
	Diagnostics arrDiagnostics;
	PageRequestResult eResult = PageRequestResult::BackingOff;
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.Request(nId, nTick, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(nId, nTick, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, true, nTick, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stTicket, nFence, arrDiagnostics));
	return stTicket;
}

void CheckBounds(const PageResidency &stCache, std::uint64_t nGpu, std::uint64_t nStaging)
{
	const EngineNext::Rendering::ResidencyTelemetry &stTelemetry = stCache.GetTelemetry();
	ENGINE_NEXT_CHECK(stTelemetry.nGpuReservedBytes <= nGpu);
	ENGINE_NEXT_CHECK(stTelemetry.nStagingReservedBytes <= nStaging);
	ENGINE_NEXT_CHECK(stTelemetry.nResidentBytes <= stTelemetry.nGpuReservedBytes);
}

} // namespace

ENGINE_NEXT_TEST("Residency initialization validates page and pinned budgets transactionally")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stCache.Initialize({ 0, 64, 2 }, { { 1, 16, 16, false } }, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Initialize({ 64, 64, 2 }, { { 1, 16, 16, false }, { 1, 16, 16, false } }, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Initialize({ 64, 64, 2 }, { { 1, 40, 16, true }, { 2, 40, 16, true } }, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Initialize({ 64, 64, 2 }, { { 1, 65, 16, false } }, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 2 }, { { 1, 64, 64, true } }, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetPageCount(), 1U);
	ENGINE_NEXT_CHECK(!stCache.Initialize({ 64, 64, 2 }, {}, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetPageCount(), 1U);
}

ENGINE_NEXT_TEST("Residency installs only after copy fence and releases staging at retirement")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 128, 64, 2 }, { { 1, 64, 32, false } }, arrDiagnostics));
	const PageLoadTicket stTicket = Load(stCache, 1, 1, 7);
	ENGINE_NEXT_CHECK_EQ(stTicket.nGeneration, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::UploadPending);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 64ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nStagingReservedBytes, 32ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nResidentBytes, 0ULL);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(6, 0, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::UploadPending);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(7, 0, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Resident);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nStagingReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nResidentBytes, 64ULL);
	PageRequestResult eResult = PageRequestResult::Pending;
	ENGINE_NEXT_CHECK(stCache.Request(1, 3, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, PageRequestResult::Ready);
}

ENGINE_NEXT_TEST("Residency graphics fences block eviction and failed reservation preserves pages")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 2 }, { { 1, 64, 64, false }, { 2, 64, 64, false } }, arrDiagnostics));
	const PageLoadTicket stFirst = Load(stCache, 1, 1, 1);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.MarkUsed(stFirst, 10, 2, arrDiagnostics));
	PageRequestResult eResult;
	ENGINE_NEXT_CHECK(stCache.Request(2, 3, eResult, arrDiagnostics));
	PageLoadTicket stTicket{ 99, 99 };
	const std::uint64_t nBeforeHash = stCache.GetTelemetry().nEventHash;
	ENGINE_NEXT_CHECK(!stCache.BeginLoad(2, 3, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stTicket.nPageId, 99ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Resident);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nEventHash, nBeforeHash);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 10, 4, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(2, 4, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Missing);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nEvictions, 1ULL);
	CheckBounds(stCache, 64, 64);
}

ENGINE_NEXT_TEST("Residency LRU is stable within a tick and pinned roots remain resident")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 192, 64, 2 }, { { 3, 64, 32, false }, { 2, 64, 32, false }, { 1, 64, 32, true }, { 4, 64, 32, false } }, arrDiagnostics));
	Load(stCache, 1, 1, 1);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 1, arrDiagnostics));
	Load(stCache, 3, 2, 2);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 0, 2, arrDiagnostics));
	Load(stCache, 2, 2, 3);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(3, 0, 2, arrDiagnostics));
	PageRequestResult eResult;
	ENGINE_NEXT_CHECK(stCache.Request(4, 3, eResult, arrDiagnostics));
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.BeginLoad(4, 3, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Resident);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(2)->eState, PageState::Missing);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(3)->eState, PageState::Resident);
}

ENGINE_NEXT_TEST("Residency failed loads roll back reservations and retry with new ticket generation")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 3 }, { { 1, 64, 64, false } }, arrDiagnostics));
	PageRequestResult eResult;
	PageLoadTicket stFirst;
	ENGINE_NEXT_CHECK(stCache.Request(1, 1, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(1, 1, stFirst, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stFirst, false, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nStagingReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK(stCache.Request(1, 4, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, PageRequestResult::BackingOff);
	ENGINE_NEXT_CHECK(stCache.Request(1, 5, eResult, arrDiagnostics));
	PageLoadTicket stSecond;
	ENGINE_NEXT_CHECK(stCache.BeginLoad(1, 5, stSecond, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stSecond.nGeneration, 2ULL);
	ENGINE_NEXT_CHECK(!stCache.FinishLoad(stFirst, true, 5, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Loading);
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stSecond, true, 5, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stSecond, false, 5, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 0ULL);
}

ENGINE_NEXT_TEST("Residency submitted discard retains both reservations through copy completion")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 2 }, { { 1, 64, 64, false }, { 2, 64, 64, false } }, arrDiagnostics));
	PageLoadTicket stTicket = Load(stCache, 1, 1, 9);
	ENGINE_NEXT_CHECK(stCache.DiscardUpload(stTicket, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 64ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nStagingReservedBytes, 64ULL);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(8, 0, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::UploadPending);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(9, 0, 4, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::RetryDelay);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nResidentBytes, 0ULL);
	PageRequestResult eResult;
	ENGINE_NEXT_CHECK(stCache.Request(1, 5, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, PageRequestResult::BackingOff);
}

ENGINE_NEXT_TEST("Residency staging budgets and fence monotonicity are enforced")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 128, 64, 2 }, { { 1, 64, 64, false }, { 2, 64, 64, false } }, arrDiagnostics));
	Load(stCache, 1, 1, 3);
	PageRequestResult eResult;
	ENGINE_NEXT_CHECK(stCache.Request(2, 1, eResult, arrDiagnostics));
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(!stCache.BeginLoad(2, 1, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(3, 7, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.AdvanceFences(2, 7, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.AdvanceFences(3, 6, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.Request(2, 1, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(2, 2, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, true, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.SubmitUpload(stTicket, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stTicket, 4, arrDiagnostics));
	CheckBounds(stCache, 128, 64);
}

ENGINE_NEXT_TEST("Residency maximum integer budgets avoid overflow and retry does not wrap")
{
	const std::uint64_t nMaximum = std::numeric_limits<std::uint64_t>::max();
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ nMaximum, nMaximum, 3 }, { { 1, nMaximum, nMaximum, false } }, arrDiagnostics));
	PageRequestResult eResult;
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.Request(1, nMaximum - 1, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(1, nMaximum - 1, stTicket, arrDiagnostics));
	CheckBounds(stCache, nMaximum, nMaximum);
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, false, nMaximum - 1, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK(stCache.Request(1, nMaximum, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(eResult, PageRequestResult::BackingOff);
}

ENGINE_NEXT_TEST("Residency action replay produces identical telemetry and event order")
{
	PageResidency arrCaches[2];
	for (PageResidency &stCache : arrCaches)
	{
		Diagnostics arrDiagnostics;
		ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 1 }, { { 1, 64, 64, false }, { 2, 64, 64, false } }, arrDiagnostics));
		Load(stCache, 1, 1, 1);
		ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 2, arrDiagnostics));
		Load(stCache, 2, 3, 2);
		ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 0, 4, arrDiagnostics));
	}
	const EngineNext::Rendering::ResidencyTelemetry &stFirst = arrCaches[0].GetTelemetry();
	const EngineNext::Rendering::ResidencyTelemetry &stSecond = arrCaches[1].GetTelemetry();
	ENGINE_NEXT_CHECK_EQ(stFirst.nRequests, 2ULL);
	ENGINE_NEXT_CHECK_EQ(stFirst.nEvictions, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stFirst.nInstalls, 2ULL);
	ENGINE_NEXT_CHECK_EQ(stFirst.nEventHash, stSecond.nEventHash);
	ENGINE_NEXT_CHECK_EQ(stFirst.nEventCount, stSecond.nEventCount);
}

ENGINE_NEXT_TEST("Residency unsuccessful multi-eviction remains fully transactional")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 128, 128, 2 }, { { 1, 64, 64, false }, { 2, 64, 64, false }, { 3, 128, 128, false } }, arrDiagnostics));
	Load(stCache, 1, 1, 1);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 1, arrDiagnostics));
	const PageLoadTicket stSecond = Load(stCache, 2, 2, 2);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 0, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.MarkUsed(stSecond, 9, 3, arrDiagnostics));
	PageRequestResult eResult;
	ENGINE_NEXT_CHECK(stCache.Request(3, 4, eResult, arrDiagnostics));
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(!stCache.BeginLoad(3, 4, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Resident);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(2)->eState, PageState::Resident);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nEvictions, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nResidentBytes, 128ULL);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 9, 5, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(3, 5, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nEvictions, 2ULL);
	CheckBounds(stCache, 128, 128);
}

ENGINE_NEXT_TEST("Residency stale draw tokens cannot protect a reloaded generation")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 1 }, { { 1, 64, 64, false }, { 2, 64, 64, false } }, arrDiagnostics));
	const PageLoadTicket stOld = Load(stCache, 1, 1, 1);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(1, 0, 1, arrDiagnostics));
	Load(stCache, 2, 2, 2);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 0, 2, arrDiagnostics));
	const PageLoadTicket stCurrent = Load(stCache, 1, 3, 3);
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(3, 0, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.MarkUsed(stOld, 4, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.MarkUsed(stCurrent, 4, 3, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->nLastRenderFence, 4ULL);
}

ENGINE_NEXT_TEST("Residency maximum page table can evict all unpinned entries within budget")
{
	std::vector<PageDescription> arrDescriptions;
	for (std::uint64_t nId = 1; nId < 256; ++nId)
	{
		arrDescriptions.push_back({ nId, 1, 1, false });
	}
	arrDescriptions.push_back({ 256, 255, 255, false });
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 255, 255, 1 }, arrDescriptions, arrDiagnostics));
	for (std::uint64_t nId = 1; nId < 256; ++nId)
	{
		Load(stCache, nId, nId, nId);
		ENGINE_NEXT_CHECK(stCache.AdvanceFences(nId, 0, nId, arrDiagnostics));
	}
	PageRequestResult eResult;
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.Request(256, 256, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(256, 256, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nEvictions, 255ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 255ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nResidentBytes, 0ULL);
	CheckBounds(stCache, 255, 255);
}

ENGINE_NEXT_TEST("Page residency supports indexed metadata beyond the prototype capacity")
{
	std::vector<PageDescription> arrDescriptions;
	for (std::uint64_t nId = 1024; nId > 0; --nId)
	{
		arrDescriptions.push_back({ nId, 1, 1, false });
	}
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 1024, 1024, 1 }, arrDescriptions, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetPageCount(), 1024U);
	ENGINE_NEXT_CHECK(stCache.Find(1) != nullptr);
	ENGINE_NEXT_CHECK(stCache.Find(1024) != nullptr);
	ENGINE_NEXT_CHECK(stCache.Find(1025) == nullptr);
}

ENGINE_NEXT_TEST("Prepared page cancellation releases reservations without publishing residency")
{
	PageResidency stCache;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stCache.Initialize({ 64, 64, 1 }, { { 1, 64, 64, true } }, arrDiagnostics));
	PageRequestResult eResult;
	PageLoadTicket stTicket;
	ENGINE_NEXT_CHECK(stCache.Request(1, 0, eResult, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.BeginLoad(1, 0, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.CancelPrepared(stTicket, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, true, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.CancelPrepared(stTicket, 0, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nGpuReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.GetTelemetry().nStagingReservedBytes, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Queued);
	ENGINE_NEXT_CHECK(stCache.BeginLoad(1, 1, stTicket, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.FinishLoad(stTicket, true, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.SubmitUpload(stTicket, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK(!stCache.CancelPrepared(stTicket, 1, arrDiagnostics));
	ENGINE_NEXT_CHECK(stCache.AdvanceFences(2, 2, 2, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCache.Find(1)->eState, PageState::Resident);
}
