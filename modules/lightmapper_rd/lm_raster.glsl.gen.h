/**************************************************************************/
/*  lm_raster.glsl.gen.h                                                  */
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

static const char lm_raster_shader_glsl[] = {
R"<!>(#[vertex]

#version 450

#VERSION_DEFINES


layout(set = 0, binding = 0) uniform BakeParameters {
	vec3 world_size;
	float bias;

	vec3 to_cell_offset;
	int grid_size;

	vec3 to_cell_size;
	uint light_count;

	mat3x4 env_transform;

	ivec2 atlas_size;
	float exposure_normalization;
	uint bounces;

	float bounce_indirect_energy;
	int shadowmask_light_idx;
	uint transparency_rays;
	float supersampling_factor;
}
bake_params;

struct Vertex {
	vec3 position;
	float normal_z;
	vec2 uv;
	vec2 normal_xy;
};

layout(set = 0, binding = 1, std430) restrict readonly buffer Vertices {
	Vertex data[];
}
vertices;

#define CULL_DISABLED 0
#define CULL_FRONT 1
#define CULL_BACK 2

struct Triangle {
	uvec3 indices;
	uint slice;
	vec3 min_bounds;
	uint cull_mode;
	vec3 max_bounds;
	uint pad1;
};

struct ClusterAABB {
	vec3 min_bounds;
	uint pad0;
	vec3 max_bounds;
	uint pad1;
};

layout(set = 0, binding = 2, std430) restrict readonly buffer Triangles {
	Triangle data[];
}
triangles;

layout(set = 0, binding = 3, std430) restrict readonly buffer TriangleIndices {
	uint data[];
}
triangle_indices;

#define LIGHT_TYPE_DIRECTIONAL 0
#define LIGHT_TYPE_OMNI 1
#define LIGHT_TYPE_SPOT 2
#define LIGHT_TYPE_AREA 3

struct Light {
	vec3 position;
	uint type;

	vec3 direction;
	float energy;

	vec3 color;
	float size;

	float range;
	float attenuation;
	float cos_spot_angle;
	float inv_spot_attenuation;

	float indirect_energy;
	float shadow_blur;
	bool static_bake;
	uint pad;

	vec4 area_width;
	vec4 area_height;
	vec4 area_texture_rect;
};

layout(set = 0, binding = 4, std430) restrict readonly buffer Lights {
	Light data[];
}
lights;

struct Seam {
	uvec2 a;
	uvec2 b;
};

layout(set = 0, binding = 5, std430) restrict readonly buffer Seams {
	Seam data[];
}
seams;

layout(set = 0, binding = 6, std430) restrict readonly buffer Probes {
	vec4 data[];
}
probe_positions;

layout(set = 0, binding = 7) uniform utexture3D grid;

layout(set = 0, binding = 8) uniform texture2DArray albedo_tex;
layout(set = 0, binding = 9) uniform texture2DArray emission_tex;

layout(set = 0, binding = 10) uniform sampler linear_sampler;
layout(set = 0, binding = 11) uniform sampler area_light_atlas_sampler;

layout(set = 0, binding = 12, std430) restrict readonly buffer ClusterIndices {
	uint data[];
}
cluster_indices;

layout(set = 0, binding = 13, std430) restrict readonly buffer ClusterAABBs {
	ClusterAABB data[];
}
cluster_aabbs;

// Fragment action constants
const uint FA_NONE = 0;
const uint FA_SMOOTHEN_POSITION = 1;

layout(location = 0) out vec3 vertex_interp;
layout(location = 1) out vec3 normal_interp;
layout(location = 2) out vec2 uv_interp;
layout(location = 3) out vec3 barycentric;
layout(location = 4) flat out uvec3 vertex_indices;
layout(location = 5) flat out vec3 face_normal;
layout(location = 6) flat out uint fragment_action;

layout(push_constant, std430) uniform Params {
	vec2 atlas_size;
	vec2 uv_offset;
	vec3 to_cell_size;
	uint base_triangle;
	vec3 to_cell_offset;
	float bias;
	ivec3 grid_size;
	uint pad2;
}
params;

void main() {
	uint triangle_idx = params.base_triangle + gl_VertexIndex / 3;
	uint triangle_subidx = gl_VertexIndex % 3;

	vertex_indices = triangles.data[triangle_idx].indices;

	uint vertex_idx;
	if (triangle_subidx == 0) {
		vertex_idx = vertex_indices.x;
		barycentric = vec3(1, 0, 0);
	} else if (triangle_subidx == 1) {
		vertex_idx = vertex_indices.y;
		barycentric = vec3(0, 1, 0);
	} else {
		vertex_idx = vertex_indices.z;
		barycentric = vec3(0, 0, 1);
	}

	vertex_interp = vertices.data[vertex_idx].position;
	uv_interp = vertices.data[vertex_idx].uv;
	normal_interp = vec3(vertices.data[vertex_idx].normal_xy, vertices.data[vertex_idx].normal_z);

	face_normal = -normalize(cross((vertices.data[vertex_indices.x].position - vertices.data[vertex_indices.y].position), (vertices.data[vertex_indices.x].position - vertices.data[vertex_indices.z].position)));

	{
		const float FLAT_THRESHOLD = 0.99;
		const vec3 norm_a = vec3(vertices.data[vertex_indices.x].normal_xy, vertices.data[vertex_indices.x].normal_z);
		const vec3 norm_b = vec3(vertices.data[vertex_indices.y].normal_xy, vertices.data[vertex_indices.y].normal_z);
		const vec3 norm_c = vec3(vertices.data[vertex_indices.z].normal_xy, vertices.data[vertex_indices.z].normal_z);
		fragment_action = (dot(norm_a, norm_b) < FLAT_THRESHOLD || dot(norm_a, norm_c) < FLAT_THRESHOLD || dot(norm_b, norm_c) < FLAT_THRESHOLD) ? FA_SMOOTHEN_POSITION : FA_NONE;
	}

	gl_Position = vec4((uv_interp + params.uv_offset) * 2.0 - 1.0, 0.0001, 1.0);
}

#[fragment]

#version 450

#VERSION_DEFINES


layout(set = 0, binding = 0) uniform BakeParameters {
	vec3 world_size;
	float bias;

	vec3 to_cell_offset;
	int grid_size;

	vec3 to_cell_size;
	uint light_count;

	mat3x4 env_transform;

	ivec2 atlas_size;
	float exposure_normalization;
	uint bounces;

	float bounce_indirect_energy;
	int shadowmask_light_idx;
	uint transparency_rays;
	float supersampling_factor;
}
bake_params;

struct Vertex {
	vec3 position;
	float normal_z;
	vec2 uv;
	vec2 normal_xy;
};

layout(set = 0, binding = 1, std430) restrict readonly buffer Vertices {
	Vertex data[];
}
vertices;

#define CULL_DISABLED 0
#define CULL_FRONT 1
#define CULL_BACK 2

struct Triangle {
	uvec3 indices;
	uint slice;
	vec3 min_bounds;
	uint cull_mode;
	vec3 max_bounds;
	uint pad1;
};

struct ClusterAABB {
	vec3 min_bounds;
	uint pad0;
	vec3 max_bounds;
	uint pad1;
};

layout(set = 0, binding = 2, std430) restrict readonly buffer Triangles {
	Triangle data[];
}
triangles;

layout(set = 0, binding = 3, std430) restrict readonly buffer TriangleIndices {
	uint data[];
}
triangle_indices;

#define LIGHT_TYPE_DIRECTIONAL 0
#define LIGHT_TYPE_OMNI 1
#define LIGHT_TYPE_SPOT 2
#define LIGHT_TYPE_AREA 3

struct Light {
	vec3 position;
	uint type;

	vec3 direction;
	float energy;

	vec3 color;
	float size;

	float range;
	float attenuation;
	float cos_spot_angle;
	float inv_spot_attenuation;

	float indirect_energy;
	float shadow_blur;
	bool static_bake;
	uint pad;

	vec4 area_width;
	vec4 area_height;
	vec4 area_texture_rect;
};

layout(set = 0, binding = 4, std430) restrict readonly buffer Lights {
	Light data[];
}
lights;

struct Seam {
	uvec2 a;
	uvec2 b;
};

layout(set = 0, binding = 5, std430) restrict readonly buffer Seams {
	Seam data[];
}
seams;

layout(set = 0, binding = 6, std430) restrict readonly buffer Probes {
	vec4 data[];
}
probe_positions;

layout(set = 0, binding = 7) uniform utexture3D grid;

layout(set = 0, binding = 8) uniform texture2DArray albedo_tex;
layout(set = 0, binding = 9) uniform texture2DArray emission_tex;

layout(set = 0, binding = 10) uniform sampler linear_sampler;
layout(set = 0, binding = 11) uniform sampler area_light_atlas_sampler;

layout(set = 0, binding = 12, std430) restrict readonly buffer ClusterIndices {
	uint data[];
}
cluster_indices;

layout(set = 0, binding = 13, std430) restrict readonly buffer ClusterAABBs {
	ClusterAABB data[];
}
cluster_aabbs;

// Fragment action constants
const uint FA_NONE = 0;
const uint FA_SMOOTHEN_POSITION = 1;

layout(push_constant, std430) uniform Params {
	vec2 atlas_size;
	vec2 uv_offset;
	vec3 to_cell_size;
	uint base_triangle;
	vec3 to_cell_offset;
	float bias;
	ivec3 grid_size;
	uint pad2;
}
params;

layout(location = 0) in vec3 vertex_interp;
layout(location = 1) in vec3 normal_interp;
layout(location = 2) in vec2 uv_interp;
layout(location = 3) in vec3 barycentric;
layout(location = 4) in flat uvec3 vertex_indices;
layout(location = 5) in flat vec3 face_normal;
layout(location = 6) in flat uint fragment_action;

layout(location = 0) out vec4 position;
layout(location = 1) out vec4 normal;
layout(location = 2) out vec4 unocclude;

void main() {
	vec3 vertex_pos = vertex_interp;

	if (fragment_action == FA_SMOOTHEN_POSITION) {
		// smooth out vertex position by interpolating its projection in the 3 normal planes (normal plane is created by vertex pos and normal)
		// because we don't want to interpolate inwards, normals found pointing inwards are pushed out.
		vec3 pos_a = vertices.data[vertex_indices.x].position;
		vec3 pos_b = vertices.data[vertex_indices.y].position;
		vec3 pos_c = vertices.data[vertex_indices.z].position;
		vec3 center = (pos_a + pos_b + pos_c) * 0.3333333;
		vec3 norm_a = vec3(vertices.data[vertex_indices.x].normal_xy, vertices.data[vertex_indices.x].normal_z);
		vec3 norm_b = vec3(vertices.data[vertex_indices.y].normal_xy, vertices.data[vertex_indices.y].normal_z);
		vec3 norm_c = vec3(vertices.data[vertex_indices.z].normal_xy, vertices.data[vertex_indices.z].normal_z);

		{
			vec3 dir_a = normalize(pos_a - center);
			float d_a = dot(dir_a, norm_a);
			if (d_a < 0) {
				//pointing inwards
				norm_a = normalize(norm_a - dir_a * d_a);
			}
		}
		{
			vec3 dir_b = normalize(pos_b - center);
			float d_b = dot(dir_b, norm_b);
			if (d_b < 0) {
				//pointing inwards
				norm_b = normalize(norm_b - dir_b * d_b);
			}
		}
		{
			vec3 dir_c = normalize(pos_c - center);
			float d_c = dot(dir_c, norm_c);
			if (d_c < 0) {
				//pointing inwards
				norm_c = normalize(norm_c - dir_c * d_c);
			}
		}

		float d_a = dot(norm_a, pos_a);
		float d_b = dot(norm_b, pos_b);
		float d_c = dot(norm_c, pos_c);

		vec3 proj_a = vertex_pos - norm_a * (dot(norm_a, vertex_pos) - d_a);
		vec3 proj_b = vertex_pos - norm_b * (dot(norm_b, vertex_pos) - d_b);
		vec3 proj_c = vertex_pos - norm_c * (dot(norm_c, vertex_pos) - d_c);

		vec3 smooth_position = proj_a * barycentric.x + proj_b * barycentric.y + proj_c * barycentric.z;

		if (dot(face_normal, smooth_position) > dot(face_normal, vertex_pos)) { //only project outwards
			vertex_pos = smooth_position;
		}
	}

	{
		// unocclusion technique based on:
		// https://ndotl.wordpress.com/2018/08/29/baking-artifact-free-lightmaps/

		/* compute texel size */
		vec3 delta_uv = max(abs(dFdx(vertex_interp)), abs(dFdy(vertex_interp)));
		float texel_size = max(delta_uv.x, max(delta_uv.y, delta_uv.z));
		texel_size *= sqrt(2.0); //expand to unit box edge length (again, worst case)

		unocclude.xyz = face_normal;
		unocclude.w = texel_size;

		//continued on lm_compute.glsl
	}

	position = vec4(vertex_pos, 1.0);
	normal = vec4(normalize(normal_interp), 1.0);
}
)<!>"
};
