/**************************************************************************/
/*  ClientRuntime.cpp                                                     */
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

#include "engine_next/Client/ClientRuntime.h"

#include "engine_next/Client/ClientSession.h"
#include "engine_next/include/EngineNext/Runtime/Clock.h"

#include <chrono>
#include <thread>

namespace EngineNext::Runtime
{

RuntimeStatus RunClient(const RuntimeConfig &stConfig)
{
	ClientSession stSession;
	RuntimeStatus eStatus = stSession.Initialize(stConfig, ClientSessionMode::Acceptance);
	if (eStatus != RuntimeStatus::Ok)
	{
		return eStatus;
	}
	SystemClock stClock;
	const std::uint64_t nStartedMsec = stClock.NowMsec();
	while (!stSession.HasSucceeded() && stClock.NowMsec() - nStartedMsec < stConfig.nDurationMsec)
	{
		eStatus = stSession.Tick(stClock.NowMsec(), Gameplay::Vector3{});
		if (eStatus != RuntimeStatus::Ok)
		{
			break;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	const bool bSucceeded = stSession.HasSucceeded();
	stSession.Shutdown();
	return bSucceeded && eStatus == RuntimeStatus::Ok ? RuntimeStatus::Ok : RuntimeStatus::IoError;
}

} // namespace EngineNext::Runtime
