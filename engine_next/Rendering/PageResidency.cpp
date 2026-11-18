/**************************************************************************/
/*  PageResidency.cpp                                                     */
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

#include <algorithm>
#include <cstddef>
#include <limits>
#include <initializer_list>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

bool Fail(const char *pMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "page_residency", "$", pMessage);
	return false;
}

void Increment(std::uint64_t &nCounter) noexcept
{
	if (nCounter != std::numeric_limits<std::uint64_t>::max())
	{
		++nCounter;
	}
}

} // namespace

bool PageResidency::Initialize(const ResidencyConfig &in_stConfig, const std::vector<PageDescription> &arrDescriptions, Assets::Diagnostics &out_arrDiagnostics)
{
	if (bInitialized || in_stConfig.nGpuBudget == 0 || in_stConfig.nStagingBudget == 0 || arrDescriptions.size() > MAX_RESIDENCY_PAGES)
	{
		return Fail("A fresh cache, positive memory budgets and at most 262144 page descriptions are required.", out_arrDiagnostics);
	}
	std::uint64_t nPinnedBytes = 0;
	PageResidency stCandidate;
	stCandidate.stConfig = in_stConfig;
	stCandidate.arrPages.resize(arrDescriptions.size());
	for (const PageDescription &stDescription : arrDescriptions)
	{
		if (stDescription.nId == 0 || stDescription.nGpuBytes == 0 || stDescription.nStagingBytes == 0 || stDescription.nGpuBytes > in_stConfig.nGpuBudget ||
			stDescription.nStagingBytes > in_stConfig.nStagingBudget)
		{
			return Fail("Page identities must be unique and each page must fit both memory budgets.", out_arrDiagnostics);
		}
		if (stDescription.bPinned)
		{
			if (stDescription.nGpuBytes > in_stConfig.nGpuBudget - nPinnedBytes)
			{
				return Fail("Pinned root pages exceed the GPU budget.", out_arrDiagnostics);
			}
			nPinnedBytes += stDescription.nGpuBytes;
		}
		stCandidate.arrPages[stCandidate.nPageCount].stDescription = stDescription;
		++stCandidate.nPageCount;
	}
	std::sort(stCandidate.arrPages.begin(), stCandidate.arrPages.end(), [](const PageRecord &stLeft, const PageRecord &stRight)
			  { return stLeft.stDescription.nId < stRight.stDescription.nId; });
	for (std::size_t nIndex = 1; nIndex < stCandidate.arrPages.size(); ++nIndex)
	{
		if (stCandidate.arrPages[nIndex - 1].stDescription.nId == stCandidate.arrPages[nIndex].stDescription.nId)
		{
			return Fail("Page identities must be unique.", out_arrDiagnostics);
		}
	}
	stCandidate.bInitialized = true;
	*this = std::move(stCandidate);
	return true;
}

bool PageResidency::ValidTime(std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics) const
{
	return bInitialized && in_nTick >= nTick ? true : Fail("Cache must be initialized and logical ticks must be monotonic.", out_arrDiagnostics);
}

std::uint32_t PageResidency::FindIndex(std::uint64_t nPageId) const noexcept
{
	const std::vector<PageRecord>::const_iterator it = std::lower_bound(arrPages.begin(), arrPages.end(), nPageId,
																		[](const PageRecord &stPage, std::uint64_t nId)
																		{ return stPage.stDescription.nId < nId; });
	return it != arrPages.end() && it->stDescription.nId == nPageId ? static_cast<std::uint32_t>(it - arrPages.begin()) : MAX_RESIDENCY_PAGES;
}

const PageRecord *PageResidency::Find(std::uint64_t nPageId) const noexcept
{
	const std::uint32_t nIndex = FindIndex(nPageId);
	return nIndex == MAX_RESIDENCY_PAGES ? nullptr : &arrPages[nIndex];
}

const ResidencyTelemetry &PageResidency::GetTelemetry() const noexcept
{
	return stTelemetry;
}

std::uint32_t PageResidency::GetPageCount() const noexcept
{
	return nPageCount;
}

void PageResidency::RecordEvent(std::uint64_t nKind, const PageRecord &stPage) noexcept
{
	Increment(stTelemetry.nEventCount);
	for (std::uint64_t nValue : { nKind, stPage.stDescription.nId, stPage.nGeneration, nTick })
	{
		for (std::uint32_t nByte = 0; nByte < 8; ++nByte)
		{
			stTelemetry.nEventHash ^= (nValue >> (nByte * 8)) & 255;
			stTelemetry.nEventHash *= 1099511628211ULL;
		}
	}
}

bool PageResidency::Request(std::uint64_t nPageId, std::uint64_t in_nTick, PageRequestResult &out_eResult, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nIndex = FindIndex(nPageId);
	if (!ValidTime(in_nTick, out_arrDiagnostics) || nIndex == MAX_RESIDENCY_PAGES)
	{
		return nIndex == MAX_RESIDENCY_PAGES ? Fail("Requested page does not exist.", out_arrDiagnostics) : false;
	}
	nTick = in_nTick;
	PageRecord &stPage = arrPages[nIndex];
	Increment(stTelemetry.nRequests);
	stPage.nLastTouchedTick = nTick;
	if (stPage.eState == PageState::Resident)
	{
		Increment(stTelemetry.nHits);
		out_eResult = PageRequestResult::Ready;
		RecordEvent(1, stPage);
		return true;
	}
	Increment(stTelemetry.nMisses);
	if (stPage.eState == PageState::RetryDelay && (stPage.bRetryOverflow || nTick < stPage.nRetryAfterTick))
	{
		out_eResult = PageRequestResult::BackingOff;
	}
	else
	{
		if (stPage.eState == PageState::Missing || stPage.eState == PageState::RetryDelay)
		{
			stPage.eState = PageState::Queued;
		}
		out_eResult = PageRequestResult::Pending;
	}
	RecordEvent(2, stPage);
	return true;
}

std::uint32_t PageResidency::FindEviction() const noexcept
{
	std::uint32_t nCandidate = MAX_RESIDENCY_PAGES;
	for (std::uint32_t nIndex = 0; nIndex < nPageCount; ++nIndex)
	{
		const PageRecord &stPage = arrPages[nIndex];
		if (stPage.eState != PageState::Resident || stPage.stDescription.bPinned || stPage.nLastRenderFence > nCompletedRenderFence)
		{
			continue;
		}
		if (nCandidate == MAX_RESIDENCY_PAGES || stPage.nLastTouchedTick < arrPages[nCandidate].nLastTouchedTick ||
			(stPage.nLastTouchedTick == arrPages[nCandidate].nLastTouchedTick && stPage.stDescription.nId < arrPages[nCandidate].stDescription.nId))
		{
			nCandidate = nIndex;
		}
	}
	return nCandidate;
}

bool PageResidency::BeginLoad(std::uint64_t nPageId, std::uint64_t in_nTick, PageLoadTicket &out_stTicket, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nIndex = FindIndex(nPageId);
	if (!ValidTime(in_nTick, out_arrDiagnostics) || nIndex == MAX_RESIDENCY_PAGES)
	{
		return nIndex == MAX_RESIDENCY_PAGES ? Fail("Load page does not exist.", out_arrDiagnostics) : false;
	}
	const PageRecord &stOriginal = arrPages[nIndex];
	if (stOriginal.eState != PageState::Queued || stOriginal.nGeneration == std::numeric_limits<std::uint64_t>::max())
	{
		return Fail("Only a queued page with an available generation can begin loading.", out_arrDiagnostics);
	}
	if (stOriginal.stDescription.nStagingBytes > stConfig.nStagingBudget - stTelemetry.nStagingReservedBytes)
	{
		return Fail("Staging memory is still owned by other loads or copy fences.", out_arrDiagnostics);
	}
	PageResidency stCandidate = *this;
	stCandidate.nTick = in_nTick;
	while (stOriginal.stDescription.nGpuBytes > stConfig.nGpuBudget - stCandidate.stTelemetry.nGpuReservedBytes)
	{
		const std::uint32_t nEviction = stCandidate.FindEviction();
		if (nEviction == MAX_RESIDENCY_PAGES)
		{
			return Fail("No unpinned, render-fence-retired page can satisfy the GPU budget.", out_arrDiagnostics);
		}
		PageRecord &stEvicted = stCandidate.arrPages[nEviction];
		stCandidate.stTelemetry.nGpuReservedBytes -= stEvicted.stDescription.nGpuBytes;
		stCandidate.stTelemetry.nResidentBytes -= stEvicted.stDescription.nGpuBytes;
		stEvicted.eState = PageState::Missing;
		Increment(stCandidate.stTelemetry.nEvictions);
		stCandidate.RecordEvent(3, stEvicted);
	}
	PageRecord &stPage = stCandidate.arrPages[nIndex];
	++stPage.nGeneration;
	stPage.eState = PageState::Loading;
	stPage.nUploadFence = 0;
	stPage.nLastRenderFence = 0;
	stPage.bDiscardUpload = false;
	stPage.bRetryOverflow = false;
	stCandidate.stTelemetry.nGpuReservedBytes += stPage.stDescription.nGpuBytes;
	stCandidate.stTelemetry.nStagingReservedBytes += stPage.stDescription.nStagingBytes;
	stCandidate.stTelemetry.nPeakGpuBytes = (std::max)(stCandidate.stTelemetry.nPeakGpuBytes, stCandidate.stTelemetry.nGpuReservedBytes);
	stCandidate.stTelemetry.nPeakStagingBytes = (std::max)(stCandidate.stTelemetry.nPeakStagingBytes, stCandidate.stTelemetry.nStagingReservedBytes);
	Increment(stCandidate.stTelemetry.nLoadsStarted);
	stCandidate.RecordEvent(4, stPage);
	out_stTicket = { nPageId, stPage.nGeneration };
	*this = stCandidate;
	return true;
}

bool PageResidency::TicketMatches(PageLoadTicket stTicket, std::uint32_t &out_nIndex, Assets::Diagnostics &out_arrDiagnostics) const
{
	const std::uint32_t nIndex = FindIndex(stTicket.nPageId);
	if (!bInitialized || nIndex == MAX_RESIDENCY_PAGES || stTicket.nGeneration == 0 || arrPages[nIndex].nGeneration != stTicket.nGeneration)
	{
		return Fail("Completion ticket is unknown or stale.", out_arrDiagnostics);
	}
	out_nIndex = nIndex;
	return true;
}

void PageResidency::ReleaseReservation(PageRecord &stPage) noexcept
{
	stTelemetry.nGpuReservedBytes -= stPage.stDescription.nGpuBytes;
	stTelemetry.nStagingReservedBytes -= stPage.stDescription.nStagingBytes;
}

void PageResidency::DelayRetry(PageRecord &stPage, std::uint64_t in_nTick) noexcept
{
	stPage.eState = PageState::RetryDelay;
	stPage.bRetryOverflow = stConfig.nRetryDelayTicks > std::numeric_limits<std::uint64_t>::max() - in_nTick;
	stPage.nRetryAfterTick = stPage.bRetryOverflow ? std::numeric_limits<std::uint64_t>::max() : in_nTick + stConfig.nRetryDelayTicks;
	Increment(stTelemetry.nLoadFailures);
	RecordEvent(5, stPage);
}

bool PageResidency::FinishLoad(PageLoadTicket stTicket, bool bSucceeded, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = MAX_RESIDENCY_PAGES;
	if (!ValidTime(in_nTick, out_arrDiagnostics) || !TicketMatches(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	PageRecord &stPage = arrPages[nIndex];
	if (stPage.eState != PageState::Loading && !(stPage.eState == PageState::UploadReady && !bSucceeded))
	{
		return Fail("Load completion does not match the page's CPU loading state.", out_arrDiagnostics);
	}
	nTick = in_nTick;
	if (bSucceeded)
	{
		stPage.eState = PageState::UploadReady;
		RecordEvent(6, stPage);
	}
	else
	{
		ReleaseReservation(stPage);
		DelayRetry(stPage, nTick);
	}
	return true;
}

bool PageResidency::CancelPrepared(PageLoadTicket stTicket, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = MAX_RESIDENCY_PAGES;
	if (!ValidTime(in_nTick, out_arrDiagnostics) || !TicketMatches(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	PageRecord &stPage = arrPages[nIndex];
	if (stPage.eState != PageState::UploadReady)
	{
		return Fail("Only an unsubmitted prepared upload can be cancelled.", out_arrDiagnostics);
	}
	nTick = in_nTick;
	ReleaseReservation(stPage);
	stPage.eState = PageState::Queued;
	RecordEvent(11, stPage);
	return true;
}

bool PageResidency::SubmitUpload(PageLoadTicket stTicket, std::uint64_t nCopyFence, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = MAX_RESIDENCY_PAGES;
	if (!TicketMatches(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	PageRecord &stPage = arrPages[nIndex];
	if (stPage.eState != PageState::UploadReady || nCopyFence <= nCompletedCopyFence || nCopyFence < nSubmittedCopyFence)
	{
		return Fail("Upload requires prepared data and a future, monotonic copy fence.", out_arrDiagnostics);
	}
	stPage.eState = PageState::UploadPending;
	stPage.nUploadFence = nCopyFence;
	nSubmittedCopyFence = nCopyFence;
	Increment(stTelemetry.nUploadsSubmitted);
	RecordEvent(7, stPage);
	return true;
}

bool PageResidency::DiscardUpload(PageLoadTicket stTicket, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = MAX_RESIDENCY_PAGES;
	if (!ValidTime(in_nTick, out_arrDiagnostics) || !TicketMatches(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	PageRecord &stPage = arrPages[nIndex];
	if (stPage.eState != PageState::UploadPending)
	{
		return Fail("Only a submitted copy can be discarded through its fence.", out_arrDiagnostics);
	}
	nTick = in_nTick;
	stPage.bDiscardUpload = true;
	RecordEvent(8, stPage);
	return true;
}

bool PageResidency::AdvanceFences(std::uint64_t in_nCopyFence, std::uint64_t in_nRenderFence, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidTime(in_nTick, out_arrDiagnostics) || in_nCopyFence < nCompletedCopyFence || in_nRenderFence < nCompletedRenderFence)
	{
		return Fail("Copy and graphics completed fences must be monotonic.", out_arrDiagnostics);
	}
	nTick = in_nTick;
	nCompletedCopyFence = in_nCopyFence;
	nCompletedRenderFence = in_nRenderFence;
	for (std::uint32_t nIndex = 0; nIndex < nPageCount; ++nIndex)
	{
		PageRecord &stPage = arrPages[nIndex];
		if (stPage.eState != PageState::UploadPending || stPage.nUploadFence > nCompletedCopyFence)
		{
			continue;
		}
		if (stPage.bDiscardUpload)
		{
			ReleaseReservation(stPage);
			DelayRetry(stPage, nTick);
		}
		else
		{
			stTelemetry.nStagingReservedBytes -= stPage.stDescription.nStagingBytes;
			stTelemetry.nResidentBytes += stPage.stDescription.nGpuBytes;
			stPage.eState = PageState::Resident;
			Increment(stTelemetry.nInstalls);
			RecordEvent(9, stPage);
		}
	}
	return true;
}

bool PageResidency::MarkUsed(PageLoadTicket stTicket, std::uint64_t nRenderFence, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = MAX_RESIDENCY_PAGES;
	if (!ValidTime(in_nTick, out_arrDiagnostics) || !TicketMatches(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	PageRecord &stPage = arrPages[nIndex];
	if (stPage.eState != PageState::Resident || nRenderFence <= nCompletedRenderFence || nRenderFence < nSubmittedRenderFence)
	{
		return Fail("Draw submission requires a resident page and a future graphics fence.", out_arrDiagnostics);
	}
	nTick = in_nTick;
	stPage.nLastTouchedTick = nTick;
	stPage.nLastRenderFence = nRenderFence;
	nSubmittedRenderFence = nRenderFence;
	RecordEvent(10, stPage);
	return true;
}

} // namespace EngineNext::Rendering
