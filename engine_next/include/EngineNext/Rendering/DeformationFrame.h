/**************************************************************************/
/*  DeformationFrame.h                                                    */
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
#include "engine_next/include/EngineNext/Serialization/Json.h"

#include <array>
#include <cstdint>
#include <vector>

namespace EngineNext::Rendering
{
struct DeformedDraw
{
	std::uint32_t nDraw = 0;
	AnimationMatrix arrWorld{};
	std::vector<MeshVertex> arrVertices;
	std::array<double, 3> arrMinimum{};
	std::array<double, 3> arrMaximum{};
};

struct DeformationFrame
{
	double dSeconds = 0;
	std::uint64_t nVertexCount = 0;
	std::vector<DeformedDraw> arrDraws;
};

[[nodiscard]] bool ParseAnimationPlayback(const Serialization::JsonValue &stValue, AnimationPlayback &out_stPlayback,
										  Assets::Diagnostics &out_arrDiagnostics);

// Owns per-render-instance vertices. The glTF node transform is applied once,
// after skinning in node-local space, and then composed with the M3 entity.
// Outputs remain unchanged on invalid input, overflow or budget exhaustion.
[[nodiscard]] bool BuildDeformationFrame(const RenderScene &stScene, const AnimationPlayback &stPlayback, double dSeconds,
										 DeformationFrame &out_stFrame, Assets::Diagnostics &out_arrDiagnostics);
} // namespace EngineNext::Rendering
