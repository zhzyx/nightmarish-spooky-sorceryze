/**************************************************************************/
/*  TestRuntimeConfig.cpp                                                 */
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

#include "engine_next/include/EngineNext/Runtime/RuntimeConfig.h"

ENGINE_NEXT_TEST("Runtime arguments are explicit, bounded and role checked")
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Client;
	const std::vector<std::string> arrValid{
		"--manual-ticks", "10", "--fixed-step-ms", "20", "--seed", "7",
		"--client-id", "Bob-2", "--trace-output", "Client.jsonl"
	};
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments(arrValid, stConfig), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stConfig.nManualTicks, 10ULL);
	ENGINE_NEXT_CHECK_EQ(stConfig.nFixedStepMsec, 20ULL);
	ENGINE_NEXT_CHECK_EQ(stConfig.nSeed, 7ULL);
	ENGINE_NEXT_CHECK_EQ(stConfig.strClientId, "Bob-2");
	ENGINE_NEXT_CHECK_EQ(stConfig.strTracePath, "Client.jsonl");

	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Server;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--client-id", "A" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--manual-ticks", "0" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--fixed-step-ms", "1001" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--seed", "nope" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--unknown" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--help" }, stConfig), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stConfig.bHelpRequested);
}

ENGINE_NEXT_TEST("Reconnect impairment and drain arguments are bounded and role checked")
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Server;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--drain-after-ms", "3000" }, stConfig), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stConfig.nDrainAfterMsec, 3000U);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--m2-reconnect" }, stConfig), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--impairment-loss-permille", "1001" }, stConfig), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--impairment-queue-capacity", "0" }, stConfig), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Client;
	ENGINE_NEXT_CHECK_EQ(
			EngineNext::Runtime::ParseArguments({ "--m2-reconnect", "--drop-first-input", "--impairment-delay-ms", "8", "--impairment-jitter-ms", "3", "--impairment-queue-capacity", "16" }, stConfig),
			EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stConfig.bReconnectTest);
	ENGINE_NEXT_CHECK(stConfig.bDropFirstInput);
	ENGINE_NEXT_CHECK_EQ(stConfig.nImpairmentDelayMsec, 8ULL);
	ENGINE_NEXT_CHECK_EQ(stConfig.nImpairmentJitterMsec, 3ULL);
	ENGINE_NEXT_CHECK_EQ(stConfig.nImpairmentQueueCapacity, 16U);
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--drain-after-ms", "3000" }, stConfig), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
}

ENGINE_NEXT_TEST("Drain acknowledgement fault injection is client only")
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Client;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--withhold-drain-ack" }, stConfig), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK(stConfig.bWithholdDrainAck);
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Server;
	ENGINE_NEXT_CHECK_EQ(EngineNext::Runtime::ParseArguments({ "--withhold-drain-ack" }, stConfig), EngineNext::Runtime::RuntimeStatus::InvalidParameter);
}
