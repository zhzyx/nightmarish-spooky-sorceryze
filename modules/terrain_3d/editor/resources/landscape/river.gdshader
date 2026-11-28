shader_type spatial;
render_mode cull_disabled;
varying vec3 world_p;
void vertex() {
	world_p=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
	VERTEX.y+=0.038*sin(world_p.z*0.74+world_p.x*0.3+TIME*1.4);
}
void fragment() {
	vec2 p=world_p.xz;
	float a=cos(p.x*1.3+p.y*.6+TIME*1.6);
	float b=cos(p.x*.64-p.y*1.25-TIME*1.8);
	float c=sin(p.y*.17+p.x*.22-TIME*.6);
	vec3 nw=normalize(vec3(.078*a+.055*b,1.0,.045*a-.083*b+.028*c));
	NORMAL=normalize((VIEW_MATRIX*vec4(nw,0.0)).xyz);
	float fres=pow(1.0-clamp(dot(NORMAL,VIEW),0.0,1.0),3.3);
	ALBEDO=mix(vec3(.042,.103,.093),vec3(.17,.23,.22),fres)+0.008*c;
	ROUGHNESS=.22+.12*(1.0-fres);
	SPECULAR=.65;
}
