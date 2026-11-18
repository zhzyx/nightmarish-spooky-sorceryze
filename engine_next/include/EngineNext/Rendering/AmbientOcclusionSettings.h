/**************************************************************************/
/*  AmbientOcclusionSettings.h                                            */
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

constexpr std::uint32_t MAX_OCCLUSION_SAMPLES = 64;

struct AmbientOcclusionSettings
{
	bool bEnabled = false;
	double dRadius = 1.0;
	double dNormalBias = 0.02;
	double dIntensity = 1.0;
	std::uint32_t nSampleCount = 32;
};

using OcclusionKernel = std::array<std::array<float, 4>, MAX_OCCLUSION_SAMPLES>;

// Distances use world units. Radius is (0,100], normal bias is [0,radius),
// intensity is [0,1], and the sample count is a power of two in [8,64].
// Validation also applies when the effect is disabled.
[[nodiscard]] bool ValidateAmbientOcclusionSettings(const AmbientOcclusionSettings &stSettings, Assets::Diagnostics &out_arrDiagnostics);

// xyz is a cosine-weighted unit hemisphere direction, w is its radius fraction.
// Unused entries are zero. Invalid settings preserve the previous output.
[[nodiscard]] bool BuildAmbientOcclusionKernel(const AmbientOcclusionSettings &stSettings, OcclusionKernel &out_arrKernel,
											   Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
