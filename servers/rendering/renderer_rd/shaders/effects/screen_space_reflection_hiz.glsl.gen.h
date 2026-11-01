/**************************************************************************/
/*  screen_space_reflection_hiz.glsl.gen.h                                */
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

class ScreenSpaceReflectionHizShaderRD : public ShaderRD {
public:
	ScreenSpaceReflectionHizShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 173, 148, 65, 143, 155, 48, 16, 133, 123, 133, 95, 49, 82, 164, 21, 110, 81, 20, 216, 84, 170,
			20, 245, 6, 187, 225, 208, 77, 213, 68, 237, 17, 121, 97, 72, 44, 25, 155, 218, 38, 37, 91, 237, 127, 223,
			9, 105, 54, 137, 146, 67, 165, 228, 0, 130, 49, 239, 155, 55, 79, 198, 254, 96, 141, 198, 10, 173, 96, 252,
			121, 228, 251, 131, 159, 233, 143, 121, 54, 123, 202, 147, 244, 33, 123, 74, 231, 190, 47, 249, 70, 183,
			46, 144, 186, 224, 50, 183, 226, 5, 243, 14, 190, 194, 151, 16, 142, 42, 155, 179, 202, 11, 85, 34, 6, 66,
			77, 222, 9, 22, 29, 21, 71, 33, 60, 11, 85, 10, 181, 220, 190, 48, 104, 149, 168, 180, 169, 193, 242, 186,
			145, 104, 226, 4, 172, 110, 77, 129, 147, 189, 204, 220, 199, 85, 8, 23, 196, 209, 65, 108, 208, 58, 35,
			10, 7, 127, 140, 112, 168, 149, 220, 128, 168, 249, 18, 137, 86, 210, 210, 193, 67, 211, 218, 85, 94, 104,
			101, 29, 87, 142, 168, 174, 28, 223, 31, 153, 248, 206, 13, 175, 45, 252, 245, 61, 177, 198, 34, 6, 91,
			24, 68, 213, 79, 52, 217, 215, 26, 94, 78, 252, 87, 191, 233, 63, 37, 242, 90, 139, 18, 106, 46, 84, 192,
			14, 194, 70, 116, 40, 243, 70, 91, 242, 217, 87, 130, 165, 204, 31, 165, 126, 230, 50, 83, 107, 138, 201,
			81, 226, 89, 50, 236, 54, 140, 16, 158, 168, 32, 224, 106, 19, 44, 13, 114, 135, 102, 177, 226, 42, 253,
			221, 114, 25, 188, 115, 66, 216, 53, 28, 30, 89, 98, 172, 239, 232, 25, 116, 173, 161, 160, 189, 87, 66,
			85, 82, 115, 71, 83, 55, 110, 69, 189, 29, 146, 254, 1, 93, 177, 10, 118, 177, 134, 71, 214, 62, 66, 12,
			159, 254, 217, 163, 100, 71, 108, 123, 13, 59, 2, 237, 229, 53, 239, 130, 254, 57, 252, 127, 82, 116, 32,
			177, 43, 81, 100, 42, 186, 17, 42, 58, 65, 249, 3, 81, 149, 88, 193, 183, 89, 146, 230, 179, 36, 201, 127,
			101, 201, 98, 122, 93, 135, 248, 118, 115, 199, 39, 102, 7, 72, 59, 190, 58, 247, 60, 77, 179, 199, 233,
			226, 234, 132, 227, 219, 37, 28, 95, 52, 77, 155, 177, 18, 10, 203, 224, 52, 109, 6, 119, 119, 231, 75,
			187, 161, 216, 213, 249, 93, 176, 226, 245, 71, 194, 220, 105, 131, 193, 246, 84, 56, 82, 135, 64, 186,
			241, 190, 207, 104, 56, 58, 220, 24, 219, 254, 237, 31, 222, 0, 201, 14, 155, 201
		};
		const CharString _code = _decompress_code(_code_compressed, 460, 1319);

		setup(nullptr, nullptr, _code.get_data() + 0, "ScreenSpaceReflectionHizShaderRD");
	}
};
