/**************************************************************************/
/*  TextureResidency.h                                                    */
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

#include "engine_next/include/EngineNext/Rendering/ShadowData.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{

struct TextureMipAllocation
{
	// Backend-provided allocation requirements for the complete mip suffix.
	// These are real resource/upload allocation bytes, not compressed texel bytes.
	std::uint64_t nGpuBytes = 0;
	std::uint64_t nUploadBytes = 0;
	std::uint64_t nIoBytes = 0;
};

struct TextureResidencyDescription
{
	std::uint64_t nTextureId = 0;
	// Finest to coarsest. The final mip is an always-retained fallback.
	std::vector<TextureMipAllocation> arrMips;
};

struct TextureResidencyConfig
{
	std::uint64_t nGpuBudget = 256ULL * 1024 * 1024;
	std::uint64_t nUploadBudget = 16ULL * 1024 * 1024;
	std::uint64_t nIoBudget = 16ULL * 1024 * 1024;
	std::uint32_t nMaximumPending = 8;
	std::uint32_t nMaximumVersions = 65536;
	std::uint64_t nRetryDelayTicks = 2;
};

struct TextureMipDemand
{
	std::uint64_t nTextureId = 0;
	std::uint32_t nFirstMip = 0;
	double dPriority = 0;
};

struct TextureLoadTicket
{
	std::uint64_t nTextureId = 0;
	std::uint64_t nGeneration = 0;
	std::uint32_t nFirstMip = 0;
};

struct TextureResidentHandle
{
	std::uint64_t nTextureId = 0;
	std::uint64_t nGeneration = 0;
	std::uint64_t nResourceToken = 0;
	std::uint32_t nFirstMip = 0;
};

struct TextureResourceRelease
{
	std::uint64_t nResourceToken = 0;
	std::uint64_t nGpuBytes = 0;
};

enum class TextureLoadState : std::uint8_t
{
	Idle = 0,
	Loading = 1,
	UploadReady = 2,
	UploadPending = 3,
	RetryDelay = 4,
};

enum class TextureScheduleResult : std::uint8_t
{
	NoWork = 0,
	Started = 1,
	BudgetBlocked = 2,
};

struct TextureResidencyStatus
{
	std::uint32_t nWantedFirstMip = 0;
	TextureLoadState eLoadState = TextureLoadState::Idle;
	TextureLoadTicket stPending;
	bool bCancellationRequested = false;
	bool bHasResident = false;
	TextureResidentHandle stResident;
	std::uint64_t nRetryAfterTick = 0;
};

struct TextureResidencyTelemetry
{
	// The coarsest fallback floor is reserved even before it is loaded.
	std::uint64_t nFallbackBudgetBytes = 0;
	std::uint64_t nGpuReservedBytes = 0;
	std::uint64_t nUploadReservedBytes = 0;
	std::uint64_t nIoReservedBytes = 0;
	std::uint64_t nResidentBytes = 0;
	std::uint64_t nRetiredBytes = 0;
	std::uint64_t nPendingGpuBytes = 0;
	std::uint64_t nPeakGpuReservedBytes = 0;
	std::uint64_t nPeakUploadReservedBytes = 0;
	std::uint64_t nPeakIoReservedBytes = 0;
	std::uint64_t nLoadsStarted = 0;
	std::uint64_t nInstalls = 0;
	std::uint64_t nCancellations = 0;
	std::uint64_t nFailures = 0;
	std::uint64_t nBudgetStalls = 0;
	std::uint32_t nPendingCount = 0;
	std::uint32_t nTrackedVersions = 0;
};

// Conservative clipped pixel footprint for raster or shadow projection.
[[nodiscard]] std::array<double, 2> ProjectTextureBounds(const WorldBounds &stBounds, const std::array<double, 16> &arrMatrix,
														 double dWidth, double dHeight) noexcept;

// Omnidirectional footprint for GI probes or reflection rays, independent of camera visibility.
[[nodiscard]] double RayTextureFootprint(const WorldBounds &stBounds, const WorldBounds &stOrigins, double dRange, double dPixelsPerRadian) noexcept;

// CPU estimate from a projected rectangular footprint and its UV span.
// Negative UV scales are supported. Zero screen coverage requests the coarsest
// mip. Secondary rays/shadows must contribute their own explicit demands.
[[nodiscard]] bool EstimateTextureMip(std::uint32_t nWidth, std::uint32_t nHeight,
									  double dScreenWidth, double dScreenHeight, double dUSpan, double dVSpan,
									  double dMipBias, std::uint32_t &out_nFirstMip) noexcept;

// One serialized owner, no GPU/IO threads or handles. Workers return only a
// generation-bearing ticket. The backend supplies actual allocation sizes and
// monotonically increasing resource tokens. A texture retains one coarsest
// resource so downshifts never expose an untextured hole. It also may have one
// current finer resource, one pending replacement and fence-retired versions.
// IO bytes include all source buffers retained through CPU upload preparation.
// GetResident + MarkUsed must precede the corresponding draw submission without
// intervening planner mutations. SubmitUpload follows successful copy submission
// and acknowledges that source IO buffers have been copied and released.
// Multiple tickets from one submitted copy batch may share its fence value.
// Released tokens are emitted only after the stated copy/render fences retire.
class TextureResidency final
{
public:
	TextureResidency() noexcept = default;
	TextureResidency(const TextureResidency &) = delete;
	TextureResidency &operator=(const TextureResidency &) = delete;
	TextureResidency(TextureResidency &&) = delete;
	TextureResidency &operator=(TextureResidency &&) = delete;
	[[nodiscard]] bool Initialize(const TextureResidencyConfig &stConfig,
								  const std::vector<TextureResidencyDescription> &arrDescriptions, Assets::Diagnostics &out_arrDiagnostics);
	// Complete demand snapshot. Duplicate texture demands coalesce to the finest
	// mip and highest priority. Unmentioned textures return to their fallback.
	// A coarser request switches to the fallback, retiring the old finer version.
	[[nodiscard]] bool SetDemand(const std::vector<TextureMipDemand> &arrDemand, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool BeginNextLoad(std::uint64_t nTick, TextureScheduleResult &out_eResult,
									 TextureLoadTicket &out_stTicket, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool FinishLoad(TextureLoadTicket stTicket, bool bSucceeded, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	// Pre-submission failure after the backend has released all candidate resources.
	[[nodiscard]] bool FailUpload(TextureLoadTicket stTicket, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool Cancel(TextureLoadTicket stTicket, std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool SubmitUpload(TextureLoadTicket stTicket, std::uint64_t nResourceToken,
									std::uint64_t nCopyFence, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool AdvanceFences(std::uint64_t nCompletedCopyFence, std::uint64_t nCompletedRenderFence,
									 std::uint64_t nTick, std::vector<TextureResourceRelease> &out_arrReleased, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] bool GetResident(std::uint64_t nTextureId, TextureResidentHandle &out_stHandle) const noexcept;
	[[nodiscard]] bool GetStatus(std::uint64_t nTextureId, TextureResidencyStatus &out_stStatus) const noexcept;
	[[nodiscard]] bool MarkUsed(TextureResidentHandle stHandle, std::uint64_t nRenderFence, Assets::Diagnostics &out_arrDiagnostics);
	// Refuses in-flight IO/copies or unretired draws. Success returns every held
	// token and resets the owner; an invalid request leaves it unchanged.
	[[nodiscard]] bool ReleaseAll(std::uint64_t nCompletedCopyFence, std::uint64_t nCompletedRenderFence,
								  std::vector<TextureResourceRelease> &out_arrReleased, Assets::Diagnostics &out_arrDiagnostics);
	[[nodiscard]] const TextureResidencyTelemetry &Telemetry() const noexcept;

private:
	struct Version
	{
		TextureResidentHandle stHandle;
		std::uint64_t nGpuBytes = 0;
		std::uint64_t nLastRenderFence = 0;
	};
	struct Pending
	{
		TextureLoadTicket stTicket;
		TextureMipAllocation stAllocation;
		std::uint64_t nResourceToken = 0;
		std::uint64_t nCopyFence = 0;
		bool bCancelled = false;
		bool bIoHeld = false;
	};
	struct Record
	{
		TextureResidencyDescription stDescription;
		TextureLoadState eState = TextureLoadState::Idle;
		std::uint32_t nWantedMip = 0;
		double dPriority = 0;
		std::uint64_t nGeneration = 0;
		std::uint64_t nRetryAfterTick = 0;
		bool bRetryOverflow = false;
		Version stFallback;
		Version stCurrent;
		Pending stPending;
	};
	[[nodiscard]] std::uint32_t FindIndex(std::uint64_t nTextureId) const noexcept;
	[[nodiscard]] bool ValidTick(std::uint64_t nTick, Assets::Diagnostics &out_arrDiagnostics) const;
	[[nodiscard]] bool FindTicket(TextureLoadTicket stTicket, std::uint32_t &out_nIndex, Assets::Diagnostics &out_arrDiagnostics) const;
	void ClearPending(Record &stRecord, bool bReleaseGpuReservation) noexcept;
	void RetireCurrent(Record &stRecord);
	void RecordFailure(Record &stRecord, std::uint64_t nTick) noexcept;

	bool bInitialized = false;
	TextureResidencyConfig stConfig;
	std::vector<Record> arrRecords;
	std::vector<Version> arrRetired;
	TextureResidencyTelemetry stTelemetry;
	std::uint64_t nTick = 0;
	std::uint64_t nCompletedCopy = 0;
	std::uint64_t nCompletedRender = 0;
	std::uint64_t nSubmittedCopy = 0;
	std::uint64_t nSubmittedRender = 0;
	std::uint64_t nLatestResourceToken = 0;
};

} // namespace EngineNext::Rendering
