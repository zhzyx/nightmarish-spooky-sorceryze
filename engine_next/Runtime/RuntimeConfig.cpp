/**************************************************************************/
/*  RuntimeConfig.cpp                                                     */
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

#include "engine_next/include/EngineNext/Runtime/RuntimeConfig.h"

#include <cctype>
#include <charconv>
#include <limits>

namespace EngineNext::Runtime
{
namespace
{

bool ParseUnsigned(const std::string &in_strValue, std::uint64_t &out_nValue) noexcept
{
	if (in_strValue.empty())
	{
		return false;
	}
	std::uint64_t nValue = 0;
	const char *pBegin = in_strValue.data();
	const char *pEnd = pBegin + in_strValue.size();
	const std::from_chars_result stResult = std::from_chars(pBegin, pEnd, nValue);
	if (stResult.ec != std::errc() || stResult.ptr != pEnd)
	{
		return false;
	}
	out_nValue = nValue;
	return true;
}

bool IsValidClientId(const std::string &in_strValue) noexcept
{
	if (in_strValue.empty() || in_strValue.size() > 32)
	{
		return false;
	}
	for (const unsigned char nCharacter : in_strValue)
	{
		if (std::isalnum(nCharacter) == 0 && nCharacter != '-' && nCharacter != '_')
		{
			return false;
		}
	}
	return true;
}

bool ParseValue(const std::vector<std::string> &in_arrArguments, std::size_t &inout_nIndex, std::string &out_strValue)
{
	if (inout_nIndex + 1 >= in_arrArguments.size())
	{
		return false;
	}
	out_strValue = in_arrArguments[++inout_nIndex];
	return true;
}

RuntimeStatus ParseUnsignedOption(const std::string &in_strArgument, const std::string &in_strValue, RuntimeConfig &out_stConfig)
{
	std::uint64_t nValue = 0;
	if (!ParseUnsigned(in_strValue, nValue))
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (in_strArgument == "--manual-ticks")
	{
		if (nValue == 0)
		{
			return RuntimeStatus::InvalidParameter;
		}
		out_stConfig.nManualTicks = nValue;
		return RuntimeStatus::Ok;
	}
	if (in_strArgument == "--fixed-step-ms")
	{
		if (nValue == 0 || nValue > 1000)
		{
			return RuntimeStatus::InvalidParameter;
		}
		out_stConfig.nFixedStepMsec = static_cast<std::uint32_t>(nValue);
		return RuntimeStatus::Ok;
	}
	if (in_strArgument == "--seed")
	{
		if (nValue == 0)
		{
			return RuntimeStatus::InvalidParameter;
		}
		out_stConfig.nSeed = nValue;
		return RuntimeStatus::Ok;
	}
	if (in_strArgument == "--port")
	{
		if (nValue > 65535)
		{
			return RuntimeStatus::InvalidParameter;
		}
		out_stConfig.nPort = static_cast<std::uint16_t>(nValue);
		return RuntimeStatus::Ok;
	}
	if (nValue == 0 || nValue > 60000)
	{
		return RuntimeStatus::InvalidParameter;
	}
	out_stConfig.nDurationMsec = static_cast<std::uint32_t>(nValue);
	return RuntimeStatus::Ok;
}

} // namespace

RuntimeStatus ParseArguments(const std::vector<std::string> &in_arrArguments, RuntimeConfig &out_stConfig)
{
	RuntimeConfig stParsed;
	stParsed.eRole = out_stConfig.eRole;
	bool bClientIdProvided = false;
	bool bNetworkEndpointProvided = false;
	for (std::size_t nIndex = 0; nIndex < in_arrArguments.size(); ++nIndex)
	{
		const std::string &strArgument = in_arrArguments[nIndex];
		if (strArgument == "--help")
		{
			stParsed.bHelpRequested = true;
			continue;
		}
		std::string strValue;
		if (strArgument == "--manual-ticks" || strArgument == "--fixed-step-ms" || strArgument == "--seed" ||
			strArgument == "--port" || strArgument == "--duration-ms")
		{
			if (!ParseValue(in_arrArguments, nIndex, strValue))
			{
				return RuntimeStatus::InvalidParameter;
			}
			const RuntimeStatus eStatus = ParseUnsignedOption(strArgument, strValue, stParsed);
			if (eStatus != RuntimeStatus::Ok)
			{
				return eStatus;
			}
			continue;
		}
		if (strArgument == "--trace-output" || strArgument == "--client-id" || strArgument == "--bind" || strArgument == "--connect")
		{
			if (!ParseValue(in_arrArguments, nIndex, strValue) || strValue.empty())
			{
				return RuntimeStatus::InvalidParameter;
			}
			if (strArgument == "--trace-output")
			{
				stParsed.strTracePath = strValue;
			}
			else if (strArgument == "--client-id")
			{
				if (!IsValidClientId(strValue))
				{
					return RuntimeStatus::InvalidParameter;
				}
				stParsed.strClientId = strValue;
				bClientIdProvided = true;
			}
			else
			{
				stParsed.strBindAddress = strValue;
				stParsed.bNetworkMode = true;
				bNetworkEndpointProvided = true;
				if ((strArgument == "--bind" && stParsed.eRole != RuntimeRole::Server) ||
					(strArgument == "--connect" && stParsed.eRole != RuntimeRole::Client))
				{
					return RuntimeStatus::InvalidParameter;
				}
			}
			continue;
		}
		return RuntimeStatus::InvalidParameter;
	}
	if (stParsed.eRole == RuntimeRole::Server && bClientIdProvided)
	{
		return RuntimeStatus::InvalidParameter;
	}
	if (stParsed.bNetworkMode &&
		(!bNetworkEndpointProvided || (stParsed.eRole == RuntimeRole::Client && stParsed.nPort == 0)))
	{
		return RuntimeStatus::InvalidParameter;
	}
	out_stConfig = stParsed;
	return RuntimeStatus::Ok;
}

const char *GetRoleName(RuntimeRole in_eRole) noexcept
{
	return in_eRole == RuntimeRole::Server ? "server" : "client";
}

} // namespace EngineNext::Runtime
