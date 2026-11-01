/**************************************************************************/
/*  copy.glsl.gen.h                                                       */
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

class CopyShaderGLES3 : public ShaderGLES3 {
public:
	enum Uniforms {
		COPY_SECTION,
		SOURCE_SECTION,
		LAYER,
		LOD,
		COLOR_IN,
		MULTIPLY,
		PIXEL_SIZE,
		MIP_LEVEL,
		EYE_CENTER,
		K1,
		K2,
		UPSCALE,
		ASPECT_RATIO,
		EXPOSURE,
	};

	enum ShaderVariant {
		MODE_DEFAULT,
		MODE_COPY_SECTION,
		MODE_COPY_SECTION_SOURCE,
		MODE_COPY_SECTION_3D,
		MODE_COPY_SECTION_2D_ARRAY,
		MODE_LENS_DISTORTION,
		MODE_SCREEN,
		MODE_GAUSSIAN_BLUR,
		MODE_MIPMAP,
		MODE_SIMPLE_COLOR,
		MODE_CUBE_TO_OCTAHEDRAL,
		MODE_CUBE_TO_PANORAMA,
		MODE_APPLY_LINEAR_EXPOSURE_TO_SRGB,
	};

	enum Specializations : uint64_t {
		CONVERT_LINEAR_TO_SRGB = 1,
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
			"copy_section",
			"source_section",
			"layer",
			"lod",
			"color_in",
			"multiply",
			"pixel_size",
			"mip_level",
			"eye_center",
			"k1",
			"k2",
			"upscale",
			"aspect_ratio",
			"exposure"
		};
		static const char *_variant_defines[] = {
			"#define MODE_SIMPLE_COPY",
			"#define USE_COPY_SECTION \n#define MODE_SIMPLE_COPY",
			"#define USE_COPY_SECTION \n#define MODE_SIMPLE_COPY \n#define MODE_COPY_FROM",
			"#define USE_COPY_SECTION \n#define MODE_SIMPLE_COPY \n#define USE_TEXTURE_3D",
			"#define USE_COPY_SECTION \n#define MODE_SIMPLE_COPY \n#define USE_TEXTURE_2D_ARRAY",
			"#define USE_COPY_SECTION \n#define MODE_SIMPLE_COPY \n#define USE_TEXTURE_2D_ARRAY \n#define APPLY_LENS_DISTORTION",
			"#define MODE_SIMPLE_COPY \n#define MODE_MULTIPLY",
			"#define MODE_GAUSSIAN_BLUR",
			"#define MODE_MIPMAP",
			"#define MODE_SIMPLE_COLOR \n#define USE_COPY_SECTION",
			"#define CUBE_TO_OCTAHEDRAL \n#define USE_COPY_SECTION",
			"#define CUBE_TO_PANORAMA",
			"#define MODE_SIMPLE_COPY \n#define MODE_MULTIPLY \n#define APPLY_LINEAR_EXPOSURE_TO_SRGB",
		};
		static TexUnitPair _texunit_pairs[] = {
			{ "source_cube", 0 },
			{ "source_3d", 0 },
			{ "source_2d_array", 0 },
			{ "source", 0 },
		};
		static UBOPair *_ubo_pairs = nullptr;
		static Specialization _spec_pairs[] = {
			{ "CONVERT_LINEAR_TO_SRGB", false },
		};
		static const Feedback *_feedbacks = nullptr;
		static const uint8_t _code_compressed[] = {
			120, 218, 197, 88, 91, 115, 226, 198, 18, 206, 43, 250, 21, 147, 202, 139, 132, 145, 16, 96, 239, 110, 150,
			56, 85, 216, 176, 94, 111, 176, 161, 0, 167, 178, 79, 170, 65, 26, 96, 202, 66, 82, 116, 225, 226, 100,
			243, 219, 211, 61, 146, 208, 13, 95, 194, 158, 170, 227, 42, 97, 105, 166, 251, 235, 158, 158, 190, 205,
			72, 54, 221, 187, 81, 40, 219, 174, 73, 67, 238, 58, 228, 146, 232, 10, 225, 14, 217, 48, 179, 13, 63, 126,
			200, 118, 6, 13, 67, 159, 207, 187, 146, 4, 148, 241, 68, 180, 49, 184, 19, 50, 223, 235, 74, 205, 58, 49,
			109, 234, 44, 213, 133, 235, 175, 105, 72, 0, 163, 222, 148, 164, 159, 248, 130, 88, 108, 193, 29, 102,
			201, 15, 211, 129, 113, 61, 26, 127, 53, 166, 131, 235, 217, 237, 232, 94, 33, 127, 255, 125, 152, 188,
			27, 245, 7, 198, 77, 239, 97, 58, 189, 237, 221, 27, 87, 195, 135, 137, 34, 53, 155, 164, 31, 79, 163, 42,
			186, 218, 34, 166, 235, 250, 86, 160, 73, 145, 195, 81, 14, 89, 241, 229, 202, 67, 93, 206, 97, 202, 219,
			27, 1, 51, 81, 253, 174, 244, 19, 115, 44, 190, 40, 136, 63, 34, 161, 162, 128, 80, 239, 211, 100, 116,
			167, 28, 19, 17, 184, 145, 111, 178, 138, 16, 105, 227, 114, 139, 172, 41, 119, 100, 133, 252, 37, 213,
			14, 86, 1, 43, 22, 76, 71, 234, 68, 215, 46, 200, 25, 254, 118, 165, 218, 210, 54, 198, 110, 192, 19, 123,
			163, 4, 185, 64, 222, 32, 45, 77, 23, 63, 74, 247, 59, 45, 153, 151, 165, 237, 246, 32, 78, 206, 219, 11,
			135, 206, 178, 221, 196, 207, 122, 193, 160, 218, 211, 86, 129, 161, 182, 166, 19, 21, 21, 250, 95, 24,
			184, 96, 167, 162, 105, 75, 250, 128, 228, 210, 252, 211, 246, 160, 193, 55, 169, 234, 123, 139, 5, 58,
			223, 15, 82, 234, 192, 175, 250, 105, 217, 184, 179, 193, 31, 179, 135, 201, 192, 232, 244, 11, 75, 200,
			79, 181, 251, 70, 111, 50, 233, 125, 205, 60, 101, 97, 187, 0, 8, 145, 196, 252, 110, 121, 208, 181, 50,
			119, 1, 97, 0, 72, 132, 61, 166, 183, 119, 227, 33, 154, 101, 56, 154, 28, 120, 18, 127, 182, 93, 31, 212,
			62, 206, 119, 247, 48, 156, 221, 142, 135, 95, 75, 114, 214, 145, 29, 114, 207, 222, 31, 103, 42, 236, 205,
			127, 137, 174, 54, 241, 248, 142, 217, 70, 192, 159, 88, 5, 250, 250, 225, 10, 172, 50, 50, 70, 215, 179,
			222, 231, 65, 127, 210, 27, 74, 192, 210, 33, 174, 25, 26, 161, 107, 224, 187, 44, 48, 152, 136, 14, 49,
			183, 137, 29, 190, 35, 51, 216, 106, 225, 226, 224, 87, 116, 30, 224, 183, 114, 120, 221, 43, 224, 248,
			181, 120, 101, 33, 112, 172, 233, 78, 86, 55, 218, 83, 3, 2, 8, 99, 162, 182, 17, 142, 114, 9, 147, 117,
			162, 6, 124, 233, 200, 56, 130, 51, 62, 11, 35, 223, 33, 14, 110, 178, 13, 90, 203, 27, 24, 253, 246, 156,
			234, 227, 222, 253, 104, 210, 187, 235, 29, 86, 110, 187, 91, 47, 53, 41, 247, 12, 155, 109, 152, 93, 88,
			248, 193, 37, 170, 171, 47, 120, 76, 89, 66, 230, 45, 1, 93, 123, 54, 243, 175, 163, 57, 75, 189, 219, 132,
			247, 46, 129, 125, 129, 28, 0, 100, 225, 71, 29, 100, 49, 59, 96, 56, 246, 143, 124, 170, 72, 69, 122, 201,
			191, 203, 10, 117, 250, 169, 58, 29, 171, 164, 12, 232, 242, 12, 78, 53, 24, 18, 180, 118, 191, 231, 251,
			116, 159, 66, 182, 45, 131, 226, 119, 21, 56, 96, 85, 214, 132, 171, 66, 156, 236, 130, 248, 143, 115, 63,
			126, 167, 105, 208, 21, 122, 99, 136, 38, 99, 56, 184, 159, 26, 253, 219, 233, 108, 52, 193, 188, 154, 143,
			72, 240, 223, 61, 108, 17, 195, 60, 82, 14, 239, 199, 86, 101, 164, 93, 30, 137, 188, 192, 164, 54, 43,
			15, 211, 192, 131, 156, 102, 248, 88, 118, 187, 185, 53, 29, 215, 167, 164, 237, 237, 253, 160, 55, 49,
			6, 127, 140, 71, 83, 220, 5, 88, 217, 116, 114, 115, 85, 146, 192, 118, 158, 27, 68, 126, 46, 112, 143,
			22, 251, 164, 168, 159, 147, 133, 79, 151, 134, 200, 62, 80, 117, 64, 147, 217, 138, 7, 132, 122, 158, 239,
			238, 248, 58, 102, 0, 72, 80, 58, 128, 240, 114, 84, 135, 45, 97, 112, 195, 32, 137, 120, 81, 216, 37, 197,
			111, 50, 103, 43, 186, 97, 1, 241, 32, 183, 216, 123, 45, 78, 13, 129, 191, 156, 99, 110, 176, 97, 87, 168,
			47, 139, 49, 33, 81, 100, 8, 92, 125, 65, 220, 194, 119, 33, 25, 133, 161, 247, 177, 217, 52, 87, 220, 182,
			57, 117, 66, 109, 110, 187, 203, 192, 115, 67, 205, 116, 215, 205, 182, 222, 106, 55, 245, 15, 77, 68, 86,
			11, 202, 6, 152, 233, 213, 149, 29, 216, 218, 42, 92, 219, 135, 212, 32, 228, 65, 222, 144, 43, 47, 186,
			214, 209, 47, 58, 250, 59, 189, 213, 18, 181, 250, 221, 135, 118, 235, 125, 11, 254, 20, 241, 9, 146, 46,
			218, 237, 15, 239, 63, 136, 140, 242, 253, 22, 2, 222, 200, 73, 60, 52, 54, 23, 119, 253, 196, 80, 177,
			129, 208, 84, 184, 176, 255, 143, 161, 48, 235, 138, 92, 13, 89, 250, 226, 2, 219, 0, 207, 221, 198, 198,
			106, 196, 73, 92, 215, 206, 91, 239, 196, 223, 123, 5, 179, 119, 50, 136, 212, 7, 10, 93, 137, 205, 85,
			236, 149, 142, 150, 194, 241, 87, 73, 148, 9, 172, 219, 224, 155, 185, 226, 253, 114, 176, 214, 18, 242,
			98, 163, 18, 35, 65, 75, 16, 176, 48, 158, 86, 11, 145, 44, 204, 24, 210, 71, 150, 132, 34, 17, 161, 8,
			123, 19, 186, 132, 154, 166, 27, 57, 161, 84, 139, 217, 181, 61, 105, 94, 150, 34, 86, 176, 91, 60, 8, 93,
			63, 44, 200, 50, 130, 63, 65, 92, 34, 183, 158, 188, 28, 202, 153, 79, 45, 30, 5, 121, 26, 120, 215, 118,
			224, 96, 217, 215, 190, 66, 125, 14, 212, 25, 103, 61, 123, 63, 80, 38, 154, 192, 118, 26, 34, 221, 0, 3,
			22, 215, 51, 34, 63, 182, 242, 12, 138, 24, 106, 231, 134, 206, 177, 108, 166, 234, 94, 86, 128, 146, 149,
			250, 12, 124, 198, 222, 23, 108, 149, 51, 79, 253, 168, 121, 168, 101, 65, 122, 241, 209, 236, 36, 54, 59,
			153, 83, 243, 17, 108, 156, 236, 89, 34, 246, 172, 176, 49, 56, 5, 230, 62, 228, 205, 24, 202, 177, 136,
			185, 98, 192, 140, 128, 194, 9, 165, 26, 100, 76, 57, 130, 202, 79, 126, 33, 42, 174, 22, 50, 62, 124, 238,
			139, 159, 59, 242, 43, 201, 79, 138, 47, 17, 70, 181, 44, 227, 165, 125, 184, 142, 141, 119, 246, 19, 183,
			224, 181, 111, 68, 20, 99, 100, 201, 92, 45, 215, 209, 191, 53, 123, 23, 43, 48, 160, 101, 13, 31, 160,
			66, 165, 131, 184, 99, 67, 215, 146, 15, 133, 56, 9, 163, 104, 211, 136, 251, 75, 136, 43, 104, 41, 149,
			238, 155, 74, 242, 107, 240, 105, 81, 126, 73, 8, 148, 231, 163, 48, 9, 70, 3, 108, 161, 228, 13, 80, 90,
			226, 161, 225, 26, 221, 255, 62, 152, 204, 210, 202, 149, 22, 172, 26, 110, 237, 132, 129, 39, 58, 203,
			56, 137, 81, 82, 23, 83, 169, 156, 164, 21, 32, 91, 72, 106, 4, 43, 10, 40, 226, 136, 211, 146, 69, 44,
			26, 82, 2, 209, 26, 39, 203, 70, 140, 54, 135, 204, 186, 5, 182, 149, 27, 217, 232, 125, 161, 72, 181, 14,
			9, 0, 244, 71, 32, 17, 235, 208, 32, 9, 194, 90, 74, 89, 246, 48, 165, 84, 122, 221, 151, 235, 110, 17,
			181, 84, 228, 242, 168, 121, 66, 8, 153, 172, 66, 159, 170, 87, 241, 76, 144, 160, 32, 116, 249, 64, 128,
			123, 83, 36, 46, 251, 127, 90, 249, 95, 78, 181, 223, 222, 224, 236, 69, 129, 133, 244, 254, 236, 17, 232,
			136, 46, 133, 51, 16, 160, 13, 22, 11, 110, 114, 72, 18, 100, 238, 238, 200, 130, 219, 152, 79, 132, 211,
			124, 225, 107, 230, 176, 167, 143, 105, 9, 220, 110, 183, 26, 247, 247, 238, 99, 36, 74, 159, 3, 174, 164,
			46, 129, 66, 228, 38, 71, 5, 163, 135, 42, 20, 64, 147, 5, 1, 56, 158, 202, 29, 21, 50, 141, 173, 186, 11,
			213, 138, 194, 189, 74, 173, 13, 117, 76, 102, 169, 91, 234, 47, 168, 207, 164, 66, 189, 133, 158, 134,
			146, 27, 26, 1, 47, 117, 208, 179, 40, 65, 20, 72, 185, 30, 13, 224, 16, 245, 252, 193, 43, 14, 164, 222,
			177, 88, 108, 228, 14, 189, 103, 185, 67, 23, 228, 25, 44, 45, 178, 42, 110, 4, 240, 87, 201, 14, 65, 136,
			118, 117, 10, 154, 254, 12, 216, 245, 41, 96, 207, 105, 214, 63, 105, 157, 144, 79, 1, 13, 126, 75, 104,
			131, 211, 214, 121, 28, 236, 211, 233, 91, 160, 87, 214, 121, 243, 10, 88, 145, 250, 243, 201, 38, 174,
			74, 190, 61, 221, 194, 85, 155, 124, 57, 217, 192, 85, 172, 223, 78, 183, 111, 213, 143, 134, 39, 123, 120,
			21, 235, 238, 100, 235, 231, 177, 210, 158, 107, 203, 248, 114, 133, 189, 37, 182, 2, 77, 114, 46, 186,
			206, 228, 222, 7, 82, 11, 243, 141, 28, 5, 28, 30, 82, 154, 82, 178, 147, 251, 32, 118, 0, 207, 45, 60,
			95, 176, 207, 142, 217, 186, 5, 186, 51, 32, 236, 1, 193, 21, 60, 55, 240, 124, 66, 194, 130, 152, 42, 61,
			210, 94, 195, 243, 25, 121, 222, 64, 255, 41, 193, 30, 194, 243, 219, 27, 232, 111, 18, 236, 59, 228, 57,
			66, 255, 250, 133, 17, 86, 236, 25, 244, 150, 33, 9, 87, 140, 60, 252, 30, 95, 69, 113, 39, 78, 179, 129,
			184, 157, 98, 142, 233, 90, 80, 238, 93, 51, 164, 43, 102, 249, 212, 206, 83, 105, 201, 205, 146, 197, 209,
			150, 249, 187, 167, 252, 53, 226, 225, 92, 160, 116, 75, 214, 47, 246, 51, 226, 42, 166, 129, 96, 226, 234,
			245, 149, 91, 35, 9, 234, 173, 19, 132, 201, 121, 123, 140, 241, 216, 209, 90, 231, 173, 139, 159, 219,
			239, 46, 58, 23, 63, 103, 174, 226, 173, 120, 254, 68, 3, 77, 105, 172, 83, 29, 184, 178, 171, 174, 21,
			131, 134, 38, 79, 182, 79, 8, 146, 53, 198, 183, 90, 64, 31, 191, 0, 202, 37, 214, 30, 25, 208, 209, 250,
			248, 42, 48, 240, 67, 141, 15, 65, 9, 229, 94, 20, 213, 32, 153, 206, 198, 159, 146, 241, 231, 17, 18, 209,
			169, 185, 74, 205, 77, 181, 169, 140, 13, 24, 195, 55, 178, 75, 52, 37, 237, 128, 170, 61, 119, 114, 162,
			76, 175, 187, 211, 219, 221, 31, 254, 5, 34, 31, 189, 206
		};
		const CharString _code = _decompress_code(_code_compressed, 1938, 6300);

		_setup(_code.get_data(), _code.get_data() + 726, "CopyShaderGLES3",
				14, _uniform_strings, 0, _ubo_pairs,
				0, _feedbacks, 4, _texunit_pairs,
				1, _spec_pairs, 13, _variant_defines);
	}
};
