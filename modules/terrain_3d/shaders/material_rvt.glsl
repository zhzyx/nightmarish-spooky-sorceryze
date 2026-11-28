// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

R"(
//INSERT: MATERIAL_RVT_READER
#ifdef T3D_MATERIAL_RVT_READER
uniform vec4 _t3d_material_rvt_grid; // world origin XZ, square side in metres, active
uniform vec4 _t3d_material_rvt_layout; // pages per side, last mip, tile size, border
uniform sampler2D _t3d_material_rvt_table : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_color : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_surface : repeat_disable, filter_nearest;
uniform vec4 _t3d_material_rvt_far_grid;
uniform vec4 _t3d_material_rvt_far_layout;
uniform float _t3d_material_rvt_far_bias;
uniform sampler2D _t3d_material_rvt_far_table : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_far_color : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_far_surface : repeat_disable, filter_nearest;
uniform vec4 _t3d_material_rvt_detail_grid;
uniform vec4 _t3d_material_rvt_detail_layout;
uniform vec2 _t3d_material_rvt_detail_limits; // camera radius, maximum world footprint
uniform sampler2D _t3d_material_rvt_detail_table : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_detail_color : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_detail_surface : repeat_disable, filter_nearest;
#ifdef T3D_DUAL_SCALING
uniform sampler2D _t3d_material_rvt_detail_far_table : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_detail_far_color : repeat_disable, filter_nearest;
uniform sampler2D _t3d_material_rvt_detail_far_surface : repeat_disable, filter_nearest;
#endif
uniform bool _t3d_material_rvt_debug = false;
uniform bool _t3d_material_rvt_sources = false;
uniform int _t3d_material_rvt_channel = 0;
uniform bool _t3d_material_rvt_bypass = false;

struct CachedTerrainSurface {
	vec4 color_wetness;
	vec3 world_normal;
	vec3 geom_normal;
	vec3 roughness_ao_affect;
	float disk_weight;
	float detail_confidence; // Fine page residency and arrival fade.
};

vec3 t3d_rvt_oct_decode(vec2 oct) {
	vec3 n = vec3(oct.x, 1.0 - abs(oct.x) - abs(oct.y), oct.y);
	n.xz += mix(vec2(1.0), vec2(-1.0), greaterThanEqual(n.xz, vec2(0.0))) * max(-n.y, 0.0);
	return normalize(n);
}

CachedTerrainSurface t3d_rvt_unpack(vec4 color, vec4 surface) {
	vec3 linear_color = mix(pow((color.rgb + 0.055) / 1.055, vec3(2.4)), color.rgb / 12.92, lessThanEqual(color.rgb, vec3(0.04045)));
	uvec2 normals = uvec2(round(surface.rg * 65535.0));
	vec3 mapped = t3d_rvt_oct_decode(vec2(normals >> uvec2(6u)) * (2.0 / 1023.0) - 1.0);
	vec3 geom = t3d_rvt_oct_decode(vec2(normals & uvec2(63u)) * (2.0 / 63.0) - 1.0);
	uint packed = uint(round(surface.a * 65535.0));
	return CachedTerrainSurface(vec4(linear_color, color.a * 2.0 - 1.0), mapped, geom, vec3(surface.b, float(packed >> 8u) / 255.0, float(packed & 255u) / 255.0), 0.0, 1.0);
}

CachedTerrainSurface t3d_rvt_filter(CachedTerrainSurface a, CachedTerrainSurface b, float f) {
	return CachedTerrainSurface(mix(a.color_wetness, b.color_wetness, f), mix(a.world_normal, b.world_normal, f), mix(a.geom_normal, b.geom_normal, f), mix(a.roughness_ao_affect, b.roughness_ao_affect, f), mix(a.disk_weight, b.disk_weight, f), min(a.detail_confidence, b.detail_confidence));
}

ivec4 t3d_rvt_page(sampler2D table, vec4 layout_info, vec2 uv, int level) {
	int pages = int(layout_info.x) >> level;
	return ivec4(round(texelFetch(table, ivec2(uv * float(pages)), level) * 255.0));
}

CachedTerrainSurface t3d_rvt_physical(sampler2D color, sampler2D surface, vec4 layout_info, vec2 uv, ivec4 entry) {
	// Descendant entries already point at their nearest resident ancestor. Its mip
	// determines the texel coordinates as well as the origin bit of the sampled page.
	int page_count = int(layout_info.x) >> entry.b;
	float tile = layout_info.z;
	float border = layout_info.w;
	vec2 texel = vec2(entry.rg) * (tile + 2.0 * border) + border + fract(uv * float(page_count)) * tile - 0.5;
	ivec2 xy = ivec2(floor(texel));
	vec2 f = fract(texel);
	CachedTerrainSurface a = t3d_rvt_unpack(texelFetch(color, xy, 0), texelFetch(surface, xy, 0));
	CachedTerrainSurface b = t3d_rvt_unpack(texelFetch(color, xy + ivec2(1,0), 0), texelFetch(surface, xy + ivec2(1,0), 0));
	CachedTerrainSurface c = t3d_rvt_unpack(texelFetch(color, xy + ivec2(0,1), 0), texelFetch(surface, xy + ivec2(0,1), 0));
	CachedTerrainSurface d = t3d_rvt_unpack(texelFetch(color, xy + ivec2(1), 0), texelFetch(surface, xy + ivec2(1), 0));
	CachedTerrainSurface result = t3d_rvt_filter(t3d_rvt_filter(a,b,f.x), t3d_rvt_filter(c,d,f.x), f.y);
	result.disk_weight = float((entry.a & 1) == 0);
	return result;
}

bool t3d_rvt_sample_surface(sampler2D table, sampler2D color, sampler2D surface, vec4 layout_info, vec2 uv, float lod, out CachedTerrainSurface result) {
	if (textureSize(table, 0).x != int(layout_info.x)) {
		return false;
	}
	int level = int(floor(lod));
	ivec4 fine = t3d_rvt_page(table, layout_info, uv, level);
	if (fine.a < 2) {
		return false;
	}
	result = t3d_rvt_physical(color, surface, layout_info, uv, fine);
	float fade = float(fine.a >> 1) / 127.0;
	float coarse_weight = max(1.0 - fade, fine.b == level ? fract(lod) : 0.0);
	float quality = clamp(1.0 - 0.5 * float(fine.b - level - 1), 0.0, 1.0);
	float confidence = fade * quality;
	if (coarse_weight > 0.0 && fine.b < int(layout_info.y)) {
		ivec4 coarse = t3d_rvt_page(table, layout_info, uv, fine.b + 1);
		if (coarse.a >= 2) {
			result = t3d_rvt_filter(result, t3d_rvt_physical(color, surface, layout_info, uv, coarse), coarse_weight);
			// A resident trilinear parent already supplies useful local detail during
			// arrival. Fading to the world atlas again would blur a moving view twice.
			float parent_quality = clamp(1.0 - 0.5 * float(coarse.b - level - 1), 0.0, 1.0);
			confidence = mix(quality, parent_quality, coarse_weight);
		}
	}
	result.detail_confidence = confidence;
	return true;
}

bool t3d_rvt_footprint(sampler2D table, sampler2D color, sampler2D data, vec4 layout_info, vec2 uv, vec2 span, int taps, float lod, out CachedTerrainSurface surface) {
	for (int i = 0; i < taps; i++) {
		vec2 sample_uv = clamp(uv + span * ((float(i) + 0.5) / float(taps) - 0.5), vec2(0.0), vec2(0.99999994));
		CachedTerrainSurface tap;
		if (!t3d_rvt_sample_surface(table, color, data, layout_info, sample_uv, lod, tap)) {
			return false;
		}
		if (i == 0) {
			surface = tap;
		} else {
			surface = t3d_rvt_filter(surface, tap, 1.0 / float(i + 1));
		}
	}
	return true;
}

// Return the major-axis span in metres and the effective texel footprint used by GPU feedback.
vec2 t3d_rvt_kernel(vec2 dx, vec2 dy, float pixels_per_meter, out int taps, out float footprint) {
	footprint = max(length(dx), length(dy)) * pixels_per_meter;
	taps = 1;
	vec2 span = vec2(0.0);
#ifdef TERRAIN_FILTER_ANISOTROPIC
	// Sample the footprint along its major axis. Choosing a single isotropic mip on
	// slopes would erase across-slope detail even though the source uses textureGrad.
	float xx = dot(dx,dx);
	float yy = dot(dy,dy);
	float xy = dot(dx,dy);
	float lambda = 0.5 * (xx + yy + length(vec2(xx - yy, 2.0 * xy)));
	float major = sqrt(max(lambda, 1e-12));
	float minor = abs(dx.x * dy.y - dx.y * dy.x) / major;
	float ratio = major / max(minor, 1.0 / pixels_per_meter);
	taps = clamp(int(ceil(ratio - 0.0001)), 1, 4);
	if (taps > 1) {
		vec2 axis = (xx >= yy) ? dx * (lambda - yy) + dy * xy : dx * xy + dy * (lambda - xx);
		span = normalize(axis) * major;
	}
	footprint = max(minor, major / float(taps)) * pixels_per_meter;
#endif
	return span;
}

bool t3d_rvt_endpoint(sampler2D table, sampler2D color, sampler2D data, vec4 grid, vec4 layout_info, float bias, vec2 pos, vec2 dx, vec2 dy, out CachedTerrainSurface surface) {
	if (grid.w < 0.5) {
		return false;
	}
	vec2 uv = (pos - grid.xy) / grid.z;
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) {
		return false;
	}
	float pixels_per_meter = layout_info.x * layout_info.z / grid.z;
	int taps;
	float footprint;
	vec2 span = t3d_rvt_kernel(dx, dy, pixels_per_meter, taps, footprint) / grid.z;
	float lod = clamp(log2(max(footprint, 1e-8)) + bias, 0.0, layout_info.y);
	return t3d_rvt_footprint(table, color, data, layout_info, uv, span, taps, lod, surface);
}

bool t3d_rvt_fixed_surface(vec2 pos, vec2 dx, vec2 dy, float far_weight, out CachedTerrainSurface surface) {
	vec2 inner = pos - _t3d_material_rvt_grid.xy;
	vec2 edge = min(inner, vec2(_t3d_material_rvt_grid.z) - inner);
	if (_t3d_material_rvt_far_grid.w > 0.5 && _t3d_material_rvt_far_grid.z > _t3d_material_rvt_grid.z) {
		// The authored data has a fine local volume. Its edge overlaps the world
		// volume by one native cell, including when flying through the region boundary.
		far_weight = max(far_weight, 1.0 - smoothstep(0.0, _vertex_spacing, min(edge.x, edge.y)));
	}
	bool near_ok = false;
	if (far_weight < 1.0) {
		near_ok = t3d_rvt_endpoint(_t3d_material_rvt_table, _t3d_material_rvt_color, _t3d_material_rvt_surface, _t3d_material_rvt_grid, _t3d_material_rvt_layout, 0.0, pos, dx, dy, surface);
	}
	if (far_weight > 0.0 || !near_ok) {
		CachedTerrainSurface far_surface;
		if (t3d_rvt_endpoint(_t3d_material_rvt_far_table, _t3d_material_rvt_far_color, _t3d_material_rvt_far_surface, _t3d_material_rvt_far_grid, _t3d_material_rvt_far_layout, _t3d_material_rvt_far_bias, pos, dx, dy, far_surface)) {
			if (near_ok) {
				surface = t3d_rvt_filter(surface, far_surface, far_weight);
			} else {
				surface = far_surface;
			}
			return true;
		}
	}
	if (far_weight >= 1.0) {
		// The outer root can still be loading while the inner volume already covers this point.
		return t3d_rvt_endpoint(_t3d_material_rvt_table, _t3d_material_rvt_color, _t3d_material_rvt_surface, _t3d_material_rvt_grid, _t3d_material_rvt_layout, 0.0, pos, dx, dy, surface);
	}
	return near_ok;
}

bool t3d_rvt_detail_surface(vec3 pos, vec3 eye, vec2 dx, vec2 dy, float far_style, out CachedTerrainSurface surface, out float weight) {
	weight = 0.0;
	vec4 grid = _t3d_material_rvt_detail_grid;
	if (grid.w < 0.5) {
		return false;
	}
	vec2 delta = abs(pos.xz - eye.xz);
	float distance_xz = max(delta.x, delta.y);
	float radius = _t3d_material_rvt_detail_limits.x;
	if (distance_xz >= radius) {
		return false;
	}
	vec2 uv = (pos.xz - grid.xy) / grid.z;
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) {
		return false;
	}
	vec4 info = _t3d_material_rvt_detail_layout;
	float density = info.x * info.z / grid.z;
	int taps;
	float footprint;
	vec2 span = t3d_rvt_kernel(dx, dy, density, taps, footprint) / grid.z;
	float cutoff = density * _t3d_material_rvt_detail_limits.y;
	if (footprint >= cutoff) {
		return false;
	}
	float lod = clamp(log2(max(footprint, 1e-8)), 0.0, info.y);
	// Fade relative to the view, not the snapped origin, so a window step never shifts the blend band.
	weight = (1.0 - smoothstep(0.75 * radius, radius, distance_xz)) * (1.0 - smoothstep(0.5 * cutoff, cutoff, footprint));
	bool near_ready = false;
	float near_weight = 0.0;
	if (far_style < 1.0) {
		near_ready = t3d_rvt_footprint(_t3d_material_rvt_detail_table, _t3d_material_rvt_detail_color, _t3d_material_rvt_detail_surface, info, uv, span, taps, lod, surface);
		if (near_ready) {
			near_weight = (1.0 - far_style) * surface.detail_confidence;
		}
	}
#ifdef T3D_DUAL_SCALING
	if (far_style > 0.0) {
		CachedTerrainSurface other;
		if (t3d_rvt_footprint(_t3d_material_rvt_detail_far_table, _t3d_material_rvt_detail_far_color, _t3d_material_rvt_detail_far_surface, info, uv, span, taps, lod, other)) {
			// A newly requested style enters only in proportion to its blend weight.
			// This preserves a ready near page on crossing the dual-scale threshold.
			float far_weight = far_style * other.detail_confidence;
			float total = near_weight + far_weight;
			if (near_ready) {
				surface = t3d_rvt_filter(surface, other, total > 0.0 ? far_weight / total : far_style);
			} else {
				surface = other;
			}
			weight *= total;
			return true;
		}
	}
#endif
	weight *= near_weight;
	return near_ready;
}

bool t3d_rvt_read(vec3 pos, vec3 eye, vec2 dx, vec2 dy, out CachedTerrainSurface surface) {
	if (_t3d_material_rvt_bypass || _t3d_material_rvt_grid.w < 0.5 || flat_terrain_normals ||
			(abs(depth_blur + 1.0 - mipmap_bias) > 0.0001 && v_vertex_xz_dist > bias_distance)) {
		return false;
	}
	float far_style = 0.0;
#ifdef T3D_DUAL_SCALING
	far_style = smoothstep(dual_scale_near, max(dual_scale_near + 0.0001, dual_scale_far), length(pos - eye));
#endif
	CachedTerrainSurface detail;
	float weight;
	bool has_detail = t3d_rvt_detail_surface(pos, eye, dx, dy, far_style, detail, weight);
	if (has_detail && weight >= 1.0) {
		surface = detail;
		return true;
	}
	if (t3d_rvt_fixed_surface(pos.xz, dx, dy, far_style, surface)) {
		if (has_detail && weight > 0.0) {
			surface = t3d_rvt_filter(surface, detail, weight);
		}
		return true;
	}
	if (has_detail) {
		surface = detail;
	}
	return has_detail;
}
#endif
)"
