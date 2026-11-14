/**************************************************************************/
/*  IProcessTransport.h                                                   */
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

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace EngineNext::AI
{

struct ProcessSpec
{
	std::string strExecutable;
	std::vector<std::string> arrArguments;
	std::string strInput;
	std::uint32_t nTimeoutMsec = 60000;
	std::size_t nOutputLimit = 384ULL * 1024ULL * 1024ULL;
};

struct ProcessResult
{
	bool bStarted = false;
	bool bExited = false;
	bool bTimedOut = false;
	bool bOutputOverflow = false;
	int nExitCode = -1;
	std::string strOutput;
	std::string strError;
};

class IProcessTransport
{
public:
	virtual ~IProcessTransport() = default;
	[[nodiscard]] virtual bool Run(const ProcessSpec &in_stSpec, ProcessResult &out_stResult) = 0;
	virtual void Cancel() noexcept = 0;
};

} // namespace EngineNext::AI
