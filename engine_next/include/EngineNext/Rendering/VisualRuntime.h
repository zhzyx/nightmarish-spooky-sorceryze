/**************************************************************************/
/*  VisualRuntime.h                                                       */
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

#include <cstdint>
#include <string>

namespace EngineNext::Rendering
{

struct VisualConfig
{
	std::uint32_t nWidth = 1280;
	std::uint32_t nHeight = 720;
	std::uint32_t nFrameLimit = 0;
	bool bHidden = false;
	bool bValidation = false;
	bool bVsync = false;
	bool bExerciseResize = false;
	bool bExerciseProjection = false;
	// Offline validation: camera [16,32), light [48,64), source node 1 [80,96).
	bool bExerciseShadowUpdates = false;
	bool bDeterministic = false;
	bool bAnimation = false;
	std::string strShaderDirectory;
	std::string strReportPath;
	std::string strCapturePath;
	std::string strAssetPackagePath;
	std::string strGpuPackagePath;
	std::string strRenderConfigPath;
	std::string strServerAddress = "127.0.0.1";
	std::string strClientId = "A";
	std::uint16_t nServerPort = 0;
	bool bConnect = false;
};

// Runs on the calling UI/render thread until close or the explicit frame limit.
// Returns zero only after all queue fences and requested evidence are complete.
[[nodiscard]] int RunVisualClient(const VisualConfig &stConfig);

} // namespace EngineNext::Rendering
