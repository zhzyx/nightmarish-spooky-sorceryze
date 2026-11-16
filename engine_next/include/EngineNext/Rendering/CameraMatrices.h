/**************************************************************************/
/*  CameraMatrices.h                                                      */
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

#include "engine_next/include/EngineNext/Assets/Types.h"

#include <array>
#include <cstdint>

namespace EngineNext::Rendering
{

struct CameraSettings;

struct CameraMatrices
{
	std::array<double, 16> arrView{};
	std::array<double, 16> arrProjection{};
	std::array<double, 16> arrViewProjection{};
	std::array<double, 16> arrInverseViewProjection{};
};

// Synchronous CPU math, callable on any thread with exclusive output access.
// Column-major matrices multiply column vectors. The camera looks along local
// -Z with right-handed Y-up world coordinates. D3D reverse depth maps the finite
// near plane to one and far plane to zero. Positive jitter pixels move raster
// positions right/down in the given viewport; {0, 0} gives unjittered matrices.
// Camera ranges follow CameraSettings, with near/far distinct in binary32.
// Zero viewport size, nonfinite inputs,
// degenerate view axes, or matrices outside finite binary32 range fail and leave
// the previous output unchanged. GPU camera-origin conversion is caller-owned.
[[nodiscard]] bool BuildCameraMatrices(const CameraSettings &stSettings, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight,
									   const std::array<double, 2> &arrJitterPixels, CameraMatrices &out_stMatrices, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
