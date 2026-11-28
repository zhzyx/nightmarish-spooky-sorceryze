extends SceneTree
## Forward+ render regression for a terrain ridge outside the color frustum casting onto the visible ground.
## Run with --fixed-fps 60 --script <this file>. Pass -- --native to compare the native height path.

var terrain := Terrain3D.new()
var camera := Camera3D.new()

func _initialize() -> void:
	run.call_deferred()

func frames(n: int) -> void:
	for i in n:
		await RenderingServer.frame_post_draw

func center_light() -> float:
	var image := root.get_texture().get_image()
	var center := image.get_size() / 2
	var total := 0.0
	for y in range(-2,3):
		for x in range(-2,3):
			total += image.get_pixelv(center + Vector2i(x,y)).get_luminance()
	return total / 25.0

func run() -> void:
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 10.0
	camera.near = 0.1
	camera.far = 100.0
	root.add_child(camera)
	camera.position = Vector3(40,30,32)
	camera.look_at(Vector3(40,0,32),Vector3.FORWARD)
	camera.environment = Environment.new()
	camera.environment.background_mode = Environment.BG_COLOR
	camera.environment.background_color = Color.BLACK
	camera.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	camera.environment.ambient_light_color = Color(0.05,0.05,0.05)
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at(Vector3(1,-0.65,0),Vector3.UP)
	light.shadow_enabled = true
	light.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	light.directional_shadow_max_distance = 100.0

	terrain.free_editor_textures = false
	root.add_child(terrain)
	terrain.region_size = Terrain3D.SIZE_64
	terrain.material.world_background = Terrain3DMaterial.NONE
	terrain.set_camera(camera)
	var region := terrain.data.add_region_blank(Vector2i.ZERO,false)
	var heights := Image.create_empty(64,64,false,Image.FORMAT_RF)
	heights.fill(Color(0,0,0))
	heights.fill_rect(Rect2i(16,8,6,48), Color(18,0,0))
	region.set_height_map(heights)
	region.calc_height_range()
	terrain.data.update_maps()
	var cv := Engine.get_singleton("CVars")
	cv.set_value("r.Terrain3D.Mode",1)
	cv.set_value("r.Terrain3D.VT.TileSize",16)
	cv.set_value("r.Terrain3D.VT.Log2Tiles",2)
	cv.set_value("r.Terrain3D.TileRes",4)
	cv.set_value("r.Terrain3D.Lod0Distance",128)
	cv.set_value("r.Terrain3D.VTHeight",int(not ("--native" in OS.get_cmdline_user_args())))
	await frames(90)
	var shader := terrain.material.get_shader_rid()
	var code := RenderingServer.shader_get_code(shader)
	var fragment := code.find("void fragment()")
	if fragment < 0 or camera.is_position_in_frustum(Vector3(21,18,32)):
		push_error("Invalid off-screen shadow fixture")
		quit(1)
		return
	RenderingServer.shader_set_code(shader,code.left(fragment) + "void fragment() { ALBEDO=vec3(1.0); NORMAL=mat3(VIEW_MATRIX)*vec3(0,1,0); ROUGHNESS=1.0; }")
	await frames(60)
	var shadow := center_light()
	terrain.cast_shadows = RenderingServer.SHADOW_CASTING_SETTING_OFF
	await frames(15)
	var lit := center_light()
	RenderingServer.shader_set_code(shader,code)
	print("Off-screen heightfield ridge: receiver luminance ", shadow, " with shadow, ", lit, " without")
	if lit-shadow <= 0.12:
		push_error("The cropped color cut lost the off-screen shadow caster")
		quit(1)
		return
	quit()
