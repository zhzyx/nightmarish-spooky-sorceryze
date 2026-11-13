/**************************************************************************/
/*  TestRuntimeHost.cpp                                                   */
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

#include "engine_next/include/EngineNext/Runtime/RuntimeHost.h"

#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

namespace
{

bool RunTrace(const std::string &in_strPath)
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Server;
	stConfig.nManualTicks = 3;
	stConfig.nSeed = 7;
	stConfig.strTracePath = in_strPath;
	EngineNext::Runtime::RuntimeHost stHost(EngineNext::Runtime::RuntimeRole::Server);
	if (stHost.Initialize(stConfig) != EngineNext::Runtime::RuntimeStatus::Ok)
	{
		return false;
	}
	EngineNext::Runtime::EntityId stEntity;
	if (stHost.GetWorld().Create(stEntity) != EngineNext::Runtime::RuntimeStatus::Ok)
	{
		return false;
	}
	if (stHost.Run() != EngineNext::Runtime::RuntimeStatus::Ok)
	{
		return false;
	}
	const bool bTicksMatch = stHost.GetFixedStepLoop().GetTick() == 3;
	stHost.Shutdown();
	return bTicksMatch && !stHost.IsInitialized() && stHost.GetWorld().Count() == 0;
}

std::string ReadFile(const std::string &in_strPath)
{
	std::ifstream stStream(in_strPath);
	return std::string(std::istreambuf_iterator<char>(stStream), std::istreambuf_iterator<char>());
}

} // namespace

ENGINE_NEXT_TEST("RuntimeHost owns lifecycle and writes repeatable deterministic traces")
{
	const std::string strFirst = "RuntimeHostFirst.jsonl";
	const std::string strSecond = "RuntimeHostSecond.jsonl";
	std::remove(strFirst.c_str());
	std::remove(strSecond.c_str());
	ENGINE_NEXT_CHECK(RunTrace(strFirst));
	ENGINE_NEXT_CHECK(RunTrace(strSecond));
	const std::string strExpected =
			"{\"tick\":0,\"event\":\"runtime_start\",\"entity_id\":0,\"value\":7}\n"
			"{\"tick\":1,\"event\":\"tick\",\"entity_id\":0,\"value\":1}\n"
			"{\"tick\":2,\"event\":\"tick\",\"entity_id\":0,\"value\":2}\n"
			"{\"tick\":3,\"event\":\"tick\",\"entity_id\":0,\"value\":3}\n"
			"{\"tick\":3,\"event\":\"runtime_stop\",\"entity_id\":0,\"value\":1}\n";
	ENGINE_NEXT_CHECK_EQ(ReadFile(strFirst), strExpected);
	ENGINE_NEXT_CHECK_EQ(ReadFile(strFirst), ReadFile(strSecond));
	std::remove(strFirst.c_str());
	std::remove(strSecond.c_str());

	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Client;
	stConfig.nManualTicks = 1;
	EngineNext::Runtime::RuntimeHost stHost(EngineNext::Runtime::RuntimeRole::Client);
	ENGINE_NEXT_CHECK_EQ(stHost.Initialize(stConfig), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stHost.Run(), EngineNext::Runtime::RuntimeStatus::Ok);
	ENGINE_NEXT_CHECK_EQ(stHost.Run(), EngineNext::Runtime::RuntimeStatus::Ok);
	stHost.Shutdown();
	stHost.Shutdown();
}
