/**************************************************************************/
/*  TestPredictionCore.h                                                  */
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

#include "../gameplay_prediction.h"

#include "../../../engine_next/Tests/Gameplay/PredictionTrace.h"

#include "core/string/print_string.h"
#include "tests/test_macros.h"

#include <algorithm>
#include <chrono>
#include <limits>
#include <vector>

namespace TestGameplayPredictionCore
{

static Vector3 ToGodot(float fX, float fY, float fZ)
{
	return Vector3(fX, fY, fZ);
}

static EngineNext::GameplayTrace::TraceState ToTrace(const Ref<GameplayPredictionState> &refState)
{
	EngineNext::GameplayTrace::TraceState stResult;
	if (refState.is_null())
	{
		return stResult;
	}
	const Vector3 vPosition = refState->get_position();
	const Vector3 vVelocity = refState->get_velocity();
	stResult.fPositionX = static_cast<float>(vPosition.x);
	stResult.fPositionY = static_cast<float>(vPosition.y);
	stResult.fPositionZ = static_cast<float>(vPosition.z);
	stResult.fVelocityX = static_cast<float>(vVelocity.x);
	stResult.fVelocityY = static_cast<float>(vVelocity.y);
	stResult.fVelocityZ = static_cast<float>(vVelocity.z);
	stResult.nConfirmedSequence = refState->get_confirmed_sequence();
	stResult.nServerTimeMsec = refState->get_server_time_msec();
	return stResult;
}

static Ref<GameplayPredictionState> ToGodot(const EngineNext::GameplayTrace::TraceState &stState)
{
	Ref<GameplayPredictionState> refResult;
	refResult.instantiate();
	refResult->set_position(ToGodot(stState.fPositionX, stState.fPositionY, stState.fPositionZ));
	refResult->set_velocity(ToGodot(stState.fVelocityX, stState.fVelocityY, stState.fVelocityZ));
	refResult->set_confirmed_sequence(stState.nConfirmedSequence);
	refResult->set_server_time_msec(stState.nServerTimeMsec);
	return refResult;
}

static uint32_t ToTraceStatus(Error eError)
{
	if (eError == OK)
	{
		return 0;
	}
	if (eError == ERR_ALREADY_EXISTS)
	{
		return 2;
	}
	return 1;
}

static uint32_t ToTraceStatus(const Dictionary &dictResult)
{
	const String strStatus = dictResult.get("status", String());
	if (strStatus == "empty")
	{
		return 0;
	}
	if (strStatus == "single_sample")
	{
		return 1;
	}
	if (strStatus == "before_range")
	{
		return 2;
	}
	if (strStatus == "interpolated")
	{
		return 3;
	}
	if (strStatus == "held")
	{
		return 4;
	}
	return 5;
}

static std::string BuildLegacyTrace()
{
	std::string strTrace;
	Ref<GameplayPredictionModel> refModel;
	refModel.instantiate();
	refModel->set_max_speed(3.5F);
	refModel->set_fixed_step_msec(100);
	Ref<GameplayPredictionState> refState = ToGodot(EngineNext::GameplayTrace::GetInitialState());
	std::size_t nIndex = 0;
	for (const EngineNext::GameplayTrace::TraceInput &stInput : EngineNext::GameplayTrace::GetModelInputs())
	{
		Ref<GameplayPredictionInput> refInput;
		refInput.instantiate();
		refInput->set_sequence(stInput.nSequence);
		refInput->set_movement_input(ToGodot(stInput.fX, stInput.fY, stInput.fZ));
		refInput->set_step_msec(stInput.nStepMsec);
		const Error eError = refModel->simulate(refState, refInput);
		EngineNext::GameplayTrace::AppendModelResult(strTrace, nIndex++, ToTraceStatus(eError), ToTrace(refState));
	}

	Ref<GameplayInterpolationBuffer> refBuffer;
	refBuffer.instantiate();
	refBuffer->set_max_samples(3);
	refBuffer->set_interpolation_delay_msec(100);
	refBuffer->set_stale_after_msec(250);
	nIndex = 0;
	for (const EngineNext::GameplayTrace::TraceState &stSample : EngineNext::GameplayTrace::GetBufferSamples())
	{
		const Error eError = refBuffer->add_sample(ToGodot(stSample));
		EngineNext::GameplayTrace::AppendBufferAdd(strTrace, nIndex++, ToTraceStatus(eError), static_cast<std::size_t>(refBuffer->get_sample_count()));
		if (nIndex == 2)
		{
			const Dictionary dictResult = refBuffer->sample(300);
			const bool bHasState = dictResult.has("state");
			const Ref<GameplayPredictionState> refResult = bHasState ? Ref<GameplayPredictionState>(dictResult["state"]) : Ref<GameplayPredictionState>();
			EngineNext::GameplayTrace::AppendBufferSample(strTrace, "interpolated", ToTraceStatus(dictResult), bHasState, ToTrace(refResult));
		}
	}
	const Dictionary dictStale = refBuffer->sample(1000);
	EngineNext::GameplayTrace::AppendBufferSample(strTrace, "stale", ToTraceStatus(dictStale), dictStale.has("state"), ToTrace(dictStale["state"]));
	const Dictionary dictBefore = refBuffer->sample(50);
	EngineNext::GameplayTrace::AppendBufferSample(strTrace, "before", ToTraceStatus(dictBefore), dictBefore.has("state"), ToTrace(dictBefore["state"]));
	Ref<GameplayInterpolationBuffer> refEmptyBuffer;
	refEmptyBuffer.instantiate();
	const Dictionary dictEmpty = refEmptyBuffer->sample(100);
	const EngineNext::GameplayTrace::TraceState stEmptyState;
	EngineNext::GameplayTrace::AppendBufferSample(strTrace, "empty", ToTraceStatus(dictEmpty), false, stEmptyState);
	return strTrace;
}

TEST_CASE("[Gameplay][Prediction][EngineNext] Core adapter rejects overflow without partial writes")
{
	Ref<GameplayPredictionModel> refModel;
	refModel.instantiate();
	refModel->set_max_speed(std::numeric_limits<float>::max());
	refModel->set_fixed_step_msec(1000);
	Ref<GameplayPredictionState> refState;
	refState.instantiate();
	refState->set_position(Vector3(std::numeric_limits<float>::max(), 0.0F, 0.0F));
	Ref<GameplayPredictionInput> refInput;
	refInput.instantiate();
	refInput->set_sequence(1);
	refInput->set_movement_input(Vector3(1.0F, 0.0F, 0.0F));
	refInput->set_step_msec(1000);
	ERR_PRINT_OFF;
	const Error eError = refModel->simulate(refState, refInput);
	ERR_PRINT_ON;
	CHECK_EQ(eError, ERR_INVALID_PARAMETER);
	CHECK(refState->get_position().is_equal_approx(Vector3(std::numeric_limits<float>::max(), 0.0F, 0.0F)));
	CHECK(refState->get_velocity().is_equal_approx(Vector3()));
	CHECK_EQ(refState->get_confirmed_sequence(), 0U);
}

static int64_t MeasureLegacyModel(uint32_t &out_nChecksum)
{
	using Clock = std::chrono::steady_clock;
	const Clock::time_point stStarted = Clock::now();
	Ref<GameplayPredictionModel> refModel;
	refModel.instantiate();
	Ref<GameplayPredictionState> refState;
	refState.instantiate();
	Ref<GameplayPredictionInput> refInput;
	refInput.instantiate();
	refInput->set_movement_input(Vector3(0.25F, -0.5F, 0.75F));
	refInput->set_step_msec(16);
	for (uint64_t nIndex = 1; nIndex <= 1000000; ++nIndex)
	{
		refInput->set_sequence(nIndex);
		if (refModel->simulate(refState, refInput) != OK)
		{
			return -1;
		}
	}
	out_nChecksum = EngineNext::GameplayTrace::GetFloatBits(static_cast<float>(refState->get_position().x)) ^ EngineNext::GameplayTrace::GetFloatBits(static_cast<float>(refState->get_position().y)) ^ EngineNext::GameplayTrace::GetFloatBits(static_cast<float>(refState->get_position().z));
	return std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - stStarted).count();
}

static int64_t MeasureLegacyBuffer(uint64_t &out_nChecksum)
{
	using Clock = std::chrono::steady_clock;
	const Clock::time_point stStarted = Clock::now();
	Ref<GameplayInterpolationBuffer> refBuffer;
	refBuffer.instantiate();
	refBuffer->set_max_samples(4096);
	Ref<GameplayPredictionState> refState;
	refState.instantiate();
	refState->set_velocity(Vector3(1.0F, 0.0F, 0.0F));
	uint64_t nChecksum = 0;
	for (uint64_t nIndex = 1; nIndex <= 50000; ++nIndex)
	{
		refState->set_position(Vector3(static_cast<float>(nIndex % 1000), 0.0F, 0.0F));
		refState->set_confirmed_sequence(nIndex);
		refState->set_server_time_msec(nIndex);
		if (refBuffer->add_sample(refState) != OK)
		{
			return -1;
		}
		if (nIndex % 4 == 0)
		{
			const Dictionary dictResult = refBuffer->sample(nIndex);
			if (!dictResult.has("state"))
			{
				return -1;
			}
			const Ref<GameplayPredictionState> refResult = dictResult["state"];
			nChecksum ^= refResult->get_confirmed_sequence();
		}
	}
	if (refBuffer->get_sample_count() != 4096)
	{
		return -1;
	}
	out_nChecksum = nChecksum ^ static_cast<uint64_t>(refBuffer->get_sample_count());
	return std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - stStarted).count();
}

TEST_CASE("[Gameplay][Prediction][EngineNext][Benchmark] Legacy prediction performance baseline")
{
	std::vector<int64_t> arrModelTimes;
	std::vector<int64_t> arrBufferTimes;
	uint32_t nModelChecksum = 0;
	uint64_t nBufferChecksum = 0;
	for (int nIndex = 0; nIndex < 5; ++nIndex)
	{
		uint32_t nCurrentModelChecksum = 0;
		uint64_t nCurrentBufferChecksum = 0;
		const int64_t nModelTime = MeasureLegacyModel(nCurrentModelChecksum);
		const int64_t nBufferTime = MeasureLegacyBuffer(nCurrentBufferChecksum);
		CHECK(nModelTime >= 0);
		CHECK(nBufferTime >= 0);
		if (nIndex == 0)
		{
			nModelChecksum = nCurrentModelChecksum;
			nBufferChecksum = nCurrentBufferChecksum;
		}
		else
		{
			CHECK_EQ(nCurrentModelChecksum, nModelChecksum);
			CHECK_EQ(nCurrentBufferChecksum, nBufferChecksum);
		}
		arrModelTimes.push_back(nModelTime);
		arrBufferTimes.push_back(nBufferTime);
	}
	std::sort(arrModelTimes.begin(), arrModelTimes.end());
	std::sort(arrBufferTimes.begin(), arrBufferTimes.end());
	print_line(vformat("ENGINE_NEXT_LEGACY_BENCHMARK model_steps=1000000 buffer_operations=50000 buffer_capacity=4096 repetitions=5 model_median_us=%d buffer_median_us=%d model_checksum=%d buffer_checksum=%d", arrModelTimes[2], arrBufferTimes[2], nModelChecksum, nBufferChecksum));
}

TEST_CASE("[Gameplay][Prediction][EngineNext] Shared core trace matches the legacy golden")
{
	ERR_PRINT_OFF;
	const std::string strActual = BuildLegacyTrace();
	ERR_PRINT_ON;
	const std::string strExpected = EngineNext::GameplayTrace::GetLegacyGolden();
	if (strActual != strExpected)
	{
		print_line(String("Legacy prediction trace mismatch. Actual trace:\n") + String(strActual.c_str()));
	}
	CHECK(strActual == strExpected);
}

} // namespace TestGameplayPredictionCore
