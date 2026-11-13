/**************************************************************************/
/*  TestPredictionReconciler.cpp                                          */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionReconciler.h"
#include "engine_next/include/EngineNext/Network/Protocol.h"

ENGINE_NEXT_TEST("Reconciler resets to authority and replays only unconfirmed inputs")
{
	EngineNext::Gameplay::PredictionReconciler stPrediction;
	ENGINE_NEXT_CHECK(stPrediction.SetInitialState({}));
	EngineNext::Gameplay::PredictionInput stInput;
	ENGINE_NEXT_CHECK(stPrediction.PredictInput(EngineNext::Gameplay::Vector3{ 1.0F, 0.0F, 0.0F }, stInput));
	ENGINE_NEXT_CHECK(stPrediction.PredictInput(EngineNext::Gameplay::Vector3{ 1.0F, 0.0F, 0.0F }, stInput));
	ENGINE_NEXT_CHECK(stPrediction.PredictInput(EngineNext::Gameplay::Vector3{ 1.0F, 0.0F, 0.0F }, stInput));
	ENGINE_NEXT_CHECK_FLOAT(stPrediction.GetPredictedState().vPosition.fX, 0.384F);

	EngineNext::Gameplay::PredictionState stAuthority = stPrediction.GetPredictedState();
	stAuthority.vPosition.fX = 0.5F;
	stAuthority.nConfirmedSequence = 2;
	float fError = 0.0F;
	ENGINE_NEXT_CHECK(stPrediction.ApplyAuthoritativeState(stAuthority, fError));
	ENGINE_NEXT_CHECK(fError > 0.24F && fError < 0.25F);
	ENGINE_NEXT_CHECK_FLOAT(stPrediction.GetPredictedState().vPosition.fX, 0.628F);
	ENGINE_NEXT_CHECK_EQ(stPrediction.GetUnconfirmedInputCount(), 1ULL);
	ENGINE_NEXT_CHECK_EQ(stPrediction.GetCorrectionCount(), 1ULL);

	stAuthority = stPrediction.GetPredictedState();
	stAuthority.nConfirmedSequence = 3;
	ENGINE_NEXT_CHECK(stPrediction.ApplyAuthoritativeState(stAuthority, fError));
	ENGINE_NEXT_CHECK_EQ(stPrediction.GetUnconfirmedInputCount(), 0ULL);
	ENGINE_NEXT_CHECK_EQ(stPrediction.GetLastConfirmedSequence(), 3ULL);
	stAuthority.nConfirmedSequence = 1;
	ENGINE_NEXT_CHECK(!stPrediction.ApplyAuthoritativeState(stAuthority, fError));
}

ENGINE_NEXT_TEST("Input and snapshot payloads preserve fixed-step movement and authority")
{
	EngineNext::Network::InputCommand stCommand;
	stCommand.nEntityId = 9;
	stCommand.stInput.nSequence = 7;
	stCommand.stInput.nStepMsec = 16;
	stCommand.stInput.vMovementInput = EngineNext::Gameplay::Vector3{ 1.0F, 0.0F, 0.0F };
	const std::vector<std::uint8_t> arrInput = EngineNext::Network::EncodeInputCommand(stCommand);
	ENGINE_NEXT_CHECK_EQ(arrInput.size(), 32ULL);
	EngineNext::Network::InputCommand stDecodedInput;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Network::DecodeInputCommand(arrInput.data(), arrInput.size(), stDecodedInput),
			EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecodedInput.nEntityId, 9ULL);
	ENGINE_NEXT_CHECK_EQ(stDecodedInput.stInput.nSequence, 7ULL);
	ENGINE_NEXT_CHECK_FLOAT(stDecodedInput.stInput.vMovementInput.fX, 1.0F);

	EngineNext::Network::Snapshot stSnapshot;
	stSnapshot.nServerTick = 48;
	stSnapshot.nEntityId = 9;
	stSnapshot.nLastProcessedInputSequence = 7;
	stSnapshot.vPosition = EngineNext::Gameplay::Vector3{ 3.0F, 2.0F, 1.0F };
	stSnapshot.vVelocity = EngineNext::Gameplay::Vector3{ 8.0F, 0.0F, 0.0F };
	const std::vector<std::uint8_t> arrSnapshot = EngineNext::Network::EncodeSnapshot(stSnapshot);
	ENGINE_NEXT_CHECK_EQ(arrSnapshot.size(), 48ULL);
	EngineNext::Network::Snapshot stDecodedSnapshot;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Network::DecodeSnapshot(arrSnapshot.data(), arrSnapshot.size(), stDecodedSnapshot),
			EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stDecodedSnapshot.nServerTick, 48ULL);
	ENGINE_NEXT_CHECK_EQ(stDecodedSnapshot.nLastProcessedInputSequence, 7ULL);
	ENGINE_NEXT_CHECK_FLOAT(stDecodedSnapshot.vPosition.fX, 3.0F);
	ENGINE_NEXT_CHECK_FLOAT(stDecodedSnapshot.vVelocity.fX, 8.0F);
}
