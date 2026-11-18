/**************************************************************************/
/*  PageResidency.h                                                       */
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

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

inline constexpr std::uint32_t MAX_RESIDENCY_PAGES = 262144;

enum class PageState : std::uint8_t
{
	Missing = 0,
	Queued = 1,
	Loading = 2,
	UploadReady = 3,
	UploadPending = 4,
	Resident = 5,
	RetryDelay = 6,
};

enum class PageRequestResult : std::uint8_t
{
	Ready = 0,
	Pending = 1,
	BackingOff = 2,
};

struct PageDescription
{
	std::uint64_t nId = 0;
	std::uint64_t nGpuBytes = 0;
	std::uint64_t nStagingBytes = 0;
	bool bPinned = false;
};

struct ResidencyConfig
{
	std::uint64_t nGpuBudget = 64ULL * 1024 * 1024;
	std::uint64_t nStagingBudget = 16ULL * 1024 * 1024;
	std::uint64_t nRetryDelayTicks = 2;
};

struct PageLoadTicket
{
	std::uint64_t nPageId = 0;
	std::uint64_t nGeneration = 0;
};

struct PageRecord
{
	PageDescription stDescription;
	PageState eState = PageState::Missing;
	std::uint64_t nGeneration = 0;
	std::uint64_t nLastTouchedTick = 0;
	std::uint64_t nLastRenderFence = 0;
	std::uint64_t nUploadFence = 0;
	std::uint64_t nRetryAfterTick = 0;
	bool bDiscardUpload = false;
	bool bRetryOverflow = false;
};

struct ResidencyTelemetry
{
	std::uint64_t nRequests = 0;
	std::uint64_t nHits = 0;
	std::uint64_t nMisses = 0;
	std::uint64_t nLoadsStarted = 0;
	std::uint64_t nLoadFailures = 0;
	std::uint64_t nUploadsSubmitted = 0;
	std::uint64_t nInstalls = 0;
	std::uint64_t nEvictions = 0;
	std::uint64_t nGpuReservedBytes = 0;
	std::uint64_t nStagingReservedBytes = 0;
	std::uint64_t nResidentBytes = 0;
	std::uint64_t nPeakGpuBytes = 0;
	std::uint64_t nPeakStagingBytes = 0;
	std::uint64_t nEventCount = 0;
	std::uint64_t nEventHash = 14695981039346656037ULL;
};

// Pure CPU bookkeeping. The owner serializes calls; background I/O returns only
// tickets/results to that owner. No OS handles, threads or memory allocations
// are represented by the records. Actual staging allocations must remain alive
// until FinishLoad reports worker completion and submitted copies reach their
// copy fence. Draw submission uses a generation-bearing ticket and runs on
// the owner without intervening eviction. Returned record pointers remain valid
// until the next mutation.
// Copy and graphics completion values are separate monotonic fence domains.
class PageResidency final
{
public:
	[[nodiscard]] bool Initialize(const ResidencyConfig &stConfig, const std::vector<PageDescription> &arrPages, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Request(std::uint64_t nPageId, std::uint64_t nTick, PageRequestResult &out_eResult, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool BeginLoad(std::uint64_t nPageId, std::uint64_t nTick, PageLoadTicket &out_stTicket, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool FinishLoad(PageLoadTicket stTicket, bool bSucceeded, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool CancelPrepared(PageLoadTicket stTicket, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool SubmitUpload(PageLoadTicket stTicket, std::uint64_t nCopyFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool DiscardUpload(PageLoadTicket stTicket, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool AdvanceFences(std::uint64_t nCompletedCopyFence, std::uint64_t nCompletedRenderFence, std::uint64_t nTick,
									 Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool MarkUsed(PageLoadTicket stTicket, std::uint64_t nRenderFence, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);

	[[nodiscard]] const PageRecord *Find(std::uint64_t nPageId) const noexcept;
	[[nodiscard]] const ResidencyTelemetry &GetTelemetry() const noexcept;
	[[nodiscard]] std::uint32_t GetPageCount() const noexcept;

private:
	[[nodiscard]] std::uint32_t FindIndex(std::uint64_t nPageId) const noexcept;
	[[nodiscard]] std::uint32_t FindEviction() const noexcept;
	[[nodiscard]] bool ValidTime(std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics) const;
	[[nodiscard]] bool TicketMatches(PageLoadTicket stTicket, std::uint32_t &out_nIndex, Assets::Diagnostics &out_arrDiagnostics) const;
	void RecordEvent(std::uint64_t nKind, const PageRecord &stPage) noexcept;
	void ReleaseReservation(PageRecord &stPage) noexcept;
	void DelayRetry(PageRecord &stPage, std::uint64_t nTick) noexcept;

	bool bInitialized = false;
	ResidencyConfig stConfig;
	std::vector<PageRecord> arrPages;
	std::uint32_t nPageCount = 0;
	std::uint64_t nTick = 0;
	std::uint64_t nCompletedCopyFence = 0;
	std::uint64_t nCompletedRenderFence = 0;
	std::uint64_t nSubmittedCopyFence = 0;
	std::uint64_t nSubmittedRenderFence = 0;
	ResidencyTelemetry stTelemetry;
};

} // namespace EngineNext::Rendering
