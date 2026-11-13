/**************************************************************************/
/*  FixedStepLoop.cpp                                                     */
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

#include "engine_next/include/EngineNext/Runtime/FixedStepLoop.h"

#include <limits>

namespace EngineNext::Runtime
{

bool FixedStepLoop::SetFixedStepMsec(std::uint32_t nValue) noexcept
{
	if (nValue == 0 || nValue > 1000)
	{
		return false;
	}
	nFixedStepMsec = nValue;
	return true;
}

bool FixedStepLoop::SetMaxCatchUpSteps(std::uint32_t nValue) noexcept
{
	if (nValue == 0 || nValue > 64)
	{
		return false;
	}
	nMaxCatchUpSteps = nValue;
	return true;
}

std::uint32_t FixedStepLoop::GetFixedStepMsec() const noexcept
{
	return nFixedStepMsec;
}

std::uint64_t FixedStepLoop::GetTick() const noexcept
{
	return nTick;
}

std::uint64_t FixedStepLoop::GetAccumulatorMsec() const noexcept
{
	return nAccumulatorMsec;
}

RuntimeStatus FixedStepLoop::Advance(std::uint64_t nNowMsec, FixedStepBatch &out_stBatch) noexcept
{
	out_stBatch = FixedStepBatch{};
	if (!bStarted)
	{
		nLastNowMsec = nNowMsec;
		bStarted = true;
		return RuntimeStatus::Ok;
	}
	if (nNowMsec < nLastNowMsec)
	{
		return RuntimeStatus::InvalidParameter;
	}

	const std::uint64_t nDeltaMsec = nNowMsec - nLastNowMsec;
	nLastNowMsec = nNowMsec;
	if (nDeltaMsec > std::numeric_limits<std::uint64_t>::max() - nAccumulatorMsec)
	{
		out_stBatch.nDroppedMsec = nDeltaMsec - (std::numeric_limits<std::uint64_t>::max() - nAccumulatorMsec);
		nAccumulatorMsec = std::numeric_limits<std::uint64_t>::max();
	}
	else
	{
		nAccumulatorMsec += nDeltaMsec;
	}

	out_stBatch.nFirstTick = nTick + 1;
	while (nAccumulatorMsec >= nFixedStepMsec && out_stBatch.nStepCount < nMaxCatchUpSteps)
	{
		nAccumulatorMsec -= nFixedStepMsec;
		++nTick;
		++out_stBatch.nStepCount;
	}
	if (nAccumulatorMsec >= nFixedStepMsec)
	{
		const std::uint64_t nDroppedMsec = nAccumulatorMsec - (nAccumulatorMsec % nFixedStepMsec);
		nAccumulatorMsec %= nFixedStepMsec;
		if (nDroppedMsec > std::numeric_limits<std::uint64_t>::max() - out_stBatch.nDroppedMsec)
		{
			out_stBatch.nDroppedMsec = std::numeric_limits<std::uint64_t>::max();
		}
		else
		{
			out_stBatch.nDroppedMsec += nDroppedMsec;
		}
	}
	if (out_stBatch.nStepCount == 0)
	{
		out_stBatch.nFirstTick = 0;
	}
	return RuntimeStatus::Ok;
}

void FixedStepLoop::Reset() noexcept
{
	nLastNowMsec = 0;
	nAccumulatorMsec = 0;
	nTick = 0;
	bStarted = false;
}

} // namespace EngineNext::Runtime
