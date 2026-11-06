@tool
extends VBoxContainer
# Local machine settings are intentionally excluded from workflow serialization.
var rigging_panel: VBoxContainer
var generator_choice: OptionButton
var graph: GraphEdit
var status: Label
var path_edit: LineEdit
var source_edit: LineEdit
var context_edit: LineEdit
var text_edit: TextEdit
var params_edit: TextEdit
var python_edit: LineEdit
var host_edit: LineEdit
var factory_edit: LineEdit
var target_edit: LineEdit
var texture: TextureRect
var viewport: SubViewport
var mesh_container: SubViewportContainer
var preview_root: Node3D
var dialog: ConfirmationDialog
var nodes: Array = []
var edges: Array = []
var selected_id = ""
var run_id = ""
var current: Dictionary = {}
var jobs: Dictionary = {}
var serial = 0
var heartbeat = 0
var auto_step = false
var creating = false
var cancel_create = false
var preview_token = ""
var preview_run = ""
var preview_node = ""
var preview_resource: Resource
var preview_scene: Node
var staged = ""
var confirmation: Dictionary = {}
var state_dir = ""
var db = ""

func line(parent: Node, placeholder: String, value: String = "") -> LineEdit:
	var edit = LineEdit.new()
	edit.placeholder_text = placeholder
	edit.text = value
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(edit)
	return edit

func button(parent: Node, label: String, action: Callable):
	var b = Button.new()
	b.text = label
	b.pressed.connect(action)
	parent.add_child(b)

func _ready():
	custom_minimum_size = Vector2(900, 520)
	var scroll = ScrollContainer.new()
	scroll.name = 'WorkbenchScroll'
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.follow_focus = true
	add_child(scroll)
	var content = VBoxContainer.new()
	content.name = 'WorkbenchContent'
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.add_child(content)
	state_dir = ProjectSettings.globalize_path("user://ainative")
	DirAccess.make_dir_recursive_absolute(state_dir)
	db = state_dir.path_join("executor.sqlite")
	var settings = ConfigFile.new()
	settings.load(state_dir.path_join("local.cfg"))
	var machine = HBoxContainer.new()
	content.add_child(machine)
	python_edit = line(machine, "Trusted local Python executable", OS.get_environment("AINATIVE_PYTHON") if OS.has_environment("AINATIVE_PYTHON") else settings.get_value("host", "python", "python"))
	host_edit = line(machine, "Trusted editor_host.py path", settings.get_value("host", "script", ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")))
	factory_edit = line(machine, "Trusted provider factory", OS.get_environment("AINATIVE_PROVIDER_FACTORY") if OS.has_environment("AINATIVE_PROVIDER_FACTORY") else settings.get_value("host", "factory", "editor_demo:factory"))
	button(machine, "Save local settings", save_settings)
	var bar = HBoxContainer.new()
	content.add_child(bar)
	path_edit = line(bar, "Workflow JSON path", ProjectSettings.globalize_path("user://workflow.json"))
	button(bar, "Save graph", save_graph)
	button(bar, "Open graph", open_graph)
	button(bar, "+ Copy node", add_node)
	generator_choice = OptionButton.new()
	for kind in ["text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh"]: generator_choice.add_item(kind)
	bar.add_child(generator_choice)
	button(bar, "+ Generate", add_generator)
	button(bar, "Delete selected", delete_node)
	button(bar, "Run", start_run)
	button(bar, "Cancel", cancel_run)
	button(bar, "Retry selected", retry_node)
	button(bar, "Resume run", resume_run)
	var split = HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(split)
	graph = GraphEdit.new()
	graph.custom_minimum_size = Vector2(460, 320)
	graph.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(graph)
	graph.connection_request.connect(connect_nodes)
	graph.disconnection_request.connect(disconnect_nodes)
	var inspector = VBoxContainer.new()
	inspector.custom_minimum_size.x = 360
	split.add_child(inspector)
	source_edit = line(inspector, "Source absolute PNG/JPEG/GLB/embedded glTF path")
	context_edit = line(inspector, "Image context absolute path (optional)")
	text_edit = TextEdit.new()
	text_edit.placeholder_text = "Text context (no credentials)"
	text_edit.custom_minimum_size.y = 65
	inspector.add_child(text_edit)
	params_edit = TextEdit.new()
	params_edit.placeholder_text = 'Parameters JSON: {"delay":2,"fail":false}'
	params_edit.custom_minimum_size.y = 55
	inspector.add_child(params_edit)
	button(inspector, "Apply selected fields", apply_fields)
	button(inspector, "Clear embedded source / context", clear_embedded)
	button(inspector, "Preview selected result", request_preview)
	texture = TextureRect.new()
	texture.custom_minimum_size = Vector2(240, 120)
	texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	inspector.add_child(texture)
	texture.hide()
	var container = SubViewportContainer.new()
	mesh_container = container
	container.custom_minimum_size = Vector2(360, 280)
	container.stretch = true
	inspector.add_child(container)
	container.hide()
	viewport = SubViewport.new()
	viewport.size = Vector2i(360, 160)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(viewport)
	preview_root = Node3D.new()
	viewport.add_child(preview_root)
	var camera = Camera3D.new()
	camera.position = Vector3(2, 2, 4)
	preview_root.add_child(camera)
	camera.look_at(Vector3.ZERO)
	var light = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -30, 0)
	preview_root.add_child(light)
	var environment = WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.08, 0.10, 0.13)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.3
	preview_root.add_child(environment)
	rigging_panel = preload('res://addons/ainative/rigging_panel.gd').new()
	content.add_child(rigging_panel)
	rigging_panel.initialize(self)
	var interop_panel = preload('res://addons/ainative/interop_panel.gd').new()
	content.add_child(interop_panel)
	interop_panel.initialize(self)
	var garments_panel = preload('res://addons/ainative/garments_panel.gd').new()
	content.add_child(garments_panel)
	garments_panel.initialize(self)
	var motion_panel = preload('res://addons/ainative/motion_panel.gd').new()
	content.add_child(motion_panel)
	motion_panel.initialize(self)
	var customization_panel = preload('res://addons/ainative/customization_panel.gd').new()
	content.add_child(customization_panel)
	customization_panel.initialize(self)
	var layering_panel = preload('res://addons/ainative/layering_panel.gd').new()
	content.add_child(layering_panel)
	layering_panel.initialize(self)
	var cloth_panel = preload('res://addons/ainative/cloth_panel.gd').new()
	content.add_child(cloth_panel)
	cloth_panel.initialize(self)
	var publish_bar = HBoxContainer.new()
	content.add_child(publish_bar)
	target_edit = line(publish_bar, "New .tres (image) or .tscn (mesh) absolute target", ProjectSettings.globalize_path("res://published.tres"))
	button(publish_bar, "Review & publish", review_publish)
	dialog = ConfirmationDialog.new()
	add_child(dialog)
	dialog.confirmed.connect(confirm_publish)
	status = Label.new()
	status.text = "Copy demo or ComfyUI generation. Configure local factory for generation."
	content.add_child(status)
	if FileAccess.file_exists(state_dir.path_join("last_run.txt")):
		run_id = FileAccess.get_file_as_string(state_dir.path_join("last_run.txt"))
	add_node()

func save_settings():
	var c = ConfigFile.new()
	c.set_value("host", "python", python_edit.text)
	c.set_value("host", "script", host_edit.text)
	c.set_value("host", "factory", factory_edit.text)
	c.save(state_dir.path_join("local.cfg"))

func add_node():
	var id = "n" + str(Time.get_ticks_usec())
	nodes.append({"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": "", "image_context": "", "text": "", "parameters": {"delay": 2, "fail": false}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45})
	rebuild()
	select_node(id)

func add_generator():
	var kind = generator_choice.get_item_text(generator_choice.selected)
	var id = "n" + str(Time.get_ticks_usec())
	nodes.append({"id": id, "type": kind, "version": "1", "provider": "comfy", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "a small stone sculpture on white background", "seed": 1}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45})
	rebuild()
	select_node(id)

func output_kind(data: Dictionary) -> int:
	return 2 if data.get("type", "copy").ends_with("mesh") else 0 if data.get("type", "copy") == "copy" else 1

func rebuild():
	graph.clear_connections()
	for child in graph.get_children():
		if child is GraphNode:
			graph.remove_child(child)
			child.queue_free()
	for data in nodes:
		var node = GraphNode.new()
		node.name = data.id
		node.title = data.id + " / " + data.get("type", "copy")
		node.position_offset = Vector2(data.x, data.y)
		var label = Label.new()
		label.text = "Local copy (not AI)" if data.get("type", "copy") == "copy" else data.type + " (ComfyUI)"
		node.add_child(label)
		node.set_slot(0, not data.get("type", "copy").begins_with("text_"), 0, Color.SKY_BLUE, true, 0, Color.SKY_BLUE)
		graph.add_child(node)
		node.node_selected.connect(select_node.bind(data.id))
		node.position_offset_changed.connect(func(): data.x = node.position_offset.x; data.y = node.position_offset.y)
	for edge in edges:
		graph.connect_node(edge.from, 0, edge.to, 0)

func select_node(id: String):
	selected_id = id
	for data in nodes:
		if data.id == id:
			source_edit.text = data.source
			context_edit.text = data.image_context
			text_edit.text = data.text
			params_edit.text = JSON.stringify(data.parameters)

func apply_fields() -> bool:
	var params = JSON.parse_string(params_edit.text)
	if not params is Dictionary or not safe(params):
		status.text = "Invalid parameters / forbidden credential key"
		return false
	for data in nodes:
		if data.id == selected_id:
			data.source = source_edit.text
			data.image_context = context_edit.text
			data.text = text_edit.text
			data.parameters = params
	return true

func safe(value) -> bool:
	if value is Dictionary:
		for key in value:
			if str(key).to_lower() in ["token", "api_key", "apikey", "password", "secret", "authorization", "credentials", "factory", "python"] or not safe(value[key]): return false
	elif value is Array:
		for child in value:
			if not safe(child): return false
	return true

func connect_nodes(from: StringName, _fp: int, to: StringName, _tp: int):
	if from == to: return
	var source_node = nodes.filter(func(n): return n.id == from)
	var target_node = nodes.filter(func(n): return n.id == to)
	if source_node.is_empty() or target_node.is_empty(): return
	if target_node[0].get("type", "copy").begins_with("text_"): return
	if target_node[0].get("type", "copy") != "copy" and output_kind(source_node[0]) != 1:
		status.text = "Generation source requires an image output"
		return
	for edge in edges:
		if edge.to == to: return
	edges.append({"from": str(from), "to": str(to), "input": "source", "output": "result"})
	rebuild()

func disconnect_nodes(from: StringName, _fp: int, to: StringName, _tp: int):
	edges = edges.filter(func(e): return not (e.from == from and e.to == to))
	rebuild()

func delete_node():
	nodes = nodes.filter(func(n): return n.id != selected_id)
	edges = edges.filter(func(e): return e.from != selected_id and e.to != selected_id)
	selected_id = ""
	rebuild()

func model() -> Dictionary:
	return {"format": 1, "nodes": nodes, "edges": edges}

func save_graph():
	if not apply_fields(): return
	if path_edit.text.get_extension().to_lower() != "json":
		status.text = "Workflow target must be .json"
		return
	for n in nodes:
		if path_edit.text.simplify_path() in [n.source.simplify_path(), n.image_context.simplify_path()]:
			status.text = "Cannot overwrite an input asset"
			return
	var portable = model().duplicate(true)
	for n in portable.nodes:
		for field in ["source", "image_context"]:
			if not n[field].is_empty():
				var input = FileAccess.open(n[field], FileAccess.READ)
				if input == null:
					status.text = "Cannot snapshot input; previous workflow preserved"
					return
				var bytes = input.get_buffer(input.get_length())
				if bytes.is_empty() or input.get_error() != OK:
					status.text = "Cannot read input; previous workflow preserved"
					return
				input.close()
				var hash_context = HashingContext.new()
				hash_context.start(HashingContext.HASH_SHA256)
				hash_context.update(bytes)
				n[field + "_snapshot"] = {"content_base64": Marshalls.raw_to_base64(bytes), "content_sha256": hash_context.finish().hex_encode(), "extension": "." + n[field].get_extension().to_lower()}
				n[field] = ""
	var temporary = path_edit.text + "." + str(Time.get_ticks_usec()) + ".tmp"
	var f = FileAccess.open(temporary, FileAccess.WRITE)
	if f == null:
		status.text = "Cannot save graph"
		return
	f.store_string(JSON.stringify(portable, "\t"))
	f.flush()
	var failed = f.get_error() != OK
	f.close()
	if failed or DirAccess.rename_absolute(temporary, path_edit.text) != OK:
		DirAccess.remove_absolute(temporary)
		status.text = "Cannot replace workflow; previous workflow preserved"
		return
	status.text = "Graph saved with embedded input snapshots"

func clear_embedded():
	for data in nodes:
		if data.id == selected_id:
			data.erase("source_snapshot")
			data.erase("image_context_snapshot")
	status.text = "Embedded source/context removed; path fields still apply"

func open_graph():
	var value = JSON.parse_string(FileAccess.get_file_as_string(path_edit.text))
	if not value is Dictionary or not safe(value) or value.get("format") != 1 or not value.get("nodes") is Array or not value.get("edges") is Array:
		status.text = "Invalid workflow"
		return
	var ids = []
	for n in value.nodes:
		if not n is Dictionary or not n.has_all(["id", "source", "image_context", "text", "parameters", "x", "y"]):
			status.text = "Invalid node"
			return
		for key in ["id", "source", "image_context", "text"]:
			if not n[key] is String:
				status.text = "Invalid node field type"
				return
		if n.id.is_empty() or not n.id.is_valid_identifier() or n.id in ids or not n.parameters is Dictionary or not (n.x is float or n.x is int) or not (n.y is float or n.y is int):
			status.text = "Invalid node identity/parameters/position"
			return
		for key in ["type", "version", "provider"]:
			if n.has(key) and not n[key] is String:
				status.text = "Invalid definition field"
				return
		ids.append(n.id)
	var destinations = []
	for e in value.edges:
		if not e is Dictionary or not e.has_all(["from", "to"]) or not e.from is String or not e.to is String:
			status.text = "Invalid edge"
			return
		if not e.from in ids or not e.to in ids or e.from == e.to or e.to in destinations:
			status.text = "Invalid edge endpoint"
			return
		destinations.append(e.to)
	nodes = value.nodes
	edges = value.edges
	rebuild()
	if not nodes.is_empty(): select_node(nodes[0].id)
	status.text = "Graph reopened"

func start_run():
	if not apply_fields() or not jobs.is_empty(): return
	preview_token = ""
	auto_step = true
	creating = true
	cancel_create = false
	launch("create", {"model": model()})

func resume_run():
	if run_id == "" or not jobs.is_empty(): return
	auto_step = true
	launch("step", {"run": run_id})

func cancel_run():
	if creating:
		cancel_create = true
		auto_step = false
		return
	auto_step = false
	preview_token = ""
	if run_id != "": launch("cancel", {"run": run_id})

func retry_node():
	preview_token = ""
	if run_id != "": launch("retry", {"run": run_id, "node": selected_id})

func launch(command: String, spec: Dictionary):
	serial += 1
	var prefix = state_dir.path_join(str(OS.get_process_id()) + "-" + str(serial))
	var f = FileAccess.open(prefix + ".json", FileAccess.WRITE)
	f.store_string(JSON.stringify(spec))
	f.close()
	var pid = OS.create_process(python_edit.text, PackedStringArray([host_edit.text, command, "--db", db, "--factory", factory_edit.text, "--spec", prefix + ".json", "--result", prefix + ".result"]))
	if pid < 0:
		status.text = "Cannot start trusted Python host"
		auto_step = false
		return
	jobs[pid] = {"command": command, "prefix": prefix, "spec": spec}

func _process(_delta):
	heartbeat += 1
	for pid in jobs.keys():
		if OS.is_process_running(pid): continue
		var job = jobs[pid]
		jobs.erase(pid)
		var result = JSON.parse_string(FileAccess.get_file_as_string(job.prefix + ".result")) if FileAccess.file_exists(job.prefix + ".result") else null
		DirAccess.remove_absolute(job.prefix + ".json")
		DirAccess.remove_absolute(job.prefix + ".result")
		if not result is Dictionary or not result.get("ok", false):
			status.text = "Command failed: " + job.command + " (sources untouched)"
			auto_step = false
			if job.command == "create": creating = false
			continue
		var data = result.result
		if job.command == "create":
			creating = false
			run_id = data.run_id
			var f = FileAccess.open(state_dir.path_join("last_run.txt"), FileAccess.WRITE)
			f.store_string(run_id)
			if cancel_create: launch("cancel", {"run": run_id})
		elif job.command == "preview":
			if job.spec.run == run_id: load_preview(data, job.spec.node)
		elif job.command == "publish":
			status.text = "Published new file: " + data.path
			if Engine.is_editor_hint(): EditorInterface.get_resource_filesystem().scan()
		else:
			current = data
			status.text = "Executor: " + data.state + " | heartbeat " + str(heartbeat)
			for id in data.nodes:
				status.text += " | " + id + ": " + data.nodes[id].state + " attempt " + str(data.nodes[id].attempt)
			if job.command == "retry": auto_step = true
			if data.state != "running": auto_step = false
			if data.state == "reconcile": status.text += " | Unknown submission outcome: paused. Resume run performs one lookup; never blindly retry."
	if auto_step and jobs.is_empty() and run_id != "": launch("step", {"run": run_id})

func request_preview():
	preview_token = ""
	launch("preview", {"run": run_id, "node": selected_id})

func load_preview(data: Dictionary, node_id: String):
	preview_resource = null
	if is_instance_valid(preview_scene): preview_scene.queue_free()
	preview_scene = null
	texture.texture = null
	texture.hide()
	mesh_container.hide()
	if data.type == "image":
		var image = Image.load_from_file(data.path)
		if image == null: status.text = "Image preview failed"; return
		preview_resource = ImageTexture.create_from_image(image)
		texture.texture = preview_resource
		texture.show()
	else:
		var document = GLTFDocument.new()
		var state = GLTFState.new()
		if document.append_from_file(data.path, state) != OK: status.text = "Mesh preview failed"; return
		preview_scene = document.generate_scene(state)
		if preview_scene == null: return
		preview_root.add_child(preview_scene)
		rigging_panel.set_source(data.path)
		mesh_container.show()
		frame_mesh()
	preview_token = data.token
	preview_run = run_id
	preview_node = node_id
	status.text = "Preview loaded: " + data.type + " — review before publishing"

func frame_mesh():
	var bounds = AABB()
	var found = false
	var meshes = preview_scene.find_children("*", "MeshInstance3D", true, false)
	if preview_scene is MeshInstance3D: meshes.append(preview_scene)
	for mesh in meshes:
		var box = mesh.global_transform * mesh.get_aabb()
		bounds = bounds.merge(box) if found else box
		found = true
	if found:
		var center = bounds.get_center()
		var radius = maxf(bounds.size.length() * 0.5, 0.05)
		var camera = preview_root.get_child(0) as Camera3D
		var distance = radius / sin(deg_to_rad(camera.fov * 0.5)) * 1.15
		camera.position = center + Vector3(0.5, 0.3, 1).normalized() * distance
		camera.near = maxf(radius / 1000, 0.001)
		camera.far = radius * 20
		camera.look_at(center)

func set_owners(node: Node, root: Node):
	for child in node.get_children():
		child.owner = root
		set_owners(child, root)

func review_publish():
	if preview_token == "" or preview_run != run_id:
		status.text = "Preview current successful result first"
		return
	var extension = ".tres" if preview_resource != null else ".tscn"
	if target_edit.text.get_extension() != extension.substr(1): status.text = "Target must end in " + extension; return
	staged = state_dir.path_join("staged-" + str(Time.get_ticks_usec()) + extension)
	var err
	if preview_resource != null: err = ResourceSaver.save(preview_resource, staged)
	else:
		var packed = PackedScene.new()
		set_owners(preview_scene, preview_scene)
		err = packed.pack(preview_scene)
		if err == OK: err = ResourceSaver.save(packed, staged)
	if err != OK: status.text = "Encoding failed"; return
	confirmation = {"run": preview_run, "node": preview_node, "confirmation": preview_token, "staged": staged, "staged_sha256": FileAccess.get_sha256(staged), "target": target_edit.text}
	dialog.dialog_text = "Publish this preview as NEW file?\nRun: " + preview_run + "\nRevision: " + preview_token + "\nEncoded SHA256: " + confirmation.staged_sha256 + "\n" + target_edit.text
	dialog.popup_centered()

func confirm_publish():
	if confirmation.get("run") != run_id or confirmation.get("confirmation") != preview_token:
		status.text = "Preview changed; confirm again"
		return
	launch("publish", confirmation.duplicate())
	confirmation = {}

func _exit_tree():
	for pid in jobs:
		if OS.is_process_running(pid): OS.kill(pid)
