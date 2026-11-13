/**************************************************************************/
/*  NextServerMain.cpp                                                    */
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

#include "engine_next/Server/ServerRuntime.h"
#include "engine_next/include/EngineNext/Runtime/RuntimeHost.h"

#include <iostream>
#include <string>
#include <vector>

namespace
{

void PrintUsage()
{
	std::cout << "Usage: next_server [--manual-ticks N] [--fixed-step-ms N] [--seed N] [--trace-output PATH]\n";
}

} // namespace

int main(int nArgumentCount, char **ppArguments)
{
	EngineNext::Runtime::RuntimeConfig stConfig;
	stConfig.eRole = EngineNext::Runtime::RuntimeRole::Server;
	std::vector<std::string> arrArguments;
	for (int nIndex = 1; nIndex < nArgumentCount; ++nIndex)
	{
		arrArguments.emplace_back(ppArguments[nIndex]);
	}
	EngineNext::Runtime::RuntimeStatus eStatus = EngineNext::Runtime::ParseArguments(arrArguments, stConfig);
	if (eStatus != EngineNext::Runtime::RuntimeStatus::Ok)
	{
		PrintUsage();
		return 2;
	}
	if (stConfig.bHelpRequested)
	{
		PrintUsage();
		return 0;
	}
	if (stConfig.bNetworkMode)
	{
		eStatus = EngineNext::Runtime::RunServer(stConfig);
		if (eStatus != EngineNext::Runtime::RuntimeStatus::Ok)
		{
			std::cerr << "Server network runtime failed with status " << static_cast<int>(eStatus) << '\n';
			return 1;
		}
		std::cout << "ENGINE_NEXT_RUNTIME role=server network=ok status=ok\n";
		return 0;
	}

	EngineNext::Runtime::RuntimeHost stHost(EngineNext::Runtime::RuntimeRole::Server);
	eStatus = stHost.Initialize(stConfig);
	if (eStatus == EngineNext::Runtime::RuntimeStatus::Ok)
	{
		eStatus = stHost.Run();
	}
	const std::uint64_t nTicks = stHost.GetFixedStepLoop().GetTick();
	stHost.Shutdown();
	if (eStatus != EngineNext::Runtime::RuntimeStatus::Ok)
	{
		std::cerr << "Server runtime failed with status " << static_cast<int>(eStatus) << '\n';
		return 1;
	}
	std::cout << "ENGINE_NEXT_RUNTIME role=server ticks=" << nTicks << " status=ok\n";
	return 0;
}
