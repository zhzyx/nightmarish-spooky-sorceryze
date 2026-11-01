/**************************************************************************/
/*  screen_space_reflection_downsample.glsl.gen.h                         */
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

class ScreenSpaceReflectionDownsampleShaderRD : public ShaderRD {
public:
	ScreenSpaceReflectionDownsampleShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 165, 84, 209, 110, 155, 48, 20, 221, 107, 248, 138, 43, 69, 170, 96, 67, 17, 33, 153, 84, 41,
			219, 27, 180, 225, 97, 237, 180, 68, 219, 35, 114, 224, 66, 44, 17, 155, 217, 38, 77, 58, 245, 223, 103,
			32, 9, 36, 164, 77, 212, 190, 32, 249, 248, 158, 115, 143, 207, 197, 54, 250, 107, 20, 146, 114, 6, 227,
			175, 142, 97, 244, 127, 251, 191, 102, 193, 227, 67, 232, 249, 119, 193, 131, 63, 51, 140, 140, 108, 121,
			161, 204, 140, 71, 36, 11, 37, 125, 198, 112, 3, 223, 225, 214, 134, 22, 178, 237, 32, 207, 26, 25, 90,
			64, 217, 228, 160, 32, 81, 105, 208, 177, 97, 65, 89, 76, 89, 90, 46, 44, 40, 24, 77, 184, 88, 129, 36,
			171, 60, 67, 225, 122, 32, 121, 33, 34, 12, 99, 204, 213, 114, 242, 6, 121, 248, 6, 153, 105, 84, 91, 17,
			188, 72, 151, 12, 165, 60, 232, 136, 145, 155, 216, 112, 70, 205, 109, 212, 4, 74, 37, 104, 164, 224, 73,
			80, 133, 156, 101, 91, 160, 43, 146, 162, 150, 143, 245, 214, 137, 51, 145, 46, 200, 237, 89, 201, 209,
			245, 146, 93, 191, 123, 249, 188, 144, 203, 48, 226, 76, 42, 194, 148, 110, 163, 226, 241, 168, 21, 219,
			79, 34, 200, 74, 194, 63, 163, 71, 215, 24, 185, 32, 35, 129, 200, 170, 25, 76, 246, 88, 78, 226, 137, 241,
			98, 228, 85, 169, 86, 94, 115, 26, 67, 138, 42, 172, 99, 51, 119, 204, 106, 17, 230, 92, 218, 122, 108,
			186, 53, 36, 25, 39, 10, 170, 211, 238, 161, 186, 244, 137, 50, 134, 34, 108, 24, 86, 105, 160, 46, 223,
			129, 21, 75, 103, 160, 112, 131, 217, 29, 170, 104, 105, 182, 231, 106, 31, 181, 115, 172, 193, 70, 251,
			234, 209, 4, 204, 154, 248, 237, 72, 167, 146, 239, 237, 37, 219, 59, 250, 140, 189, 142, 155, 166, 70,
			47, 116, 197, 139, 62, 124, 125, 232, 21, 161, 204, 180, 154, 180, 114, 170, 221, 237, 40, 21, 98, 166,
			89, 120, 159, 241, 5, 201, 2, 182, 214, 127, 179, 210, 23, 35, 240, 6, 155, 173, 181, 247, 71, 216, 214,
			76, 5, 18, 133, 98, 190, 36, 204, 255, 91, 144, 204, 60, 232, 216, 80, 167, 60, 104, 205, 193, 178, 106,
			255, 2, 85, 33, 88, 229, 231, 48, 173, 182, 231, 198, 204, 103, 112, 225, 203, 206, 144, 83, 198, 51, 217,
			167, 251, 174, 88, 91, 163, 62, 223, 99, 88, 214, 218, 208, 145, 40, 251, 94, 36, 107, 131, 195, 119, 147,
			135, 175, 147, 141, 62, 77, 98, 76, 224, 199, 163, 231, 135, 143, 158, 23, 254, 9, 188, 249, 244, 10, 77,
			247, 35, 167, 113, 95, 55, 212, 71, 125, 177, 147, 174, 175, 169, 31, 220, 79, 231, 215, 37, 229, 126, 36,
			41, 247, 178, 49, 189, 159, 80, 134, 177, 121, 156, 154, 5, 55, 55, 221, 173, 218, 184, 117, 93, 42, 151,
			154, 247, 170, 247, 108, 166, 184, 64, 179, 121, 37, 109, 104, 93, 13, 45, 53, 54, 119, 176, 51, 112, 154,
			143, 85, 38, 112, 202, 63, 125, 18, 143, 164, 186, 255, 127, 183, 252, 248, 42, 88, 229, 19, 248, 233, 63,
			211, 11, 73, 132
		};
		const CharString _code = _decompress_code(_code_compressed, 576, 1774);

		setup(nullptr, nullptr, _code.get_data() + 0, "ScreenSpaceReflectionDownsampleShaderRD");
	}
};
