/**************************************************************************/
/*  shadow_frustum.glsl.gen.h                                             */
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

#include "servers/rendering/renderer_rd/shader_rd.h"

class ShadowFrustumShaderRD : public ShaderRD {
public:
	ShadowFrustumShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 189, 144, 61, 111, 131, 48, 16, 134, 179, 230, 126, 197, 73, 89, 0, 81, 112, 21, 58, 161, 108,
			165, 18, 75, 90, 53, 82, 87, 228, 16, 160, 150, 140, 29, 25, 67, 147, 86, 249, 239, 61, 83, 146, 126, 168,
			82, 183, 46, 30, 238, 158, 247, 241, 233, 133, 197, 80, 153, 78, 104, 133, 201, 13, 3, 88, 60, 101, 143,
			155, 252, 126, 93, 220, 102, 119, 249, 58, 219, 0, 196, 1, 150, 146, 171, 230, 170, 214, 166, 229, 22, 137,
			12, 98, 0, 201, 143, 186, 183, 222, 190, 239, 158, 139, 82, 171, 206, 114, 101, 67, 236, 236, 46, 89, 50,
			31, 123, 37, 28, 142, 185, 170, 53, 190, 193, 156, 130, 9, 182, 195, 62, 133, 249, 80, 149, 9, 150, 90,
			106, 147, 194, 9, 4, 1, 233, 197, 38, 117, 201, 173, 187, 101, 133, 36, 17, 10, 9, 94, 210, 99, 108, 117,
			40, 184, 181, 70, 108, 9, 30, 180, 216, 97, 203, 133, 242, 124, 231, 30, 133, 31, 12, 229, 156, 48, 162,
			159, 48, 112, 225, 196, 251, 22, 14, 241, 58, 98, 254, 120, 132, 155, 70, 135, 227, 43, 198, 171, 41, 28,
			189, 208, 162, 145, 197, 131, 238, 196, 116, 196, 23, 3, 177, 33, 178, 136, 157, 21, 167, 95, 154, 169,
			107, 87, 205, 12, 254, 170, 244, 31, 186, 163, 201, 120, 61, 214, 134, 55, 197, 20, 249, 217, 220, 231,
			238, 92, 220, 197, 61, 123, 7, 52, 123, 169, 96
		};
		const CharString _code = _decompress_code(_code_compressed, 264, 536);

		setup(_code.get_data() + 0, _code.get_data() + 339, nullptr, "ShadowFrustumShaderRD");
	}
};
