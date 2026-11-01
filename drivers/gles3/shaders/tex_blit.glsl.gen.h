/**************************************************************************/
/*  tex_blit.glsl.gen.h                                                   */
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

class TexBlitShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		OFFSET,
		SIZE,
		CONVERT_TO_SRGB,
		MODULATE,
		TIME,
	};

	enum ShaderVariant {
		MODE_DEFAULT,
	};

	enum Specializations : uint64_t {
		USE_OUTPUT1 = 1,
		USE_OUTPUT2 = 2,
		USE_OUTPUT3 = 4,
	};

	_FORCE_INLINE_ bool version_bind_shader(RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		return _version_bind_shader(p_version, p_variant, p_specialization);
	}

	_FORCE_INLINE_ int version_get_uniform(Uniforms p_uniform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		return _version_get_uniform(p_uniform, p_version, p_variant, p_specialization);
	}

	/* clang-format off */
#define TRY_GET_UNIFORM(var_name) int var_name = version_get_uniform(p_uniform, p_version, p_variant, p_specialization); if (var_name < 0) return
	/* clang-format on */

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, double p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Color &p_color, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat col[4] = { p_color.r, p_color.g, p_color.b, p_color.a };
		glUniform4fv(uniform_location, 1, col);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector2 &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec2[2] = { float(p_vec2.x), float(p_vec2.y) };
		glUniform2fv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Size2i &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		GLint vec2[2] = { GLint(p_vec2.x), GLint(p_vec2.y) };
		glUniform2iv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector3 &p_vec3, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec3[3] = { float(p_vec3.x), float(p_vec3.y), float(p_vec3.z) };
		glUniform3fv(uniform_location, 1, vec3);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector4 &p_vec4, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec4[4] = { float(p_vec4.x), float(p_vec4.y), float(p_vec4.z), float(p_vec4.w) };
		glUniform4fv(uniform_location, 1, vec4);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform2f(uniform_location, p_a, p_b);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform3f(uniform_location, p_a, p_b, p_c);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, float p_d, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform4f(uniform_location, p_a, p_b, p_c, p_d);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform3D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
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

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform2D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
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

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Projection &p_matrix, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 7) {
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
			"offset",
			"size",
			"convert_to_srgb",
			"modulate",
			"time"
		};
		static const char *_variant_defines[] = {
			"",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "source0", 0 },
			{ "source1", -1 },
			{ "source2", -2 },
			{ "source3", -3 },
			{ "global_shader_parameters_texture", -4 },
		};
		static UBOPair _ubo_pairs[] = {
			{ "MaterialUniforms", 0 },
		};
		static Specialization _spec_pairs[] = {
			{ "USE_OUTPUT1", true },
			{ "USE_OUTPUT2", true },
			{ "USE_OUTPUT3", true },
		};
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 149, 85, 109, 111, 226, 56, 16, 222, 175, 228, 87, 140, 132, 180, 74, 174, 148, 230, 133, 74,
			187, 203, 94, 165, 246, 160, 91, 116, 237, 177, 203, 203, 221, 125, 139, 76, 226, 128, 165, 16, 35, 219,
			105, 123, 183, 234, 127, 191, 177, 67, 154, 64, 67, 225, 190, 152, 224, 121, 230, 213, 51, 207, 88, 41,
			249, 135, 231, 202, 78, 121, 68, 20, 227, 25, 252, 10, 174, 3, 44, 131, 71, 26, 249, 120, 8, 69, 159, 67,
			162, 148, 96, 139, 190, 101, 229, 25, 75, 184, 88, 23, 66, 158, 36, 146, 170, 254, 238, 165, 100, 255, 82,
			4, 162, 201, 226, 127, 254, 136, 255, 30, 57, 139, 97, 77, 88, 102, 59, 240, 211, 106, 229, 143, 232, 101,
			199, 52, 252, 2, 110, 247, 18, 206, 244, 217, 183, 90, 23, 23, 48, 91, 49, 137, 42, 106, 5, 50, 34, 41,
			149, 160, 86, 20, 254, 52, 58, 112, 109, 116, 114, 69, 225, 71, 78, 98, 80, 92, 3, 163, 149, 129, 76, 104,
			164, 204, 71, 46, 169, 128, 13, 145, 146, 198, 152, 78, 7, 22, 68, 127, 97, 130, 99, 19, 54, 124, 132, 41,
			134, 106, 181, 150, 105, 248, 157, 75, 182, 205, 29, 99, 238, 217, 96, 23, 169, 97, 84, 126, 215, 133, 115,
			240, 186, 88, 147, 51, 176, 117, 114, 120, 105, 239, 198, 126, 102, 228, 78, 71, 255, 152, 195, 233, 91,
			47, 150, 245, 225, 181, 48, 146, 172, 55, 41, 21, 254, 0, 36, 207, 69, 68, 221, 62, 96, 134, 104, 1, 1,
			234, 139, 107, 29, 4, 122, 59, 192, 115, 239, 48, 210, 223, 69, 250, 135, 145, 193, 46, 50, 168, 144, 43,
			182, 92, 109, 106, 248, 101, 202, 23, 36, 13, 229, 138, 196, 84, 132, 27, 34, 200, 154, 42, 42, 100, 136,
			202, 42, 23, 84, 27, 122, 181, 211, 179, 172, 118, 76, 19, 150, 81, 248, 118, 63, 190, 185, 190, 15, 167,
			119, 215, 131, 225, 36, 156, 255, 49, 186, 29, 79, 30, 194, 217, 240, 239, 217, 124, 50, 12, 255, 26, 13,
			102, 119, 225, 195, 245, 244, 119, 176, 109, 15, 190, 126, 61, 9, 63, 189, 27, 221, 206, 28, 253, 20, 206,
			171, 159, 221, 248, 182, 89, 72, 123, 29, 178, 44, 166, 207, 142, 206, 145, 166, 183, 20, 59, 195, 62, 150,
			74, 7, 152, 238, 86, 155, 101, 170, 210, 255, 120, 114, 38, 168, 94, 87, 188, 186, 250, 31, 57, 117, 112,
			222, 170, 218, 141, 231, 179, 239, 243, 153, 27, 78, 39, 223, 110, 32, 215, 86, 107, 9, 23, 66, 175, 38,
			244, 247, 133, 126, 77, 216, 219, 23, 6, 53, 225, 39, 167, 122, 120, 125, 1, 17, 207, 116, 91, 135, 138,
			135, 82, 44, 23, 59, 99, 221, 131, 53, 143, 243, 148, 40, 90, 93, 39, 41, 39, 56, 105, 108, 173, 199, 189,
			228, 11, 51, 237, 5, 163, 192, 30, 165, 108, 25, 161, 167, 63, 194, 136, 167, 92, 184, 136, 109, 179, 4,
			67, 132, 249, 116, 24, 110, 179, 107, 82, 247, 154, 212, 189, 190, 213, 166, 89, 204, 146, 6, 43, 126, 147,
			21, 191, 201, 138, 255, 142, 149, 160, 201, 74, 208, 100, 37, 168, 172, 148, 220, 149, 81, 26, 75, 205,
			77, 11, 170, 113, 146, 197, 20, 162, 148, 100, 203, 115, 93, 62, 44, 157, 228, 5, 79, 45, 56, 214, 126,
			189, 166, 248, 6, 168, 134, 149, 212, 183, 2, 103, 81, 193, 38, 37, 17, 45, 227, 122, 184, 158, 13, 39,
			35, 108, 170, 109, 55, 77, 67, 140, 116, 176, 13, 209, 150, 42, 246, 122, 88, 230, 242, 121, 30, 240, 177,
			4, 35, 233, 124, 59, 22, 63, 113, 88, 209, 149, 102, 155, 246, 27, 75, 150, 245, 82, 43, 67, 209, 187, 120,
			137, 57, 6, 144, 98, 255, 16, 81, 182, 133, 109, 238, 76, 206, 134, 202, 177, 107, 164, 41, 70, 0, 164,
			160, 207, 192, 118, 187, 238, 229, 101, 130, 36, 216, 18, 20, 135, 43, 131, 53, 123, 182, 141, 162, 141,
			228, 152, 104, 38, 37, 14, 210, 232, 134, 63, 217, 198, 82, 23, 13, 119, 224, 21, 0, 23, 72, 187, 189, 196,
			209, 227, 78, 144, 80, 253, 238, 103, 63, 65, 124, 13, 139, 11, 65, 206, 86, 36, 123, 163, 143, 190, 221,
			192, 11, 220, 79, 168, 94, 208, 240, 222, 238, 193, 231, 185, 35, 89, 92, 110, 148, 8, 183, 2, 60, 173,
			168, 216, 46, 140, 136, 199, 230, 75, 2, 18, 131, 32, 250, 229, 54, 248, 120, 184, 62, 240, 205, 235, 87,
			160, 136, 88, 82, 37, 225, 73, 235, 102, 92, 193, 130, 231, 89, 108, 181, 76, 99, 20, 253, 93, 238, 19,
			87, 239, 133, 234, 40, 54, 68, 13, 232, 157, 10, 244, 79, 5, 6, 239, 2, 173, 246, 111, 227, 193, 16, 190,
			192, 205, 253, 104, 102, 153, 154, 12, 24, 174, 89, 17, 239, 165, 13, 44, 57, 45, 233, 106, 166, 209, 241,
			123, 195, 93, 33, 189, 18, 89, 205, 113, 195, 24, 87, 120, 191, 196, 251, 135, 241, 65, 13, 31, 148, 248,
			218, 108, 182, 48, 31, 123, 193, 121, 106, 239, 177, 29, 114, 125, 157, 121, 29, 211, 42, 181, 172, 116,
			135, 161, 189, 189, 89, 216, 149, 59, 102, 177, 78, 232, 18, 137, 82, 108, 161, 112, 126, 5, 134, 115, 11,
			127, 18, 41, 164, 107, 181, 94, 26, 43, 115, 52, 54, 175, 49, 54, 239, 72, 108, 94, 17, 155, 241, 122, 184,
			204, 71, 157, 251, 141, 206, 253, 35, 206, 253, 227, 206, 131, 19, 156, 7, 141, 206, 131, 35, 206, 131,
			55, 206, 95, 172, 15, 255, 1, 185, 154, 119, 167
		};
		const CharString _code = _decompress_code(_code_compressed, 1002, 2800);

		_setup(_code.get_data(), _code.get_data() + 347, "TexBlitShaderGLES3",
				5, _uniform_strings, 1, _ubo_pairs,
				0, _feedbacks, 5, _texunit_pairs,
				3, _spec_pairs, 1, _variant_defines);
	}
};
