/**************************************************************************/
/*  resolve_raster.glsl.gen.h                                             */
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

class ResolveRasterShaderRD : public ShaderRD {
public:
	ResolveRasterShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 157, 82, 61, 111, 194, 48, 16, 101, 197, 191, 226, 164, 46, 14, 164, 33, 5, 58, 165, 76, 5, 36,
			134, 126, 168, 72, 44, 21, 138, 76, 98, 192, 82, 176, 35, 219, 137, 168, 170, 254, 247, 158, 19, 8, 65,
			101, 106, 134, 216, 58, 223, 123, 247, 238, 221, 145, 187, 146, 107, 35, 148, 132, 241, 99, 72, 200, 221,
			106, 246, 177, 92, 188, 189, 198, 211, 217, 124, 241, 58, 91, 18, 146, 177, 47, 85, 88, 154, 169, 132, 89,
			151, 54, 129, 208, 3, 140, 64, 201, 147, 33, 20, 101, 44, 164, 229, 58, 143, 200, 160, 7, 73, 198, 228,
			238, 126, 171, 244, 129, 89, 192, 220, 222, 128, 144, 82, 137, 20, 14, 76, 72, 234, 193, 55, 233, 86, 168,
			13, 51, 60, 102, 90, 127, 142, 214, 200, 231, 66, 159, 107, 234, 14, 122, 255, 16, 132, 62, 184, 191, 231,
			67, 43, 50, 186, 4, 70, 77, 134, 23, 145, 238, 46, 139, 223, 149, 17, 39, 105, 152, 48, 166, 13, 59, 190,
			173, 184, 182, 252, 184, 144, 41, 63, 174, 125, 8, 29, 212, 33, 17, 216, 40, 71, 24, 234, 62, 228, 180,
			69, 21, 28, 191, 78, 213, 42, 72, 120, 169, 254, 112, 166, 240, 160, 7, 195, 32, 140, 128, 252, 144, 191,
			189, 111, 183, 174, 249, 14, 249, 151, 187, 66, 254, 49, 247, 156, 104, 184, 117, 57, 62, 108, 132, 76,
			133, 220, 213, 128, 66, 10, 87, 24, 12, 182, 145, 113, 61, 156, 190, 44, 193, 168, 66, 39, 60, 78, 121,
			110, 247, 23, 124, 94, 152, 125, 156, 40, 105, 44, 147, 214, 7, 99, 211, 241, 168, 69, 240, 206, 52, 59,
			24, 156, 19, 224, 39, 42, 17, 57, 75, 209, 45, 212, 113, 98, 71, 116, 33, 109, 84, 103, 96, 20, 223, 135,
			17, 122, 144, 87, 208, 166, 18, 220, 216, 152, 109, 166, 156, 55, 133, 109, 84, 93, 47, 71, 171, 168, 50,
			8, 171, 238, 110, 44, 115, 205, 118, 207, 74, 233, 20, 231, 130, 179, 35, 221, 154, 169, 98, 137, 89, 89,
			185, 128, 163, 192, 184, 210, 64, 157, 42, 225, 66, 17, 30, 79, 80, 11, 11, 174, 212, 131, 232, 247, 171,
			117, 236, 94, 56, 250, 19, 192, 85, 225, 217, 156, 219, 100, 79, 219, 246, 249, 78, 143, 15, 194, 11, 52,
			214, 248, 33, 45, 208, 96, 82, 119, 69, 111, 84, 113, 91, 214, 52, 139, 122, 26, 148, 179, 171, 243, 11,
			189, 73, 18, 183
		};
		const CharString _code = _decompress_code(_code_compressed, 442, 889);

		setup(_code.get_data() + 0, _code.get_data() + 350, nullptr, "ResolveRasterShaderRD");
	}
};
