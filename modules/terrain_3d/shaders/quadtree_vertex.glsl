// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.
// Terrain3D runtime V2: VHM-style quadtree GPU-driven vertex path.
// Blocks are merged into main.glsl by Terrain3DMaterial (same mechanism as backgrounds.glsl).

R"(
//INSERT: QUADTREE_FUNCTIONS
float t3d_native_height(vec2 pos) {
	ivec3 coord = get_index_coord(pos);
	return coord.z >= 0 ? texelFetch(_height_maps, coord, 0).r : 0.0;
}

//INSERT: HEIGHT_VT_FUNCTIONS
float t3d_physical_height(vec2 uv, ivec4 entry) {
	float resident_pages = float(int(_t3d_vt_layout.x) >> entry.b);
	float tile = _t3d_vt_layout.z;
	int border = int(_t3d_vt_layout.w);
	vec2 local_texel = fract(uv * resident_pages) * tile;
	ivec2 base = entry.rg * (int(tile) + 2 * border) + ivec2(border) + ivec2(floor(local_texel));
	vec2 f = fract(local_texel);
	float h = texelFetch(_t3d_vt_physical0, base, 0).r;
	if (f == vec2(0.0)) {
		return h;
	}
	return mix(mix(h, texelFetch(_t3d_vt_physical0, base + ivec2(1, 0), 0).r, f.x),
			mix(texelFetch(_t3d_vt_physical0, base + ivec2(0, 1), 0).r,
					texelFetch(_t3d_vt_physical0, base + ivec2(1), 0).r, f.x), f.y);
}

// RG selects the physical page, B identifies its resident mip and A fades in a
// new mapping. The pinned root terminates the chain even with a minimal pool.
vec2 t3d_height_level(vec2 uv, int requested_level) {
	int level = requested_level;
	int last_level = int(_t3d_vt_layout.y);
	float height = 0.0;
	float weight = 1.0;
	for (int i = 0; i <= last_level; i++) {
		int pages = int(_t3d_vt_layout.x) >> level;
		ivec2 coord = ivec2(floor(uv * float(pages)));
		ivec4 entry = ivec4(round(texelFetch(_t3d_vt_page_table, coord, level) * 255.0));
		if (entry.a > 0 && entry.b >= level && entry.b <= last_level) {
			float blend = entry.b == last_level ? 1.0 : float(entry.a) / 255.0;
			height += weight * blend * t3d_physical_height(uv, entry);
			if (blend == 1.0) {
				return vec2(height, entry.b == requested_level ? 1.0 : 2.0);
			}
			weight *= 1.0 - blend;
			level = entry.b;
		}
		level++;
		if (level > last_level) {
			break;
		}
	}
	return vec2(height, -2.0);
}

vec2 t3d_vt_sample(vec2 pos, float geometry_lod) {
	vec2 uv = (pos - _t3d_vt_grid.xy) / _t3d_vt_grid.z;
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) {
		return vec2(0.0, -1.0); // Authored regions end here; the background shader supplies the surface.
	}
	float texels_per_cell = _t3d_vt_layout.x * _t3d_vt_layout.z / _t3d_vt_grid.z;
	float mip = clamp(geometry_lod + log2(texels_per_cell), 0.0, _t3d_vt_layout.y);
	vec2 a = t3d_height_level(uv, int(floor(mip)));
	if (fract(mip) == 0.0) {
		return a;
	}
	vec2 b = t3d_height_level(uv, int(ceil(mip)));
	return vec2(mix(a.x, b.x, fract(mip)), min(a.y, b.y) < 0.0 ? -2.0 : max(a.y, b.y));
}

//INSERT: QUADTREE_VIEW_FUNCTIONS
float t3d_continuous_lod(float distance_ratio) {
	float band = distance_ratio < 1.0 ? 0.0 : floor(log2(max(distance_ratio, 1.0))) + 1.0;
	return band + smoothstep(0.86, 1.0, distance_ratio * exp2(-band));
}

// Shadow and color passes use the same main-view distance for a shared vertex.
// Estimate its elevation before choosing a mip; perspective includes height above the ground.
float t3d_view_distance(vec2 grid, vec2 world_xz, vec3 camera, float radius, bool ortho) {
	vec2 delta = world_xz - camera.xz;
	float planar = length(delta);
	if (ortho) {
		return planar;
	}
	float h = _t3d_vt_grid.w > 0.5 ? t3d_vt_sample(grid, t3d_continuous_lod(planar / radius)).x : t3d_native_height(grid);
	return length(vec3(delta, h - camera.y));
}

//INSERT: QUADTREE_UNIFORMS
uniform float _t3d_mode = 0.0;
uniform vec4 _t3d_draw_bounds; // Terrain vertex-grid limits of the outer native clipmap ring.
uniform float _t3d_lod0_distance = 256.0;
uniform int _t3d_last_lod = 8;
uniform float _t3d_tile_res = 32.0;
//INSERT: HEIGHT_VT_UNIFORMS
uniform sampler2D _t3d_vt_page_table : repeat_disable, filter_nearest;
uniform sampler2D _t3d_vt_physical0 : repeat_disable, filter_nearest;
uniform vec4 _t3d_vt_grid; // origin in grid cells, extent in cells, enabled
uniform vec4 _t3d_vt_layout; // base pages per axis, last mip, page texels, border

//INSERT: QUADTREE_VERTEX_HEAD
		vec2 local = VERTEX.xz;
		float res = _t3d_tile_res;
		float x_stride = local.x == 0.0 ? INSTANCE_CUSTOM.x : (local.x == res ? INSTANCE_CUSTOM.y : 1.0);
		float z_stride = local.y == 0.0 ? INSTANCE_CUSTOM.z : (local.y == res ? INSTANCE_CUSTOM.w : 1.0);
		local.y = floor(local.y / x_stride) * x_stride;
		local.x = floor(local.x / z_stride) * z_stride;
		float tile_scale = MODEL_MATRIX[0][0];
		float scale = tile_scale * max(x_stride, z_stride);
		float lod_scale = scale * _vertex_density;
		float sample_lod = round(log2(lod_scale));
		vec2 world_xz = MODEL_MATRIX[3].xz + local * tile_scale;
		vec2 start_pos = round(world_xz * _vertex_density);
		vec2 end_pos = start_pos - mod(round(local * tile_scale / scale), 2.0) * lod_scale;
		if (_t3d_draw_bounds.z > _t3d_draw_bounds.x) {
			start_pos = clamp(start_pos, _t3d_draw_bounds.xy, _t3d_draw_bounds.zw);
			end_pos = clamp(end_pos, _t3d_draw_bounds.xy, _t3d_draw_bounds.zw);
			world_xz = start_pos * _vertex_spacing;
		}
		float view_scale = MODEL_MATRIX[1][1];
		bool ortho = view_scale > 3.0;
		float lod0_radius = _t3d_lod0_distance * (ortho ? view_scale - 3.0 : view_scale);
		float radius = lod0_radius * lod_scale;
		float start_distance = t3d_view_distance(start_pos, world_xz, v_camera_pos, lod0_radius, ortho);
		float vertex_lerp = sample_lod < float(_t3d_last_lod) ?
				smoothstep(0.86 * radius, radius, start_distance) : 0.0;
		UV = mix(start_pos, end_pos, vertex_lerp);
		UV2 = fma(UV, vec2(_region_texel_size), vec2(0.5 * _region_texel_size));
		v_vertex.xz = UV * _vertex_spacing;
		v_vertex_xz_dist = length(v_vertex.xz - _target_pos.xz);
		ivec3 v_region = get_index_coord(start_pos);
		uint control = get_control_bits(v_region);
		bool hole = DECODE_HOLE(control);
		bool none_bg = false;
		float h;
		if (_t3d_vt_grid.w > 0.5) {
			// Shared vertices choose the same mip from the morphed world position,
			// independently of the tile (or shadow pass) submitting them.
			float distance_to_view = t3d_view_distance(UV, v_vertex.xz, v_camera_pos, lod0_radius, ortho);
			float geo_lod = min(float(_t3d_last_lod), t3d_continuous_lod(distance_to_view / lod0_radius));
			h = t3d_vt_sample(UV, geo_lod).x;
		} else {
			h = mix(t3d_native_height(start_pos), t3d_native_height(end_pos), vertex_lerp);
		}

//INSERT: QUADTREE_NONE_CHECK
		none_bg = (_background_mode == 0u && is_none_bg(UV));

//INSERT: QUADTREE_VERTEX_TAIL
		if (hole || none_bg) {
			v_vertex.x = 0.0 / 0.0;
		}
		v_vertex.y = h;
)"
