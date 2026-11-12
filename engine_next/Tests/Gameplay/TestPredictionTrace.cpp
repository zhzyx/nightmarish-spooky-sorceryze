/**************************************************************************/
/*  TestPredictionTrace.cpp                                               */
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
#include "engine_next/Tests/Gameplay/PredictionTrace.h"

#include "EngineNext/Gameplay/InterpolationBuffer.h"
#include "EngineNext/Gameplay/PredictionModel.h"

#include <fstream>
#include <iostream>
#include <string>

namespace EngineNext::Tests
{

namespace
{

GameplayTrace::TraceState Convert(const Gameplay::PredictionState &stState)
{
	GameplayTrace::TraceState stResult;
	stResult.fPositionX = stState.vPosition.fX;
	stResult.fPositionY = stState.vPosition.fY;
	stResult.fPositionZ = stState.vPosition.fZ;
	stResult.fVelocityX = stState.vVelocity.fX;
	stResult.fVelocityY = stState.vVelocity.fY;
	stResult.fVelocityZ = stState.vVelocity.fZ;
	stResult.nConfirmedSequence = stState.nConfirmedSequence;
	stResult.nServerTimeMsec = stState.nServerTimeMsec;
	return stResult;
}

Gameplay::PredictionState Convert(const GameplayTrace::TraceState &stState)
{
	Gameplay::PredictionState stResult;
	stResult.vPosition = { stState.fPositionX, stState.fPositionY, stState.fPositionZ };
	stResult.vVelocity = { stState.fVelocityX, stState.fVelocityY, stState.fVelocityZ };
	stResult.nConfirmedSequence = stState.nConfirmedSequence;
	stResult.nServerTimeMsec = stState.nServerTimeMsec;
	return stResult;
}

std::string BuildTrace()
{
	std::string strTrace;
	Gameplay::PredictionModel stModel;
	ENGINE_NEXT_CHECK(stModel.SetMaxSpeed(3.5F));
	ENGINE_NEXT_CHECK(stModel.SetFixedStepMsec(100));
	Gameplay::PredictionState stState = Convert(GameplayTrace::GetInitialState());
	std::size_t nIndex = 0;
	for (const GameplayTrace::TraceInput &stInput : GameplayTrace::GetModelInputs())
	{
		const Gameplay::PredictionInput stCommand{ stInput.nSequence, { stInput.fX, stInput.fY, stInput.fZ }, stInput.nStepMsec };
		const Gameplay::Status eStatus = stModel.Simulate(stState, stCommand);
		GameplayTrace::AppendModelResult(strTrace, nIndex++, static_cast<std::uint32_t>(eStatus), Convert(stState));
	}

	Gameplay::InterpolationBuffer stBuffer;
	ENGINE_NEXT_CHECK(stBuffer.SetMaxSamples(3));
	ENGINE_NEXT_CHECK(stBuffer.SetInterpolationDelayMsec(100));
	ENGINE_NEXT_CHECK(stBuffer.SetStaleAfterMsec(250));
	nIndex = 0;
	for (const GameplayTrace::TraceState &stSample : GameplayTrace::GetBufferSamples())
	{
		const Gameplay::Status eStatus = stBuffer.AddSample(Convert(stSample));
		GameplayTrace::AppendBufferAdd(strTrace, nIndex++, static_cast<std::uint32_t>(eStatus), stBuffer.GetSampleCount());
		if (nIndex == 2)
		{
			const Gameplay::InterpolationResult stResult = stBuffer.Sample(300);
			const GameplayTrace::TraceState stEmpty;
			GameplayTrace::AppendBufferSample(strTrace, "interpolated", static_cast<std::uint32_t>(stResult.eStatus), stResult.stState.has_value(), stResult.stState.has_value() ? Convert(*stResult.stState) : stEmpty);
		}
	}
	const Gameplay::InterpolationResult stStale = stBuffer.Sample(1000);
	GameplayTrace::AppendBufferSample(strTrace, "stale", static_cast<std::uint32_t>(stStale.eStatus), stStale.stState.has_value(), Convert(*stStale.stState));
	const Gameplay::InterpolationResult stBefore = stBuffer.Sample(50);
	GameplayTrace::AppendBufferSample(strTrace, "before", static_cast<std::uint32_t>(stBefore.eStatus), stBefore.stState.has_value(), Convert(*stBefore.stState));
	Gameplay::InterpolationBuffer stEmptyBuffer;
	const Gameplay::InterpolationResult stEmpty = stEmptyBuffer.Sample(100);
	const GameplayTrace::TraceState stEmptyState;
	GameplayTrace::AppendBufferSample(strTrace, "empty", static_cast<std::uint32_t>(stEmpty.eStatus), stEmpty.stState.has_value(), stEmptyState);
	return strTrace;
}

} // namespace

bool WritePredictionTrace(const char *pPath)
{
	std::ofstream stream(pPath, std::ios::binary | std::ios::trunc);
	const std::string strTrace = BuildTrace();
	stream.write(strTrace.data(), static_cast<std::streamsize>(strTrace.size()));
	return stream.good();
}

} // namespace EngineNext::Tests

ENGINE_NEXT_TEST("Shared prediction trace matches the legacy golden")
{
	const std::string strActual = EngineNext::Tests::BuildTrace();
	const std::string strExpected = EngineNext::GameplayTrace::GetLegacyGolden();
	if (strActual != strExpected)
	{
		std::cerr << "Prediction trace mismatch. Actual trace:\n"
				  << strActual;
	}
	ENGINE_NEXT_CHECK_EQ(strActual, strExpected);
}
