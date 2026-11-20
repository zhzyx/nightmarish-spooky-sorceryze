@tool
extends VBoxContainer
# Local machine settings are intentionally excluded from workflow serialization.
signal settings_requested(section: String)
var rigging_panel: VBoxContainer
var generator_choice: OptionButton
var graph: GraphEdit
var status: Label
var path_edit: LineEdit
var source_edit: LineEdit
var context_edit: LineEdit
var source_picker: FileDialog
var context_picker: FileDialog
var source_browse: Button
var context_browse: Button
var source_clear: Button
var context_clear: Button
var text_edit: TextEdit
var params_edit: TextEdit
var parameter_form: VBoxContainer
var developer_mode: CheckButton
var python_edit: LineEdit
var host_edit: LineEdit
var factory_edit: LineEdit
var target_edit: LineEdit
var texture: TextureRect
var viewport: SubViewport
var mesh_container: SubViewportContainer
var preview_maximize_button: Button
var preview_restore_button: Button
var preview_window: Window
var preview_window_host: VBoxContainer
var preview_maximized := false
var preview_inline_parent: Control
var preview_inline_index := -1
var preview_inline_minimum_size := Vector2.ZERO
var preview_inline_size_flags_horizontal := Control.SIZE_FILL
var preview_inline_size_flags_vertical := Control.SIZE_FILL
var mesh_focus := Vector3.ZERO
var mesh_frame_distance := 1.0
var preview_root: Node3D
var dialog: ConfirmationDialog
var capability_notice_dialog: AcceptDialog
var capability_notices: Dictionary = {}
var failure_dialog: AcceptDialog
var failure_text: TextEdit
var failure_copy_button: Button
var failure_copy_hint: Label
var failure_notices: Dictionary = {}
var nodes: Array = []
var edges: Array = []
var selected_id = ""
const WorkbenchController = preload("res://addons/ainative/workbench_controller.gd")
var controller = WorkbenchController.new()
# Preserve the workbench's existing scripting API while the controller owns state.
var run_id: String:
	get: return controller.run_id
	set(value): controller.run_id = value
var current: Dictionary:
	get: return controller.current
	set(value): controller.current = value
var jobs: Dictionary:
	get: return controller.jobs
var serial: int:
	get: return controller.serial
var heartbeat: int:
	get: return controller.heartbeat
var auto_step: bool:
	get: return controller.auto_step
	set(value): controller.auto_step = value
var creating: bool:
	get: return controller.creating
	set(value): controller.creating = value
var cancel_create: bool:
	get: return controller.cancel_create
	set(value): controller.cancel_create = value
var preview_target: String:
	get: return controller.preview_target
	set(value): controller.preview_target = value
var preview_history: Dictionary = {}
# Image artifacts are presentation-only graph nodes; they never enter the execution DAG.
var artifact_nodes: Dictionary = {}
var dismissed_artifacts: Dictionary = {}
var artifact_preview_queue: Array = []
var artifact_download_picker: FileDialog
var artifact_download_source = ""
var artifact_layout_pending = false
var context_artifact_source = ""
var history_choice: OptionButton
var result_choice: OptionButton
var current_images: Array = []
var preview_artifact: Dictionary = {}
var preview_token = ""
var preview_run = ""
var preview_node = ""
var preview_source_path = ""
var save_picker: FileDialog
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
var settings_sections: Dictionary = {}
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
var workflow_dialog: FileDialog
var workflow_path_display: LineEdit
var workflow_mode = ""
var inspector_fields: VBoxContainer
var node_model_label: Label
var node_model_choice: OptionButton
var node_model_edit: LineEdit
var node_image_model_label: Label
var node_image_model_choice: OptionButton
var node_image_model_edit: LineEdit
var service_choice: OptionButton
var endpoint_edit: LineEdit
var kimi_model_edit: LineEdit
var kimi_model_label: Label
var kimi_auth_label: Label
var kimi_model3d_fields: VBoxContainer
var model3d_tool_edit: LineEdit
var model3d_pythonw_edit: LineEdit
var kimi_image_fields: VBoxContainer
var kimi_image_tool_edit: LineEdit
var kimi_image_pythonw_edit: LineEdit
var image_model_choice: OptionButton
var mesh_model_choice: OptionButton
var image_model_label: Label
var mesh_model_label: Label
var cli_billing: Label
var service_status: Label
var service_capability_labels: Dictionary = {}
var service_config_path = ""
var service_profiles_path = ""
var service_profiles: Dictionary = {}
var service_profile_mode = "comfy"
var service_control_defaults: Dictionary = {}
var cli_path_edit: LineEdit
var cli_fields: VBoxContainer
var blender_fields: VBoxContainer
var blender_path_edit: LineEdit
var managed_comfy_panel: VBoxContainer
const ManagedComfyPanel = preload('res://addons/ainative/managed_comfy_panel.gd')
var bundled_runtime: Dictionary = {}
var service_guide: Label
var service_saved: Dictionary = {}
var service_report: Dictionary = {}
var service_report_draft = ""
var service_config_link: Button
var service_settings_section = 'ai'
var service_fields: VBoxContainer
var service_advanced: VBoxContainer
var service_ui_loading = false
const SERVICE_PROFILE_MODES = ["comfy", "codex", "kimi_native", "local_mesh", "api_modeling", "api_sculpt"]
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
const CONTEXT_ARTIFACT_DOWNLOAD = 13
const CONTEXT_ARTIFACT_DELETE = 14
const RETIRED_GPT_MESH_PROVIDERS = ["codex-modeling", "codex-sculpt"]
const RETIRED_GPT_MESH_MODES = ["codex_modeling", "codex_sculpt"]
const RETIRED_GPT_MESH_NOTICE = "GPT CLI 单独网格生成已下线。请使用当前网格服务新建节点，再连接源文件与下游节点。"
const GENERATE_IMAGE = "generate_image"
const IMAGE_KINDS = [GENERATE_IMAGE, "text_to_image", "image_to_image"]
const NODE_KINDS = [GENERATE_IMAGE, "text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh", "model_adjust", "copy"]
const CREATION_NODE_KINDS = [GENERATE_IMAGE, "image_to_mesh", "text_to_mesh", "model_adjust", "copy"]
const PORT_DYNAMIC = 0
const PORT_IMAGE = 1
const PORT_MESH = 2
const PORT_TEXT = 3
const PORT_IMAGE_SET = 4
const PORT_COLORS = {
	PORT_DYNAMIC: Color(0.65, 0.68, 0.75),
	PORT_IMAGE: Color.SKY_BLUE,
	PORT_MESH: Color.PALE_GREEN,
	PORT_TEXT: Color(0.85, 0.65, 1.0),
	PORT_IMAGE_SET: Color(0.4, 0.85, 0.85),
}

func node_label(kind: String) -> String:
	return {"copy":"离线复制", GENERATE_IMAGE:"生成图片", "text_to_image":"文字生成图像", "image_to_image":"图像生成图像", "image_to_mesh":"图像生成网格", "text_to_mesh":"文字生成网格", "model_adjust":"模型调整"}.get(kind,kind)

func _is_mesh_kind(kind: String) -> bool:
	return kind in ["text_to_mesh", "image_to_mesh", "model_adjust"]

func _is_image_kind(kind: String) -> bool:
	return kind in IMAGE_KINDS

func _new_node_version(kind: String) -> String:
	if kind == GENERATE_IMAGE: return "2"
	if kind == "image_to_mesh": return "2"
	if kind == "model_adjust": return "2"
	return "4" if kind in ["text_to_image", "image_to_image"] else "1"

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

func _make_file_picker(picker_name: String, title_text: String) -> FileDialog:
	var picker = FileDialog.new()
	picker.name = picker_name
	picker.title = title_text
	picker.ok_button_text = "打开"
	picker.cancel_button_text = "取消"
	picker.access = FileDialog.ACCESS_FILESYSTEM
	picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	picker.use_native_dialog = true
	add_child(picker)
	return picker

func _show_file_picker(picker: FileDialog, selected_path: String):
	var first = selected_path.split(" ; ")[0]
	if not first.is_empty(): picker.current_path = first
	picker.popup_centered_ratio(0.7)

func _configure_source_picker(kind: String, data: Dictionary = {}):
	var copy = kind == "copy"
	var adjust = kind == "model_adjust"
	var multiple = _is_image_kind(kind) or _accepts_image_set(data)
	source_picker.title = "选择已生成模型（GLB / 内嵌 glTF）" if adjust else "选择源图像或模型" if copy else "选择源图像（可多选）"
	source_picker.filters = PackedStringArray(["*.glb,*.gltf ; GLB / 内嵌 glTF 模型" if adjust else "*.png,*.jpg,*.jpeg,*.glb,*.gltf ; 图像 / 网格" if copy else "*.png,*.jpg,*.jpeg ; PNG / JPEG 图像"])
	source_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILES if multiple else FileDialog.FILE_MODE_OPEN_FILE
	context_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILES if multiple or adjust else FileDialog.FILE_MODE_OPEN_FILE
	source_browse.text = "选择模型…" if adjust else "选择文件…" if copy else "选择图片…"
	source_edit.placeholder_text = "必须选择已生成模型" if adjust else "未选择源图像或模型" if copy else "未选择源图像，可多选；也可仅填写文本" if kind == GENERATE_IMAGE else "未选择源图像，可多选"
	context_edit.placeholder_text = "微调参考图（可选，单图或四视角）" if adjust else "未选择参考图像（可选）"

func _node_paths(data: Dictionary, field: String) -> Array:
	var paths: Array = data.get(field + "_paths", []).duplicate()
	if paths.is_empty() and not str(data.get(field, "")).is_empty(): paths.append(str(data[field]))
	if paths.is_empty() and not data.get(field + "_snapshots", []).is_empty():
		for _item in data[field + "_snapshots"]: paths.append("")
	return paths

func _sync_node_files(data: Dictionary):
	for field in ["source", "image_context"]:
		var paths = _node_paths(data, field)
		data[field + "_paths"] = paths
		data[field] = str(paths[0]) if not paths.is_empty() else ""

func _set_node_file(field: String, selection):
	if not field in ["source", "image_context"] or selected_id.is_empty(): return
	if not (selection is String or selection is PackedStringArray or selection is Array): return
	var paths: Array = [selection] if selection is String else Array(selection)
	paths = paths.filter(func(path): return path is String and not path.is_empty())
	for data in nodes:
		if data.id != selected_id: continue
		var other = "image_context" if field == "source" else "source"
		var image_node = _is_image_kind(str(data.get("type", "copy"))) or _accepts_image_set(data)
		var reviewed_mesh = data.get("type", "") == "image_to_mesh" and data.get("version", "1") == "2"
		var total = paths.size() + _node_paths(data, other).size()
		if not reviewed_mesh and (paths.size() > 8 or (image_node and total > 8)):
			status.text = "源图与参考图合计每次最多 8 张"
			return
		data[field + "_paths"] = paths
		data[field + "_snapshots"] = []
		data[field] = ""
		data.erase(field + "_snapshot")
		_sync_node_files(data)
		var edit = source_edit if field == "source" else context_edit
		edit.text = " ; ".join(_node_paths(data, field))
		edit.tooltip_text = edit.text if not edit.text.is_empty() else "通过系统资源管理器选择文件，可多选"
		var label = "源文件" if field == "source" else "参考图像"
		status.text = ("已清除" + label) if paths.is_empty() else ("已选择 %d 个%s" % [paths.size(), label])
		return

func _ready():
	controller.command_completed.connect(_controller_completed)
	controller.command_failed.connect(_controller_failed)
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
			if item[0] != 'settings':
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
	state_dir = state_dir.replace('\\', '/')
	DirAccess.make_dir_recursive_absolute(state_dir)
	db = state_dir.path_join("executor.sqlite")
	var settings = ConfigFile.new()
	settings.load(state_dir.path_join("local.cfg"))
	if builtin: bundled_runtime = ManagedComfyPanel.discover_bundle()
	var machine = VBoxContainer.new()
	machine.name = 'AINativeLocalSettings'
	content.add_child(machine)
	var default_python = _default_python_path(builtin)
	var bundled_host = str(get_meta('ainative_tools_dir','')).path_join('editor_host.py') if builtin else ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	var configured_host = bundled_host if builtin and settings.get_value('host','use_bundled_script',true) else settings.get_value('host','script',bundled_host)
	_setup_service_controls(machine, settings)
	service_fields.name = 'AINativeAISettings'
	var environment_settings = VBoxContainer.new()
	environment_settings.name = 'AINativeEnvironmentSettings'
	machine.add_child(environment_settings)
	settings_sections = {'ai':service_fields, 'environment':environment_settings}
	var environment_title = Label.new()
	environment_title.text = '马良运行环境'
	environment_settings.add_child(environment_title)
	cli_fields.reparent(environment_settings)
	service_advanced = VBoxContainer.new()
	environment_settings.add_child(service_advanced)
	if not builtin:
		service_advanced.hide()
		var advanced_button = button(environment_settings, "高级运行环境与旧配置", func(): service_advanced.visible = not service_advanced.visible)
		environment_settings.move_child(advanced_button, service_advanced.get_index())
	var runtime_label = Label.new()
	runtime_label.text = '马良工具与本机模型 Python（3.11+，独立于引擎编译 Python）'
	runtime_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service_advanced.add_child(runtime_label)
	var configured_python = bundled_runtime.get('python', '') if settings.get_value('host', 'use_bundled_python', false) else settings.get_value('host', 'python', default_python)
	python_edit = line(service_advanced, "马良 Python 可执行文件（3.11+）", OS.get_environment("AINATIVE_PYTHON") if OS.has_environment("AINATIVE_PYTHON") else configured_python)
	host_edit = line(service_advanced, "本机 editor_host.py 路径", configured_host)
	factory_edit = line(service_advanced, "旧生成服务入口（兼容已有配置）", OS.get_environment("AINATIVE_PROVIDER_FACTORY") if OS.has_environment("AINATIVE_PROVIDER_FACTORY") else settings.get_value("host", "factory", "editor_demo:factory"))
	button(service_advanced, "保存高级运行环境", save_settings)
	button(environment_settings, "打开本机诊断日志", open_diagnostics)
	_restore_service_settings(settings)
	managed_comfy_panel = ManagedComfyPanel.new()
	environment_settings.add_child(managed_comfy_panel)
	managed_comfy_panel.initialize(self, settings)
	_update_service_summary()
	factory_edit.text_changed.connect(_legacy_factory_changed)
	developer_mode = CheckButton.new()
	developer_mode.text = "开发者模式"
	developer_mode.button_pressed = settings.get_value("interface", "developer_mode", false)
	environment_settings.add_child(developer_mode)
	developer_mode.toggled.connect(func(enabled):
		if parameter_form != null: parameter_form.set_developer_mode(enabled)
	)
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
	workflow_dialog = FileDialog.new()
	workflow_dialog.title = "工作流文件"
	workflow_dialog.cancel_button_text = "取消"
	workflow_dialog.access = FileDialog.ACCESS_FILESYSTEM
	workflow_dialog.use_native_dialog = true
	workflow_dialog.filters = PackedStringArray(["*.json ; 马良工作流"])
	workflow_dialog.file_selected.connect(_workflow_confirmed)
	add_child(workflow_dialog)
	# Keep the scripted path API, while the visible UI uses a real file picker.
	path_edit = LineEdit.new()
	path_edit.name = "WorkflowPathState"
	path_edit.text = str(settings.get_value("workflow", "last_path", ProjectSettings.globalize_path("user://workflow.json")))
	path_edit.hide()
	add_child(path_edit)
	workflow_path_display = LineEdit.new()
	workflow_path_display.name = "CurrentWorkflowPath"
	workflow_path_display.placeholder_text = "当前工作流路径；粘贴后按回车打开"
	workflow_path_display.custom_minimum_size.x = 320
	workflow_path_display.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	workflow_path_display.text_submitted.connect(_open_workflow_path)
	bar.add_child(workflow_path_display)
	bar.move_child(workflow_path_display, 1)
	_update_workflow_path_display()
	# Retained for saved automation and callers; node creation is now in the canvas menu.
	generator_choice = OptionButton.new()
	for kind in CREATION_NODE_KINDS:
		if kind == "copy": continue
		generator_choice.add_item(node_label(kind))
		generator_choice.set_item_metadata(generator_choice.item_count - 1, kind)
	if builtin: generator_choice.selected = 1
	add_child(generator_choice)
	generator_choice.hide()
	var split = HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(split)
	graph = GraphEdit.new()
	# Let users drag an ordered image list onto the combined image/list input.
	graph.add_valid_connection_type(PORT_IMAGE_SET, PORT_IMAGE)
	# Dynamic artifact ports are presentation adapters, not executable node types.
	graph.add_valid_connection_type(PORT_IMAGE, PORT_DYNAMIC)
	graph.add_valid_connection_type(PORT_IMAGE_SET, PORT_DYNAMIC)
	graph.add_valid_connection_type(PORT_DYNAMIC, PORT_IMAGE)
	graph.add_valid_connection_type(PORT_MESH, PORT_DYNAMIC)
	graph.add_valid_connection_type(PORT_DYNAMIC, PORT_MESH)
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
	var source_row = HBoxContainer.new()
	source_row.name = "SourceFileField"
	inspector.add_child(source_row)
	source_edit = line(source_row, "未选择源图像或模型")
	source_edit.editable = false
	source_edit.tooltip_text = "通过系统资源管理器选择源图像或模型"
	source_browse = button(source_row, "选择文件…", func(): _show_file_picker(source_picker, source_edit.text))
	source_browse.name = "SourceFileBrowse"
	source_clear = button(source_row, "清除", func(): _set_node_file("source", ""))
	source_clear.tooltip_text = "清除选中节点的源文件"
	var context_row = HBoxContainer.new()
	context_row.name = "ReferenceImageField"
	inspector.add_child(context_row)
	context_edit = line(context_row, "未选择参考图像（可选）")
	context_edit.editable = false
	context_edit.tooltip_text = "通过系统资源管理器选择一张参考图像"
	context_browse = button(context_row, "选择图片…", func(): _show_file_picker(context_picker, context_edit.text))
	context_browse.name = "ReferenceImageBrowse"
	context_clear = button(context_row, "清除", func(): _set_node_file("image_context", ""))
	context_clear.tooltip_text = "清除选中节点的参考图像"
	source_picker = _make_file_picker("SourceFilePicker", "选择源图像或模型")
	source_picker.file_selected.connect(func(path): _set_node_file("source", path))
	source_picker.files_selected.connect(func(paths): _set_node_file("source", paths))
	context_picker = _make_file_picker("ReferenceImagePicker", "选择参考图像（可多选）")
	context_picker.filters = PackedStringArray(["*.png,*.jpg,*.jpeg ; PNG / JPEG 图像"])
	context_picker.file_selected.connect(func(path): _set_node_file("image_context", path))
	context_picker.files_selected.connect(func(paths): _set_node_file("image_context", paths))
	node_model_label = Label.new()
	node_model_label.text = "本节点模型"
	inspector.add_child(node_model_label)
	node_model_choice = OptionButton.new()
	node_model_choice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector.add_child(node_model_choice)
	node_model_edit = line(inspector, "本节点模型 ID；CLI 留空使用默认模型")
	node_model_choice.item_selected.connect(func(index): node_model_edit.text = str(node_model_choice.get_item_metadata(index)))
	node_image_model_label = Label.new()
	node_image_model_label.text = "本节点重绘图像模型"
	inspector.add_child(node_image_model_label)
	node_image_model_choice = OptionButton.new()
	node_image_model_choice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector.add_child(node_image_model_choice)
	node_image_model_edit = line(inspector, "重绘提示词非空时使用的图像模型")
	node_image_model_choice.item_selected.connect(func(index): node_image_model_edit.text = str(node_image_model_choice.get_item_metadata(index)))
	text_edit = TextEdit.new()
	text_edit.placeholder_text = "复制节点的文字说明（请勿填写凭据）"
	text_edit.custom_minimum_size.y = 65
	inspector.add_child(text_edit)
	parameter_form = preload("res://addons/ainative/parameter_form.gd").new()
	inspector.add_child(parameter_form)
	params_edit = parameter_form.raw_edit
	parameter_form.set_developer_mode(developer_mode.button_pressed)
	button(inspector, "应用到选中节点", apply_fields)
	button(inspector, "清除内嵌源文件和参考图像", clear_embedded)
	button(inspector, "运行并预览选中节点", func(): run_node_preview(selected_id))
	button(inspector, "预览选中结果", request_preview)
	history_choice = OptionButton.new()
	history_choice.item_selected.connect(show_history)
	inspector.add_child(history_choice)
	result_choice = OptionButton.new()
	result_choice.name = "ImageResultChoice"
	result_choice.item_selected.connect(show_result)
	inspector.add_child(result_choice)
	result_choice.hide()
	refresh_history()
	preview_maximize_button = button(inspector, "最大化预览", toggle_preview_maximized)
	preview_maximize_button.name = "PreviewMaximizeButton"
	preview_maximize_button.tooltip_text = "打开最大化预览；也可以双击图片或网格"
	preview_maximize_button.disabled = true
	native_inspector_fields = inspector.get_children()
	texture = TextureRect.new()
	texture.custom_minimum_size = Vector2(240, 120)
	texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	texture.tooltip_text = "双击最大化预览"
	texture.gui_input.connect(_image_preview_input)
	inspector.add_child(texture)
	texture.hide()
	var container = SubViewportContainer.new()
	mesh_container = container
	container.custom_minimum_size = Vector2(360, 280)
	container.stretch = true
	container.tooltip_text = "左键拖动旋转 · 中键拖动平移 · 滚轮缩放 · 双击最大化 / 还原预览"
	container.gui_input.connect(_mesh_preview_input)
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
	preview_window = Window.new()
	preview_window.name = "MaximizedNodePreview"
	preview_window.title = "节点预览"
	preview_window.min_size = Vector2i(480, 360)
	preview_window.size = Vector2i(1100, 760)
	preview_window.transient = true
	preview_window.exclusive = true
	preview_window.close_requested.connect(restore_preview)
	add_child(preview_window)
	preview_window.hide()
	var window_fields = VBoxContainer.new()
	window_fields.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	preview_window.add_child(window_fields)
	var preview_bar = HBoxContainer.new()
	window_fields.add_child(preview_bar)
	var preview_hint = Label.new()
	preview_hint.text = "双击预览可还原到工作台"
	preview_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview_bar.add_child(preview_hint)
	preview_restore_button = button(preview_bar, "还原预览", restore_preview)
	preview_restore_button.name = "PreviewRestoreButton"
	preview_window_host = VBoxContainer.new()
	preview_window_host.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview_window_host.size_flags_vertical = Control.SIZE_EXPAND_FILL
	window_fields.add_child(preview_window_host)
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
	button(publish_bar, "保存生成物…", open_save_dialog)
	save_picker = FileDialog.new()
	save_picker.title = "保存生成物"
	save_picker.ok_button_text = "保存"
	save_picker.cancel_button_text = "取消"
	save_picker.access = FileDialog.ACCESS_FILESYSTEM
	save_picker.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	save_picker.use_native_dialog = true
	save_picker.file_selected.connect(save_preview_to)
	add_child(save_picker)
	artifact_download_picker = FileDialog.new()
	artifact_download_picker.title = "下载全部图片到项目目录"
	artifact_download_picker.ok_button_text = "下载到这里"
	artifact_download_picker.cancel_button_text = "取消"
	artifact_download_picker.access = FileDialog.ACCESS_FILESYSTEM
	artifact_download_picker.file_mode = FileDialog.FILE_MODE_OPEN_DIR
	artifact_download_picker.use_native_dialog = true
	artifact_download_picker.dir_selected.connect(_download_artifact_images)
	add_child(artifact_download_picker)
	dialog = ConfirmationDialog.new()
	dialog.title = "确认发布"
	dialog.ok_button_text = "发布新文件"
	dialog.cancel_button_text = "取消"
	add_child(dialog)
	dialog.confirmed.connect(confirm_publish)
	capability_notice_dialog = AcceptDialog.new()
	capability_notice_dialog.title = "模型已按能力受限结果交付"
	capability_notice_dialog.ok_button_text = "知道了"
	add_child(capability_notice_dialog)
	failure_dialog = AcceptDialog.new()
	failure_dialog.title = "操作失败"
	failure_dialog.ok_button_text = "关闭"
	failure_dialog.exclusive = false
	var failure_box = VBoxContainer.new()
	failure_text = TextEdit.new()
	failure_text.editable = false
	failure_text.selecting_enabled = true
	failure_text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	failure_text.custom_minimum_size = Vector2(680, 250)
	failure_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	failure_box.add_child(failure_text)
	var failure_actions = HBoxContainer.new()
	failure_copy_button = Button.new()
	failure_copy_button.text = "复制全部报错"
	failure_copy_button.pressed.connect(_copy_failure_text)
	failure_actions.add_child(failure_copy_button)
	failure_copy_hint = Label.new()
	failure_copy_hint.text = "也可直接选择文本复制。"
	failure_copy_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	failure_actions.add_child(failure_copy_hint)
	failure_box.add_child(failure_actions)
	failure_dialog.add_child(failure_box)
	add_child(failure_dialog)
	status = Label.new()
	status.text = "右键节点运行；真实生成请先在“设置 → AI”连接服务，并在各节点选择模型。" if builtin else "右键节点运行；真实生成请先在“本机设置”连接服务，并在各节点选择模型。"
	if managed_comfy_panel.using_bundle() and _service_mode() in ['codex', 'local_mesh']:
		status.text = '已有图片可直接运行“图像生成网格”。使用原图时请留空提示词。'
	content.add_child(status)
	service_config_link = button(self, "配置生成服务", open_service_settings)
	service_config_link.hide()
	if builtin:
		native_sections = {'machine':machine,'character':character_panel,'advanced':advanced,'title':diagnostics_title,'bar':bar,'split':split,'publish':publish_bar}
		status.reparent(self)
		status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		show_native_section('mesh')
	var reopen_previous = settings.has_section_key("workflow", "last_path") and FileAccess.file_exists(path_edit.text)
	if reopen_previous:
		open_graph()
	elif FileAccess.file_exists(state_dir.path_join("last_run.txt")):
		_configure_controller()
		controller.restore_run(FileAccess.get_file_as_string(state_dir.path_join("last_run.txt")))
	if nodes.is_empty(): add_node()

func show_native_section(section: String):
	if native_sections.is_empty(): return
	if section != 'mesh': restore_preview()
	if section == 'settings':
		settings_requested.emit('environment')
		return
	native_sections.character.visible = section=='character'
	native_sections.advanced.visible = section!='character'
	native_sections.machine.hide()
	native_sections.bar.visible = section=='mesh'
	native_sections.split.visible = section in ['mesh','rig','other']
	graph.visible = section=='mesh'
	rigging_panel.visible = section=='rig'
	native_sections.publish.visible = section=='mesh'
	for field in native_inspector_fields: field.visible = section=='mesh'
	result_choice.visible = section=='mesh' and current_images.size() > 1
	for panel in native_other_panels: panel.visible = section=='other'
	texture.visible = section=='mesh' and preview_resource!=null
	mesh_container.visible = is_instance_valid(preview_scene)
	native_sections.title.text = {'mesh':'网格生成 · 右键画布添加节点，右键节点编辑、预览和管理结果。','rig':'骨骼绑定 · 使用当前网格一键绑定；需要修正时展开高级选项。','other':'独立模块工具 · 每个模块使用自己的角色。','settings':'本机设置 · 内置工具已随引擎提供；真实生成需要配置模型服务。'}.get(section,'')
	for key in native_buttons: native_buttons[key].button_pressed = key==section
	native_scroll.scroll_vertical = 0

# The native settings page reparents these exact controls. Consumers keep their
# original pointers and local.cfg / generation-service.json remain authoritative.
func get_settings_sections() -> Dictionary:
	return settings_sections.duplicate()

# Called by the native host before removing this workbench. Reclaiming the
# controls preserves their lifetime relationship with callbacks to this host.
func reclaim_settings_sections():
	for control in settings_sections.values():
		if not is_instance_valid(control): continue
		if control.get_parent() != self:
			if control.get_parent() == null: add_child(control)
			else: control.reparent(self)
		control.hide()

func save_settings():
	var c = ConfigFile.new()
	c.load(state_dir.path_join("local.cfg"))
	# Resolve shipped components again from the executable after a move.
	var uses_bundled_python = bundled_runtime.has('python') and python_edit.text == bundled_runtime.python
	c.set_value('host', 'use_bundled_python', uses_bundled_python)
	c.set_value("host", "python", null if uses_bundled_python else python_edit.text)
	var bundled = get_meta('ainative_builtin',false) and host_edit.text==str(get_meta('ainative_tools_dir','')).path_join('editor_host.py')
	c.set_value('host','use_bundled_script',bundled)
	if not bundled: c.set_value("host", "script", host_edit.text)
	c.set_value("host", "factory", factory_edit.text)
	c.set_value("interface", "developer_mode", developer_mode.button_pressed)
	if blender_path_edit != null: c.set_value("service", "blender_path", blender_path_edit.text.strip_edges())
	if kimi_image_tool_edit != null: c.set_value('service', 'image_tool_path', kimi_image_tool_edit.text.strip_edges())
	if kimi_image_pythonw_edit != null: c.set_value('service', 'image_pythonw_path', kimi_image_pythonw_edit.text.strip_edges())
	if _using_legacy_service(): c.set_value("service", "mode", "legacy")
	c.save(state_dir.path_join("local.cfg"))

func diagnostic_error(summary: String, raw_details) -> String:
	var path = state_dir.path_join('diagnostics.log')
	var output = FileAccess.open(path,FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
	if output==null: return summary.trim_suffix('。')+'。本机诊断日志无法写入。'
	output.seek_end()
	output.store_line(Time.get_datetime_string_from_system(true)+' '+summary+'\n'+str(raw_details))
	output.close()
	return summary.trim_suffix('。')+'。可在“本机设置”中打开诊断日志。'

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
	var data = {"id": id, "type": kind, "version": _new_node_version(kind), "provider": _generator_provider(kind), "source": "", "image_context": "", "text": "", "parameters": {"prompt": "" if kind in ["image_to_mesh", "model_adjust"] else "白色背景上的小型石雕", "seed": 1}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45}
	if kind != 'copy' and _service_mode() in ['api_modeling', 'api_sculpt']: data.model = ''
	_migrate_node_models(data, service_draft())
	nodes.append(data)
	rebuild()
	select_node(id)

func _migrate_node_models(data: Dictionary, legacy: Dictionary):
	var kind = str(data.get('type', 'copy'))
	var mode = _service_mode()
	# Nodes created before the first saved service inherit once on that first save.
	if kind == 'copy' or _retired_mesh_node(data) or _using_legacy_service() or (service_saved.is_empty() and not data.has('model')): return
	var cli_mode = mode == 'codex'
	var mesh_kind = _is_mesh_kind(kind)
	var legacy_image = str(legacy.get('image_model', ''))
	if not data.has('model'):
		if mode in ['api_modeling', 'api_sculpt']:
			var legacy_model = legacy.get('api_model', '')
			data.model = legacy_model if typeof(legacy_model) == TYPE_STRING else ''
		elif mode == 'kimi_native': data.model = str(legacy.get('model3d_model', 'v3.1')) if mesh_kind else ''
		elif cli_mode and not mesh_kind: data.model = legacy_image if not legacy_image.is_empty() else 'builtin'
		else: data.model = str(legacy.get('mesh_model', '') if mesh_kind else legacy_image)
	if kind.ends_with('mesh') and not data.has('image_model'):
		if mode == 'codex': data.image_model = legacy_image if not legacy_image.is_empty() else 'builtin'
		else: data.image_model = legacy_image if mode == 'comfy' else ''

func _sync_node_model_controls(data: Dictionary):
	var kind = str(data.get('type', 'copy'))
	var generating = kind != 'copy' and not _retired_mesh_node(data) and not _using_legacy_service()
	node_model_label.visible = generating
	node_model_choice.visible = generating and _service_mode() not in ['api_modeling', 'api_sculpt']
	node_model_edit.visible = generating
	var secondary_image = generating and kind == 'text_to_mesh' and _service_mode() not in ['kimi_native', 'api_modeling', 'api_sculpt']
	node_image_model_label.text = '本节点文字生成图像模型'
	node_image_model_label.visible = secondary_image
	node_image_model_choice.visible = secondary_image
	node_image_model_edit.visible = secondary_image
	if not generating: return
	var models: Dictionary = service_report.get('models', {}) if service_report_draft == JSON.stringify(service_draft()) else {}
	var primary = models.get('mesh' if _is_mesh_kind(kind) else 'image', [])
	var primary_name = str(data.get('model', ''))
	if _service_mode() in ['api_modeling', 'api_sculpt'] and typeof(data.get('model', '')) != TYPE_STRING:
		primary_name = ''
	if _service_mode() == 'codex' and not _is_mesh_kind(kind): primary = ['builtin']
	_set_model_options(node_model_choice, primary, primary_name, not models.is_empty())
	node_model_edit.text = primary_name
	node_model_edit.placeholder_text = '填写或选择本节点模型 ID'
	if secondary_image:
		var image_name = str(data.get('image_model', ''))
		_set_model_options(node_image_model_choice, models.get('image', ['builtin'] if _service_mode() == 'codex' else []), image_name, not models.is_empty())
		node_image_model_edit.text = image_name

func _image_queue_node(data: Dictionary) -> bool:
	var kind = str(data.get("type", "copy"))
	if kind == GENERATE_IMAGE: return data.get("version", "2") in ["1", "2"]
	return kind in ["text_to_image", "image_to_image"] and data.get("version", "4") in ["2", "3", "4"]

func _queue_only_node(data: Dictionary) -> bool:
	var kind = str(data.get("type", "copy"))
	return _image_queue_node(data) and (kind == GENERATE_IMAGE or data.get("version", "4") in ["3", "4"])

func _accepts_image_set(data: Dictionary) -> bool:
	var kind = str(data.get("type", "copy"))
	return (kind == GENERATE_IMAGE or kind == "image_to_image") and _image_queue_node(data) or kind == "image_to_mesh" and data.get("version", "1") == "2"

func _accepts_single_image(source: Dictionary, target: Dictionary) -> bool:
	return _accepts_image_set(target) and output_kind(source) == PORT_IMAGE

func input_kind(data: Dictionary) -> int:
	var kind = str(data.get("type", "copy"))
	if kind in ["text_to_image", "text_to_mesh"]: return PORT_TEXT
	# The GraphEdit compatibility rule registered in _ready also permits image_set here.
	if _accepts_image_set(data): return PORT_IMAGE
	if kind in ["image_to_image", "image_to_mesh"]: return PORT_IMAGE
	if kind == "model_adjust": return PORT_MESH
	return PORT_DYNAMIC

func output_kind(data: Dictionary) -> int:
	var kind = str(data.get("type", "copy"))
	if _queue_only_node(data): return PORT_IMAGE_SET
	return PORT_MESH if _is_mesh_kind(kind) else PORT_DYNAMIC if kind == "copy" else PORT_IMAGE

func port_type_name(kind: int) -> String:
	return {PORT_DYNAMIC:"图片 / Mesh", PORT_IMAGE:"图片", PORT_MESH:"Mesh", PORT_TEXT:"文本", PORT_IMAGE_SET:"图片队列"}.get(kind, "未知")

func input_type_name(data: Dictionary) -> String:
	var kind = str(data.get("type", "copy"))
	if kind == GENERATE_IMAGE: return "图片 / 图片列表（可选）＋文本（参数）"
	return "图片 / 图片列表" if _accepts_image_set(data) and kind in ["image_to_image", "image_to_mesh"] else port_type_name(input_kind(data))

func _latest_image_entry(node_id: String) -> Dictionary:
	var history: Array = preview_history.get(node_id, [])
	if history.is_empty(): return {}
	var entry = history.back()
	if not entry is Dictionary or entry.get("type", "") != "image": return {}
	return entry

func _latest_mesh_entry(node_id: String) -> Dictionary:
	var history: Array = preview_history.get(node_id, [])
	if history.is_empty(): return {}
	var entry = history.back()
	if not entry is Dictionary or entry.get("type", "") != "mesh": return {}
	return entry

func _artifact_images(entry: Dictionary) -> Array:
	var images = entry.get("images", [])
	if images is Array and not images.is_empty(): return images
	return [entry]

func _mesh_iterations(entry: Dictionary) -> Array:
	var iterations = entry.get("iterations", [])
	if iterations is Array and not iterations.is_empty(): return iterations
	return [entry] if entry.get("type", "") == "mesh" else []

func _mesh_artifact_key(source_id: String, entry: Dictionary) -> String:
	return source_id + "::" + str(entry.get("artifact", {}).get("revision", entry.get("token", "")))

func _style_artifact_node(node: GraphNode):
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.055, 0.14, 0.16, 0.98)
	style.border_color = Color(0.24, 0.82, 0.72)
	style.set_border_width_all(2)
	style.set_corner_radius_all(18)
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	node.add_theme_stylebox_override("panel", style)
	var selected_style = style.duplicate() as StyleBoxFlat
	selected_style.border_color = Color(0.95, 0.82, 0.38)
	node.add_theme_stylebox_override("panel_selected", selected_style)

func _artifact_preview_input(event: InputEvent, key: String, index: int, control: Control):
	if not event is InputEventMouseButton or not event.pressed or event.button_index != MOUSE_BUTTON_LEFT or not event.double_click: return
	_show_artifact_result(key, index)
	if _displayed_preview() != null: toggle_preview_maximized()
	control.accept_event()

func _create_artifact_node(data: Dictionary, entry: Dictionary):
	var source_id = str(data.id)
	var artifact_id = "artifact_" + source_id
	while nodes.any(func(item): return item.id == artifact_id): artifact_id += "_dynamic"
	var images = _artifact_images(entry)
	var node = GraphNode.new()
	node.name = artifact_id
	node.title = "◇ 图片生成物"
	node.position_offset = Vector2(data.x + 340, data.y)
	node.tooltip_text = "动态生成物节点：双击放大对应图片；不参与工作流执行"
	node.set_meta("maliang_artifact", true)
	node.set_meta("artifact_source", source_id)
	node.set_meta("artifact_key", source_id)
	_style_artifact_node(node)
	var summary = Label.new()
	summary.name = "ArtifactSummary"
	summary.text = "动态节点 · 来自 %s · %d 张图片" % [source_id, images.size()]
	summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(summary)
	node.set_slot(0, true, PORT_DYNAMIC, PORT_COLORS[PORT_IMAGE_SET], true, PORT_DYNAMIC, PORT_COLORS[PORT_IMAGE_SET])
	var gallery = GridContainer.new()
	gallery.name = "ArtifactGallery"
	gallery.columns = 2 if images.size() > 1 else 1
	gallery.add_theme_constant_override("h_separation", 10)
	gallery.add_theme_constant_override("v_separation", 10)
	node.add_child(gallery)
	for index in images.size():
		var item = images[index]
		if not item is Dictionary: continue
		var item_box = VBoxContainer.new()
		item_box.custom_minimum_size.x = 132
		gallery.add_child(item_box)
		var thumbnail = TextureRect.new()
		thumbnail.name = "ArtifactThumbnail%d" % index
		thumbnail.custom_minimum_size = Vector2(124, 78)
		thumbnail.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		thumbnail.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		thumbnail.mouse_filter = Control.MOUSE_FILTER_STOP
		thumbnail.tooltip_text = "双击放大这张图片"
		var image = Image.load_from_file(str(item.get("path", "")))
		if image != null: thumbnail.texture = ImageTexture.create_from_image(image)
		item_box.add_child(thumbnail)
		thumbnail.gui_input.connect(_artifact_preview_input.bind(source_id, index, thumbnail))
		var preview_button = button(item_box, "%d. %s" % [index + 1, str(item.get("label", "独立图片"))], _show_artifact_result.bind(source_id, index))
		preview_button.name = "ArtifactImage%d" % index
		preview_button.tooltip_text = "在右侧预览这张图片；双击放大"
		preview_button.clip_text = true
		preview_button.gui_input.connect(_artifact_preview_input.bind(source_id, index, preview_button))
	var download_button = button(node, "下载全部到项目…", _open_artifact_download.bind(source_id))
	download_button.name = "DownloadArtifacts"
	download_button.tooltip_text = "选择项目目录，保留每张图片的原始字节"
	graph.add_child(node)
	node.gui_input.connect(_artifact_preview_input.bind(source_id, 0, node))
	node.node_selected.connect(_show_artifact_result.bind(source_id, 0))
	artifact_nodes[source_id] = {"id": artifact_id, "entry": entry, "source": source_id, "kind": "image"}

func _create_mesh_artifact_node(data: Dictionary, entry: Dictionary, attempt: int):
	var source_id = str(data.id)
	var key = _mesh_artifact_key(source_id, entry)
	var artifact_id = "artifact_%s_round_%03d" % [source_id, attempt]
	while nodes.any(func(item): return item.id == artifact_id): artifact_id += "_dynamic"
	var node = GraphNode.new()
	node.name = artifact_id
	node.title = "◇ Mesh 生成物 · 第 %d 轮" % attempt
	node.position_offset = Vector2(data.x + 340, data.y + (attempt - 1) * 180)
	node.tooltip_text = "双击放大本轮 Mesh；可独立保存并作为固定轮次输入连接到下游节点"
	node.set_meta("maliang_artifact", true)
	node.set_meta("artifact_source", source_id)
	node.set_meta("artifact_key", key)
	node.set_meta("iteration", attempt)
	_style_artifact_node(node)
	var summary = Label.new()
	summary.name = "ArtifactSummary"
	var review_text = "已生成 GLB"
	if entry.get("review_passed", null) == true: review_text = "视觉审核通过"
	elif entry.get("review_passed", null) == false: review_text = "视觉审核未通过"
	summary.text = "动态节点 · 来自 %s · %s" % [source_id, review_text]
	summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(summary)
	node.set_slot(0, true, PORT_DYNAMIC, PORT_COLORS[PORT_MESH], true, PORT_DYNAMIC, PORT_COLORS[PORT_MESH])
	var thumbnail = preload("res://addons/ainative/mesh_artifact_preview.gd").new()
	thumbnail.name = "ArtifactMeshPreview"
	thumbnail.mouse_filter = Control.MOUSE_FILTER_STOP
	thumbnail.tooltip_text = "双击放大本轮 Mesh"
	node.add_child(thumbnail)
	thumbnail.gui_input.connect(_artifact_preview_input.bind(key, 0, thumbnail))
	var preview_button = button(node, "旋转 / 缩放第 %d 轮 Mesh" % attempt, _show_artifact_result.bind(key))
	preview_button.name = "PreviewMeshArtifact"
	preview_button.tooltip_text = "在右侧旋转和缩放；双击直接放大"
	preview_button.gui_input.connect(_artifact_preview_input.bind(key, 0, preview_button))
	var save_button = button(node, "保存本轮 GLB…", _save_mesh_artifact.bind(key))
	save_button.name = "SaveMeshArtifact"
	save_button.tooltip_text = "另存本轮原始 GLB，不覆盖其他轮次"
	graph.add_child(node)
	thumbnail.show_mesh(str(entry.get("path", "")))
	node.gui_input.connect(_artifact_preview_input.bind(key, 0, node))
	node.node_selected.connect(_show_artifact_result.bind(key))
	artifact_nodes[key] = {"id": artifact_id, "entry": entry, "source": source_id, "kind": "mesh", "attempt": attempt}

func _mark_artifact_deleted(key: String):
	if artifact_nodes.has(key):
		dismissed_artifacts[key] = str(artifact_nodes[key].entry.get("token", ""))
		return
	var entry = _latest_image_entry(key)
	if not entry.is_empty(): dismissed_artifacts[key] = str(entry.get("token", ""))

func _delete_artifact_node(key: String):
	if is_graph_busy():
		status.text = "请等待当前运行结束或先取消，再删除生成物节点"
		return
	_mark_artifact_deleted(key)
	rebuild()
	status.text = "已删除动态生成物节点；正式节点、生成历史和生成物文件均保留"

func _reveal_mesh_preview():
	if is_instance_valid(native_scroll) and native_scroll.is_ancestor_of(mesh_container) and mesh_container.is_visible_in_tree():
		native_scroll.ensure_control_visible(mesh_container)

func _show_artifact_result(key: String, index: int = 0):
	if artifact_nodes.has(key) and artifact_nodes[key].get("kind", "image") == "mesh":
		var record: Dictionary = artifact_nodes[key]
		var entry: Dictionary = record.entry
		select_node(record.source)
		load_preview(entry, record.source, str(entry.get("run", "")))
		if is_instance_valid(preview_scene): call_deferred("_reveal_mesh_preview")
		status.text += " · 第 %d 轮" % int(record.get("attempt", 1))
		return
	var entry = _latest_image_entry(key)
	if entry.is_empty(): return
	select_node(key)
	load_preview(entry, key, str(entry.get("run", "")))
	if index > 0: show_result(index)

func _save_mesh_artifact(key: String):
	if not artifact_nodes.has(key) or artifact_nodes[key].get("kind", "") != "mesh": return
	_show_artifact_result(key)
	if preview_source_path.is_empty(): return
	var attempt = int(artifact_nodes[key].get("attempt", 1))
	open_save_dialog()
	save_picker.current_file = ("mesh-round-%03d-%s.glb" % [attempt, str(artifact_nodes[key].entry.get("artifact", {}).get("revision", "")).left(12)]).validate_filename()

func _open_artifact_download(key: String):
	if artifact_nodes.has(key) and artifact_nodes[key].get("kind", "image") == "mesh":
		_save_mesh_artifact(key)
		return
	if _latest_image_entry(key).is_empty():
		status.text = "该节点暂无可下载的图片"
		return
	artifact_download_source = key
	var project_output = ProjectSettings.globalize_path("res://generated").path_join(key)
	if DirAccess.make_dir_recursive_absolute(project_output) != OK:
		status.text = "无法创建项目生成物目录：" + project_output
		return
	artifact_download_picker.current_dir = project_output
	artifact_download_picker.popup_centered_ratio(0.7)

func _download_artifact_images(directory: String, source_id: String = ""):
	var source = artifact_download_source if source_id.is_empty() else source_id
	var entry = _latest_image_entry(source)
	if entry.is_empty() or directory.is_empty():
		status.text = "请选择有效的生成物和目标目录"
		return
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		status.text = "无法创建下载目录：" + directory
		return
	var images = _artifact_images(entry)
	for index in images.size():
		var item = images[index]
		if not item is Dictionary: return
		var source_path = str(item.get("path", ""))
		if not FileAccess.file_exists(source_path):
			status.text = "生成物源文件已不可用：" + source_path
			return
		var extension = "." + source_path.get_extension().to_lower()
		if extension not in [".png", ".jpg", ".jpeg"]: extension = ".png"
		var artifact = item.get("artifact", {})
		var identity = str(artifact.get("id", source)) if artifact is Dictionary else source
		if identity.is_empty(): identity = source
		var filename = ("%02d-%s" % [index + 1, identity]).validate_filename() + extension
		var target = directory.path_join(filename)
		var err = DirAccess.copy_absolute(source_path, target)
		if err != OK or FileAccess.get_sha256(target) != FileAccess.get_sha256(source_path):
			status.text = "下载生成物失败：" + (error_string(err) if err != OK else target)
			return
	status.text = "已下载 %d 张图片：%s" % [images.size(), directory]
	if Engine.is_editor_hint(): EditorInterface.get_resource_filesystem().scan()

func _schedule_artifact_layout():
	if artifact_nodes.is_empty() or artifact_layout_pending: return
	artifact_layout_pending = true
	call_deferred("_layout_graph_with_artifacts")

func _layout_graph_with_artifacts():
	artifact_layout_pending = false
	if not is_instance_valid(graph) or artifact_nodes.is_empty(): return
	var graph_nodes: Array = []
	for child in graph.get_children():
		if child is GraphNode:
			child.reset_size()
			graph_nodes.append(child)
	var layers: Dictionary = {}
	var indegree: Dictionary = {}
	var outgoing: Dictionary = {}
	var ids: Array = []
	for node in graph_nodes:
		var id = str(node.name)
		ids.append(id)
		layers[id] = 0
		indegree[id] = 0
		outgoing[id] = []
	for connection in graph.get_connection_list():
		var from_id = str(connection.from_node)
		var to_id = str(connection.to_node)
		if not indegree.has(from_id) or not indegree.has(to_id): continue
		indegree[to_id] += 1
		outgoing[from_id].append(to_id)
	var ready: Array = []
	for id in ids:
		if indegree[id] == 0: ready.append(id)
	ready.sort()
	while not ready.is_empty():
		var id = ready.pop_front()
		for next_id in outgoing[id]:
			layers[next_id] = maxi(layers[next_id], layers[id] + 1)
			indegree[next_id] -= 1
			if indegree[next_id] == 0:
				ready.append(next_id)
				ready.sort()
	var columns: Dictionary = {}
	for id in ids:
		var layer = layers[id]
		if not columns.has(layer): columns[layer] = []
		columns[layer].append(id)
	var column_keys = columns.keys()
	column_keys.sort()
	var x_positions: Dictionary = {}
	var column_heights: Dictionary = {}
	var x = 60.0
	var tallest = 0.0
	for layer in column_keys:
		var width = 0.0
		var height = 48.0 * maxi(columns[layer].size() - 1, 0)
		for id in columns[layer]:
			var node = graph.get_node(NodePath(id)) as GraphNode
			var minimum = node.get_combined_minimum_size()
			var measured = Vector2(maxf(node.size.x, minimum.x), maxf(node.size.y, minimum.y))
			node.set_meta("artifact_layout_size", measured)
			width = maxf(width, measured.x)
			height += measured.y
		x_positions[layer] = x
		column_heights[layer] = height
		tallest = maxf(tallest, height)
		x += width + 120.0
	for layer in column_keys:
		var y = 60.0 + (tallest - column_heights[layer]) * 0.5
		for id in columns[layer]:
			var node = graph.get_node(NodePath(id)) as GraphNode
			node.position_offset = Vector2(x_positions[layer], y)
			y += node.get_meta("artifact_layout_size").y + 48.0
			if node.get_meta("maliang_artifact", false): continue
			for data in nodes:
				if data.id == id:
					data.x = node.position_offset.x
					data.y = node.position_offset.y
					break
	# Keep the complete generated chain visible when the inspector narrows the canvas.
	var content_width = maxf(x - 60.0, 1.0)
	var fit_zoom = clampf((graph.size.x - 24.0) / content_width, 0.55, 1.0)
	if graph.zoom > fit_zoom: graph.zoom = fit_zoom
	graph.scroll_offset = Vector2.ZERO

func rebuild():
	graph.clear_connections()
	artifact_nodes.clear()
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
		label.name = 'GeneratorDescription'
		label.text = _generator_description(data)
		node.add_child(label)
		var type_row = HBoxContainer.new()
		type_row.name = 'PortTypes'
		node.add_child(type_row)
		var input_label = Label.new()
		input_label.name = 'InputType'
		input_label.text = "输入：" + input_type_name(data)
		input_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if input_kind(data) == PORT_TEXT:
			input_label.text += "（参数）"
			input_label.tooltip_text = "文本由当前节点的提示词参数提供"
		type_row.add_child(input_label)
		var output_label = Label.new()
		output_label.name = 'OutputType'
		output_label.text = "输出：" + port_type_name(output_kind(data))
		output_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		type_row.add_child(output_label)
		node.set_slot(1, input_kind(data) != PORT_TEXT, input_kind(data), PORT_COLORS[input_kind(data)], true, output_kind(data), PORT_COLORS[output_kind(data)])
		graph.add_child(node)
		var run_button = button(node, "运行并预览", run_node_preview.bind(data.id))
		run_button.mouse_filter = Control.MOUSE_FILTER_PASS
		if _image_queue_node(data) and not _queue_only_node(data):
			var set_label = Label.new()
			set_label.name = 'ImageSetOutputType'
			set_label.text = "输出：图片队列（有序）"
			set_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			node.add_child(set_label)
			node.set_slot(3, false, 0, PORT_COLORS[PORT_IMAGE], true, PORT_IMAGE_SET, PORT_COLORS[PORT_IMAGE_SET])
		node.node_selected.connect(select_node.bind(data.id))
		node.position_offset_changed.connect(func(): data.x = node.position_offset.x; data.y = node.position_offset.y)
	var mesh_chains: Dictionary = {}
	for data in nodes:
		var source_id = str(data.id)
		var entry = _latest_image_entry(source_id)
		if not entry.is_empty() and dismissed_artifacts.get(source_id, "") != str(entry.get("token", "")):
			_create_artifact_node(data, entry)
		if not _is_mesh_kind(str(data.get("type", ""))): continue
		var mesh_entry = _latest_mesh_entry(source_id)
		if mesh_entry.is_empty(): continue
		mesh_chains[source_id] = []
		var iterations = _mesh_iterations(mesh_entry)
		for index in iterations.size():
			var iteration: Dictionary = iterations[index]
			var key = _mesh_artifact_key(source_id, iteration)
			if dismissed_artifacts.get(key, "") == str(iteration.get("token", "")): continue
			_create_mesh_artifact_node(data, iteration, int(iteration.get("attempt", index + 1)))
			mesh_chains[source_id].append(key)
	for key in artifact_nodes:
		var record: Dictionary = artifact_nodes[key]
		var source_id = str(record.source)
		var source = nodes.filter(func(n): return n.id == source_id)[0]
		if record.get("kind", "image") == "image":
			var entry: Dictionary = record.entry
			var from_port = 1 if not _queue_only_node(source) and entry.has("images") else 0
			graph.connect_node(source_id, from_port, str(record.id), 0)
			continue
		var chain: Array = mesh_chains.get(source_id, [])
		var chain_index = chain.find(key)
		if chain_index > 0:
			graph.connect_node(str(artifact_nodes[chain[chain_index - 1]].id), 0, str(record.id), 0)
		else:
			graph.connect_node(source_id, 0, str(record.id), 0)
	for edge in edges:
		var source = nodes.filter(func(n): return n.id == edge.from)[0]
		var from_port = 1 if edge.get("output", "result") == "image_set" and not _queue_only_node(source) else 0
		if edge.has("artifact"):
			var selected_key = _mesh_artifact_key(str(edge.from), {"artifact": edge.artifact})
			if artifact_nodes.has(selected_key):
				graph.connect_node(str(artifact_nodes[selected_key].id), 0, edge.to, 0)
				continue
		if artifact_nodes.has(edge.from):
			graph.connect_node(str(artifact_nodes[edge.from].id), 0, edge.to, 0)
		elif not mesh_chains.get(edge.from, []).is_empty():
			var chain: Array = mesh_chains[edge.from]
			graph.connect_node(str(artifact_nodes[chain.back()].id), 0, edge.to, 0)
		else:
			graph.connect_node(edge.from, from_port, edge.to, 0)
	_schedule_artifact_layout()

func _merged_requirements(primary: String, supplementary: String) -> String:
	var main = primary.strip_edges()
	var extra = supplementary.strip_edges()
	if main.is_empty(): return extra
	if extra.is_empty(): return main
	return main + "\n" + extra

func _clear_image_mesh_text(data: Dictionary):
	if str(data.get("type", "")) != "image_to_mesh": return
	data.text = ""
	var parameters: Dictionary = data.get("parameters", {})
	parameters["prompt"] = ""
	data.parameters = parameters

func select_node(id: String):
	var changed = selected_id != id
	selected_id = id
	var selected_kind = "copy"
	for data in nodes:
		if data.id == id:
			_clear_image_mesh_text(data)
			selected_kind = data.get("type", "copy")
			_sync_node_model_controls(data)
			_sync_node_files(data)
			source_edit.text = " ; ".join(_node_paths(data, "source"))
			context_edit.text = " ; ".join(_node_paths(data, "image_context"))
			text_edit.visible = selected_kind == "copy"
			if selected_kind == "copy":
				text_edit.text = str(data.get("text", ""))
				parameter_form.configure(selected_kind, data.parameters)
			else:
				# Legacy text and prompt become one editable requirement. The old
				# field is cleared only when the user applies or runs the node.
				var requirements = data.parameters.duplicate(true)
				requirements["prompt"] = _merged_requirements(str(requirements.get("prompt", "")), str(data.get("text", "")))
				text_edit.text = ""
				parameter_form.configure(selected_kind, requirements, str(data.get("version", "1")))
	_configure_source_picker(selected_kind, nodes.filter(func(n): return n.id == selected_id)[0])
	source_edit.tooltip_text = source_edit.text if not source_edit.text.is_empty() else "通过系统资源管理器选择源文件，可多选"
	context_edit.tooltip_text = context_edit.text if not context_edit.text.is_empty() else "通过系统资源管理器选择参考图像，可多选"
	refresh_history()
	if changed:
		clear_preview()
		if not preview_history.get(id, []).is_empty():
			show_history(preview_history[id].size() - 1)

func apply_fields() -> bool:
	var params = parameter_form.parameters()
	if not params is Dictionary or not safe(params):
		_show_run_problem(parameter_form.error_label.text if not params is Dictionary else "参数含有禁止填写的凭据字段")
		return false
	for data in nodes:
		if data.id == selected_id:
			if data.get('type', 'copy') != 'copy' and not _retired_mesh_node(data) and not _using_legacy_service():
				var primary_name = node_model_edit.text.strip_edges()
				if _service_mode() in ['api_modeling', 'api_sculpt']: primary_name = node_model_edit.text
				if data.has('model') or not primary_name.is_empty(): data.model = primary_name
				if data.get('type', '') == 'text_to_mesh':
					var secondary_name = node_image_model_edit.text.strip_edges()
					if data.has('image_model') or not secondary_name.is_empty(): data.image_model = secondary_name
			_sync_node_files(data)
			if data.get("type", "copy") == "copy":
				data.text = text_edit.text
			else:
				# Keep the hidden control compatible with existing automation while
				# storing all non-copy requirements in the canonical prompt field.
				params["prompt"] = _merged_requirements(str(params.get("prompt", "")), text_edit.text)
				data.text = ""
			data.parameters = params
			_clear_image_mesh_text(data)
	_update_service_summary()
	return true

func safe(value) -> bool:
	if value is Dictionary:
		for key in value:
			if str(key).to_lower() in ["token", "api_key", "apikey", "password", "secret", "authorization", "credentials", "factory", "python"] or not safe(value[key]): return false
	elif value is Array:
		for child in value:
			if not safe(child): return false
	return true

func connect_nodes(from: StringName, from_port: int, to: StringName, _tp: int):
	if from == to: return
	var source_node = nodes.filter(func(n): return n.id == from)
	var target_node = nodes.filter(func(n): return n.id == to)
	if target_node.is_empty(): return
	var target_kind = target_node[0].get("type", "copy")
	if target_kind.begins_with("text_"): return
	for key in artifact_nodes:
		var record: Dictionary = artifact_nodes[key]
		if record.id != str(from): continue
		if record.get("kind", "image") != "mesh":
			status.text = "图片生成物请从正式图片节点连接下游"
			return
		if target_kind not in ["copy", "model_adjust"]:
			status.text = "Mesh 轮次生成物只能连接到 Mesh 输入"
			return
		for edge in edges:
			if edge.to == to: return
		edges.append({
			"from": str(record.source),
			"to": str(to),
			"input": "source",
			"output": "result",
			"artifact": record.entry.get("artifact", {}).duplicate(true),
			"iteration": int(record.get("attempt", 1))
		})
		rebuild()
		status.text = "已连接第 %d 轮 Mesh；下游将使用这一轮的固定 GLB 快照" % int(record.get("attempt", 1))
		return
	if source_node.is_empty(): return
	var output = "image_set" if _queue_only_node(source_node[0]) or (_image_queue_node(source_node[0]) and from_port == 1) else "result"
	if output == "image_set":
		if not _accepts_image_set(target_node[0]):
			status.text = "目标节点不支持图片列表输入；请连接单张图片或选择支持图片列表的节点"
			return
	elif target_kind != "copy" and ((_accepts_image_set(target_node[0]) and not _accepts_single_image(source_node[0], target_node[0])) or (not _accepts_image_set(target_node[0]) and output_kind(source_node[0]) != input_kind(target_node[0]))):
		status.text = "模型调整需要连接已生成模型" if target_kind == "model_adjust" else "生成节点的输入与输出类型不匹配"
		return
	for edge in edges:
		if edge.to == to: return
	edges.append({"from": str(from), "to": str(to), "input": "source", "output": output})
	rebuild()

func disconnect_nodes(from: StringName, _fp: int, to: StringName, _tp: int):
	var source_id = str(from)
	var target_id = str(to)
	# Removing an artifact-to-consumer wire removes the underlying formal edge.
	for key in artifact_nodes:
		if artifact_nodes[key].id == source_id:
			source_id = str(artifact_nodes[key].source)
			break
	edges = edges.filter(func(e): return not (e.from == source_id and e.to == target_id))
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
	parameter_form.configure("copy", {})
	refresh_history()
	rebuild()

func model() -> Dictionary:
	for data in nodes:
		_clear_image_mesh_text(data)
		_sync_node_files(data)
		if data.get("type", "copy") in ["text_to_image", "image_to_image"] and not data.has("version"): data.version = "4"
	return {"format": 1, "nodes": nodes, "edges": edges}

func _matching_output_entry(entry: Dictionary, reference: Dictionary) -> Dictionary:
	if entry.get("artifact", {}) == reference: return entry
	for collection in ["images", "iterations"]:
		for item in entry.get(collection, []):
			if item is Dictionary:
				var found = _matching_output_entry(item, reference)
				if not found.is_empty(): return found
	return {}

func _find_output_entry(source_id: String, reference: Dictionary) -> Dictionary:
	for entry in preview_history.get(source_id, []):
		if not entry is Dictionary: continue
		var found = _matching_output_entry(entry, reference)
		if not found.is_empty(): return found
	return {}

func execution_model() -> Dictionary:
	var executable = model().duplicate(true)
	for edge in executable.edges:
		if not edge.has("artifact"): continue
		var entry = _find_output_entry(str(edge.from), edge.artifact)
		if entry.is_empty():
			status.text = "所选 Mesh 轮次已不可用，请重新连接生成物"
			return {}
		var snapshot: Dictionary = entry.get("snapshot", {}).duplicate(true)
		if snapshot.is_empty(): snapshot = _snapshot_file(str(entry.get("path", "")))
		if snapshot.is_empty():
			status.text = "无法读取所选 Mesh 轮次，请重新预览后再运行"
			return {}
		snapshot["provenance"] = entry.get("provenance", {}).duplicate(true)
		edge["artifact_snapshot"] = snapshot
	return executable

func _snapshot_file(path: String) -> Dictionary:
	var input = FileAccess.open(path, FileAccess.READ)
	if input == null: return {}
	var bytes = input.get_buffer(input.get_length())
	var valid = not bytes.is_empty() and input.get_error() == OK
	input.close()
	if not valid: return {}
	var hash_context = HashingContext.new()
	if hash_context.start(HashingContext.HASH_SHA256) != OK or hash_context.update(bytes) != OK: return {}
	return {"content_base64": Marshalls.raw_to_base64(bytes), "content_sha256": hash_context.finish().hex_encode(), "extension": "." + path.get_extension().to_lower()}

func _snapshot_inputs(data: Dictionary, field: String) -> bool:
	var paths = _node_paths(data, field)
	var previous: Array = data.get(field + "_snapshots", []).duplicate()
	var snapshots: Array = []
	for index in range(paths.size()):
		var path: String = paths[index]
		var snapshot = previous[index] if index < previous.size() else data.get(field + "_snapshot", {}) if index == 0 else {}
		if not path.is_empty():
			var disk_snapshot = _snapshot_file(path)
			if not disk_snapshot.is_empty(): snapshot = disk_snapshot
		if not snapshot is Dictionary or snapshot.is_empty(): return false
		snapshots.append(snapshot)
	data[field + "_paths"] = paths
	data[field + "_snapshots"] = snapshots
	data[field] = str(paths[0]) if not paths.is_empty() else ""
	data.erase(field + "_snapshot")
	return true

func _snapshot_output_entry(entry: Dictionary, node_id: String) -> Dictionary:
	var snapshot = _snapshot_file(str(entry.get("path", "")))
	if snapshot.is_empty(): return {}
	var saved = {
		"type": str(entry.get("type", "")),
		"preview_token": str(entry.get("token", "")),
		"run": str(entry.get("run", "")),
		"node": node_id,
		"description": str(entry.get("description", "")),
		"artifact": {"id": str(entry.get("artifact", {}).get("id", "")), "revision": str(entry.get("artifact", {}).get("revision", ""))},
		"provenance": entry.get("provenance", {}).duplicate(true),
		"snapshot": snapshot
	}
	if entry.has("images"):
		if not entry.images is Array or entry.images.is_empty(): return {}
		var images: Array = []
		for item in entry.images:
			if not item is Dictionary or item.has("images"): return {}
			var saved_item = _snapshot_output_entry(item, node_id)
			if saved_item.is_empty(): return {}
			saved_item["label"] = str(item.get("label", "独立图片"))
			images.append(saved_item)
		saved["images"] = images
	if entry.has("iterations") and not entry.iterations.is_empty():
		if not entry.iterations is Array: return {}
		var iterations: Array = []
		for item in entry.iterations:
			if not item is Dictionary or item.has("iterations") or item.has("images"): return {}
			var saved_item = _snapshot_output_entry(item, node_id)
			if saved_item.is_empty(): return {}
			saved_item["label"] = str(item.get("label", "Mesh 轮次"))
			saved_item["attempt"] = int(item.get("attempt", iterations.size() + 1))
			saved_item["review_passed"] = item.get("review_passed", null)
			iterations.append(saved_item)
		saved["iterations"] = iterations
	return saved

func _result_artifact(manifest: Dictionary, reference: Dictionary) -> Dictionary:
	for artifact in manifest.get("artifacts", []):
		if artifact is Dictionary and artifact.get("id") == reference.get("id") and artifact.get("revision") == reference.get("revision"):
			return artifact
	return {}

func _result_mesh_iterations(manifest: Dictionary, reference: Dictionary) -> Array:
	var iterations: Array = []
	for artifact in manifest.get("artifacts", []):
		if not artifact is Dictionary or artifact.get("type", "") != "mesh": continue
		var provenance: Dictionary = artifact.get("payload", {}).get("provenance", {})
		if provenance.get("iteration_of", "") == reference.get("id", ""): iterations.append(artifact)
	iterations.sort_custom(func(left, right): return int(left.payload.provenance.get("generation_iteration", 0)) < int(right.payload.provenance.get("generation_iteration", 0)))
	return iterations

func _snapshot_result_artifact(result_run: String, node_id: String, reference: Dictionary, artifact: Dictionary) -> Dictionary:
	var payload = artifact.get("payload", {})
	if not payload is Dictionary: return {}
	var snapshot = {
		"content_base64": payload.get("content_base64", ""),
		"content_sha256": payload.get("content_sha256", ""),
		"extension": payload.get("extension", "")
	}
	if not _valid_input_snapshots([snapshot]): return {}
	var hash_context = HashingContext.new()
	if hash_context.start(HashingContext.HASH_SHA256) != OK: return {}
	if hash_context.update(JSON.stringify([result_run, reference, artifact], "", true, true).to_utf8_buffer()) != OK: return {}
	return {
		"type": str(artifact.get("type", "")),
		"preview_token": hash_context.finish().hex_encode(),
		"run": result_run,
		"node": node_id,
		"description": "",
		"artifact": {"id": str(reference.get("id", "")), "revision": str(reference.get("revision", ""))},
		"provenance": payload.get("provenance", {}).duplicate(true),
		"snapshot": snapshot
	}

func _snapshot_current_result(node_id: String, state: Dictionary) -> Dictionary:
	var job = state.get("job", {})
	var manifest = state.get("result", {})
	if not job is Dictionary or not manifest is Dictionary: return {}
	var outputs = job.get("outputs", {})
	if not outputs is Dictionary: return {}
	var references: Array = []
	var labels: Array = []
	var image_set = outputs.get("image_set", {})
	if not image_set.is_empty():
		if not image_set is Dictionary: return {}
		var collection = _result_artifact(manifest, image_set)
		var items = collection.get("payload", {}).get("items", [])
		if not items is Array or items.is_empty(): return {}
		for item in items:
			if not item is Dictionary or not item.get("artifact", {}) is Dictionary: return {}
			references.append(item.artifact)
			labels.append(str(item.get("label", "独立图片")))
	elif outputs.get("result", {}) is Dictionary and not outputs.get("result", {}).is_empty():
		references.append(outputs.result)
		labels.append("")
	else:
		return {}
	var images: Array = []
	for index in references.size():
		var artifact = _result_artifact(manifest, references[index])
		if artifact.is_empty(): return {}
		var saved = _snapshot_result_artifact(run_id, node_id, references[index], artifact)
		if saved.is_empty(): return {}
		saved["label"] = labels[index]
		images.append(saved)
	var primary: Dictionary = images[0].duplicate(true)
	primary.erase("label")
	primary["description"] = JSON.stringify(state.get("request", {}), "  ", true, true)
	if references.size() > 1 or not image_set.is_empty(): primary["images"] = images
	if primary.get("type", "") == "mesh":
		var iterations: Array = []
		for artifact in _result_mesh_iterations(manifest, outputs.result):
			var reference = {"id": str(artifact.id), "revision": str(artifact.revision)}
			var saved = _snapshot_result_artifact(run_id, node_id, reference, artifact)
			if saved.is_empty(): return {}
			var provenance: Dictionary = artifact.payload.provenance
			saved["label"] = "第 %d 轮" % int(provenance.get("generation_iteration", iterations.size() + 1))
			saved["attempt"] = int(provenance.get("generation_iteration", iterations.size() + 1))
			saved["review_passed"] = provenance.get("visual_review_passed", null)
			iterations.append(saved)
		if not iterations.is_empty(): primary["iterations"] = iterations
	return primary

func _snapshot_outputs():
	var saved: Dictionary = {}
	for node_id in preview_history:
		if not nodes.any(func(node): return node.id == node_id): continue
		var history: Array = []
		for entry in preview_history[node_id]:
			if not entry is Dictionary: return null
			var snapshot = _snapshot_output_entry(entry, str(node_id))
			if snapshot.is_empty(): return null
			history.append(snapshot)
		saved[node_id] = history
	for node_id in current.get("nodes", {}):
		var state = current.nodes[node_id]
		if not state is Dictionary or state.get("state") != "succeeded": continue
		var snapshot = _snapshot_current_result(str(node_id), state)
		if snapshot.is_empty(): return null
		var history: Array = saved.get(node_id, [])
		if not history.any(func(entry): return entry.preview_token == snapshot.preview_token): history.append(snapshot)
		saved[node_id] = history
	return saved

func _output_version_count(history: Dictionary) -> int:
	var count = 0
	for versions in history.values(): count += versions.size()
	return count

func _update_workflow_path_display():
	if workflow_path_display == null or path_edit == null: return
	workflow_path_display.text = path_edit.text
	workflow_path_display.tooltip_text = "当前工作流：" + path_edit.text
	workflow_path_display.caret_column = path_edit.text.length()

func _remember_workflow_path() -> bool:
	_update_workflow_path_display()
	var local = ConfigFile.new()
	local.load(state_dir.path_join("local.cfg"))
	local.set_value("workflow", "last_path", path_edit.text)
	return local.save(state_dir.path_join("local.cfg")) == OK

func save_graph():
	if not apply_fields(): return
	if path_edit.text.get_extension().to_lower() != "json":
		status.text = "工作流文件必须以 .json 结尾"
		return
	for n in nodes:
		for field in ["source", "image_context"]:
			for path in _node_paths(n, field):
				if not path.is_empty() and path.simplify_path() == path_edit.text.simplify_path():
					status.text = "不能覆盖输入资源"
					return
	var portable = model().duplicate(true)
	for n in portable.nodes:
		for field in ["source", "image_context"]:
			if not _snapshot_inputs(n, field):
				status.text = "无法读取输入并建立有序快照，已保留原工作流"
				return
	var output_history = _snapshot_outputs()
	if output_history == null:
		status.text = "无法读取全部生成物，已保留原工作流"
		return
	if not output_history.is_empty(): portable["output_history"] = output_history
	var temporary = path_edit.text + "." + str(Time.get_ticks_usec()) + ".tmp"
	var f = FileAccess.open(temporary, FileAccess.WRITE)
	if f == null:
		status.text = "无法保存工作流"
		return
	f.store_string(JSON.stringify(portable, "\t", true, true))
	f.flush()
	var failed = f.get_error() != OK
	f.close()
	if failed or DirAccess.rename_absolute(temporary, path_edit.text) != OK:
		DirAccess.remove_absolute(temporary)
		status.text = "无法替换工作流，已保留原工作流"
		return
	var remembered = _remember_workflow_path()
	status.text = "已保存工作流及全部有序输入快照"
	if not output_history.is_empty(): status.text += "，已内嵌 " + str(_output_version_count(output_history)) + " 个生成结果版本"
	status.text += "；文件：" + path_edit.text
	if not remembered: status.text += "（未能记录最近路径）"

func clear_embedded():
	for data in nodes:
		if data.id == selected_id:
			for field in ["source", "image_context"]:
				data.erase(field + "_snapshot")
				data.erase(field + "_snapshots")
	status.text = "已清除内嵌源文件和参考图像，路径字段仍然有效"

func _valid_input_snapshots(value, uncapped: bool = false) -> bool:
	if not value is Array or (not uncapped and value.size() > 8): return false
	for snapshot in value:
		if not snapshot is Dictionary: return false
		for key in ["content_base64", "content_sha256", "extension"]:
			if not snapshot.get(key) is String: return false
		if snapshot.extension.to_lower() not in [".png", ".jpg", ".jpeg", ".glb", ".gltf"]: return false
		var bytes = Marshalls.base64_to_raw(snapshot.content_base64)
		if bytes.is_empty(): return false
		var hash_context = HashingContext.new()
		if hash_context.start(HashingContext.HASH_SHA256) != OK: return false
		if hash_context.update(bytes) != OK or hash_context.finish().hex_encode() != snapshot.content_sha256: return false
	return true

func _valid_artifact_reference(value) -> bool:
	return value is Dictionary and value.get("id") is String and value.get("revision") is String and not value.id.is_empty() and not value.revision.is_empty()

func _valid_output_entry(entry, node_id: String) -> bool:
	if not entry is Dictionary or not entry.has_all(["type", "preview_token", "run", "node", "artifact", "snapshot"]): return false
	for key in ["type", "preview_token", "run", "node"]:
		if not entry.get(key) is String: return false
	if entry.has("description") and not entry.description is String: return false
	if entry.has("provenance") and not entry.provenance is Dictionary: return false
	if entry.node != node_id or entry.preview_token.is_empty() or not _valid_artifact_reference(entry.artifact): return false
	if not _valid_input_snapshots([entry.snapshot]): return false
	var image = entry.type == "image" and entry.snapshot.extension.to_lower() in [".png", ".jpg", ".jpeg"]
	var mesh = entry.type == "mesh" and entry.snapshot.extension.to_lower() in [".glb", ".gltf"]
	if not image and not mesh: return false
	if entry.has("images"):
		if not entry.images is Array or entry.images.is_empty(): return false
		for item in entry.images:
			if not item is Dictionary or item.has("images") or not item.get("label") is String or not _valid_output_entry(item, node_id): return false
	if entry.has("iterations"):
		if not mesh or not entry.iterations is Array or entry.iterations.is_empty(): return false
		for item in entry.iterations:
			if not item is Dictionary or item.has("images") or item.has("iterations") or not item.get("label") is String: return false
			if not (item.get("attempt", 0) is int or item.get("attempt", 0) is float) or int(item.attempt) < 1: return false
			if item.get("review_passed", null) != null and not item.review_passed is bool: return false
			if not _valid_output_entry(item, node_id): return false
	return true

func _valid_output_history(value, by_id: Dictionary) -> bool:
	if not value is Dictionary: return false
	for node_id in value:
		if not node_id is String or not by_id.has(node_id) or not value[node_id] is Array: return false
		for entry in value[node_id]:
			if not _valid_output_entry(entry, node_id): return false
	return true

func _output_history_has_artifact(history: Dictionary, source_id: String, reference: Dictionary) -> bool:
	for entry in history.get(source_id, []):
		if entry is Dictionary and not _matching_output_entry(entry, reference).is_empty(): return true
	return false

func _materialize_output_snapshot(snapshot: Dictionary, directory: String) -> String:
	var bytes = Marshalls.base64_to_raw(snapshot.content_base64)
	var path = directory.path_join(snapshot.content_sha256 + snapshot.extension.to_lower())
	if FileAccess.file_exists(path): return path if FileAccess.get_sha256(path) == snapshot.content_sha256 else ""
	var temporary = path + "." + str(Time.get_ticks_usec()) + ".tmp"
	var output = FileAccess.open(temporary, FileAccess.WRITE)
	if output == null: return ""
	output.store_buffer(bytes)
	output.flush()
	var failed = output.get_error() != OK
	output.close()
	if not failed and DirAccess.rename_absolute(temporary, path) == OK: return path
	DirAccess.remove_absolute(temporary)
	return path if FileAccess.file_exists(path) and FileAccess.get_sha256(path) == snapshot.content_sha256 else ""

func _restore_missing_input_paths(node_list: Array, workflow_path: String) -> int:
	var restored = 0
	var directory = workflow_path + ".assets/inputs"
	for data in node_list:
		for field in ["source", "image_context"]:
			var paths = _node_paths(data, field)
			var snapshots: Array = data.get(field + "_snapshots", [])
			for index in range(mini(paths.size(), snapshots.size())):
				if not str(paths[index]).is_empty(): continue
				if DirAccess.make_dir_recursive_absolute(directory) != OK: return -1
				var path = _materialize_output_snapshot(snapshots[index], directory)
				if path.is_empty(): return -1
				paths[index] = path
				restored += 1
			data[field + "_paths"] = paths
			data[field] = str(paths[0]) if not paths.is_empty() else ""
	return restored

func _restore_output_entry(saved: Dictionary, directory: String):
	var path = _materialize_output_snapshot(saved.snapshot, directory)
	if path.is_empty(): return null
	var entry = {
		"type": saved.type,
		"token": saved.preview_token,
		"run": saved.run,
		"node": saved.node,
		"description": saved.get("description", ""),
		"artifact": saved.artifact.duplicate(true),
		"provenance": saved.get("provenance", {}).duplicate(true),
		"path": path
	}
	if saved.has("images"):
		var images: Array = []
		for item in saved.images:
			var restored = _restore_output_entry(item, directory)
			if restored == null: return null
			restored["label"] = item.label
			images.append(restored)
		entry["images"] = images
	if saved.has("iterations"):
		var iterations: Array = []
		for item in saved.iterations:
			var restored = _restore_output_entry(item, directory)
			if restored == null: return null
			restored["label"] = item.label
			restored["attempt"] = int(item.attempt)
			restored["review_passed"] = item.get("review_passed", null)
			iterations.append(restored)
		entry["iterations"] = iterations
	return entry

func _restore_output_history(saved: Dictionary, workflow_path: String):
	if saved.is_empty(): return {}
	var directory = workflow_path + ".assets"
	if DirAccess.make_dir_recursive_absolute(directory) != OK: return null
	var restored: Dictionary = {}
	for node_id in saved:
		var history: Array = []
		for entry in saved[node_id]:
			var item = _restore_output_entry(entry, directory)
			if item == null: return null
			history.append(item)
		restored[node_id] = history
	return restored

func _valid_workflow_edge(edge: Dictionary, by_id: Dictionary) -> bool:
	if not edge.has_all(["from", "to"]) or not edge.from is String or not edge.to is String: return false
	if not by_id.has(edge.from) or not by_id.has(edge.to) or edge.from == edge.to: return false
	if not edge.get("input", "source") is String or not edge.get("output", "result") is String: return false
	if edge.get("input", "source") != "source": return false
	var target_kind = by_id[edge.to].get("type", "copy")
	if target_kind.begins_with("text_"): return false
	var output = edge.get("output", "result")
	if edge.has("artifact"):
		return (
			output == "result"
			and target_kind in ["copy", "model_adjust"]
			and output_kind(by_id[edge.from]) == PORT_MESH
			and _valid_artifact_reference(edge.artifact)
			and edge.artifact.size() == 2
			and (edge.get("iteration", 0) is int or edge.get("iteration", 0) is float)
			and int(edge.get("iteration", 0)) > 0
			and not edge.has("artifact_snapshot")
		)
	if output == "image_set":
		return _image_queue_node(by_id[edge.from]) and _accepts_image_set(by_id[edge.to])
	if _queue_only_node(by_id[edge.from]): return false
	return output == "result" and (target_kind == "copy" or (_accepts_image_set(by_id[edge.to]) and _accepts_single_image(by_id[edge.from], by_id[edge.to])) or (not _accepts_image_set(by_id[edge.to]) and output_kind(by_id[edge.from]) == input_kind(by_id[edge.to])))

func open_graph():
	_invalidate_context()
	if creating or auto_step or not jobs.is_empty():
		status.text = "请等待当前运行结束或先取消，再打开工作流"
		return
	var value = JSON.parse_string(FileAccess.get_file_as_string(path_edit.text))
	if not value is Dictionary or not safe(value) or value.get("format") != 1 or not value.get("nodes") is Array or not value.get("edges") is Array:
		status.text = "工作流无效"
		return
	var by_id: Dictionary = {}
	for n in value.nodes:
		if not n is Dictionary or not n.has_all(["id", "source", "image_context", "text", "parameters", "x", "y"]):
			status.text = "节点无效"
			return
		for key in ["id", "source", "image_context", "text"]:
			if not n[key] is String:
				status.text = "节点字段类型无效"
				return
		if n.id.is_empty() or not n.id.is_valid_identifier() or by_id.has(n.id) or not n.parameters is Dictionary or not (n.x is float or n.x is int) or not (n.y is float or n.y is int):
			status.text = "节点标识、参数或位置无效"
			return
		for key in ["type", "version", "provider", "model", "image_model"]:
			if n.has(key) and not n[key] is String:
				status.text = "节点定义字段无效"
				return
		if n.get("type", "copy") not in NODE_KINDS:
			status.text = "节点类型无效"
			return
		# Workflows saved before explicit node versions used the original batch
		# contract on their first multi-image save, never the queue-only contract.
		if n.get("type", "copy") in ["text_to_image", "image_to_image"] and not n.has("version"): n.version = "2"
		var reviewed_mesh = n.get("type", "") == "image_to_mesh" and n.get("version", "1") == "2"
		for field in ["source", "image_context"]:
			var paths = n.get(field + "_paths", [])
			if not paths is Array or (not reviewed_mesh and paths.size() > 8) or paths.any(func(path): return not path is String):
				status.text = "输入路径列表无效"
				return
			if n.has(field + "_snapshots") and not _valid_input_snapshots(n[field + "_snapshots"], reviewed_mesh):
				status.text = "输入快照列表无效"
				return
			if not paths.is_empty() and not n.get(field + "_snapshots", []).is_empty() and paths.size() != n[field + "_snapshots"].size():
				status.text = "输入路径与快照的数量不一致"
				return
			if n.has(field + "_snapshot") and not _valid_input_snapshots([n[field + "_snapshot"]]):
				status.text = "输入快照无效"
				return
		by_id[n.id] = n
	var destinations = []
	for e in value.edges:
		if not e is Dictionary or not _valid_workflow_edge(e, by_id) or e.to in destinations:
			status.text = "连接端点或端口无效"
			return
		destinations.append(e.to)
	var saved_outputs = value.get("output_history", {})
	if not _valid_output_history(saved_outputs, by_id):
		status.text = "生成物快照无效"
		return
	for edge in value.edges:
		if edge.has("artifact") and not _output_history_has_artifact(saved_outputs, str(edge.from), edge.artifact):
			status.text = "生成物连线引用的轮次不存在"
			return
	var recovered_inputs = _restore_missing_input_paths(value.nodes, path_edit.text)
	if recovered_inputs < 0:
		status.text = "无法从快照恢复输入文件，已保留当前工作流"
		return
	var restored_history = _restore_output_history(saved_outputs, path_edit.text)
	if restored_history == null:
		status.text = "无法恢复生成物，已保留当前工作流"
		return
	preview_history = restored_history
	artifact_preview_queue.clear()
	dismissed_artifacts.clear()
	controller.reset()
	clear_preview()
	nodes = value.nodes
	var legacy = service_draft()
	for data in nodes: _migrate_node_models(data, legacy)
	edges = value.edges
	selected_id = ""
	rebuild()
	if not nodes.is_empty(): select_node(nodes[0].id)
	var remembered = _remember_workflow_path()
	status.text = RETIRED_GPT_MESH_NOTICE if nodes.any(_retired_mesh_node) else "已重新打开工作流"
	if not saved_outputs.is_empty() and not nodes.any(_retired_mesh_node):
		status.text += "，已恢复 " + str(_output_version_count(saved_outputs)) + " 个生成结果版本，无需重新运行"
	elif not nodes.any(_retired_mesh_node):
		status.text += "；此文件没有内嵌生成结果，仅恢复节点和输入快照"
	if recovered_inputs > 0: status.text += "；已从快照恢复 " + str(recovered_inputs) + " 个输入文件路径"
	status.text += "；文件：" + path_edit.text
	if not remembered: status.text += "（未能记录最近路径）"

func _reject_missing_run_resources(target: String = "") -> bool:
	var pending: Array = nodes.map(func(node): return str(node.id)) if target.is_empty() else [target]
	var visited: Array = []
	var missing: Array = []
	while not pending.is_empty():
		var node_id = str(pending.pop_back())
		if node_id in visited: continue
		visited.append(node_id)
		for edge in edges:
			if edge.to == node_id and not edge.has("artifact"): pending.append(str(edge.from))
		for data in nodes:
			if data.id != node_id: continue
			var changed = false
			for field in ["source", "image_context"]:
				var paths = _node_paths(data, field)
				for index in paths.size():
					var path = str(paths[index])
					if path.is_empty() or FileAccess.file_exists(path): continue
					missing.append("节点 " + node_id + " · " + ("源文件" if field == "source" else "参考图像") + "：\n" + path)
					paths[index] = ""
					changed = true
				data[field + "_paths"] = paths
				data[field] = str(paths[0]) if not paths.is_empty() else ""
				if selected_id == node_id:
					var edit = source_edit if field == "source" else context_edit
					edit.text = " ; ".join(paths)
					edit.tooltip_text = edit.text
			if changed and selected_id == node_id: _sync_node_files(data)
	if missing.is_empty(): return false
	var message = "无法运行：以下输入路径的资源已不存在，对应路径已清空。请重新选择文件后再运行。\n\n" + "\n\n".join(missing)
	status.text = message
	if service_config_link != null: service_config_link.hide()
	_show_failure_dialog(message)
	return true

func run_node_preview(id: String):
	if is_graph_busy():
		status.text = "正在运行，请等待结果或先取消"
		return
	if id.is_empty() or nodes.filter(func(n): return n.id == id).is_empty(): return
	if not apply_fields(): return
	if _reject_missing_run_resources(id): return
	var blocker = node_run_blocker(id)
	if not blocker.is_empty():
		_show_run_problem(blocker)
		return
	if selected_id != id: select_node(id)
	if service_config_link != null: service_config_link.hide()
	preview_token = ""
	artifact_preview_queue.clear()
	status.text = "正在运行选中节点及必要的上游节点…"
	var executable = execution_model()
	if executable.is_empty(): return
	_configure_controller()
	controller.start(executable, id)

func start_run():
	if is_graph_busy() or not apply_fields(): return
	if _reject_missing_run_resources(): return
	for data in nodes:
		var blocker = node_run_blocker(data.id)
		if not blocker.is_empty():
			_show_run_problem(blocker)
			return
	if service_config_link != null: service_config_link.hide()
	preview_token = ""
	artifact_preview_queue.clear()
	var executable = execution_model()
	if executable.is_empty(): return
	_configure_controller()
	controller.start(executable)

func resume_run():
	_configure_controller()
	controller.resume()

func cancel_run():
	preview_token = ""
	artifact_preview_queue.clear()
	_configure_controller()
	controller.cancel()

func retry_node():
	if is_graph_busy(): return
	if not selected_id.is_empty() and _reject_missing_run_resources(selected_id): return
	if nodes.any(func(node): return node.id == selected_id and _retired_mesh_node(node)):
		status.text = RETIRED_GPT_MESH_NOTICE
		return
	preview_token = ""
	artifact_preview_queue.clear()
	_configure_controller()
	controller.retry(selected_id)

func _configure_controller():
	var configuration = {"python": python_edit.text.strip_edges(), "script": host_edit.text.strip_edges(), "database": db, "factory": factory_edit.text, "state_dir": state_dir, "use_service": _uses_gui_service(), "service_config": service_config_path}
	if bundled_runtime.has("python"):
		configuration.bundled_python = bundled_runtime.python
	if bundled_runtime.has("root"):
		configuration.bundled_root = bundled_runtime.root
	controller.configure(configuration)

func launch(command: String, spec: Dictionary):
	_configure_controller()
	controller.submit(command, spec)

func _queue_completed_image_previews(data: Dictionary):
	if data.get("state", "") != "succeeded": return
	for data_node in nodes:
		var kind = str(data_node.get("type", ""))
		if not _is_image_kind(kind) and not _is_mesh_kind(kind): continue
		var node_id = str(data_node.id)
		var state = data.get("nodes", {}).get(node_id, {})
		if state.get("state", "") != "succeeded" or artifact_preview_queue.has(node_id): continue
		var outputs = state.get("job", {}).get("outputs", {})
		if not outputs is Dictionary or (not outputs.has("image_set") and not outputs.has("result")): continue
		var already_loading = jobs.values().any(func(job): return job.command == "preview" and job.spec.get("node", "") == node_id)
		if not already_loading: artifact_preview_queue.append(node_id)

func _process(_delta):
	controller.tick()
	# Full-workflow runs also refresh every image artifact, not only a preview target.
	if not artifact_preview_queue.is_empty() and jobs.is_empty() and not creating and not auto_step and not run_id.is_empty():
		var node_id = str(artifact_preview_queue.pop_front())
		launch("preview", {"run": run_id, "node": node_id})

func _controller_failed(command: String, failure: Dictionary):
	var message = str(failure.message)
	var section = "ai"
	match failure.code:
		"runtime_unavailable", "runtime_rejected":
			message = "当前编辑器缺少统一 AI 运行时，请使用包含 AIWorkflowRuntime 的完整构建。"
			section = "environment"
		"runtime_path_empty":
			message = "运行环境为空。请在环境设置中选择马良使用的 Python 3.11 或更高版本。" if str(failure.diagnostic.get("python", "")).is_empty() else "运行工具路径为空。请在环境设置中恢复马良内置工具路径。"
			section = "environment"
		"request_write_failed":
			message = "无法写入本机运行请求，请检查用户目录是否可写。"
		"process_start_failed":
			message = "无法启动本机运行环境，请检查马良 Python 的位置与执行权限。"
			section = "environment"
	if message.is_empty():
		message = "本机运行环境未返回有效结果。请确认 Python 3.11 或更高版本可用，并检查本机设置。"
	message = diagnostic_error("操作失败：" + message, failure.diagnostic)
	_show_run_problem(message, section)
	if command == "service-check": service_status.text = message
	if command == "managed-comfy": managed_comfy_panel.failed(message)

func _capability_limited_artifact(node_state: Dictionary) -> Dictionary:
	if node_state.get("state") != "succeeded": return {}
	var manifest = node_state.get("result", {})
	if not manifest is Dictionary: return {}
	for artifact in manifest.get("artifacts", []):
		if not artifact is Dictionary or artifact.get("type") != "mesh": continue
		var payload = artifact.get("payload", {})
		if not payload is Dictionary: continue
		var provenance = payload.get("provenance", {})
		if provenance is Dictionary and provenance.get("capability_limited", false): return artifact
	return {}

func _capability_issue_summaries(issues: Array) -> PackedStringArray:
	var summaries := PackedStringArray()
	for issue in issues:
		var value = str(issue).to_lower()
		var summary = ""
		if ["face","facial","skin","eye","nose","ear","brow","jaw","cheek","identity","面部","皮肤","眼睛"].any(func(term): return term in value):
			summary = "面部身份、比例或肤质细节仍与参考图存在差异。"
		elif ["proportion","anatomy","limb","比例","肢体"].any(func(term): return term in value):
			summary = "整体或局部比例、解剖结构仍需人工检查。"
		elif ["hair","头发","发型"].any(func(term): return term in value):
			summary = "发型、头发体积或发丝细节仍与参考图存在差异。"
		elif ["gem","宝石"].any(func(term): return term in value):
			summary = "宝石或装饰镶嵌的颜色、形状及完整性仍需检查。"
		elif ["glove","手套"].any(func(term): return term in value):
			summary = "手套、腕部或手部细节未完整符合参考图。"
		elif ["boot","shoe","靴","鞋"].any(func(term): return term in value):
			summary = "靴鞋的结构、材质或装饰细节仍需检查。"
		elif ["gold","metal","filigree","ornament","embroider","金属","纹饰","刺绣"].any(func(term): return term in value):
			summary = "金属、刺绣或浮雕细节存在软化、缺失或变形。"
		elif ["cloth","fabric","navy","ivory","color","leather","cloak","tabard","服装","布料","配色","材质"].any(func(term): return term in value):
			summary = "服装配色、布料或材质质感仍与参考图存在差异。"
		elif ["camera","view","视角","相机"].any(func(term): return term in value):
			summary = "部分视图与参考图的对应关系仍需人工检查。"
		else:
			summary = "仍有其他模型质量或结构问题，请查看任务中的完整审核记录。"
		if not summaries.has(summary): summaries.append(summary)
	if summaries.is_empty(): summaries.append("存在未解决问题，请查看任务中的完整审核记录。")
	return summaries

func _capability_notice_text(artifact: Dictionary) -> String:
	var provenance: Dictionary = artifact.get("payload", {}).get("provenance", {})
	var lines := PackedStringArray()
	lines.append("模型已保留并按成功结果交付，但视觉审核未完全通过。")
	lines.append("这是能力受限交付，不代表完整审核通过。模型校验值：" + str(artifact.get("revision", "")))
	var issues = provenance.get("unresolved_issues", [])
	if issues is Array and not issues.is_empty():
		lines.append("未解决问题的中文摘要（原始审核意见已完整保留在任务记录中）：")
		for summary in _capability_issue_summaries(issues): lines.append("• " + summary)
	return "\n".join(lines)

func _show_capability_notice(node_id: String, artifact: Dictionary):
	var key = run_id + "/" + node_id + "/" + str(artifact.get("revision", ""))
	if capability_notices.has(key): return
	capability_notices[key] = true
	capability_notice_dialog.dialog_text = _capability_notice_text(artifact)
	capability_notice_dialog.popup_centered(Vector2i(760, 480))

func _node_failure_text(node_id: String, state: Dictionary) -> String:
	var reason_value = state.get("public_error")
	var has_public_reason = reason_value != null and not str(reason_value).is_empty()
	if not has_public_reason: reason_value = state.get("error")
	var reason = str(reason_value) if reason_value != null else "未知错误"
	var node_job = state.get("job", {})
	if not has_public_reason and node_job is Dictionary and not str(node_job.get("error", "")).is_empty():
		reason = str(node_job.error)
	if reason == "invalid_result":
		reason = "生成结果未通过校验，已停止；请保留本次记录，修正问题后重新运行节点。"
	return "节点 " + node_id + " 执行失败。\n原因：" + reason + "\n运行 ID：" + run_id

func _controller_completed(command: String, data: Dictionary, request: Dictionary):
	if command == "managed-comfy":
		managed_comfy_panel.completed(data, request)
	elif command == "service-check":
		_apply_service_check(data, request.service)
	elif command == "preview":
		if request.run == run_id:
			remember_preview(data, request.node, request.run)
			if request.node == selected_id: load_preview(data, request.node, request.run)
	elif command == "publish":
		status.text = "已发布新文件：" + data.path
		if Engine.is_editor_hint(): EditorInterface.get_resource_filesystem().scan()
	elif command != "create":
		status.text = "运行状态：" + state_label(data.state) + " | 响应计数 " + str(heartbeat)
		var failure_messages := PackedStringArray()
		for id in data.nodes:
			var node_state: Dictionary = data.nodes[id]
			status.text += " | " + id + "：" + state_label(node_state.state) + "，尝试次数 " + str(node_state.attempt)
			var limited = _capability_limited_artifact(node_state)
			if not limited.is_empty():
				status.text += "（能力受限交付：审核未完全通过，详见弹窗）"
				_show_capability_notice(id, limited)
			if node_state.state == "failed" and node_state.get("error") == "invalid_result":
				status.text += "（生成结果未通过校验，已停止；请保留本次记录，修正问题后重新运行节点）"
			if node_state.state == "failed":
				var failure_message = _node_failure_text(id, node_state)
				var failure_key = run_id + "/" + id + "/" + str(node_state.get("attempt", 0)) + "/" + failure_message
				if not failure_notices.has(failure_key):
					failure_notices[failure_key] = true
					failure_messages.append(failure_message)
			if node_state.state == "failed" and managed_comfy_panel.using_bundle() and _service_mode() in ["codex", "local_mesh"]:
				var job_result = node_state.get("job")
				var details = {"run": run_id, "node": id, "error": node_state.get("error"), "job_error": job_result.get("error") if job_result is Dictionary else null, "model_log": managed_comfy_panel.last_report.get("log_path", "")}
				status.text = diagnostic_error(status.text, details)
		if data.state == "reconcile": status.text += " | 提交结果未知，已暂停。点击“继续运行”查询一次结果，避免重复提交。"
		if not failure_messages.is_empty():
			_show_run_problem("生成任务失败，可复制以下报错：\n\n" + "\n\n".join(failure_messages))
		if command in ["step", "status"]: _queue_completed_image_previews(data)

func request_preview():
	if creating:
		status.text = "正在创建运行，请稍候"
		return
	if run_id.is_empty() or selected_id.is_empty():
		status.text = "请先点击节点的“运行并预览”"
		return
	if controller.has_command("preview"): return
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
		entry["description"] = JSON.stringify(current.get("nodes", {}).get(node_id, {}).get("request", {}), "  ", true, true)
		history.append(entry)
		preview_history[node_id] = history
	if node_id == selected_id: refresh_history()
	# An explicit new run restores previously dismissed result nodes.
	for key in dismissed_artifacts.keys():
		if key == node_id or str(key).begins_with(node_id + "::"): dismissed_artifacts.erase(key)
	if data.get("type", "") in ["image", "mesh"] or artifact_nodes.has(node_id): rebuild()

func show_history(index: int):
	var history: Array = preview_history.get(selected_id, [])
	if index < 0 or index >= history.size(): return
	var entry: Dictionary = history[index]
	load_preview(entry, selected_id, entry.run)
	history_choice.select(index)
	status.text += " · 版本 " + str(index + 1)

func _displayed_preview() -> Control:
	if preview_resource != null: return texture
	if is_instance_valid(preview_scene): return mesh_container
	return null

func _update_preview_maximize_controls():
	if not is_instance_valid(preview_maximize_button): return
	preview_maximize_button.disabled = _displayed_preview() == null
	preview_maximize_button.text = "还原预览" if preview_maximized else "最大化预览"
	preview_maximize_button.tooltip_text = "还原到工作台" if preview_maximized else "打开最大化预览；也可以双击图片或网格"

func toggle_preview_maximized():
	if preview_maximized: restore_preview()
	else: maximize_preview()

func maximize_preview():
	if preview_maximized: return
	var displayed = _displayed_preview()
	if displayed == null: return
	preview_inline_parent = displayed.get_parent() as Control
	preview_inline_index = displayed.get_index()
	preview_inline_minimum_size = displayed.custom_minimum_size
	preview_inline_size_flags_horizontal = displayed.size_flags_horizontal
	preview_inline_size_flags_vertical = displayed.size_flags_vertical
	displayed.reparent(preview_window_host)
	displayed.custom_minimum_size = Vector2.ZERO
	displayed.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	displayed.size_flags_vertical = Control.SIZE_EXPAND_FILL
	preview_maximized = true
	preview_window.popup()
	preview_window.mode = Window.MODE_MAXIMIZED
	_update_preview_maximize_controls()

func restore_preview():
	if not preview_maximized: return
	var displayed = _displayed_preview()
	preview_maximized = false
	preview_window.hide()
	preview_window.mode = Window.MODE_WINDOWED
	if displayed != null and is_instance_valid(preview_inline_parent):
		displayed.reparent(preview_inline_parent)
		preview_inline_parent.move_child(displayed, mini(preview_inline_index, preview_inline_parent.get_child_count() - 1))
		displayed.custom_minimum_size = preview_inline_minimum_size
		displayed.size_flags_horizontal = preview_inline_size_flags_horizontal
		displayed.size_flags_vertical = preview_inline_size_flags_vertical
	preview_inline_parent = null
	preview_inline_index = -1
	_update_preview_maximize_controls()

func _image_preview_input(event: InputEvent):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and event.double_click:
		toggle_preview_maximized()
		texture.accept_event()

func clear_preview():
	restore_preview()
	preview_token = ""
	preview_run = ""
	preview_node = ""
	preview_source_path = ""
	preview_resource = null
	preview_artifact = {}
	current_images = []
	result_choice.clear()
	result_choice.hide()
	if is_instance_valid(preview_scene): preview_scene.queue_free()
	preview_scene = null
	texture.texture = null
	texture.hide()
	mesh_container.hide()
	_update_preview_maximize_controls()

func show_result(index: int):
	if index < 0 or index >= current_images.size(): return
	var entry: Dictionary = current_images[index]
	result_choice.select(index)
	load_preview(entry, preview_node, preview_run, true)

func load_preview(data: Dictionary, node_id: String, result_run: String = "", preserve_set: bool = false):
	if not preserve_set:
		clear_preview()
		current_images = data.get("images", []).duplicate(true)
		preview_run = run_id if result_run.is_empty() else result_run
		preview_node = node_id
		for index in current_images.size():
			var item: Dictionary = current_images[index]
			result_choice.add_item("%d. %s" % [index + 1, str(item.get("label", "独立图片"))])
		result_choice.visible = current_images.size() > 1
		if not current_images.is_empty():
			show_result(0)
			return
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
	preview_source_path = str(data.path)
	# Keep the exact result or iteration identity for save confirmation and publishing.
	preview_artifact = data.get("artifact", {}).duplicate(true)
	preview_run = run_id if result_run.is_empty() else result_run
	preview_node = node_id
	status.text = "已加载" + {"image":"图像", "mesh":"网格"}.get(data.type,data.type) + "预览，请检查后再发布"
	if not current_images.is_empty(): status.text += "；当前为“" + str(data.get("label", "独立图片")) + "”，共 " + str(current_images.size()) + " 张"
	_update_preview_maximize_controls()

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
		mesh_focus = center
		mesh_frame_distance = distance
		camera.position = center + Vector3(0.5, 0.3, 1).normalized() * distance
		camera.near = maxf(radius / 1000, 0.001)
		camera.far = radius * 20
		camera.look_at(center)

func _mesh_preview_input(event: InputEvent):
	if not is_instance_valid(preview_scene) or preview_node.is_empty(): return
	var camera := preview_root.get_child(0) as Camera3D
	var offset := camera.position - mesh_focus
	var distance := offset.length()
	if distance <= 0.0: return
	if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_LEFT:
		var azimuth: float = atan2(offset.x, offset.z) - event.relative.x * 0.009
		var elevation := clampf(asin(clampf(offset.y / distance, -1.0, 1.0)) + event.relative.y * 0.009, -1.5, 1.5)
		offset = Vector3(sin(azimuth) * cos(elevation), sin(elevation), cos(azimuth) * cos(elevation)) * distance
	elif event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_MIDDLE:
		var pixel_scale := 2.0 * distance * tan(deg_to_rad(camera.fov * 0.5)) / maxf(mesh_container.size.y, 1.0)
		mesh_focus += (camera.basis.y * event.relative.y - camera.basis.x * event.relative.x) * pixel_scale
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT and event.double_click:
			frame_mesh()
			toggle_preview_maximized()
			mesh_container.accept_event()
			return
		if event.button_index not in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]: return
		var direction := -1.0 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0
		var zoom := pow(1.18, direction * maxf(event.factor, 0.1))
		offset = offset.normalized() * clampf(distance * zoom, mesh_frame_distance * 0.1, mesh_frame_distance * 3.0)
	else:
		return
	camera.position = mesh_focus + offset
	camera.look_at(mesh_focus)
	mesh_container.accept_event()

func set_owners(node: Node, root: Node):
	for child in node.get_children():
		child.owner = root
		set_owners(child, root)

func open_save_dialog():
	if preview_source_path.is_empty() or not FileAccess.file_exists(preview_source_path):
		status.text = "请先预览要保存的图像或网格"
		return
	var extension = preview_source_path.get_extension().to_lower()
	if extension.is_empty(): extension = "png" if preview_resource != null else "glb"
	save_picker.filters = ["*." + extension + " ; " + ("图像" if preview_resource != null else "网格") + "生成物"]
	save_picker.current_dir = preview_source_path.get_base_dir()
	save_picker.current_file = preview_source_path.get_file()
	save_picker.popup_centered_ratio(0.7)

func save_preview_to(path: String):
	if preview_source_path.is_empty() or not FileAccess.file_exists(preview_source_path):
		status.text = "生成物源文件已不可用，请重新预览后再保存"
		return
	var target = path
	if target.get_extension().is_empty(): target += "." + preview_source_path.get_extension().to_lower()
	var err = DirAccess.copy_absolute(preview_source_path, target)
	if err != OK:
		status.text = "保存生成物失败：" + error_string(err)
		return
	status.text = "已保存生成物：" + target

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
	if not preview_artifact.is_empty(): confirmation.artifact = preview_artifact.duplicate(true)
	dialog.dialog_text = "将当前预览发布为新文件？\n运行编号：" + preview_run + "\n预览版本：" + preview_token + "\n资源 SHA256：" + confirmation.staged_sha256 + "\n" + target_edit.text
	dialog.popup_centered()

func confirm_publish():
	if confirmation.get("run") != run_id or confirmation.get("confirmation") != preview_token:
		status.text = "预览已变化，请重新确认"
		return
	launch("publish", confirmation.duplicate())
	confirmation = {}

func _exit_tree():
	if is_instance_valid(managed_comfy_panel): managed_comfy_panel.release_connection()
	controller.shutdown()

func is_graph_busy() -> bool:
	return controller.is_busy()

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
		if child is GraphNode and child.selected and not child.get_meta("maliang_artifact", false): ids.append(str(child.name))
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
	context_model = JSON.stringify(model(), "", true, true)
	context_run = run_id
	context_selection = _graph_selected_ids()
	context_inspected_id = selected_id

func _context_is_current() -> bool:
	if context_model.is_empty() or context_model != JSON.stringify(model(), "", true, true) or context_run != run_id or context_inspected_id != selected_id or context_selection != _graph_selected_ids():
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
		_clear_image_mesh_text(data)
		var kind: String = data.get("type", "copy")
		if _retired_mesh_node(data): return RETIRED_GPT_MESH_NOTICE
		var incoming = edges.filter(func(edge): return edge.to == next_id)
		for edge in incoming:
			if not edge.has("artifact"): pending.append(edge.from)
		var has_images = not incoming.is_empty() or not _node_paths(data, "source").is_empty() or not _node_paths(data, "image_context").is_empty()
		if kind != GENERATE_IMAGE and not kind.begins_with("text_") and incoming.is_empty() and _node_paths(data, "source").is_empty():
			return "请先设置源文件或连接上游节点（" + str(next_id) + "）"
		for field in ["source", "image_context"]:
			for path in _node_paths(data, field):
				if not path.is_empty() and not FileAccess.file_exists(path):
					return ("源文件" if field == "source" else "参考图像") + "不存在（" + str(next_id) + "）"
		var reviewed_mesh = kind == "image_to_mesh" and data.get("version", "1") == "2"
		if not reviewed_mesh and (_is_image_kind(kind) or _accepts_image_set(data)) and _node_paths(data, "source").size() + _node_paths(data, "image_context").size() > 8:
			return "源图与参考图合计每次最多 8 张（" + str(next_id) + "）"
		var prompt = str(data.get("parameters", {}).get("prompt", "")) + "\n" + str(data.get("text", ""))
		if kind == GENERATE_IMAGE and not has_images and prompt.strip_edges().is_empty():
			return "请至少选择图片或填写生成提示词（" + str(next_id) + "）"
		if kind != GENERATE_IMAGE and not kind in ["copy", "image_to_mesh", "model_adjust"] and prompt.strip_edges().is_empty():
			return "请先填写生成提示词（" + str(next_id) + "）"
		var service_reason = _service_blocker(kind, data)
		if not service_reason.is_empty(): return service_reason
	return ""

func _retry_blocker(id: String) -> String:
	if is_graph_busy(): return "正在运行，请等待结束或先取消"
	if nodes.any(func(node): return node.id == id and _retired_mesh_node(node)): return RETIRED_GPT_MESH_NOTICE
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
	context_artifact_source = ""
	var hit = _node_at_context(local_position)
	if not hit.is_empty():
		var hit_node = graph.get_node(NodePath(hit)) as GraphNode
		if hit_node.get_meta("maliang_artifact", false):
			context_artifact_source = str(hit_node.get_meta("artifact_key", hit_node.get_meta("artifact_source", "")))
			_show_artifact_result(context_artifact_source)
			_remember_context()
			context_menu.clear()
			context_history_menu.clear()
			var mesh_artifact = artifact_nodes.has(context_artifact_source) and artifact_nodes[context_artifact_source].get("kind", "image") == "mesh"
			_context_item("保存本轮 GLB…" if mesh_artifact else "下载全部到项目…", CONTEXT_ARTIFACT_DOWNLOAD)
			_context_item("删除生成物节点", CONTEXT_ARTIFACT_DELETE, "请等待当前运行结束或先取消" if is_graph_busy() else "")
			context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
			context_menu.popup(Rect2i(Vector2i(graph.get_screen_transform() * local_position), Vector2i.ZERO))
			return
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
		var context_kind = str(nodes.filter(func(n): return n.id == id)[0].get("type", "copy"))
		_context_item("编辑参数" if context_kind == "image_to_mesh" else "编辑提示词与参数", CONTEXT_EDIT)
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
				if parameter_form.prompt_edit.is_visible_in_tree(): parameter_form.prompt_edit.grab_focus()
				elif text_edit.is_visible_in_tree(): text_edit.grab_focus()
				else: parameter_form.advanced_toggle.grab_focus()
				status.text = "在右侧编辑参数，完成后右键选择“运行并预览”"
		CONTEXT_RETRY:
			if context_node_ids.size() == 1:
				var reason = _retry_blocker(context_node_ids[0])
				if not reason.is_empty(): status.text = reason; return
				preview_target = context_node_ids[0]
				retry_node()
		CONTEXT_DUPLICATE: duplicate_context_nodes()
		CONTEXT_DELETE: delete_context_nodes()
		CONTEXT_ARTIFACT_DOWNLOAD:
			if not context_artifact_source.is_empty(): _open_artifact_download(context_artifact_source)
		CONTEXT_ARTIFACT_DELETE:
			if not context_artifact_source.is_empty(): _delete_artifact_node(context_artifact_source)
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
	for group in [["图像生成", [GENERATE_IMAGE]], ["网格生成", ["image_to_mesh", "text_to_mesh"]], ["模型处理", ["model_adjust"]], ["离线工具", ["copy"]]]:
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
	var data = {"id": id, "type": kind, "version": _new_node_version(kind), "provider": "local-copy" if kind == "copy" else _generator_provider(kind), "source": "", "image_context": "", "text": "", "parameters": {"delay": 2, "fail": false} if kind == "copy" else {"prompt": "" if kind in ["image_to_mesh", "model_adjust"] else "白色背景上的小型石雕", "seed": 1}, "x": position.x, "y": position.y}
	if kind != 'copy' and _service_mode() in ['api_modeling', 'api_sculpt']: data.model = ''
	_migrate_node_models(data, service_draft())
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
		parameter_form.configure("copy", {})
		refresh_history()
	rebuild()
	status.text = "已删除 " + str(removed.size()) + " 个节点及关联连接"

func _keyboard_duplicate():
	context_node_ids = _graph_selected_ids()
	context_connection = {}
	_remember_context()
	duplicate_context_nodes()

func _keyboard_delete(ids: Array):
	if is_graph_busy():
		status.text = "请等待当前运行结束或先取消，再删除节点"
		return
	context_node_ids = []
	var artifact_sources: Array = []
	for id in ids:
		var node = graph.get_node_or_null(NodePath(str(id)))
		if node != null and node.get_meta("maliang_artifact", false):
			var key = str(node.get_meta("artifact_key", node.get_meta("artifact_source", "")))
			artifact_sources.append(key)
			_mark_artifact_deleted(key)
			continue
		context_node_ids.append(str(id))
	if context_node_ids.is_empty():
		if not artifact_sources.is_empty():
			rebuild()
			status.text = "已删除动态生成物节点；正式节点、生成历史和生成物文件均保留"
		return
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

func _open_workflow_path(selected_path: String):
	if is_graph_busy():
		status.text = "请等待当前运行结束或先取消，再打开工作流"
		_update_workflow_path_display()
		return
	path_edit.text = selected_path.strip_edges()
	_update_workflow_path_display()
	open_graph()

func _workflow_action(action: int):
	if action == CONTEXT_OPEN and is_graph_busy():
		status.text = "请等待运行结束或先取消，再打开工作流"
		return
	workflow_mode = "save" if action == CONTEXT_SAVE else "open"
	workflow_dialog.title = "保存工作流" if workflow_mode == "save" else "打开工作流"
	workflow_dialog.ok_button_text = "保存" if workflow_mode == "save" else "打开"
	workflow_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE if workflow_mode == "save" else FileDialog.FILE_MODE_OPEN_FILE
	workflow_dialog.current_path = path_edit.text
	workflow_dialog.popup_centered_ratio(0.75)

func _workflow_confirmed(selected_path: String = ""):
	if not selected_path.is_empty():
		if workflow_mode == "save" and selected_path.get_extension().is_empty(): selected_path += ".json"
		path_edit.text = selected_path
		_update_workflow_path_display()
	if workflow_mode == "save": save_graph()
	elif workflow_mode == "open": open_graph()

func _default_python_path(builtin: bool) -> String:
	if bundled_runtime.has('python'): return bundled_runtime.python
	if OS.get_name() == "Windows": return "python"
	if builtin and OS.get_name() == "macOS":
		var home = OS.get_environment("HOME")
		for candidate in [home.path_join(".local/bin/python3.12"), "/opt/homebrew/bin/python3.13", "/opt/homebrew/bin/python3.12", "/usr/local/bin/python3.12"]:
			if FileAccess.file_exists(candidate): return candidate
	return "python3"

func _setup_service_controls(machine: VBoxContainer, settings: ConfigFile):
	service_config_path = state_dir.path_join("generation-service.json")
	service_profiles_path = state_dir.path_join("generation-service-profiles.json")
	service_fields = VBoxContainer.new()
	machine.add_child(service_fields)
	var title = Label.new()
	title.text = "生成服务"
	service_fields.add_child(title)
	service_choice = OptionButton.new()
	service_choice.fit_to_longest_item = false
	service_choice.clip_text = true
	service_choice.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	for choice in [["comfy", "ComfyUI 图像与网格生成"], ["legacy", "兼容已有服务配置（高级）"], ['codex', 'Codex CLI 图像 + 本机网格（沿用当前登录额度）'], ['kimi_native', 'Kimi Native 直接 3D（Tripo API）+ Kimi Work 二维图像'], ['local_mesh', '本机图生网格（无需 CLI）'], ['api_modeling', '自选 API 语义建模（Godot）'], ['api_sculpt', '自选 API 语义建模（Blender）']]:
		service_choice.add_item(choice[1])
		service_choice.set_item_metadata(service_choice.item_count - 1, choice[0])
	service_fields.add_child(service_choice)
	cli_fields = VBoxContainer.new()
	service_fields.add_child(cli_fields)
	var cli_label = Label.new()
	cli_label.text = '马良 Codex CLI（保留独立任务服务快照）'
	cli_fields.add_child(cli_label)
	cli_path_edit = line(cli_fields, '马良 Codex CLI 程序', str(settings.get_value('service', 'cli_path', 'codex')))
	var cli_picker = FileDialog.new()
	cli_picker.title = '选择已登录的 Codex CLI'
	cli_picker.access = FileDialog.ACCESS_FILESYSTEM
	cli_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	cli_picker.file_selected.connect(func(path): cli_path_edit.text = path)
	cli_fields.add_child(cli_picker)
	button(cli_fields, '选择 Codex CLI…', func(): cli_picker.popup_centered_ratio(0.7))
	blender_fields = VBoxContainer.new()
	blender_fields.name = 'BlenderModelingEnvironment'
	cli_fields.add_child(blender_fields)
	var blender_default = OS.get_environment('BLENDER_EXECUTABLE') if OS.has_environment('BLENDER_EXECUTABLE') else str(settings.get_value('service', 'blender_path', 'blender'))
	blender_path_edit = line(blender_fields, 'Blender 可执行文件', blender_default)
	var blender_picker = FileDialog.new()
	blender_picker.title = '选择本机 Blender'
	blender_picker.access = FileDialog.ACCESS_FILESYSTEM
	blender_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	blender_picker.file_selected.connect(func(path): blender_path_edit.text = path)
	blender_fields.add_child(blender_picker)
	button(blender_fields, '选择 Blender…', func(): blender_picker.popup_centered_ratio(0.7))
	blender_path_edit.text_changed.connect(func(_text): _service_settings_changed())
	button(cli_fields, '保存 CLI 与生成服务设置', save_service_settings)
	var billing = Label.new()
	cli_billing = billing
	billing.text = '复用 Codex CLI 当前的 ChatGPT 登录；图像生成与编辑计入同一 Codex 额度。网格由本机模型执行。'
	billing.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cli_fields.add_child(billing)
	cli_path_edit.text_changed.connect(func(_text): _service_settings_changed())
	endpoint_edit = line(service_fields, "生成服务地址，如 http://127.0.0.1:8188", "http://127.0.0.1:8188")
	kimi_model_label = Label.new()
	kimi_model_label.text = 'Kimi 模型 ID'
	service_fields.add_child(kimi_model_label)
	kimi_model_edit = line(service_fields, 'Kimi 模型，例如 k3.1-pro', 'k3.1-pro')
	kimi_auth_label = Label.new()
	kimi_auth_label.text = 'Mesh：Kimi Work 通过 Tripo API 直接生成 GLB，无需 Blender 或 K3 原语规划。二维：独立 Kimi Work 图像服务。凭据由 agent-gw SDK 管理，不写入工作流或日志。'
	kimi_auth_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service_fields.add_child(kimi_auth_label)
	kimi_model3d_fields = VBoxContainer.new()
	kimi_model3d_fields.name = 'KimiWorkModel3DSettings'
	service_fields.add_child(kimi_model3d_fields)
	var model3d_label = Label.new()
	model3d_label.text = 'Tripo API 直接三维（generate_3d_model）'
	kimi_model3d_fields.add_child(model3d_label)
	var model3d_tool_default = OS.get_environment('KIMI_WORK_MODEL3D_TOOL') if OS.has_environment('KIMI_WORK_MODEL3D_TOOL') else str(settings.get_value('service', 'model3d_tool_path', ''))
	var model3d_pythonw_default = OS.get_environment('KIMI_WORK_MODEL3D_PYTHONW') if OS.has_environment('KIMI_WORK_MODEL3D_PYTHONW') else str(settings.get_value('service', 'model3d_pythonw_path', ''))
	model3d_tool_edit = line(kimi_model3d_fields, 'Kimi Work 3D 工具 model3d_generation_tool.py', model3d_tool_default)
	model3d_pythonw_edit = line(kimi_model3d_fields, '3D 插件已验证的 pythonw.exe（macOS／Linux 为 Python 3）', model3d_pythonw_default)
	var model3d_tool_picker = FileDialog.new()
	model3d_tool_picker.title = '选择 Kimi Work 3D 工具'
	model3d_tool_picker.access = FileDialog.ACCESS_FILESYSTEM
	model3d_tool_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	model3d_tool_picker.use_native_dialog = true
	model3d_tool_picker.filters = PackedStringArray(['model3d_generation_tool.py'])
	model3d_tool_picker.file_selected.connect(func(path): model3d_tool_edit.text = path; _service_settings_changed())
	kimi_model3d_fields.add_child(model3d_tool_picker)
	button(kimi_model3d_fields, '选择 3D 工具…', func(): model3d_tool_picker.popup_centered_ratio(0.7))
	var model3d_pythonw_picker = FileDialog.new()
	model3d_pythonw_picker.title = '选择 3D 插件已验证的运行时'
	model3d_pythonw_picker.access = FileDialog.ACCESS_FILESYSTEM
	model3d_pythonw_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	model3d_pythonw_picker.use_native_dialog = true
	model3d_pythonw_picker.filters = PackedStringArray(['pythonw.exe', 'python3', 'python'])
	model3d_pythonw_picker.file_selected.connect(func(path): model3d_pythonw_edit.text = path; _service_settings_changed())
	kimi_model3d_fields.add_child(model3d_pythonw_picker)
	button(kimi_model3d_fields, '选择 3D 运行时…', func(): model3d_pythonw_picker.popup_centered_ratio(0.7))
	var model3d_hint = Label.new()
	model3d_hint.text = '直接生成 GLB，支持文字、单图与 2–4 视图；三视图整图按正面／右侧／背面裁切。工具路径仅保存在本机设置。'
	model3d_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	kimi_model3d_fields.add_child(model3d_hint)
	model3d_tool_edit.text_changed.connect(func(_text): _service_settings_changed())
	model3d_pythonw_edit.text_changed.connect(func(_text): _service_settings_changed())
	kimi_image_fields = VBoxContainer.new()
	kimi_image_fields.name = 'KimiWorkImageSettings'
	service_fields.add_child(kimi_image_fields)
	var image_tool_default = OS.get_environment('KIMI_WORK_IMAGE_TOOL') if OS.has_environment('KIMI_WORK_IMAGE_TOOL') else str(settings.get_value('service', 'image_tool_path', ''))
	var image_pythonw_default = OS.get_environment('KIMI_WORK_IMAGE_PYTHONW') if OS.has_environment('KIMI_WORK_IMAGE_PYTHONW') else str(settings.get_value('service', 'image_pythonw_path', ''))
	kimi_image_tool_edit = line(kimi_image_fields, 'Kimi Work 图像工具 image_generation_tool.py', image_tool_default)
	kimi_image_pythonw_edit = line(kimi_image_fields, '图像插件已验证的 pythonw.exe（不是控制台 Python）', image_pythonw_default)
	var image_tool_picker = FileDialog.new()
	image_tool_picker.title = '选择 Kimi Work 图像工具'
	image_tool_picker.access = FileDialog.ACCESS_FILESYSTEM
	image_tool_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	image_tool_picker.use_native_dialog = true
	image_tool_picker.filters = PackedStringArray(['image_generation_tool.py'])
	image_tool_picker.file_selected.connect(func(path): kimi_image_tool_edit.text = path; _service_settings_changed())
	kimi_image_fields.add_child(image_tool_picker)
	button(kimi_image_fields, '选择图像工具…', func(): image_tool_picker.popup_centered_ratio(0.7))
	var image_pythonw_picker = FileDialog.new()
	image_pythonw_picker.title = '选择图像插件已验证的 pythonw'
	image_pythonw_picker.access = FileDialog.ACCESS_FILESYSTEM
	image_pythonw_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	image_pythonw_picker.use_native_dialog = true
	image_pythonw_picker.filters = PackedStringArray(['pythonw.exe'])
	image_pythonw_picker.file_selected.connect(func(path): kimi_image_pythonw_edit.text = path; _service_settings_changed())
	kimi_image_fields.add_child(image_pythonw_picker)
	button(kimi_image_fields, '选择无窗口 Python…', func(): image_pythonw_picker.popup_centered_ratio(0.7))
	var image_tool_hint = Label.new()
	image_tool_hint.text = '二维路径仅保存在本机设置；检测只核对工具与运行时，不上传或生成。图生图运行时通过官方工具按顺序上传全部参考图，每次最多 8 张；保存的来源与任务回执用于重开恢复。'
	image_tool_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	kimi_image_fields.add_child(image_tool_hint)
	kimi_image_tool_edit.text_changed.connect(func(_text): _service_settings_changed())
	kimi_image_pythonw_edit.text_changed.connect(func(_text): _service_settings_changed())
	var image_label = Label.new()
	image_model_label = image_label
	image_label.text = "图像模型"
	service_fields.add_child(image_label)
	image_model_choice = OptionButton.new()
	image_model_choice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	service_fields.add_child(image_model_choice)
	var mesh_label = Label.new()
	mesh_model_label = mesh_label
	mesh_label.text = "网格模型"
	service_fields.add_child(mesh_label)
	mesh_model_choice = OptionButton.new()
	mesh_model_choice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	service_fields.add_child(mesh_model_choice)
	_set_model_options(image_model_choice, [], "", false)
	_set_model_options(mesh_model_choice, [], "", false)
	var actions = HFlowContainer.new()
	service_fields.add_child(actions)
	button(actions, "检测连接与模型", check_service)
	button(actions, "保存生成服务设置", save_service_settings)
	service_status = Label.new()
	service_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service_status.text = "请选择生成服务；本机复制节点始终可用，配置草稿会自动保存。"
	service_fields.add_child(service_status)
	for kind in NODE_KINDS:
		var label = Label.new()
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		service_capability_labels[kind] = label
		service_fields.add_child(label)
	var guide = Label.new()
	service_guide = guide
	guide.text = "请先启动你已有的 ComfyUI 服务，再填写地址、检测并保存接入配置。检测只查询连接、节点和模型列表，不生成内容、不下载模型。各节点在检查器中独立选择模型；图像生成网格需要源图与网格模型，可选重绘提示词还需要图像模型，文字生成网格需要两类模型。"
	guide.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service_fields.add_child(guide)
	service_control_defaults = {
		"cli_path": cli_path_edit.text,
		"blender_path": blender_path_edit.text,
		"image_tool_path": kimi_image_tool_edit.text,
		"image_pythonw_path": kimi_image_pythonw_edit.text,
		"model3d_tool_path": model3d_tool_edit.text,
		"model3d_pythonw_path": model3d_pythonw_edit.text,
	}
	service_choice.item_selected.connect(_service_mode_selected)
	endpoint_edit.text_changed.connect(func(_text): _service_settings_changed())
	kimi_model_edit.text_changed.connect(func(_text): _service_settings_changed())
	image_model_choice.item_selected.connect(func(_index): _service_settings_changed())
	mesh_model_choice.item_selected.connect(func(_index): _service_settings_changed())
	if settings.get_value("service", "mode", "") == "legacy": select_service_mode('legacy')

func _normalize_service_profile(loaded: Dictionary) -> Dictionary:
	if loaded.get("schema_version") != 1: return {}
	var mode = str(loaded.get("mode", ""))
	if mode in RETIRED_GPT_MESH_MODES:
		loaded = {"schema_version":1, "mode":"codex", "image_model":"builtin", "cli_path":loaded.get("cli_path", "codex")}
		mode = "codex"
	if mode not in SERVICE_PROFILE_MODES: return {}
	var value = {"schema_version":1, "mode":mode, "endpoint":str(loaded.get("endpoint", "http://127.0.0.1:8188")), "image_model":str(loaded.get("image_model", "")), "mesh_model":str(loaded.get("mesh_model", ""))}
	if mode in ['comfy', 'codex']:
		# Resolve trusted bundled tools again after an engine move.
		value.merge(_image_board_runtime(), true)
	if mode == 'codex': value['cli_path'] = str(loaded.get('cli_path', service_control_defaults.get('cli_path', 'codex')))
	if mode in ['kimi_native', 'api_modeling']:
		value.mesh_model = ''
		value['godot_path'] = str(loaded.get('godot_path', OS.get_executable_path()))
		value['builder_path'] = str(loaded.get('builder_path', ProjectSettings.globalize_path(get_script().resource_path.get_base_dir().path_join('modeling_builder.gd'))))
	if mode == 'kimi_native':
		value.image_model = ''
		value.endpoint = ''
		for field in ['image_tool_path', 'image_pythonw_path', 'model3d_tool_path', 'model3d_pythonw_path']:
			var fallback = value.get('image_pythonw_path', service_control_defaults.get(field, '')) if field == 'model3d_pythonw_path' else service_control_defaults.get(field, '')
			value[field] = str(loaded.get(field, fallback))
		value['model3d_model'] = str(loaded.get('model3d_model', 'v3.1'))
		value['texture_model'] = str(loaded.get('texture_model', 'v3.5'))
	if mode == 'api_sculpt':
		value.mesh_model = ''
		value['blender_path'] = str(loaded.get('blender_path', service_control_defaults.get('blender_path', 'blender')))
		value['builder_path'] = str(loaded.get('builder_path', str(get_meta('ainative_tools_dir', '')).path_join('sculpt_builder.py') if get_meta('ainative_builtin', false) else ProjectSettings.globalize_path('res://../../tools/ainative/sculpt_builder.py')))
	if mode in ['api_modeling', 'api_sculpt']:
		value.image_model = ''
		if loaded.has('api_model'): value['api_model'] = loaded.api_model
		value['api_key_env'] = str(loaded.get('api_key_env', 'AINATIVE_API_KEY'))
	if mode == 'local_mesh': value.image_model = ''
	return value

func _default_service_profile(mode: String) -> Dictionary:
	return _normalize_service_profile({"schema_version":1, "mode":mode})

func _apply_service_profile(profile: Dictionary):
	var mode = str(profile.get('mode', ''))
	if mode not in SERVICE_PROFILE_MODES: return
	service_profile_mode = mode
	select_service_mode(mode)
	endpoint_edit.text = str(profile.get('endpoint', ''))
	if mode == 'codex': cli_path_edit.text = str(profile.get('cli_path', 'codex'))
	if mode == 'api_sculpt': blender_path_edit.text = str(profile.get('blender_path', ''))
	if mode == 'kimi_native':
		kimi_image_tool_edit.text = str(profile.get('image_tool_path', ''))
		kimi_image_pythonw_edit.text = str(profile.get('image_pythonw_path', ''))
		model3d_tool_edit.text = str(profile.get('model3d_tool_path', ''))
		model3d_pythonw_edit.text = str(profile.get('model3d_pythonw_path', ''))
	_set_model_options(image_model_choice, [], str(profile.get('image_model', '')), false)
	_set_model_options(mesh_model_choice, [], str(profile.get('mesh_model', '')), false)

func _load_service_profiles() -> String:
	service_profiles = {}
	if not FileAccess.file_exists(service_profiles_path): return ''
	var loaded = JSON.parse_string(FileAccess.get_file_as_string(service_profiles_path))
	if not loaded is Dictionary or loaded.get('schema_version') != 1 or not loaded.get('profiles') is Dictionary: return ''
	for mode in SERVICE_PROFILE_MODES:
		var candidate = loaded.profiles.get(mode, {})
		if candidate is Dictionary:
			var profile = _normalize_service_profile(candidate)
			if not profile.is_empty(): service_profiles[mode] = profile
	var selected = str(loaded.get('selected_mode', ''))
	return selected if selected in SERVICE_PROFILE_MODES else ''

func _persist_service_profiles() -> bool:
	var selected = _service_mode() if _service_mode() in SERVICE_PROFILE_MODES else service_profile_mode
	var document = {"schema_version":1, "selected_mode":selected, "profiles":service_profiles}
	var temporary = service_profiles_path + '.tmp-' + str(Time.get_ticks_usec())
	var output = FileAccess.open(temporary, FileAccess.WRITE)
	if output == null: return false
	output.store_string(JSON.stringify(document, '  '))
	output.flush()
	var failed = output.get_error() != OK
	output.close()
	if not failed and DirAccess.rename_absolute(temporary, service_profiles_path) == OK: return true
	DirAccess.remove_absolute(temporary)
	return false

func _store_service_profile(mode: String):
	if mode in SERVICE_PROFILE_MODES: service_profiles[mode] = _service_draft_for_mode(mode)

func _restore_service_settings(settings: ConfigFile):
	service_ui_loading = true
	var selected = _load_service_profiles()
	if FileAccess.file_exists(service_config_path):
		var loaded = JSON.parse_string(FileAccess.get_file_as_string(service_config_path))
		if loaded is Dictionary and loaded.get('mode') in RETIRED_GPT_MESH_MODES:
			settings.set_value('managed_comfy', 'autostart', false)
			selected = 'codex'
			service_profiles.erase('codex')
		if loaded is Dictionary:
			service_saved = _normalize_service_profile(loaded)
			if not service_saved.is_empty() and not service_profiles.has(service_saved.mode):
				service_profiles[service_saved.mode] = service_saved.duplicate(true)
		if service_saved.is_empty(): service_status.text = '已保存的生成服务设置无效或已下线，请重新选择服务、检测并保存。'
	if selected.is_empty(): selected = str(service_saved.get('mode', 'comfy'))
	if selected not in SERVICE_PROFILE_MODES: selected = 'comfy'
	var profile = service_profiles.get(selected, _default_service_profile(selected))
	service_profiles[selected] = profile.duplicate(true)
	_apply_service_profile(profile)
	if settings.get_value('service', 'mode', '') == 'legacy' or not factory_edit.text in ['editor_demo:factory', 'comfy_provider:factory'] or (service_saved.is_empty() and OS.has_environment('AINATIVE_COMFY_CONFIG')):
		select_service_mode('legacy')
		if OS.has_environment('AINATIVE_COMFY_CONFIG') and factory_edit.text == 'editor_demo:factory': factory_edit.text = 'comfy_provider:factory'
	service_ui_loading = false
	_persist_service_profiles()
	_update_service_summary()

func _retired_mesh_node(data: Dictionary) -> bool:
	if not _is_mesh_kind(str(data.get('type', 'copy'))): return false
	var provider := str(data.get('provider', ''))
	if provider in RETIRED_GPT_MESH_PROVIDERS: return true
	var split := provider.rfind('_')
	if split < 0 or provider.left(split) not in RETIRED_GPT_MESH_PROVIDERS: return false
	var suffix := provider.substr(split + 1)
	for digit in suffix:
		if digit < '0' or digit > '9': return false
	return not suffix.is_empty()

func _generator_description(data: Dictionary) -> String:
	var kind = str(data.get('type', 'copy'))
	if _retired_mesh_node(data): return node_label(kind) + ' · GPT CLI 网格已下线'
	if kind == 'copy': return '本机离线复制'
	var selected_model = str(data.get('model', '')) if not _using_legacy_service() else '高级自定义服务'
	var description = node_label(kind) + ' · ' + (selected_model if not selected_model.is_empty() else 'CLI 默认／待选择模型')
	if _service_mode() in ['api_modeling', 'api_sculpt']: description += ' · 自选 API 语义规划'
	elif _service_mode() == 'local_mesh': description += ' · 本机网格'
	elif _service_mode() == 'kimi_native': description += ' · Tripo API 直接 3D' if _is_mesh_kind(kind) else ' · Kimi Work 图像服务'
	return description

func _generator_provider(kind: String) -> String:
	if _service_mode() == 'api_modeling': return 'api-modeling'
	if _service_mode() == 'api_sculpt': return 'api-sculpt'
	if _service_mode() == 'local_mesh': return 'comfy'
	if _service_mode() == 'kimi_native': return 'kimi_native' if _is_mesh_kind(kind) else 'kimi_work_image'
	if _service_mode() == 'codex' and not _is_mesh_kind(kind): return 'codex'
	return 'comfy'

func select_service_mode(mode: String) -> bool:
	for index in service_choice.item_count:
		if service_choice.get_item_metadata(index) == mode:
			service_choice.select(index)
			return true
	return false

func _service_mode() -> String:
	if service_choice == null or service_choice.selected < 0: return "comfy"
	return str(service_choice.get_item_metadata(service_choice.selected))

func _model_name(choice: OptionButton) -> String:
	if choice.selected < 0: return ""
	return str(choice.get_item_metadata(choice.selected))

func _image_board_runtime() -> Dictionary:
	# Installed bundles keep image_contact_sheet.gd beside modeling_builder.gd.
	# Source-tree tests use the same trusted repository tool, never a relative
	# path which escapes a missing bundle metadata directory.
	var builder = ProjectSettings.globalize_path(get_script().resource_path.get_base_dir().path_join('image_contact_sheet.gd'))
	if not FileAccess.file_exists(builder):
		builder = ProjectSettings.globalize_path('res://../../tools/ainative/image_contact_sheet.gd')
	return {'image_board_godot_path':OS.get_executable_path(), 'image_board_builder_path':builder}

func service_draft() -> Dictionary:
	return _service_draft_for_mode(_service_mode())

func _service_draft_for_mode(mode: String) -> Dictionary:
	var value = {"schema_version":1, "mode":mode, "endpoint":endpoint_edit.text.strip_edges(), "image_model":_model_name(image_model_choice), "mesh_model":_model_name(mesh_model_choice)}
	var profile: Dictionary = service_profiles.get(mode, {})
	if value.mode in ['comfy', 'codex']:
		value.merge(_image_board_runtime(), true)
	if value.mode == 'codex':
		value['cli_path'] = cli_path_edit.text.strip_edges()
		value.image_model = 'builtin'
	if value.mode in ['kimi_native', 'api_modeling']:
		value.mesh_model = ''
		value['godot_path'] = OS.get_executable_path()
		value['builder_path'] = ProjectSettings.globalize_path(get_script().resource_path.get_base_dir().path_join('modeling_builder.gd'))
	if value.mode == 'kimi_native':
		value.image_model = ''
		value.endpoint = ''
		value['image_tool_path'] = kimi_image_tool_edit.text.strip_edges()
		value['image_pythonw_path'] = kimi_image_pythonw_edit.text.strip_edges()
		value['model3d_tool_path'] = model3d_tool_edit.text.strip_edges()
		value['model3d_pythonw_path'] = model3d_pythonw_edit.text.strip_edges()
		value['model3d_model'] = str(profile.get('model3d_model', 'v3.1'))
		value['texture_model'] = str(profile.get('texture_model', 'v3.5'))
	if value.mode == 'api_sculpt':
		value.mesh_model = ''
		value['blender_path'] = blender_path_edit.text.strip_edges()
		value['builder_path'] = str(get_meta('ainative_tools_dir', '')).path_join('sculpt_builder.py') if get_meta('ainative_builtin', false) else ProjectSettings.globalize_path('res://../../tools/ainative/sculpt_builder.py')
	if value.mode in ['api_modeling', 'api_sculpt']:
		value.image_model = ''
		# Retain the old value only to migrate unopened legacy workflows.
		if profile.has('api_model'): value['api_model'] = profile.api_model
		value['api_key_env'] = str(profile.get('api_key_env', 'AINATIVE_API_KEY'))
	if value.mode == 'local_mesh': value.image_model = ''
	return value

func _set_model_options(choice: OptionButton, names: Array, selected_name: String, detected: bool):
	choice.clear()
	choice.add_item("请选择已安装模型" if detected else "请先检测模型")
	choice.set_item_metadata(0, "")
	var chosen = 0
	for name in names:
		choice.add_item('CLI 内置图像生成' if str(name) == 'builtin' else str(name))
		choice.set_item_metadata(choice.item_count - 1, str(name))
		if str(name) == selected_name: chosen = choice.item_count - 1
	if not selected_name.is_empty() and chosen == 0:
		choice.add_item(selected_name + ("（当前服务未提供）" if detected else "（已保存，待检测）"))
		choice.set_item_metadata(choice.item_count - 1, selected_name)
		chosen = choice.item_count - 1
	choice.select(chosen)

func _service_mode_selected(_index: int):
	if service_ui_loading: return
	var mode = _service_mode()
	if service_profile_mode in SERVICE_PROFILE_MODES and service_profile_mode != mode:
		# The option has already changed, but the controls still hold the previous service.
		_store_service_profile(service_profile_mode)
	if mode in SERVICE_PROFILE_MODES:
		service_ui_loading = true
		var profile = service_profiles.get(mode, _default_service_profile(mode))
		service_profiles[mode] = profile.duplicate(true)
		_apply_service_profile(profile)
		service_ui_loading = false
	_service_settings_changed()

func _service_settings_changed():
	if service_ui_loading: return
	var mode = _service_mode()
	if mode in SERVICE_PROFILE_MODES:
		service_profile_mode = mode
		_store_service_profile(mode)
	service_report = {}
	service_report_draft = ""
	_update_service_summary()
	if not _persist_service_profiles():
		service_status.text = '配置草稿无法写入本机文件，请检查用户目录是否可写。'

func _update_service_summary():
	if service_choice == null: return
	var mode = _service_mode()
	var cli_mode = mode == 'codex'
	var api_mode = mode in ['api_modeling', 'api_sculpt']
	var sculpt_mode = mode == 'api_sculpt'
	var kimi_mode = mode == 'kimi_native'
	if graph != null:
		for data in nodes:
			var description = graph.get_node_or_null(NodePath(str(data.id) + '/GeneratorDescription'))
			if description is Label: description.text = _generator_description(data)
	if parameter_form != null:
		parameter_form.set_cli_mode(cli_mode)
		parameter_form.set_sculpt_mode(sculpt_mode)
		parameter_form.set_kimi_mode(kimi_mode)
		parameter_form.set_api_mode(api_mode)
	if cli_fields != null: cli_fields.visible = cli_mode
	if blender_fields != null: blender_fields.visible = sculpt_mode
	if cli_billing != null:
		cli_billing.text = '图像生成与编辑使用当前 Codex CLI 登录额度。网格由本机模型执行。'
	if managed_comfy_panel != null: managed_comfy_panel.visible = mode in ['codex', 'local_mesh']
	if service_guide != null: service_guide.visible = not cli_mode and not kimi_mode and not api_mode
	if cli_mode and _model_name(image_model_choice) != 'builtin':
		_set_model_options(image_model_choice, ['builtin'], 'builtin', true)
	endpoint_edit.visible = not cli_mode and not kimi_mode
	endpoint_edit.editable = mode in ['comfy', 'local_mesh', 'api_modeling', 'api_sculpt']
	kimi_model_label.text = 'Kimi 模型'
	kimi_auth_label.text = '凭据环境变量：' + str(service_profiles.get(mode, {}).get('api_key_env', 'AINATIVE_API_KEY')) + '；模型请在各节点检查器中选择。检测仅核对本机配置，运行时验证接口。' if mode in ['api_modeling', 'api_sculpt'] else 'Tripo API 与 Kimi Work 凭据由 agent-gw SDK 管理。检测仅核对本机工具；账号授权、额度与网络尚未验证，以实际任务回执为准。无需配置 Kimi 语言模型地址或模型。'
	kimi_model_label.hide()
	kimi_model_edit.hide()
	kimi_auth_label.visible = kimi_mode or api_mode
	if kimi_model3d_fields != null: kimi_model3d_fields.visible = kimi_mode
	if kimi_image_fields != null: kimi_image_fields.visible = kimi_mode
	image_model_choice.hide()
	mesh_model_choice.hide()
	if image_model_label != null: image_model_label.hide()
	if mesh_model_label != null: mesh_model_label.hide()
	if node_model_edit != null and not selected_id.is_empty():
		for data in nodes:
			if data.id == selected_id:
				_sync_node_model_controls(data)
				break
	if mode == 'legacy':
		service_status.text = '正在兼容已有的高级服务配置。'
	elif service_report.is_empty():
		if service_draft() != service_saved:
			service_status.text = '服务设置尚未保存。请检测连接并保存。'
		elif api_mode:
			service_status.text = '自选 API 规划结构，' + ('Blender' if sculpt_mode else 'Godot') + ' 构造网格；已恢复设置，待核对配置。'
		elif kimi_mode:
			service_status.text = 'Tripo API 直接生成 GLB，无需 Blender；Kimi Work 图像服务负责二维。'
		else:
			service_status.text = '图像使用当前 CLI 登录额度；网格需要本机模型。请检测并保存。' if mode == 'codex' else '已恢复服务设置，待检测；运行前会检查连接与模型。'
	for kind in service_capability_labels:
		var label: Label = service_capability_labels[kind]
		if kind == 'copy': label.text = node_label(kind) + '：可用，不调用模型'
		elif mode == 'legacy': label.text = node_label(kind) + '：由已有高级配置检查'
		elif api_mode:
			label.text = node_label(kind) + ('：待核对配置 · 自选 API 与 ' + ('Blender' if sculpt_mode else 'Godot') if kind.ends_with('mesh') else '：不可用 · 语义规划仅生成网格')
		elif mode == 'local_mesh':
			label.text = node_label(kind) + ('：待检测 · 本机模型' if kind == 'image_to_mesh' else '：不可用 · 仅直接图生网格')
		else: label.text = node_label(kind) + ('：待检测 · Kimi Work 独立图像服务' if kimi_mode and not _is_mesh_kind(kind) else '：待检测 · Tripo API 直接三维' if kimi_mode else '：待检测')

func _using_legacy_service() -> bool:
	return _service_mode() == "legacy" or (factory_edit != null and not factory_edit.text in ["editor_demo:factory", "comfy_provider:factory"])

func _uses_gui_service() -> bool:
	return not _using_legacy_service() and not service_saved.is_empty() and FileAccess.file_exists(service_config_path)

func save_service_settings():
	if is_graph_busy():
		_show_run_problem("请等待当前操作结束或取消后，再保存生成服务设置。")
		return
	if _service_mode() == "legacy":
		save_settings()
		var legacy = ConfigFile.new()
		legacy.load(state_dir.path_join("local.cfg"))
		legacy.set_value("service", "mode", "legacy")
		if legacy.save(state_dir.path_join("local.cfg")) != OK:
			_show_run_problem("无法保存本机设置，请检查本机用户目录是否可写。")
			return
		service_status.text = "已保存旧配置兼容模式。已有服务仍由其高级配置提供。"
		return
	var draft = service_draft()
	if draft.mode in ['comfy', 'codex'] and not _valid_service_endpoint(draft.endpoint):
		_show_run_problem("服务地址应为 http:// 或 https:// 加主机与端口，不可包含账号、密码、查询参数或路径。请修正后重新检测。")
		return
	if draft.mode in ['local_mesh', 'api_modeling', 'api_sculpt']:
		var authority = draft.endpoint.get_slice('/', 2)
		if authority.contains(':') and not authority.ends_with(']'):
			var port = authority.get_slice(':', authority.get_slice_count(':') - 1)
			if not port.is_valid_int() or port.to_int() < 0 or port.to_int() > 65535:
				_show_run_problem('服务端口无效，已保留原配置。')
				return
	if draft.mode == 'local_mesh':
		var local_address = RegEx.new()
		local_address.compile('^http://(localhost|127\\.0\\.0\\.1|\\[::1\\])(:[0-9]{1,5})?/?$')
		if not _valid_service_endpoint(draft.endpoint) or local_address.search(draft.endpoint) == null:
			_show_run_problem('本机网格地址必须是本机 HTTP 服务，不可包含账号、密码、查询参数或额外路径。')
			return
	if draft.mode in ['api_modeling', 'api_sculpt']:
		var api_address = RegEx.new()
		api_address.compile('^(https://([^/?#@:\\s]+|\\[[0-9a-fA-F:]+\\])(:[0-9]{1,5})?|http://(localhost|127\\.0\\.0\\.1|\\[::1\\])(:[0-9]{1,5})?)(/[^?#@\\s]*)?$')
		var key_name = RegEx.new()
		key_name.compile('^[A-Za-z_][A-Za-z0-9_]*$')
		var control = RegEx.new()
		control.compile('[\\x00-\\x1f\\x7f]')
		if api_address.search(draft.endpoint) == null or control.search(draft.endpoint) != null or key_name.search(draft.api_key_env) == null:
			_show_run_problem('请填写有效 API 地址和凭据环境变量名。远程地址须用 HTTPS，不可包含账号、密码或查询参数。')
			return
		if draft.mode == 'api_sculpt' and draft.blender_path.is_empty():
			_show_run_problem('请填写 Blender 程序路径后保存。')
			return
	var temporary = service_config_path + ".tmp-" + str(Time.get_ticks_usec())
	var output = FileAccess.open(temporary, FileAccess.WRITE)
	if output == null:
		_show_run_problem("无法保存生成服务设置，请检查本机用户目录是否可写。")
		return
	output.store_string(JSON.stringify(draft, "  "))
	output.flush()
	var write_error = output.get_error()
	output.close()
	if write_error != OK or DirAccess.rename_absolute(temporary, service_config_path) != OK:
		DirAccess.remove_absolute(temporary)
		_show_run_problem("无法替换生成服务设置，已保留上一次配置。")
		return
	service_saved = draft.duplicate(true)
	service_profiles[draft.mode] = draft.duplicate(true)
	service_profile_mode = draft.mode
	if not _persist_service_profiles():
		_show_run_problem('运行配置已写入，但分服务配置库保存失败，请检查用户目录。')
		return
	# An explicit GUI save chooses this service over legacy host configuration.
	factory_edit.text = "editor_demo:factory"
	# Nodes created before service setup inherit once; explicit choices stay independent.
	for data in nodes: _migrate_node_models(data, draft)
	save_settings()
	var local = ConfigFile.new()
	local.load(state_dir.path_join("local.cfg"))
	local.set_value("service", "mode", draft.mode)
	if local.save(state_dir.path_join("local.cfg")) != OK:
		_show_run_problem("服务配置已写入，但运行环境设置保存失败，请检查用户目录。")
		return
	_update_service_summary()
	service_status.text = ('已保存自选 API 设置；' + ('Blender' if draft.mode == 'api_sculpt' else 'Godot') + ' 构造网格。') if draft.mode in ['api_modeling', 'api_sculpt'] else '已保存本机图生网格设置；无需 CLI。' if draft.mode == 'local_mesh' else '已保存 Kimi 复合设置；Mesh 由 Tripo API 直接生成且无需 Blender，二维由独立 Kimi Work 图像服务生成；本机路径不进入工作流。' if draft.mode == 'kimi_native' else '已保存 CLI 图像与本机网格设置；图像沿用当前 CLI 登录额度。' if draft.mode == 'codex' else "已保存生成服务设置；检测通过后可明确查看各类生成能力。"
	if status != null: status.text = service_status.text
	if service_config_link != null: service_config_link.hide()

func check_service():
	if is_graph_busy():
		_show_run_problem("正在处理其他操作，请结束后再检测生成服务。")
		return
	if _service_mode() == "legacy":
		service_status.text = "旧配置由原服务适配器检查。选择 ComfyUI 可在本界面检测地址与模型。"
		return
	service_status.text = '正在核对 API 配置、凭据环境变量与构造器；不检测远端生成能力…' if _service_mode() in ['api_modeling', 'api_sculpt'] else '正在分别检测 Tripo API 直接三维工具与 Kimi Work 二维图像工具；不会上传或生成…' if _service_mode() == 'kimi_native' else "正在检测连接、节点和模型列表；不会生成内容或下载模型…"
	launch("service-check", {"service":service_draft()})

func _apply_service_check(data: Dictionary, checked_draft: Dictionary):
	if checked_draft != service_draft():
		service_status.text = "检测期间设置已改变，请重新检测当前设置。"
		_show_run_problem(service_status.text)
		return
	service_ui_loading = true
	var models: Dictionary = data.get("models", {})
	_set_model_options(image_model_choice, models.get("image", []), checked_draft.image_model, true)
	_set_model_options(mesh_model_choice, models.get("mesh", []), checked_draft.mesh_model, true)
	service_report = data.duplicate(true)
	service_report_draft = JSON.stringify(service_draft())
	service_ui_loading = false
	_update_service_summary()
	service_status.text = str(data.get("message", "检测完成，请查看各类能力状态。"))
	for kind in service_capability_labels:
		if kind == "copy": continue
		var capability: Dictionary = data.get("capabilities", {}).get(kind, {})
		service_capability_labels[kind].text = node_label(kind) + "：" + ("就绪" if capability.get("ready", false) else "不可用") + " · " + str(capability.get("message", "服务未提供该能力"))
	if status != null: status.text = service_status.text
	if not data.get("connected", false):
		_show_run_problem(service_status.text)

func _service_blocker(kind: String, data: Dictionary = {}) -> String:
	if kind == "copy" or _using_legacy_service(): return ""
	if _is_mesh_kind(kind) and managed_comfy_panel != null and _service_mode() in ['codex', 'local_mesh']:
		var bundle_problem: String = managed_comfy_panel.bundled_mesh_blocker()
		if not bundle_problem.is_empty(): return bundle_problem
	if _service_mode() not in SERVICE_PROFILE_MODES:
		return "请选择一种生成服务，再保存配置。"
	if kind == 'model_adjust' and _service_mode() != 'kimi_native':
		return '模型调整目前使用 Kimi Native / Tripo API，请先在 AI 设置中选择 Kimi Native。'
	if service_saved.is_empty() or service_draft() != service_saved:
		return "生成服务设置尚未保存。请在 AI 设置中检测连接并保存。"
	if _service_mode() in ['api_modeling', 'api_sculpt'] and not _is_mesh_kind(kind):
		return '当前语义建模模式仅支持文字生成网格和图像生成网格。'
	if _service_mode() == 'kimi_native' and _is_mesh_kind(kind):
		if str(service_saved.get('model3d_tool_path', '')).is_empty() or str(service_saved.get('model3d_pythonw_path', '')).is_empty():
			return '请在 AI 设置中配置 Kimi Work 的 model3d_generation_tool.py 和已验证的运行时，再保存并检测。Mesh 使用 Tripo API 直接生成，无需 Blender。'
	if _service_mode() == 'kimi_native' and not _is_mesh_kind(kind):
		if str(service_saved.get('image_tool_path', '')).is_empty() or str(service_saved.get('image_pythonw_path', '')).is_empty():
			return '请在 AI 设置中配置 Kimi Work 的 image_generation_tool.py 和已验证的 pythonw，再保存并检测。二维使用独立图像服务，不调用 K3.1 Pro 直接出图。'
	var effective_prompt = (str(data.get("parameters", {}).get("prompt", "")) + "\n" + str(data.get("text", ""))).strip_edges()
	if _service_mode() == 'local_mesh' and (kind != 'image_to_mesh' or not effective_prompt.is_empty()):
		return '本机网格模式只接受已有图片；请留空重绘提示词。'
	var redraw = kind == "image_to_mesh" and not effective_prompt.is_empty() and _service_mode() not in ['kimi_native', 'local_mesh', 'api_modeling', 'api_sculpt']
	var selected_model = str(data.get('model', '')).strip_edges()
	var secondary_image = str(data.get('image_model', '')).strip_edges()
	var fixed_model = _service_mode() == 'kimi_native' and not _is_mesh_kind(kind)
	if not fixed_model and selected_model.is_empty():
		return '该节点尚未选择模型，请在节点检查器中填写或选择模型。'
	if _service_mode() in ['api_modeling', 'api_sculpt']:
		var raw_model = data.get('model', '')
		var invalid_chars = RegEx.new()
		invalid_chars.compile('[\\x00-\\x1f\\x7f]')
		var retired_model = RegEx.new()
		retired_model.compile('^(chatgpt(-[0-9][a-z0-9]*([.-][a-z0-9]+)*)?|gpt-([0-9][a-z0-9]*|oss)([.-][a-z0-9]+)*)$')
		var normalized = selected_model.to_lower().trim_prefix('ft:').get_slice(':', 0)
		if not raw_model is String or raw_model != selected_model or selected_model.length() > 256 or invalid_chars.search(selected_model) != null or selected_model.to_lower().begins_with('openai/') or retired_model.search(normalized) != null:
			return '该节点的 API 模型无效或已下线，请在节点检查器中填写有效的本节点模型 ID。'
	if _service_mode() in ['comfy', 'codex'] and ((kind == 'text_to_mesh') or redraw) and secondary_image.is_empty():
		return '该节点需要图像模型，请在节点检查器中选择文字生成图像／重绘模型。'
	if not service_report.is_empty() and service_report_draft == JSON.stringify(service_draft()):
		var models: Dictionary = service_report.get('models', {})
		var catalog: Array = models.get('mesh' if _is_mesh_kind(kind) else 'image', [])
		var catalog_primary = _service_mode() in ['comfy', 'kimi_native', 'local_mesh'] or (_service_mode() == 'codex' and kind.ends_with('mesh'))
		if catalog_primary and not selected_model.is_empty() and not selected_model in catalog:
			return '该节点模型不在当前服务目录中，请重新检测并修正节点选择。'
		if _service_mode() == 'comfy' and (kind == 'text_to_mesh' or redraw) and not secondary_image in models.get('image', []):
			return '该节点的图像模型不在当前服务目录中，请重新选择。'
		if redraw:
			var image_capability: Dictionary = service_report.get("variants", {}).get("image_to_mesh_redraw", service_report.get("capabilities", {}).get("image_to_image", {}))
			if not image_capability.get("ready", false): return "该节点需要先重绘图像：" + str(image_capability.get("message", "当前服务的图像生成能力尚未就绪"))
		var capability: Dictionary = service_report.get("capabilities", {}).get(kind, {})
		if not capability.get("ready", false): return str(capability.get("message", "当前服务不具备该节点所需能力，请重新检测并修正设置。"))
	return ""

func _copy_failure_text():
	if failure_text == null: return
	if DisplayServer.has_feature(DisplayServer.FEATURE_CLIPBOARD):
		DisplayServer.clipboard_set(failure_text.text)
		failure_copy_hint.text = "已复制全部报错内容。"
	else:
		failure_copy_hint.text = "当前环境不支持系统剪贴板，请手动选择文本复制。"

func _show_failure_dialog(message: String):
	if failure_dialog == null: return
	failure_text.text = message
	failure_copy_hint.text = "也可直接选择文本复制。"
	failure_dialog.popup_centered(Vector2i(760, 400))

func _show_run_problem(message: String, section: String = 'ai'):
	if status != null: status.text = message
	service_settings_section = section
	if service_config_link != null:
		service_config_link.text = '配置运行环境' if section == 'environment' else '配置生成服务'
		service_config_link.show()
	_show_failure_dialog(message)

func open_service_settings():
	if get_meta('ainative_builtin', false):
		settings_requested.emit(service_settings_section)
		return
	elif service_fields != null:
		var current_parent: Node = python_edit if service_settings_section == 'environment' else service_fields
		while current_parent != self and current_parent != null:
			if current_parent is Control: current_parent.show()
			current_parent = current_parent.get_parent()
	var focus_control = python_edit if service_settings_section == 'environment' else service_choice
	if focus_control != null: focus_control.grab_focus()

func _valid_service_endpoint(value: String) -> bool:
	var pattern = RegEx.new()
	pattern.compile("^https?://(\\[[0-9a-fA-F:]+\\]|[A-Za-z0-9.-]+)(:([0-9]{1,5}))?/?$")
	var result = pattern.search(value)
	if result == null: return false
	var port = result.get_string(3)
	return port.is_empty() or (port.to_int() > 0 and port.to_int() <= 65535)

func _legacy_factory_changed(_text: String):
	if service_ui_loading: return
	if not factory_edit.text in ["editor_demo:factory", "comfy_provider:factory"]:
		select_service_mode('legacy')
		_service_settings_changed()
