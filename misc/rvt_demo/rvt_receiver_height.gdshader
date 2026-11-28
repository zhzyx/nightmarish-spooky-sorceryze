shader_type spatial;
render_mode unshaded;

#include "res://rvt.gdshaderinc"

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 uvh = (rvt_world_to_uv * vec4(world_pos, 1.0)).xyz;
	float h = rvt_sample_height01(uvh.xz, rvt_compute_lod(uvh.xz));
	ALBEDO = vec3(h);
}
