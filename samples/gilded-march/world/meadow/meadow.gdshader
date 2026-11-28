shader_type spatial;
render_mode cull_disabled;

uniform sampler2D field : filter_linear, repeat_disable;
uniform float patch_width = 6.0;
uniform vec2 fade_in = vec2(-2.0, -1.0);
uniform vec2 fade_out = vec2(22.0, 38.0);
varying vec3 blade_tint;
varying float tip;
varying float across;

float hash(vec2 p) {
	vec3 q = fract(vec3(p.xyx) * 0.1031);
	q += dot(q, q.yzx + 33.33);
	return fract((q.x + q.y) * q.z);
}

void vertex() {
	vec3 base = vec3((UV2.x - 0.5) * patch_width, 0.0, (UV2.y - 0.5) * patch_width);
	vec3 root = (MODEL_MATRIX * vec4(base, 1.0)).xyz;
	vec3 field_data = textureLod(field, (root.xz + vec2(768.75)) / 1536.0, 0.0).rgb;
	float y = dot(field_data.rg, vec2(255.0 * 256.0, 255.0)) / 128.0 - 64.0;
	float dist = length(MAIN_CAM_INV_VIEW_MATRIX[3].xyz - vec3(root.x, y, root.z));
	float seed = hash(floor(root.xz * 14.0));
	float colony = 0.5 + 0.5*sin(root.x*0.63 + sin(root.z*0.44)*1.8)*cos(root.z*0.31 + root.x*0.14);
	float density = smoothstep(0.0, 0.16, field_data.b - seed * (0.54 + colony*0.51));
	density *= float(max(abs(root.x),abs(root.z)) < 765.0);
	float lod = smoothstep(fade_in.x, fade_in.y, dist) * (1.0 - smoothstep(fade_out.x, fade_out.y, dist));
	float scale = density * lod;
	vec3 offset = VERTEX - base;
	vec2 meadow = root.xz;
	float band = sin(dot(meadow,vec2(0.115,0.058)) + 1.2*sin(meadow.y*0.046));
	float warm = clamp(0.48 + 0.32*band + 0.13*sin(meadow.x*0.062-meadow.y*0.13) + 0.12*seed, 0.0, 1.0);
	float size = (0.72 + 0.51*seed + warm*0.21) * scale;
	tip = UV.x;
	across = UV.y;
	float gust = sin(dot(meadow,vec2(0.26,0.115)) - TIME*1.62 + 0.65*sin(meadow.y*0.08 - TIME*0.43));
	float ripple = sin(dot(meadow,vec2(1.22,0.58)) - TIME*2.7 + seed);
	vec2 wind = vec2(0.84,0.34) * (0.075 + 0.14*gust + 0.042*ripple) * tip*tip * size;
	vec3 local_wind = transpose(mat3(MODEL_MATRIX)) * vec3(wind.x,0.0,wind.y);
	vec2 axis = normalize(offset.xz + vec2(0.0001));
	NORMAL = normalize(vec3(axis.x*0.50 + across*0.11, 1.0, axis.y*0.50) + local_wind*1.7);
	VERTEX = base + offset*size + local_wind;
	VERTEX.y += y - root.y - 0.038;
	blade_tint = COLOR.rgb * mix(vec3(0.76,0.92,0.81),vec3(1.13,1.02,0.83),warm) * (0.86 + seed*0.21);
}

void fragment() {
	vec3 soft_up = normalize(mat3(VIEW_MATRIX) * vec3(0.0,1.0,0.0));
	vec3 face = FRONT_FACING ? NORMAL : -NORMAL;
	NORMAL = normalize(soft_up * 0.42 + face * 0.58);
	float grain = smoothstep(1.05,1.55,abs(across));
	float blade_rib = (1.0 - smoothstep(0.03,0.19,abs(across))) * 0.09;
	float daylight = mix(0.71,1.04,smoothstep(0.02,0.84,tip));
	ALBEDO = blade_tint * daylight * (1.0 + blade_rib + across*0.04);
	ROUGHNESS = 0.96;
	SPECULAR = 0.13;
	BACKLIGHT = blade_tint * (0.26 + grain*0.26) * tip;
}
