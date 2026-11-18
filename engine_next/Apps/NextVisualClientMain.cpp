/**************************************************************************/
/*  NextVisualClientMain.cpp                                              */
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

#include "engine_next/include/EngineNext/Rendering/VisualRuntime.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#include <array>
#include <charconv>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <string>
#include <system_error>

namespace
{

bool ParseUnsigned(const char *pValue, std::uint32_t &out_nValue)
{
	const char *pEnd = pValue + std::strlen(pValue);
	const std::from_chars_result stResult = std::from_chars(pValue, pEnd, out_nValue);
	return stResult.ec == std::errc{} && stResult.ptr == pEnd;
}

} // namespace

int main(int nArgumentCount, char **ppArguments)
{
	EngineNext::Rendering::VisualConfig stConfig;
	bool bExplicitClientId = false;
	std::array<wchar_t, 32768> arrModulePath{};
	const DWORD nPathLength = GetModuleFileNameW(nullptr, arrModulePath.data(), static_cast<DWORD>(arrModulePath.size()));
	if (nPathLength == 0 || nPathLength >= arrModulePath.size())
	{
		std::cerr << "Cannot resolve executable directory\n";
		return 2;
	}
	stConfig.strShaderDirectory = std::filesystem::path(arrModulePath.data()).parent_path().u8string();
	for (int nIndex = 1; nIndex < nArgumentCount; ++nIndex)
	{
		const std::string strOption = ppArguments[nIndex];
		if (strOption == "--help")
		{
			std::cout << "next_visual_client [--width N] [--height N] [--frames N] [--validation] [--hidden] [--vsync] [--exercise-resize] [--deterministic] [--animation] [--shader-directory PATH] [--report PATH] [--capture PATH] [--asset-package PATH] [--gpu-package PATH] [--render-config PATH] [--connect --port N --client-id ID --server ADDRESS]\n";
			std::cout << "WASD moves camera or connected player. R reconnects a connected session. Escape closes.\n";
			return 0;
		}
		if (strOption == "--validation" || strOption == "--hidden" || strOption == "--vsync" || strOption == "--exercise-resize" || strOption == "--deterministic" || strOption == "--connect" || strOption == "--animation")
		{
			stConfig.bValidation = stConfig.bValidation || strOption == "--validation";
			stConfig.bHidden = stConfig.bHidden || strOption == "--hidden";
			stConfig.bVsync = stConfig.bVsync || strOption == "--vsync";
			stConfig.bExerciseResize = stConfig.bExerciseResize || strOption == "--exercise-resize";
			stConfig.bDeterministic = stConfig.bDeterministic || strOption == "--deterministic";
			stConfig.bAnimation = stConfig.bAnimation || strOption == "--animation";
			stConfig.bConnect = stConfig.bConnect || strOption == "--connect";
			continue;
		}
		if (nIndex + 1 >= nArgumentCount)
		{
			std::cerr << "Missing value for " << strOption << '\n';
			return 2;
		}
		const char *pValue = ppArguments[++nIndex];
		if (strOption == "--width" || strOption == "--height" || strOption == "--frames")
		{
			std::uint32_t nValue = 0;
			if (!ParseUnsigned(pValue, nValue))
			{
				std::cerr << "Invalid unsigned integer\n";
				return 2;
			}
			if (strOption == "--width")
			{
				stConfig.nWidth = nValue;
			}
			else if (strOption == "--height")
			{
				stConfig.nHeight = nValue;
			}
			else
			{
				stConfig.nFrameLimit = nValue;
			}
		}
		else if (strOption == "--shader-directory")
		{
			stConfig.strShaderDirectory = pValue;
		}
		else if (strOption == "--report")
		{
			stConfig.strReportPath = pValue;
		}
		else if (strOption == "--asset-package")
		{
			stConfig.strAssetPackagePath = pValue;
		}
		else if (strOption == "--gpu-package")
		{
			stConfig.strGpuPackagePath = pValue;
		}
		else if (strOption == "--render-config")
		{
			stConfig.strRenderConfigPath = pValue;
		}
		else if (strOption == "--server")
		{
			stConfig.strServerAddress = pValue;
		}
		else if (strOption == "--client-id")
		{
			stConfig.strClientId = pValue;
			bExplicitClientId = !stConfig.strClientId.empty();
		}
		else if (strOption == "--port")
		{
			std::uint32_t nPort = 0;
			if (!ParseUnsigned(pValue, nPort) || nPort == 0 || nPort > 65535)
			{
				std::cerr << "Invalid server port\n";
				return 2;
			}
			stConfig.nServerPort = static_cast<std::uint16_t>(nPort);
		}
		else if (strOption == "--capture")
		{
			stConfig.strCapturePath = pValue;
		}
		else
		{
			std::cerr << "Unknown option " << strOption << '\n';
			return 2;
		}
	}
	if (stConfig.nWidth < 64 || stConfig.nHeight < 64 || stConfig.nWidth > 8192 || stConfig.nHeight > 8192)
	{
		std::cerr << "Window dimensions must be in [64, 8192]\n";
		return 2;
	}
	if (stConfig.bConnect && (stConfig.nServerPort == 0 || stConfig.strAssetPackagePath.empty() || !bExplicitClientId))
	{
		std::cerr << "--connect requires --port, --client-id and --asset-package\n";
		return 2;
	}
	return EngineNext::Rendering::RunVisualClient(stConfig);
}
