/**************************************************************************/
/*  TestClockAndFixedStep.cpp                                             */
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

#include "engine_next/include/EngineNext/Runtime/Clock.h"
#include "engine_next/include/EngineNext/Runtime/FixedStepLoop.h"

#include <limits>

ENGINE_NEXT_TEST("Manual and system clocks expose monotonic milliseconds")
{
	EngineNext::Runtime::ManualClock stManual;
	ENGINE_NEXT_CHECK_EQ(stManual.NowMsec(), 0ULL);
	ENGINE_NEXT_CHECK(stManual.AdvanceMsec(16));
	ENGINE_NEXT_CHECK_EQ(stManual.NowMsec(), 16ULL);
	ENGINE_NEXT_CHECK(stManual.AdvanceMsec(8));
	ENGINE_NEXT_CHECK_EQ(stManual.NowMsec(), 24ULL);
	ENGINE_NEXT_CHECK(!stManual.AdvanceMsec(std::numeric_limits<std::uint64_t>::max()));
	ENGINE_NEXT_CHECK_EQ(stManual.NowMsec(), 24ULL);
	stManual.Reset();
	ENGINE_NEXT_CHECK_EQ(stManual.NowMsec(), 0ULL);

	const EngineNext::Runtime::SystemClock stSystem;
	ENGINE_NEXT_CHECK(stSystem.NowMsec() <= stSystem.NowMsec());
}

ENGINE_NEXT_TEST("Fixed step loop accumulates, limits catch-up and rejects backwards time")
{
	EngineNext::Runtime::FixedStepLoop stLoop;
	ENGINE_NEXT_CHECK(!stLoop.SetFixedStepMsec(0));
	ENGINE_NEXT_CHECK(!stLoop.SetFixedStepMsec(1001));
	ENGINE_NEXT_CHECK(stLoop.SetFixedStepMsec(16));
	ENGINE_NEXT_CHECK(stLoop.SetMaxCatchUpSteps(2));

	EngineNext::Runtime::FixedStepBatch stBatch;
	ENGINE_NEXT_CHECK_EQ(stLoop.Advance(0, stBatch), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stBatch.nStepCount, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.Advance(8, stBatch), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stBatch.nStepCount, 0ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.Advance(16, stBatch), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stBatch.nFirstTick, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stBatch.nStepCount, 1ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.GetTick(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.Advance(100, stBatch), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stBatch.nFirstTick, 2ULL);
	ENGINE_NEXT_CHECK_EQ(stBatch.nStepCount, 2ULL);
	ENGINE_NEXT_CHECK_EQ(stBatch.nDroppedMsec, 48ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.GetAccumulatorMsec(), 4ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.GetTick(), 3ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.Advance(99, stBatch), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stLoop.Reset();
	ENGINE_NEXT_CHECK_EQ(stLoop.GetTick(), 0ULL);
	ENGINE_NEXT_CHECK_EQ(stLoop.GetAccumulatorMsec(), 0ULL);
}
