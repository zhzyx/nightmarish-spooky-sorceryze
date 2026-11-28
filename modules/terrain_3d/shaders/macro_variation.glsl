// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

R"(

//INSERT: MACRO_VARIATION_UNIFORMS
group_uniforms macro_variation;
uniform vec3 macro_variation1 : source_color = vec3(1.);
uniform vec3 macro_variation2 : source_color = vec3(1.);
uniform float macro_variation_slope : hint_range(0., 1.)  = 0.333;
uniform highp sampler2D noise_texture : source_color, FILTER_METHOD, repeat_enable;
uniform float noise1_scale : hint_range(0.001, 1.) = 0.04; // Used for macro variation 1. Scaled up 10x
uniform float noise1_angle : hint_range(0, 6.283) = 0.;
uniform vec2 noise1_offset = vec2(0.5);
uniform float noise2_scale : hint_range(0.001, 1.) = 0.076;	// Used for macro variation 2. Scaled up 10x
group_uniforms;

//INSERT: MACRO_VARIATION
	// Macro variation. 2 lookups
	{
		vec2 rotation = vec2(cos(noise1_angle), sin(noise1_angle));
		vec2 n1_uv = rotate_vec2(fma(uv, vec2(noise1_scale * .1), noise1_offset), rotation);
		vec2 n2_uv = uv * noise2_scale * .1;
#ifdef T3D_MATERIAL_RVT_READER
		vec2 uv_dx = t3d_view_dx.xz * _vertex_density;
		vec2 uv_dy = t3d_view_dy.xz * _vertex_density;
		float noise1 = textureGrad(noise_texture, n1_uv, rotate_vec2(uv_dx * noise1_scale * .1, rotation), rotate_vec2(uv_dy * noise1_scale * .1, rotation)).r;
		float noise2 = textureGrad(noise_texture, n2_uv, uv_dx * noise2_scale * .1, uv_dy * noise2_scale * .1).r;
#else
		float noise1 = texture(noise_texture, n1_uv).r;
		float noise2 = texture(noise_texture, n2_uv).r;
#endif
		vec3 macrov = mix(macro_variation1, vec3(1.), noise1);
		macrov *= mix(macro_variation2, vec3(1.), noise2);
		mat.albedo_height.rgb *= mix(vec3(1.0), macrov, clamp(w_normal.y + macro_variation_slope, 0., 1.));
	}

)"
