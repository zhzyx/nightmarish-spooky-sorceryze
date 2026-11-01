/**************************************************************************/
/*  scene_forward_streaming_inc.glsl.gen.h                                */
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

/* THIS FILE IS GENERATED. EDITS WILL BE LOST. */

#pragma once

static const char scene_forward_streaming_inc_shader_glsl[] = {
R"<!>(// Helper functions for texture streaming feedback.
// Used by the Forward+ and Mobile renderers.

// Reference texture size used for LOD normalization: 4096x4096.
#define STREAMING_LOD_REFERENCE_LOG2 12.0

// Returns the squared pixel footprint in UV space.
float streaming_footprint_sq(vec2 uv_ddx, vec2 uv_ddy) {
	float uv_ddx_sq = dot(uv_ddx, uv_ddx);
	float uv_ddy_sq = dot(uv_ddy, uv_ddy);

	// Limit anisotropic filtering to 16x.
	const float MAX_ANISOTROPY = 16.0;

	return max(
			min(uv_ddx_sq, uv_ddy_sq),
			max(uv_ddx_sq, uv_ddy_sq) / (MAX_ANISOTROPY * MAX_ANISOTROPY));
}

// Undoes the reference offset on a shader-supplied STREAMING_LOD, so both feedback paths
// hand the same squared UV footprint to the encoder.
float streaming_footprint_sq_from_lod(float lod) {
	return exp2(2.0 * (clamp(lod, -32.0, 32.0) - STREAMING_LOD_REFERENCE_LOG2));
}
)<!>"
};
