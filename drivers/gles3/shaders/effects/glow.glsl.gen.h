/**************************************************************************/
/*  glow.glsl.gen.h                                                       */
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

class GlowShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		VIEW,
		PIXEL_SIZE,
		LUMINANCE_MULTIPLIER,
		GLOW_BLOOM,
		GLOW_HDR_THRESHOLD,
		GLOW_HDR_SCALE,
		GLOW_LUMINANCE_CAP,
	};

	enum ShaderVariant {
		MODE_FILTER,
		MODE_DOWNSAMPLE,
		MODE_UPSAMPLE,
	};

	enum Specializations : uint64_t {
		USE_MULTIVIEW = 1,
	};

	_FORCE_INLINE_ bool version_bind_shader(RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		return _version_bind_shader(p_version, p_variant, p_specialization);
	}

	_FORCE_INLINE_ int version_get_uniform(Uniforms p_uniform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		return _version_get_uniform(p_uniform, p_version, p_variant, p_specialization);
	}

	/* clang-format off */
#define TRY_GET_UNIFORM(var_name) int var_name = version_get_uniform(p_uniform, p_version, p_variant, p_specialization); if (var_name < 0) return
	/* clang-format on */

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, double p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Color &p_color, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat col[4] = { p_color.r, p_color.g, p_color.b, p_color.a };
		glUniform4fv(uniform_location, 1, col);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector2 &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec2[2] = { float(p_vec2.x), float(p_vec2.y) };
		glUniform2fv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Size2i &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLint vec2[2] = { GLint(p_vec2.x), GLint(p_vec2.y) };
		glUniform2iv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector3 &p_vec3, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec3[3] = { float(p_vec3.x), float(p_vec3.y), float(p_vec3.z) };
		glUniform3fv(uniform_location, 1, vec3);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector4 &p_vec4, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec4[4] = { float(p_vec4.x), float(p_vec4.y), float(p_vec4.z), float(p_vec4.w) };
		glUniform4fv(uniform_location, 1, vec4);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform2f(uniform_location, p_a, p_b);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform3f(uniform_location, p_a, p_b, p_c);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, float p_d, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform4f(uniform_location, p_a, p_b, p_c, p_d);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform3D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		const Transform3D &tr = p_transform;

		GLfloat matrix[16] = { /* build a 16x16 matrix */
			(GLfloat)tr.basis.rows[0][0],
			(GLfloat)tr.basis.rows[1][0],
			(GLfloat)tr.basis.rows[2][0],
			(GLfloat)0,
			(GLfloat)tr.basis.rows[0][1],
			(GLfloat)tr.basis.rows[1][1],
			(GLfloat)tr.basis.rows[2][1],
			(GLfloat)0,
			(GLfloat)tr.basis.rows[0][2],
			(GLfloat)tr.basis.rows[1][2],
			(GLfloat)tr.basis.rows[2][2],
			(GLfloat)0,
			(GLfloat)tr.origin.x,
			(GLfloat)tr.origin.y,
			(GLfloat)tr.origin.z,
			(GLfloat)1
		};

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform2D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		const Transform2D &tr = p_transform;

		GLfloat matrix[16] = { /* build a 16x16 matrix */
			(GLfloat)tr.columns[0][0],
			(GLfloat)tr.columns[0][1],
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)tr.columns[1][0],
			(GLfloat)tr.columns[1][1],
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)1,
			(GLfloat)0,
			(GLfloat)tr.columns[2][0],
			(GLfloat)tr.columns[2][1],
			(GLfloat)0,
			(GLfloat)1
		};

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Projection &p_matrix, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 0) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat matrix[16];

		for (int i = 0; i < 4; i++) {
			for (int j = 0; j < 4; j++) {
				matrix[i * 4 + j] = p_matrix.columns[i][j];
			}
		}

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}

#undef TRY_GET_UNIFORM

protected:
	virtual void _init() override {
		static const char *_uniform_strings[] = {
			"view",
			"pixel_size",
			"luminance_multiplier",
			"glow_bloom",
			"glow_hdr_threshold",
			"glow_hdr_scale",
			"glow_luminance_cap"
		};
		static const char *_variant_defines[] = {
			"#define MODE_FILTER",
			"#define MODE_DOWNSAMPLE",
			"#define MODE_UPSAMPLE",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "source_color", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization _spec_pairs[] = {
			{ "USE_MULTIVIEW", false },
		};
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 189, 86, 93, 111, 155, 48, 20, 237, 107, 248, 21, 150, 250, 18, 26, 242, 209, 52, 147, 166, 69,
			125, 168, 212, 76, 170, 148, 182, 209, 218, 174, 143, 200, 1, 3, 214, 12, 142, 140, 73, 210, 77, 253, 239,
			187, 198, 33, 64, 66, 58, 104, 211, 189, 160, 4, 238, 61, 247, 220, 115, 125, 108, 51, 252, 194, 19, 217,
			102, 220, 193, 146, 242, 8, 93, 162, 129, 137, 104, 132, 150, 196, 25, 194, 67, 72, 178, 182, 177, 148,
			130, 206, 199, 134, 209, 63, 67, 14, 195, 145, 223, 245, 184, 8, 177, 68, 16, 127, 214, 55, 12, 0, 208,
			241, 201, 210, 166, 145, 36, 98, 1, 177, 75, 78, 93, 20, 98, 26, 181, 77, 244, 199, 104, 109, 63, 65, 133,
			18, 44, 58, 67, 131, 222, 23, 212, 81, 207, 177, 209, 242, 153, 61, 227, 49, 221, 112, 1, 212, 81, 187,
			20, 110, 161, 243, 222, 32, 125, 152, 99, 227, 181, 130, 146, 231, 41, 78, 39, 7, 168, 158, 82, 207, 37,
			30, 186, 189, 191, 158, 216, 223, 111, 166, 143, 147, 31, 217, 171, 167, 135, 137, 125, 251, 52, 125, 188,
			249, 121, 51, 121, 54, 146, 136, 170, 68, 20, 227, 112, 193, 136, 24, 94, 95, 9, 129, 95, 80, 204, 19, 225,
			16, 219, 225, 140, 139, 49, 234, 247, 17, 16, 131, 80, 249, 109, 96, 156, 18, 22, 147, 253, 188, 183, 83,
			34, 151, 122, 234, 93, 117, 113, 143, 113, 96, 190, 164, 100, 53, 222, 190, 75, 117, 94, 208, 53, 97, 118,
			76, 127, 147, 241, 78, 48, 75, 66, 26, 225, 8, 10, 134, 9, 147, 116, 193, 40, 17, 187, 49, 62, 227, 43,
			123, 206, 56, 15, 43, 191, 4, 174, 176, 101, 32, 72, 28, 112, 230, 30, 140, 136, 29, 204, 72, 229, 215,
			156, 130, 131, 97, 33, 228, 77, 22, 69, 47, 13, 226, 250, 254, 249, 238, 225, 234, 118, 54, 157, 52, 211,
			239, 160, 38, 59, 53, 11, 248, 165, 186, 79, 179, 207, 172, 186, 69, 55, 50, 59, 21, 237, 193, 170, 124,
			183, 49, 210, 8, 121, 2, 251, 155, 226, 187, 78, 170, 88, 193, 45, 40, 121, 199, 37, 177, 208, 138, 32,
			65, 176, 11, 249, 60, 68, 56, 66, 52, 196, 62, 65, 43, 42, 3, 228, 242, 100, 206, 212, 231, 152, 179, 68,
			149, 180, 160, 73, 149, 128, 193, 95, 42, 74, 6, 60, 38, 138, 66, 181, 35, 90, 105, 11, 1, 102, 158, 157,
			54, 13, 140, 243, 230, 181, 137, 199, 105, 208, 5, 244, 169, 173, 123, 209, 222, 118, 108, 165, 203, 216,
			204, 34, 210, 214, 32, 8, 84, 149, 137, 32, 83, 238, 182, 139, 138, 91, 0, 97, 1, 226, 192, 236, 9, 95,
			237, 16, 163, 222, 0, 82, 117, 86, 231, 205, 52, 212, 213, 149, 115, 162, 26, 40, 135, 171, 11, 212, 57,
			22, 208, 30, 163, 222, 218, 66, 221, 194, 223, 151, 163, 81, 172, 129, 172, 247, 169, 218, 211, 28, 234,
			105, 22, 150, 238, 127, 152, 224, 174, 230, 205, 52, 249, 72, 118, 58, 171, 225, 91, 138, 190, 119, 76,
			245, 65, 15, 29, 11, 155, 98, 253, 203, 202, 93, 30, 52, 254, 170, 52, 54, 90, 122, 47, 14, 241, 218, 94,
			98, 150, 16, 24, 18, 252, 110, 167, 201, 61, 32, 148, 255, 241, 45, 61, 198, 222, 220, 84, 206, 212, 121,
			30, 33, 238, 28, 59, 191, 54, 105, 113, 200, 185, 12, 98, 73, 22, 237, 253, 211, 193, 170, 56, 49, 160,
			219, 242, 33, 97, 229, 84, 76, 171, 112, 248, 152, 138, 107, 182, 140, 160, 31, 77, 10, 218, 200, 24, 88,
			122, 117, 239, 31, 42, 102, 154, 154, 239, 145, 217, 69, 225, 128, 44, 155, 65, 232, 43, 67, 179, 227, 168,
			182, 77, 70, 117, 12, 177, 221, 11, 213, 172, 27, 121, 34, 187, 59, 237, 91, 163, 33, 64, 231, 163, 0, 181,
			13, 210, 152, 88, 125, 220, 210, 228, 55, 166, 208, 139, 191, 233, 193, 95, 107, 190, 141, 7, 156, 53, 83,
			164, 191, 6, 180, 161, 186, 185, 230, 251, 241, 251, 20, 234, 150, 37, 170, 80, 72, 87, 122, 31, 250, 64,
			81, 44, 98, 106, 176, 35, 206, 244, 200, 132, 63, 67, 226, 127, 47, 194, 15, 75, 220, 61, 178, 198, 221,
			250, 156, 15, 248, 231, 124, 88, 97, 160, 173, 81, 94, 141, 147, 191, 61, 214, 162, 90
		};
		const CharString _code = _decompress_code(_code_compressed, 781, 3626);

		_setup(_code.get_data(), _code.get_data() + 216, "GlowShaderGLES3",
				7, _uniform_strings, 0, _ubo_pairs,
				0, _feedbacks, 1, _texunit_pairs,
				1, _spec_pairs, 3, _variant_defines);
	}
};
