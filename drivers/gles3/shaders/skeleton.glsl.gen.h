/**************************************************************************/
/*  skeleton.glsl.gen.h                                                   */
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

class SkeletonShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		BLEND_WEIGHT,
		BLEND_SHAPE_COUNT,
		SKELETON_TRANSFORM_X,
		SKELETON_TRANSFORM_Y,
		SKELETON_TRANSFORM_OFFSET,
		INVERSE_TRANSFORM_X,
		INVERSE_TRANSFORM_Y,
		INVERSE_TRANSFORM_OFFSET,
	};

	enum ShaderVariant {
		MODE_BASE_PASS,
		MODE_BLEND_PASS,
	};

	enum Specializations : uint64_t {
		MODE_2D = 1,
		USE_BLEND_SHAPES = 2,
		USE_SKELETON = 4,
		USE_NORMAL = 8,
		USE_TANGENT = 16,
		FINAL_PASS = 32,
		USE_EIGHT_WEIGHTS = 64,
	};

	_FORCE_INLINE_ bool version_bind_shader(RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		return _version_bind_shader(p_version, p_variant, p_specialization);
	}

	_FORCE_INLINE_ int version_get_uniform(Uniforms p_uniform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		return _version_get_uniform(p_uniform, p_version, p_variant, p_specialization);
	}

	/* clang-format off */
#define TRY_GET_UNIFORM(var_name) int var_name = version_get_uniform(p_uniform, p_version, p_variant, p_specialization); if (var_name < 0) return
	/* clang-format on */

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, double p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int8_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int16_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int32_t p_value, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Color &p_color, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat col[4] = { p_color.r, p_color.g, p_color.b, p_color.a };
		glUniform4fv(uniform_location, 1, col);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector2 &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec2[2] = { float(p_vec2.x), float(p_vec2.y) };
		glUniform2fv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Size2i &p_vec2, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		GLint vec2[2] = { GLint(p_vec2.x), GLint(p_vec2.y) };
		glUniform2iv(uniform_location, 1, vec2);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector3 &p_vec3, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec3[3] = { float(p_vec3.x), float(p_vec3.y), float(p_vec3.z) };
		glUniform3fv(uniform_location, 1, vec3);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector4 &p_vec4, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec4[4] = { float(p_vec4.x), float(p_vec4.y), float(p_vec4.z), float(p_vec4.w) };
		glUniform4fv(uniform_location, 1, vec4);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform2f(uniform_location, p_a, p_b);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform3f(uniform_location, p_a, p_b, p_c);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, float p_d, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
		TRY_GET_UNIFORM(uniform_location);
		glUniform4f(uniform_location, p_a, p_b, p_c, p_d);
	}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform3D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
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

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform2D &p_transform, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
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

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Projection &p_matrix, RID p_version, ShaderVariant p_variant, uint64_t p_specialization = 1) {
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
			"blend_weight",
			"blend_shape_count",
			"skeleton_transform_x",
			"skeleton_transform_y",
			"skeleton_transform_offset",
			"inverse_transform_x",
			"inverse_transform_y",
			"inverse_transform_offset"
		};
		static const char *_variant_defines[] = {
			"",
			"#define MODE_BLEND_PASS",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "skeleton_texture", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization _spec_pairs[] = {
			{ "MODE_2D", true },
			{ "USE_BLEND_SHAPES", false },
			{ "USE_SKELETON", false },
			{ "USE_NORMAL", false },
			{ "USE_TANGENT", false },
			{ "FINAL_PASS", false },
			{ "USE_EIGHT_WEIGHTS", false },
		};
		static const Feedback _feedbacks[] = {
			{ "out_vertex", 0 },
			{ "out_normal", 8 },
			{ "out_tangent", 16 },
		};
		static const uint8_t _code_compressed[] = {
			120, 218, 205, 90, 235, 115, 219, 184, 17, 191, 175, 214, 95, 129, 94, 166, 29, 42, 150, 21, 137, 146, 108,
			95, 116, 206, 141, 211, 200, 73, 166, 142, 125, 19, 41, 109, 166, 55, 55, 26, 74, 2, 37, 212, 20, 169, 227,
			67, 15, 55, 249, 223, 187, 187, 32, 72, 144, 2, 101, 231, 49, 109, 253, 65, 162, 128, 125, 239, 98, 241,
			3, 232, 218, 179, 103, 236, 175, 193, 114, 229, 196, 98, 34, 60, 17, 239, 88, 200, 125, 103, 201, 163, 38,
			27, 45, 120, 196, 153, 19, 114, 198, 183, 171, 32, 226, 51, 182, 17, 241, 130, 197, 11, 206, 126, 156, 7,
			179, 32, 30, 255, 200, 86, 33, 119, 197, 182, 6, 66, 226, 128, 109, 130, 240, 14, 232, 131, 196, 159, 177,
			120, 19, 176, 153, 136, 98, 225, 79, 99, 118, 57, 3, 161, 1, 155, 36, 243, 232, 57, 210, 182, 155, 108,
			24, 44, 185, 26, 159, 241, 181, 152, 242, 40, 85, 195, 6, 195, 78, 187, 197, 220, 4, 56, 69, 224, 71, 76,
			248, 56, 212, 106, 177, 104, 225, 204, 120, 24, 53, 81, 4, 252, 189, 245, 99, 30, 250, 142, 231, 237, 26,
			108, 195, 217, 50, 137, 98, 150, 0, 191, 193, 192, 6, 232, 166, 201, 80, 9, 73, 101, 108, 132, 231, 177,
			9, 48, 59, 171, 21, 56, 232, 36, 113, 176, 132, 80, 76, 81, 42, 233, 177, 155, 202, 202, 206, 199, 143,
			153, 165, 11, 103, 205, 217, 42, 8, 66, 38, 150, 43, 143, 47, 185, 31, 59, 210, 216, 192, 37, 253, 1, 124,
			132, 108, 229, 76, 239, 132, 63, 79, 117, 101, 30, 53, 88, 20, 160, 197, 255, 82, 22, 7, 73, 200, 130, 141,
			143, 156, 16, 109, 136, 228, 29, 231, 43, 38, 98, 22, 145, 248, 102, 173, 246, 68, 184, 51, 238, 178, 15,
			195, 193, 248, 205, 229, 245, 149, 125, 117, 125, 123, 57, 66, 185, 87, 94, 0, 154, 253, 57, 88, 35, 252,
			152, 52, 62, 75, 124, 252, 210, 34, 136, 57, 92, 57, 97, 172, 172, 123, 125, 61, 188, 134, 152, 50, 10,
			234, 138, 79, 133, 11, 30, 35, 41, 90, 51, 99, 147, 29, 88, 55, 97, 14, 164, 113, 25, 64, 85, 112, 138,
			196, 219, 152, 97, 144, 156, 48, 66, 11, 33, 102, 145, 227, 146, 177, 105, 218, 98, 42, 23, 144, 33, 121,
			100, 200, 55, 11, 238, 179, 48, 241, 125, 52, 49, 94, 64, 109, 204, 23, 236, 242, 230, 245, 245, 0, 126,
			137, 168, 32, 49, 228, 206, 93, 179, 150, 160, 27, 46, 122, 101, 47, 28, 207, 181, 228, 239, 58, 251, 119,
			237, 136, 30, 57, 187, 96, 46, 251, 11, 195, 31, 86, 107, 123, 230, 158, 183, 240, 175, 222, 175, 29, 9,
			151, 89, 156, 253, 124, 161, 230, 58, 114, 170, 85, 39, 238, 163, 144, 199, 73, 232, 167, 147, 72, 255,
			153, 113, 15, 76, 214, 230, 44, 203, 101, 47, 94, 72, 146, 246, 41, 240, 101, 122, 206, 165, 156, 79, 64,
			123, 116, 100, 89, 160, 231, 196, 160, 38, 227, 237, 232, 188, 103, 211, 2, 175, 91, 65, 214, 234, 184,
			110, 157, 236, 170, 125, 174, 201, 56, 96, 4, 108, 10, 134, 140, 195, 34, 143, 195, 98, 140, 145, 88, 148,
			180, 0, 119, 230, 202, 98, 207, 250, 159, 127, 214, 92, 251, 36, 159, 45, 20, 148, 25, 132, 84, 127, 82,
			1, 132, 231, 167, 32, 135, 40, 142, 149, 168, 246, 180, 36, 171, 67, 178, 10, 234, 164, 39, 5, 18, 176,
			76, 57, 37, 151, 38, 150, 232, 27, 116, 111, 219, 62, 181, 214, 124, 106, 179, 53, 57, 151, 154, 175, 85,
			0, 61, 190, 20, 113, 52, 10, 62, 160, 184, 117, 115, 75, 42, 15, 146, 236, 138, 238, 146, 118, 210, 34,
			181, 203, 37, 146, 233, 39, 187, 10, 250, 145, 150, 134, 165, 84, 90, 102, 150, 150, 142, 117, 238, 173,
			235, 162, 183, 245, 6, 166, 247, 32, 135, 94, 89, 230, 128, 124, 240, 131, 112, 89, 142, 72, 66, 207, 201,
			26, 210, 77, 143, 22, 117, 88, 107, 234, 57, 203, 149, 181, 110, 72, 83, 91, 205, 86, 61, 125, 108, 55,
			101, 230, 78, 123, 189, 78, 15, 159, 243, 162, 72, 32, 118, 152, 120, 136, 207, 195, 209, 201, 141, 33,
			43, 87, 123, 225, 145, 126, 173, 202, 145, 104, 48, 53, 81, 112, 24, 44, 2, 35, 225, 175, 221, 179, 123,
			63, 181, 236, 118, 159, 209, 86, 208, 98, 207, 148, 169, 44, 88, 197, 98, 41, 238, 169, 23, 25, 194, 51,
			252, 234, 240, 156, 180, 247, 227, 211, 177, 207, 78, 207, 224, 25, 106, 91, 61, 126, 101, 164, 134, 166,
			72, 73, 19, 193, 170, 175, 136, 85, 110, 135, 116, 3, 138, 231, 36, 183, 247, 105, 150, 114, 248, 235, 180,
			122, 237, 243, 94, 187, 94, 229, 40, 89, 252, 4, 54, 15, 225, 115, 166, 23, 189, 97, 29, 102, 116, 197,
			229, 97, 92, 51, 5, 153, 89, 169, 152, 106, 185, 36, 181, 76, 91, 26, 45, 200, 29, 26, 228, 14, 43, 228,
			14, 141, 114, 115, 234, 218, 19, 238, 207, 96, 139, 128, 162, 43, 109, 163, 184, 187, 93, 122, 27, 103,
			23, 21, 247, 50, 39, 194, 135, 29, 109, 159, 101, 80, 130, 155, 163, 31, 192, 150, 184, 118, 132, 231, 76,
			60, 158, 195, 20, 64, 5, 180, 193, 118, 58, 173, 166, 121, 133, 119, 183, 231, 88, 193, 93, 173, 130, 187,
			121, 5, 119, 13, 21, 220, 205, 23, 120, 55, 43, 96, 187, 103, 94, 222, 86, 161, 106, 207, 101, 127, 134,
			177, 251, 242, 6, 128, 131, 155, 108, 208, 238, 214, 179, 250, 238, 238, 39, 7, 141, 54, 54, 130, 174, 169,
			184, 243, 210, 214, 106, 251, 92, 223, 238, 42, 104, 138, 219, 174, 121, 141, 160, 165, 170, 159, 116, 126,
			178, 219, 189, 211, 243, 83, 91, 107, 39, 20, 152, 170, 254, 241, 53, 193, 207, 87, 85, 30, 253, 182, 157,
			54, 15, 249, 112, 184, 117, 156, 215, 229, 72, 33, 5, 114, 168, 144, 0, 115, 252, 135, 134, 248, 75, 23,
			100, 123, 249, 31, 101, 192, 216, 165, 100, 140, 40, 36, 105, 167, 162, 218, 109, 157, 157, 159, 117, 161,
			245, 159, 117, 235, 85, 49, 221, 235, 84, 170, 236, 12, 203, 199, 212, 83, 114, 202, 226, 224, 126, 71,
			41, 202, 28, 154, 101, 14, 77, 50, 51, 90, 133, 200, 223, 221, 190, 26, 140, 237, 87, 25, 239, 223, 175,
			110, 223, 191, 187, 28, 81, 3, 134, 142, 3, 248, 210, 52, 213, 73, 155, 81, 38, 230, 234, 237, 205, 229,
			245, 248, 215, 203, 225, 48, 35, 191, 173, 150, 164, 166, 146, 116, 78, 138, 130, 242, 151, 71, 182, 41,
			158, 173, 220, 48, 88, 18, 216, 143, 224, 116, 49, 133, 19, 14, 143, 22, 212, 181, 232, 120, 146, 196, 43,
			64, 231, 68, 3, 39, 164, 181, 8, 146, 8, 194, 19, 69, 112, 238, 171, 121, 206, 14, 230, 45, 47, 72, 207,
			4, 23, 12, 202, 28, 186, 219, 66, 204, 23, 171, 204, 11, 225, 143, 215, 60, 140, 249, 182, 95, 8, 197, 203,
			235, 193, 205, 171, 212, 145, 252, 204, 114, 131, 60, 215, 6, 201, 109, 77, 178, 220, 200, 65, 46, 198,
			216, 241, 250, 202, 49, 77, 206, 8, 142, 14, 131, 155, 145, 65, 144, 109, 18, 20, 59, 254, 28, 142, 102,
			185, 36, 194, 251, 16, 167, 111, 53, 245, 123, 89, 90, 109, 168, 218, 170, 202, 150, 234, 58, 134, 127,
			27, 92, 15, 70, 183, 55, 250, 216, 224, 237, 235, 55, 163, 241, 63, 232, 107, 104, 242, 162, 85, 10, 84,
			23, 245, 79, 2, 159, 143, 157, 56, 14, 197, 164, 111, 98, 106, 63, 192, 100, 27, 185, 164, 167, 75, 62,
			19, 201, 146, 124, 37, 182, 13, 7, 49, 241, 33, 109, 157, 135, 249, 236, 126, 186, 36, 190, 175, 135, 15,
			216, 170, 86, 90, 226, 11, 23, 50, 159, 234, 136, 28, 60, 164, 135, 246, 43, 22, 221, 113, 143, 199, 1,
			228, 147, 111, 161, 47, 114, 218, 146, 224, 25, 232, 227, 231, 173, 124, 161, 62, 197, 134, 233, 207, 79,
			80, 136, 19, 227, 153, 249, 233, 179, 170, 85, 180, 111, 107, 199, 176, 26, 1, 128, 248, 179, 242, 130,
			60, 88, 206, 221, 114, 25, 74, 17, 95, 83, 209, 61, 179, 168, 47, 40, 106, 16, 88, 114, 8, 70, 148, 59,
			192, 17, 187, 147, 231, 53, 131, 91, 174, 135, 225, 203, 152, 111, 53, 230, 212, 145, 148, 89, 227, 169,
			246, 236, 128, 52, 229, 139, 38, 78, 113, 149, 58, 57, 78, 73, 215, 134, 111, 46, 127, 29, 12, 75, 197,
			66, 27, 105, 26, 32, 89, 93, 253, 140, 194, 11, 54, 69, 130, 104, 225, 172, 248, 120, 10, 128, 36, 143,
			162, 177, 1, 40, 9, 90, 253, 218, 90, 53, 134, 142, 31, 225, 252, 120, 219, 127, 52, 233, 238, 241, 164,
			129, 235, 70, 28, 44, 52, 51, 8, 31, 242, 24, 241, 71, 88, 177, 79, 185, 123, 52, 165, 178, 65, 69, 73,
			218, 42, 230, 254, 77, 16, 255, 147, 135, 129, 225, 138, 97, 41, 182, 150, 241, 204, 212, 96, 243, 144,
			59, 49, 15, 71, 11, 199, 31, 252, 145, 56, 30, 222, 57, 236, 180, 147, 118, 14, 148, 59, 44, 152, 66, 121,
			4, 99, 124, 150, 74, 96, 128, 212, 192, 55, 44, 14, 252, 4, 168, 14, 184, 244, 4, 209, 105, 159, 144, 91,
			71, 33, 183, 142, 5, 243, 36, 187, 77, 20, 206, 36, 146, 35, 117, 237, 199, 174, 174, 110, 183, 8, 64, 34,
			236, 149, 55, 90, 104, 21, 200, 177, 114, 94, 192, 156, 91, 194, 93, 5, 215, 129, 76, 222, 43, 41, 215,
			229, 226, 16, 247, 220, 90, 107, 71, 90, 180, 7, 93, 1, 157, 22, 25, 201, 73, 13, 236, 152, 23, 36, 156,
			163, 89, 199, 233, 227, 46, 127, 188, 175, 247, 211, 227, 174, 116, 25, 70, 216, 139, 11, 52, 211, 101,
			191, 192, 47, 48, 242, 57, 179, 84, 120, 93, 229, 26, 55, 217, 202, 83, 91, 83, 67, 101, 244, 90, 205, 158,
			11, 218, 240, 43, 7, 200, 105, 220, 113, 101, 102, 113, 31, 163, 168, 49, 247, 167, 193, 140, 207, 200,
			120, 232, 54, 47, 133, 116, 151, 244, 176, 116, 18, 59, 214, 14, 145, 210, 10, 54, 6, 63, 46, 216, 79, 150,
			150, 165, 53, 183, 13, 149, 144, 226, 248, 174, 174, 231, 87, 179, 157, 144, 173, 94, 29, 88, 24, 13, 178,
			194, 36, 69, 75, 4, 250, 164, 37, 162, 203, 38, 78, 196, 243, 75, 133, 204, 202, 44, 91, 56, 15, 129, 163,
			68, 128, 199, 3, 18, 202, 38, 5, 199, 203, 14, 83, 101, 201, 2, 133, 239, 82, 144, 179, 89, 146, 188, 209,
			210, 41, 39, 158, 167, 245, 74, 191, 10, 233, 34, 47, 192, 134, 91, 188, 211, 14, 197, 92, 248, 96, 128,
			240, 9, 110, 194, 201, 88, 90, 36, 207, 207, 105, 83, 141, 152, 136, 152, 205, 218, 167, 39, 19, 145, 94,
			253, 202, 59, 254, 145, 90, 221, 236, 138, 243, 217, 4, 239, 180, 23, 14, 221, 21, 111, 66, 17, 19, 138,
			101, 29, 27, 185, 0, 188, 242, 144, 77, 97, 185, 250, 220, 35, 222, 219, 105, 236, 44, 248, 44, 4, 229,
			232, 115, 200, 163, 8, 55, 171, 144, 255, 145, 8, 248, 145, 175, 128, 25, 6, 50, 14, 194, 40, 189, 176,
			230, 204, 7, 101, 168, 36, 130, 81, 142, 178, 252, 192, 63, 217, 167, 135, 99, 66, 44, 60, 130, 211, 208,
			140, 118, 80, 88, 179, 102, 138, 193, 67, 14, 86, 115, 122, 43, 65, 47, 24, 148, 5, 116, 209, 175, 34, 0,
			199, 168, 0, 156, 102, 100, 126, 18, 225, 5, 57, 230, 137, 207, 52, 93, 40, 207, 21, 91, 80, 154, 94, 239,
			135, 124, 42, 208, 17, 124, 59, 3, 81, 195, 55, 46, 240, 201, 61, 15, 172, 231, 83, 7, 95, 38, 128, 210,
			59, 63, 216, 128, 97, 176, 143, 112, 103, 186, 72, 53, 162, 44, 129, 142, 51, 207, 9, 231, 16, 46, 32, 240,
			217, 167, 246, 167, 244, 109, 196, 212, 209, 250, 2, 190, 3, 152, 137, 181, 152, 161, 89, 240, 140, 94,
			250, 201, 114, 2, 108, 129, 43, 119, 39, 148, 71, 27, 20, 36, 43, 81, 253, 163, 155, 22, 187, 45, 235, 118,
			133, 207, 122, 207, 149, 55, 116, 197, 59, 51, 34, 194, 101, 223, 96, 166, 137, 251, 141, 126, 45, 129,
			252, 169, 142, 174, 37, 213, 238, 41, 145, 115, 190, 81, 11, 40, 49, 207, 100, 11, 48, 16, 51, 182, 116,
			132, 111, 161, 200, 210, 41, 239, 40, 135, 37, 176, 54, 180, 35, 80, 229, 238, 95, 129, 234, 42, 4, 193,
			250, 211, 145, 28, 172, 202, 34, 82, 144, 152, 183, 138, 121, 159, 90, 71, 58, 218, 17, 179, 40, 32, 223,
			12, 242, 225, 186, 1, 181, 237, 249, 102, 132, 34, 217, 33, 117, 52, 248, 104, 45, 235, 8, 127, 185, 119,
			197, 227, 233, 194, 42, 195, 227, 6, 19, 84, 14, 75, 246, 103, 102, 247, 78, 147, 6, 91, 210, 229, 205,
			105, 2, 89, 106, 213, 51, 73, 175, 7, 163, 241, 203, 219, 155, 193, 24, 208, 216, 251, 183, 31, 45, 7, 138,
			29, 22, 87, 29, 210, 20, 219, 219, 174, 133, 154, 28, 96, 193, 239, 9, 237, 40, 155, 154, 186, 216, 65,
			220, 31, 201, 40, 105, 71, 0, 32, 145, 151, 61, 118, 130, 45, 83, 35, 29, 59, 216, 244, 136, 233, 56, 165,
			105, 35, 77, 237, 72, 226, 55, 169, 18, 12, 189, 216, 51, 139, 184, 112, 155, 72, 5, 225, 99, 249, 12, 209,
			196, 200, 30, 45, 217, 113, 21, 251, 46, 103, 223, 25, 216, 119, 15, 176, 223, 231, 236, 247, 6, 246, 251,
			7, 216, 55, 57, 251, 198, 192, 190, 161, 64, 64, 8, 186, 57, 12, 132, 95, 161, 192, 50, 194, 97, 90, 245,
			150, 9, 120, 54, 112, 255, 160, 15, 117, 231, 99, 194, 156, 251, 84, 234, 55, 1, 164, 135, 248, 37, 8, 204,
			233, 9, 55, 145, 185, 10, 48, 26, 172, 53, 224, 211, 125, 51, 12, 208, 244, 75, 108, 173, 194, 171, 38,
			83, 169, 76, 139, 118, 46, 127, 107, 253, 14, 139, 227, 183, 246, 239, 15, 106, 202, 103, 116, 201, 181,
			163, 162, 212, 114, 246, 158, 50, 178, 12, 239, 190, 45, 141, 18, 151, 82, 49, 114, 40, 170, 208, 60, 116,
			114, 117, 221, 151, 19, 232, 86, 64, 135, 239, 151, 186, 137, 214, 52, 10, 55, 51, 208, 105, 255, 75, 13,
			213, 112, 166, 148, 248, 60, 69, 78, 23, 197, 13, 39, 187, 242, 65, 111, 238, 51, 105, 133, 115, 154, 206,
			63, 166, 121, 9, 178, 50, 24, 168, 31, 180, 235, 251, 77, 219, 220, 173, 117, 123, 50, 216, 151, 119, 238,
			116, 250, 184, 160, 183, 94, 47, 236, 24, 186, 136, 226, 62, 109, 102, 151, 117, 5, 29, 121, 207, 201, 170,
			221, 33, 141, 160, 233, 108, 45, 239, 171, 83, 196, 103, 8, 107, 58, 83, 175, 142, 105, 198, 93, 14, 42,
			157, 0, 10, 87, 14, 143, 142, 106, 110, 79, 25, 114, 107, 177, 77, 137, 40, 227, 199, 69, 35, 8, 115, 55,
			212, 88, 115, 83, 138, 120, 193, 221, 82, 200, 31, 20, 107, 10, 252, 158, 42, 67, 18, 84, 196, 171, 111,
			59, 31, 139, 31, 30, 94, 28, 122, 89, 231, 107, 163, 255, 216, 122, 43, 42, 52, 59, 220, 146, 29, 172, 250,
			214, 166, 92, 89, 122, 85, 104, 133, 213, 127, 56, 37, 42, 182, 225, 124, 242, 40, 211, 14, 231, 98, 239,
			142, 89, 165, 99, 31, 71, 225, 153, 237, 157, 115, 199, 153, 220, 103, 147, 24, 208, 71, 254, 98, 17, 142,
			9, 116, 143, 159, 246, 236, 244, 63, 152, 24, 104, 193, 23, 144, 120, 20, 138, 185, 143, 32, 93, 174, 11,
			133, 201, 43, 177, 170, 33, 171, 133, 116, 61, 234, 94, 187, 20, 204, 131, 119, 216, 255, 103, 192, 113,
			170, 176, 99, 25, 57, 202, 239, 233, 161, 173, 244, 75, 176, 101, 231, 17, 208, 178, 76, 50, 217, 35, 177,
			139, 224, 19, 160, 39, 65, 184, 199, 193, 207, 84, 232, 119, 64, 162, 74, 210, 183, 131, 82, 37, 233, 219,
			241, 169, 146, 84, 9, 85, 43, 223, 139, 28, 153, 83, 103, 23, 115, 119, 48, 107, 135, 243, 117, 192, 135,
			71, 103, 200, 254, 126, 41, 178, 191, 95, 142, 236, 239, 151, 36, 155, 178, 164, 110, 108, 177, 9, 190,
			231, 4, 54, 89, 16, 98, 135, 83, 55, 26, 120, 65, 146, 225, 211, 89, 185, 179, 89, 123, 152, 179, 45, 255,
			73, 102, 73, 32, 173, 95, 185, 139, 73, 242, 177, 113, 51, 203, 27, 162, 105, 55, 51, 0, 48, 105, 69, 65,
			100, 138, 159, 148, 33, 249, 38, 81, 130, 75, 149, 123, 90, 42, 205, 188, 181, 105, 253, 119, 127, 111,
			59, 128, 102, 10, 134, 106, 24, 164, 108, 109, 163, 164, 94, 223, 229, 202, 80, 163, 2, 213, 151, 246, 66,
			64, 245, 159, 13, 47, 191, 92, 23, 223, 126, 253, 80, 186, 120, 1, 82, 243, 107, 178, 31, 254, 3, 103, 48,
			75, 90
		};
		const CharString _code = _decompress_code(_code_compressed, 3047, 11442);

		_setup(_code.get_data(), _code.get_data() + 11401, "SkeletonShaderGLES3",
				8, _uniform_strings, 0, _ubo_pairs,
				3, _feedbacks, 1, _texunit_pairs,
				7, _spec_pairs, 2, _variant_defines);
	}
};
