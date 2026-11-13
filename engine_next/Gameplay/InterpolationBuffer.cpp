/**************************************************************************/
/*  InterpolationBuffer.cpp                                               */
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

#include "engine_next/include/EngineNext/Gameplay/InterpolationBuffer.h"

namespace EngineNext::Gameplay
{

bool InterpolationBuffer::SetMaxSamples(std::size_t nValue) noexcept
{
	if (nValue < 2 || nValue > 4096)
	{
		return false;
	}

	nMaxSamples = nValue;
	while (arrSamples.size() > nMaxSamples)
	{
		arrSamples.erase(arrSamples.begin());
	}
	return true;
}

std::size_t InterpolationBuffer::GetMaxSamples() const noexcept
{
	return nMaxSamples;
}

bool InterpolationBuffer::SetInterpolationDelayMsec(std::uint64_t nValue) noexcept
{
	if (nValue > 60000)
	{
		return false;
	}

	nInterpolationDelayMsec = nValue;
	return true;
}

std::uint64_t InterpolationBuffer::GetInterpolationDelayMsec() const noexcept
{
	return nInterpolationDelayMsec;
}

bool InterpolationBuffer::SetStaleAfterMsec(std::uint64_t nValue) noexcept
{
	if (nValue == 0 || nValue > 60000)
	{
		return false;
	}

	nStaleAfterMsec = nValue;
	return true;
}

std::uint64_t InterpolationBuffer::GetStaleAfterMsec() const noexcept
{
	return nStaleAfterMsec;
}

Status InterpolationBuffer::AddSample(const PredictionState &in_stState)
{
	if (!in_stState.vPosition.IsFinite() || !in_stState.vVelocity.IsFinite())
	{
		return Status::InvalidParameter;
	}

	const std::uint64_t nSampleTime = in_stState.nServerTimeMsec;
	std::size_t nInsertAt = arrSamples.size();
	for (std::size_t nIndex = 0; nIndex < arrSamples.size(); ++nIndex)
	{
		const PredictionState &stExisting = arrSamples[nIndex];
		if (stExisting.nServerTimeMsec == nSampleTime)
		{
			if (in_stState.nConfirmedSequence <= stExisting.nConfirmedSequence)
			{
				return Status::AlreadyExists;
			}

			arrSamples[nIndex] = in_stState;
			return Status::Ok;
		}
		if (nSampleTime < stExisting.nServerTimeMsec)
		{
			nInsertAt = nIndex;
			break;
		}
	}

	const std::deque<PredictionState>::difference_type nOffset = static_cast<std::deque<PredictionState>::difference_type>(nInsertAt);
	arrSamples.insert(arrSamples.begin() + nOffset, in_stState);
	while (arrSamples.size() > nMaxSamples)
	{
		arrSamples.erase(arrSamples.begin());
	}
	return Status::Ok;
}

InterpolationResult InterpolationBuffer::Sample(std::uint64_t nNowMsec) const noexcept
{
	InterpolationResult stResult;
	if (arrSamples.empty())
	{
		return stResult;
	}

	const std::uint64_t nTargetTime = nNowMsec > nInterpolationDelayMsec ? nNowMsec - nInterpolationDelayMsec : 0;
	if (arrSamples.size() == 1 || nTargetTime <= arrSamples.front().nServerTimeMsec)
	{
		stResult.eStatus = arrSamples.size() == 1 ? InterpolationStatus::SingleSample : InterpolationStatus::BeforeRange;
		stResult.stState = arrSamples.front();
		return stResult;
	}

	for (std::size_t nIndex = 1; nIndex < arrSamples.size(); ++nIndex)
	{
		const PredictionState &stPrevious = arrSamples[nIndex - 1];
		const PredictionState &stNext = arrSamples[nIndex];
		if (nTargetTime <= stNext.nServerTimeMsec)
		{
			const std::uint64_t nSpan = stNext.nServerTimeMsec - stPrevious.nServerTimeMsec;
			const float fWeight = nSpan == 0 ? 1.0F : static_cast<float>(nTargetTime - stPrevious.nServerTimeMsec) / static_cast<float>(nSpan);
			PredictionState stInterpolated;
			if (!TryLerp(stPrevious.vPosition, stNext.vPosition, fWeight, stInterpolated.vPosition) || !TryLerp(stPrevious.vVelocity, stNext.vVelocity, fWeight, stInterpolated.vVelocity))
			{
				stResult.eStatus = InterpolationStatus::NumericError;
				stResult.stState.reset();
				return stResult;
			}
			stInterpolated.nConfirmedSequence = stNext.nConfirmedSequence;
			stInterpolated.nServerTimeMsec = nTargetTime;
			stResult.eStatus = InterpolationStatus::Interpolated;
			stResult.stState = stInterpolated;
			return stResult;
		}
	}

	const PredictionState &stLatest = arrSamples.back();
	const bool bStale = nNowMsec > stLatest.nServerTimeMsec && nNowMsec - stLatest.nServerTimeMsec > nStaleAfterMsec;
	stResult.eStatus = bStale ? InterpolationStatus::StaleHeld : InterpolationStatus::Held;
	stResult.stState = stLatest;
	return stResult;
}

std::size_t InterpolationBuffer::GetSampleCount() const noexcept
{
	return arrSamples.size();
}

void InterpolationBuffer::Clear() noexcept
{
	arrSamples.clear();
}

} // namespace EngineNext::Gameplay
