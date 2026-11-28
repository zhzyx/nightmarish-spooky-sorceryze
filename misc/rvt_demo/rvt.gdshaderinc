// Runtime Virtual Texture sampling helpers.
// Include after `shader_type spatial;`. Uniforms are filled by RuntimeVirtualTexture.apply_to_material(material, "rvt").

uniform sampler2D rvt_page_table : filter_nearest, repeat_disable;
uniform sampler2D rvt_physical0 : filter_linear, repeat_disable;
uniform sampler2D rvt_physical1 : filter_linear, repeat_disable;
uniform vec4 rvt_params0; // x: level 0 tiles per side, y: max level, z: tile size px, w: tile border px.
uniform vec4 rvt_params1; // x, y: physical texture size px, z: volume height, w: material type.
uniform mat4 rvt_world_to_uv; // World to volume unit space: x -> u, z -> v, y -> height (all 0..1).
uniform mat4 rvt_normal_basis; // Volume local to world rotation.
uniform int rvt_debug_mode = 0; // 1 page table, 2 page table (mip), 3 physical pool, 4 LOD, 5 borders.
uniform int rvt_debug_force_lod = -1; // -1 keeps the computed LOD.

// Physical texture UV of `uv` at `level`. Falls back to the nearest resident ancestor page.
vec2 rvt_physical_uv(vec2 uv, int level, out bool valid) {
	int max_level = int(rvt_params0.y);
	level = clamp(level, 0, max_level);
	int tiles0 = int(rvt_params0.x);
	int level_tiles = max(tiles0 >> level, 1);
	ivec2 page = clamp(ivec2(floor(uv * float(level_tiles))), ivec2(0), ivec2(level_tiles - 1));
	vec4 e = floor(texelFetch(rvt_page_table, page, level) * 255.0 + 0.5);
	valid = e.a > 0.5;
	float res_tiles = float(max(tiles0 >> int(e.b), 1));
	vec2 scaled = uv * res_tiles;
	vec2 in_page = clamp(scaled - floor(scaled), vec2(0.0), vec2(1.0));
	float tile = rvt_params0.z;
	float border = rvt_params0.w;
	vec2 texel = e.rg * (tile + 2.0 * border) + border + in_page * tile;
	return texel / rvt_params1.xy;
}

float rvt_compute_lod(vec2 uv) {
	float texels = rvt_params0.x * rvt_params0.z;
	vec2 dx = dFdx(uv) * texels;
	vec2 dy = dFdy(uv) * texels;
	float d = max(dot(dx, dx), dot(dy, dy));
	return clamp(0.5 * log2(max(d, 1e-8)), 0.0, rvt_params0.y);
}

vec3 rvt_srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

// Samples both layers at an explicit mip level (usable in vertex()).
void rvt_fetch_level(vec2 uv, int level, out vec4 layer0, out vec4 layer1, out bool valid) {
	vec2 puv = rvt_physical_uv(uv, level, valid);
	layer0 = textureLod(rvt_physical0, puv, 0.0);
	layer1 = textureLod(rvt_physical1, puv, 0.0);
}

// Debug colors use the same page indirection the sampler uses, so what you see is what is read.
vec3 rvt_debug_hash_color(float p_h) {
	// Cheap hue rotation: neighboring pool tiles get clearly different colors.
	return 0.5 + 0.5 * cos(6.28318 * (vec3(0.0, 0.33, 0.67) + p_h));
}

vec3 rvt_debug_level_color(int p_level) {
	float t = float(p_level) / max(rvt_params0.y, 1.0);
	return clamp(vec3(t, 1.0 - abs(t * 2.0 - 1.0), 1.0 - t), vec3(0.0), vec3(1.0));
}

vec3 rvt_debug_color(vec2 p_uv, float p_lod) {
	const vec3 invalid_color = vec3(1.0, 0.0, 1.0);
	int max_level = int(rvt_params0.y);
	int tiles0 = int(rvt_params0.x);
	int level = clamp(int(floor(p_lod)), 0, max_level);
	int level_tiles = max(tiles0 >> level, 1);
	vec2 scaled = p_uv * float(level_tiles);
	ivec2 page = clamp(ivec2(floor(scaled)), ivec2(0), ivec2(level_tiles - 1));
	vec4 e = floor(texelFetch(rvt_page_table, page, level) * 255.0 + 0.5);
	bool valid = e.a > 0.5;
	int res = int(e.b);
	float tile = rvt_params0.z;
	float border = rvt_params0.w;

	// Distance to the edge of the sampling page, and to the edge of the resident page.
	float edge = min(min(scaled.x - float(page.x), float(page.x + 1) - scaled.x),
			min(scaled.y - float(page.y), float(page.y + 1) - scaled.y)) * tile;
	bool grid = edge < 2.0;
	vec2 in_page = fract(p_uv * pow(2.0, float(res)));
	float band = min(min(in_page.x, 1.0 - in_page.x), min(in_page.y, 1.0 - in_page.y)) * tile;

	vec3 c = vec3(0.0);
	if (rvt_debug_mode == 1) {
		// Page table: a distinct color per pool tile, darker as the resident level gets coarser.
		float h = fract(float(e.r) * 0.618033 + float(e.g) * 0.414213);
		c = valid ? rvt_debug_hash_color(h) * mix(1.0, 0.45, float(res) / max(float(max_level), 1.0)) : invalid_color;
		if (grid) {
			c = vec3(1.0);
		}
	} else if (rvt_debug_mode == 2) {
		// Residency: one color per resident mip level.
		c = valid ? rvt_debug_level_color(res) : invalid_color;
		if (grid) {
			c = vec3(1.0);
		}
	} else if (rvt_debug_mode == 3) {
		// Physical pool tile identity, with the source tile border drawn in green.
		float h = fract(float(e.r) * 0.618033 + float(e.g) * 0.414213);
		c = valid ? rvt_debug_hash_color(h) : invalid_color;
		if (band < border) {
			c = mix(c, vec3(0.0, 1.0, 0.0), 0.85);
		}
		if (grid) {
			c = vec3(1.0);
		}
	} else if (rvt_debug_mode == 4) {
		// LOD heat map: blue = level 0, red = coarsest.
		float t = clamp(p_lod / max(float(max_level), 1.0), 0.0, 1.0);
		c = vec3(t, 1.0 - abs(t * 2.0 - 1.0), 1.0 - t);
	} else if (rvt_debug_mode == 5) {
		// Page grid in red, tile border ring in green.
		c = vec3(0.08);
		if (grid) {
			c = vec3(1.0, 0.0, 0.0);
		}
		if (band < border) {
			c = vec3(0.0, 1.0, 0.0);
		}
	}
	return c;
}

// Trilinear sample of the virtual texture at a world position (fragment only).
// color: linear albedo + alpha. normal_roughness_metallic: world normal in xyz is returned in `world_normal`.
void rvt_sample(vec3 world_pos, out vec4 color, out vec3 world_normal, out float roughness, out float metallic, out bool inside) {
	vec3 uvh = (rvt_world_to_uv * vec4(world_pos, 1.0)).xyz;
	vec2 uv = uvh.xz;
	inside = all(greaterThanEqual(uv, vec2(0.0))) && all(lessThanEqual(uv, vec2(1.0)));
	uv = clamp(uv, vec2(0.0), vec2(0.999999));

	float lod = rvt_compute_lod(uv);
	if (rvt_debug_force_lod >= 0) {
		lod = clamp(float(rvt_debug_force_lod), 0.0, rvt_params0.y);
	}
	if (rvt_debug_mode > 0) {
		color = vec4(rvt_srgb_to_linear(rvt_debug_color(uv, lod)), 1.0);
		world_normal = vec3(0.0, 1.0, 0.0);
		roughness = 1.0;
		metallic = 0.0;
		return;
	}
	int l0 = int(floor(lod));
	float f = lod - floor(lod);

	vec4 a0, b0, a1, b1;
	bool v0, v1;
	rvt_fetch_level(uv, l0, a0, b0, v0);
	rvt_fetch_level(uv, l0 + 1, a1, b1, v1);
	vec4 a = mix(a0, a1, f);
	vec4 b = mix(b0, b1, f);

	color = vec4(rvt_srgb_to_linear(a.rgb), a.a);
	vec2 n = b.rg * 2.0 - 1.0;
	vec3 local_n = vec3(n.x, sqrt(max(1.0 - dot(n, n), 0.0)), n.y);
	world_normal = normalize((rvt_normal_basis * vec4(local_n, 0.0)).xyz);
	roughness = b.b;
	metallic = b.a;
}

// World height from a WORLD_HEIGHT virtual texture, in [volume bottom, volume top] via `rvt_params1.z`.
float rvt_sample_height01(vec2 uv, float lod) {
	int l0 = int(floor(lod));
	float f = lod - floor(lod);
	bool v;
	vec2 p0 = rvt_physical_uv(clamp(uv, vec2(0.0), vec2(0.999999)), l0, v);
	vec2 p1 = rvt_physical_uv(clamp(uv, vec2(0.0), vec2(0.999999)), l0 + 1, v);
	return mix(textureLod(rvt_physical0, p0, 0.0).r, textureLod(rvt_physical0, p1, 0.0).r, f);
}
