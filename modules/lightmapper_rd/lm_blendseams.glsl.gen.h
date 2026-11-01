/**************************************************************************/
/*  lm_blendseams.glsl.gen.h                                              */
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

static const char lm_blendseams_shader_glsl[] = {
R"<!>(#[versions]

lines = "#define MODE_LINES";
triangles = "#define MODE_TRIANGLES";

#[vertex]

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
	uint base_index;
	uint slice;
	vec2 uv_offset;
	bool debug;
	float blend;
	uint pad[2];
}
params;

layout(location = 0) out vec3 uv_interp;

void main() {
#ifdef MODE_TRIANGLES
	uint triangle_idx = params.base_index + gl_VertexIndex / 3;
	uint triangle_subidx = gl_VertexIndex % 3;

	vec2 uv;
	if (triangle_subidx == 0) {
		uv = vertices.data[triangles.data[triangle_idx].indices.x].uv;
	} else if (triangle_subidx == 1) {
		uv = vertices.data[triangles.data[triangle_idx].indices.y].uv;
	} else {
		uv = vertices.data[triangles.data[triangle_idx].indices.z].uv;
	}

	uv_interp = vec3(uv, float(params.slice));
	gl_Position = vec4((uv + params.uv_offset) * 2.0 - 1.0, 0.0001, 1.0);
#endif

#ifdef MODE_LINES
	uint seam_idx = params.base_index + gl_VertexIndex / 4;
	uint seam_subidx = gl_VertexIndex % 4;

	uint src_idx;
	uint dst_idx;

	if (seam_subidx == 0) {
		src_idx = seams.data[seam_idx].b.x;
		dst_idx = seams.data[seam_idx].a.x;
	} else if (seam_subidx == 1) {
		src_idx = seams.data[seam_idx].b.y;
		dst_idx = seams.data[seam_idx].a.y;
	} else if (seam_subidx == 2) {
		src_idx = seams.data[seam_idx].a.x;
		dst_idx = seams.data[seam_idx].b.x;
	} else if (seam_subidx == 3) {
		src_idx = seams.data[seam_idx].a.y;
		dst_idx = seams.data[seam_idx].b.y;
	}

	vec2 src_uv = vertices.data[src_idx].uv;
	vec2 dst_uv = vertices.data[dst_idx].uv + params.uv_offset;

	uv_interp = vec3(src_uv, float(params.slice));
	gl_Position = vec4(dst_uv * 2.0 - 1.0, 0.0001, 1.0);
#endif
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
	uint base_index;
	uint slice;
	vec2 uv_offset;
	bool debug;
	float blend;
	uint pad[2];
}
params;

layout(location = 0) in vec3 uv_interp;

layout(location = 0) out vec4 dst_color;

layout(set = 1, binding = 0) uniform texture2DArray src_color_tex;

void main() {
	if (params.debug) {
#ifdef MODE_TRIANGLES
		dst_color = vec4(1, 0, 1, 1);
#else
		dst_color = vec4(1, 1, 0, 1);
#endif
	} else {
		vec4 src_color = textureLod(sampler2DArray(src_color_tex, linear_sampler), uv_interp, 0.0);
		dst_color = vec4(src_color.rgb, params.blend); //mix
	}
}
)<!>"
};
