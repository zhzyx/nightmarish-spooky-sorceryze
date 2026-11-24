/**************************************************************************/
/*  ShadowPageCache.cpp                                                   */
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

#include "engine_next/Rendering/ShadowPageCache.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

bool Error(Assets::Diagnostics &out_arrDiagnostics, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "virtual_shadow", "$.shadows.virtual_pages", pMessage);
	return false;
}

bool ValidProjection(const ShadowData &stProjection)
{
	for (const ShadowCascade &stCascade : stProjection.arrCascades)
	{
		for (double dValue : stCascade.arrViewProjection)
		{
			if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
			{
				return false;
			}
		}
		const std::array<double, 16> &arrMatrix = stCascade.arrViewProjection;
		if (arrMatrix[3] != 0 || arrMatrix[7] != 0 || arrMatrix[11] != 0 || arrMatrix[15] != 1)
		{
			return false;
		}
		for (std::size_t nRow = 0; nRow < 3; ++nRow)
		{
			double dLength = 0;
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				dLength += arrMatrix[nAxis * 4 + nRow] * arrMatrix[nAxis * 4 + nRow];
			}
			if (dLength <= 0 || !std::isfinite(dLength))
			{
				return false;
			}
		}
		for (std::size_t nLeft = 0; nLeft < 3; ++nLeft)
		{
			for (std::size_t nRight = nLeft + 1; nRight < 3; ++nRight)
			{
				double dDot = 0;
				double dLeft = 0;
				double dRight = 0;
				for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
				{
					const double dA = arrMatrix[nAxis * 4 + nLeft];
					const double dB = arrMatrix[nAxis * 4 + nRight];
					dDot += dA * dB;
					dLeft += dA * dA;
					dRight += dB * dB;
				}
				if (dDot * dDot > dLeft * dRight * 1.0e-12)
				{
					return false;
				}
			}
		}
	}
	return true;
}

bool SameProjection(const ShadowCascade &stLeft, const ShadowCascade &stRight, bool bIncludeDepth)
{
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < (bIncludeDepth ? 3U : 2U); ++nRow)
		{
			if (static_cast<float>(stLeft.arrViewProjection[nColumn * 4 + nRow]) !=
				static_cast<float>(stRight.arrViewProjection[nColumn * 4 + nRow]))
			{
				return false;
			}
		}
	}
	return true;
}

bool ValidBounds(const WorldBounds &stBounds)
{
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		if (!std::isfinite(stBounds.arrMinimum[nAxis]) || !std::isfinite(stBounds.arrMaximum[nAxis]) ||
			stBounds.arrMinimum[nAxis] > stBounds.arrMaximum[nAxis] ||
			std::abs(stBounds.arrMinimum[nAxis]) > std::numeric_limits<float>::max() ||
			std::abs(stBounds.arrMaximum[nAxis]) > std::numeric_limits<float>::max())
		{
			return false;
		}
	}
	return true;
}

struct PageRectangle
{
	std::uint32_t nMinX = 0;
	std::uint32_t nMinY = 0;
	std::uint32_t nMaxX = 0;
	std::uint32_t nMaxY = 0;
	bool bEmpty = true;
};

PageRectangle Rectangle(double dMinU, double dMinV, double dMaxU, double dMaxV, std::uint32_t nAxisPages)
{
	PageRectangle stResult;
	if (dMaxU < 0 || dMaxV < 0 || dMinU > 1 || dMinV > 1)
	{
		return stResult;
	}
	stResult.bEmpty = false;
	const double dLast = static_cast<double>(nAxisPages - 1);
	stResult.nMinX = static_cast<std::uint32_t>((std::min)(dLast, std::floor((std::max)(0.0, dMinU) * nAxisPages)));
	stResult.nMinY = static_cast<std::uint32_t>((std::min)(dLast, std::floor((std::max)(0.0, dMinV) * nAxisPages)));
	stResult.nMaxX = static_cast<std::uint32_t>((std::min)(dLast, std::floor((std::max)(0.0, dMaxU) * nAxisPages)));
	stResult.nMaxY = static_cast<std::uint32_t>((std::min)(dLast, std::floor((std::max)(0.0, dMaxV) * nAxisPages)));
	return stResult;
}

PageRectangle ProjectBounds(const WorldBounds &stBounds, const ShadowCascade &stCascade, std::uint32_t nResolution)
{
	std::array<double, 2> arrMin{ std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity() };
	std::array<double, 2> arrMax{ -std::numeric_limits<double>::infinity(), -std::numeric_limits<double>::infinity() };
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		for (std::size_t nRow = 0; nRow < 2; ++nRow)
		{
			double dValue = static_cast<float>(stCascade.arrViewProjection[12 + nRow]);
			double dMagnitude = std::abs(dValue);
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const double dPoint = (nCorner & (1U << nAxis)) != 0 ? stBounds.arrMaximum[nAxis] : stBounds.arrMinimum[nAxis];
				const double dTerm = static_cast<float>(stCascade.arrViewProjection[nAxis * 4 + nRow]) * dPoint;
				dValue += dTerm;
				dMagnitude += std::abs(dTerm);
			}
			// Cover binary32 position conversion and the shader dot-product roundoff.
			const double dError = (dMagnitude + 1) * 16 * std::numeric_limits<float>::epsilon();
			arrMin[nRow] = (std::min)(arrMin[nRow], dValue - dError);
			arrMax[nRow] = (std::max)(arrMax[nRow], dValue + dError);
		}
	}
	const double dBorder = static_cast<double>(SHADOW_PAGE_BORDER) / nResolution;
	return Rectangle(arrMin[0] * 0.5 + 0.5 - dBorder, 0.5 - arrMax[1] * 0.5 - dBorder,
					 arrMax[0] * 0.5 + 0.5 + dBorder, 0.5 - arrMin[1] * 0.5 + dBorder, nResolution / SHADOW_PAGE_TEXELS);
}

bool FeedbackTransform(const ShadowCascade &stFrom, const ShadowCascade &stTo, std::array<double, 4> &out_arrScaleOffset)
{
	for (std::size_t nRow = 0; nRow < 2; ++nRow)
	{
		double dLengthFrom = 0;
		double dLengthTo = 0;
		double dDot = 0;
		for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
		{
			const double dFrom = stFrom.arrViewProjection[nAxis * 4 + nRow];
			const double dTo = stTo.arrViewProjection[nAxis * 4 + nRow];
			dLengthFrom += dFrom * dFrom;
			dLengthTo += dTo * dTo;
			dDot += dFrom * dTo;
		}
		if (dDot <= 0 || dDot * dDot < dLengthFrom * dLengthTo * (1 - 1.0e-12))
		{
			return false;
		}
		const double dScale = dDot / dLengthFrom;
		const double dClipOffset = stTo.arrViewProjection[12 + nRow] - dScale * stFrom.arrViewProjection[12 + nRow];
		out_arrScaleOffset[nRow] = dScale;
		out_arrScaleOffset[nRow + 2] = (1 - dScale + (nRow == 0 ? dClipOffset : -dClipOffset)) * 0.5;
		if (!std::isfinite(dScale) || !std::isfinite(out_arrScaleOffset[nRow + 2]))
		{
			return false;
		}
	}
	return true;
}

} // namespace

bool ValidateVirtualShadowSettings(const VirtualShadowSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics)
{
	const bool bResolution = stSettings.nResolution >= 2048 && stSettings.nResolution <= 16384 &&
			(stSettings.nResolution & (stSettings.nResolution - 1)) == 0;
	if (!bResolution || stSettings.nPhysicalPages < 16 || stSettings.nPhysicalPages > 2048 ||
		stSettings.nUpdatesPerFrame == 0 || stSettings.nUpdatesPerFrame > stSettings.nPhysicalPages ||
		stSettings.nMemoryBudget < 8ULL * 1024 * 1024 || stSettings.nMemoryBudget > 1024ULL * 1024 * 1024)
	{
		return Error(out_arrDiagnostics, "Invalid virtual resolution, physical page count, update count or memory budget.");
	}
	const std::uint64_t nAxis = stSettings.nResolution / SHADOW_PAGE_TEXELS;
	const std::uint64_t nLogical = 4 * nAxis * nAxis;
	const std::uint64_t nPool = static_cast<std::uint64_t>(stSettings.nPhysicalPages) * SHADOW_PAGE_PHYSICAL_TEXELS * SHADOW_PAGE_PHYSICAL_TEXELS * 4;
	// Logical payload lower bound. The D3D owner additionally validates actual
	// allocation alignment against this same caller-provided total budget.
	const std::uint64_t nPayload = nPool + 3 * (nLogical * (sizeof(ShadowPageTableEntry) * 2 + 8) + 65536);
	return nPayload <= stSettings.nMemoryBudget || Error(out_arrDiagnostics, "Virtual shadow resource payload exceeds its memory budget.");
}

bool BuildShadowPageProjection(const ShadowCascade &stCascade, std::uint32_t nResolution,
							   std::uint32_t nPageX, std::uint32_t nPageY, std::array<float, 16> &out_arrProjection) noexcept
{
	if (nResolution < SHADOW_PAGE_TEXELS || nResolution > 16384 || nResolution % SHADOW_PAGE_TEXELS != 0 ||
		nPageX >= nResolution / SHADOW_PAGE_TEXELS || nPageY >= nResolution / SHADOW_PAGE_TEXELS ||
		stCascade.arrViewProjection[3] != 0 || stCascade.arrViewProjection[7] != 0 ||
		stCascade.arrViewProjection[11] != 0 || stCascade.arrViewProjection[15] != 1)
	{
		return false;
	}
	std::array<float, 16> arrOutput{};
	const double dScale = static_cast<double>(nResolution) / SHADOW_PAGE_PHYSICAL_TEXELS;
	const double dOffsetX = (static_cast<double>(nResolution) - 2.0 * (nPageX * SHADOW_PAGE_TEXELS - static_cast<double>(SHADOW_PAGE_BORDER)) - SHADOW_PAGE_PHYSICAL_TEXELS) / SHADOW_PAGE_PHYSICAL_TEXELS;
	const double dOffsetY = (-static_cast<double>(nResolution) + 2.0 * (nPageY * SHADOW_PAGE_TEXELS - static_cast<double>(SHADOW_PAGE_BORDER)) + SHADOW_PAGE_PHYSICAL_TEXELS) / SHADOW_PAGE_PHYSICAL_TEXELS;
	for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
	{
		for (std::size_t nRow = 0; nRow < 4; ++nRow)
		{
			double dValue = stCascade.arrViewProjection[nColumn * 4 + nRow];
			if (nRow < 2)
			{
				dValue = dValue * dScale + stCascade.arrViewProjection[nColumn * 4 + 3] * (nRow == 0 ? dOffsetX : dOffsetY);
			}
			if (!std::isfinite(dValue) || std::abs(dValue) > std::numeric_limits<float>::max())
			{
				return false;
			}
			arrOutput[nColumn * 4 + nRow] = static_cast<float>(dValue);
		}
	}
	out_arrProjection = arrOutput;
	return true;
}

bool IntersectsShadowPage(const WorldBounds &stBounds, const std::array<float, 16> &arrProjection) noexcept
{
	if (!ValidBounds(stBounds))
	{
		return true;
	}
	for (float fValue : arrProjection)
	{
		if (!std::isfinite(fValue))
		{
			return true;
		}
	}
	if (arrProjection[3] != 0 || arrProjection[7] != 0 || arrProjection[11] != 0 || arrProjection[15] != 1)
	{
		return true;
	}
	std::array<bool, 6> arrOutside{ true, true, true, true, true, true };
	for (std::uint32_t nCorner = 0; nCorner < 8; ++nCorner)
	{
		std::array<double, 3> arrClip{};
		std::array<double, 3> arrMagnitude{};
		for (std::size_t nRow = 0; nRow < 3; ++nRow)
		{
			arrClip[nRow] = arrProjection[12 + nRow];
			arrMagnitude[nRow] = std::abs(arrClip[nRow]);
			for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
			{
				const double dTerm = arrProjection[nAxis * 4 + nRow] *
						((nCorner & (1U << nAxis)) != 0 ? stBounds.arrMaximum[nAxis] : stBounds.arrMinimum[nAxis]);
				arrClip[nRow] += dTerm;
				arrMagnitude[nRow] += std::abs(dTerm);
			}
		}
		const double dMargin = (1 + arrMagnitude[0] + arrMagnitude[1] + arrMagnitude[2]) * 16 * std::numeric_limits<float>::epsilon();
		arrOutside[0] = arrOutside[0] && arrClip[0] < -1 - dMargin;
		arrOutside[1] = arrOutside[1] && arrClip[0] > 1 + dMargin;
		arrOutside[2] = arrOutside[2] && arrClip[1] < -1 - dMargin;
		arrOutside[3] = arrOutside[3] && arrClip[1] > 1 + dMargin;
		arrOutside[4] = arrOutside[4] && arrClip[2] < -dMargin;
		arrOutside[5] = arrOutside[5] && arrClip[2] > 1 + dMargin;
	}
	return std::find(arrOutside.begin(), arrOutside.end(), true) == arrOutside.end();
}

bool ShadowPageCache::Initialize(const VirtualShadowSettings &stInput, Assets::Diagnostics &out_arrDiagnostics)
{
	if (bInitialized || !ValidateVirtualShadowSettings(stInput, out_arrDiagnostics))
	{
		return Error(out_arrDiagnostics, "Cache initialization requires an unused owner and valid settings.");
	}
	stSettings = stInput;
	const std::uint32_t nAxis = stSettings.nResolution / SHADOW_PAGE_TEXELS;
	stCommitted.arrTable.resize(4 * nAxis * nAxis);
	stCommitted.arrPhysical.resize(stSettings.nPhysicalPages);
	bInitialized = true;
	return true;
}

bool ShadowPageCache::Prepare(const ShadowData &stProjection, const std::vector<WorldBounds> &arrCasters,
							  const std::vector<std::uint32_t> &arrChangedDraws, const std::vector<ShadowPageFeedback> &arrFeedback,
							  Assets::Diagnostics &out_arrDiagnostics)
{
	if (!bInitialized || bPending || stCommitted.nEpoch == UINT64_MAX || stCommitted.nSceneRevision == UINT64_MAX ||
		!ValidProjection(stProjection) || arrCasters.size() > 65536 || arrFeedback.size() > 3)
	{
		return Error(out_arrDiagnostics, "Prepare requires a valid projection and an idle initialized cache.");
	}
	for (const WorldBounds &stBounds : arrCasters)
	{
		if (!ValidBounds(stBounds))
		{
			return Error(out_arrDiagnostics, "Caster bounds must be finite, ordered and representable.");
		}
	}
	std::vector<bool> arrForced(arrCasters.size(), false);
	for (std::uint32_t nDraw : arrChangedDraws)
	{
		if (nDraw >= arrCasters.size() || arrForced[nDraw])
		{
			return Error(out_arrDiagnostics, "Changed draw IDs must be unique and in range.");
		}
		arrForced[nDraw] = true;
	}
	for (const ShadowPageFeedback &stFeedback : arrFeedback)
	{
		if (stFeedback.arrCoverage.size() != LogicalPages() || !ValidProjection(stFeedback.stProjection))
		{
			return Error(out_arrDiagnostics, "Feedback must match the logical page count and contain a valid projection.");
		}
	}
	State stCandidate = stCommitted;
	if (!arrFeedback.empty())
	{
		stCandidate.arrFeedback = arrFeedback;
	}
	ShadowPagePlan stCandidatePlan;
	stCandidatePlan.nEpoch = stCandidate.nEpoch + 1;
	const std::uint32_t nAxis = stSettings.nResolution / SHADOW_PAGE_TEXELS;
	const std::uint32_t nPerCascade = nAxis * nAxis;
	std::vector<bool> arrDirty(LogicalPages(), false);
	bool bSceneChanged = stCandidate.nEpoch == 0 || stCandidate.arrCasters.size() != arrCasters.size();
	if (!bSceneChanged)
	{
		for (std::size_t nDraw = 0; nDraw < arrCasters.size(); ++nDraw)
		{
			if (arrForced[nDraw] || stCandidate.arrCasters[nDraw].arrMinimum != arrCasters[nDraw].arrMinimum ||
				stCandidate.arrCasters[nDraw].arrMaximum != arrCasters[nDraw].arrMaximum)
			{
				bSceneChanged = true;
				break;
			}
		}
	}
	for (std::uint32_t nCascade = 0; nCascade < 4; ++nCascade)
	{
		const bool bSameXY = stCandidate.nEpoch != 0 && SameProjection(stProjection.arrCascades[nCascade], stCandidate.stProjection.arrCascades[nCascade], false);
		bSceneChanged = bSceneChanged || !SameProjection(stProjection.arrCascades[nCascade], stCandidate.stProjection.arrCascades[nCascade], true);
		if (!stSettings.bCache || !bSameXY || stCandidate.arrCasters.size() != arrCasters.size())
		{
			std::fill(arrDirty.begin() + nCascade * nPerCascade, arrDirty.begin() + (nCascade + 1) * nPerCascade, true);
			continue;
		}
		for (std::size_t nDraw = 0; nDraw < arrCasters.size(); ++nDraw)
		{
			const WorldBounds &stPrevious = stCandidate.arrCasters[nDraw];
			if (!arrForced[nDraw] && stPrevious.arrMinimum == arrCasters[nDraw].arrMinimum && stPrevious.arrMaximum == arrCasters[nDraw].arrMaximum)
			{
				continue;
			}
			for (const WorldBounds *pBounds : { &stPrevious, &arrCasters[nDraw] })
			{
				const PageRectangle stRange = ProjectBounds(*pBounds, stProjection.arrCascades[nCascade], stSettings.nResolution);
				if (!stRange.bEmpty)
				{
					for (std::uint32_t nY = stRange.nMinY; nY <= stRange.nMaxY; ++nY)
					{
						for (std::uint32_t nX = stRange.nMinX; nX <= stRange.nMaxX; ++nX)
						{
							arrDirty[nCascade * nPerCascade + nY * nAxis + nX] = true;
						}
					}
				}
			}
		}
	}
	for (std::uint32_t nLogical = 0; nLogical < LogicalPages(); ++nLogical)
	{
		ShadowPageTableEntry &stEntry = stCandidate.arrTable[nLogical];
		if (arrDirty[nLogical] && stEntry.nPhysicalPlusOne != 0)
		{
			stCandidate.arrPhysical[stEntry.nPhysicalPlusOne - 1].nLogical = INVALID_SHADOW_PAGE;
			stEntry = {};
			++stCandidatePlan.stStatistics.nInvalidated;
		}
	}
	std::vector<std::uint64_t> arrRequests(LogicalPages(), 0);
	for (const ShadowPageFeedback &stFeedback : stCandidate.arrFeedback)
	{
		for (std::uint32_t nCascade = 0; nCascade < 4; ++nCascade)
		{
			if (SameProjection(stFeedback.stProjection.arrCascades[nCascade], stProjection.arrCascades[nCascade], false))
			{
				for (std::uint32_t nPage = 0; nPage < nPerCascade; ++nPage)
				{
					arrRequests[nCascade * nPerCascade + nPage] += stFeedback.arrCoverage[nCascade * nPerCascade + nPage];
				}
				continue;
			}
			std::array<double, 4> arrTransform{};
			if (!FeedbackTransform(stFeedback.stProjection.arrCascades[nCascade], stProjection.arrCascades[nCascade], arrTransform))
			{
				++stCandidatePlan.stStatistics.nRejectedFeedback;
				continue;
			}
			for (std::uint32_t nPage = 0; nPage < nPerCascade; ++nPage)
			{
				const std::uint32_t nCount = stFeedback.arrCoverage[nCascade * nPerCascade + nPage];
				if (nCount == 0)
				{
					continue;
				}
				const double dMinU = static_cast<double>(nPage % nAxis) / nAxis;
				const double dMinV = static_cast<double>(nPage / nAxis) / nAxis;
				// Include a small binary32 edge margin, including exact page borders.
				const double dMargin = 16 * std::numeric_limits<float>::epsilon();
				const PageRectangle stRange = Rectangle(dMinU * arrTransform[0] + arrTransform[2] - dMargin,
														dMinV * arrTransform[1] + arrTransform[3] - dMargin,
														(dMinU + 1.0 / nAxis) * arrTransform[0] + arrTransform[2] + dMargin,
														(dMinV + 1.0 / nAxis) * arrTransform[1] + arrTransform[3] + dMargin, nAxis);
				if (!stRange.bEmpty)
				{
					for (std::uint32_t nY = stRange.nMinY; nY <= stRange.nMaxY; ++nY)
					{
						for (std::uint32_t nX = stRange.nMinX; nX <= stRange.nMaxX; ++nX)
						{
							arrRequests[nCascade * nPerCascade + nY * nAxis + nX] += nCount;
						}
					}
				}
			}
		}
	}
	std::vector<std::uint32_t> arrOrder;
	for (std::uint32_t nLogical = 0; nLogical < LogicalPages(); ++nLogical)
	{
		if (arrRequests[nLogical] != 0)
		{
			arrOrder.push_back(nLogical);
			const ShadowPageTableEntry &stEntry = stCandidate.arrTable[nLogical];
			if (stEntry.nPhysicalPlusOne != 0)
			{
				stCandidate.arrPhysical[stEntry.nPhysicalPlusOne - 1].nLastRequest = stCandidatePlan.nEpoch;
				++stCandidatePlan.stStatistics.nReused;
			}
		}
	}
	std::sort(arrOrder.begin(), arrOrder.end(), [&arrRequests, nPerCascade](std::uint32_t nLeft, std::uint32_t nRight)
			  {
				  if (nLeft / nPerCascade != nRight / nPerCascade)
				  {
					  return nLeft / nPerCascade < nRight / nPerCascade;
				  }
				  return arrRequests[nLeft] == arrRequests[nRight] ? nLeft < nRight : arrRequests[nLeft] > arrRequests[nRight]; });
	stCandidatePlan.stStatistics.nRequested = static_cast<std::uint32_t>(arrOrder.size());
	for (std::uint32_t nLogical : arrOrder)
	{
		if (stCandidate.arrTable[nLogical].nPhysicalPlusOne != 0)
		{
			continue;
		}
		std::uint32_t nPhysical = INVALID_SHADOW_PAGE;
		if (stCandidatePlan.arrRender.size() < stSettings.nUpdatesPerFrame)
		{
			for (std::uint32_t nIndex = 0; nIndex < stCandidate.arrPhysical.size(); ++nIndex)
			{
				const PhysicalPage &stPage = stCandidate.arrPhysical[nIndex];
				if (stPage.nLogical == INVALID_SHADOW_PAGE)
				{
					nPhysical = nIndex;
					break;
				}
				if (arrRequests[stPage.nLogical] == 0 && (nPhysical == INVALID_SHADOW_PAGE || stPage.nLastRequest < stCandidate.arrPhysical[nPhysical].nLastRequest))
				{
					nPhysical = nIndex;
				}
			}
		}
		if (nPhysical == INVALID_SHADOW_PAGE)
		{
			++stCandidatePlan.stStatistics.nDeferred;
			continue;
		}
		PhysicalPage &stPage = stCandidate.arrPhysical[nPhysical];
		if (stPage.nLogical != INVALID_SHADOW_PAGE)
		{
			stCandidate.arrTable[stPage.nLogical] = {};
			++stCandidatePlan.stStatistics.nEvicted;
		}
		ShadowPageRender stRender;
		stRender.nLogical = nLogical;
		stRender.nPhysical = nPhysical;
		const ShadowCascade &stCascade = stProjection.arrCascades[nLogical / nPerCascade];
		const std::uint32_t nPage = nLogical % nPerCascade;
		if (!BuildShadowPageProjection(stCascade, stSettings.nResolution, nPage % nAxis, nPage / nAxis, stRender.arrViewProjection))
		{
			return Error(out_arrDiagnostics, "Page projection is not representable in binary32.");
		}
		stPage.nLogical = nLogical;
		stPage.nLastRequest = stCandidatePlan.nEpoch;
		ShadowPageTableEntry &stEntry = stCandidate.arrTable[nLogical];
		stEntry.nPhysicalPlusOne = nPhysical + 1;
		for (std::size_t nColumn = 0; nColumn < 4; ++nColumn)
		{
			stEntry.arrDepthPlane[nColumn] = static_cast<float>(stCascade.arrViewProjection[nColumn * 4 + 2]);
		}
		stCandidatePlan.arrRender.push_back(stRender);
	}
	stCandidate.stProjection = stProjection;
	stCandidate.arrCasters = arrCasters;
	stCandidate.nEpoch = stCandidatePlan.nEpoch;
	stCandidate.nSceneRevision += bSceneChanged ? 1 : 0;
	stCandidatePlan.nSceneRevision = stCandidate.nSceneRevision;
	stCandidatePlan.arrTable = stCandidate.arrTable;
	stCandidatePlan.stStatistics.nRendered = static_cast<std::uint32_t>(stCandidatePlan.arrRender.size());
	for (const PhysicalPage &stPage : stCandidate.arrPhysical)
	{
		stCandidatePlan.stStatistics.nResident += stPage.nLogical != INVALID_SHADOW_PAGE ? 1 : 0;
	}
	stPending = std::move(stCandidate);
	stPlan = std::move(stCandidatePlan);
	bPending = true;
	return true;
}

bool ShadowPageCache::Commit() noexcept
{
	if (!bPending)
	{
		return false;
	}
	stCommitted = std::move(stPending);
	bPending = false;
	return true;
}

void ShadowPageCache::Cancel() noexcept
{
	stPending = {};
	stPlan = {};
	bPending = false;
}

const ShadowPagePlan &ShadowPageCache::Plan() const noexcept
{
	return stPlan;
}

std::uint32_t ShadowPageCache::LogicalPages() const noexcept
{
	return static_cast<std::uint32_t>(stCommitted.arrTable.size());
}

std::uint64_t ShadowPageCache::Epoch() const noexcept
{
	return stCommitted.nEpoch;
}

} // namespace EngineNext::Rendering
