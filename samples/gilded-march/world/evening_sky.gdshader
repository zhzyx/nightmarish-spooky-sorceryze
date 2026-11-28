shader_type sky;
uniform sampler2D clouds : source_color, filter_linear, repeat_enable;
void sky() {
	vec3 light = max(texture(clouds, SKY_COORDS).rgb, vec3(0.0));
	float y = dot(light, vec3(.2126,.7152,.0722));
	float horizon = pow(1.0 - clamp(EYEDIR.y,0.0,1.0),3.0);
	vec3 muted = mix(vec3(y),light,.40);
	vec3 tint = mix(vec3(.56,.69,.72),vec3(1.0,.78,.49), horizon*.82);
	COLOR = pow(muted,vec3(1.12))*tint*.47 + vec3(.033,.027,.014)*horizon;
}
