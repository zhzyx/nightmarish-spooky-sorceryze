/**************************************************************************/
/*  PredictionModel.cpp                                                   */
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

#include "engine_next/include/EngineNext/Gameplay/PredictionModel.h"

#include <cmath>

namespace EngineNext::Gameplay
{

bool PredictionModel::SetMaxSpeed(float fValue) noexcept
{
	if (!std::isfinite(fValue) || fValue <= 0.0F)
	{
		return false;
	}

	fMaxSpeed = fValue;
	return true;
}

float PredictionModel::GetMaxSpeed() const noexcept
{
	return fMaxSpeed;
}

bool PredictionModel::SetFixedStepMsec(std::uint32_t nValue) noexcept
{
	if (nValue == 0 || nValue > 1000)
	{
		return false;
	}

	nFixedStepMsec = nValue;
	return true;
}

std::uint32_t PredictionModel::GetFixedStepMsec() const noexcept
{
	return nFixedStepMsec;
}

Status PredictionModel::Simulate(PredictionState &out_stState, const PredictionInput &in_stInput) const noexcept
{
	if (in_stInput.nSequence == 0 || in_stInput.nStepMsec != nFixedStepMsec)
	{
		return Status::InvalidParameter;
	}
	if (!out_stState.vPosition.IsFinite() || !out_stState.vVelocity.IsFinite() || !in_stInput.vMovementInput.IsFinite())
	{
		return Status::InvalidParameter;
	}
	if (in_stInput.vMovementInput.LengthSquared() > 1.000001F)
	{
		return Status::InvalidParameter;
	}

	PredictionState stNext = out_stState;
	stNext.vVelocity = Scale(in_stInput.vMovementInput, fMaxSpeed);
	const float fDeltaSeconds = static_cast<float>(static_cast<double>(nFixedStepMsec) / 1000.0);
	stNext.vPosition = Add(stNext.vPosition, Scale(stNext.vVelocity, fDeltaSeconds));
	stNext.nConfirmedSequence = in_stInput.nSequence;
	if (!stNext.vPosition.IsFinite() || !stNext.vVelocity.IsFinite())
	{
		return Status::InvalidParameter;
	}

	out_stState = stNext;
	return Status::Ok;
}

} // namespace EngineNext::Gameplay
