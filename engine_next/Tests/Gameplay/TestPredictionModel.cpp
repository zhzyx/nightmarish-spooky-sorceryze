/**************************************************************************/
/*  TestPredictionModel.cpp                                               */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"

#include <limits>

using EngineNext::Gameplay::PredictionInput;
using EngineNext::Gameplay::PredictionModel;
using EngineNext::Gameplay::PredictionState;
using EngineNext::Gameplay::Status;

ENGINE_NEXT_TEST("Prediction model defaults and configuration are bounded")
{
	PredictionModel stModel;
	ENGINE_NEXT_CHECK_FLOAT(stModel.GetMaxSpeed(), 8.0F);
	ENGINE_NEXT_CHECK_EQ(stModel.GetFixedStepMsec(), 16U);
	ENGINE_NEXT_CHECK(stModel.SetMaxSpeed(10.0F));
	ENGINE_NEXT_CHECK(stModel.SetFixedStepMsec(100));
	ENGINE_NEXT_CHECK_FLOAT(stModel.GetMaxSpeed(), 10.0F);
	ENGINE_NEXT_CHECK_EQ(stModel.GetFixedStepMsec(), 100U);
	ENGINE_NEXT_CHECK(!stModel.SetMaxSpeed(0.0F));
	ENGINE_NEXT_CHECK(!stModel.SetMaxSpeed(std::numeric_limits<float>::infinity()));
	ENGINE_NEXT_CHECK(!stModel.SetFixedStepMsec(0));
	ENGINE_NEXT_CHECK(!stModel.SetFixedStepMsec(1001));
	ENGINE_NEXT_CHECK_FLOAT(stModel.GetMaxSpeed(), 10.0F);
	ENGINE_NEXT_CHECK_EQ(stModel.GetFixedStepMsec(), 100U);
}

ENGINE_NEXT_TEST("Prediction model advances one fixed step and preserves server time")
{
	PredictionModel stModel;
	ENGINE_NEXT_CHECK(stModel.SetMaxSpeed(10.0F));
	ENGINE_NEXT_CHECK(stModel.SetFixedStepMsec(100));
	PredictionState stState;
	stState.nServerTimeMsec = 777;
	const PredictionInput stInput{ 42, { 1.0F, 0.0F, 0.0F }, 100 };
	ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stState, stInput), Status::Ok);
	ENGINE_NEXT_CHECK_FLOAT(stState.vPosition.fX, 1.0F);
	ENGINE_NEXT_CHECK_FLOAT(stState.vVelocity.fX, 10.0F);
	ENGINE_NEXT_CHECK_EQ(stState.nConfirmedSequence, 42U);
	ENGINE_NEXT_CHECK_EQ(stState.nServerTimeMsec, 777U);
}

ENGINE_NEXT_TEST("Prediction model rejects invalid input without partial writes")
{
	PredictionModel stModel;
	PredictionState stInitial;
	stInitial.vPosition = { 1.0F, 2.0F, 3.0F };
	stInitial.vVelocity = { 4.0F, 5.0F, 6.0F };
	stInitial.nConfirmedSequence = 9;
	stInitial.nServerTimeMsec = 1000;

	const PredictionInput arrInvalid[] = {
		{ 0, { 1.0F, 0.0F, 0.0F }, 16 },
		{ 10, { 1.0F, 0.0F, 0.0F }, 17 },
		{ 10, { 2.0F, 0.0F, 0.0F }, 16 },
		{ 10, { std::numeric_limits<float>::quiet_NaN(), 0.0F, 0.0F }, 16 },
	};
	for (const PredictionInput &stInput : arrInvalid)
	{
		PredictionState stState = stInitial;
		ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stState, stInput), Status::InvalidParameter);
		ENGINE_NEXT_CHECK_FLOAT(stState.vPosition.fX, stInitial.vPosition.fX);
		ENGINE_NEXT_CHECK_FLOAT(stState.vVelocity.fX, stInitial.vVelocity.fX);
		ENGINE_NEXT_CHECK_EQ(stState.nConfirmedSequence, stInitial.nConfirmedSequence);
	}

	PredictionState stNonFinite = stInitial;
	stNonFinite.vPosition.fY = std::numeric_limits<float>::infinity();
	const PredictionInput stInput{ 10, { 1.0F, 0.0F, 0.0F }, 16 };
	ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stNonFinite, stInput), Status::InvalidParameter);
	ENGINE_NEXT_CHECK_FLOAT(stNonFinite.vVelocity.fX, stInitial.vVelocity.fX);
}

ENGINE_NEXT_TEST("Prediction model rejects arithmetic overflow transactionally")
{
	PredictionModel stModel;
	ENGINE_NEXT_CHECK(stModel.SetMaxSpeed(std::numeric_limits<float>::max()));
	ENGINE_NEXT_CHECK(stModel.SetFixedStepMsec(1000));
	PredictionState stState;
	stState.vPosition.fX = std::numeric_limits<float>::max();
	const PredictionInput stInput{ 1, { 1.0F, 0.0F, 0.0F }, 1000 };
	ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stState, stInput), Status::InvalidParameter);
	ENGINE_NEXT_CHECK_FLOAT(stState.vPosition.fX, std::numeric_limits<float>::max());
	ENGINE_NEXT_CHECK_FLOAT(stState.vVelocity.fX, 0.0F);
	ENGINE_NEXT_CHECK_EQ(stState.nConfirmedSequence, 0U);
}

ENGINE_NEXT_TEST("Prediction model repeated simulation is deterministic")
{
	PredictionModel stModel;
	PredictionState stFirst;
	PredictionState stSecond;
	const PredictionInput stInput{ 1, { 0.25F, -0.5F, 0.75F }, 16 };
	for (int nIndex = 0; nIndex < 100000; ++nIndex)
	{
		PredictionInput stStep = stInput;
		stStep.nSequence = static_cast<std::uint64_t>(nIndex + 1);
		ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stFirst, stStep), Status::Ok);
		ENGINE_NEXT_CHECK_EQ(stModel.Simulate(stSecond, stStep), Status::Ok);
	}
	ENGINE_NEXT_CHECK_FLOAT(stFirst.vPosition.fX, stSecond.vPosition.fX);
	ENGINE_NEXT_CHECK_FLOAT(stFirst.vPosition.fY, stSecond.vPosition.fY);
	ENGINE_NEXT_CHECK_FLOAT(stFirst.vPosition.fZ, stSecond.vPosition.fZ);
	ENGINE_NEXT_CHECK_FLOAT(stFirst.vVelocity.fX, stSecond.vVelocity.fX);
	ENGINE_NEXT_CHECK_EQ(stFirst.nConfirmedSequence, 100000U);
}
