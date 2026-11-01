/**************************************************************************/
/*  cubemap_filter.glsl.gen.h                                             */
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

class CubemapFilterShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		FACE_ID,
		SAMPLE_COUNT,
		SAMPLE_DIRECTIONS_MIP,
		WEIGHT,
	};

	enum ShaderVariant {
		MODE_DEFAULT,
		MODE_COPY,
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
			"face_id",
			"sample_count",
			"sample_directions_mip",
			"weight"
		};
		static const char *_variant_defines[] = {
			"",
			"#define MODE_DIRECT_WRITE",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "source_cube", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization *_spec_pairs = nullptr;
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 165, 150, 91, 111, 226, 56, 20, 128, 231, 21, 255, 138, 35, 245, 97, 67, 33, 33, 9, 208, 203,
			48, 221, 213, 168, 237, 67, 165, 210, 169, 102, 232, 236, 74, 85, 21, 165, 193, 80, 75, 193, 142, 114, 161,
			192, 106, 254, 251, 30, 219, 33, 132, 198, 204, 3, 203, 3, 74, 124, 46, 254, 206, 37, 246, 33, 113, 184,
			22, 69, 110, 197, 34, 10, 115, 38, 56, 92, 129, 219, 6, 198, 225, 141, 205, 223, 18, 88, 210, 200, 199,
			191, 52, 167, 171, 32, 204, 243, 148, 189, 142, 72, 239, 20, 162, 56, 228, 115, 123, 38, 210, 69, 152, 3,
			26, 157, 246, 8, 65, 47, 117, 163, 98, 25, 48, 158, 211, 52, 25, 17, 178, 20, 108, 10, 139, 144, 113, 171,
			13, 255, 146, 86, 37, 194, 205, 62, 248, 110, 205, 227, 224, 81, 100, 172, 68, 65, 79, 3, 171, 82, 239,
			130, 235, 184, 93, 240, 28, 183, 61, 34, 191, 72, 19, 100, 54, 147, 36, 159, 8, 57, 153, 210, 25, 227, 20,
			198, 193, 227, 29, 244, 29, 111, 224, 13, 47, 253, 179, 97, 127, 120, 73, 72, 193, 153, 212, 135, 44, 92,
			36, 49, 77, 175, 139, 87, 10, 153, 40, 210, 136, 6, 17, 62, 143, 160, 215, 67, 34, 212, 202, 63, 187, 228,
			80, 176, 91, 39, 8, 6, 179, 16, 77, 217, 20, 227, 60, 97, 51, 142, 59, 195, 248, 219, 205, 109, 112, 115,
			247, 253, 246, 122, 18, 252, 253, 253, 110, 114, 91, 233, 23, 210, 64, 239, 28, 68, 162, 224, 249, 168,
			18, 201, 88, 183, 162, 41, 75, 105, 36, 115, 144, 5, 11, 150, 60, 143, 191, 254, 19, 252, 248, 58, 126,
			188, 191, 13, 174, 191, 61, 61, 76, 94, 118, 86, 179, 88, 32, 213, 59, 197, 196, 163, 175, 19, 202, 167,
			108, 70, 200, 126, 253, 234, 165, 48, 150, 91, 150, 78, 109, 63, 75, 195, 57, 114, 197, 34, 29, 253, 62,
			137, 189, 30, 220, 8, 254, 71, 142, 9, 136, 226, 98, 74, 33, 23, 156, 46, 194, 4, 55, 138, 156, 121, 156,
			197, 240, 74, 163, 176, 200, 40, 132, 113, 140, 120, 240, 30, 98, 224, 44, 131, 252, 141, 226, 226, 172,
			224, 58, 188, 174, 148, 77, 149, 39, 165, 129, 98, 40, 67, 203, 228, 38, 147, 55, 180, 9, 147, 36, 21, 43,
			182, 208, 196, 116, 149, 96, 110, 50, 224, 130, 219, 156, 206, 113, 113, 73, 17, 35, 41, 242, 17, 236, 191,
			203, 253, 10, 174, 163, 152, 34, 208, 91, 184, 100, 34, 117, 8, 134, 218, 135, 24, 23, 195, 52, 200, 69,
			144, 165, 243, 87, 75, 173, 169, 200, 85, 139, 166, 52, 47, 82, 142, 61, 187, 82, 18, 11, 123, 110, 56,
			108, 195, 41, 36, 226, 221, 82, 106, 93, 80, 2, 215, 25, 120, 103, 234, 119, 222, 110, 131, 189, 93, 148,
			218, 149, 134, 219, 46, 251, 245, 255, 198, 163, 66, 160, 25, 66, 136, 52, 94, 151, 129, 72, 124, 25, 134,
			14, 232, 64, 32, 106, 1, 241, 173, 198, 131, 235, 244, 221, 97, 223, 61, 115, 61, 15, 58, 248, 118, 118,
			225, 123, 231, 30, 254, 218, 234, 213, 245, 252, 161, 239, 95, 156, 95, 232, 16, 148, 119, 252, 60, 104,
			124, 141, 12, 211, 137, 248, 73, 35, 171, 108, 178, 110, 245, 53, 220, 221, 168, 189, 49, 192, 190, 122,
			127, 90, 162, 90, 46, 210, 236, 249, 12, 91, 151, 180, 48, 17, 246, 138, 180, 246, 69, 222, 203, 179, 251,
			162, 191, 121, 149, 180, 250, 215, 142, 223, 36, 20, 96, 255, 9, 157, 141, 193, 204, 219, 55, 179, 189,
			210, 88, 219, 45, 165, 157, 189, 54, 216, 249, 149, 93, 101, 82, 179, 179, 87, 138, 93, 227, 118, 26, 184,
			174, 25, 215, 222, 231, 181, 55, 6, 187, 163, 120, 221, 58, 175, 1, 183, 83, 199, 109, 154, 247, 235, 184,
			6, 115, 157, 221, 149, 193, 204, 251, 109, 148, 75, 115, 148, 253, 58, 173, 41, 74, 123, 93, 207, 110, 3,
			215, 63, 14, 215, 55, 227, 238, 211, 54, 123, 200, 111, 208, 238, 195, 118, 234, 176, 205, 96, 135, 117,
			88, 251, 16, 109, 179, 227, 135, 71, 182, 194, 176, 129, 251, 161, 40, 246, 166, 158, 220, 6, 239, 224,
			184, 228, 14, 142, 196, 29, 152, 113, 43, 218, 78, 157, 86, 94, 69, 87, 72, 112, 10, 89, 160, 221, 72, 214,
			14, 250, 174, 173, 120, 114, 165, 122, 243, 95, 28, 210, 82, 7, 83, 74, 179, 34, 150, 246, 214, 62, 129,
			62, 147, 84, 212, 167, 120, 80, 57, 43, 121, 182, 29, 208, 241, 74, 157, 181, 212, 49, 171, 248, 120, 136,
			109, 15, 86, 46, 199, 130, 152, 109, 168, 165, 55, 47, 143, 201, 253, 129, 103, 119, 38, 215, 210, 128,
			154, 173, 242, 228, 148, 17, 239, 238, 104, 173, 254, 128, 139, 31, 15, 90, 121, 198, 150, 211, 70, 91,
			143, 27, 230, 105, 163, 181, 187, 199, 183, 67, 20, 186, 66, 94, 122, 47, 166, 86, 109, 216, 233, 194, 131,
			174, 159, 131, 151, 200, 118, 178, 58, 161, 113, 38, 171, 161, 7, 146, 98, 177, 117, 177, 99, 238, 195,
			83, 162, 147, 130, 178, 240, 53, 179, 30, 156, 77, 27, 190, 160, 167, 203, 203, 75, 248, 203, 84, 105, 248,
			108, 108, 183, 242, 146, 152, 224, 195, 68, 55, 229, 46, 161, 81, 42, 178, 204, 218, 238, 132, 168, 242,
			26, 69, 53, 213, 132, 90, 136, 244, 210, 76, 175, 171, 38, 123, 144, 247, 11, 142, 15, 96, 213, 71, 45,
			174, 162, 112, 139, 81, 125, 225, 203, 254, 32, 86, 19, 117, 58, 170, 108, 45, 227, 72, 38, 39, 50, 116,
			102, 158, 212, 118, 62, 100, 143, 232, 92, 221, 163, 246, 68, 182, 175, 193, 145, 179, 90, 111, 42, 197,
			101, 24, 235, 162, 27, 43, 117, 223, 53, 123, 120, 87, 197, 147, 78, 240, 243, 25, 179, 21, 20, 25, 227,
			243, 114, 190, 145, 174, 149, 215, 143, 83, 66, 24, 203, 164, 181, 176, 188, 210, 26, 58, 87, 106, 247,
			3, 144, 18, 17, 187, 90, 106, 67, 239, 170, 154, 54, 73, 101, 126, 245, 113, 156, 42, 5, 114, 143, 102,
			47, 150, 194, 93, 191, 169, 161, 245, 23, 249, 244, 31, 116, 226, 193, 244
		};
		const CharString _code = _decompress_code(_code_compressed, 1114, 3213);

		_setup(_code.get_data(), _code.get_data() + 212, "CubemapFilterShaderGLES3",
				4, _uniform_strings, 0, _ubo_pairs,
				0, _feedbacks, 1, _texunit_pairs,
				0, _spec_pairs, 2, _variant_defines);
	}
};
