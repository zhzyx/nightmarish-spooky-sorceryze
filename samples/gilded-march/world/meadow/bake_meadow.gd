extends SceneTree
## Rebuild the static meadow after editing the terrain:
## <project editor> --path <GildedMarch> --script res://world/meadow/bake_meadow.gd

const DIR := "res://world/meadow/"
const WIDTH := 1024
const SPACING := 1.5
const HALF_WORLD := 768.0
const PLOT := [6.0, 12.0, 25.0]
const FADE_IN := [Vector2(-2,-1), Vector2(8,20), Vector2(43,75)]
const FADE_OUT := [Vector2(17,30), Vector2(54,96), Vector2(175,300)]

var rng := RandomNumberGenerator.new()
var stream := SurfaceTool.new()
var plant_uv := Vector2.ZERO
var surface := Image.create_empty(WIDTH, WIDTH, false, Image.FORMAT_RGBA8)
var terrain: Terrain3D
var meadow := Node3D.new()

func _initialize() -> void:
	bake.call_deferred()

func bake() -> void:
	change_scene_to_file("res://March.tscn")
	await scene_changed
	if RenderingServer.get_rendering_device() == null:
		push_error("Rebuild with the project Vulkan renderer so MultiMesh buffers are serialized")
		quit(1)
		return
	terrain = current_scene.get_node("Terrain3D")
	if terrain.data.get_region_count() != 16 or not is_equal_approx(terrain.vertex_spacing, SPACING):
		push_error("Expected the 16 authored Gilded March terrain regions at 1.5 m spacing")
		quit(1)
		return
	meadow.name = "WindMeadow"
	bake_surface()
	var atlas := ImageTexture.create_from_image(surface)
	for level in 3:
		build_layer(level, atlas)
	var packed := PackedScene.new()
	var err := packed.pack(meadow)
	if err == OK:
		err = ResourceSaver.save(packed, DIR + "meadow.scn", ResourceSaver.FLAG_COMPRESS)
	print("Meadow bake: ", meadow.get_child_count(), " batches, ", error_string(err))
	meadow.free()
	quit(0 if err == OK else 1)

func bake_surface() -> void:
	var data := terrain.data
	for z in WIDTH:
		for x in WIDTH:
			var p := Vector3(x * SPACING - HALF_WORLD, 0, z * SPACING - HALF_WORLD)
			var h := data.get_height(p)
			var density := 0.0
			if is_finite(h):
				var control := data.get_control(p)
				var overlay := (control >> 22) & 31
				var blend := float((control >> 14) & 255) / 255.0
				density = 1.0 - smoothstep(0.14, 0.81 if overlay == 1 else 0.68, blend)
				density *= smoothstep(0.5, 2.8, h - (16.12 - (p.z+HALF_WORLD)*0.012))
				# Leave the spring basin and its apron clear of grass.
				density *= smoothstep(2.8, 4.1, Vector2(p.x, p.z).distance_to(Vector2(25.26, 332.20)))
				if (absf(p.x+210) < 46 and absf(p.z+215) < 32) or (absf(p.x-125.53) < 82 and absf(p.z+65) < 5):
					density = 0.0
			else:
				h = 0.0
			var packed_h := clampi(roundi((h + 64.0) * 128.0), 0, 65535)
			surface.set_pixel(x, z, Color8(packed_h >> 8, packed_h & 255, roundi(density*255), 255))

func vertex(p: Vector3, color: Color, bend: float, silk := 0.0) -> void:
	stream.set_color(color)
	stream.set_normal(Vector3.UP)
	stream.set_uv(Vector2(bend, silk))
	stream.set_uv2(plant_uv)
	stream.add_vertex(p)

func blade(root_pos: Vector3, azimuth: float, h: float, w: float, lean: float, young: Color, mature: Color, detail: bool) -> void:
	var run := Vector3(cos(azimuth),0,sin(azimuth))
	var side := Vector3(-run.z,0,run.x) * w
	var mid := root_pos + Vector3.UP*h*0.62 + run*lean*0.29
	var tip := root_pos + Vector3.UP*h + run*lean
	var dark := young.darkened(0.57)
	if detail:
		var prev := root_pos
		var prev_width := 0.42
		var prev_t := 0.0
		for t: float in [0.39,0.73,1.0]:
			var center := root_pos + Vector3.UP*h*(1.32*t - 0.32*t*t) + run*lean*t*t
			var width := sin(PI*(0.19 + t*0.81)) * (1.0 - 0.33*t)
			var low := dark.lerp(mature,prev_t)
			var high := dark.lerp(mature,t)
			var ridge := center + run*w*width*0.74
			var prev_ridge := prev + run*w*prev_width*0.74
			for sign_dir: float in [-1.0,1.0]:
				var left := prev+side*sign_dir*prev_width
				var right := center+side*sign_dir*width
				vertex(prev_ridge,low,prev_t); vertex(left,low,prev_t,sign_dir); vertex(right,high,t,sign_dir)
				if t < 1.0:
					vertex(prev_ridge,low,prev_t); vertex(right,high,t,sign_dir); vertex(ridge,high,t)
			prev = center
			prev_t = t
			prev_width = width
	else:
		vertex(root_pos-side*0.58,dark,0); vertex(root_pos+side*0.58,dark,0); vertex(mid+side,young,0.53)
		vertex(root_pos-side*0.58,dark,0); vertex(mid+side,young,0.53); vertex(mid-side,young,0.53)
		vertex(mid-side,young,0.53); vertex(mid+side,young,0.53); vertex(tip,mature,1.0)

func seed_head(p: Vector3, h: float, angle: float, pale: Color, detailed: bool) -> void:
	var run := Vector3(cos(angle),0,sin(angle))
	var side := Vector3(-run.z,0,run.x)
	var neck := p + Vector3.UP * h * 0.78 + run * h * 0.18
	var top := neck + Vector3.UP * h * 0.25 + run * h * 0.13
	var straw := pale.darkened(0.48)
	var stem := side * (0.0055 if detailed else 0.013)
	vertex(p-stem,straw,0); vertex(p+stem,straw,0); vertex(neck+stem*0.60,pale,0.68)
	vertex(p-stem,straw,0); vertex(neck+stem*0.60,pale,0.68); vertex(neck-stem*0.60,pale,0.68)
	var middle := neck.lerp(top,0.54)
	if not detailed:
		var breadth := side*0.023
		vertex(neck,straw,0.68); vertex(middle+breadth,pale,0.83,2); vertex(top,pale,1,2)
		vertex(neck,straw,0.68); vertex(top,pale,1,2); vertex(middle-breadth,pale,0.83,2)
		return
	# A fine central stem carries either upright awned grains or loose, nodding oat spikelets.
	var oat := rng.randf() < 0.32
	var rachis := side*0.004
	vertex(neck-rachis,straw,0.68); vertex(neck+rachis,pale,0.68); vertex(top,pale,1,2)
	for j in 8:
		var t := (j+0.2)/9.0
		var origin := neck.lerp(top,t)
		var sign_dir := -1.0 if j%2==0 else 1.0
		var across := side*sign_dir + run*(0.26*sin(j*2.4))
		var lean := (1.2-t)*rng.randf_range(0.038,0.069)
		var grain_base := origin
		var grain_dir := Vector3.UP*0.062 + across*lean
		if oat:
			grain_base += across*lean*1.75 + Vector3.UP*0.021
			vertex(origin-run*0.003,straw,0.7+t*0.3); vertex(origin+run*0.003,pale,0.7+t*0.3); vertex(grain_base,pale,0.74+t*0.26)
			grain_dir = Vector3.DOWN*0.060 + across*0.028
		var mid := grain_base + grain_dir*0.52
		var husk := side * (0.011 if oat else 0.008) + run*0.004
		var end := grain_base + grain_dir
		var bend := 0.71+t*0.27
		vertex(grain_base,straw,bend,2); vertex(mid+husk,pale,bend,2); vertex(end,pale,bend+0.02,2)
		vertex(grain_base,straw,bend,2); vertex(end,pale,bend+0.02,2); vertex(mid-husk,straw,bend,2)
		vertex(end-husk*0.22,pale,bend+0.02,2); vertex(end+husk*0.22,pale,bend+0.02,2); vertex(end+grain_dir*0.93,pale,bend+0.03,2)

func plot_mesh(level: int) -> ArrayMesh:
	rng.seed = 57381 + level
	var width: float = PLOT[level]
	stream.begin(Mesh.PRIMITIVE_TRIANGLES)
	var greens := [Color("#364627"), Color("#485b32"), Color("#66763b"), Color("#6e6736")]
	var tips := [Color("#929b56"), Color("#a6ae71"), Color("#ac9d63"), Color("#ba9e67")]
	var count: int = [89,69,70][level]
	for i in count:
		plant_uv = Vector2(rng.randf(),rng.randf())
		var center := Vector3(plant_uv.x-0.5,0,plant_uv.y-0.5)*width
		var tone := rng.randi_range(0,3)
		var base: Color = greens[tone].srgb_to_linear()
		var tip: Color = tips[tone].srgb_to_linear()
		var h := rng.randf_range(0.28,0.70) * (1.0+level*0.14)
		var rotation := rng.randf()*TAU
		var blades: int = [13,8,7][level]
		for j in blades:
			var a := rotation + j*2.40 + rng.randf_range(-0.44,0.44)
			var spread := rng.randf_range(0.035,0.145)*(1.0+level*0.8)
			var p := center + Vector3(cos(a)*spread,-0.015,sin(a)*spread)
			blade(p,a,h*rng.randf_range(0.48,1.14),rng.randf_range(0.010,0.021)*(1.0+level*1.55),rng.randf_range(0.16,0.53)*(1.0+level*0.55),base,tip.darkened(rng.randf_range(0.00,0.28)),level==0)
		if rng.randf() < [0.69,0.46,0.24][level]:
			var ear := Color("#cdbd95").lerp(Color("#92704c"),rng.randf()).srgb_to_linear()
			for j in rng.randi_range(1,3 if level==0 else 2):
				var a := rng.randf()*TAU
				seed_head(center+Vector3(cos(a)*0.11,0,sin(a)*0.11),h*rng.randf_range(1.38,2.0),a,ear,level==0)
	# Finer basal growth fills the spaces between the taller flowering tussocks.
	if level == 0:
		for i in 190:
			plant_uv = Vector2(rng.randf(),rng.randf())
			var center := Vector3(plant_uv.x-0.5,0,plant_uv.y-0.5)*width
			var length := rng.randf_range(0.12,0.29)
			var young := Color("#52633b").lerp(Color("#7d8447"),rng.randf()).srgb_to_linear()
			var mature := Color("#8c9758").lerp(Color("#ad985e"),rng.randf()).srgb_to_linear()
			for j in 8:
				var a := rng.randf()*TAU
				var foot := center + Vector3(cos(a),0,sin(a))*rng.randf_range(0.03,0.14)
				blade(foot,a,length*rng.randf_range(0.6,1.2),rng.randf_range(0.011,0.019),rng.randf_range(0.10,0.25),young,mature,false)
	stream.index()
	var mesh := stream.commit()
	stream.clear()
	return mesh

func build_layer(level: int, atlas: ImageTexture) -> void:
	var width: float = PLOT[level]
	var mesh := plot_mesh(level)
	var material := ShaderMaterial.new()
	material.shader = load(DIR+"meadow.gdshader")
	material.set_shader_parameter("field",atlas)
	material.set_shader_parameter("patch_width",width)
	material.set_shader_parameter("fade_in",FADE_IN[level])
	material.set_shader_parameter("fade_out",FADE_OUT[level])
	mesh.surface_set_material(0,material)
	# The renderer culls a block of plots with one draw. All blocks share this GPU buffer.
	var per_side := 5
	var span := width * per_side
	var batch := MultiMesh.new()
	batch.transform_format = MultiMesh.TRANSFORM_3D
	batch.mesh = mesh
	batch.instance_count = per_side*per_side
	for iz in per_side:
		for ix in per_side:
			var rot := Basis(Vector3.UP, rng.randi_range(0,3)*PI/2.0)
			batch.set_instance_transform(iz*per_side+ix,Transform3D(rot,Vector3((ix+0.5)*width,0,(iz+0.5)*width)))
	for iz in ceili(2*HALF_WORLD/span):
		for ix in ceili(2*HALF_WORLD/span):
			var corner := Vector2(ix*span, iz*span)
			var first := Vector2i(corner/SPACING)
			var end := Vector2i((corner+Vector2.ONE*span)/SPACING).min(Vector2i(WIDTH-1,WIDTH-1))
			var low := INF
			var high := -INF
			for z in range(first.y,end.y+1):
				for x in range(first.x,end.x+1):
					var c := surface.get_pixel(x,z)
					if c.b8 < 3: continue
					var y := (c.r8*256+c.g8)/128.0-64.0
					low = minf(low,y)
					high = maxf(high,y)
			if high < low: continue
			var node := MultiMeshInstance3D.new()
			node.multimesh = batch
			node.name = "Grass_%d_%d_%d" % [level,ix,iz]
			node.position = Vector3(corner.x-HALF_WORLD,0,corner.y-HALF_WORLD)
			node.custom_aabb = AABB(Vector3(-2,low-3,-2), Vector3(span+4,high-low+8,span+4))
			var radius := node.custom_aabb.size.length()*0.5
			node.visibility_range_end = FADE_OUT[level].y + radius + 2
			if level > 0: node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			meadow.add_child(node)
			node.owner = meadow
