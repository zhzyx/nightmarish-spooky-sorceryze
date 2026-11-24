/**************************************************************************/
/*  TextureResidency.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/TextureResidency.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <initializer_list>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{
constexpr std::uint32_t MAX_TEXTURES = 65536;
constexpr std::uint32_t MAX_VERSIONS = 262144;
constexpr std::uint64_t MAX_GPU_BYTES = 8ULL * 1024 * 1024 * 1024;
constexpr std::uint64_t MAX_UPLOAD_BYTES = 1024ULL * 1024 * 1024;
constexpr std::uint32_t INVALID_TEXTURE = UINT32_MAX;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "texture_residency", "$", pMessage);
	return false;
}

void Increment(std::uint64_t &out_nCounter) noexcept
{
	if (out_nCounter != UINT64_MAX)
	{
		++out_nCounter;
	}
}

bool SameHandle(const TextureResidentHandle &stLeft, const TextureResidentHandle &stRight) noexcept
{
	return stLeft.nTextureId == stRight.nTextureId && stLeft.nGeneration == stRight.nGeneration &&
			stLeft.nResourceToken == stRight.nResourceToken && stLeft.nFirstMip == stRight.nFirstMip;
}
} // namespace

std::array<double, 2> ProjectTextureBounds(const WorldBounds &stBounds, const std::array<double, 16> &arrMatrix,
										   double dWidth, double dHeight) noexcept
{
	std::array<double, 2> arrMin{ 1, 1 };
	std::array<double, 2> arrMax{ -1, -1 };
	bool bInFront = false;
	bool bBehind = false;
	bool bBeyondNear = false;
	bool bWithinFar = false;
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		std::array<double, 4> arrPoint{ 0, 0, 0, 1 };
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			arrPoint[nAxis] = (nCorner & (1U << nAxis)) ? stBounds.arrMaximum[nAxis] : stBounds.arrMinimum[nAxis];
		}
		std::array<double, 4> arrClip{};
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			for (std::size_t nCol = 0; nCol < 4; ++nCol)
			{
				arrClip[nRow] += arrMatrix[nCol * 4 + nRow] * arrPoint[nCol];
			}
		}
		bBeyondNear = bBeyondNear || arrClip[2] >= 0;
		bWithinFar = bWithinFar || arrClip[2] <= arrClip[3];
		if (arrClip[3] <= 0.000001)
		{
			bBehind = true;
			continue;
		}
		bInFront = true;
		for (std::size_t nAxis = 0; nAxis < 2; ++nAxis)
		{
			const double dNdc = arrClip[nAxis] / arrClip[3];
			arrMin[nAxis] = (std::min)(arrMin[nAxis], dNdc);
			arrMax[nAxis] = (std::max)(arrMax[nAxis], dNdc);
		}
	}
	if (!bInFront || !bBeyondNear || !bWithinFar)
	{
		return {};
	}
	if (bBehind)
	{
		return { dWidth, dHeight };
	}
	return { dWidth * 0.5 * (std::clamp(arrMax[0], -1.0, 1.0) - std::clamp(arrMin[0], -1.0, 1.0)),
			 dHeight * 0.5 * (std::clamp(arrMax[1], -1.0, 1.0) - std::clamp(arrMin[1], -1.0, 1.0)) };
}

// An omnidirectional source region can hit casters outside the camera frustum.
// Pixel density is pixels per radian, distance and extents are world meters.
double RayTextureFootprint(const WorldBounds &stBounds, const WorldBounds &stOrigins, double dRange, double dPixelsPerRadian) noexcept
{
	double dDistanceSquared = 0;
	double dSizeSquared = 0;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		const double dSeparation = (std::max)({ 0.0, stBounds.arrMinimum[nAxis] - stOrigins.arrMaximum[nAxis],
												stOrigins.arrMinimum[nAxis] - stBounds.arrMaximum[nAxis] });
		const double dSize = stBounds.arrMaximum[nAxis] - stBounds.arrMinimum[nAxis];
		dDistanceSquared += dSeparation * dSeparation;
		dSizeSquared += dSize * dSize;
	}
	if (dDistanceSquared > dRange * dRange)
	{
		return 0;
	}
	return 2 * std::atan2(0.5 * std::sqrt(dSizeSquared), std::sqrt(dDistanceSquared)) * dPixelsPerRadian;
}

bool EstimateTextureMip(std::uint32_t nWidth, std::uint32_t nHeight, double dScreenWidth, double dScreenHeight,
						double dUSpan, double dVSpan, double dMipBias, std::uint32_t &out_nFirstMip) noexcept
{
	if (nWidth == 0 || nHeight == 0 || nWidth > 8192 || nHeight > 8192 || !std::isfinite(dScreenWidth) ||
		!std::isfinite(dScreenHeight) || dScreenWidth < 0 || dScreenHeight < 0 || !std::isfinite(dUSpan) ||
		!std::isfinite(dVSpan) || !std::isfinite(dMipBias) || std::abs(dMipBias) > 16)
	{
		return false;
	}
	std::uint32_t nLastMip = 0;
	for (std::uint32_t nSize = (std::max)(nWidth, nHeight); nSize > 1; nSize /= 2)
	{
		++nLastMip;
	}
	if (dScreenWidth == 0 || dScreenHeight == 0)
	{
		out_nFirstMip = nLastMip;
		return true;
	}
	const double dDensity = (std::max)(nWidth * std::abs(dUSpan) / dScreenWidth, nHeight * std::abs(dVSpan) / dScreenHeight);
	const double dMip = std::floor(std::log2((std::max)(1.0, dDensity)) + dMipBias);
	out_nFirstMip = !std::isfinite(dMip) || dMip >= nLastMip ? nLastMip : static_cast<std::uint32_t>((std::max)(0.0, dMip));
	return true;
}

bool TextureResidency::Initialize(const TextureResidencyConfig &in_stConfig,
								  const std::vector<TextureResidencyDescription> &arrDescriptions, Assets::Diagnostics &out_arrDiagnostics)
{
	if (bInitialized || arrDescriptions.size() > MAX_TEXTURES || in_stConfig.nGpuBudget == 0 || in_stConfig.nGpuBudget > MAX_GPU_BYTES ||
		in_stConfig.nUploadBudget == 0 || in_stConfig.nUploadBudget > MAX_UPLOAD_BYTES ||
		in_stConfig.nIoBudget == 0 || in_stConfig.nIoBudget > MAX_UPLOAD_BYTES || in_stConfig.nMaximumPending == 0 ||
		in_stConfig.nMaximumPending > MAX_TEXTURES || in_stConfig.nMaximumVersions == 0 || in_stConfig.nMaximumVersions < arrDescriptions.size() || in_stConfig.nMaximumVersions > MAX_VERSIONS)
	{
		return Fail(out_arrDiagnostics, "Initialization requires a fresh owner and bounded positive budgets.");
	}
	std::vector<Record> arrCandidate;
	arrCandidate.reserve(arrDescriptions.size());
	std::uint64_t nFallbackBytes = 0;
	for (const TextureResidencyDescription &stDescription : arrDescriptions)
	{
		if (stDescription.nTextureId == 0 || stDescription.arrMips.empty() || stDescription.arrMips.size() > 14)
		{
			return Fail(out_arrDiagnostics, "Texture identities and complete allocation chains are required.");
		}
		std::uint64_t nPreviousGpu = MAX_GPU_BYTES;
		std::uint64_t nPreviousUpload = MAX_UPLOAD_BYTES;
		std::uint64_t nPreviousIo = MAX_UPLOAD_BYTES;
		for (const TextureMipAllocation &stMip : stDescription.arrMips)
		{
			if (stMip.nGpuBytes == 0 || stMip.nUploadBytes == 0 || stMip.nIoBytes == 0 || stMip.nGpuBytes > nPreviousGpu || stMip.nUploadBytes > nPreviousUpload || stMip.nIoBytes > nPreviousIo)
			{
				return Fail(out_arrDiagnostics, "Mip-suffix allocation sizes must be positive, bounded and nonincreasing.");
			}
			nPreviousGpu = stMip.nGpuBytes;
			nPreviousUpload = stMip.nUploadBytes;
			nPreviousIo = stMip.nIoBytes;
		}
		if (nPreviousGpu > in_stConfig.nGpuBudget - nFallbackBytes || nPreviousUpload > in_stConfig.nUploadBudget || nPreviousIo > in_stConfig.nIoBudget)
		{
			return Fail(out_arrDiagnostics, "Coarsest fallback resources must fit the GPU floor and individual upload budget.");
		}
		nFallbackBytes += nPreviousGpu;
		Record stRecord;
		stRecord.stDescription = stDescription;
		stRecord.nWantedMip = static_cast<std::uint32_t>(stDescription.arrMips.size() - 1);
		arrCandidate.push_back(std::move(stRecord));
	}
	std::sort(arrCandidate.begin(), arrCandidate.end(), [](const Record &stLeft, const Record &stRight)
			  { return stLeft.stDescription.nTextureId < stRight.stDescription.nTextureId; });
	for (std::size_t nIndex = 1; nIndex < arrCandidate.size(); ++nIndex)
	{
		if (arrCandidate[nIndex - 1].stDescription.nTextureId == arrCandidate[nIndex].stDescription.nTextureId)
		{
			return Fail(out_arrDiagnostics, "Texture identities must be unique.");
		}
	}
	arrRecords = std::move(arrCandidate);
	stConfig = in_stConfig;
	stTelemetry.nFallbackBudgetBytes = nFallbackBytes;
	stTelemetry.nGpuReservedBytes = nFallbackBytes;
	stTelemetry.nPeakGpuReservedBytes = nFallbackBytes;
	bInitialized = true;
	return true;
}

std::uint32_t TextureResidency::FindIndex(std::uint64_t nTextureId) const noexcept
{
	const std::vector<Record>::const_iterator it = std::lower_bound(arrRecords.begin(), arrRecords.end(), nTextureId,
																	[](const Record &stRecord, std::uint64_t nId)
																	{
																		return stRecord.stDescription.nTextureId < nId;
																	});
	return it != arrRecords.end() && it->stDescription.nTextureId == nTextureId ? static_cast<std::uint32_t>(it - arrRecords.begin()) : INVALID_TEXTURE;
}

bool TextureResidency::ValidTick(std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics) const
{
	return bInitialized && in_nTick >= nTick ? true : Fail(out_arrDiagnostics, "Owner must be initialized and logical ticks must not go backwards.");
}

bool TextureResidency::FindTicket(TextureLoadTicket stTicket, std::uint32_t &out_nIndex, Assets::Diagnostics &out_arrDiagnostics) const
{
	const std::uint32_t nIndex = FindIndex(stTicket.nTextureId);
	if (!bInitialized || nIndex == INVALID_TEXTURE || stTicket.nGeneration == 0 ||
		arrRecords[nIndex].stPending.stTicket.nGeneration != stTicket.nGeneration ||
		arrRecords[nIndex].stPending.stTicket.nFirstMip != stTicket.nFirstMip)
	{
		return Fail(out_arrDiagnostics, "Completion ticket is unknown, cancelled or stale.");
	}
	out_nIndex = nIndex;
	return true;
}

void TextureResidency::RetireCurrent(Record &stRecord)
{
	if (stRecord.stCurrent.stHandle.nResourceToken == 0)
	{
		return;
	}
	stTelemetry.nResidentBytes -= stRecord.stCurrent.nGpuBytes;
	stTelemetry.nRetiredBytes += stRecord.stCurrent.nGpuBytes;
	arrRetired.push_back(stRecord.stCurrent);
	stRecord.stCurrent = {};
}

void TextureResidency::ClearPending(Record &stRecord, bool bReleaseGpuReservation) noexcept
{
	const Pending &stPending = stRecord.stPending;
	stTelemetry.nUploadReservedBytes -= stPending.stAllocation.nUploadBytes;
	if (stPending.bIoHeld)
	{
		stTelemetry.nIoReservedBytes -= stPending.stAllocation.nIoBytes;
	}
	stTelemetry.nPendingGpuBytes -= stPending.stAllocation.nGpuBytes;
	--stTelemetry.nPendingCount;
	if (bReleaseGpuReservation)
	{
		if (stPending.stTicket.nFirstMip + 1 != stRecord.stDescription.arrMips.size())
		{
			stTelemetry.nGpuReservedBytes -= stPending.stAllocation.nGpuBytes;
		}
		--stTelemetry.nTrackedVersions;
	}
	stRecord.stPending = {};
	stRecord.eState = TextureLoadState::Idle;
}

void TextureResidency::RecordFailure(Record &stRecord, std::uint64_t in_nTick) noexcept
{
	stRecord.eState = TextureLoadState::RetryDelay;
	stRecord.bRetryOverflow = stConfig.nRetryDelayTicks > UINT64_MAX - in_nTick;
	stRecord.nRetryAfterTick = stRecord.bRetryOverflow ? UINT64_MAX : in_nTick + stConfig.nRetryDelayTicks;
	Increment(stTelemetry.nFailures);
}

bool TextureResidency::SetDemand(const std::vector<TextureMipDemand> &arrDemand, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidTick(in_nTick, out_arrDiagnostics))
	{
		return false;
	}
	if (arrDemand.size() > MAX_TEXTURES)
	{
		return Fail(out_arrDiagnostics, "Demand list exceeds the bounded texture count.");
	}
	std::vector<std::uint32_t> arrWanted;
	std::vector<double> arrPriority(arrRecords.size(), 0);
	arrWanted.reserve(arrRecords.size());
	for (const Record &stRecord : arrRecords)
	{
		arrWanted.push_back(static_cast<std::uint32_t>(stRecord.stDescription.arrMips.size() - 1));
	}
	for (const TextureMipDemand &stDemand : arrDemand)
	{
		const std::uint32_t nIndex = FindIndex(stDemand.nTextureId);
		if (nIndex == INVALID_TEXTURE || stDemand.nFirstMip >= arrRecords[nIndex].stDescription.arrMips.size() ||
			!std::isfinite(stDemand.dPriority) || stDemand.dPriority < 0)
		{
			return Fail(out_arrDiagnostics, "Demand needs a known texture, valid first mip and finite nonnegative priority.");
		}
		arrWanted[nIndex] = (std::min)(arrWanted[nIndex], stDemand.nFirstMip);
		arrPriority[nIndex] = (std::max)(arrPriority[nIndex], stDemand.dPriority);
	}
	nTick = in_nTick;
	for (std::size_t nIndex = 0; nIndex < arrRecords.size(); ++nIndex)
	{
		Record &stRecord = arrRecords[nIndex];
		stRecord.nWantedMip = arrWanted[nIndex];
		stRecord.dPriority = arrPriority[nIndex];
		if (stRecord.stCurrent.stHandle.nResourceToken != 0 && stRecord.nWantedMip > stRecord.stCurrent.stHandle.nFirstMip)
		{
			RetireCurrent(stRecord);
		}
		if (stRecord.stPending.stTicket.nGeneration != 0 && stRecord.stPending.stTicket.nFirstMip < stRecord.nWantedMip && !stRecord.stPending.bCancelled)
		{
			Increment(stTelemetry.nCancellations);
			if (stRecord.eState == TextureLoadState::UploadReady)
			{
				ClearPending(stRecord, true);
			}
			else
			{
				stRecord.stPending.bCancelled = true;
			}
		}
	}
	return true;
}

bool TextureResidency::BeginNextLoad(std::uint64_t in_nTick, TextureScheduleResult &out_eResult,
									 TextureLoadTicket &out_stTicket, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidTick(in_nTick, out_arrDiagnostics))
	{
		return false;
	}
	std::uint32_t nBest = INVALID_TEXTURE;
	std::uint32_t nBestMip = 0;
	bool bAnyBlocked = false;
	bool bBestFallback = false;
	for (std::uint32_t nIndex = 0; nIndex < arrRecords.size(); ++nIndex)
	{
		const Record &stRecord = arrRecords[nIndex];
		if (stRecord.eState != TextureLoadState::Idle &&
			(stRecord.eState != TextureLoadState::RetryDelay || stRecord.bRetryOverflow || in_nTick < stRecord.nRetryAfterTick))
		{
			continue;
		}
		const bool bFallback = stRecord.stFallback.stHandle.nResourceToken == 0;
		const std::uint32_t nMip = bFallback ? static_cast<std::uint32_t>(stRecord.stDescription.arrMips.size() - 1) : stRecord.nWantedMip;
		const TextureResidentHandle &stResident = stRecord.stCurrent.stHandle.nResourceToken != 0 ? stRecord.stCurrent.stHandle : stRecord.stFallback.stHandle;
		if (!bFallback && stResident.nFirstMip == nMip)
		{
			continue;
		}
		const TextureMipAllocation &stAllocation = stRecord.stDescription.arrMips[nMip];
		if (stRecord.nGeneration == UINT64_MAX || stTelemetry.nPendingCount >= stConfig.nMaximumPending ||
			stTelemetry.nTrackedVersions >= stConfig.nMaximumVersions || stAllocation.nUploadBytes > stConfig.nUploadBudget - stTelemetry.nUploadReservedBytes ||
			stAllocation.nIoBytes > stConfig.nIoBudget - stTelemetry.nIoReservedBytes ||
			(!bFallback && stAllocation.nGpuBytes > stConfig.nGpuBudget - stTelemetry.nGpuReservedBytes))
		{
			bAnyBlocked = true;
			continue;
		}
		if (nBest == INVALID_TEXTURE || (bFallback && !bBestFallback) || (bFallback == bBestFallback && stRecord.dPriority > arrRecords[nBest].dPriority))
		{
			nBest = nIndex;
			nBestMip = nMip;
			bBestFallback = bFallback;
		}
	}
	nTick = in_nTick;
	if (nBest == INVALID_TEXTURE)
	{
		out_eResult = bAnyBlocked ? TextureScheduleResult::BudgetBlocked : TextureScheduleResult::NoWork;
		out_stTicket = {};
		if (bAnyBlocked)
		{
			Increment(stTelemetry.nBudgetStalls);
		}
		return true;
	}
	Record &stRecord = arrRecords[nBest];
	++stRecord.nGeneration;
	stRecord.stPending.stTicket = { stRecord.stDescription.nTextureId, stRecord.nGeneration, nBestMip };
	stRecord.stPending.stAllocation = stRecord.stDescription.arrMips[nBestMip];
	stRecord.stPending.bIoHeld = true;
	stRecord.eState = TextureLoadState::Loading;
	stRecord.bRetryOverflow = false;
	stRecord.nRetryAfterTick = 0;
	const TextureMipAllocation &stAllocation = stRecord.stPending.stAllocation;
	stTelemetry.nPendingGpuBytes += stAllocation.nGpuBytes;
	stTelemetry.nUploadReservedBytes += stAllocation.nUploadBytes;
	stTelemetry.nIoReservedBytes += stAllocation.nIoBytes;
	if (!bBestFallback)
	{
		stTelemetry.nGpuReservedBytes += stAllocation.nGpuBytes;
	}
	++stTelemetry.nPendingCount;
	++stTelemetry.nTrackedVersions;
	Increment(stTelemetry.nLoadsStarted);
	stTelemetry.nPeakGpuReservedBytes = (std::max)(stTelemetry.nPeakGpuReservedBytes, stTelemetry.nGpuReservedBytes);
	stTelemetry.nPeakUploadReservedBytes = (std::max)(stTelemetry.nPeakUploadReservedBytes, stTelemetry.nUploadReservedBytes);
	stTelemetry.nPeakIoReservedBytes = (std::max)(stTelemetry.nPeakIoReservedBytes, stTelemetry.nIoReservedBytes);
	out_stTicket = stRecord.stPending.stTicket;
	out_eResult = TextureScheduleResult::Started;
	return true;
}

bool TextureResidency::FinishLoad(TextureLoadTicket stTicket, bool bSucceeded, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = 0;
	if (!ValidTick(in_nTick, out_arrDiagnostics) || !FindTicket(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	if (arrRecords[nIndex].eState != TextureLoadState::Loading)
	{
		return Fail(out_arrDiagnostics, "Only an active IO ticket can finish loading.");
	}
	nTick = in_nTick;
	Record &stRecord = arrRecords[nIndex];
	const bool bCancelled = stRecord.stPending.bCancelled;
	if (bCancelled || !bSucceeded)
	{
		ClearPending(stRecord, true);
		if (!bCancelled)
		{
			RecordFailure(stRecord, in_nTick);
		}
	}
	else
	{
		stRecord.eState = TextureLoadState::UploadReady;
	}
	return true;
}

bool TextureResidency::FailUpload(TextureLoadTicket stTicket, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = 0;
	if (!ValidTick(in_nTick, out_arrDiagnostics) || !FindTicket(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	Record &stRecord = arrRecords[nIndex];
	if (stRecord.eState != TextureLoadState::UploadReady)
	{
		return Fail(out_arrDiagnostics, "Only an unsubmitted upload can release its reservations on failure.");
	}
	nTick = in_nTick;
	ClearPending(stRecord, true);
	RecordFailure(stRecord, in_nTick);
	return true;
}

bool TextureResidency::Cancel(TextureLoadTicket stTicket, std::uint64_t in_nTick, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = 0;
	if (!ValidTick(in_nTick, out_arrDiagnostics) || !FindTicket(stTicket, nIndex, out_arrDiagnostics))
	{
		return false;
	}
	nTick = in_nTick;
	Record &stRecord = arrRecords[nIndex];
	if (!stRecord.stPending.bCancelled)
	{
		Increment(stTelemetry.nCancellations);
	}
	if (stRecord.eState == TextureLoadState::UploadReady)
	{
		ClearPending(stRecord, true);
	}
	else
	{
		stRecord.stPending.bCancelled = true;
	}
	return true;
}

bool TextureResidency::SubmitUpload(TextureLoadTicket stTicket, std::uint64_t nResourceToken,
									std::uint64_t nCopyFence, Assets::Diagnostics &out_arrDiagnostics)
{
	std::uint32_t nIndex = 0;
	if (!FindTicket(stTicket, nIndex, out_arrDiagnostics) || arrRecords[nIndex].eState != TextureLoadState::UploadReady ||
		nResourceToken == UINT64_MAX || nResourceToken <= nLatestResourceToken || nCopyFence == UINT64_MAX ||
		nCopyFence < nSubmittedCopy || nCopyFence <= nCompletedCopy)
	{
		return Fail(out_arrDiagnostics, "Upload needs a ready ticket, a new nonzero resource token and a nondecreasing pending copy fence.");
	}
	Record &stRecord = arrRecords[nIndex];
	stTelemetry.nIoReservedBytes -= stRecord.stPending.stAllocation.nIoBytes;
	stRecord.stPending.bIoHeld = false;
	stRecord.stPending.nResourceToken = nResourceToken;
	stRecord.stPending.nCopyFence = nCopyFence;
	stRecord.eState = TextureLoadState::UploadPending;
	nLatestResourceToken = nResourceToken;
	nSubmittedCopy = nCopyFence;
	return true;
}

bool TextureResidency::AdvanceFences(std::uint64_t nCopy, std::uint64_t nRender, std::uint64_t in_nTick,
									 std::vector<TextureResourceRelease> &out_arrReleased, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!ValidTick(in_nTick, out_arrDiagnostics) || nCopy == UINT64_MAX || nRender == UINT64_MAX || nCopy < nCompletedCopy || nRender < nCompletedRender)
	{
		return Fail(out_arrDiagnostics, "Completed fence values must advance monotonically and cannot be device-removal sentinels.");
	}
	nTick = in_nTick;
	nCompletedCopy = nCopy;
	nCompletedRender = nRender;
	std::vector<TextureResourceRelease> arrReleased;
	for (Record &stRecord : arrRecords)
	{
		if (stRecord.eState != TextureLoadState::UploadPending || stRecord.stPending.nCopyFence > nCopy)
		{
			continue;
		}
		if (stRecord.stPending.bCancelled)
		{
			arrReleased.push_back({ stRecord.stPending.nResourceToken, stRecord.stPending.stAllocation.nGpuBytes });
			ClearPending(stRecord, true);
			continue;
		}
		Version stVersion;
		stVersion.stHandle = { stRecord.stDescription.nTextureId, stRecord.stPending.stTicket.nGeneration,
							   stRecord.stPending.nResourceToken, stRecord.stPending.stTicket.nFirstMip };
		stVersion.nGpuBytes = stRecord.stPending.stAllocation.nGpuBytes;
		const bool bFallback = stVersion.stHandle.nFirstMip + 1 == stRecord.stDescription.arrMips.size();
		if (bFallback)
		{
			stRecord.stFallback = stVersion;
		}
		else
		{
			RetireCurrent(stRecord);
			stRecord.stCurrent = stVersion;
		}
		stTelemetry.nResidentBytes += stVersion.nGpuBytes;
		ClearPending(stRecord, false);
		Increment(stTelemetry.nInstalls);
	}
	std::size_t nKept = 0;
	for (std::size_t nIndex = 0; nIndex < arrRetired.size(); ++nIndex)
	{
		const Version stVersion = arrRetired[nIndex];
		if (stVersion.nLastRenderFence > nRender)
		{
			arrRetired[nKept++] = stVersion;
			continue;
		}
		arrReleased.push_back({ stVersion.stHandle.nResourceToken, stVersion.nGpuBytes });
		stTelemetry.nRetiredBytes -= stVersion.nGpuBytes;
		stTelemetry.nGpuReservedBytes -= stVersion.nGpuBytes;
		--stTelemetry.nTrackedVersions;
	}
	arrRetired.resize(nKept);
	out_arrReleased = std::move(arrReleased);
	return true;
}

bool TextureResidency::GetResident(std::uint64_t nTextureId, TextureResidentHandle &out_stHandle) const noexcept
{
	const std::uint32_t nIndex = FindIndex(nTextureId);
	if (!bInitialized || nIndex == INVALID_TEXTURE)
	{
		return false;
	}
	const Record &stRecord = arrRecords[nIndex];
	const TextureResidentHandle &stHandle = stRecord.stCurrent.stHandle.nResourceToken != 0 ? stRecord.stCurrent.stHandle : stRecord.stFallback.stHandle;
	if (stHandle.nResourceToken == 0)
	{
		return false;
	}
	out_stHandle = stHandle;
	return true;
}

bool TextureResidency::GetStatus(std::uint64_t nTextureId, TextureResidencyStatus &out_stStatus) const noexcept
{
	const std::uint32_t nIndex = FindIndex(nTextureId);
	if (!bInitialized || nIndex == INVALID_TEXTURE)
	{
		return false;
	}
	const Record &stRecord = arrRecords[nIndex];
	TextureResidencyStatus stStatus;
	stStatus.nWantedFirstMip = stRecord.nWantedMip;
	stStatus.eLoadState = stRecord.eState;
	stStatus.stPending = stRecord.stPending.stTicket;
	stStatus.bCancellationRequested = stRecord.stPending.bCancelled;
	stStatus.bHasResident = GetResident(nTextureId, stStatus.stResident);
	stStatus.nRetryAfterTick = stRecord.nRetryAfterTick;
	out_stStatus = stStatus;
	return true;
}

bool TextureResidency::MarkUsed(TextureResidentHandle stHandle, std::uint64_t nRenderFence, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::uint32_t nIndex = FindIndex(stHandle.nTextureId);
	TextureResidentHandle stCurrent;
	if (!GetResident(stHandle.nTextureId, stCurrent) || !SameHandle(stCurrent, stHandle) ||
		nRenderFence == UINT64_MAX || nRenderFence <= nCompletedRender || nRenderFence < nSubmittedRender)
	{
		return Fail(out_arrDiagnostics, "Draw must use the current generation and a valid nondecreasing render submission fence.");
	}
	Record &stRecord = arrRecords[nIndex];
	Version &stVersion = stRecord.stCurrent.stHandle.nResourceToken != 0 ? stRecord.stCurrent : stRecord.stFallback;
	stVersion.nLastRenderFence = (std::max)(stVersion.nLastRenderFence, nRenderFence);
	nSubmittedRender = nRenderFence;
	return true;
}

bool TextureResidency::ReleaseAll(std::uint64_t nCopy, std::uint64_t nRender,
								  std::vector<TextureResourceRelease> &out_arrReleased, Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || nCopy == UINT64_MAX || nRender == UINT64_MAX || nCopy < nCompletedCopy || nRender < nCompletedRender || stTelemetry.nPendingCount != 0)
	{
		return Fail(out_arrDiagnostics, "Release requires an initialized owner, completed fences and no pending IO or uploads.");
	}
	for (const Record &stRecord : arrRecords)
	{
		if (stRecord.stFallback.nLastRenderFence > nRender || stRecord.stCurrent.nLastRenderFence > nRender)
		{
			return Fail(out_arrDiagnostics, "A current resource is still used by an unretired draw.");
		}
	}
	for (const Version &stVersion : arrRetired)
	{
		if (stVersion.nLastRenderFence > nRender)
		{
			return Fail(out_arrDiagnostics, "A replaced resource is still used by an unretired draw.");
		}
	}
	std::vector<TextureResourceRelease> arrReleased;
	for (const Record &stRecord : arrRecords)
	{
		for (const Version *pVersion : { &stRecord.stFallback, &stRecord.stCurrent })
		{
			if (pVersion->stHandle.nResourceToken != 0)
			{
				arrReleased.push_back({ pVersion->stHandle.nResourceToken, pVersion->nGpuBytes });
			}
		}
	}
	for (const Version &stVersion : arrRetired)
	{
		arrReleased.push_back({ stVersion.stHandle.nResourceToken, stVersion.nGpuBytes });
	}
	arrRecords.clear();
	arrRetired.clear();
	stTelemetry = {};
	nTick = nCompletedCopy = nCompletedRender = nSubmittedCopy = nSubmittedRender = nLatestResourceToken = 0;
	bInitialized = false;
	out_arrReleased = std::move(arrReleased);
	return true;
}

const TextureResidencyTelemetry &TextureResidency::Telemetry() const noexcept
{
	return stTelemetry;
}

} // namespace EngineNext::Rendering
