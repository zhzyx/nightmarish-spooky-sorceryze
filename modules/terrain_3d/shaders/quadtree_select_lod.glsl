// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.
// Terrain3D runtime V2 (VHM-style quadtree, GPU driven). This file is loaded as a raw string
// into Terrain3DMaterial's shader code database (same pattern as the other src/shaders/*.glsl).

R"(
#[compute]

#version 450

#VERSION_DEFINES

// Selects quadtree tiles for the current camera: screen-space LOD selection from the min/max
// pyramid, frustum culling, compaction into the visible instance buffer and an atomic draw count.

#define GROUPS 64u

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// Tile buffer (std430):
//   vec4 data0: x, z (world origin), size (meters), lod (float)
//   vec4 data1: min_y, max_y, neighbor_lod N, neighbor_lod E
//   vec4 data2: neighbor_lod S, neighbor_lod W, flags, pad
layout(set = 0, binding = 0, std430) restrict readonly buffer Tiles {
	vec4 tile_data[];
}
tiles;

// Visible instance output. One entry per visible tile:
//   vec4 inst0: x, z (origin), scale (vertex_spacing * 2^lod), lod (float)
//   vec4 inst1: min_y, max_y, neighbor_lods pack N/E/S/W
layout(set = 0, binding = 1, std430) restrict writeonly buffer Visible {
	vec4 visible_data[];
}
visible;

// Atomic counter of visible tiles (offset 0), clear to 0 before the dispatch.
layout(set = 0, binding = 2, std430) buffer Count {
	uint count;
}
count;

// DrawElementsIndirect command: indexCount, instanceCount, firstIndex, vertexOffset, firstInstance.
layout(set = 0, binding = 3, std430) buffer DrawArgs {
	uint args[5];
}
draw_args;

layout(set = 0, binding = 4) uniform sampler2D minmax_texture; // R32G32F: x = min height, y = max height.

layout(push_constant, std430) uniform Params {
	mat4 view_projection; // World -> clip.
	vec4 frustum[6]; // Outward facing planes in world space.
	vec4 camera_pos; // xyz = camera position, w = viewport height in pixels.
	vec4 lod_params; // x = LOD0 cell target screen size (px), y = max lod, z = vertex_spacing, w = minmax level 0 texels per side.
	vec4 terrain_aabb; // x, z = origin; y = min height, w = max height; and size in... (see below)
	vec4 terrain_extent; // x = world size (meters), y = min height, z = max height, w = debug mode.
}
params;

uint visible_index() {
	return atomicAdd(count.count, 1u);
}

void main() {
	uint tile_index = gl_GlobalInvocationID.x;
	if (tile_index >= tiles.tile_data.length()) {
		return;
	}

	vec4 d0 = tiles.tile_data[tile_index * 3u + 0u];
	vec4 d1 = tiles.tile_data[tile_index * 3u + 1u];
	vec4 d2 = tiles.tile_data[tile_index * 3u + 2u];

	// Tile world box.
	vec2 origin = d0.xy;
	float size = d0.z;
	float min_y = d1.x;
	float max_y = d1.y;

	// Frustum test on the tile AABB.
	vec3 center = vec3(origin.x + size * 0.5, (min_y + max_y) * 0.5, origin.y + size * 0.5);
	vec3 extent = vec3(size * 0.5, max(max_y - min_y, 0.5) * 0.5, size * 0.5);
	for (int p = 0; p < 6; p++) {
		vec4 pl = params.frustum[p];
		vec3 n = pl.xyz;
		float r = dot(abs(n), extent);
		float s = dot(n, center) + pl.w;
		if (s + r < 0.0) {
			return; // Fully outside.
		}
	}

	// Screen-space size of the LOD0 cell: project the tile AABB corners and take the longest
	// projected edge, clamped against degenerate projections.
	float lod0_cell = params.lod_params.z; // meters per vertex at LOD0.
	float texels = (params.lod_params.w > 0.0) ? (size / lod0_cell) : 1.0;

	// Conservative screen size: project center and center + max(x, z) extent.
	vec4 c0 = params.view_projection * vec4(center, 1.0);
	if (c0.w <= 0.0) {
		return; // Behind camera.
	}
	vec3 cndc = c0.xyz / c0.w;
	float dx = extent.x + extent.z;
	vec4 c1 = params.view_projection * vec4(center + vec3(dx, 0.0, dx), 1.0);
	vec3 c1ndc = c1.xyz / max(c1.w, 1e-6);
	float pixel_extent = length((c1ndc.xy - cndc.xy)) * 0.5 * params.camera_pos.w;
	// Pixels per LOD0 cell.
	float px_per_cell = max(pixel_extent / max(texels, 1.0), 1e-4);
	float target = max(params.lod_params.x, 1.0);

	float lod = clamp(floor(log2(px_per_cell / target)), 0.0, params.lod_params.y);
	if (lod > log2(max(size / lod0_cell, 1.0))) {
		lod = floor(log2(max(size / lod0_cell, 1.0))); // Cannot be coarser than the tile itself.
	}

	// Compaction.
	uint slot = visible_index();
	visible.visible_data[slot * 2u + 0u] = vec4(origin.x, origin.y, lod0_cell * exp2(lod), lod);
	visible.visible_data[slot * 2u + 1u] = vec4(min_y, max_y, float(d1.z) + float(d1.w) * 4.0, float(d2.x) + float(d2.y) * 16.0);
}
)"
