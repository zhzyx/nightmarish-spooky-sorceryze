/**************************************************************************/
/*  ShadowData.h                                                          */
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
#include <vector>

namespace EngineNext::Rendering
{

struct CameraSettings;
struct DirectionalLightSettings;
struct ShadowSettings;

struct WorldBounds
{
	std::array<double, 3> arrMinimum{};
	std::array<double, 3> arrMaximum{};
};

// Uploaded through FrameConstants::arrLighting for the shader transition.
inline constexpr double SHADOW_CASCADE_BLEND_FRACTION = 0.1;

struct ShadowCascade
{
	std::array<double, 16> arrViewProjection{};
	double dSplitNear = 0;
	double dSplitFar = 0;
	double dWorldUnitsPerTexel = 0;
};

struct ShadowData
{
	std::array<ShadowCascade, 4> arrCascades;
};

// Synchronous CPU math with column-major matrices and world-space meter bounds.
// Light direction follows the rays toward the scene. Each cascade occupies its
// own full-resolution slice and maps the nearest light-space depth to one.
// All caster bounds extend each cascade's depth range, including offscreen ones.
// The camera frustum is unjittered. Radius rounding and world-space texel snapping
// keep its square projection stable under camera translation and orientation.
// Empty caster input is valid. At most 65536 finite binary32-range ordered bounds
// are accepted. Invalid inputs or unrepresentable matrices preserve prior output.
[[nodiscard]] bool BuildDirectionalShadows(const CameraSettings &stCamera, std::uint32_t nViewportWidth, std::uint32_t nViewportHeight,
										   const DirectionalLightSettings &stLight, const ShadowSettings &stSettings, const std::vector<WorldBounds> &arrCasters,
										   ShadowData &out_stData, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
