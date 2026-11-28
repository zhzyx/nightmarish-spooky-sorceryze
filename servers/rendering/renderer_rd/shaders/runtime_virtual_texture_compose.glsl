#[compute]

#version 450

#VERSION_DEFINES

// [ZXB] Converts the material pass buffers of one RVT page into the physical page pool layers.

#define BLOCK_SIZE 8

layout(local_size_x = BLOCK_SIZE, local_size_y = BLOCK_SIZE, local_size_z = 1) in;

layout(set = 0, binding = 0) uniform sampler2D src_albedo; // sRGB attachment, fetched as linear.

#if defined(MODE_BASE_COLOR_NORMAL_ROUGHNESS) || defined(MODE_TERRAIN_PBR)
layout(set = 0, binding = 1) uniform sampler2D src_normal;
layout(set = 0, binding = 2) uniform sampler2D src_orm;
#endif

#ifdef MODE_TERRAIN_PBR
layout(set = 0, binding = 4) uniform sampler2D src_emission;
layout(rgba16, set = 1, binding = 1) uniform restrict writeonly image2D dst_layer1;
#endif

#ifdef MODE_WORLD_HEIGHT
layout(set = 0, binding = 3) uniform sampler2D src_depth;
#endif

#ifdef MODE_WORLD_HEIGHT
layout(r32f, set = 1, binding = 0) uniform restrict writeonly image2D dst_layer0;
#else
layout(rgba8, set = 1, binding = 0) uniform restrict writeonly image2D dst_layer0;
#endif

#ifdef MODE_BASE_COLOR_NORMAL_ROUGHNESS
layout(rgba8, set = 1, binding = 1) uniform restrict writeonly image2D dst_layer1;
#endif

layout(push_constant, std430) uniform Params {
	ivec2 dst_offset;
	ivec2 size;
	float height_scale; // 1 / metric volume height.
	int flip_y;
	float pad0;
	float pad1;
}
params;

vec3 linear_to_srgb(vec3 p_color) {
	vec3 c = clamp(p_color, vec3(0.0), vec3(1.0));
	return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, c * 12.92, lessThan(c, vec3(0.0031308)));
}

void main() {
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(p, params.size))) {
		return;
	}

	ivec2 src = ivec2(p.x, params.flip_y != 0 ? params.size.y - 1 - p.y : p.y);
	ivec2 dst = params.dst_offset + p;

	vec4 albedo = texelFetch(src_albedo, src, 0);

#ifdef MODE_WORLD_HEIGHT
	float depth = texelFetch(src_depth, src, 0).r;
	float height = albedo.a > 0.0 ? clamp(1.0 - depth * params.height_scale, 0.0, 1.0) : 0.0;
	imageStore(dst_layer0, dst, vec4(height, 0.0, 0.0, 0.0));
#elif defined(MODE_TERRAIN_PBR)
	vec4 orm = texelFetch(src_orm, src, 0);
	// Keep directional lighting on the terrain consumer. The mapped normal gets ten
	// bits per octahedral axis and the geometric normal for specular gets six.
	vec3 view_normal = texelFetch(src_normal, src, 0).xyz * 2.0 - 1.0;
	vec3 n = vec3(view_normal.x, view_normal.z, -view_normal.y);
	n /= max(dot(abs(n), vec3(1.0)), 0.00001);
	vec2 oct = n.xz;
	if (n.y < 0.0) {
		oct = (1.0 - abs(oct.yx)) * mix(vec2(-1.0), vec2(1.0), greaterThanEqual(oct, vec2(0.0)));
	}
	vec3 aux = texelFetch(src_emission, src, 0).rgb;
	vec2 packed_normals = round(clamp(oct * 0.5 + 0.5, 0.0, 1.0) * 1023.0) * 64.0 + round(clamp(aux.gb, 0.0, 1.0) * 63.0);
	float affect = aux.r;
	float packed_ao = round(orm.r * 255.0) * 256.0 + round(clamp(affect, 0.0, 1.0) * 255.0);
	imageStore(dst_layer0, dst, vec4(linear_to_srgb(albedo.rgb), orm.b));
	imageStore(dst_layer1, dst, vec4(packed_normals / 65535.0, orm.g, packed_ao / 65535.0));
#else
	imageStore(dst_layer0, dst, vec4(linear_to_srgb(albedo.rgb), albedo.a));
#endif

#ifdef MODE_BASE_COLOR_NORMAL_ROUGHNESS
	// View space (camera looking down the volume) to volume local space: x -> x, y -> -z, z -> y.
	vec3 n = texelFetch(src_normal, src, 0).xyz * 2.0 - 1.0;
	n = length(n) > 0.001 ? normalize(n) : vec3(0.0, 0.0, 1.0);
	vec4 orm = texelFetch(src_orm, src, 0);
	imageStore(dst_layer1, dst, vec4(n.x * 0.5 + 0.5, -n.y * 0.5 + 0.5, orm.g, orm.b));
#endif
}
