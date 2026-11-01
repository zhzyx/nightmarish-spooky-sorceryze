/**************************************************************************/
/*  luminance_reduce_raster.glsl.gen.h                                    */
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

class LuminanceReduceRasterShaderRD : public ShaderRD {
public:
	LuminanceReduceRasterShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 229, 85, 77, 111, 155, 64, 16, 205, 149, 253, 21, 35, 249, 178, 216, 4, 227, 56, 61, 81, 31, 162,
			38, 145, 34, 85, 105, 20, 87, 185, 68, 22, 194, 176, 216, 27, 17, 64, 187, 96, 225, 86, 254, 239, 157, 5,
			22, 150, 36, 106, 122, 175, 108, 97, 237, 44, 239, 205, 155, 79, 147, 201, 129, 9, 201, 243, 12, 46, 191,
			120, 132, 76, 158, 110, 30, 215, 119, 63, 238, 131, 235, 155, 219, 187, 251, 155, 53, 33, 105, 120, 204,
			171, 146, 22, 149, 220, 7, 81, 158, 201, 50, 204, 74, 7, 100, 25, 95, 46, 61, 27, 170, 140, 39, 185, 120,
			133, 7, 188, 254, 214, 221, 194, 111, 98, 241, 3, 139, 46, 64, 230, 149, 136, 88, 32, 249, 47, 230, 107,
			91, 204, 100, 217, 89, 136, 149, 164, 121, 88, 2, 171, 139, 92, 86, 130, 5, 97, 252, 82, 201, 210, 215,
			246, 87, 158, 5, 105, 133, 207, 48, 139, 216, 96, 13, 235, 145, 181, 226, 232, 178, 8, 227, 133, 79, 78,
			68, 178, 178, 228, 217, 78, 250, 189, 240, 52, 143, 194, 82, 197, 183, 2, 212, 139, 22, 104, 100, 84, 135,
			0, 113, 76, 20, 62, 153, 79, 33, 74, 195, 108, 119, 174, 34, 65, 7, 248, 238, 116, 78, 200, 33, 231, 49,
			58, 227, 25, 181, 85, 68, 13, 106, 27, 74, 84, 41, 196, 243, 114, 131, 124, 202, 244, 188, 161, 234, 135,
			158, 47, 92, 207, 1, 245, 180, 29, 48, 44, 203, 193, 176, 236, 223, 176, 81, 246, 46, 13, 30, 114, 201,
			59, 105, 248, 194, 37, 237, 217, 241, 238, 137, 137, 146, 213, 119, 89, 204, 234, 141, 3, 158, 130, 42,
			164, 138, 87, 43, 71, 24, 234, 126, 45, 168, 65, 229, 214, 199, 206, 91, 3, 241, 6, 239, 11, 77, 97, 195,
			20, 46, 92, 207, 7, 76, 215, 251, 216, 147, 68, 5, 127, 70, 254, 175, 182, 224, 217, 191, 118, 69, 7, 71,
			66, 133, 116, 96, 203, 179, 24, 153, 91, 26, 29, 182, 196, 170, 164, 76, 92, 92, 235, 80, 117, 40, 232,
			127, 194, 147, 152, 37, 128, 105, 188, 250, 30, 60, 92, 173, 215, 99, 202, 197, 167, 148, 133, 96, 7, 51,
			210, 9, 195, 215, 147, 191, 244, 251, 158, 239, 246, 5, 180, 89, 50, 112, 111, 27, 220, 168, 3, 138, 69,
			120, 99, 160, 67, 187, 77, 65, 167, 209, 237, 171, 101, 247, 5, 148, 34, 250, 28, 103, 84, 222, 86, 133,
			110, 161, 25, 171, 181, 79, 218, 251, 159, 117, 60, 139, 166, 97, 63, 98, 128, 249, 7, 130, 80, 143, 65,
			135, 77, 65, 245, 209, 233, 37, 26, 212, 56, 5, 196, 106, 19, 132, 166, 165, 174, 87, 148, 167, 185, 104,
			199, 114, 169, 38, 73, 133, 137, 101, 0, 170, 154, 138, 227, 69, 71, 229, 214, 62, 30, 191, 246, 17, 52,
			231, 217, 172, 201, 231, 0, 120, 49, 0, 71, 31, 143, 6, 64, 157, 53, 192, 26, 121, 159, 173, 0, 55, 0, 75,
			111, 89, 25, 237, 233, 155, 70, 114, 186, 16, 184, 3, 47, 56, 225, 158, 237, 138, 221, 22, 69, 90, 39, 130,
			95, 50, 102, 154, 175, 218, 234, 83, 58, 232, 132, 243, 33, 6, 149, 224, 225, 234, 104, 92, 29, 213, 170,
			26, 90, 246, 113, 253, 179, 109, 89, 171, 239, 163, 46, 201, 166, 63, 87, 56, 239, 109, 59, 103, 148, 91,
			119, 219, 48, 91, 205, 103, 194, 82, 201, 198, 156, 99, 190, 161, 201, 223, 79, 143, 53, 6, 182, 27, 177,
			183, 56, 67, 139, 140, 214, 134, 105, 55, 23, 71, 39, 202, 28, 25, 61, 111, 48, 170, 199, 120, 10, 117,
			57, 212, 202, 237, 202, 129, 157, 53, 18, 214, 211, 204, 96, 144, 135, 169, 214, 118, 85, 132, 86, 124,
			175, 236, 205, 2, 28, 253, 13, 116, 9, 57, 145, 179, 63, 222, 156, 133, 144
		};
		const CharString _code = _decompress_code(_code_compressed, 690, 1986);

		setup(_code.get_data() + 0, _code.get_data() + 535, nullptr, "LuminanceReduceRasterShaderRD");
	}
};
