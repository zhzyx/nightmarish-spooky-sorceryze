/**************************************************************************/
/*  TemporalState.cpp                                                     */
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

#include "engine_next/include/EngineNext/Rendering/TemporalState.h"

#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <tuple>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::array<std::array<double, 2>, TEMPORAL_SAMPLE_COUNT> JITTER_PIXELS{ { { 0, -1.0 / 6 }, { -0.25, 1.0 / 6 }, { 0.25, -7.0 / 18 }, { -0.375, -1.0 / 18 }, { 0.125, 5.0 / 18 }, { -0.125, -5.0 / 18 }, { 0.375, 1.0 / 18 }, { -0.4375, 7.0 / 18 } } };

bool Fail(const char *pCode, const char *pMessage, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, "$.temporal", pMessage);
	return false;
}

bool LessKey(const TemporalDrawKey &stLeft, const TemporalDrawKey &stRight) noexcept
{
	return std::tie(stLeft.nEntityId, stLeft.nAssetIndex, stLeft.nPrimitive, stLeft.nNode) <
			std::tie(stRight.nEntityId, stRight.nAssetIndex, stRight.nPrimitive, stRight.nNode);
}

bool SameKey(const TemporalDrawKey &stLeft, const TemporalDrawKey &stRight) noexcept
{
	return stLeft.nEntityId == stRight.nEntityId && stLeft.nAssetIndex == stRight.nAssetIndex &&
			stLeft.nPrimitive == stRight.nPrimitive && stLeft.nNode == stRight.nNode;
}

bool LessDraw(const TemporalDrawInput &stLeft, const TemporalDrawInput &stRight) noexcept
{
	return LessKey(stLeft.stKey, stRight.stKey);
}

bool LessDrawKey(const TemporalDrawInput &stDraw, const TemporalDrawKey &stKey) noexcept
{
	return LessKey(stDraw.stKey, stKey);
}

} // namespace

bool TemporalState::PrepareFrame(const CameraSettings &stCamera, std::uint32_t nWidth, std::uint32_t nHeight,
								 const std::vector<TemporalDrawInput> &arrDraws, TemporalFrame &out_stFrame, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrDraws.size() > MAX_TEMPORAL_DRAWS)
	{
		return Fail("temporal_draw_count", "Temporal draw budget exceeded.", out_arrDiagnostics);
	}
	if (nLastToken == std::numeric_limits<std::uint64_t>::max())
	{
		return Fail("temporal_token", "Temporal candidate token space exhausted.", out_arrDiagnostics);
	}
	for (const TemporalDrawInput &stDraw : arrDraws)
	{
		for (double dValue : stDraw.arrWorld)
		{
			if (!std::isfinite(dValue))
			{
				return Fail("temporal_transform", "Temporal draw transforms must be finite.", out_arrDiagnostics);
			}
		}
	}
	Snapshot stCandidate;
	stCandidate.arrDraws = arrDraws;
	std::sort(stCandidate.arrDraws.begin(), stCandidate.arrDraws.end(), LessDraw);
	for (std::size_t nIndex = 1; nIndex < stCandidate.arrDraws.size(); ++nIndex)
	{
		if (SameKey(stCandidate.arrDraws[nIndex - 1].stKey, stCandidate.arrDraws[nIndex].stKey))
		{
			return Fail("temporal_draw_key", "Temporal draw keys must be unique within a frame.", out_arrDiagnostics);
		}
	}
	TemporalFrame stFrame;
	stFrame.bHistoryValid = bHasCommitted && nWidth == stCommitted.nWidth && nHeight == stCommitted.nHeight &&
			stCamera.dVerticalFovDegrees == stCommitted.dVerticalFovDegrees && stCamera.dNearPlane == stCommitted.dNearPlane &&
			stCamera.dFarPlane == stCommitted.dFarPlane;
	stFrame.nEpoch = nEpoch;
	if (bHasCommitted && !stFrame.bHistoryValid)
	{
		if (nEpoch == std::numeric_limits<std::uint64_t>::max())
		{
			return Fail("temporal_epoch", "Temporal history epoch space exhausted.", out_arrDiagnostics);
		}
		++stFrame.nEpoch;
	}
	stFrame.nSampleIndex = stFrame.bHistoryValid ? stCommitted.nNextSampleIndex : 0;
	stFrame.arrJitterPixels = JITTER_PIXELS[stFrame.nSampleIndex];
	if (!BuildCameraMatrices(stCamera, nWidth, nHeight, { 0, 0 }, stFrame.stCurrentUnjitteredCamera, out_arrDiagnostics) ||
		!BuildCameraMatrices(stCamera, nWidth, nHeight, stFrame.arrJitterPixels, stFrame.stCurrentCamera, out_arrDiagnostics))
	{
		return false;
	}
	stFrame.stPreviousUnjitteredCamera = stFrame.bHistoryValid ? stCommitted.stCamera : stFrame.stCurrentUnjitteredCamera;
	stFrame.arrDraws.reserve(arrDraws.size());
	for (const TemporalDrawInput &stDraw : arrDraws)
	{
		TemporalDrawFrame stDrawFrame;
		stDrawFrame.stKey = stDraw.stKey;
		stDrawFrame.arrCurrentWorld = stDraw.arrWorld;
		stDrawFrame.arrPreviousWorld = stDraw.arrWorld;
		if (stFrame.bHistoryValid && !stDraw.bResetHistory)
		{
			const std::vector<TemporalDrawInput>::const_iterator itPrevious = std::lower_bound(
					stCommitted.arrDraws.begin(), stCommitted.arrDraws.end(), stDraw.stKey, LessDrawKey);
			if (itPrevious != stCommitted.arrDraws.end() && SameKey(itPrevious->stKey, stDraw.stKey))
			{
				stDrawFrame.arrPreviousWorld = itPrevious->arrWorld;
				stDrawFrame.bHistoryValid = true;
			}
		}
		stFrame.arrDraws.push_back(stDrawFrame);
	}
	stCandidate.stCamera = stFrame.stCurrentUnjitteredCamera;
	stCandidate.nWidth = nWidth;
	stCandidate.nHeight = nHeight;
	stCandidate.dVerticalFovDegrees = stCamera.dVerticalFovDegrees;
	stCandidate.dNearPlane = stCamera.dNearPlane;
	stCandidate.dFarPlane = stCamera.dFarPlane;
	stCandidate.nEpoch = stFrame.nEpoch;
	stCandidate.nNextSampleIndex = (stFrame.nSampleIndex + 1) % TEMPORAL_SAMPLE_COUNT;
	stFrame.nToken = nLastToken + 1;
	stPending = std::move(stCandidate);
	nPendingToken = stFrame.nToken;
	nLastToken = stFrame.nToken;
	out_stFrame = std::move(stFrame);
	return true;
}

bool TemporalState::CommitFrame(std::uint64_t nToken, Assets::Diagnostics &out_arrDiagnostics)
{
	if (nToken == 0 || nToken != nPendingToken)
	{
		return Fail("temporal_commit", "Commit requires the newest uncommitted temporal candidate token.", out_arrDiagnostics);
	}
	stCommitted = std::move(stPending);
	nEpoch = stCommitted.nEpoch;
	bHasCommitted = true;
	nPendingToken = 0;
	return true;
}

bool TemporalState::Reset(Assets::Diagnostics &out_arrDiagnostics)
{
	if (nEpoch == std::numeric_limits<std::uint64_t>::max())
	{
		return Fail("temporal_epoch", "Temporal history epoch space exhausted.", out_arrDiagnostics);
	}
	++nEpoch;
	stCommitted = Snapshot{};
	stPending = Snapshot{};
	nPendingToken = 0;
	bHasCommitted = false;
	return true;
}

std::uint64_t TemporalState::GetEpoch() const noexcept
{
	return nEpoch;
}

bool TemporalState::HasHistory() const noexcept
{
	return bHasCommitted;
}

} // namespace EngineNext::Rendering
