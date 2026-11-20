@tool
extends SubViewportContainer
## Static, actual GLB rendering for one dynamic Mesh artifact node.

var rendering: SubViewport
var scene_root: Node3D
var camera: Camera3D
var mesh_count := 0

func _ready():
	custom_minimum_size = Vector2(264, 156)
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = "本轮 Mesh 的实际 GLB 渲染；双击放大，点击下方按钮可旋转和缩放"
	rendering = SubViewport.new()
	rendering.name = "Rendering"
	rendering.size = Vector2i(264, 156)
	rendering.own_world_3d = true
	rendering.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(rendering)
	scene_root = Node3D.new()
	rendering.add_child(scene_root)
	camera = Camera3D.new()
	camera.fov = 42.0
	camera.current = true
	scene_root.add_child(camera)
	var key_light = DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-38, -32, 0)
	key_light.light_energy = 1.15
	scene_root.add_child(key_light)
	var fill_light = DirectionalLight3D.new()
	fill_light.rotation_degrees = Vector3(-15, 145, 0)
	fill_light.light_energy = 0.35
	scene_root.add_child(fill_light)
	var world = WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color(0.075, 0.095, 0.12)
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color.WHITE
	world.environment.ambient_light_energy = 0.42
	scene_root.add_child(world)

func show_mesh(path: String) -> bool:
	mesh_count = 0
	if rendering == null or path.is_empty() or not FileAccess.file_exists(path): return false
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(path, state) != OK: return false
	var generated = preload("res://addons/ainative/runtime_mesh.gd").generate(document, state)
	if generated == null: return false
	scene_root.add_child(generated)
	var bounds = AABB()
	var found = false
	var meshes = generated.find_children("*", "MeshInstance3D", true, false)
	if generated is MeshInstance3D: meshes.append(generated)
	for mesh in meshes:
		var box = mesh.global_transform * mesh.get_aabb()
		bounds = bounds.merge(box) if found else box
		found = true
	mesh_count = meshes.size()
	if not found: return false
	var center = bounds.get_center()
	var radius = maxf(bounds.size.length() * 0.5, 0.05)
	var distance = radius / sin(deg_to_rad(camera.fov * 0.5)) * 1.18
	camera.position = center + Vector3(0.55, 0.3, 1.0).normalized() * distance
	camera.near = maxf(radius / 1000.0, 0.001)
	camera.far = maxf(radius * 20.0, distance + radius * 4.0)
	camera.look_at(center)
	rendering.render_target_update_mode = SubViewport.UPDATE_ONCE
	return true
