shader_type spatial;

#include "res://rvt.gdshaderinc"

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 color;
	vec3 world_normal;
	float roughness;
	float metallic;
	bool inside;
	rvt_sample(world_pos, color, world_normal, roughness, metallic, inside);
	ALBEDO = color.rgb;
	ROUGHNESS = roughness;
	METALLIC = metallic;
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);
}
