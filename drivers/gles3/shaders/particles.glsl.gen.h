/**************************************************************************/
/*  particles.glsl.gen.h                                                  */
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

class ParticlesShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		LIFETIME,
		CLEAR,
		TOTAL_PARTICLES,
		USE_FRACTIONAL_DELTA,
	};

	enum ShaderVariant {
		MODE_DEFAULT,
	};

	enum Specializations : uint64_t {
		MODE_3D = 1,
		USERDATA1_USED = 2,
		USERDATA2_USED = 4,
		USERDATA3_USED = 8,
		USERDATA4_USED = 16,
		USERDATA5_USED = 32,
		USERDATA6_USED = 64,
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
			"lifetime",
			"clear",
			"total_particles",
			"use_fractional_delta"
		};
		static const char *_variant_defines[] = {
			"",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "global_shader_parameters_texture", -2 },
			{ "height_field_texture", 0 },
		};
		static UBOPair _ubo_pairs[] = {
			{ "MaterialUniforms", 1 },
			{ "FrameData", 0 },
		};
		static Specialization _spec_pairs[] = {
			{ "MODE_3D", false },
			{ "USERDATA1_USED", false },
			{ "USERDATA2_USED", false },
			{ "USERDATA3_USED", false },
			{ "USERDATA4_USED", false },
			{ "USERDATA5_USED", false },
			{ "USERDATA6_USED", false },
		};
		static const Feedback _feedbacks[] = {
			{ "out_color", 0 },
			{ "out_velocity_flags", 0 },
			{ "out_custom", 0 },
			{ "out_xform_1", 0 },
			{ "out_xform_2", 0 },
			{ "out_xform_3", 1 },
			{ "out_userdata1", 2 },
			{ "out_userdata2", 4 },
			{ "out_userdata3", 8 },
			{ "out_userdata4", 16 },
			{ "out_userdata5", 32 },
			{ "out_userdata6", 64 },
		};
		static const uint8_t _code_compressed[] = {
			120, 218, 205, 91, 109, 115, 218, 72, 18, 222, 175, 240, 43, 102, 43, 117, 41, 225, 96, 12, 2, 187, 118,
			67, 156, 45, 98, 112, 76, 157, 19, 167, 12, 217, 203, 214, 150, 79, 37, 35, 97, 116, 39, 36, 74, 18, 54,
			120, 227, 251, 237, 215, 61, 239, 163, 23, 112, 118, 183, 238, 54, 31, 18, 52, 234, 238, 233, 233, 233,
			233, 126, 186, 71, 169, 191, 240, 252, 121, 16, 249, 100, 50, 60, 119, 62, 12, 190, 56, 151, 163, 143, 239,
			167, 23, 164, 115, 210, 253, 161, 215, 106, 215, 235, 235, 40, 152, 199, 201, 146, 44, 130, 187, 197, 138,
			164, 238, 114, 21, 250, 137, 61, 36, 119, 97, 124, 235, 134, 78, 186, 112, 61, 63, 113, 86, 110, 226, 46,
			253, 204, 79, 82, 39, 243, 55, 217, 58, 241, 251, 228, 232, 8, 126, 2, 123, 246, 250, 208, 174, 215, 197,
			60, 239, 47, 175, 222, 13, 46, 157, 201, 197, 96, 56, 186, 118, 62, 127, 28, 159, 95, 93, 127, 112, 166,
			163, 47, 211, 207, 215, 35, 231, 31, 227, 225, 244, 2, 244, 152, 252, 157, 88, 86, 135, 188, 121, 243, 44,
			250, 201, 197, 248, 124, 218, 32, 135, 164, 211, 144, 243, 152, 250, 241, 85, 164, 214, 210, 9, 34, 207,
			223, 52, 8, 232, 230, 135, 231, 126, 54, 91, 88, 251, 150, 210, 36, 193, 189, 63, 179, 173, 32, 202, 20,
			255, 203, 103, 175, 4, 216, 117, 198, 183, 111, 191, 97, 77, 77, 210, 110, 212, 235, 71, 71, 100, 186, 8,
			82, 18, 249, 190, 151, 146, 44, 38, 183, 62, 137, 215, 89, 26, 120, 62, 153, 133, 110, 116, 119, 136, 139,
			115, 51, 146, 198, 36, 91, 248, 100, 125, 27, 147, 89, 188, 92, 250, 81, 70, 128, 45, 136, 232, 104, 2,
			59, 152, 145, 85, 232, 206, 252, 250, 139, 96, 14, 118, 34, 31, 6, 211, 209, 245, 24, 84, 225, 58, 76, 156,
			207, 147, 209, 176, 30, 186, 91, 16, 111, 165, 153, 215, 233, 181, 27, 68, 184, 192, 7, 23, 172, 18, 184,
			225, 103, 110, 204, 223, 96, 139, 97, 170, 215, 29, 216, 221, 130, 164, 122, 253, 169, 95, 127, 225, 71,
			94, 48, 135, 5, 28, 152, 122, 198, 17, 57, 56, 82, 62, 129, 126, 55, 152, 78, 175, 7, 103, 211, 171, 235,
			9, 233, 106, 238, 34, 135, 157, 233, 47, 159, 70, 206, 228, 211, 197, 232, 122, 68, 214, 104, 209, 118,
			163, 138, 234, 221, 213, 23, 70, 210, 169, 36, 249, 121, 68, 127, 159, 143, 71, 151, 67, 70, 107, 131, 161,
			211, 44, 89, 207, 50, 50, 200, 178, 196, 157, 101, 113, 66, 126, 171, 215, 64, 223, 30, 129, 231, 40, 69,
			229, 251, 245, 26, 248, 66, 143, 128, 103, 128, 117, 83, 244, 114, 50, 98, 191, 9, 208, 39, 174, 23, 172,
			211, 22, 121, 56, 156, 45, 220, 40, 242, 67, 180, 255, 202, 245, 188, 32, 186, 107, 213, 235, 53, 156, 137,
			100, 219, 149, 15, 114, 230, 97, 140, 91, 150, 37, 126, 116, 151, 45, 228, 128, 155, 129, 180, 181, 155,
			5, 113, 36, 199, 188, 32, 241, 103, 56, 226, 134, 65, 182, 237, 163, 105, 13, 227, 157, 93, 93, 94, 142,
			193, 151, 76, 219, 137, 209, 157, 166, 51, 137, 202, 44, 151, 19, 51, 60, 151, 246, 42, 167, 184, 24, 141,
			223, 95, 76, 117, 211, 118, 171, 72, 237, 161, 146, 215, 83, 246, 63, 139, 195, 16, 124, 251, 127, 98, 254,
			153, 27, 170, 39, 32, 109, 235, 15, 29, 102, 234, 138, 243, 112, 142, 129, 98, 232, 102, 46, 17, 39, 161,
			93, 175, 221, 198, 113, 72, 252, 101, 144, 101, 48, 103, 159, 79, 57, 219, 206, 180, 89, 210, 109, 154,
			249, 75, 103, 181, 112, 83, 109, 234, 196, 191, 119, 204, 55, 226, 149, 191, 89, 133, 113, 10, 49, 40, 242,
			211, 84, 50, 128, 73, 188, 120, 105, 12, 101, 193, 82, 9, 244, 252, 48, 115, 149, 16, 8, 107, 89, 0, 90,
			56, 105, 240, 168, 136, 220, 101, 188, 142, 50, 39, 65, 119, 203, 45, 92, 61, 216, 125, 97, 58, 54, 167,
			147, 66, 28, 18, 75, 115, 197, 89, 113, 102, 40, 74, 174, 152, 111, 161, 57, 58, 71, 139, 161, 52, 186,
			171, 96, 165, 52, 5, 167, 118, 180, 237, 165, 251, 219, 101, 6, 4, 238, 123, 63, 140, 103, 212, 229, 185,
			58, 32, 197, 79, 86, 78, 22, 59, 16, 90, 144, 92, 157, 85, 169, 73, 250, 171, 25, 80, 110, 128, 91, 186,
			148, 80, 140, 17, 201, 131, 115, 99, 30, 170, 79, 131, 235, 233, 248, 236, 114, 228, 156, 95, 14, 222, 59,
			32, 102, 252, 243, 168, 112, 48, 76, 162, 201, 20, 30, 71, 195, 194, 225, 48, 169, 64, 167, 241, 165, 160,
			234, 149, 81, 93, 15, 62, 140, 88, 6, 100, 71, 117, 115, 14, 127, 42, 9, 105, 154, 224, 154, 157, 176, 84,
			241, 137, 239, 52, 122, 166, 112, 93, 176, 34, 141, 40, 228, 20, 18, 10, 38, 4, 150, 206, 233, 89, 2, 139,
			196, 73, 191, 132, 178, 147, 167, 20, 187, 225, 204, 67, 247, 46, 45, 99, 177, 11, 194, 215, 105, 22, 47,
			203, 72, 187, 121, 210, 13, 122, 128, 211, 41, 163, 237, 149, 211, 130, 99, 138, 68, 118, 53, 28, 57, 221,
			97, 9, 235, 113, 57, 107, 87, 38, 39, 46, 1, 18, 223, 245, 112, 48, 29, 116, 88, 10, 52, 121, 214, 169,
			159, 120, 96, 206, 78, 21, 151, 189, 139, 203, 174, 226, 234, 238, 226, 170, 212, 176, 183, 139, 171, 87,
			197, 117, 188, 139, 235, 184, 138, 235, 100, 23, 215, 137, 74, 240, 96, 116, 157, 2, 30, 29, 230, 86, 136,
			2, 231, 183, 175, 203, 8, 114, 222, 180, 131, 146, 59, 209, 14, 10, 225, 59, 123, 73, 108, 73, 146, 243,
			156, 74, 142, 174, 224, 16, 148, 59, 253, 166, 68, 140, 114, 30, 46, 40, 199, 178, 211, 163, 118, 200, 179,
			243, 242, 236, 93, 242, 186, 123, 229, 117, 243, 242, 186, 187, 228, 245, 246, 202, 235, 229, 229, 245,
			118, 201, 59, 222, 43, 239, 56, 47, 239, 120, 151, 188, 147, 189, 242, 78, 242, 242, 78, 12, 121, 178, 242,
			81, 53, 207, 194, 71, 8, 237, 204, 3, 63, 244, 202, 234, 28, 173, 92, 98, 217, 42, 12, 230, 62, 75, 202,
			98, 156, 194, 3, 8, 206, 110, 162, 198, 24, 42, 137, 51, 168, 65, 68, 150, 78, 115, 28, 160, 179, 51, 199,
			236, 70, 49, 160, 35, 114, 59, 229, 4, 176, 176, 176, 232, 47, 168, 46, 0, 49, 109, 32, 234, 89, 214, 6,
			11, 13, 145, 23, 26, 228, 159, 248, 242, 64, 164, 148, 222, 177, 247, 227, 188, 123, 219, 232, 255, 46,
			234, 34, 49, 188, 73, 124, 176, 70, 132, 63, 159, 234, 117, 154, 195, 83, 119, 238, 59, 17, 2, 254, 16,
			32, 135, 69, 199, 36, 144, 165, 154, 206, 226, 40, 205, 184, 169, 70, 159, 38, 227, 203, 171, 143, 152,
			160, 90, 237, 54, 226, 143, 96, 78, 172, 144, 98, 99, 75, 99, 123, 35, 40, 169, 4, 49, 45, 10, 183, 128,
			17, 117, 124, 146, 202, 168, 201, 149, 0, 170, 31, 100, 201, 143, 128, 97, 124, 143, 60, 44, 0, 85, 221,
			3, 46, 128, 237, 77, 189, 57, 225, 187, 138, 184, 49, 241, 93, 15, 16, 75, 188, 36, 46, 212, 80, 25, 131,
			146, 179, 127, 3, 19, 132, 195, 235, 247, 239, 6, 63, 180, 234, 76, 119, 116, 45, 132, 36, 244, 201, 162,
			142, 182, 130, 240, 54, 163, 42, 114, 93, 188, 56, 179, 232, 96, 147, 146, 91, 157, 86, 155, 28, 17, 203,
			62, 62, 134, 31, 7, 196, 248, 23, 202, 190, 178, 215, 114, 152, 62, 209, 135, 6, 110, 147, 13, 131, 135,
			248, 68, 215, 246, 130, 85, 151, 80, 128, 221, 199, 129, 71, 150, 110, 16, 89, 84, 17, 234, 72, 238, 106,
			21, 66, 196, 141, 147, 153, 159, 130, 173, 1, 111, 35, 24, 212, 94, 137, 168, 172, 94, 114, 87, 134, 148,
			202, 29, 15, 94, 229, 192, 229, 210, 77, 81, 26, 85, 129, 75, 75, 252, 52, 3, 103, 134, 209, 185, 27, 50,
			52, 171, 143, 59, 43, 64, 180, 60, 69, 115, 2, 243, 125, 2, 231, 1, 223, 59, 20, 161, 87, 81, 105, 218,
			150, 190, 167, 73, 168, 242, 37, 77, 43, 186, 134, 20, 150, 210, 176, 15, 163, 248, 128, 219, 212, 144,
			232, 21, 243, 20, 58, 232, 26, 105, 209, 61, 233, 65, 102, 142, 40, 83, 30, 16, 136, 13, 70, 206, 154, 74,
			96, 226, 77, 91, 123, 99, 38, 193, 28, 197, 19, 241, 65, 177, 130, 120, 14, 216, 42, 5, 152, 32, 45, 167,
			129, 0, 100, 181, 26, 93, 231, 175, 237, 27, 24, 148, 208, 75, 140, 118, 212, 104, 17, 100, 9, 34, 91, 17,
			41, 176, 194, 95, 82, 247, 1, 84, 15, 219, 236, 91, 116, 132, 46, 89, 40, 73, 221, 230, 93, 144, 165, 211,
			248, 51, 6, 18, 83, 233, 214, 67, 163, 95, 145, 95, 217, 106, 100, 74, 5, 81, 207, 197, 102, 38, 167, 173,
			113, 238, 195, 103, 38, 103, 87, 227, 220, 135, 209, 76, 206, 158, 198, 185, 15, 167, 153, 156, 199, 26,
			231, 62, 172, 102, 114, 158, 104, 156, 10, 175, 65, 140, 172, 215, 142, 142, 168, 251, 18, 122, 24, 32,
			170, 161, 233, 9, 120, 117, 234, 103, 117, 190, 81, 47, 79, 201, 127, 74, 171, 28, 121, 156, 121, 57, 229,
			105, 103, 140, 6, 122, 58, 78, 139, 59, 22, 132, 153, 103, 203, 24, 205, 194, 134, 34, 242, 252, 85, 182,
			96, 177, 95, 214, 128, 170, 178, 164, 225, 202, 148, 128, 139, 39, 223, 179, 154, 200, 179, 134, 227, 201,
			224, 221, 37, 118, 117, 46, 175, 206, 198, 211, 95, 26, 252, 124, 162, 138, 22, 95, 74, 105, 77, 215, 96,
			135, 151, 249, 115, 247, 166, 181, 217, 62, 146, 87, 167, 37, 240, 148, 190, 57, 208, 163, 32, 205, 52,
			194, 158, 52, 62, 208, 6, 31, 218, 27, 61, 250, 46, 116, 126, 246, 193, 174, 155, 241, 176, 193, 147, 153,
			232, 10, 176, 57, 121, 21, 47, 194, 33, 150, 252, 226, 96, 88, 188, 85, 120, 196, 31, 115, 216, 0, 151,
			95, 163, 18, 85, 15, 128, 188, 69, 219, 49, 201, 76, 27, 44, 210, 241, 188, 243, 214, 3, 103, 48, 166, 123,
			123, 106, 244, 34, 56, 119, 141, 114, 30, 158, 138, 122, 151, 50, 63, 213, 197, 139, 3, 254, 162, 168, 148,
			160, 0, 3, 210, 5, 208, 17, 189, 89, 33, 215, 71, 33, 11, 210, 54, 200, 223, 152, 180, 147, 227, 227, 46,
			130, 137, 35, 66, 127, 161, 27, 212, 48, 187, 235, 234, 130, 92, 109, 193, 7, 66, 232, 1, 207, 138, 85,
			182, 170, 81, 111, 207, 201, 130, 85, 208, 20, 124, 104, 118, 87, 148, 105, 117, 195, 128, 113, 11, 237,
			25, 110, 44, 64, 18, 5, 155, 22, 104, 17, 58, 192, 33, 244, 176, 63, 43, 53, 163, 61, 14, 209, 155, 157,
			7, 73, 202, 219, 35, 248, 188, 37, 46, 96, 144, 85, 18, 67, 150, 6, 190, 122, 229, 246, 21, 167, 122, 249,
			50, 167, 208, 155, 210, 61, 86, 233, 153, 103, 121, 62, 67, 25, 208, 20, 60, 53, 19, 3, 152, 38, 58, 52,
			167, 69, 92, 162, 208, 111, 77, 120, 16, 221, 9, 158, 214, 112, 58, 38, 75, 247, 221, 231, 45, 243, 207,
			92, 6, 115, 131, 156, 171, 229, 140, 86, 92, 12, 93, 141, 90, 200, 95, 218, 230, 92, 95, 77, 79, 46, 94,
			164, 99, 17, 153, 200, 79, 196, 42, 109, 125, 125, 173, 104, 118, 125, 5, 12, 132, 1, 6, 111, 106, 202,
			58, 83, 112, 162, 95, 83, 188, 164, 31, 102, 133, 252, 164, 29, 42, 81, 95, 129, 162, 136, 79, 213, 59,
			1, 144, 138, 47, 4, 250, 17, 111, 158, 88, 10, 164, 41, 76, 118, 70, 113, 7, 238, 113, 210, 253, 105, 67,
			118, 68, 37, 115, 180, 94, 222, 250, 56, 57, 103, 132, 18, 169, 212, 32, 162, 172, 202, 199, 41, 112, 57,
			30, 52, 235, 250, 70, 225, 121, 206, 41, 136, 123, 247, 226, 12, 176, 24, 152, 150, 238, 3, 91, 11, 50,
			149, 80, 194, 38, 131, 77, 88, 125, 24, 48, 240, 10, 255, 190, 41, 244, 109, 73, 240, 234, 21, 247, 10,
			81, 169, 105, 241, 155, 245, 137, 251, 242, 109, 226, 135, 88, 203, 8, 252, 39, 82, 231, 161, 222, 132,
			13, 110, 90, 178, 177, 203, 9, 148, 0, 230, 214, 224, 10, 32, 66, 8, 59, 64, 200, 221, 181, 42, 68, 176,
			208, 76, 151, 153, 163, 216, 174, 96, 211, 78, 203, 175, 138, 196, 57, 130, 229, 192, 76, 185, 146, 148,
			79, 204, 82, 151, 104, 155, 3, 25, 175, 58, 165, 142, 152, 150, 204, 57, 249, 253, 67, 107, 163, 78, 177,
			7, 97, 172, 35, 195, 88, 13, 139, 91, 56, 82, 107, 253, 36, 214, 152, 25, 105, 109, 177, 65, 32, 195, 10,
			186, 67, 226, 241, 36, 171, 226, 201, 179, 150, 248, 238, 234, 203, 51, 215, 71, 105, 24, 170, 186, 77,
			185, 217, 225, 151, 90, 98, 245, 10, 183, 143, 5, 251, 160, 246, 92, 78, 107, 211, 52, 30, 183, 77, 49,
			67, 235, 177, 209, 248, 191, 90, 71, 191, 226, 227, 243, 210, 121, 150, 190, 23, 172, 151, 43, 34, 175,
			219, 248, 57, 208, 46, 222, 208, 58, 198, 20, 230, 165, 156, 166, 234, 42, 126, 176, 216, 67, 179, 92, 20,
			211, 189, 116, 123, 150, 193, 6, 27, 19, 205, 202, 67, 99, 211, 67, 147, 127, 111, 94, 6, 114, 35, 231,
			193, 242, 225, 41, 43, 202, 15, 248, 209, 133, 31, 168, 195, 65, 78, 150, 118, 251, 200, 114, 68, 201, 101,
			17, 174, 210, 188, 60, 210, 42, 15, 118, 131, 50, 25, 95, 125, 116, 38, 103, 131, 203, 17, 202, 48, 185,
			1, 105, 97, 239, 131, 98, 119, 126, 176, 68, 229, 73, 157, 171, 73, 140, 209, 78, 233, 40, 179, 68, 163,
			209, 20, 53, 64, 87, 253, 105, 208, 114, 128, 55, 237, 152, 183, 153, 183, 79, 232, 27, 157, 53, 70, 82,
			117, 249, 211, 86, 110, 83, 118, 37, 41, 209, 157, 61, 84, 85, 74, 157, 71, 47, 155, 176, 3, 164, 133, 62,
			17, 216, 122, 36, 139, 157, 212, 155, 59, 27, 86, 167, 107, 179, 201, 93, 109, 223, 20, 168, 183, 213, 212,
			29, 73, 109, 99, 131, 138, 159, 93, 250, 61, 2, 55, 107, 207, 130, 177, 38, 193, 227, 2, 246, 17, 243, 195,
			207, 93, 239, 169, 223, 72, 53, 112, 4, 95, 204, 18, 223, 143, 68, 19, 194, 80, 72, 11, 7, 77, 83, 85, 154,
			169, 149, 48, 155, 172, 239, 185, 146, 66, 221, 3, 83, 62, 200, 64, 124, 101, 12, 61, 62, 104, 209, 61,
			12, 173, 187, 196, 199, 143, 13, 166, 11, 55, 178, 152, 188, 38, 91, 51, 2, 69, 0, 21, 176, 151, 72, 6,
			137, 51, 45, 210, 208, 190, 88, 67, 132, 26, 177, 97, 54, 61, 173, 41, 76, 205, 4, 53, 77, 175, 230, 177,
			74, 183, 179, 93, 102, 104, 123, 159, 165, 237, 82, 83, 171, 0, 74, 133, 231, 206, 151, 23, 64, 178, 143,
			102, 190, 197, 103, 110, 74, 21, 68, 236, 86, 193, 215, 108, 54, 242, 126, 165, 85, 214, 154, 110, 242,
			173, 160, 77, 66, 243, 251, 30, 46, 21, 170, 151, 65, 24, 198, 15, 8, 253, 16, 38, 184, 36, 133, 216, 20,
			18, 127, 149, 6, 33, 132, 193, 44, 70, 51, 199, 15, 210, 84, 228, 95, 128, 164, 96, 120, 61, 91, 32, 143,
			116, 4, 164, 100, 103, 205, 77, 101, 79, 160, 206, 3, 253, 142, 30, 47, 134, 70, 140, 85, 5, 163, 232, 153,
			35, 215, 242, 21, 187, 132, 142, 106, 180, 151, 109, 139, 189, 101, 78, 253, 109, 54, 18, 110, 193, 103,
			106, 18, 238, 104, 135, 191, 195, 222, 140, 169, 32, 171, 249, 199, 181, 163, 73, 81, 24, 227, 15, 106,
			151, 147, 37, 226, 1, 238, 152, 108, 233, 168, 58, 165, 166, 157, 9, 113, 174, 95, 193, 22, 64, 90, 225,
			4, 165, 7, 70, 112, 201, 51, 81, 17, 229, 236, 27, 253, 20, 61, 151, 171, 123, 163, 180, 142, 248, 241,
			62, 164, 103, 221, 88, 139, 217, 134, 50, 111, 36, 172, 136, 111, 79, 63, 207, 32, 90, 82, 60, 15, 241,
			68, 94, 44, 99, 89, 33, 85, 138, 177, 115, 31, 65, 104, 16, 155, 97, 49, 166, 138, 129, 174, 112, 82, 54,
			32, 218, 107, 122, 127, 122, 47, 252, 86, 134, 170, 66, 223, 123, 225, 119, 185, 136, 198, 95, 40, 98, 232,
			25, 222, 0, 128, 101, 31, 60, 201, 152, 81, 128, 247, 2, 29, 131, 217, 44, 51, 32, 191, 50, 237, 40, 115,
			159, 116, 182, 170, 184, 84, 99, 251, 165, 29, 155, 154, 112, 163, 67, 113, 78, 106, 37, 158, 104, 22, 34,
			28, 14, 107, 120, 247, 25, 171, 213, 106, 129, 157, 64, 95, 204, 193, 174, 232, 238, 34, 145, 171, 131,
			187, 200, 32, 82, 11, 117, 163, 173, 145, 143, 185, 224, 102, 133, 145, 16, 166, 41, 131, 28, 29, 173, 98,
			60, 22, 226, 115, 197, 219, 120, 195, 69, 243, 62, 113, 24, 167, 80, 233, 34, 232, 15, 158, 35, 186, 175,
			51, 131, 217, 216, 242, 120, 92, 227, 194, 242, 166, 87, 251, 141, 123, 93, 146, 102, 248, 134, 82, 242,
			146, 77, 45, 217, 85, 181, 137, 187, 206, 12, 28, 41, 203, 216, 100, 28, 225, 54, 151, 43, 209, 60, 68,
			29, 126, 225, 3, 70, 144, 209, 204, 25, 68, 210, 154, 154, 61, 220, 77, 144, 58, 33, 69, 112, 85, 6, 196,
			18, 157, 217, 171, 47, 69, 98, 199, 49, 241, 241, 30, 153, 127, 91, 234, 66, 196, 73, 97, 187, 201, 131,
			187, 197, 33, 15, 63, 43, 13, 210, 159, 52, 99, 25, 232, 75, 204, 219, 218, 64, 53, 40, 31, 76, 71, 168,
			153, 247, 0, 29, 26, 219, 219, 210, 10, 122, 113, 87, 42, 122, 187, 213, 68, 111, 118, 137, 198, 156, 81,
			34, 186, 154, 154, 38, 25, 101, 247, 189, 71, 25, 243, 20, 23, 114, 32, 117, 226, 149, 73, 167, 129, 157,
			156, 82, 31, 251, 70, 151, 41, 186, 202, 239, 9, 11, 170, 150, 249, 70, 70, 253, 43, 78, 51, 176, 200, 40,
			225, 220, 198, 25, 107, 171, 201, 161, 190, 222, 180, 84, 36, 173, 45, 130, 188, 124, 21, 185, 43, 194,
			88, 121, 17, 141, 231, 197, 27, 179, 175, 32, 78, 145, 158, 82, 134, 163, 203, 233, 128, 93, 86, 147, 35,
			242, 67, 231, 71, 155, 221, 57, 201, 245, 173, 239, 31, 84, 149, 213, 45, 40, 2, 76, 149, 138, 192, 158,
			181, 91, 199, 224, 0, 240, 183, 144, 201, 102, 165, 253, 202, 61, 232, 236, 129, 53, 84, 30, 27, 173, 68,
			183, 14, 86, 75, 34, 15, 190, 149, 100, 91, 61, 198, 242, 112, 192, 4, 83, 185, 70, 144, 5, 122, 188, 41,
			101, 128, 71, 206, 211, 36, 91, 53, 235, 163, 241, 33, 1, 62, 84, 45, 178, 159, 147, 108, 23, 37, 131, 194,
			212, 202, 205, 103, 47, 89, 0, 92, 206, 6, 120, 172, 149, 252, 25, 202, 117, 203, 150, 253, 173, 74, 65,
			124, 160, 122, 229, 148, 18, 171, 252, 6, 229, 170, 17, 192, 44, 137, 211, 212, 162, 27, 197, 16, 108, 147,
			168, 135, 174, 132, 167, 198, 199, 24, 91, 185, 56, 189, 141, 247, 44, 231, 108, 180, 182, 253, 111, 9,
			116, 76, 27, 76, 159, 250, 88, 225, 140, 154, 129, 170, 174, 163, 53, 233, 174, 248, 252, 189, 0, 124, 6,
			114, 42, 169, 58, 170, 1, 124, 145, 64, 106, 173, 165, 209, 92, 236, 103, 144, 67, 164, 71, 93, 236, 65,
			254, 50, 90, 202, 199, 107, 71, 73, 36, 59, 147, 108, 50, 211, 28, 51, 181, 77, 59, 235, 142, 89, 163, 90,
			121, 142, 85, 242, 80, 80, 221, 227, 236, 234, 245, 139, 91, 129, 79, 215, 87, 103, 163, 201, 132, 209,
			86, 221, 228, 179, 155, 140, 254, 174, 139, 3, 202, 249, 245, 148, 84, 48, 162, 244, 29, 31, 123, 104, 223,
			101, 202, 66, 133, 246, 190, 180, 175, 49, 229, 11, 108, 115, 229, 63, 51, 209, 190, 193, 148, 116, 246,
			141, 250, 136, 161, 228, 150, 254, 129, 95, 191, 179, 79, 75, 206, 105, 81, 76, 223, 240, 239, 190, 242,
			255, 15, 101, 62, 199, 255, 136, 242, 93, 238, 83, 169, 167, 138, 255, 176, 242, 221, 127, 1, 150, 99, 132,
			83
		};
		const CharString _code = _decompress_code(_code_compressed, 3649, 13614);

		_setup(_code.get_data(), _code.get_data() + 13574, "ParticlesShaderGLES3",
				4, _uniform_strings, 2, _ubo_pairs,
				12, _feedbacks, 2, _texunit_pairs,
				7, _spec_pairs, 1, _variant_defines);
	}
};
