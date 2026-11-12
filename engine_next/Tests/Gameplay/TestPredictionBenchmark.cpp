/**************************************************************************/
/*  TestPredictionBenchmark.cpp                                           */
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

#include "engine_next/include/EngineNext/Gameplay/InterpolationBuffer.h"
#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <vector>

namespace
{

using Clock = std::chrono::steady_clock;

std::int64_t MeasureModel(std::uint32_t &out_nChecksum)
{
	const Clock::time_point stStarted = Clock::now();
	EngineNext::Gameplay::PredictionModel stModel;
	EngineNext::Gameplay::PredictionState stState;
	EngineNext::Gameplay::PredictionInput stInput{ 1, { 0.25F, -0.5F, 0.75F }, 16 };
	for (std::uint64_t nIndex = 1; nIndex <= 1000000; ++nIndex)
	{
		stInput.nSequence = nIndex;
		if (stModel.Simulate(stState, stInput) != EngineNext::Gameplay::Status::Ok)
		{
			return -1;
		}
	}
	out_nChecksum = EngineNext::Tests::FloatBits(stState.vPosition.fX) ^ EngineNext::Tests::FloatBits(stState.vPosition.fY) ^ EngineNext::Tests::FloatBits(stState.vPosition.fZ);
	const Clock::time_point stFinished = Clock::now();
	return std::chrono::duration_cast<std::chrono::microseconds>(stFinished - stStarted).count();
}

std::int64_t MeasureBuffer(std::uint64_t &out_nChecksum)
{
	const Clock::time_point stStarted = Clock::now();
	EngineNext::Gameplay::InterpolationBuffer stBuffer;
	if (!stBuffer.SetMaxSamples(4096))
	{
		return -1;
	}
	EngineNext::Gameplay::PredictionState stState;
	stState.vVelocity = { 1.0F, 0.0F, 0.0F };
	std::uint64_t nChecksum = 0;
	for (std::uint64_t nIndex = 1; nIndex <= 50000; ++nIndex)
	{
		stState.vPosition.fX = static_cast<float>(nIndex % 1000);
		stState.nConfirmedSequence = nIndex;
		stState.nServerTimeMsec = nIndex;
		if (stBuffer.AddSample(stState) != EngineNext::Gameplay::Status::Ok)
		{
			return -1;
		}
		if (nIndex % 4 == 0)
		{
			const EngineNext::Gameplay::InterpolationResult stResult = stBuffer.Sample(nIndex);
			if (!stResult.stState.has_value())
			{
				return -1;
			}
			nChecksum ^= stResult.stState->nConfirmedSequence;
		}
	}
	if (stBuffer.GetSampleCount() != 4096)
	{
		return -1;
	}
	out_nChecksum = nChecksum ^ stBuffer.GetSampleCount();
	const Clock::time_point stFinished = Clock::now();
	return std::chrono::duration_cast<std::chrono::microseconds>(stFinished - stStarted).count();
}

} // namespace

ENGINE_NEXT_TEST("Prediction release benchmark is deterministic and bounded")
{
	std::vector<std::int64_t> arrModelTimes;
	std::vector<std::int64_t> arrBufferTimes;
	std::uint32_t nModelChecksum = 0;
	std::uint64_t nBufferChecksum = 0;
	for (int nIndex = 0; nIndex < 5; ++nIndex)
	{
		std::uint32_t nCurrentModelChecksum = 0;
		std::uint64_t nCurrentBufferChecksum = 0;
		const std::int64_t nModelTime = MeasureModel(nCurrentModelChecksum);
		const std::int64_t nBufferTime = MeasureBuffer(nCurrentBufferChecksum);
		ENGINE_NEXT_CHECK(nModelTime >= 0);
		ENGINE_NEXT_CHECK(nBufferTime >= 0);
		if (nIndex == 0)
		{
			nModelChecksum = nCurrentModelChecksum;
			nBufferChecksum = nCurrentBufferChecksum;
		}
		else
		{
			ENGINE_NEXT_CHECK_EQ(nCurrentModelChecksum, nModelChecksum);
			ENGINE_NEXT_CHECK_EQ(nCurrentBufferChecksum, nBufferChecksum);
		}
		arrModelTimes.push_back(nModelTime);
		arrBufferTimes.push_back(nBufferTime);
	}
	std::sort(arrModelTimes.begin(), arrModelTimes.end());
	std::sort(arrBufferTimes.begin(), arrBufferTimes.end());
	std::cout << "ENGINE_NEXT_BENCHMARK model_steps=1000000 buffer_operations=50000 buffer_capacity=4096 repetitions=5"
			  << " model_median_us=" << arrModelTimes[2] << " buffer_median_us=" << arrBufferTimes[2]
			  << " model_checksum=" << nModelChecksum << " buffer_checksum=" << nBufferChecksum << '\n';
}
