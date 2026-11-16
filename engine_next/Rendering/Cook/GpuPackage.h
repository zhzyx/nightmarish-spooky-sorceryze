/**************************************************************************/
/*  GpuPackage.h                                                          */
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

#include <string>

namespace EngineNext::Rendering
{

struct GpuCookConfig
{
	// Version two includes uncompressed texture mips and initial mesh clusters.
	// Image-backed materials require a supported pixel decoder on this host.
	bool bPrepareGpuData = true;
};

// CPU-only deterministic legacy version-one cook. The original package remains read-only. Existing
// matching output reconciles; different content is never overwritten.
[[nodiscard]] bool CookGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage, Assets::Diagnostics &out_arrDiagnostics);
[[nodiscard]] bool CookGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage, const GpuCookConfig &stConfig, Assets::Diagnostics &out_arrDiagnostics);

// Verifies canonical manifest, exact files, declared source digest, page hashes,
// bounded little-endian layout, and render references before replacing output.
// Use VerifyCookedScene to bind the decoded payload to a validated source scene.
[[nodiscard]] bool LoadGpuPackage(const std::string &strPackage, const std::string &strExpectedSourceDigest, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics);

// Both inputs must come from validated source/package loaders. Compares every
// canonical field, including identity, geometry, materials, images and instances.
// Startup-only validation uses at most two 512 MiB temporary encoded pages.
[[nodiscard]] bool VerifyCookedScene(const RenderScene &stSource, const RenderScene &stCooked, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
