/**************************************************************************/
/*  motion_vectors_store.glsl.gen.h                                       */
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

class MotionVectorsStoreShaderRD : public ShaderRD {
public:
	MotionVectorsStoreShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 125, 83, 93, 111, 218, 64, 16, 236, 43, 254, 21, 43, 229, 197, 215, 58, 46, 80, 82, 85, 66, 121,
			168, 130, 137, 44, 53, 16, 1, 69, 149, 170, 234, 116, 216, 103, 251, 82, 251, 206, 61, 159, 29, 72, 213,
			255, 222, 61, 243, 17, 4, 180, 47, 6, 207, 238, 206, 142, 119, 103, 157, 171, 134, 235, 74, 40, 9, 131,
			155, 174, 227, 92, 45, 131, 217, 60, 156, 78, 232, 40, 24, 135, 147, 96, 238, 56, 13, 143, 250, 16, 115,
			45, 26, 78, 11, 101, 48, 147, 34, 100, 148, 118, 219, 72, 221, 120, 144, 228, 138, 25, 204, 41, 77, 230,
			65, 193, 204, 0, 52, 47, 181, 122, 194, 52, 155, 142, 136, 22, 107, 2, 191, 157, 14, 150, 12, 160, 212,
			188, 17, 170, 174, 104, 169, 42, 42, 227, 8, 110, 47, 229, 195, 91, 176, 217, 110, 221, 224, 191, 190, 223,
			77, 224, 26, 122, 248, 227, 109, 27, 157, 130, 246, 73, 134, 78, 71, 115, 83, 107, 9, 93, 255, 38, 129,
			119, 224, 158, 246, 242, 215, 27, 120, 127, 166, 192, 127, 38, 200, 215, 214, 92, 227, 23, 13, 157, 63,
			56, 137, 152, 39, 66, 114, 24, 143, 191, 209, 241, 124, 214, 167, 211, 199, 133, 29, 204, 253, 116, 52,
			93, 224, 120, 102, 225, 50, 160, 225, 100, 249, 249, 75, 56, 162, 15, 211, 54, 182, 12, 238, 22, 211, 217,
			156, 142, 191, 78, 238, 44, 224, 10, 15, 158, 60, 248, 73, 46, 15, 112, 31, 117, 156, 156, 109, 84, 109,
			220, 92, 69, 44, 167, 149, 120, 225, 116, 141, 83, 249, 228, 193, 17, 178, 57, 67, 94, 16, 233, 17, 16,
			114, 184, 39, 168, 184, 65, 172, 235, 193, 74, 200, 88, 200, 212, 190, 16, 168, 165, 72, 148, 46, 160, 98,
			69, 153, 115, 221, 31, 109, 71, 72, 87, 117, 146, 112, 125, 40, 214, 105, 239, 35, 78, 242, 2, 71, 239,
			149, 67, 243, 10, 183, 19, 25, 120, 214, 194, 112, 37, 243, 13, 136, 130, 165, 28, 73, 27, 142, 218, 132,
			217, 28, 120, 247, 196, 101, 93, 101, 52, 82, 178, 50, 76, 26, 108, 96, 226, 193, 135, 35, 89, 143, 76,
			179, 162, 178, 246, 200, 68, 154, 149, 255, 116, 208, 176, 245, 79, 223, 74, 80, 121, 109, 3, 136, 212,
			66, 26, 40, 89, 252, 189, 255, 195, 174, 173, 108, 185, 176, 117, 163, 68, 140, 76, 66, 186, 173, 241, 156,
			142, 72, 192, 101, 114, 227, 166, 154, 51, 195, 245, 34, 99, 50, 248, 85, 179, 188, 181, 177, 155, 230,
			244, 62, 87, 43, 150, 135, 178, 193, 1, 91, 242, 112, 132, 102, 33, 30, 108, 41, 253, 215, 174, 132, 180,
			148, 59, 171, 161, 6, 116, 75, 71, 180, 210, 208, 79, 56, 46, 241, 127, 74, 84, 215, 57, 58, 25, 44, 48,
			124, 205, 243, 49, 55, 81, 230, 30, 111, 198, 179, 124, 30, 110, 208, 63, 124, 59, 94, 195, 45, 108, 37,
			99, 140, 160, 197, 173, 107, 137, 245, 244, 169, 204, 125, 201, 126, 45, 88, 120, 209, 133, 246, 130, 119,
			183, 123, 224, 56, 191, 94, 100, 107, 247, 60, 199, 18, 238, 158, 172, 122, 39, 180, 189, 215, 125, 8, 117,
			183, 135, 105, 159, 132, 216, 221, 188, 249, 11, 3, 162, 118, 235
		};
		const CharString _code = _decompress_code(_code_compressed, 586, 1132);

		setup(nullptr, nullptr, _code.get_data() + 0, "MotionVectorsStoreShaderRD");
	}
};
