#[compute]
#version 450

#VERSION_DEFINES

layout(local_size_x = 8, local_size_y = 8) in;
#ifdef DEPTH_MSAA
layout(set = 0, binding = 0) uniform sampler2DMS scene_depth;
#define READ_DEPTH(p) texelFetch(scene_depth, p, 0).r
#else
layout(set = 0, binding = 0) uniform sampler2D scene_depth;
#define READ_DEPTH(p) texelFetch(scene_depth, p, 0).r
#endif
layout(set = 0, binding = 1, std430) writeonly buffer Feedback { uint pages[]; };
#ifdef WORLD_LIMITS
layout(set = 0, binding = 2, std140) uniform WorldFilter {
	vec4 axes[3];
	vec4 limits;
} filter_data;
#endif
layout(push_constant, std430) uniform Params {
	mat4 clip_to_volume;
	ivec2 size;
	ivec2 grid;
	int pixel_step;
	int offset;
	int log2_tiles;
	int tile_size;
	int anisotropy;
	float lod_bias;
	int pad1, pad2;
	vec4 eye_in_volume;
} pc;

vec3 volume_position(ivec2 pixel, float depth) {
	vec2 ndc = ((vec2(pixel) + 0.5) / vec2(pc.size)) * 2.0 - 1.0;
	vec4 position = pc.clip_to_volume * vec4(ndc, depth, 1.0);
	return position.xyz / position.w;
}

void main() {
	ivec2 sample_xy = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(sample_xy, pc.grid))) {
		return;
	}
	int index = pc.offset + sample_xy.y * pc.grid.x + sample_xy.x;
	pages[index] = 0xffffffffu;
	ivec2 pixel = min(sample_xy * pc.pixel_step + pc.pixel_step / 2, pc.size - 1);
	float depth = READ_DEPTH(pixel);
	if (depth <= 0.0) {
		return;
	}
	vec3 pos = volume_position(pixel, depth);
	vec2 uv = pos.xz + 0.5;
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0))) || abs(pos.y) > 0.501) {
		return;
	}
#ifdef WORLD_LIMITS
	// Reconstruct from the camera's actual transform for both projection types.
	// The volume basis converts signed local deltas to world meters, including rotation.
	mat3 axes = mat3(filter_data.axes[0].xyz, filter_data.axes[1].xyz, filter_data.axes[2].xyz);
	vec3 world_offset = axes * (pos - pc.eye_in_volume.xyz);
	float distance_squared = dot(world_offset, world_offset);
	vec4 limits = filter_data.limits;
	if ((limits.x > 0.0 && distance_squared < limits.x * limits.x) ||
			(limits.y > 0.0 && distance_squared > limits.y * limits.y) ||
			(limits.z > 0.0 && max(abs(world_offset.x), abs(world_offset.z)) > limits.z)) {
		return;
	}
#endif
	ivec2 px = pixel + ivec2((pixel.x+1 < pc.size.x) ? 1 : -1, 0);
	ivec2 py = pixel + ivec2(0, (pixel.y+1 < pc.size.y) ? 1 : -1);
	vec2 dx = volume_position(px, READ_DEPTH(px)).xz - pos.xz;
	vec2 dy = volume_position(py, READ_DEPTH(py)).xz - pos.xz;
	float texels = float(pc.tile_size << pc.log2_tiles);
	float footprint = max(length(dx), length(dy)) * texels;
	float taps = 1.0;
	if (pc.anisotropy > 1) {
		float xx = dot(dx, dx), yy = dot(dy, dy), xy = dot(dx, dy);
		float major = sqrt(max(0.5 * (xx + yy + length(vec2(xx - yy, 2.0 * xy))), 1e-20));
		float minor = abs(dx.x * dy.y - dx.y * dy.x) / major;
		taps = clamp(ceil(major / max(minor, 1.0 / texels) - 0.0001), 1.0, float(pc.anisotropy));
		footprint = max(minor, major / taps) * texels;
	}
#ifdef WORLD_LIMITS
	if (limits.w > 0.0) {
		// Use the same anisotropic tap count as the mip calculation. Express its
		// projected footprint on the physical material plane in meters before LOD bias.
		vec3 world_dx = axes[0] * dx.x + axes[2] * dx.y;
		vec3 world_dy = axes[0] * dy.x + axes[2] * dy.y;
		float footprint_m = max(length(world_dx), length(world_dy));
		if (pc.anisotropy > 1) {
			float xx = dot(world_dx, world_dx), yy = dot(world_dy, world_dy), xy = dot(world_dx, world_dy);
			float major = sqrt(max(0.5 * (xx + yy + length(vec2(xx - yy, 2.0 * xy))), 1e-20));
			float minor = length(cross(world_dx, world_dy)) / major;
			footprint_m = max(minor, major / taps);
		}
		if (footprint_m > limits.w) {
			return;
		}
	}
#endif
	int mip = int(clamp(floor(log2(max(footprint, 1e-8)) + pc.lod_bias), 0.0, float(pc.log2_tiles)));
	uvec2 xy = uvec2(uv * float(1 << (pc.log2_tiles - mip)));
	pages[index] = (uint(mip) << 24) | (xy.y << 12) | xy.x;
}
