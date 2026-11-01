/**************************************************************************/
/*  feed.glsl.gen.h                                                       */
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

#include "drivers/gles3/shader_gles3.h"

class FeedShaderGLES3 : public ShaderGLES3 {
public:
	enum ShaderVariant {
		MODE_DEFAULT,
	};

	enum Specializations : uint64_t {
		USE_EXTERNAL_SAMPLER = 1,
	};

	_FORCE_INLINE_ bool version_bind_shader(RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		return _version_bind_shader(p_version, p_variant, p_specialization);
	}

protected:
	virtual void _init() override {
		static const char **_uniform_strings = nullptr;
		static const char *_variant_defines[] = {
			"",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "sourceFeed", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization _spec_pairs[] = {
			{ "USE_EXTERNAL_SAMPLER", false },
		};
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 125, 144, 177, 78, 195, 48, 16, 134, 187, 230, 158, 226, 164, 46, 73, 40, 77, 168, 202, 66, 196,
			80, 9, 51, 21, 168, 26, 144, 216, 34, 147, 216, 145, 37, 199, 174, 28, 39, 42, 66, 125, 119, 156, 144, 18,
			74, 17, 203, 13, 190, 255, 62, 223, 119, 32, 233, 187, 110, 172, 47, 117, 78, 173, 208, 10, 111, 49, 14,
			80, 40, 108, 89, 190, 112, 197, 88, 182, 207, 168, 181, 70, 188, 37, 0, 46, 249, 213, 104, 218, 76, 40,
			203, 204, 206, 61, 66, 171, 69, 129, 21, 21, 202, 15, 240, 3, 188, 239, 158, 99, 157, 0, 48, 196, 120, 126,
			141, 23, 93, 77, 192, 43, 101, 182, 209, 181, 24, 126, 117, 216, 165, 127, 18, 159, 225, 213, 60, 238, 75,
			144, 192, 1, 32, 10, 49, 151, 84, 149, 151, 92, 155, 138, 90, 212, 156, 99, 24, 193, 4, 254, 84, 24, 86,
			93, 34, 55, 180, 204, 114, 45, 181, 73, 224, 232, 245, 115, 253, 51, 172, 234, 168, 83, 193, 11, 198, 241,
			37, 37, 25, 121, 125, 38, 219, 199, 213, 58, 75, 87, 15, 155, 53, 217, 66, 163, 68, 151, 197, 154, 86, 59,
			201, 12, 217, 59, 146, 162, 242, 137, 164, 88, 235, 198, 228, 236, 158, 177, 34, 193, 40, 66, 39, 227, 194,
			246, 38, 134, 41, 147, 53, 251, 61, 185, 184, 251, 111, 64, 21, 130, 159, 29, 183, 87, 234, 109, 156, 166,
			75, 219, 198, 48, 127, 132, 204, 70, 53, 119, 52, 240, 70, 121, 23, 31, 142, 112, 128, 201, 39, 199, 221,
			163, 138
		};
		const CharString _code = _decompress_code(_code_compressed, 282, 502);

		_setup(_code.get_data(), _code.get_data() + 195, "FeedShaderGLES3",
				0, _uniform_strings, 0, _ubo_pairs,
				0, _feedbacks, 1, _texunit_pairs,
				1, _spec_pairs, 1, _variant_defines);
	}
};
