/**************************************************************************/
/*  TestTemporalState.cpp                                                 */
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
#include "engine_next/include/EngineNext/Rendering/RenderConfiguration.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"
#include "engine_next/include/EngineNext/Rendering/TemporalState.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <vector>

namespace
{

using EngineNext::Rendering::CameraSettings;
using EngineNext::Rendering::TemporalDrawInput;
using EngineNext::Rendering::TemporalDrawKey;
using EngineNext::Rendering::TemporalFrame;
using EngineNext::Rendering::TemporalState;

static_assert(std::is_same_v<decltype(TemporalDrawKey::nEntityId), decltype(EngineNext::Rendering::RenderInstance::nEntityId)>);
static_assert(std::is_same_v<decltype(TemporalDrawKey::nAssetIndex), decltype(EngineNext::Rendering::RenderInstance::nAsset)>);
static_assert(std::is_same_v<decltype(TemporalDrawKey::nPrimitive), decltype(EngineNext::Rendering::RenderInstance::nPrimitive)>);
static_assert(std::is_same_v<decltype(TemporalDrawKey::nNode), decltype(EngineNext::Rendering::RenderInstance::nNode)>);

TemporalDrawInput Draw(std::uint64_t nEntityId, double dTranslation = 0)
{
	TemporalDrawInput stDraw;
	stDraw.stKey.nEntityId = nEntityId;
	stDraw.arrWorld = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, dTranslation, 0, 0, 1 };
	return stDraw;
}

bool Prepare(TemporalState &stState, const std::vector<TemporalDrawInput> &arrDraws, TemporalFrame &out_stFrame)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return stState.PrepareFrame(CameraSettings{}, 640, 480, arrDraws, out_stFrame, arrDiagnostics);
}

bool Commit(TemporalState &stState, const TemporalFrame &stFrame)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return stState.CommitFrame(stFrame.nToken, arrDiagnostics);
}

void CheckNear(double dActual, double dExpected)
{
	ENGINE_NEXT_CHECK(std::isfinite(dActual));
	ENGINE_NEXT_CHECK(std::abs(dActual - dExpected) < 1e-12);
}

} // namespace

ENGINE_NEXT_TEST("Temporal state advances the eight pixel jitter samples only on commit")
{
	TemporalState stState;
	TemporalFrame stFrame;
	ENGINE_NEXT_CHECK(!stState.HasHistory());
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 1U);
	const std::array<std::array<double, 2>, 8> arrExpected{ { { 0, -1.0 / 6 }, { -0.25, 1.0 / 6 }, { 0.25, -7.0 / 18 }, { -0.375, -1.0 / 18 }, { 0.125, 5.0 / 18 }, { -0.125, -5.0 / 18 }, { 0.375, 1.0 / 18 }, { -0.4375, 7.0 / 18 } } };
	for (std::uint32_t nFrame = 0; nFrame < 17; ++nFrame)
	{
		ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
		const std::uint32_t nSample = nFrame % 8;
		ENGINE_NEXT_CHECK_EQ(stFrame.nSampleIndex, nSample);
		CheckNear(stFrame.arrJitterPixels[0], arrExpected[nSample][0]);
		CheckNear(stFrame.arrJitterPixels[1], arrExpected[nSample][1]);
		ENGINE_NEXT_CHECK_EQ(stFrame.bHistoryValid, nFrame != 0);
		CheckNear(stFrame.stCurrentCamera.arrProjection[8] - stFrame.stCurrentUnjitteredCamera.arrProjection[8], -2 * arrExpected[nSample][0] / 640);
		CheckNear(stFrame.stCurrentCamera.arrProjection[9] - stFrame.stCurrentUnjitteredCamera.arrProjection[9], 2 * arrExpected[nSample][1] / 480);
		ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	}
	ENGINE_NEXT_CHECK(stState.HasHistory());
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 1U);
}

ENGINE_NEXT_TEST("Temporal preparation and output mutations cannot replace committed history")
{
	TemporalState stState;
	TemporalFrame stFirst;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 2) }, stFirst));
	ENGINE_NEXT_CHECK(!stFirst.arrDraws[0].bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stFirst.arrDraws[0].arrPreviousWorld, stFirst.arrDraws[0].arrCurrentWorld);
	ENGINE_NEXT_CHECK_EQ(stFirst.stPreviousUnjitteredCamera.arrViewProjection, stFirst.stCurrentUnjitteredCamera.arrViewProjection);
	stFirst.arrDraws[0].arrCurrentWorld[12] = 500;
	stFirst.stCurrentUnjitteredCamera.arrView[12] = 500;
	ENGINE_NEXT_CHECK(Commit(stState, stFirst));
	TemporalFrame stSecond;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 8) }, stSecond));
	ENGINE_NEXT_CHECK(stSecond.arrDraws[0].bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stSecond.arrDraws[0].arrPreviousWorld[12], 2);
	ENGINE_NEXT_CHECK_EQ(stSecond.nSampleIndex, 1U);
	TemporalFrame stAbandoned;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 9) }, stAbandoned));
	ENGINE_NEXT_CHECK_EQ(stAbandoned.nSampleIndex, 1U);
	ENGINE_NEXT_CHECK_EQ(stAbandoned.arrDraws[0].arrPreviousWorld[12], 2);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stState.CommitFrame(stSecond.nToken, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK(Commit(stState, stAbandoned));
	ENGINE_NEXT_CHECK(!Commit(stState, stAbandoned));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 10) }, stSecond));
	ENGINE_NEXT_CHECK_EQ(stSecond.arrDraws[0].arrPreviousWorld[12], 9);
	ENGINE_NEXT_CHECK_EQ(stSecond.nSampleIndex, 2U);
}

ENGINE_NEXT_TEST("Temporal draw identity handles reordered nodes new removals and explicit resets")
{
	TemporalState stState;
	TemporalFrame stFrame;
	std::vector<TemporalDrawInput> arrDraws{ Draw(1, 10), Draw(1, 20), Draw(1, 30), Draw(1, 40) };
	arrDraws[1].stKey.nNode = 1;
	arrDraws[2].stKey.nAssetIndex = 1;
	arrDraws[3].stKey.nPrimitive = 1;
	ENGINE_NEXT_CHECK(Prepare(stState, arrDraws, stFrame));
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	std::vector<TemporalDrawInput> arrNext{ arrDraws[3], arrDraws[1], Draw(2, 50), arrDraws[0] };
	arrNext[0].arrWorld[12] = 41;
	arrNext[1].bResetHistory = true;
	ENGINE_NEXT_CHECK(Prepare(stState, arrNext, stFrame));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws[0].stKey.nPrimitive, 1U);
	ENGINE_NEXT_CHECK(stFrame.arrDraws[0].bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws[0].arrPreviousWorld[12], 40);
	ENGINE_NEXT_CHECK(!stFrame.arrDraws[1].bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws[1].arrPreviousWorld, stFrame.arrDraws[1].arrCurrentWorld);
	ENGINE_NEXT_CHECK(!stFrame.arrDraws[2].bHistoryValid);
	ENGINE_NEXT_CHECK(stFrame.arrDraws[3].bHistoryValid);
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK(Prepare(stState, { arrDraws[1], arrDraws[2] }, stFrame));
	ENGINE_NEXT_CHECK(stFrame.arrDraws[0].bHistoryValid);
	ENGINE_NEXT_CHECK(!stFrame.arrDraws[1].bHistoryValid);
}

ENGINE_NEXT_TEST("Temporal projection changes reset candidates while camera motion keeps previous matrices")
{
	TemporalState stState;
	TemporalFrame stFrame;
	CameraSettings stCamera;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	const std::array<double, 16> arrInitialView = stFrame.stCurrentUnjitteredCamera.arrView;
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	stCamera.arrPosition[0] = 2;
	stCamera.arrTarget[0] = 2;
	ENGINE_NEXT_CHECK(stState.PrepareFrame(stCamera, 640, 480, { Draw(1) }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK(stFrame.bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stFrame.stPreviousUnjitteredCamera.arrView, arrInitialView);
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	for (std::uint32_t nChange = 0; nChange < 5; ++nChange)
	{
		std::uint32_t nWidth = 640;
		std::uint32_t nHeight = 480;
		CameraSettings stChanged = stCamera;
		if (nChange == 0)
		{
			nWidth = 800;
		}
		if (nChange == 1)
		{
			nHeight = 600;
		}
		if (nChange == 2)
		{
			stChanged.dVerticalFovDegrees = 60;
		}
		if (nChange == 3)
		{
			stChanged.dNearPlane = 0.1;
		}
		if (nChange == 4)
		{
			stChanged.dFarPlane = 2000;
		}
		ENGINE_NEXT_CHECK(stState.PrepareFrame(stChanged, nWidth, nHeight, { Draw(1) }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK(!stFrame.bHistoryValid);
		ENGINE_NEXT_CHECK(!stFrame.arrDraws[0].bHistoryValid);
		ENGINE_NEXT_CHECK_EQ(stFrame.nSampleIndex, 0U);
		ENGINE_NEXT_CHECK_EQ(stFrame.nEpoch, stState.GetEpoch() + 1);
		ENGINE_NEXT_CHECK_EQ(stFrame.stPreviousUnjitteredCamera.arrViewProjection, stFrame.stCurrentUnjitteredCamera.arrViewProjection);
		ENGINE_NEXT_CHECK(Commit(stState, stFrame));
		ENGINE_NEXT_CHECK_EQ(stFrame.nEpoch, stState.GetEpoch());
		ENGINE_NEXT_CHECK(stState.PrepareFrame(stCamera, 640, 480, { Draw(1) }, stFrame, arrDiagnostics));
		ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	}
}

ENGINE_NEXT_TEST("Temporal reset invalidates pending tokens and restarts history epoch and jitter")
{
	TemporalState stState;
	TemporalFrame stFrame;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	const std::uint64_t nOldToken = stFrame.nToken;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stState.Reset(arrDiagnostics));
	ENGINE_NEXT_CHECK(!stState.HasHistory());
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 2U);
	ENGINE_NEXT_CHECK(!stState.CommitFrame(nOldToken, arrDiagnostics));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	ENGINE_NEXT_CHECK(stFrame.nToken > nOldToken);
	ENGINE_NEXT_CHECK_EQ(stFrame.nEpoch, 2U);
	ENGINE_NEXT_CHECK_EQ(stFrame.nSampleIndex, 0U);
	ENGINE_NEXT_CHECK(!stFrame.bHistoryValid);
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK(Prepare(stState, {}, stFrame));
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	ENGINE_NEXT_CHECK(!stFrame.arrDraws[0].bHistoryValid);
}

ENGINE_NEXT_TEST("Temporal abandoned projection reset leaves the committed epoch and sample intact")
{
	TemporalState stState;
	TemporalFrame stFrame;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	CameraSettings stChanged;
	stChanged.dVerticalFovDegrees = 65;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(stState.PrepareFrame(stChanged, 640, 480, { Draw(1) }, stFrame, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stFrame.nEpoch, 2U);
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 1U);
	const std::uint64_t nAbandonedToken = stFrame.nToken;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1) }, stFrame));
	ENGINE_NEXT_CHECK(stFrame.bHistoryValid);
	ENGINE_NEXT_CHECK_EQ(stFrame.nEpoch, 1U);
	ENGINE_NEXT_CHECK_EQ(stFrame.nSampleIndex, 1U);
	ENGINE_NEXT_CHECK(!stState.CommitFrame(nAbandonedToken, arrDiagnostics));
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 1U);
}

ENGINE_NEXT_TEST("Temporal invalid candidates preserve output pending commit and prior history")
{
	TemporalState stState;
	TemporalFrame stPending;
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 2) }, stPending));
	ENGINE_NEXT_CHECK(Commit(stState, stPending));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 3) }, stPending));
	TemporalFrame stOutput = stPending;
	CameraSettings stCamera;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!stState.PrepareFrame(stCamera, 0, 480, {}, stOutput, arrDiagnostics));
	stCamera.arrTarget = stCamera.arrPosition;
	ENGINE_NEXT_CHECK(!stState.PrepareFrame(stCamera, 640, 480, {}, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK(!Prepare(stState, { Draw(1), Draw(1) }, stOutput));
	for (double dValue : { std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity() })
	{
		TemporalDrawInput stInvalid = Draw(1);
		stInvalid.arrWorld[3] = dValue;
		ENGINE_NEXT_CHECK(!Prepare(stState, { stInvalid }, stOutput));
	}
	ENGINE_NEXT_CHECK_EQ(stOutput.nToken, stPending.nToken);
	ENGINE_NEXT_CHECK_EQ(stOutput.arrDraws[0].arrCurrentWorld, stPending.arrDraws[0].arrCurrentWorld);
	ENGINE_NEXT_CHECK_EQ(stState.GetEpoch(), 1U);
	ENGINE_NEXT_CHECK(Commit(stState, stPending));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(1, 4) }, stOutput));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrDraws[0].arrPreviousWorld[12], 3);
	ENGINE_NEXT_CHECK(!stState.CommitFrame(0, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}

ENGINE_NEXT_TEST("Temporal draw count is bounded and finite double transforms retain exact values")
{
	TemporalState stState;
	TemporalFrame stFrame;
	std::vector<TemporalDrawInput> arrDraws(EngineNext::Rendering::MAX_TEMPORAL_DRAWS);
	for (std::size_t nIndex = 0; nIndex < arrDraws.size(); ++nIndex)
	{
		arrDraws[nIndex] = Draw(static_cast<std::uint64_t>(nIndex));
	}
	arrDraws.front().arrWorld[12] = std::numeric_limits<double>::max();
	ENGINE_NEXT_CHECK(Prepare(stState, arrDraws, stFrame));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.size(), arrDraws.size());
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.front().arrCurrentWorld[12], std::numeric_limits<double>::max());
	const std::uint64_t nToken = stFrame.nToken;
	arrDraws.push_back(Draw(EngineNext::Rendering::MAX_TEMPORAL_DRAWS));
	ENGINE_NEXT_CHECK(!Prepare(stState, arrDraws, stFrame));
	ENGINE_NEXT_CHECK_EQ(stFrame.nToken, nToken);
	ENGINE_NEXT_CHECK(Commit(stState, stFrame));
	ENGINE_NEXT_CHECK(Prepare(stState, { Draw(0) }, stFrame));
	ENGINE_NEXT_CHECK_EQ(stFrame.arrDraws.front().arrPreviousWorld[12], std::numeric_limits<double>::max());
}
