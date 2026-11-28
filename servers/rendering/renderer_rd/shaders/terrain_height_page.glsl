#[compute]
#version 450

#VERSION_DEFINES

// A height page is a lattice of grid vertices (including its apron). Keep signed metres.
layout(local_size_x = 8, local_size_y = 8) in;
layout(set = 0, binding = 0) uniform sampler2DArray heights;
layout(set = 0, binding = 1, std430) readonly buffer Regions { int layers[]; } regions;
layout(set = 0, binding = 2, r32f) uniform restrict writeonly image2D pool;
layout(push_constant, std430) uniform Params {
	ivec2 page_origin;
	ivec2 pool_origin;
	ivec2 grid_origin;
	int dimension;
	int extent;
	int region_size;
	int map_width;
	int border;
	int stride;
} pc;

float grid_height(ivec2 xy) {
	ivec2 region = ivec2(floor(vec2(xy) / float(pc.region_size)));
	ivec2 map_coord = region + pc.map_width / 2;
	if (any(lessThan(map_coord, ivec2(0))) || any(greaterThanEqual(map_coord, ivec2(pc.map_width)))) {
		return 0.0;
	}
	int layer = regions.layers[map_coord.y * pc.map_width + map_coord.x] - 1;
	if (layer < 0 || layer >= textureSize(heights, 0).z) {
		return 0.0;
	}
	float h = texelFetch(heights, ivec3(xy - region * pc.region_size, layer), 0).r;
	return (isnan(h) || isinf(h)) ? 0.0 : h;
}

void main() {
	ivec2 local = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(local, ivec2(pc.stride)))) {
		return;
	}
	ivec2 texel = clamp(pc.page_origin + local - pc.border, ivec2(0), ivec2(pc.dimension - 1));
	vec2 grid = min(vec2(texel) * (float(pc.extent) / float(pc.dimension)), vec2(pc.extent - 1));
	ivec2 a = ivec2(floor(grid)) + pc.grid_origin;
	vec2 f = fract(grid);
	float h = grid_height(a);
	if (any(notEqual(f, vec2(0)))) {
		ivec2 b = min(a + 1, pc.grid_origin + pc.extent - 1);
		h = mix(mix(h, grid_height(ivec2(b.x, a.y)), f.x),
				mix(grid_height(ivec2(a.x, b.y)), grid_height(b), f.x), f.y);
	}
	imageStore(pool, pc.pool_origin + local, vec4(h));
}
