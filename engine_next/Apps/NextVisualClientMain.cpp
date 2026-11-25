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
	bool bScaleProvided = false;
	std::string strUpscaleMode;
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
			std::cout << "next_visual_client [--width N] [--height N] [--diagnostic-view NAME] [--upscale-mode native|spatial] [--render-scale-percent 25..100] [--frames N] [--recording-threads 1|2|4] [--duration-seconds N] [--validation] [--hidden] [--vsync] [--exercise-resize] [--exercise-projection] [--exercise-shadow-updates] [--deterministic] [--animation] [--shader-directory PATH] [--report PATH] [--telemetry PATH] [--capture PATH] [--asset-package PATH] [--gpu-package PATH] [--render-config PATH] [--connect --port N --client-id ID --server ADDRESS]\n";
			std::cout << "Diagnostic views:";
			for (const char *pName : EngineNext::Rendering::DIAGNOSTIC_VIEW_NAMES)
			{
				std::cout << ' ' << pName;
			}
			std::cout << '\n';
			std::cout << "WASD moves camera or connected player. R reconnects a connected session. Escape closes.\n";
			return 0;
		}
		if (strOption == "--validation" || strOption == "--hidden" || strOption == "--vsync" || strOption == "--exercise-resize" || strOption == "--exercise-projection" || strOption == "--exercise-shadow-updates" || strOption == "--deterministic" || strOption == "--connect" || strOption == "--animation")
		{
			stConfig.bValidation = stConfig.bValidation || strOption == "--validation";
			stConfig.bHidden = stConfig.bHidden || strOption == "--hidden";
			stConfig.bVsync = stConfig.bVsync || strOption == "--vsync";
			stConfig.bExerciseResize = stConfig.bExerciseResize || strOption == "--exercise-resize";
			stConfig.bExerciseProjection = stConfig.bExerciseProjection || strOption == "--exercise-projection";
			stConfig.bExerciseShadowUpdates = stConfig.bExerciseShadowUpdates || strOption == "--exercise-shadow-updates";
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
		if (strOption == "--diagnostic-view")
		{
			std::uint32_t nView = 0;
			for (const char *pName : EngineNext::Rendering::DIAGNOSTIC_VIEW_NAMES)
			{
				if (std::strcmp(pName, pValue) == 0)
				{
					break;
				}
				++nView;
			}
			if (nView >= std::size(EngineNext::Rendering::DIAGNOSTIC_VIEW_NAMES))
			{
				std::cerr << "Unknown diagnostic view: " << pValue << '\n';
				return 2;
			}
			stConfig.eDiagnosticView = static_cast<EngineNext::Rendering::DiagnosticView>(nView);
		}
		else if (strOption == "--upscale-mode")
		{
			strUpscaleMode = pValue;
			if (strUpscaleMode != "native" && strUpscaleMode != "spatial")
			{
				std::cerr << "Upscale mode must be native or spatial\n";
				return 2;
			}
		}
		else if (strOption == "--render-scale-percent")
		{
			bScaleProvided = true;
			if (!ParseUnsigned(pValue, stConfig.nRenderScalePercent) || stConfig.nRenderScalePercent < 25 || stConfig.nRenderScalePercent > 100)
			{
				std::cerr << "Render scale must be 25..100 percent\n";
				return 2;
			}
		}
		else if (strOption == "--width" || strOption == "--height" || strOption == "--frames" || strOption == "--recording-threads" || strOption == "--duration-seconds")
		{
			std::uint32_t nValue = 0;
			if (!ParseUnsigned(pValue, nValue))
			{
				std::cerr << "Invalid unsigned integer\n";
				return 2;
			}
			if (strOption == "--recording-threads")
			{
				if (nValue != 1 && nValue != 2 && nValue != 4)
				{
					std::cerr << "Recording threads must be 1, 2 or 4\n";
					return 2;
				}
				stConfig.nRecordingThreads = nValue;
			}
			else if (strOption == "--width")
			{
				stConfig.nWidth = nValue;
			}
			else if (strOption == "--height")
			{
				stConfig.nHeight = nValue;
			}
			else if (strOption == "--frames")
			{
				stConfig.nFrameLimit = nValue;
			}
			else
			{
				stConfig.nDurationSeconds = nValue;
			}
		}
		else if (strOption == "--shader-directory")
		{
			stConfig.strShaderDirectory = pValue;
		}
		else if (strOption == "--telemetry")
		{
			stConfig.strTelemetryPath = pValue;
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
	if (strUpscaleMode == "spatial" && !bScaleProvided)
	{
		stConfig.nRenderScalePercent = 50;
	}
	if ((strUpscaleMode == "native" && stConfig.nRenderScalePercent != 100) || (strUpscaleMode == "spatial" && stConfig.nRenderScalePercent == 100))
	{
		std::cerr << "Native mode requires 100 percent; spatial mode requires 25..99 percent\n";
		return 2;
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
