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
var preview_target = ""
var preview_history: Dictionary = {}
var history_choice: OptionButton
var preview_token = ""
var preview_run = ""
var preview_node = ""
var preview_resource: Resource
var preview_scene: Node
var staged = ""
var confirmation: Dictionary = {}
var state_dir = ""
var db = ""
var native_sections: Dictionary = {}
var native_buttons: Dictionary = {}
var native_scroll: ScrollContainer
var native_inspector_fields: Array = []
var native_other_panels: Array = []
var context_menu: PopupMenu
var context_history_menu: PopupMenu
var context_node_ids: Array = []
var context_connection: Dictionary = {}
var context_position = Vector2.ZERO
var context_model = ""
var context_run = ""
var context_selection: Array = []
var context_inspected_id = ""
var node_picker: ConfirmationDialog
var node_picker_search: LineEdit
var node_picker_list: ItemList
var workflow_menu: MenuButton
var workflow_dialog: ConfirmationDialog
var workflow_mode = ""
var inspector_fields: VBoxContainer
const CONTEXT_ADD = 1
const CONTEXT_RUN = 2
const CONTEXT_PREVIEW = 3
const CONTEXT_EDIT = 4
const CONTEXT_RETRY = 5
const CONTEXT_DUPLICATE = 6
const CONTEXT_DELETE = 7
const CONTEXT_DISCONNECT = 8
const CONTEXT_SAVE = 9
const CONTEXT_OPEN = 10
const CONTEXT_RUN_ALL = 11
const CONTEXT_HISTORY = 12
const NODE_KINDS = ["text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh", "copy"]

func node_label(kind: String) -> String:
	return {"copy":"离线复制", "text_to_image":"文字生成图像", "image_to_image":"图像生成图像", "image_to_mesh":"图像生成网格", "text_to_mesh":"文字生成网格"}.get(kind,kind)

func state_label(value: String) -> String:
	return {"pending":"等待中", "queued":"排队中", "ready":"就绪", "running":"运行中", "succeeded":"已成功", "failed":"已失败", "cancelled":"已取消", "blocked":"受阻", "reconcile":"待查询提交结果", "skipped":"已跳过"}.get(value,value)

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
	return b

func _ready():
	custom_minimum_size = Vector2(900, 520)
	var builtin = get_meta('ainative_builtin',false)
	if builtin:
		var navigation = HFlowContainer.new()
		navigation.name = 'AINativeNavigation'
		add_child(navigation)
		var group = ButtonGroup.new()
		for item in [['mesh','网格生成'],['rig','骨骼绑定'],['character','角色工作台'],['other','其他工具'],['settings','本机设置']]:
			var action = button(navigation,item[1],show_native_section.bind(item[0]))
			action.name = 'AINativeNav_'+item[0]
			action.toggle_mode = true
			action.button_group = group
			native_buttons[item[0]] = action
	var scroll = ScrollContainer.new()
	native_scroll = scroll
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
	if state_dir.is_empty(): state_dir = ProjectSettings.globalize_path("user://ainative")
	DirAccess.make_dir_recursive_absolute(state_dir)
	db = state_dir.path_join("executor.sqlite")
	var settings = ConfigFile.new()
	settings.load(state_dir.path_join("local.cfg"))
	var machine = VBoxContainer.new()
	machine.name = 'AINativeLocalSettings'
	content.add_child(machine)
	var default_python = 'python' if OS.get_name()=='Windows' or not builtin else 'python3'
	var bundled_host = str(get_meta('ainative_tools_dir','')).path_join('editor_host.py') if builtin else ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	var configured_host = bundled_host if builtin and settings.get_value('host','use_bundled_script',true) else settings.get_value('host','script',bundled_host)
	python_edit = line(machine, "本机 Python 可执行文件（3.11+）", OS.get_environment("AINATIVE_PYTHON") if OS.has_environment("AINATIVE_PYTHON") else settings.get_value("host", "python", default_python))
	host_edit = line(machine, "本机 editor_host.py 路径", configured_host)
	factory_edit = line(machine, "本机生成服务入口", OS.get_environment("AINATIVE_PROVIDER_FACTORY") if OS.has_environment("AINATIVE_PROVIDER_FACTORY") else settings.get_value("host", "factory", "editor_demo:factory"))
	button(machine, "保存本机设置", save_settings)
	button(machine, "打开本机诊断日志", open_diagnostics)
	var character_panel = preload('res://addons/ainative/character_panel.gd').new()
	content.add_child(character_panel)
	character_panel.initialize(self)
	var advanced = VBoxContainer.new()
	advanced.name = 'IndependentModuleDiagnostics'
	advanced.size_flags_vertical = Control.SIZE_EXPAND_FILL
	if not builtin: button(content,'展开独立模块诊断',func(): advanced.visible = not advanced.visible)
	content.add_child(advanced)
	advanced.hide()
	machine.reparent(advanced)
	content = advanced
	var diagnostics_title = Label.new()
	diagnostics_title.text = '独立模块诊断使用各自的角色。'
	content.add_child(diagnostics_title)
	var bar = HFlowContainer.new()
	content.add_child(bar)
	bar.name = "WorkflowToolbar"
	workflow_menu = MenuButton.new()
	workflow_menu.text = "工作流"
	bar.add_child(workflow_menu)
	workflow_menu.get_popup().add_item("保存工作流…", CONTEXT_SAVE)
	workflow_menu.get_popup().add_item("打开工作流…", CONTEXT_OPEN)
	workflow_menu.get_popup().id_pressed.connect(_workflow_action)
	workflow_menu.get_popup().about_to_popup.connect(func():
		workflow_menu.get_popup().set_item_disabled(1, is_graph_busy())
		workflow_menu.get_popup().set_item_tooltip(1, "请等待运行结束或取消后再打开" if is_graph_busy() else "打开保存的工作流"))
	button(bar, "运行", start_run)
	button(bar, "取消", cancel_run)
	button(bar, "继续运行", resume_run)
	var context_hint = Label.new()
	context_hint.text = "右键画布添加节点 · 右键节点编辑与预览 · ⇧F10 打开菜单"
	context_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	context_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(context_hint)
	workflow_dialog = ConfirmationDialog.new()
	workflow_dialog.title = "工作流文件"
	workflow_dialog.ok_button_text = "确定"
	workflow_dialog.cancel_button_text = "取消"
	var workflow_fields = VBoxContainer.new()
	workflow_dialog.add_child(workflow_fields)
	path_edit = line(workflow_fields, "工作流 JSON 绝对路径", ProjectSettings.globalize_path("user://workflow.json"))
	path_edit.custom_minimum_size.x = 420
	workflow_dialog.confirmed.connect(_workflow_confirmed)
	add_child(workflow_dialog)
	# Retained for saved automation and callers; node creation is now in the canvas menu.
	generator_choice = OptionButton.new()
	for kind in NODE_KINDS:
		if kind == "copy": continue
		generator_choice.add_item(node_label(kind))
		generator_choice.set_item_metadata(generator_choice.item_count - 1, kind)
	if builtin: generator_choice.selected = 2
	add_child(generator_choice)
	generator_choice.hide()
	var split = HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(split)
	graph = GraphEdit.new()
	graph.custom_minimum_size = Vector2(460, 320)
	graph.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(graph)
	graph.connection_request.connect(connect_nodes)
	graph.disconnection_request.connect(disconnect_nodes)
	graph.popup_request.connect(show_context_menu)
	graph.gui_input.connect(_graph_context_input)
	graph.duplicate_nodes_request.connect(_keyboard_duplicate)
	graph.delete_nodes_request.connect(_keyboard_delete)
	graph.focus_mode = Control.FOCUS_ALL
	_setup_context_controls()
	var inspector = VBoxContainer.new()
	inspector_fields = inspector
	inspector.custom_minimum_size.x = 360
	split.add_child(inspector)
	source_edit = line(inspector, "源文件绝对路径（PNG/JPEG/GLB/内嵌 glTF）")
	context_edit = line(inspector, "参考图像绝对路径（可选）")
	text_edit = TextEdit.new()
	text_edit.placeholder_text = "文字说明（请勿填写凭据）"
	text_edit.custom_minimum_size.y = 65
	inspector.add_child(text_edit)
	params_edit = TextEdit.new()
	params_edit.placeholder_text = '参数 JSON：{"delay":2,"fail":false}'
	params_edit.custom_minimum_size.y = 55
	inspector.add_child(params_edit)
	button(inspector, "应用到选中节点", apply_fields)
	button(inspector, "清除内嵌源文件和参考图像", clear_embedded)
	button(inspector, "运行并预览选中节点", func(): run_node_preview(selected_id))
	button(inspector, "预览选中结果", request_preview)
	history_choice = OptionButton.new()
	history_choice.item_selected.connect(show_history)
	inspector.add_child(history_choice)
	refresh_history()
	native_inspector_fields = inspector.get_children()
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
	var hair_panel = preload('res://addons/ainative/hair_panel.gd').new()
	content.add_child(hair_panel)
	hair_panel.initialize(self)
	var layering_panel = preload('res://addons/ainative/layering_panel.gd').new()
	content.add_child(layering_panel)
	layering_panel.initialize(self)
	var cloth_panel = preload('res://addons/ainative/cloth_panel.gd').new()
	content.add_child(cloth_panel)
	cloth_panel.initialize(self)
	native_other_panels = [interop_panel,garments_panel,motion_panel,customization_panel,hair_panel,layering_panel,cloth_panel]
	var publish_bar = HBoxContainer.new()
	content.add_child(publish_bar)
	target_edit = line(publish_bar, "新文件绝对路径：图像用 .tres，网格用 .tscn", ProjectSettings.globalize_path("res://published.tres"))
	button(publish_bar, "检查并发布", review_publish)
	dialog = ConfirmationDialog.new()
	dialog.title = "确认发布"
	dialog.ok_button_text = "发布新文件"
	dialog.cancel_button_text = "取消"
	add_child(dialog)
	dialog.confirmed.connect(confirm_publish)
	status = Label.new()
	status.text = "可使用离线复制演示或 ComfyUI 生成；真实生成需要先配置本机服务。"
	content.add_child(status)
	if builtin:
		native_sections = {'machine':machine,'character':character_panel,'advanced':advanced,'title':diagnostics_title,'bar':bar,'split':split,'publish':publish_bar}
		status.reparent(self)
		status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		show_native_section('mesh')
	if FileAccess.file_exists(state_dir.path_join("last_run.txt")):
		run_id = FileAccess.get_file_as_string(state_dir.path_join("last_run.txt"))
	add_node()

func show_native_section(section: String):
	if native_sections.is_empty(): return
	native_sections.character.visible = section=='character'
	native_sections.advanced.visible = section!='character'
	native_sections.machine.visible = section=='settings'
	native_sections.bar.visible = section=='mesh'
	native_sections.split.visible = section in ['mesh','rig','other']
	graph.visible = section=='mesh'
	rigging_panel.visible = section=='rig'
	native_sections.publish.visible = section=='mesh'
	for field in native_inspector_fields: field.visible = section=='mesh'
	for panel in native_other_panels: panel.visible = section=='other'
	texture.visible = section=='mesh' and preview_resource!=null
	mesh_container.visible = is_instance_valid(preview_scene)
	native_sections.title.text = {'mesh':'网格生成 · 右键画布添加节点，右键节点编辑、预览和管理结果。','rig':'骨骼绑定 · 使用已预览的网格，或选择本地网格；检查姿势后拟合。','other':'独立模块工具 · 每个模块使用自己的角色。','settings':'本机设置 · 内置工具已随引擎提供；真实生成需要配置模型服务。'}.get(section,'')
	for key in native_buttons: native_buttons[key].button_pressed = key==section
	native_scroll.scroll_vertical = 0

func save_settings():
	var c = ConfigFile.new()
	c.set_value("host", "python", python_edit.text)
	var bundled = get_meta('ainative_builtin',false) and host_edit.text==str(get_meta('ainative_tools_dir','')).path_join('editor_host.py')
	c.set_value('host','use_bundled_script',bundled)
	if not bundled: c.set_value("host", "script", host_edit.text)
	c.set_value("host", "factory", factory_edit.text)
	c.save(state_dir.path_join("local.cfg"))

func diagnostic_error(summary: String, raw_details) -> String:
	var path = state_dir.path_join('diagnostics.log')
	var output = FileAccess.open(path,FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
	if output==null: return summary+'；本机诊断日志无法写入。'
	output.seek_end()
	output.store_line(Time.get_datetime_string_from_system(true)+' '+summary+'\n'+str(raw_details))
	output.close()
	return summary+'；可在“本机设置”中打开诊断日志。'

func open_diagnostics():
	var path = state_dir.path_join('diagnostics.log')
	if FileAccess.file_exists(path): OS.shell_open(path)
	else: status.text = '暂无本机诊断日志。'

func add_node():
	var id = "n" + str(Time.get_ticks_usec())
	nodes.append({"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": "", "image_context": "", "text": "", "parameters": {"delay": 2, "fail": false}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45})
	rebuild()
	select_node(id)

func add_generator():
	var kind = generator_choice.get_item_metadata(generator_choice.selected)
	var id = "n" + str(Time.get_ticks_usec())
	nodes.append({"id": id, "type": kind, "version": "1", "provider": "comfy", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "白色背景上的小型石雕", "seed": 1}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45})
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
		node.title = data.id + " / " + node_label(data.get("type", "copy"))
		node.position_offset = Vector2(data.x, data.y)
		var label = Label.new()
		label.text = "本机离线复制" if data.get("type", "copy") == "copy" else node_label(data.type) + "（ComfyUI）"
		node.add_child(label)
		node.set_slot(0, not data.get("type", "copy").begins_with("text_"), 0, Color.SKY_BLUE, true, 0, Color.SKY_BLUE)
		graph.add_child(node)
		var run_button = button(node, "运行并预览", run_node_preview.bind(data.id))
		run_button.mouse_filter = Control.MOUSE_FILTER_PASS
		node.node_selected.connect(select_node.bind(data.id))
		node.position_offset_changed.connect(func(): data.x = node.position_offset.x; data.y = node.position_offset.y)
	for edge in edges:
		graph.connect_node(edge.from, 0, edge.to, 0)

func select_node(id: String):
	var changed = selected_id != id
	selected_id = id
	for data in nodes:
		if data.id == id:
			source_edit.text = data.source
			context_edit.text = data.image_context
			text_edit.text = data.text
			params_edit.text = JSON.stringify(data.parameters)
	refresh_history()
	if changed:
		clear_preview()
		if not preview_history.get(id, []).is_empty():
			show_history(preview_history[id].size() - 1)

func apply_fields() -> bool:
	var params = JSON.parse_string(params_edit.text)
	if not params is Dictionary or not safe(params):
		status.text = "参数无效，或含有禁止填写的凭据字段"
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
		status.text = "生成节点需要连接图像输出"
		return
	for edge in edges:
		if edge.to == to: return
	edges.append({"from": str(from), "to": str(to), "input": "source", "output": "result"})
	rebuild()

func disconnect_nodes(from: StringName, _fp: int, to: StringName, _tp: int):
	edges = edges.filter(func(e): return not (e.from == from and e.to == to))
	rebuild()

func delete_node():
	if creating or auto_step or not jobs.is_empty():
		status.text = "请等待当前运行结束或先取消，再删除节点"
		return
	preview_history.erase(selected_id)
	clear_preview()
	nodes = nodes.filter(func(n): return n.id != selected_id)
	edges = edges.filter(func(e): return e.from != selected_id and e.to != selected_id)
	selected_id = ""
	refresh_history()
	rebuild()

func model() -> Dictionary:
	return {"format": 1, "nodes": nodes, "edges": edges}

func save_graph():
	if not apply_fields(): return
	if path_edit.text.get_extension().to_lower() != "json":
		status.text = "工作流文件必须以 .json 结尾"
		return
	for n in nodes:
		if path_edit.text.simplify_path() in [n.source.simplify_path(), n.image_context.simplify_path()]:
			status.text = "不能覆盖输入资源"
			return
	var portable = model().duplicate(true)
	for n in portable.nodes:
		for field in ["source", "image_context"]:
			if not n[field].is_empty():
				var input = FileAccess.open(n[field], FileAccess.READ)
				if input == null:
					status.text = "无法建立输入快照，已保留原工作流"
					return
				var bytes = input.get_buffer(input.get_length())
				if bytes.is_empty() or input.get_error() != OK:
					status.text = "无法读取输入，已保留原工作流"
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
		status.text = "无法保存工作流"
		return
	f.store_string(JSON.stringify(portable, "\t"))
	f.flush()
	var failed = f.get_error() != OK
	f.close()
	if failed or DirAccess.rename_absolute(temporary, path_edit.text) != OK:
		DirAccess.remove_absolute(temporary)
		status.text = "无法替换工作流，已保留原工作流"
		return
	status.text = "已保存工作流及内嵌输入快照"

func clear_embedded():
	for data in nodes:
		if data.id == selected_id:
			data.erase("source_snapshot")
			data.erase("image_context_snapshot")
	status.text = "已清除内嵌源文件和参考图像，路径字段仍然有效"

func open_graph():
	_invalidate_context()
	if creating or auto_step or not jobs.is_empty():
		status.text = "请等待当前运行结束或先取消，再打开工作流"
		return
	var value = JSON.parse_string(FileAccess.get_file_as_string(path_edit.text))
	if not value is Dictionary or not safe(value) or value.get("format") != 1 or not value.get("nodes") is Array or not value.get("edges") is Array:
		status.text = "工作流无效"
		return
	var ids = []
	for n in value.nodes:
		if not n is Dictionary or not n.has_all(["id", "source", "image_context", "text", "parameters", "x", "y"]):
			status.text = "节点无效"
			return
		for key in ["id", "source", "image_context", "text"]:
			if not n[key] is String:
				status.text = "节点字段类型无效"
				return
		if n.id.is_empty() or not n.id.is_valid_identifier() or n.id in ids or not n.parameters is Dictionary or not (n.x is float or n.x is int) or not (n.y is float or n.y is int):
			status.text = "节点标识、参数或位置无效"
			return
		for key in ["type", "version", "provider"]:
			if n.has(key) and not n[key] is String:
				status.text = "节点定义字段无效"
				return
		ids.append(n.id)
	var destinations = []
	for e in value.edges:
		if not e is Dictionary or not e.has_all(["from", "to"]) or not e.from is String or not e.to is String:
			status.text = "连接无效"
			return
		if not e.from in ids or not e.to in ids or e.from == e.to or e.to in destinations:
			status.text = "连接端点无效"
			return
		destinations.append(e.to)
	preview_history.clear()
	run_id = ""
	current = {}
	preview_target = ""
	clear_preview()
	nodes = value.nodes
	edges = value.edges
	rebuild()
	if not nodes.is_empty(): select_node(nodes[0].id)
	status.text = "已重新打开工作流"

func run_node_preview(id: String):
	if creating or auto_step or not jobs.is_empty():
		status.text = "正在运行，请等待结果或先取消"
		return
	if id.is_empty() or nodes.filter(func(n): return n.id == id).is_empty(): return
	if not apply_fields(): return
	if selected_id != id: select_node(id)
	preview_target = id
	current = {}
	preview_token = ""
	auto_step = true
	creating = true
	cancel_create = false
	status.text = "正在运行选中节点及必要的上游节点…"
	launch("create", {"model": model(), "target": id})

func start_run():
	if creating or auto_step or not jobs.is_empty() or not apply_fields(): return
	preview_target = ""
	current = {}
	preview_token = ""
	auto_step = true
	creating = true
	cancel_create = false
	launch("create", {"model": model()})

func resume_run():
	if creating or run_id == "" or not jobs.is_empty(): return
	auto_step = true
	launch("step", {"run": run_id})

func cancel_run():
	if creating:
		cancel_create = true
		preview_target = ""
		auto_step = false
		return
	auto_step = false
	preview_target = ""
	preview_token = ""
	if run_id != "": launch("cancel", {"run": run_id})

func retry_node():
	if creating or auto_step or not jobs.is_empty(): return
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
		status.text = "无法启动本机 Python 服务"
		auto_step = false
		if command == "create":
			creating = false
			preview_target = ""
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
			status.text = "操作失败：" + {"create":"创建运行", "step":"执行节点", "cancel":"取消运行", "retry":"重试节点", "preview":"加载预览", "publish":"发布文件", "status":"查询状态"}.get(job.command,job.command) + "（源文件未改动）"
			auto_step = false
			if job.command == "create":
				creating = false
				preview_target = ""
			continue
		var data = result.result
		if job.command == "create":
			creating = false
			run_id = data.run_id
			var f = FileAccess.open(state_dir.path_join("last_run.txt"), FileAccess.WRITE)
			f.store_string(run_id)
			if cancel_create: launch("cancel", {"run": run_id})
		elif job.command == "preview":
			if job.spec.run == run_id:
				remember_preview(data, job.spec.node, job.spec.run)
				if job.spec.node == selected_id: load_preview(data, job.spec.node, job.spec.run)
		elif job.command == "publish":
			status.text = "已发布新文件：" + data.path
			if Engine.is_editor_hint(): EditorInterface.get_resource_filesystem().scan()
		else:
			current = data
			status.text = "运行状态：" + state_label(data.state) + " | 响应计数 " + str(heartbeat)
			for id in data.nodes:
				status.text += " | " + id + "：" + state_label(data.nodes[id].state) + "，尝试次数 " + str(data.nodes[id].attempt)
			if job.command == "retry": auto_step = true
			if data.state != "running": auto_step = false
			if not preview_target.is_empty() and data.nodes.has(preview_target) and data.nodes[preview_target].state == "succeeded":
				var finished_target = preview_target
				preview_target = ""
				auto_step = false
				launch("preview", {"run": run_id, "node": finished_target})
			if data.state == "reconcile": status.text += " | 提交结果未知，已暂停。点击“继续运行”查询一次结果，避免重复提交。"
	if auto_step and jobs.is_empty() and run_id != "": launch("step", {"run": run_id})

func request_preview():
	if creating:
		status.text = "正在创建运行，请稍候"
		return
	if run_id.is_empty() or selected_id.is_empty():
		status.text = "请先点击节点的“运行并预览”"
		return
	if jobs.values().any(func(job): return job.command == "preview"): return
	if not current.get("nodes", {}).has(selected_id) or current.nodes[selected_id].state != "succeeded":
		status.text = "选中节点尚未生成成功，请点击“运行并预览”"
		return
	launch("preview", {"run": run_id, "node": selected_id})

func refresh_history():
	if history_choice == null: return
	history_choice.clear()
	var history: Array = preview_history.get(selected_id, [])
	for i in history.size():
		history_choice.add_item("本次会话版本 " + str(i + 1) + ("（最新）" if i == history.size() - 1 else ""))
		history_choice.set_item_tooltip(i, history[i].get("description", ""))
	history_choice.disabled = history.is_empty()
	if history.is_empty(): history_choice.add_item("暂无预览版本")
	else: history_choice.select(history.size() - 1)

func remember_preview(data: Dictionary, node_id: String, result_run: String):
	var history: Array = preview_history.get(node_id, [])
	if not history.any(func(entry): return entry.token == data.token):
		var entry = data.duplicate(true)
		entry["run"] = result_run
		entry["node"] = node_id
		entry["description"] = JSON.stringify(current.get("nodes", {}).get(node_id, {}).get("request", {}), "  ")
		history.append(entry)
		preview_history[node_id] = history
	if node_id == selected_id: refresh_history()

func show_history(index: int):
	var history: Array = preview_history.get(selected_id, [])
	if index < 0 or index >= history.size(): return
	var entry: Dictionary = history[index]
	load_preview(entry, selected_id, entry.run)
	history_choice.select(index)
	status.text += " · 版本 " + str(index + 1)

func clear_preview():
	preview_token = ""
	preview_run = ""
	preview_node = ""
	preview_resource = null
	if is_instance_valid(preview_scene): preview_scene.queue_free()
	preview_scene = null
	texture.texture = null
	texture.hide()
	mesh_container.hide()

func load_preview(data: Dictionary, node_id: String, result_run: String = ""):
	clear_preview()
	if data.type == "image":
		var image = Image.load_from_file(data.path)
		if image == null: status.text = "图像预览失败"; return
		preview_resource = ImageTexture.create_from_image(image)
		texture.texture = preview_resource
		texture.show()
	else:
		var document = GLTFDocument.new()
		var state = GLTFState.new()
		if document.append_from_file(data.path, state) != OK: status.text = "网格预览失败"; return
		preview_scene = preload('res://addons/ainative/runtime_mesh.gd').generate(document,state)
		if preview_scene == null: return
		preview_root.add_child(preview_scene)
		rigging_panel.set_source(data.path)
		mesh_container.show()
		frame_mesh()
	preview_token = data.token
	preview_run = run_id if result_run.is_empty() else result_run
	preview_node = node_id
	status.text = "已加载" + {"image":"图像", "mesh":"网格"}.get(data.type,data.type) + "预览，请检查后再发布"

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
		status.text = "请先预览本次运行成功的结果"
		return
	var extension = ".tres" if preview_resource != null else ".tscn"
	if target_edit.text.get_extension() != extension.substr(1): status.text = "目标文件必须以此扩展名结尾：" + extension; return
	staged = state_dir.path_join("staged-" + str(Time.get_ticks_usec()) + extension)
	var err
	if preview_resource != null: err = ResourceSaver.save(preview_resource, staged)
	else:
		var packed = PackedScene.new()
		set_owners(preview_scene, preview_scene)
		err = packed.pack(preview_scene)
		if err == OK: err = ResourceSaver.save(packed, staged)
	if err != OK: status.text = "资源编码失败"; return
	confirmation = {"run": preview_run, "node": preview_node, "confirmation": preview_token, "staged": staged, "staged_sha256": FileAccess.get_sha256(staged), "target": target_edit.text}
	dialog.dialog_text = "将当前预览发布为新文件？\n运行编号：" + preview_run + "\n预览版本：" + preview_token + "\n资源 SHA256：" + confirmation.staged_sha256 + "\n" + target_edit.text
	dialog.popup_centered()

func confirm_publish():
	if confirmation.get("run") != run_id or confirmation.get("confirmation") != preview_token:
		status.text = "预览已变化，请重新确认"
		return
	launch("publish", confirmation.duplicate())
	confirmation = {}

func _exit_tree():
	for pid in jobs:
		if OS.is_process_running(pid): OS.kill(pid)

func is_graph_busy() -> bool:
	return creating or auto_step or not jobs.is_empty()

func _setup_context_controls():
	context_menu = PopupMenu.new()
	context_menu.name = "GraphContextMenu"
	context_menu.allow_search = true
	context_menu.id_pressed.connect(_context_action)
	add_child(context_menu)
	context_history_menu = PopupMenu.new()
	context_history_menu.name = "ContextHistory"
	context_history_menu.id_pressed.connect(_history_context_action)
	context_menu.add_child(context_history_menu)
	node_picker = ConfirmationDialog.new()
	node_picker.title = "添加节点"
	node_picker.ok_button_text = "添加"
	node_picker.cancel_button_text = "取消"
	node_picker.min_size = Vector2i(420, 320)
	var fields = VBoxContainer.new()
	node_picker.add_child(fields)
	node_picker_search = line(fields, "搜索节点类型，如：图像、网格、离线")
	node_picker_search.text_changed.connect(filter_node_picker)
	node_picker_search.text_submitted.connect(func(_text): _node_picker_confirmed())
	node_picker_list = ItemList.new()
	node_picker_list.custom_minimum_size = Vector2(400, 240)
	node_picker_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	node_picker_list.item_activated.connect(func(_index): _node_picker_confirmed())
	fields.add_child(node_picker_list)
	node_picker.confirmed.connect(_node_picker_confirmed)
	add_child(node_picker)

func _graph_selected_ids() -> Array:
	var ids: Array = []
	for child in graph.get_children():
		if child is GraphNode and child.selected: ids.append(str(child.name))
	return ids

func _node_at_context(point: Vector2) -> String:
	var global_point = graph.get_global_transform() * point
	var children = graph.get_children()
	children.reverse()
	for child in children:
		if child is GraphNode and child.visible:
			var local_point = child.get_global_transform().affine_inverse() * global_point
			if Rect2(Vector2.ZERO, child.size).has_point(local_point): return str(child.name)
	return ""

func _remember_context():
	context_model = JSON.stringify(model())
	context_run = run_id
	context_selection = _graph_selected_ids()
	context_inspected_id = selected_id

func _context_is_current() -> bool:
	if context_model.is_empty() or context_model != JSON.stringify(model()) or context_run != run_id or context_inspected_id != selected_id or context_selection != _graph_selected_ids():
		status.text = "编辑内容或运行已变化，请重新打开右键菜单"
		return false
	for id in context_node_ids:
		if nodes.filter(func(n): return n.id == id).is_empty():
			status.text = "节点已不存在，请重新打开右键菜单"
			return false
	return true

func _invalidate_context():
	context_model = ""
	context_node_ids.clear()
	context_connection.clear()
	if is_instance_valid(context_menu): context_menu.hide()
	if is_instance_valid(node_picker): node_picker.hide()

func _context_item(label: String, action: int, reason: String = ""):
	context_menu.add_item(label, action)
	var index = context_menu.item_count - 1
	context_menu.set_item_disabled(index, not reason.is_empty())
	if not reason.is_empty(): context_menu.set_item_tooltip(index, reason)

func node_run_blocker(id: String) -> String:
	if is_graph_busy(): return "正在运行，请等待结果或先取消"
	var pending: Array = [id]
	var visited: Array = []
	while not pending.is_empty():
		var next_id = pending.pop_back()
		if next_id in visited: continue
		visited.append(next_id)
		var matching = nodes.filter(func(n): return n.id == next_id)
		if matching.is_empty(): return "缺少必要的上游节点"
		var data: Dictionary = matching[0]
		var kind: String = data.get("type", "copy")
		var incoming = edges.filter(func(edge): return edge.to == next_id)
		for edge in incoming: pending.append(edge.from)
		if not kind.begins_with("text_") and incoming.is_empty():
			if data.get("source", "").is_empty() and not data.has("source_snapshot"):
				return "请先设置源文件或连接上游节点（" + str(next_id) + "）"
			if not data.get("source", "").is_empty() and not FileAccess.file_exists(data.source):
				return "源文件不存在（" + str(next_id) + "）"
		var prompt = str(data.get("parameters", {}).get("prompt", "")) + "\n" + str(data.get("text", ""))
		if not kind in ["copy", "image_to_mesh"] and prompt.strip_edges().is_empty():
			return "请先填写生成提示词（" + str(next_id) + "）"
		if not data.get("image_context", "").is_empty() and not FileAccess.file_exists(data.image_context):
			return "参考图像不存在（" + str(next_id) + "）"
	return ""

func _retry_blocker(id: String) -> String:
	if is_graph_busy(): return "正在运行，请等待结束或先取消"
	var state: Dictionary = current.get("nodes", {}).get(id, {})
	var job = state.get("job")
	if run_id.is_empty() or state.get("state") != "failed" or not job is Dictionary or job.get("state") != "failed":
		return "仅可重试原运行中已确认失败的节点"
	return ""

func show_context_menu(local_position: Vector2):
	if not graph.is_visible_in_tree(): return
	# Persist the previous inspector before selecting a different context target.
	if not selected_id.is_empty() and not apply_fields(): return
	context_position = local_position
	context_node_ids = []
	context_connection = {}
	var hit = _node_at_context(local_position)
	if not hit.is_empty():
		var selected = _graph_selected_ids()
		if not hit in selected:
			for child in graph.get_children():
				if child is GraphNode: child.selected = str(child.name) == hit
			selected = [hit]
		select_node(hit)
		context_node_ids = selected
	else:
		context_connection = graph.get_closest_connection_at_point(local_position, 8.0)
	_remember_context()
	context_menu.clear()
	context_history_menu.clear()
	var busy_reason = "请等待当前运行结束或先取消" if is_graph_busy() else ""
	if context_node_ids.size() == 1:
		var id: String = context_node_ids[0]
		_context_item("运行并预览", CONTEXT_RUN, node_run_blocker(id))
		var has_result = not preview_history.get(id, []).is_empty() or current.get("nodes", {}).get(id, {}).get("state") == "succeeded"
		_context_item("查看已有结果", CONTEXT_PREVIEW, "该节点尚无成功结果" if not has_result else "")
		var history: Array = preview_history.get(id, [])
		for i in history.size():
			context_history_menu.add_item("版本 " + str(i + 1) + ("（最新）" if i == history.size() - 1 else ""), i)
			context_history_menu.set_item_tooltip(i, history[i].get("description", ""))
		context_menu.add_submenu_item("预览历史", "ContextHistory", CONTEXT_HISTORY)
		context_menu.set_item_disabled(context_menu.item_count - 1, history.is_empty())
		if history.is_empty(): context_menu.set_item_tooltip(context_menu.item_count - 1, "本次会话暂无该节点的预览版本")
		_context_item("编辑提示词与参数", CONTEXT_EDIT)
		_context_item("重试节点", CONTEXT_RETRY, _retry_blocker(id))
		context_menu.add_separator()
		_context_item("复制节点", CONTEXT_DUPLICATE, busy_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_MASK_CMD_OR_CTRL | KEY_D)
		_context_item("删除节点", CONTEXT_DELETE, busy_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
	elif context_node_ids.size() > 1:
		context_menu.add_separator("已选择 " + str(context_node_ids.size()) + " 个节点")
		_context_item("复制选中节点", CONTEXT_DUPLICATE, busy_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_MASK_CMD_OR_CTRL | KEY_D)
		_context_item("删除选中节点", CONTEXT_DELETE, busy_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
	elif not context_connection.is_empty():
		_context_item("断开连接", CONTEXT_DISCONNECT, busy_reason)
	else:
		_context_item("添加节点…", CONTEXT_ADD, busy_reason)
		context_menu.add_separator()
		_context_item("保存工作流…", CONTEXT_SAVE)
		_context_item("打开工作流…", CONTEXT_OPEN, busy_reason)
		_context_item("运行整个工作流", CONTEXT_RUN_ALL, busy_reason if not busy_reason.is_empty() else ("请先添加节点" if nodes.is_empty() else ""))
	context_menu.popup(Rect2i(Vector2i(graph.get_screen_transform() * local_position), Vector2i.ZERO))

func _context_action(action: int):
	if not _context_is_current(): return
	context_menu.hide()
	match action:
		CONTEXT_ADD:
			if is_graph_busy(): return
			node_picker_search.text = ""
			filter_node_picker("")
			node_picker.popup_centered()
			node_picker_search.grab_focus()
		CONTEXT_RUN:
			if context_node_ids.size() == 1:
				var reason = node_run_blocker(context_node_ids[0])
				if not reason.is_empty(): status.text = reason; return
				run_node_preview(context_node_ids[0])
		CONTEXT_PREVIEW:
			if context_node_ids.size() == 1:
				var id: String = context_node_ids[0]
				if not creating and current.get("nodes", {}).get(id, {}).get("state") == "succeeded": request_preview()
				elif not preview_history.get(id, []).is_empty(): show_history(preview_history[id].size() - 1)
		CONTEXT_HISTORY:
			if context_node_ids.size() == 1 and not preview_history.get(context_node_ids[0], []).is_empty():
				history_choice.grab_focus()
				status.text = "在预览历史子菜单或右侧版本列表选择结果"
		CONTEXT_EDIT:
			if context_node_ids.size() == 1:
				text_edit.grab_focus()
				status.text = "在右侧编辑提示词与参数，完成后右键选择“运行并预览”"
		CONTEXT_RETRY:
			if context_node_ids.size() == 1:
				var reason = _retry_blocker(context_node_ids[0])
				if not reason.is_empty(): status.text = reason; return
				preview_target = context_node_ids[0]
				retry_node()
		CONTEXT_DUPLICATE: duplicate_context_nodes()
		CONTEXT_DELETE: delete_context_nodes()
		CONTEXT_DISCONNECT:
			if is_graph_busy() or context_connection.is_empty(): return
			disconnect_nodes(context_connection.from_node, context_connection.from_port, context_connection.to_node, context_connection.to_port)
		CONTEXT_SAVE, CONTEXT_OPEN: _workflow_action(action)
		CONTEXT_RUN_ALL:
			if not is_graph_busy(): start_run()

func _history_context_action(index: int):
	if _context_is_current() and context_node_ids.size() == 1:
		show_history(index)

func filter_node_picker(text: String):
	node_picker_list.clear()
	var search = text.strip_edges().to_lower()
	for group in [["图像生成", ["text_to_image", "image_to_image"]], ["网格生成", ["image_to_mesh", "text_to_mesh"]], ["离线工具", ["copy"]]]:
		var matches: Array = []
		for kind in group[1]:
			if search.is_empty() or search in (node_label(kind) + " " + kind + " " + group[0]).to_lower(): matches.append(kind)
		if matches.is_empty(): continue
		node_picker_list.add_item(group[0])
		node_picker_list.set_item_selectable(node_picker_list.item_count - 1, false)
		for kind in matches:
			node_picker_list.add_item("  " + node_label(kind))
			node_picker_list.set_item_metadata(node_picker_list.item_count - 1, kind)
	for i in node_picker_list.item_count:
		if node_picker_list.is_item_selectable(i):
			node_picker_list.select(i)
			break
	node_picker.get_ok_button().disabled = node_picker_list.get_selected_items().is_empty()

func _node_picker_confirmed():
	var selected = node_picker_list.get_selected_items()
	if selected.is_empty(): return
	create_context_node(str(node_picker_list.get_item_metadata(selected[0])))

func create_context_node(kind: String):
	if not kind in NODE_KINDS or is_graph_busy() or not _context_is_current(): return
	if not selected_id.is_empty() and not apply_fields(): return
	var position = (context_position + graph.scroll_offset) / graph.zoom
	var id = "n" + str(Time.get_ticks_usec())
	while not nodes.filter(func(n): return n.id == id).is_empty(): id += "x"
	var data = {"id": id, "type": kind, "version": "1", "provider": "local-copy" if kind == "copy" else "comfy", "source": "", "image_context": "", "text": "", "parameters": {"delay": 2, "fail": false} if kind == "copy" else {"prompt": "白色背景上的小型石雕", "seed": 1}, "x": position.x, "y": position.y}
	nodes.append(data)
	node_picker.hide()
	context_menu.hide()
	rebuild()
	for child in graph.get_children():
		if child is GraphNode: child.selected = str(child.name) == id
	select_node(id)
	status.text = "已在右键位置添加“" + node_label(kind) + "”节点"

func duplicate_context_nodes() -> Array:
	if is_graph_busy() or not _context_is_current() or context_node_ids.is_empty(): return []
	if not apply_fields(): return []
	var mapping: Dictionary = {}
	var copies: Array = []
	for id in context_node_ids:
		var matching = nodes.filter(func(n): return n.id == id)
		if matching.is_empty(): return []
		var copy: Dictionary = matching[0].duplicate(true)
		var new_id = "n" + str(Time.get_ticks_usec())
		while mapping.values().has(new_id) or not nodes.filter(func(n): return n.id == new_id).is_empty(): new_id += "x"
		mapping[id] = new_id
		copy.id = new_id
		copy.x += 40
		copy.y += 40
		copies.append(copy)
	var copied_edges: Array = []
	for edge in edges:
		if mapping.has(edge.from) and mapping.has(edge.to):
			var copy = edge.duplicate(true)
			copy.from = mapping[edge.from]
			copy.to = mapping[edge.to]
			copied_edges.append(copy)
	nodes.append_array(copies)
	edges.append_array(copied_edges)
	rebuild()
	for child in graph.get_children():
		if child is GraphNode: child.selected = mapping.values().has(str(child.name))
	select_node(copies[-1].id)
	status.text = "已复制 " + str(copies.size()) + " 个节点及其内部连接"
	return mapping.values()

func delete_context_nodes():
	if is_graph_busy() or not _context_is_current() or context_node_ids.is_empty(): return
	var removed = context_node_ids.duplicate()
	for id in removed: preview_history.erase(id)
	if preview_node in removed: clear_preview()
	nodes = nodes.filter(func(n): return not n.id in removed)
	edges = edges.filter(func(edge): return not edge.from in removed and not edge.to in removed)
	if selected_id in removed:
		selected_id = ""
		source_edit.text = ""
		context_edit.text = ""
		text_edit.text = ""
		params_edit.text = "{}"
		refresh_history()
	rebuild()
	status.text = "已删除 " + str(removed.size()) + " 个节点及关联连接"

func _keyboard_duplicate():
	context_node_ids = _graph_selected_ids()
	context_connection = {}
	_remember_context()
	duplicate_context_nodes()

func _keyboard_delete(ids: Array):
	context_node_ids = []
	for id in ids: context_node_ids.append(str(id))
	context_connection = {}
	_remember_context()
	delete_context_nodes()

func _graph_context_input(event: InputEvent):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and event.ctrl_pressed and OS.get_name() == "macOS":
		# Cocoa already maps real Control-click to RIGHT. This is the synthetic-input fallback.
		show_context_menu(event.position)
		graph.accept_event()
	elif event is InputEventKey and event.pressed and not event.echo and (event.keycode == KEY_MENU or (event.keycode == KEY_F10 and event.shift_pressed)):
		var position = graph.size * 0.5
		var ids = _graph_selected_ids()
		if not ids.is_empty():
			var node = graph.get_node_or_null(NodePath(ids[0])) as GraphNode
			if node != null: position = graph.get_global_transform().affine_inverse() * (node.get_global_transform() * (node.size * 0.5))
		show_context_menu(position)
		graph.accept_event()

func _workflow_action(action: int):
	if action == CONTEXT_OPEN and is_graph_busy():
		status.text = "请等待运行结束或先取消，再打开工作流"
		return
	workflow_mode = "save" if action == CONTEXT_SAVE else "open"
	workflow_dialog.title = "保存工作流" if workflow_mode == "save" else "打开工作流"
	workflow_dialog.ok_button_text = "保存" if workflow_mode == "save" else "打开"
	workflow_dialog.popup_centered()
	path_edit.grab_focus()

func _workflow_confirmed():
	if workflow_mode == "save": save_graph()
	elif workflow_mode == "open": open_graph()
