/**************************************************************************/
/*  specular_merge.glsl.gen.h                                             */
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

class SpecularMergeShaderRD : public ShaderRD {
public:
	SpecularMergeShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 149, 83, 75, 111, 155, 64, 16, 206, 213, 251, 43, 70, 242, 5, 90, 106, 225, 71, 47, 69, 61, 84,
			50, 141, 144, 226, 164, 50, 137, 83, 41, 178, 208, 218, 94, 172, 149, 96, 177, 118, 129, 226, 84, 253, 239,
			29, 176, 13, 172, 227, 58, 244, 2, 98, 248, 94, 59, 179, 67, 250, 57, 147, 138, 39, 2, 38, 159, 109, 66,
			250, 11, 119, 238, 123, 15, 247, 193, 212, 253, 238, 221, 187, 62, 86, 120, 8, 27, 22, 114, 193, 54, 198,
			147, 239, 6, 179, 167, 187, 71, 111, 225, 185, 207, 38, 233, 179, 34, 101, 162, 34, 223, 222, 5, 238, 207,
			199, 32, 206, 162, 148, 231, 156, 253, 130, 47, 192, 4, 93, 69, 140, 244, 15, 100, 88, 96, 213, 19, 27,
			86, 192, 54, 10, 234, 15, 212, 16, 27, 116, 168, 124, 16, 9, 154, 5, 137, 232, 62, 201, 82, 35, 74, 214,
			52, 45, 109, 190, 130, 109, 2, 86, 32, 103, 235, 49, 100, 121, 192, 69, 202, 228, 206, 65, 153, 72, 49,
			184, 138, 31, 233, 248, 163, 109, 158, 240, 13, 196, 148, 11, 195, 132, 223, 164, 87, 225, 86, 84, 177,
			128, 74, 249, 50, 94, 162, 66, 89, 122, 89, 26, 229, 203, 248, 52, 28, 216, 22, 148, 79, 211, 130, 86, 101,
			220, 20, 198, 53, 194, 116, 72, 15, 207, 250, 35, 81, 252, 24, 6, 1, 19, 163, 86, 47, 251, 192, 100, 202,
			138, 170, 19, 75, 11, 236, 146, 90, 50, 145, 88, 103, 29, 20, 123, 100, 174, 35, 26, 239, 140, 150, 26,
			150, 143, 134, 21, 203, 110, 2, 12, 79, 42, 38, 124, 128, 209, 192, 118, 224, 114, 111, 91, 22, 175, 232,
			80, 143, 228, 212, 28, 242, 135, 144, 27, 210, 225, 122, 116, 28, 27, 23, 255, 53, 181, 3, 252, 242, 208,
			174, 153, 42, 150, 150, 2, 22, 172, 56, 162, 197, 246, 160, 150, 9, 30, 38, 50, 6, 133, 109, 140, 152, 28,
			77, 191, 73, 73, 247, 160, 118, 108, 157, 69, 84, 158, 71, 233, 40, 162, 241, 245, 108, 179, 135, 169, 27,
			248, 254, 188, 75, 216, 97, 199, 176, 234, 31, 57, 135, 239, 231, 84, 90, 196, 195, 124, 181, 168, 51, 119,
			126, 235, 118, 9, 59, 234, 22, 22, 13, 194, 76, 177, 203, 129, 223, 213, 104, 211, 207, 66, 95, 91, 241,
			9, 132, 146, 110, 131, 117, 18, 37, 120, 222, 243, 221, 110, 254, 13, 228, 118, 133, 68, 92, 189, 52, 147,
			204, 56, 77, 209, 106, 46, 155, 89, 66, 28, 141, 67, 75, 43, 92, 167, 183, 19, 238, 85, 214, 216, 227, 3,
			178, 173, 172, 52, 81, 231, 66, 136, 152, 23, 134, 94, 180, 26, 169, 243, 79, 106, 58, 87, 166, 215, 18,
			135, 143, 77, 136, 99, 47, 245, 32, 71, 149, 30, 110, 249, 205, 95, 138, 88, 232, 15
		};
		const CharString _code = _decompress_code(_code_compressed, 508, 1540);

		setup(_code.get_data() + 0, _code.get_data() + 543, nullptr, "SpecularMergeShaderRD");
	}
};
