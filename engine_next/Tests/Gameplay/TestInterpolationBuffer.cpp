/**************************************************************************/
/*  TestInterpolationBuffer.cpp                                           */
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

#include "../TestFramework.h"

#include "EngineNext/Gameplay/InterpolationBuffer.h"

#include <limits>

using EngineNext::Gameplay::InterpolationBuffer;
using EngineNext::Gameplay::InterpolationResult;
using EngineNext::Gameplay::InterpolationStatus;
using EngineNext::Gameplay::PredictionState;
using EngineNext::Gameplay::Status;

namespace
{

PredictionState MakeState(float fPosition, std::uint64_t nSequence, std::uint64_t nTime)
{
	PredictionState stState;
	stState.vPosition = { fPosition, 0.0F, 0.0F };
	stState.vVelocity = { 10.0F, 0.0F, 0.0F };
	stState.nConfirmedSequence = nSequence;
	stState.nServerTimeMsec = nTime;
	return stState;
}

} // namespace

ENGINE_NEXT_TEST("Interpolation buffer configuration is validated and bounded")
{
	InterpolationBuffer stBuffer;
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetMaxSamples(), 32U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetInterpolationDelayMsec(), 100U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetStaleAfterMsec(), 500U);
	ENGINE_NEXT_CHECK(!stBuffer.SetMaxSamples(1));
	ENGINE_NEXT_CHECK(!stBuffer.SetMaxSamples(4097));
	ENGINE_NEXT_CHECK(!stBuffer.SetInterpolationDelayMsec(60001));
	ENGINE_NEXT_CHECK(!stBuffer.SetStaleAfterMsec(0));
	ENGINE_NEXT_CHECK(!stBuffer.SetStaleAfterMsec(60001));
	ENGINE_NEXT_CHECK(stBuffer.SetMaxSamples(2));
	ENGINE_NEXT_CHECK(stBuffer.SetInterpolationDelayMsec(0));
	ENGINE_NEXT_CHECK(stBuffer.SetStaleAfterMsec(1));
}

ENGINE_NEXT_TEST("Interpolation buffer handles empty single and before-range states")
{
	InterpolationBuffer stBuffer;
	ENGINE_NEXT_CHECK_EQ(stBuffer.Sample(100).eStatus, InterpolationStatus::Empty);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(5.0F, 1, 50)), Status::Ok);
	ENGINE_NEXT_CHECK_EQ(stBuffer.Sample(1000).eStatus, InterpolationStatus::SingleSample);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(20.0F, 2, 300)), Status::Ok);
	const InterpolationResult stResult = stBuffer.Sample(100);
	ENGINE_NEXT_CHECK_EQ(stResult.eStatus, InterpolationStatus::BeforeRange);
	ENGINE_NEXT_CHECK(stResult.stState.has_value());
	ENGINE_NEXT_CHECK_FLOAT(stResult.stState->vPosition.fX, 5.0F);
}

ENGINE_NEXT_TEST("Interpolation buffer sorts interpolates replaces and evicts")
{
	InterpolationBuffer stBuffer;
	ENGINE_NEXT_CHECK(stBuffer.SetMaxSamples(3));
	ENGINE_NEXT_CHECK(stBuffer.SetInterpolationDelayMsec(100));
	ENGINE_NEXT_CHECK(stBuffer.SetStaleAfterMsec(250));
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(20.0F, 2, 300)), Status::Ok);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(0.0F, 1, 100)), Status::Ok);
	const InterpolationResult stInterpolated = stBuffer.Sample(300);
	ENGINE_NEXT_CHECK_EQ(stInterpolated.eStatus, InterpolationStatus::Interpolated);
	ENGINE_NEXT_CHECK(stInterpolated.stState.has_value());
	ENGINE_NEXT_CHECK_FLOAT(stInterpolated.stState->vPosition.fX, 10.0F);
	ENGINE_NEXT_CHECK_FLOAT(stInterpolated.stState->vVelocity.fX, 10.0F);
	ENGINE_NEXT_CHECK_EQ(stInterpolated.stState->nConfirmedSequence, 2U);
	ENGINE_NEXT_CHECK_EQ(stInterpolated.stState->nServerTimeMsec, 200U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(30.0F, 3, 400)), Status::Ok);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(40.0F, 4, 500)), Status::Ok);
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetSampleCount(), 3U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(41.0F, 4, 500)), Status::AlreadyExists);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(42.0F, 5, 500)), Status::Ok);
	const InterpolationResult stHeld = stBuffer.Sample(700);
	ENGINE_NEXT_CHECK_EQ(stHeld.eStatus, InterpolationStatus::Held);
	const InterpolationResult stBoundary = stBuffer.Sample(750);
	ENGINE_NEXT_CHECK_EQ(stBoundary.eStatus, InterpolationStatus::Held);
	const InterpolationResult stStale = stBuffer.Sample(751);
	ENGINE_NEXT_CHECK_EQ(stStale.eStatus, InterpolationStatus::StaleHeld);
	ENGINE_NEXT_CHECK(stStale.stState.has_value());
	ENGINE_NEXT_CHECK_FLOAT(stStale.stState->vPosition.fX, 42.0F);
	ENGINE_NEXT_CHECK_EQ(stStale.stState->nServerTimeMsec, 500U);
}

ENGINE_NEXT_TEST("Interpolation buffer rejects nonfinite samples and isolates results")
{
	InterpolationBuffer stBuffer;
	PredictionState stInvalid = MakeState(0.0F, 1, 100);
	stInvalid.vVelocity.fX = std::numeric_limits<float>::quiet_NaN();
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(stInvalid), Status::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetSampleCount(), 0U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(10.0F, 1, 100)), Status::Ok);
	InterpolationResult stResult = stBuffer.Sample(100);
	ENGINE_NEXT_CHECK(stResult.stState.has_value());
	stResult.stState->vPosition.fX = 99.0F;
	ENGINE_NEXT_CHECK_FLOAT(stBuffer.Sample(100).stState->vPosition.fX, 10.0F);
	stBuffer.Clear();
	ENGINE_NEXT_CHECK_EQ(stBuffer.GetSampleCount(), 0U);
	ENGINE_NEXT_CHECK_EQ(stBuffer.Sample(100).eStatus, InterpolationStatus::Empty);
}

ENGINE_NEXT_TEST("Interpolation buffer avoids timestamp underflow and extrapolation")
{
	InterpolationBuffer stBuffer;
	ENGINE_NEXT_CHECK(stBuffer.SetInterpolationDelayMsec(60000));
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(1.0F, 1, 0)), Status::Ok);
	ENGINE_NEXT_CHECK_EQ(stBuffer.AddSample(MakeState(2.0F, 2, 1)), Status::Ok);
	const InterpolationResult stResult = stBuffer.Sample(10);
	ENGINE_NEXT_CHECK_EQ(stResult.eStatus, InterpolationStatus::BeforeRange);
	ENGINE_NEXT_CHECK_EQ(stResult.stState->nServerTimeMsec, 0U);
	const InterpolationResult stHeld = stBuffer.Sample(std::numeric_limits<std::uint64_t>::max());
	ENGINE_NEXT_CHECK_EQ(stHeld.eStatus, InterpolationStatus::StaleHeld);
	ENGINE_NEXT_CHECK_EQ(stHeld.stState->nServerTimeMsec, 1U);
}
