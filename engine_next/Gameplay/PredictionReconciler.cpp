/**************************************************************************/
/*  PredictionReconciler.cpp                                              */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionReconciler.h"

#include <algorithm>
#include <cmath>

namespace EngineNext::Gameplay
{
namespace
{

float Distance(const Vector3 &in_vLeft, const Vector3 &in_vRight) noexcept
{
	const float fX = in_vLeft.fX - in_vRight.fX;
	const float fY = in_vLeft.fY - in_vRight.fY;
	const float fZ = in_vLeft.fZ - in_vRight.fZ;
	return std::sqrt(fX * fX + fY * fY + fZ * fZ);
}

} // namespace

bool PredictionReconciler::SetInitialState(const PredictionState &in_stState) noexcept
{
	if (!in_stState.vPosition.IsFinite() || !in_stState.vVelocity.IsFinite())
	{
		return false;
	}
	stPredictedState = in_stState;
	arrHistory.clear();
	nLastConfirmedSequence = in_stState.nConfirmedSequence;
	nNextSequence = nLastConfirmedSequence + 1;
	return true;
}

bool PredictionReconciler::PredictInput(const Vector3 &in_vMovement, PredictionInput &out_stInput) noexcept
{
	if (!in_vMovement.IsFinite() || in_vMovement.LengthSquared() > 1.000001F || arrHistory.size() >= nMaxHistory)
	{
		return false;
	}
	out_stInput = PredictionInput{};
	out_stInput.nSequence = nNextSequence++;
	out_stInput.vMovementInput = in_vMovement;
	out_stInput.nStepMsec = stModel.GetFixedStepMsec();
	if (stModel.Simulate(stPredictedState, out_stInput) != Status::Ok)
	{
		return false;
	}
	arrHistory.push_back(HistoryEntry{ out_stInput, stPredictedState });
	return true;
}

bool PredictionReconciler::ApplyAuthoritativeState(const PredictionState &in_stState, float &out_fPositionError) noexcept
{
	out_fPositionError = 0.0F;
	if (!in_stState.vPosition.IsFinite() || !in_stState.vVelocity.IsFinite() ||
		in_stState.nConfirmedSequence < nLastConfirmedSequence)
	{
		return false;
	}
	out_fPositionError = Distance(stPredictedState.vPosition, in_stState.vPosition);
	for (const HistoryEntry &stEntry : arrHistory)
	{
		if (stEntry.stInput.nSequence == in_stState.nConfirmedSequence)
		{
			out_fPositionError = Distance(stEntry.stPredictedState.vPosition, in_stState.vPosition);
			break;
		}
	}
	while (!arrHistory.empty() && arrHistory.front().stInput.nSequence <= in_stState.nConfirmedSequence)
	{
		arrHistory.pop_front();
	}
	stPredictedState = in_stState;
	for (HistoryEntry &stEntry : arrHistory)
	{
		if (stModel.Simulate(stPredictedState, stEntry.stInput) != Status::Ok)
		{
			return false;
		}
		stEntry.stPredictedState = stPredictedState;
	}
	nLastConfirmedSequence = in_stState.nConfirmedSequence;
	if (out_fPositionError > fCorrectionThreshold)
	{
		++nCorrectionCount;
	}
	return true;
}

const PredictionState &PredictionReconciler::GetPredictedState() const noexcept
{
	return stPredictedState;
}

std::size_t PredictionReconciler::GetUnconfirmedInputCount() const noexcept
{
	return arrHistory.size();
}

std::uint64_t PredictionReconciler::GetLastConfirmedSequence() const noexcept
{
	return nLastConfirmedSequence;
}

std::uint32_t PredictionReconciler::GetCorrectionCount() const noexcept
{
	return nCorrectionCount;
}

} // namespace EngineNext::Gameplay
