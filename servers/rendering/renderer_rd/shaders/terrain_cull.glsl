#[compute]

#version 450

#VERSION_DEFINES

// Select and compact quadtree tiles, then finalize their indirect draw count.
// Native mode writes MultiMesh transforms. The legacy path writes a node texture.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

#ifdef NATIVE_MULTIMESH
// Native 3D MultiMesh layout: three transform rows followed by INSTANCE_CUSTOM.
layout(set = 0, binding = 0, std430) writeonly buffer Instances { vec4 rows[]; } instances;
#else
layout(set = 0, binding = 0, rgba32f) uniform restrict image2D compact_nodes;
#endif
layout(set = 0, binding = 1) uniform sampler2D src_nodes;
#ifndef NATIVE_MULTIMESH
layout(set = 0, binding = 2, std430) buffer restrict Counter {
	uint counter;
}
counter_buf;
#endif

layout(push_constant, std430) uniform Params {
	mat4 vp; // view-projection of the color camera (world -> clip).
	vec4 camera_pos; // xyz = world camera position.
	vec4 params0; // x: src node texture width (texels), y: node count, z: lod0 distance (m), w: max distance (m).
	vec4 params1; // x: max lod, y: vertex spacing (m), z: compact texture width (texels), w: pad.
}
params;

uint node_count() {
	return uint(params.params0.y);
}

ivec2 src_coord_of(uint idx, float w) {
	return ivec2(int(idx % uint(w)), int(idx / uint(w)));
}

#ifdef NATIVE_MULTIMESH
layout(set = 0, binding = 3) uniform sampler2D minmax_heights;
layout(set = 0, binding = 4, std430) buffer Feedback { uint bits[]; } feedback;
layout(set = 0, binding = 5, std140) uniform Heightfield {
	vec4 domain; // World XZ origin and size.
	vec4 range; // Background min/max, displacement padding, min/max texture present.
	uvec4 grid; // Last VT mip, texels per page, terrain has VT, reserved.
} field;
layout(set = 0, binding = 6, std430) buffer Compaction { uvec4 groups[]; } compaction;

vec4 read_node(uint index) {
	return texelFetch(src_nodes, src_coord_of(index, params.params0.x), 0);
}

vec2 tile_heights(vec2 origin, float size) {
	if (field.range.w == 0.0) {
		return field.range.xy;
	}
	vec2 uv0 = (origin - field.domain.xy) / field.domain.zw;
	vec2 uv1 = (origin + size - field.domain.xy) / field.domain.zw;
	if (any(lessThan(uv1, vec2(0))) || any(greaterThanEqual(uv0, vec2(1)))) {
		return field.range.xy;
	}
	int last_mip = textureQueryLevels(minmax_heights) - 1;
	float texels = max(size / field.domain.z, size / field.domain.w) * float(textureSize(minmax_heights, 0).x);
	int mip = clamp(int(ceil(log2(max(texels, 1.0)))), 0, last_mip);
	ivec2 dim = textureSize(minmax_heights, mip);
	ivec2 a = clamp(ivec2(floor(uv0 * vec2(dim))), ivec2(0), dim - 1);
	ivec2 b = clamp(ivec2(ceil(uv1 * vec2(dim))) - 1, a, dim - 1);
	vec2 h0 = texelFetch(minmax_heights, a, mip).rg;
	vec2 h1 = texelFetch(minmax_heights, b, mip).rg;
	vec2 h2 = texelFetch(minmax_heights, ivec2(a.x,b.y), mip).rg;
	vec2 h3 = texelFetch(minmax_heights, ivec2(b.x,a.y), mip).rg;
	vec2 h = vec2(min(min(h0.x,h1.x), min(h2.x,h3.x)), max(max(h0.y,h1.y), max(h2.y,h3.y)));
	if (any(lessThan(uv0, vec2(0))) || any(greaterThan(uv1, vec2(1)))) {
		h = vec2(min(h.x, field.range.x), max(h.y, field.range.y));
	}
	return h;
}

float view_scale() {
	return params.camera_pos.w > 3.0 ? params.camera_pos.w - 3.0 : params.camera_pos.w;
}

float distance_to_tile(vec2 origin, float size, vec2 h) {
	vec2 xz = params.camera_pos.xz - clamp(params.camera_pos.xz, origin, origin + size);
	float y = params.camera_pos.w > 3.0 ? 0.0 : params.camera_pos.y - clamp(params.camera_pos.y, h.x - field.range.z, h.y + field.range.z);
	return length(vec3(xz, y));
}

bool subdivide(vec2 origin, float size, float level, float radius) {
	return level > 0.0 && (level > params.params1.x ||
			distance_to_tile(origin, size, tile_heights(origin, size)) < radius * exp2(level - 1.0));
}

bool outside_frustum(vec4 tile, vec2 heights) {
	if (params.params1.w == 0.0) {
		return false; // Dual-paraboloid shadows use a conservative cut.
	}
	vec3 center = vec3(tile.x + 0.5 * tile.z, 0.5 * (heights.x + heights.y), tile.y + 0.5 * tile.z);
	vec3 extent = vec3(0.5 * tile.z, 0.5 * (heights.y - heights.x), 0.5 * tile.z) + field.range.z;
	mat4 rows = transpose(params.vp);
	for (int axis = 0; axis < 3; axis++) {
		vec4 plus = rows[3] + rows[axis];
		vec4 minus = rows[3] - rows[axis];
		// A directional light's "pancake" shadow accepts occluders before its near plane.
		if ((axis != 2 || params.params1.w != 2.0) && dot(plus, vec4(center, 1.0)) + dot(abs(plus.xyz), extent) < 0.0) {
			return true;
		}
		if (dot(minus, vec4(center, 1.0)) + dot(abs(minus.xyz), extent) < 0.0) {
			return true;
		}
	}
	return false;
}

float distance_mip(float d, float radius) {
	float normalized = d / radius;
	float band = normalized < 1.0 ? 0.0 : floor(log2(normalized)) + 1.0;
	float geometry_lod = min(params.params1.x, band + smoothstep(0.86, 1.0, normalized * exp2(-band)));
	float texels_per_cell = float((1u << field.grid.x) * field.grid.y) * params.params1.y / field.domain.z;
	return clamp(geometry_lod + log2(texels_per_cell), 0.0, float(field.grid.x));
}

void request_pages(vec4 tile, vec2 h, float radius) {
	if (field.grid.z == 0u) {
		return;
	}
	vec2 uv0 = (tile.xy - field.domain.xy) / field.domain.zw;
	vec2 uv1 = (tile.xy + tile.z - field.domain.xy) / field.domain.zw;
	if (any(lessThan(uv1, vec2(0))) || any(greaterThanEqual(uv0, vec2(1)))) {
		return;
	}
	vec2 eye = params.camera_pos.xz;
	float near_d = length(eye - clamp(eye, tile.xy, tile.xy + tile.z));
	vec2 far_xz = max(abs(eye - tile.xy), abs(eye - tile.xy - tile.z));
	float far_y = params.camera_pos.w > 3.0 ? 0.0 : max(abs(params.camera_pos.y - h.x), abs(params.camera_pos.y - h.y)) + field.range.z;
	int first = int(floor(distance_mip(near_d, radius)));
	int last = int(ceil(distance_mip(length(vec3(far_xz, far_y)), radius)));
	uint base_side = 1u << field.grid.x;
	// Bitsets are dense by mip, fine to coarse. Duplicate requests collapse on the GPU.
	uint offset = (base_side * base_side * 4u - (base_side >> first) * (base_side >> first) * 4u) / 3u;
	float ratio = float(base_side * field.grid.y) * params.params1.y / field.domain.z;
	for (int mip = first; mip <= last; ++mip) {
		int side = int(base_side) >> mip;
		ivec2 a = clamp(ivec2(floor(uv0 * float(side))), ivec2(0), ivec2(side - 1));
		ivec2 b = clamp(ivec2(floor(uv1 * float(side))), ivec2(0), ivec2(side - 1));
		// Bound fine requests for very large quads viewed from high above.
		if (mip < int(field.grid.x) && float(mip) < ceil(params.params1.x + log2(ratio))) {
			float reach = radius * exp2(float(mip + 1)) / ratio + params.params1.y;
			a = max(a, ivec2(floor((eye - reach - field.domain.xy) * float(side) / field.domain.zw)));
			b = min(b, ivec2(floor((eye + reach - field.domain.xy) * float(side) / field.domain.zw)));
		}
		for (int y = a.y; y <= b.y; ++y) {
			for (int x = a.x; x <= b.x; ++x) {
				uint index = offset + uint(y * side + x);
				atomicOr(feedback.bits[index >> 5u], 1u << (index & 31u));
			}
		}
		offset += uint(side * side);
	}
}

// Walk the adjacent cell's ancestors in integer grid coordinates. This keeps a
// shared edge on the same parent even when vertex spacing is not a power of two.
float neighbor_stride(ivec2 cell, vec4 tile, vec4 root, float radius) {
	int width = int(round(root.z / tile.z));
	if (any(lessThan(cell, ivec2(0))) || any(greaterThanEqual(cell, ivec2(width)))) {
		return 1.0;
	}
	float size = tile.z;
	for (float level = tile.w + 1.0; level <= root.w; level += 1.0) {
		cell /= 2;
		size *= 2.0;
		if (subdivide(root.xy + vec2(cell) * size, size, level, radius)) {
			break;
		}
		float parent_size = 2.0 * size;
		if (level == root.w || subdivide(root.xy + vec2(cell / 2) * parent_size, parent_size, level + 1.0, radius)) {
			return size / tile.z;
		}
	}
	return 1.0;
}

bool find_candidate(uint id, out vec4 root, out ivec2 cell, out vec4 tile) {
	if (id >= node_count()) {
		return false;
	}
	int root_index = int(params.params0.x) - 1;
	root = read_node(uint(root_index));
	int index = root_index - 1;
	vec4 desc = read_node(uint(index));
	while (id < uint(desc.y)) {
		desc = read_node(uint(--index));
	}
	uint width = uint(abs(desc.x));
	uint offset = id - uint(desc.y);
	cell = ivec2(offset % width, offset / width);
	if (desc.x > 0.0) {
		cell += ivec2(floor((params.camera_pos.xz - root.xy) / desc.z)) - ivec2(width / 2u);
		if (any(lessThan(cell, ivec2(0))) || any(greaterThanEqual(cell, ivec2(round(root.z / desc.z))))) {
			return false;
		}
	}
	tile = vec4(root.xy + vec2(cell) * desc.z, desc.zw);
	return true;
}

bool select_tile(vec4 root, ivec2 cell, vec4 tile, float radius) {
	vec2 h = tile_heights(tile.xy, tile.z);
	float distance = distance_to_tile(tile.xy, tile.z, h);
	if (distance > params.params0.w || (tile.w > 0.0 && distance < radius * exp2(tile.w - 1.0))) {
		return false;
	}
	if (tile.w < root.w) {
		float parent_size = 2.0 * tile.z;
		vec2 parent = root.xy + vec2(cell / 2) * parent_size;
		if (!subdivide(parent, parent_size, tile.w + 1.0, radius)) {
			return false;
		}
	}
	if (outside_frustum(tile, h)) {
		return false;
	}
	request_pages(tile, h, radius);
	return true;
}

shared uint masks[2];

void main() {
	uint group = gl_WorkGroupID.x + gl_WorkGroupID.y * gl_NumWorkGroups.x;
	uint lane = gl_LocalInvocationIndex;
	if (group >= (node_count() + 63u) / 64u) {
		return;
	}
	uint id = group * 64u + lane;
	vec4 root, tile;
	ivec2 cell;
	if (params.params1.w >= 4.0) {
		uvec4 record = compaction.groups[group];
		uint mask = lane < 32u ? record.x : record.y;
		uint bit = 1u << (lane & 31u);
		if ((mask & bit) == 0u || !find_candidate(id, root, cell, tile)) {
			return;
		}
		uint group_count = (node_count() + 63u) / 64u;
		uint slot = record.w + compaction.groups[group_count + group / 256u].w;
		slot += (lane < 32u ? 0u : uint(bitCount(record.x))) + uint(bitCount(mask & (bit - 1u)));
		if (slot >= uint(params.params1.z)) {
			return;
		}
		float radius = max(params.params0.z, 4.0 * tile.z * exp2(-tile.w)) * view_scale();
		float scale = params.params1.y * exp2(tile.w);
		instances.rows[4u * slot] = vec4(scale, 0.0, 0.0, tile.x);
		instances.rows[4u * slot + 1u] = vec4(0.0, params.camera_pos.w, 0.0, 0.0);
		instances.rows[4u * slot + 2u] = vec4(0.0, 0.0, scale, tile.y);
		instances.rows[4u * slot + 3u] = vec4(
				neighbor_stride(cell - ivec2(1, 0), tile, root, radius),
				neighbor_stride(cell + ivec2(1, 0), tile, root, radius),
				neighbor_stride(cell - ivec2(0, 1), tile, root, radius),
				neighbor_stride(cell + ivec2(0, 1), tile, root, radius));
		return;
	}
	if (lane < 2u) {
		masks[lane] = 0u;
	}
	barrier();
	if (find_candidate(id, root, cell, tile)) {
		float radius = max(params.params0.z, 4.0 * tile.z * exp2(-tile.w)) * view_scale();
		if (select_tile(root, cell, tile, radius)) {
			atomicOr(masks[lane >> 5u], 1u << (lane & 31u));
		}
	}
	barrier();
	if (lane == 0u) {
		compaction.groups[group] = uvec4(masks[0], masks[1], bitCount(masks[0]) + bitCount(masks[1]), 0u);
	}
}
#else
void main() {
	uint nidx = gl_GlobalInvocationID.x + gl_WorkGroupID.y * gl_NumWorkGroups.x * gl_WorkGroupSize.x;
	if (nidx >= node_count()) {
		return;
	}

	float src_w = params.params0.x;
	ivec2 c0 = src_coord_of(nidx * 3u, src_w);
	ivec2 c1 = src_coord_of(nidx * 3u + 1u, src_w);
	ivec2 c2 = src_coord_of(nidx * 3u + 2u, src_w);
	vec4 n0 = texelFetch(src_nodes, c0, 0);
	vec4 n1 = texelFetch(src_nodes, c1, 0);
	vec4 n2 = texelFetch(src_nodes, c2, 0);

	vec3 mn = vec3(n0.x, n1.x, n0.y);
	vec3 mx = vec3(n0.x + n0.z, n1.y, n0.y + n0.z);

	// Frustum culling is disabled for now: the compacted set is shared between the color and the
	// shadow passes, and the shadow pass must keep tiles outside the main frustum that still cast
	// shadows into the view. Distance + LOD culling already bound the tile count.
	bool frustum_ok = true;
	if (false) {
		// n-vertex test against the four side planes, plus an all-behind rejection. Re-enable once
		// the shadow pass gets its own per-pass compact list.
		mat4 vp = params.vp;
		vec4 pL = vec4(vp[0][3] + vp[0][0], vp[1][3] + vp[1][0], vp[2][3] + vp[2][0], vp[3][3] + vp[3][0]);
		vec4 pR = vec4(vp[0][3] - vp[0][0], vp[1][3] - vp[1][0], vp[2][3] - vp[2][0], vp[3][3] - vp[3][0]);
		vec4 pB = vec4(vp[0][3] + vp[0][1], vp[1][3] + vp[1][1], vp[2][3] + vp[2][1], vp[3][3] + vp[3][1]);
		vec4 pT = vec4(vp[0][3] - vp[0][1], vp[1][3] - vp[1][1], vp[2][3] - vp[2][1], vp[3][3] - vp[3][1]);

		bool all_behind = true;
		for (int ci = 0; ci < 8; ci++) {
			vec3 p = vec3((ci & 1) != 0 ? mx.x : mn.x, (ci & 2) != 0 ? mx.y : mn.y, (ci & 4) != 0 ? mx.z : mn.z);
			vec4 c = vp * vec4(p, 1.0);
			all_behind = all_behind && c.w < 0.0;
		}

		bool side_ok = true;
		vec4 s_planes[4];
		s_planes[0] = pL;
		s_planes[1] = pR;
		s_planes[2] = pB;
		s_planes[3] = pT;
		for (int pl = 0; pl < 4; pl++) {
			vec4 sp = s_planes[pl];
			vec3 pv = vec3(sp.x > 0.0 ? mx.x : mn.x, sp.y > 0.0 ? mx.y : mn.y, sp.z > 0.0 ? mx.z : mn.z);
			if (dot(sp.xyz, pv) + sp.w < 0.0) {
				side_ok = false;
				break;
			}
		}
		frustum_ok = !all_behind && side_ok;
	}

	vec2 tc = vec2(n0.x + n0.z * 0.5, n0.y + n0.z * 0.5);
	float dist_cam = length(params.camera_pos.xz - tc);

	// Distance culling.
	if (dist_cam >= max(params.params0.w, n0.z)) {
		return;
	}

	// Distance LOD selection: LOD0 inside lod0_distance meters, doubling per level.
	float lodf = clamp(floor(log2(max(dist_cam / max(params.params0.z, 1.0), 1.0))), 0.0, params.params1.x);
	if (lodf != n0.w) {
		return;
	}

	uint slot = atomicAdd(counter_buf.counter, 1u);
	float compact_w = params.params1.z;
	if (slot >= uint(compact_w)) {
		return; // Compact pool exhausted (visible nodes capped at the compact texture width).
	}
	imageStore(compact_nodes, src_coord_of(slot * 3u, compact_w), n0);
	imageStore(compact_nodes, src_coord_of(slot * 3u + 1u, compact_w), n1);
	imageStore(compact_nodes, src_coord_of(slot * 3u + 2u, compact_w), n2);
}
#endif
