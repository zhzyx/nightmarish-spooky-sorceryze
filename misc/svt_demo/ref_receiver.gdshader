shader_type spatial;
render_mode unshaded;

uniform sampler2D src_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform float area = 64.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	// Same mapping the virtual texture uses: world xz over the covered box.
	vec2 uv = world_pos.xz / area + 0.5;
	ALBEDO = texture(src_tex, clamp(uv, vec2(0.0), vec2(1.0))).rgb;
}
