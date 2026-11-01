/**************************************************************************/
/*  cube_to_dp.glsl.gen.h                                                 */
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

class CubeToDpShaderRD : public ShaderRD {
public:
	CubeToDpShaderRD() {
		static const uint8_t _code_compressed[] = {
			120, 218, 189, 84, 77, 111, 218, 64, 16, 205, 53, 254, 21, 35, 69, 138, 108, 176, 93, 8, 228, 82, 148, 244,
			208, 16, 137, 75, 26, 53, 82, 46, 17, 178, 22, 123, 33, 43, 25, 27, 237, 218, 8, 59, 234, 127, 207, 236,
			135, 237, 53, 208, 42, 167, 94, 192, 51, 251, 230, 205, 155, 143, 93, 231, 106, 79, 185, 96, 121, 6, 211,
			219, 145, 227, 92, 189, 206, 127, 191, 44, 126, 61, 69, 15, 243, 199, 197, 211, 252, 197, 113, 82, 82, 229,
			101, 225, 238, 74, 241, 30, 197, 121, 38, 10, 146, 21, 62, 136, 34, 153, 78, 70, 30, 148, 25, 91, 231, 124,
			11, 207, 132, 147, 173, 128, 15, 231, 114, 157, 230, 164, 128, 58, 90, 19, 62, 235, 172, 140, 42, 115, 79,
			227, 27, 40, 232, 129, 166, 145, 96, 53, 157, 57, 127, 156, 157, 138, 156, 181, 137, 210, 60, 38, 133, 212,
			115, 7, 200, 143, 30, 80, 65, 229, 62, 98, 89, 65, 249, 14, 145, 251, 156, 37, 176, 37, 44, 115, 61, 153,
			81, 157, 175, 136, 160, 17, 225, 252, 109, 186, 196, 72, 233, 122, 91, 186, 242, 207, 29, 133, 35, 31, 240,
			199, 243, 161, 179, 199, 157, 61, 62, 103, 75, 188, 135, 130, 219, 180, 72, 218, 166, 216, 164, 209, 43,
			229, 88, 198, 34, 75, 232, 97, 137, 48, 244, 60, 231, 130, 25, 221, 72, 51, 117, 187, 200, 1, 220, 132,
			35, 8, 160, 33, 214, 217, 100, 237, 206, 133, 243, 197, 246, 247, 187, 194, 178, 211, 166, 24, 160, 160,
			133, 196, 248, 176, 98, 89, 194, 178, 141, 14, 104, 198, 36, 200, 118, 151, 82, 254, 179, 92, 81, 16, 121,
			201, 99, 26, 197, 248, 61, 251, 143, 99, 62, 55, 188, 114, 143, 50, 173, 98, 142, 9, 240, 148, 172, 132,
			171, 57, 194, 206, 143, 77, 148, 35, 194, 227, 56, 197, 202, 176, 231, 216, 108, 57, 64, 24, 170, 158, 15,
			44, 14, 15, 39, 208, 89, 221, 46, 88, 99, 247, 20, 31, 90, 19, 200, 176, 90, 146, 234, 89, 78, 52, 111,
			127, 136, 114, 57, 52, 40, 172, 101, 143, 195, 219, 38, 117, 0, 73, 94, 184, 230, 236, 80, 249, 208, 126,
			34, 63, 52, 81, 24, 163, 63, 80, 140, 1, 171, 236, 6, 92, 225, 121, 208, 124, 203, 40, 182, 134, 211, 250,
			195, 3, 220, 223, 41, 53, 240, 129, 24, 91, 80, 19, 92, 163, 78, 92, 52, 51, 161, 132, 238, 138, 119, 60,
			69, 138, 162, 228, 212, 181, 118, 160, 209, 233, 133, 92, 234, 48, 125, 40, 165, 211, 180, 223, 82, 41,
			213, 184, 234, 76, 75, 208, 159, 149, 7, 215, 215, 112, 234, 175, 61, 53, 106, 228, 188, 108, 248, 154,
			158, 192, 189, 148, 15, 63, 116, 159, 187, 27, 162, 106, 250, 174, 189, 65, 223, 45, 11, 2, 154, 10, 10,
			150, 138, 10, 137, 76, 94, 91, 68, 245, 21, 17, 85, 95, 68, 115, 67, 251, 34, 148, 55, 24, 255, 83, 68,
			125, 94, 68, 231, 174, 254, 170, 161, 62, 163, 161, 125, 42, 122, 26, 90, 33, 150, 6, 195, 105, 209, 158,
			105, 231, 233, 34, 68, 107, 118, 64, 172, 92, 218, 111, 214, 210, 250, 90, 173, 26, 116, 179, 48, 250, 54,
			105, 75, 93, 130, 246, 210, 167, 76, 94, 250, 168, 15, 52, 155, 170, 31, 4, 219, 198, 231, 2, 115, 185,
			61, 123, 120, 4, 31, 154, 60, 131, 35, 92, 208, 199, 169, 247, 185, 83, 120, 140, 237, 233, 26, 116, 5,
			123, 152, 223, 134, 234, 215, 251, 145, 147, 205, 131, 97, 82, 80, 249, 102, 93, 124, 2, 226, 188, 28, 15
		};
		const CharString _code = _decompress_code(_code_compressed, 648, 1821);

		setup(_code.get_data() + 0, _code.get_data() + 383, nullptr, "CubeToDpShaderRD");
	}
};
