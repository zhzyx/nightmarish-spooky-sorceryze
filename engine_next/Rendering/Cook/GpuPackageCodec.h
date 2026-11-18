/**************************************************************************/
/*  GpuPackageCodec.h                                                     */
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

#include "engine_next/include/EngineNext/Rendering/RenderScene.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace EngineNext::Rendering
{
// Private shared codec boundary. Input is a validated M3 scene. Metadata retains
// all non-payload fields while geometry, images and mip bytes live in pages.
[[nodiscard]] bool PrepareGpuSceneForPaging(const RenderScene &stSource, RenderScene &out_stPrepared, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool EncodeGpuSceneMetadata(const RenderScene &stPrepared, std::vector<std::uint8_t> &out_arrBytes, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool DecodeGpuSceneMetadata(const std::vector<std::uint8_t> &arrBytes, const std::string &strSourceDigest, RenderScene &out_stMetadata, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool PublishGpuDirectoryNoReplace(const std::filesystem::path &stSource, const std::filesystem::path &stTarget);
} // namespace EngineNext::Rendering
