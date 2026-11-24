@tool
extends SubViewportContainer
## Static, actual GLB rendering for one dynamic Mesh artifact node.
## File decoding runs off the UI thread; scene creation and presentation stay on the main thread.

var rendering: SubViewport
var scene_root: Node3D
var camera: Camera3D
var generated_scene: Node3D
var mesh_count := 0
var decode_count := 0
var load_error := ""
var current_path := ""
var current_kind := ""
var _request_serial := 0
var _pending_request: Dictionary = {}
var _active_request: Dictionary = {}
var _worker_task := -1
var _worker_result: Dictionary = {}

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

func is_loading() -> bool:
	return not _pending_request.is_empty() or _worker_task >= 0 or _active_request.get("kind", "") == "character"

func show_mesh(path: String) -> bool:
	return _queue_load(path, "mesh", "本轮 Mesh 的实际 GLB 渲染；双击放大，点击下方按钮可旋转和缩放")

func show_character(path: String) -> bool:
	return _queue_load(path, "character", "实际角色与骨骼预览；双击进入骨骼绑定页签")

func _queue_load(path: String, kind: String, ready_tooltip: String) -> bool:
	if rendering == null or path.is_empty() or not FileAccess.file_exists(path): return false
	if current_path == path and current_kind == kind and (is_loading() or mesh_count > 0): return true
	_request_serial += 1
	current_path = path
	current_kind = kind
	load_error = ""
	mesh_count = 0
	if is_instance_valid(generated_scene): generated_scene.queue_free()
	generated_scene = null
	_pending_request = {"serial": _request_serial, "path": path, "kind": kind, "ready_tooltip": ready_tooltip}
	tooltip_text = "正在后台加载生成物缩略图…"
	rendering.render_target_update_mode = SubViewport.UPDATE_ONCE
	return true

func _decode_request(request: Dictionary) -> Dictionary:
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(request.path, state) != OK: return {"error": "Mesh 缩略图加载失败"}
	return {"document": document, "state": state}

func _decode_request_task(request: Dictionary):
	_worker_result = _decode_request(request)

func _process(_delta):
	if _active_request.get("kind", "") == "character": _poll_character_resource()
	if _worker_task >= 0 and WorkerThreadPool.is_task_completed(_worker_task):
		WorkerThreadPool.wait_for_task_completion(_worker_task)
		_worker_task = -1
		var request = _active_request
		var decoded = _worker_result
		_active_request = {}
		_worker_result = {}
		if int(request.get("serial", -1)) == _request_serial: _present_decoded(request, decoded)
	if _worker_task < 0 and _active_request.is_empty() and not _pending_request.is_empty():
		_active_request = _pending_request
		_pending_request = {}
		decode_count += 1
		if _active_request.kind == "character":
			var error = ResourceLoader.load_threaded_request(_active_request.path, "PackedScene", true, ResourceLoader.CACHE_MODE_IGNORE)
			if error != OK:
				load_error = "角色缩略图加载失败：" + error_string(error)
				tooltip_text = load_error
				_active_request = {}
		else:
			_worker_task = WorkerThreadPool.add_task(_decode_request_task.bind(_active_request), false, "Maliang artifact thumbnail decode")

func _poll_character_resource():
	var request = _active_request
	var status = ResourceLoader.load_threaded_get_status(request.path)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
	_active_request = {}
	var packed: PackedScene = null
	if status == ResourceLoader.THREAD_LOAD_LOADED: packed = ResourceLoader.load_threaded_get(request.path) as PackedScene
	# Always finalize a completed native request, even when a newer selection superseded it.
	if int(request.get("serial", -1)) != _request_serial: return
	if packed != null:
		_present_decoded(request, {"packed": packed})
	else:
		load_error = "角色缩略图加载失败"
		tooltip_text = load_error

func _present_decoded(request: Dictionary, decoded: Dictionary):
	if decoded.has("error"):
		load_error = str(decoded.error)
		tooltip_text = load_error
		return
	var generated: Node3D
	if request.kind == "character":
		var packed: PackedScene = decoded.get("packed")
		if packed != null: generated = packed.instantiate() as Node3D
	else:
		generated = preload("res://addons/ainative/runtime_mesh.gd").generate(decoded.get("document"), decoded.get("state"))
	if generated == null:
		load_error = "生成物缩略图没有可显示的 Mesh"
		tooltip_text = load_error
		return
	tooltip_text = str(request.ready_tooltip)
	_show_generated(generated, request.kind == "character")

func _preview_mesh_bounds(mesh_instance: MeshInstance3D) -> AABB:
	if mesh_instance.skin == null:
		return mesh_instance.global_transform * mesh_instance.get_aabb()
	# Rig-preserving surface extraction retains unused source vertices. Frame
	# only indices that actually render instead of the whole original character.
	var bounds = AABB()
	var found = false
	for surface in mesh_instance.mesh.get_surface_count():
		var arrays = mesh_instance.mesh.surface_get_arrays(surface)
		var vertices = arrays[Mesh.ARRAY_VERTEX]
		var indices = arrays[Mesh.ARRAY_INDEX]
		if vertices == null: continue
		if indices == null:
			indices = range(vertices.size())
		for index in indices:
			var point: Vector3 = vertices[index]
			bounds = bounds.expand(point) if found else AABB(point, Vector3.ZERO)
			found = true
	return mesh_instance.global_transform * bounds if found else mesh_instance.global_transform * mesh_instance.get_aabb()

func _show_generated(generated: Node3D, include_skeleton: bool) -> bool:
	mesh_count = 0
	generated_scene = generated
	scene_root.add_child(generated)
	var bounds = AABB()
	var found = false
	var meshes = generated.find_children("*", "MeshInstance3D", true, false)
	if generated is MeshInstance3D: meshes.append(generated)
	for mesh in meshes:
		var box = _preview_mesh_bounds(mesh)
		bounds = bounds.merge(box) if found else box
		found = true
	mesh_count = meshes.size()
	if not found:
		generated.queue_free()
		generated_scene = null
		return false
	if include_skeleton:
		var skeleton = generated.get_node_or_null("Skeleton3D") as Skeleton3D
		if skeleton != null:
			var overlay = MeshInstance3D.new()
			var lines = ImmediateMesh.new()
			lines.surface_begin(Mesh.PRIMITIVE_LINES)
			for index in skeleton.get_bone_count():
				var parent = skeleton.get_bone_parent(index)
				if parent<0: continue
				lines.surface_add_vertex(skeleton.get_bone_global_rest(index).origin)
				lines.surface_add_vertex(skeleton.get_bone_global_rest(parent).origin)
			lines.surface_end()
			overlay.mesh = lines
			var material = StandardMaterial3D.new()
			material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			material.no_depth_test = true
			material.albedo_color = Color(1.0,0.65,0.1)
			overlay.material_override = material
			generated.add_child(overlay)
	var center = bounds.get_center()
	var radius = maxf(bounds.size.length() * 0.5, 0.05)
	var distance = radius / sin(deg_to_rad(camera.fov * 0.5)) * 1.18
	camera.position = center + Vector3(0.55, 0.3, 1.0).normalized() * distance
	camera.near = maxf(radius / 1000.0, 0.001)
	camera.far = radius * 20.0
	camera.look_at(center)
	rendering.render_target_update_mode = SubViewport.UPDATE_ONCE
	return true

func _exit_tree():
	_request_serial += 1
	_pending_request = {}
	# Native threaded ResourceLoader requests are owned by ResourceLoader, not this Node.
	# Only the bounded GLTFDocument worker needs joining; it never waits for the main thread.
	_active_request = {}
	if _worker_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_worker_task)
		_worker_task = -1
	_worker_result = {}
