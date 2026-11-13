/**************************************************************************/
/*  RuntimeHost.cpp                                                       */
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

#include "engine_next/include/EngineNext/Runtime/RuntimeHost.h"

namespace EngineNext::Runtime
{

RuntimeHost::RuntimeHost(RuntimeRole in_eRole)
{
	stConfig.eRole = in_eRole;
}

RuntimeHost::~RuntimeHost()
{
	Shutdown();
}

RuntimeStatus RuntimeHost::Initialize(const RuntimeConfig &in_stConfig)
{
	if (bInitialized || in_stConfig.eRole != stConfig.eRole || in_stConfig.nManualTicks == 0)
	{
		return RuntimeStatus::InvalidState;
	}
	stConfig = in_stConfig;
	stWorld.Clear();
	stManualClock.Reset();
	stFixedStepLoop.Reset();
	if (!stFixedStepLoop.SetFixedStepMsec(stConfig.nFixedStepMsec))
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (!stConfig.strTracePath.empty())
	{
		const RuntimeStatus eOpenStatus = stTrace.Open(stConfig.strTracePath);
		if (eOpenStatus != RuntimeStatus::Ok)
		{
			return eOpenStatus;
		}
	}
	bInitialized = true;
	const RuntimeStatus eTraceStatus = stTrace.Record(0, "runtime_start", EntityId{}, stConfig.nSeed);
	if (eTraceStatus != RuntimeStatus::Ok)
	{
		Shutdown();
		return eTraceStatus;
	}
	return RuntimeStatus::Ok;
}

RuntimeStatus RuntimeHost::Run()
{
	if (!bInitialized || bRunning)
	{
		return RuntimeStatus::InvalidState;
	}
	bRunning = true;
	FixedStepBatch stPrimeBatch;
	const RuntimeStatus ePrimeStatus = stFixedStepLoop.Advance(stManualClock.NowMsec(), stPrimeBatch);
	if (ePrimeStatus != RuntimeStatus::Ok)
	{
		bRunning = false;
		return ePrimeStatus;
	}
	for (std::uint64_t nIndex = 0; nIndex < stConfig.nManualTicks; ++nIndex)
	{
		if (!stManualClock.AdvanceMsec(stConfig.nFixedStepMsec))
		{
			bRunning = false;
			return RuntimeStatus::InvalidState;
		}
		FixedStepBatch stBatch;
		const RuntimeStatus eAdvanceStatus = stFixedStepLoop.Advance(stManualClock.NowMsec(), stBatch);
		if (eAdvanceStatus != RuntimeStatus::Ok)
		{
			bRunning = false;
			return eAdvanceStatus;
		}
		for (std::uint32_t nStep = 0; nStep < stBatch.nStepCount; ++nStep)
		{
			const std::uint64_t nTick = stBatch.nFirstTick + nStep;
			const RuntimeStatus eTraceStatus = stTrace.Record(nTick, "tick", EntityId{}, nTick);
			if (eTraceStatus != RuntimeStatus::Ok)
			{
				bRunning = false;
				return eTraceStatus;
			}
		}
	}
	bRunning = false;
	return RuntimeStatus::Ok;
}

World &RuntimeHost::GetWorld() noexcept
{
	return stWorld;
}

FixedStepLoop &RuntimeHost::GetFixedStepLoop() noexcept
{
	return stFixedStepLoop;
}

ManualClock &RuntimeHost::GetManualClock() noexcept
{
	return stManualClock;
}

bool RuntimeHost::IsInitialized() const noexcept
{
	return bInitialized;
}

void RuntimeHost::Shutdown() noexcept
{
	if (bInitialized)
	{
		const RuntimeStatus eTraceStatus = stTrace.Record(stFixedStepLoop.GetTick(), "runtime_stop", EntityId{}, stWorld.Count());
		(void)eTraceStatus;
	}
	bRunning = false;
	bInitialized = false;
	stWorld.Clear();
	stFixedStepLoop.Reset();
	stManualClock.Reset();
	stTrace.Close();
}

} // namespace EngineNext::Runtime
