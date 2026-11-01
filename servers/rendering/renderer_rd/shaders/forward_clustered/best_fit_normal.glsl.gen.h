/**************************************************************************/
/*  best_fit_normal.glsl.gen.h                                            */
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

class BestFitNormalShaderRD : public ShaderRD {
public:
	BestFitNormalShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 125, 82, 77, 143, 155, 48, 16, 237, 53, 254, 21, 35, 237, 197, 36, 44, 155, 176, 65, 173, 148,
			221, 91, 210, 42, 151, 173, 180, 145, 122, 69, 4, 76, 100, 9, 236, 212, 24, 10, 169, 242, 223, 59, 99, 39,
			33, 253, 80, 17, 50, 204, 155, 153, 247, 102, 198, 195, 30, 58, 97, 26, 169, 21, 44, 147, 57, 99, 15, 223,
			54, 239, 187, 237, 215, 183, 116, 189, 249, 188, 125, 219, 236, 24, 171, 178, 65, 183, 150, 87, 58, 207,
			170, 180, 145, 39, 145, 246, 240, 10, 159, 66, 184, 67, 134, 191, 144, 19, 34, 139, 0, 164, 90, 221, 24,
			12, 70, 52, 194, 162, 99, 30, 194, 94, 170, 66, 170, 3, 25, 1, 180, 74, 150, 218, 212, 96, 68, 99, 141,
			204, 45, 252, 48, 210, 10, 173, 170, 1, 100, 157, 29, 68, 188, 134, 188, 53, 70, 40, 155, 58, 27, 57, 221,
			211, 137, 252, 25, 190, 183, 153, 178, 40, 201, 157, 149, 7, 240, 147, 77, 140, 176, 173, 81, 96, 116, 171,
			10, 158, 87, 89, 125, 228, 57, 76, 97, 30, 37, 48, 163, 51, 196, 3, 139, 88, 68, 40, 62, 133, 56, 73, 252,
			15, 71, 0, 158, 70, 59, 70, 243, 145, 162, 86, 236, 204, 88, 89, 233, 204, 66, 137, 133, 167, 181, 84, 178,
			110, 235, 84, 24, 163, 141, 23, 86, 216, 64, 86, 57, 117, 31, 136, 49, 222, 79, 147, 152, 211, 67, 60, 23,
			167, 77, 247, 216, 43, 117, 239, 65, 140, 226, 222, 163, 26, 43, 142, 148, 18, 37, 171, 139, 241, 2, 139,
			248, 35, 153, 179, 153, 3, 156, 200, 149, 8, 67, 125, 212, 211, 37, 10, 93, 174, 160, 142, 88, 124, 85,
			216, 138, 189, 225, 215, 121, 21, 228, 31, 135, 119, 12, 198, 204, 66, 150, 37, 58, 249, 93, 232, 35, 242,
			5, 168, 225, 120, 188, 244, 181, 185, 58, 235, 121, 182, 111, 184, 75, 139, 250, 32, 252, 3, 25, 16, 25,
			173, 83, 16, 56, 37, 89, 2, 247, 12, 47, 227, 168, 124, 103, 147, 251, 209, 185, 47, 37, 76, 110, 51, 115,
			53, 156, 25, 189, 151, 139, 246, 46, 119, 75, 157, 150, 5, 22, 32, 21, 119, 100, 216, 80, 12, 109, 135,
			89, 244, 199, 15, 85, 250, 165, 210, 251, 172, 218, 170, 14, 151, 213, 226, 222, 111, 215, 81, 63, 208,
			109, 187, 0, 191, 1, 139, 121, 188, 164, 21, 152, 121, 144, 246, 230, 6, 162, 120, 219, 69, 3, 76, 95, 145,
			55, 234, 113, 23, 253, 212, 10, 105, 188, 202, 51, 39, 60, 36, 239, 224, 119, 12, 83, 220, 222, 238, 172,
			54, 130, 255, 182, 202, 33, 200, 255, 23, 22, 18, 229, 146, 255, 99, 237, 80, 48, 112, 252, 227, 65, 163,
			61, 179, 15, 191, 0, 200, 194, 35, 166
		};
		const CharString _code = _decompress_code(_code_compressed, 500, 980);

		setup(nullptr, nullptr, _code.get_data() + 0, "BestFitNormalShaderRD");
	}
};
