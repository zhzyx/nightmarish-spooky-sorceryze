/**************************************************************************/
/*  LocalShadowData.h                                                     */
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

struct PointLightSettings;
struct SpotLightSettings;

struct LocalShadowView
{
	std::array<double, 16> arrViewProjection{};
	std::uint32_t nLightId = 0;
	std::uint32_t nFace = 0;
};

struct LocalShadowData
{
	std::vector<LocalShadowView> arrViews;
};

// Synchronous right-handed, column-major perspective shadow views in meters.
// Point faces use +X, -X, +Y, -Y, +Z, -Z order. Sampling selects the major-axis
// face and projects through that face matrix into a Texture2DArray slice.
// Spot direction follows light rays toward the scene; its face value is zero.
// Input order is preserved, with point views followed by spot views. Only lights
// with bCastsShadow produce views. All inputs are validated, including unshadowed
// lights, with at most four lights per kind and unique nonzero IDs across kinds.
// Near is min(0.05, range * 0.01), far is range, and reverse depth maps near to one.
// Failed validation leaves prior output unchanged. GPU-bound coordinates and
// matrix elements must fit finite binary32. No shared mutable state is used.
[[nodiscard]] bool BuildLocalShadows(const std::vector<PointLightSettings> &arrPointLights, const std::vector<SpotLightSettings> &arrSpotLights,
									 LocalShadowData &out_stData, Assets::Diagnostics &out_arrDiagnostics);

} // namespace EngineNext::Rendering
