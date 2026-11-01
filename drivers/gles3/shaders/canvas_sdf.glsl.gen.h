/**************************************************************************/
/*  canvas_sdf.glsl.gen.h                                                 */
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

class CanvasSdfShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		SIZE,
		STRIDE,
		SHIFT,
		BASE_SIZE,
	};

	enum ShaderVariant {
		MODE_LOAD,
		MODE_LOAD_SHRINK,
		MODE_PROCESS,
		MODE_STORE,
		MODE_STORE_SHRINK,
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
			"size",
			"stride",
			"shift",
			"base_size"
		};
		static const char *_variant_defines[] = {
			"#define MODE_LOAD",
			"#define MODE_LOAD_SHRINK",
			"#define MODE_PROCESS",
			"#define MODE_STORE",
			"#define MODE_STORE_SHRINK",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "src_pixels", 0 },
			{ "src_process", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization *_spec_pairs = nullptr;
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 213, 87, 219, 110, 219, 70, 16, 205, 43, 249, 21, 91, 248, 133, 52, 37, 145, 82, 236, 36, 8, 173,
			22, 65, 44, 55, 69, 147, 56, 176, 252, 80, 32, 48, 8, 154, 92, 74, 235, 174, 184, 10, 185, 74, 165, 52,
			254, 247, 206, 222, 120, 149, 148, 34, 40, 90, 212, 128, 121, 153, 219, 206, 158, 57, 51, 75, 217, 52, 222,
			177, 13, 119, 40, 75, 98, 78, 88, 142, 166, 40, 112, 17, 201, 209, 103, 156, 76, 224, 82, 112, 188, 141,
			98, 206, 11, 114, 31, 218, 182, 127, 138, 18, 26, 231, 139, 97, 198, 138, 85, 204, 17, 216, 159, 250, 182,
			189, 201, 137, 16, 32, 34, 157, 74, 242, 5, 135, 181, 44, 231, 168, 4, 247, 180, 43, 91, 146, 140, 135,
			29, 215, 251, 184, 196, 145, 242, 183, 63, 51, 146, 162, 85, 76, 114, 199, 69, 127, 218, 214, 130, 70, 31,
			88, 73, 116, 142, 96, 125, 230, 180, 178, 27, 160, 241, 40, 144, 23, 55, 180, 31, 247, 164, 154, 101, 34,
			215, 39, 246, 73, 138, 51, 146, 99, 52, 191, 188, 138, 222, 189, 250, 45, 122, 59, 123, 255, 243, 237, 27,
			52, 126, 246, 244, 197, 217, 40, 176, 237, 19, 146, 33, 101, 146, 58, 239, 174, 47, 103, 209, 219, 235,
			87, 151, 46, 250, 250, 181, 47, 141, 230, 111, 110, 126, 121, 255, 171, 91, 237, 130, 178, 63, 214, 168,
			140, 87, 107, 138, 139, 201, 37, 42, 139, 36, 90, 147, 45, 166, 101, 232, 251, 144, 42, 152, 241, 151, 129,
			125, 2, 2, 92, 249, 44, 201, 98, 185, 70, 164, 227, 85, 176, 4, 151, 93, 183, 60, 37, 89, 133, 182, 181,
			7, 109, 107, 15, 218, 86, 31, 109, 171, 143, 246, 119, 236, 186, 167, 252, 112, 115, 253, 122, 54, 159,
			187, 246, 94, 78, 129, 68, 86, 249, 12, 165, 164, 228, 113, 158, 224, 40, 35, 152, 166, 161, 198, 227, 160,
			211, 1, 31, 5, 134, 84, 102, 148, 197, 60, 226, 44, 146, 180, 144, 111, 104, 29, 201, 187, 224, 14, 130,
			63, 133, 178, 180, 78, 216, 106, 13, 209, 179, 34, 78, 184, 163, 205, 208, 169, 162, 212, 228, 252, 124,
			20, 192, 75, 235, 62, 216, 251, 170, 184, 6, 100, 179, 100, 192, 225, 84, 6, 30, 109, 183, 187, 47, 38,
			90, 160, 173, 144, 223, 112, 217, 251, 34, 194, 20, 152, 111, 138, 92, 70, 145, 12, 238, 52, 128, 170, 217,
			154, 149, 144, 187, 124, 118, 160, 37, 174, 138, 120, 241, 154, 177, 34, 29, 109, 119, 174, 42, 35, 148,
			4, 85, 181, 178, 109, 235, 158, 49, 138, 74, 70, 33, 216, 20, 1, 155, 48, 189, 194, 60, 89, 58, 53, 57,
			7, 34, 234, 0, 224, 30, 21, 232, 71, 20, 140, 206, 33, 153, 54, 222, 224, 169, 34, 252, 164, 74, 232, 168,
			4, 134, 79, 39, 207, 159, 61, 119, 193, 85, 120, 163, 151, 45, 101, 75, 87, 23, 172, 155, 161, 102, 19,
			36, 42, 121, 10, 43, 141, 209, 197, 133, 33, 108, 131, 169, 160, 17, 155, 239, 233, 18, 156, 115, 92, 128,
			86, 26, 121, 26, 27, 105, 35, 16, 209, 86, 5, 166, 21, 110, 42, 51, 8, 160, 74, 47, 118, 55, 198, 147, 32,
			84, 41, 100, 108, 147, 11, 145, 121, 151, 27, 143, 154, 82, 104, 33, 228, 8, 21, 145, 2, 184, 65, 78, 112,
			243, 60, 89, 168, 90, 255, 160, 244, 15, 74, 255, 96, 244, 166, 115, 69, 1, 100, 57, 91, 153, 147, 1, 122,
			16, 201, 129, 89, 134, 156, 56, 223, 57, 139, 2, 199, 176, 197, 219, 101, 156, 207, 62, 109, 98, 234, 104,
			207, 65, 221, 193, 174, 171, 67, 3, 25, 115, 78, 242, 13, 150, 17, 30, 197, 229, 239, 16, 160, 138, 216,
			34, 129, 74, 65, 186, 154, 240, 26, 50, 96, 7, 4, 163, 56, 95, 240, 165, 163, 0, 215, 187, 25, 234, 130,
			184, 106, 15, 50, 130, 52, 191, 64, 85, 16, 75, 100, 34, 132, 202, 196, 82, 197, 209, 17, 148, 76, 102,
			110, 53, 176, 247, 188, 122, 71, 13, 1, 188, 63, 138, 34, 155, 60, 77, 161, 166, 170, 142, 106, 69, 223,
			95, 197, 197, 239, 26, 3, 150, 211, 29, 2, 251, 152, 82, 20, 23, 88, 73, 109, 147, 68, 139, 216, 161, 10,
			222, 235, 5, 69, 115, 112, 56, 202, 110, 61, 14, 237, 127, 154, 196, 221, 18, 170, 163, 162, 110, 226, 237,
			46, 236, 182, 61, 56, 142, 182, 80, 129, 32, 108, 98, 165, 192, 81, 65, 135, 226, 54, 212, 235, 142, 205,
			206, 133, 169, 78, 237, 7, 25, 197, 224, 41, 65, 212, 43, 11, 48, 9, 112, 130, 225, 18, 229, 12, 38, 47,
			19, 220, 231, 12, 132, 37, 166, 153, 45, 57, 9, 4, 16, 82, 150, 149, 17, 143, 239, 169, 98, 45, 172, 251,
			34, 172, 245, 114, 143, 149, 197, 199, 182, 237, 157, 41, 206, 199, 59, 71, 17, 75, 85, 106, 60, 64, 195,
			177, 59, 104, 136, 130, 158, 196, 51, 70, 29, 199, 160, 103, 21, 244, 141, 188, 94, 116, 175, 31, 29, 68,
			178, 78, 135, 251, 67, 225, 219, 236, 141, 125, 99, 164, 189, 231, 198, 76, 233, 205, 12, 113, 245, 26,
			104, 145, 59, 56, 117, 204, 209, 223, 24, 30, 20, 42, 36, 38, 71, 61, 52, 244, 62, 196, 200, 128, 19, 252,
			248, 128, 249, 214, 108, 169, 179, 58, 206, 205, 230, 124, 17, 252, 172, 198, 18, 200, 13, 73, 117, 20,
			67, 84, 51, 125, 140, 133, 73, 162, 94, 108, 104, 30, 91, 188, 181, 36, 115, 59, 206, 130, 190, 7, 162,
			144, 214, 248, 50, 157, 233, 134, 200, 247, 59, 76, 22, 68, 103, 240, 153, 68, 178, 12, 23, 88, 104, 118,
			107, 92, 47, 168, 74, 47, 2, 29, 24, 143, 125, 10, 84, 73, 154, 9, 9, 55, 147, 161, 14, 98, 180, 106, 44,
			214, 147, 18, 158, 170, 50, 116, 135, 224, 183, 27, 251, 59, 71, 218, 252, 246, 250, 102, 246, 223, 141,
			163, 250, 188, 238, 119, 22, 44, 167, 90, 176, 19, 79, 88, 15, 83, 179, 109, 228, 79, 59, 31, 254, 226,
			91, 7, 76, 224, 183, 194, 106, 237, 164, 98, 78, 212, 63, 35, 250, 48, 181, 191, 52, 211, 83, 56, 39, 61,
			248, 151, 159, 94, 135, 240, 106, 124, 225, 252, 95, 207, 129, 99, 192, 215, 124, 62, 134, 253, 191, 1,
			253, 163, 253, 228, 47, 110, 125, 86, 42
		};
		const CharString _code = _decompress_code(_code_compressed, 1144, 3791);

		_setup(_code.get_data(), _code.get_data() + 241, "CanvasSdfShaderGLES3",
				4, _uniform_strings, 0, _ubo_pairs,
				0, _feedbacks, 2, _texunit_pairs,
				0, _spec_pairs, 5, _variant_defines);
	}
};
