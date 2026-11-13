/**************************************************************************/
/*  RuntimeConfig.h                                                       */
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

#pragma once

#include "engine_next/include/EngineNext/Runtime/Types.h"

#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::Runtime
{

struct RuntimeConfig
{
	RuntimeRole eRole = RuntimeRole::Server;
	std::uint64_t nManualTicks = 1;
	std::uint32_t nFixedStepMsec = 16;
	std::uint64_t nSeed = 1;
	std::string strClientId = "A";
	std::string strTracePath;
	std::string strBindAddress = "127.0.0.1";
	std::uint16_t nPort = 0;
	std::uint32_t nDurationMsec = 5000;
	bool bNetworkMode = false;
	bool bHelpRequested = false;
};

[[nodiscard]] RuntimeStatus ParseArguments(const std::vector<std::string> &in_arrArguments, RuntimeConfig &out_stConfig);
[[nodiscard]] const char *GetRoleName(RuntimeRole in_eRole) noexcept;

} // namespace EngineNext::Runtime
