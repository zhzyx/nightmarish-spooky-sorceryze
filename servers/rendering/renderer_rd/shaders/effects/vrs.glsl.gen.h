/**************************************************************************/
/*  vrs.glsl.gen.h                                                        */
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

class VrsShaderRD : public ShaderRD {
public:
	VrsShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 205, 84, 203, 110, 218, 64, 20, 205, 150, 249, 138, 43, 177, 177, 9, 16, 131, 97, 83, 232, 162,
			82, 220, 8, 137, 166, 40, 16, 90, 41, 66, 214, 0, 99, 119, 36, 51, 70, 227, 49, 133, 86, 252, 123, 239,
			248, 29, 30, 169, 148, 110, 186, 177, 53, 119, 206, 57, 247, 61, 164, 190, 99, 50, 226, 161, 128, 94, 223,
			34, 164, 62, 119, 158, 166, 163, 175, 143, 238, 189, 243, 121, 244, 232, 76, 209, 194, 189, 53, 243, 224,
			121, 234, 184, 95, 158, 199, 179, 209, 124, 228, 124, 35, 117, 182, 87, 76, 36, 180, 135, 177, 235, 124,
			159, 185, 155, 56, 80, 124, 199, 217, 79, 248, 0, 76, 208, 101, 192, 72, 29, 121, 92, 48, 152, 163, 117,
			36, 214, 108, 15, 126, 224, 22, 7, 212, 16, 107, 238, 193, 21, 15, 1, 61, 132, 177, 50, 130, 112, 69, 149,
			118, 243, 17, 44, 19, 208, 2, 59, 182, 178, 33, 222, 185, 92, 40, 38, 183, 3, 148, 9, 34, 246, 38, 188,
			251, 26, 174, 189, 146, 156, 176, 141, 163, 31, 238, 42, 20, 145, 162, 66, 53, 33, 82, 235, 158, 141, 204,
			88, 112, 47, 148, 27, 152, 80, 73, 55, 17, 252, 38, 53, 47, 8, 169, 130, 13, 221, 187, 138, 237, 89, 224,
			122, 116, 165, 66, 57, 200, 47, 36, 139, 58, 213, 67, 183, 122, 176, 7, 228, 72, 182, 137, 212, 128, 144,
			93, 200, 215, 40, 196, 133, 97, 106, 225, 36, 192, 37, 141, 152, 75, 165, 124, 177, 23, 24, 186, 54, 189,
			44, 12, 253, 51, 90, 157, 182, 213, 4, 253, 53, 155, 80, 177, 216, 165, 193, 46, 16, 38, 122, 197, 26, 79,
			194, 136, 103, 85, 64, 64, 207, 40, 212, 117, 253, 153, 196, 4, 146, 14, 44, 154, 96, 105, 170, 102, 34,
			177, 40, 82, 123, 127, 64, 230, 42, 160, 155, 173, 81, 81, 67, 115, 230, 48, 97, 89, 101, 0, 157, 92, 197,
			132, 6, 116, 219, 214, 0, 46, 247, 180, 226, 226, 23, 122, 40, 70, 161, 232, 202, 145, 144, 27, 242, 174,
			129, 188, 216, 127, 46, 206, 166, 37, 195, 69, 76, 105, 72, 19, 150, 28, 29, 11, 63, 197, 231, 93, 143,
			48, 243, 128, 201, 238, 253, 39, 41, 233, 1, 162, 48, 150, 43, 134, 83, 18, 232, 134, 39, 243, 6, 119, 141,
			215, 1, 64, 227, 238, 173, 24, 186, 239, 143, 225, 204, 125, 178, 53, 151, 252, 231, 149, 153, 78, 198,
			163, 153, 251, 244, 240, 151, 165, 240, 36, 245, 95, 37, 117, 29, 31, 99, 232, 39, 248, 255, 107, 139, 46,
			143, 91, 214, 124, 204, 227, 236, 189, 168, 101, 77, 57, 189, 75, 211, 170, 37, 247, 61, 72, 178, 69, 8,
			6, 171, 98, 201, 198, 225, 218, 168, 118, 163, 137, 220, 116, 17, 6, 231, 197, 71, 141, 178, 98, 168, 129,
			73, 27, 249, 182, 120, 38, 180, 82, 241, 182, 244, 203, 37, 194, 182, 66, 183, 223, 215, 247, 102, 17, 40,
			169, 101, 192, 98, 39, 177, 34, 161, 52, 114, 107, 3, 210, 154, 180, 79, 171, 10, 183, 24, 90, 199, 204,
			150, 252, 10, 72, 47, 126, 170, 228, 95, 212, 247, 255, 93, 95, 167, 128, 19, 91, 4, 60, 132, 66, 187, 149,
			189, 26, 56, 25, 213, 44, 171, 183, 24, 223, 177, 202, 247, 75, 190, 188, 192, 247, 11, 190, 172, 240, 207,
			154, 129, 13, 47, 68, 210, 52, 96, 56, 132, 100, 220, 74, 216, 109, 21, 231, 103, 184, 202, 91, 117, 243,
			7, 56, 18, 65, 212
		};
		const CharString _code = _decompress_code(_code_compressed, 631, 1852);

		setup(_code.get_data() + 0, _code.get_data() + 657, nullptr, "VrsShaderRD");
	}
};
