/**************************************************************************/
/*  particles_copy.glsl.gen.h                                             */
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

class ParticlesCopyShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		SORT_DIRECTION,
		FRAME_REMAINDER,
		ALIGN_UP,
		ALIGN_MODE,
		INV_EMISSION_TRANSFORM,
		ALIGN_CHANNEL_FILTER,
		ALIGN_AXIS,
	};

	enum ShaderVariant {
		MODE_DEFAULT,
	};

	enum Specializations : uint64_t {
		MODE_3D = 1,
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
			"sort_direction",
			"frame_remainder",
			"align_up",
			"align_mode",
			"inv_emission_transform",
			"align_channel_filter",
			"align_axis"
		};
		static const char *_variant_defines[] = {
			"",
		};
		static TexUnitPair *_texunit_pairs = nullptr;
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization _spec_pairs[] = {
			{ "MODE_3D", false },
		};
		static const Feedback _feedbacks[] = {
			{ "out_xform_1", 0 },
			{ "out_xform_2", 0 },
			{ "out_xform_3", 1 },
			{ "instance_color_custom_data", 0 },
		};
		static const uint8_t _code_compressed[] = {
			120, 218, 205, 90, 91, 111, 219, 56, 22, 158, 87, 251, 87, 112, 167, 192, 66, 78, 28, 71, 23, 39, 241, 140,
			235, 2, 110, 227, 180, 6, 60, 201, 160, 78, 103, 146, 46, 6, 130, 44, 83, 54, 167, 178, 104, 72, 242, 117,
			167, 255, 125, 15, 73, 221, 40, 81, 73, 155, 151, 174, 31, 82, 154, 231, 194, 195, 239, 92, 200, 67, 183,
			121, 126, 142, 222, 209, 213, 218, 137, 201, 140, 248, 36, 62, 160, 16, 7, 206, 10, 71, 29, 116, 191, 196,
			17, 70, 78, 136, 17, 222, 175, 105, 132, 231, 104, 71, 226, 37, 138, 151, 24, 253, 188, 160, 115, 26, 219,
			63, 163, 117, 136, 61, 178, 111, 130, 146, 152, 162, 29, 13, 191, 0, 63, 221, 4, 115, 20, 239, 40, 154,
			147, 40, 38, 129, 27, 163, 225, 28, 148, 82, 52, 219, 44, 162, 95, 25, 175, 209, 65, 83, 186, 194, 233,
			252, 28, 111, 137, 139, 163, 100, 25, 52, 154, 90, 134, 142, 188, 13, 72, 18, 26, 68, 136, 4, 108, 74, 215,
			81, 180, 116, 230, 56, 140, 58, 76, 5, 124, 198, 65, 140, 195, 192, 241, 253, 67, 27, 237, 48, 90, 109,
			162, 24, 109, 64, 94, 97, 96, 27, 214, 230, 196, 48, 85, 146, 232, 216, 17, 223, 71, 51, 16, 118, 214, 107,
			216, 160, 179, 137, 233, 10, 160, 112, 153, 86, 190, 142, 217, 73, 173, 180, 30, 30, 50, 75, 151, 206, 22,
			163, 53, 165, 33, 34, 171, 181, 143, 87, 56, 136, 29, 97, 44, 245, 248, 250, 20, 254, 132, 104, 237, 184,
			95, 72, 176, 72, 214, 202, 118, 212, 70, 17, 101, 22, 255, 157, 90, 76, 55, 33, 162, 187, 128, 73, 2, 218,
			128, 228, 23, 140, 215, 136, 196, 40, 226, 234, 59, 205, 230, 43, 226, 205, 177, 135, 62, 77, 71, 246, 135,
			225, 228, 198, 188, 153, 220, 13, 239, 153, 222, 27, 159, 194, 202, 193, 2, 172, 33, 65, 204, 87, 60, 223,
			4, 236, 159, 2, 130, 204, 135, 107, 39, 140, 83, 235, 222, 79, 166, 19, 192, 20, 113, 80, 215, 216, 37,
			30, 236, 152, 177, 50, 107, 230, 104, 118, 0, 235, 102, 200, 1, 55, 174, 40, 68, 5, 230, 72, 140, 99, 196,
			64, 114, 194, 136, 89, 8, 152, 69, 142, 199, 141, 77, 220, 22, 243, 112, 1, 29, 66, 70, 64, 190, 91, 226,
			0, 133, 155, 32, 96, 38, 198, 75, 136, 141, 197, 18, 13, 111, 223, 79, 70, 240, 141, 68, 146, 198, 16, 59,
			95, 58, 205, 13, 219, 134, 199, 118, 101, 46, 29, 223, 211, 196, 247, 22, 250, 111, 179, 193, 135, 24, 13,
			144, 135, 254, 141, 216, 23, 77, 223, 95, 121, 61, 157, 125, 90, 253, 102, 131, 120, 72, 195, 232, 245,
			32, 165, 89, 130, 164, 183, 184, 116, 35, 196, 241, 38, 12, 18, 34, 227, 255, 138, 176, 15, 38, 23, 104,
			154, 230, 161, 55, 111, 4, 139, 113, 9, 114, 217, 58, 61, 161, 231, 31, 224, 109, 52, 52, 13, 214, 57, 83,
			44, 147, 201, 90, 69, 217, 43, 87, 146, 245, 106, 216, 116, 203, 243, 90, 220, 174, 230, 215, 166, 192,
			129, 33, 96, 114, 48, 4, 14, 203, 28, 135, 165, 205, 144, 88, 150, 86, 1, 233, 108, 43, 203, 138, 245, 175,
			95, 23, 182, 246, 143, 24, 107, 76, 81, 102, 16, 227, 250, 87, 10, 32, 140, 79, 64, 15, 231, 56, 77, 85,
			25, 110, 73, 151, 197, 117, 73, 203, 137, 157, 72, 44, 96, 89, 186, 41, 145, 154, 44, 68, 63, 176, 237,
			237, 141, 75, 109, 139, 93, 19, 109, 249, 230, 18, 243, 11, 17, 192, 135, 111, 73, 28, 221, 211, 79, 76,
			221, 182, 179, 231, 75, 62, 201, 114, 144, 183, 203, 87, 231, 171, 136, 213, 69, 138, 100, 235, 115, 187,
			164, 245, 25, 47, 159, 22, 90, 121, 154, 105, 5, 119, 108, 243, 221, 122, 30, 219, 109, 171, 205, 220, 251,
			164, 68, 49, 178, 212, 128, 124, 10, 104, 184, 42, 35, 178, 225, 227, 205, 22, 220, 205, 135, 26, 175, 176,
			154, 235, 59, 171, 181, 182, 109, 11, 83, 245, 142, 222, 74, 134, 70, 71, 120, 238, 242, 226, 194, 186,
			96, 227, 60, 40, 54, 128, 29, 115, 60, 224, 243, 60, 58, 185, 49, 220, 202, 117, 5, 30, 177, 175, 117, 25,
			137, 54, 74, 9, 210, 134, 193, 34, 48, 18, 62, 198, 133, 121, 241, 139, 110, 26, 125, 196, 143, 2, 29, 157,
			167, 166, 34, 186, 142, 201, 138, 28, 121, 45, 82, 192, 51, 125, 49, 60, 103, 70, 21, 31, 203, 188, 186,
			188, 130, 49, 196, 118, 58, 124, 33, 82, 83, 21, 82, 194, 68, 176, 234, 5, 88, 229, 118, 136, 109, 64, 240,
			156, 229, 246, 158, 100, 46, 135, 143, 165, 95, 24, 189, 11, 163, 85, 183, 81, 110, 241, 43, 56, 60, 72,
			128, 81, 49, 232, 21, 121, 152, 241, 201, 233, 161, 204, 25, 73, 103, 22, 42, 170, 88, 46, 105, 45, 243,
			150, 102, 37, 189, 83, 133, 222, 105, 141, 222, 169, 82, 111, 206, 221, 124, 133, 131, 57, 28, 17, 16, 116,
			165, 99, 148, 157, 110, 67, 127, 231, 28, 34, 249, 44, 115, 34, 54, 56, 240, 227, 179, 124, 41, 97, 135,
			99, 64, 225, 72, 220, 58, 196, 119, 102, 62, 206, 175, 41, 112, 43, 224, 7, 172, 101, 233, 29, 117, 134,
			119, 247, 61, 22, 193, 221, 66, 4, 119, 243, 8, 238, 42, 34, 184, 155, 39, 120, 55, 11, 96, 243, 66, 157,
			222, 154, 20, 181, 61, 81, 159, 97, 238, 88, 62, 0, 216, 228, 46, 155, 52, 187, 173, 44, 190, 187, 85, 231,
			48, 163, 149, 133, 160, 171, 10, 238, 60, 180, 11, 177, 221, 43, 30, 119, 53, 60, 242, 177, 171, 206, 17,
			102, 105, 90, 79, 172, 95, 76, 227, 226, 178, 119, 105, 22, 202, 9, 7, 166, 174, 126, 188, 4, 252, 60, 171,
			114, 244, 13, 51, 41, 30, 98, 240, 116, 233, 232, 181, 196, 140, 228, 2, 49, 37, 57, 64, 141, 255, 84, 129,
			191, 216, 130, 40, 47, 63, 200, 3, 202, 42, 37, 48, 226, 144, 36, 149, 138, 199, 174, 126, 213, 187, 234,
			66, 233, 191, 234, 182, 234, 48, 173, 84, 170, 52, 236, 20, 233, 163, 170, 41, 57, 167, 60, 89, 173, 40,
			178, 206, 169, 90, 231, 84, 165, 51, 227, 101, 53, 227, 119, 184, 82, 19, 215, 199, 215, 78, 236, 52, 125,
			231, 64, 55, 177, 230, 211, 228, 38, 61, 64, 16, 28, 80, 19, 150, 100, 177, 92, 243, 93, 34, 151, 250, 52,
			236, 43, 56, 141, 50, 231, 22, 3, 21, 154, 49, 219, 243, 157, 69, 164, 18, 49, 43, 202, 161, 153, 160, 43,
			21, 171, 85, 102, 221, 123, 176, 9, 219, 80, 241, 118, 213, 188, 102, 63, 237, 64, 126, 187, 187, 30, 217,
			214, 181, 66, 244, 66, 45, 106, 245, 147, 194, 11, 144, 157, 176, 64, 9, 22, 103, 140, 224, 196, 172, 87,
			56, 57, 111, 130, 154, 162, 20, 124, 181, 83, 3, 33, 163, 99, 111, 246, 107, 61, 139, 153, 177, 148, 204,
			171, 149, 176, 82, 137, 148, 51, 49, 14, 128, 142, 81, 46, 37, 170, 2, 9, 162, 216, 9, 92, 108, 115, 207,
			217, 2, 98, 123, 14, 238, 206, 214, 109, 110, 2, 194, 20, 35, 159, 238, 248, 98, 22, 52, 119, 97, 108, 207,
			73, 136, 249, 81, 209, 207, 56, 132, 102, 158, 73, 200, 11, 161, 199, 182, 67, 188, 114, 72, 0, 237, 104,
			191, 89, 226, 226, 138, 28, 159, 44, 2, 123, 179, 46, 171, 224, 85, 64, 16, 87, 116, 142, 43, 194, 128,
			45, 179, 125, 107, 227, 21, 137, 34, 176, 193, 142, 67, 39, 136, 24, 71, 129, 183, 160, 197, 93, 58, 65,
			128, 125, 219, 35, 126, 204, 140, 81, 176, 56, 123, 2, 113, 152, 165, 200, 112, 50, 126, 127, 107, 95, 143,
			167, 195, 183, 147, 209, 117, 218, 47, 148, 200, 111, 199, 147, 201, 219, 187, 225, 199, 132, 110, 148,
			233, 143, 246, 253, 157, 253, 199, 104, 114, 247, 110, 124, 255, 152, 212, 149, 50, 207, 231, 92, 139, 138,
			223, 42, 243, 3, 113, 56, 41, 175, 220, 109, 229, 150, 191, 251, 48, 188, 189, 29, 77, 236, 155, 241, 228,
			126, 244, 209, 190, 189, 187, 29, 85, 204, 47, 241, 60, 84, 236, 47, 49, 84, 141, 47, 49, 124, 174, 88,
			91, 98, 248, 179, 106, 168, 216, 207, 240, 97, 60, 77, 13, 168, 0, 204, 137, 143, 53, 232, 114, 226, 231,
			204, 178, 140, 250, 251, 240, 227, 253, 248, 221, 100, 100, 223, 76, 134, 239, 237, 225, 187, 251, 241,
			31, 163, 76, 69, 198, 117, 51, 185, 183, 127, 27, 62, 36, 133, 223, 234, 116, 117, 179, 103, 90, 221, 203,
			75, 124, 106, 245, 128, 111, 75, 201, 28, 177, 232, 213, 248, 105, 4, 213, 112, 138, 99, 20, 185, 142, 207,
			223, 4, 142, 56, 164, 252, 142, 196, 35, 15, 114, 139, 207, 158, 141, 111, 111, 216, 219, 199, 58, 41, 156,
			217, 243, 11, 4, 43, 137, 8, 220, 162, 184, 38, 188, 197, 208, 0, 194, 53, 10, 2, 25, 135, 196, 241, 217,
			61, 12, 146, 6, 226, 144, 194, 85, 44, 164, 226, 177, 229, 92, 172, 166, 145, 14, 238, 160, 25, 104, 154,
			81, 39, 156, 71, 173, 78, 179, 193, 51, 32, 230, 25, 15, 149, 137, 125, 211, 202, 151, 40, 245, 240, 44,
			217, 119, 27, 169, 70, 122, 114, 221, 98, 15, 13, 51, 74, 253, 106, 223, 41, 213, 237, 206, 142, 157, 163,
			42, 188, 249, 139, 68, 169, 100, 53, 26, 153, 193, 28, 52, 118, 17, 213, 184, 233, 73, 57, 108, 167, 197,
			56, 29, 88, 185, 253, 220, 182, 228, 15, 63, 76, 91, 172, 236, 250, 17, 254, 46, 181, 37, 109, 70, 50, 106,
			61, 183, 142, 40, 239, 13, 142, 75, 94, 151, 208, 96, 80, 170, 19, 226, 29, 134, 185, 24, 174, 206, 75,
			246, 50, 214, 72, 31, 97, 234, 68, 179, 76, 78, 100, 69, 249, 132, 67, 196, 103, 207, 31, 122, 167, 207,
			38, 115, 97, 185, 146, 49, 53, 138, 124, 79, 84, 177, 40, 177, 16, 59, 193, 124, 17, 36, 150, 198, 78, 119,
			80, 116, 196, 154, 27, 210, 40, 210, 210, 10, 220, 46, 21, 117, 118, 37, 170, 165, 113, 147, 26, 169, 94,
			241, 239, 137, 208, 47, 92, 145, 112, 136, 47, 255, 209, 255, 234, 236, 15, 199, 148, 19, 190, 74, 84, 67,
			166, 26, 50, 213, 148, 169, 166, 160, 22, 222, 181, 190, 11, 155, 135, 20, 152, 70, 138, 175, 56, 241, 58,
			251, 126, 147, 207, 87, 124, 245, 172, 202, 199, 58, 149, 135, 23, 171, 252, 92, 167, 242, 248, 98, 149,
			127, 214, 169, 220, 9, 180, 191, 10, 197, 226, 80, 134, 131, 16, 24, 242, 72, 81, 122, 95, 132, 41, 99,
			140, 160, 68, 114, 173, 18, 197, 101, 107, 208, 72, 65, 161, 140, 196, 218, 152, 51, 228, 246, 243, 48,
			229, 69, 15, 207, 211, 64, 21, 214, 54, 128, 249, 132, 91, 4, 29, 71, 54, 56, 69, 110, 27, 41, 40, 7, 80,
			201, 7, 71, 152, 137, 138, 44, 199, 162, 112, 194, 203, 88, 234, 87, 57, 164, 140, 21, 93, 135, 34, 139,
			171, 164, 28, 83, 67, 246, 234, 85, 10, 230, 156, 21, 205, 81, 235, 58, 45, 234, 82, 109, 138, 177, 184,
			9, 198, 220, 133, 1, 222, 65, 222, 2, 148, 41, 168, 39, 133, 171, 214, 183, 21, 6, 161, 66, 85, 22, 106,
			40, 253, 66, 8, 249, 56, 16, 125, 91, 230, 71, 152, 89, 196, 75, 77, 170, 8, 173, 182, 146, 104, 60, 69,
			20, 245, 160, 245, 76, 129, 129, 253, 130, 24, 203, 234, 167, 10, 77, 194, 117, 120, 186, 224, 36, 92, 71,
			81, 120, 158, 175, 231, 210, 29, 46, 73, 59, 14, 138, 104, 101, 165, 227, 19, 86, 234, 55, 165, 100, 210,
			202, 64, 177, 254, 187, 140, 79, 117, 206, 252, 11, 14, 220, 115, 100, 117, 244, 236, 184, 72, 24, 182,
			45, 244, 134, 31, 113, 73, 1, 40, 131, 145, 251, 125, 219, 170, 214, 214, 122, 110, 217, 89, 9, 56, 77,
			133, 79, 202, 129, 37, 9, 182, 145, 202, 175, 101, 87, 240, 64, 146, 143, 101, 150, 11, 253, 234, 114, 39,
			3, 121, 218, 144, 167, 159, 113, 93, 237, 85, 188, 232, 198, 72, 237, 71, 72, 100, 57, 33, 192, 66, 232,
			170, 75, 197, 179, 173, 144, 108, 177, 86, 43, 114, 67, 140, 131, 140, 218, 44, 121, 49, 2, 55, 14, 6, 69,
			63, 114, 51, 164, 164, 22, 240, 243, 249, 66, 237, 222, 38, 137, 249, 156, 91, 162, 109, 53, 215, 69, 232,
			203, 225, 168, 64, 119, 192, 48, 57, 169, 70, 169, 210, 151, 21, 144, 42, 129, 252, 13, 142, 42, 245, 64,
			9, 38, 57, 183, 56, 194, 6, 82, 135, 145, 2, 247, 67, 11, 84, 37, 127, 244, 66, 254, 60, 145, 109, 137,
			143, 74, 177, 36, 235, 104, 169, 235, 152, 148, 117, 186, 156, 117, 89, 246, 42, 140, 133, 156, 169, 173,
			161, 9, 77, 89, 57, 19, 218, 177, 88, 76, 158, 244, 204, 227, 143, 244, 204, 183, 85, 182, 239, 45, 106,
			229, 68, 250, 127, 244, 76, 51, 169, 24, 9, 143, 37, 120, 78, 149, 181, 237, 68, 241, 156, 3, 205, 93, 32,
			119, 119, 236, 39, 244, 0, 45, 124, 58, 131, 107, 5, 75, 216, 54, 154, 133, 236, 103, 113, 243, 58, 107,
			136, 249, 15, 225, 226, 226, 225, 82, 26, 206, 73, 0, 247, 147, 72, 8, 167, 191, 70, 164, 61, 243, 60, 116,
			118, 65, 254, 95, 50, 2, 86, 2, 160, 185, 35, 188, 112, 0, 51, 13, 201, 130, 4, 157, 98, 3, 168, 126, 19,
			2, 251, 5, 71, 214, 202, 177, 237, 43, 186, 198, 172, 123, 129, 14, 184, 246, 101, 12, 46, 98, 3, 233, 119,
			38, 141, 179, 0, 80, 188, 115, 174, 151, 59, 168, 229, 142, 187, 103, 228, 142, 21, 185, 164, 105, 121,
			110, 193, 93, 141, 160, 88, 177, 240, 14, 201, 64, 72, 67, 76, 162, 152, 57, 133, 53, 102, 229, 134, 190,
			240, 234, 152, 51, 178, 30, 45, 129, 249, 171, 226, 73, 212, 243, 216, 155, 232, 79, 165, 247, 149, 175,
			53, 111, 167, 63, 253, 15, 167, 12, 17, 221
		};
		const CharString _code = _decompress_code(_code_compressed, 2538, 9151);

		_setup(_code.get_data(), _code.get_data() + 9111, "ParticlesCopyShaderGLES3",
				7, _uniform_strings, 0, _ubo_pairs,
				4, _feedbacks, 0, _texunit_pairs,
				1, _spec_pairs, 1, _variant_defines);
	}
};
