@tool
extends VBoxContainer
# Local machine settings are intentionally excluded from workflow serialization.
signal settings_requested(section: String)
var rigging_panel: VBoxContainer
var generator_choice: OptionButton
var graph: GraphEdit
var status: Label
var process_button: Button
var process_panel: PanelContainer
var process_summary: Label
var process_steps: TextEdit
var process_logs: TextEdit
var process_entries: Array = []
var process_expanded := false
var path_edit: LineEdit
var source_edit: LineEdit
var context_row: HBoxContainer
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
var humanoid_review_node = ""
var humanoid_review_source = ""
var humanoid_review_directory = ""
var humanoid_review_input: Dictionary = {}
# Post-rigging assessment keeps the reloaded candidate alive while text-only AI runs.
var humanoid_text_review: Dictionary = {}
# Test-only synthetic receipt; production runs always use rigging-text-review.
var humanoid_text_review_fixture: Dictionary = {}
var run_all_dialog: ConfirmationDialog
var run_all_button: Button
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
var custom_templates: Dictionary = {}
var main_graph: Dictionary = {"nodes": [], "edges": []}
var active_template_id = ""
var workflow_tabs: TabBar
var template_name_edit: LineEdit
var template_rename_button: Button
var template_edit_button: Button
var boundary_hint: Label
var node_editor_controls: Array = []
var document_histories: Dictionary = {}
var template_target_aliases: Dictionary = {}
const WorkflowTemplate = preload("res://addons/ainative/workflow_template.gd")
const WorkbenchController = preload("res://addons/ainative/workbench_controller.gd")
const HumanoidRigNode = preload("res://addons/ainative/humanoid_rig_node.gd")
const Rig = preload("res://addons/ainative/rigging.gd")
var controller = WorkbenchController.new()
# Maps an upstream preview node to local humanoid targets waiting for its GLB.
var humanoid_waiting: Dictionary = {}
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
var cache_full_run := false
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
# Selection preview decoding runs off the UI thread; only the latest request may present.
var preview_request_serial := 0
var preview_pending_request: Dictionary = {}
var preview_active_request: Dictionary = {}
var preview_request_delay := 0.0
var preview_worker_task := -1
var preview_worker_result: Dictionary = {}
var preview_decode_count := 0
var preview_continuous_render := false
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
const HUMANOID_RIG = "humanoid_rig"
const HUMAN_SHAPE = "human_shape_adjust"
const GARMENT_SPLIT = "garment_split"
const IMAGE_KINDS = [GENERATE_IMAGE, "text_to_image", "image_to_image"]
const CUSTOM_TEMPLATE = WorkflowTemplate.CUSTOM_TEMPLATE
const TEMPLATE_INPUT = WorkflowTemplate.TEMPLATE_INPUT
const TEMPLATE_OUTPUT = WorkflowTemplate.TEMPLATE_OUTPUT
const NODE_KINDS = [GENERATE_IMAGE, "text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh", "model_adjust", HUMAN_SHAPE, HUMANOID_RIG, GARMENT_SPLIT, "copy", CUSTOM_TEMPLATE, TEMPLATE_INPUT, TEMPLATE_OUTPUT]
const CREATION_NODE_KINDS = [GENERATE_IMAGE, "image_to_mesh", "text_to_mesh", "model_adjust", HUMAN_SHAPE, HUMANOID_RIG, GARMENT_SPLIT, "copy"]
const PORT_DYNAMIC = 0
const PORT_IMAGE = 1
const PORT_MESH = 2
const PORT_TEXT = 3
const PORT_IMAGE_SET = 4
const PORT_CHARACTER = 5
const PORT_COLORS = {
	PORT_DYNAMIC: Color(0.65, 0.68, 0.75),
	PORT_IMAGE: Color.SKY_BLUE,
	PORT_MESH: Color.PALE_GREEN,
	PORT_TEXT: Color(0.85, 0.65, 1.0),
	PORT_IMAGE_SET: Color(0.4, 0.85, 0.85),
	PORT_CHARACTER: Color(1.0, 0.65, 0.25),
}

func node_label(kind: String) -> String:
	return {"copy":"离线复制", GENERATE_IMAGE:"生成图片", "text_to_image":"文字生成图像", "image_to_image":"图像生成图像", "image_to_mesh":"图像生成网格", "text_to_mesh":"文字生成网格", "model_adjust":"模型调整", HUMAN_SHAPE:"人形体态调整", HUMANOID_RIG:"创建人形17根骨骼", GARMENT_SPLIT:"衣服拆分", CUSTOM_TEMPLATE:"自定义流程模板", TEMPLATE_INPUT:"流程输入（固定）", TEMPLATE_OUTPUT:"流程输出（固定）"}.get(kind,kind)

func template_name(template_id: String) -> String:
	return str(custom_templates.get(template_id, {}).get("name", template_id))

func _template_display_name(data: Dictionary) -> String:
	if str(data.get("type", "")) != CUSTOM_TEMPLATE: return node_label(str(data.get("type", "copy")))
	return template_name(str(data.get("template_id", "")))

func _is_mesh_kind(kind: String) -> bool:
	return kind in ["text_to_mesh", "image_to_mesh", "model_adjust", HUMAN_SHAPE, GARMENT_SPLIT]

func _is_image_kind(kind: String) -> bool:
	return kind in IMAGE_KINDS

func _new_node_version(kind: String) -> String:
	if kind == GENERATE_IMAGE: return "2"
	if kind == "image_to_mesh": return "2"
	if kind == "model_adjust": return "2"
	return "4" if kind in ["text_to_image", "image_to_image"] else "1"

func human_shape_default_parameters() -> Dictionary:
	return {
		"height_cm":180, "head_ratio":7.5, "arm_length_scale":1.0,
		"leg_length_scale":1.0, "build":0.0
	}

func garment_split_default_parameters() -> Dictionary:
	return {"items":[]}

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
	var shape = kind == HUMAN_SHAPE
	var garment = kind == GARMENT_SPLIT
	var mesh_input = kind in ["model_adjust",HUMAN_SHAPE,HUMANOID_RIG,GARMENT_SPLIT]
	var multiple = _is_image_kind(kind) or _accepts_image_set(data)
	source_picker.title = "选择项目中的 GLB 人形模型" if kind == HUMANOID_RIG else "选择绑骨前的静态 GLB 人形模型" if shape else "选择已绑骨 GLB，也支持未绑骨静态模型" if garment else "选择已生成模型（GLB / 内嵌 glTF）" if adjust else "选择源图像或模型" if copy else "选择源图像（可多选）"
	source_picker.filters = PackedStringArray(["*.glb ; 已绑骨或静态 GLB 模型" if garment else "*.glb,*.gltf ; GLB / 内嵌 glTF 模型" if mesh_input else "*.png,*.jpg,*.jpeg,*.glb,*.gltf ; 图像 / 网格" if copy else "*.png,*.jpg,*.jpeg ; PNG / JPEG 图像"])
	source_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILES if multiple else FileDialog.FILE_MODE_OPEN_FILE
	context_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILES if multiple or adjust else FileDialog.FILE_MODE_OPEN_FILE
	source_browse.text = "选择模型…" if mesh_input else "选择文件…" if copy else "选择图片…"
	source_edit.placeholder_text = "选择项目路径下的 GLB，或连接上游 Mesh" if kind == HUMANOID_RIG else "选择绑骨前 GLB；关键点须绑定此文件 SHA" if shape else "选择已绑骨 GLB，或连接上游 Mesh" if garment else "必须选择已生成模型" if adjust else "未选择源图像或模型" if copy else "未选择源图像，可多选；也可仅填写文本" if kind == GENERATE_IMAGE else "未选择源图像，可多选"
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
	controller.command_started.connect(_record_command_started)
	controller.command_completed.connect(_record_command_completed)
	controller.command_failed.connect(_record_command_failed)
	controller.runtime_event.connect(_record_runtime_event)
	var builtin = get_meta('ainative_builtin',false)
	# The embedded editor shares horizontal space with the workbench sidebar.
	# Wide tools remain reachable in WorkbenchScroll.
	custom_minimum_size = Vector2(0 if builtin else 900, 520)
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
	run_all_button = button(bar, "全部重跑", request_run_all)
	run_all_button.name = "RunAllButton"
	run_all_button.tooltip_text = "清空所有节点的缓存结果，并重新运行整个工作流"
	run_all_dialog = ConfirmationDialog.new()
	run_all_dialog.name = "RunAllConfirmation"
	run_all_dialog.title = "确认全部重跑"
	run_all_dialog.dialog_text = "全部重跑将清空所有节点的现有缓存结果，并重新运行全部节点。\n\n此操作无法撤销，是否继续？"
	run_all_dialog.ok_button_text = "清空缓存并重跑"
	run_all_dialog.cancel_button_text = "取消"
	run_all_dialog.confirmed.connect(confirm_run_all)
	add_child(run_all_dialog)
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
	var template_bar = HBoxContainer.new()
	template_bar.name = "WorkflowTemplateTabs"
	content.add_child(template_bar)
	workflow_tabs = TabBar.new()
	workflow_tabs.name = "WorkflowTabs"
	workflow_tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	workflow_tabs.tab_selected.connect(_workflow_tab_selected)
	template_bar.add_child(workflow_tabs)
	button(template_bar, "+ 自定义流程模板", create_custom_template)
	template_name_edit = LineEdit.new()
	template_name_edit.name = "TemplateName"
	template_name_edit.placeholder_text = "模板名称"
	template_name_edit.custom_minimum_size.x = 180
	template_name_edit.max_length = 80
	template_name_edit.text_submitted.connect(rename_active_template)
	template_bar.add_child(template_name_edit)
	template_rename_button = button(template_bar, "改名", func(): rename_active_template(template_name_edit.text))
	_refresh_workflow_tabs()
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
	graph.add_valid_connection_type(PORT_CHARACTER, PORT_DYNAMIC)
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
	boundary_hint = Label.new()
	boundary_hint.name = "TemplateBoundaryHint"
	boundary_hint.text = "固定边界节点：用于模板对外输入或输出，不能删除或复制。"
	boundary_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector.add_child(boundary_hint)
	template_edit_button = button(inspector, "打开并编辑此模板", func():
		var selected = nodes.filter(func(node): return node.id == selected_id)
		if not selected.is_empty(): open_custom_template(str(selected[0].get("template_id", "")))
	)
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
	context_row = HBoxContainer.new()
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
	var apply_button = button(inspector, "应用到选中节点", apply_fields)
	var clear_button = button(inspector, "清除内嵌源文件和参考图像", clear_embedded)
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
	node_editor_controls = [source_row, context_row, node_model_label, node_model_choice, node_model_edit, node_image_model_label, node_image_model_choice, node_image_model_edit, text_edit, parameter_form, apply_button, clear_button]
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
	container.resized.connect(_request_preview_redraw)
	inspector.add_child(container)
	container.hide()
	viewport = SubViewport.new()
	viewport.size = Vector2i(360, 160)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
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
	_setup_process_panel()

func _setup_process_panel():
	process_panel = PanelContainer.new()
	process_panel.name = "ExecutionProcessPanel"
	process_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	process_panel.size_flags_vertical = Control.SIZE_SHRINK_END
	add_child(process_panel)
	var layout = VBoxContainer.new()
	process_panel.add_child(layout)
	var header = HBoxContainer.new()
	layout.add_child(header)
	var title = Label.new()
	title.text = "具体过程"
	header.add_child(title)
	process_summary = Label.new()
	process_summary.name = "ExecutionProcessSummary"
	process_summary.text = "尚无运行记录"
	process_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	process_summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(process_summary)
	var minimize = button(header, "最小化", toggle_process_panel)
	minimize.name = "MinimizeProcessButton"
	minimize.tooltip_text = "收起过程面板；正在运行的任务不会中断"
	var tabs = TabContainer.new()
	tabs.name = "ExecutionProcessTabs"
	tabs.custom_minimum_size = Vector2(0, 250)
	tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layout.add_child(tabs)
	process_steps = _make_process_text(tabs, "思考与执行过程")
	process_logs = _make_process_text(tabs, "完整日志")
	process_logs.wrap_mode = TextEdit.LINE_WRAPPING_NONE
	var actions = HBoxContainer.new()
	layout.add_child(actions)
	button(actions, "复制全部日志", _copy_process_logs)
	button(actions, "刷新日志", _refresh_process_views)
	button(actions, "打开本机诊断日志", open_diagnostics)
	process_panel.hide()
	process_button = button(self, "查看具体过程", toggle_process_panel)
	process_button.name = "ViewProcessButton"
	process_button.tooltip_text = "查看本次会话的思考、执行步骤、运行事件与完整诊断日志"
	_refresh_process_views()

func _make_process_text(parent: TabContainer, tab_title: String) -> TextEdit:
	var output = TextEdit.new()
	output.name = tab_title
	output.editable = false
	output.selecting_enabled = true
	output.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	output.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	output.size_flags_vertical = Control.SIZE_EXPAND_FILL
	parent.add_child(output)
	return output

func toggle_process_panel():
	if process_panel == null: return
	process_expanded = not process_expanded
	process_panel.visible = process_expanded
	process_button.text = "收起具体过程" if process_expanded else "查看具体过程"
	process_button.tooltip_text = "最小化过程面板；正在运行的任务不会中断" if process_expanded else "查看本次会话的思考、执行步骤、运行事件与完整诊断日志"
	if process_expanded:
		_refresh_process_views()
	else:
		process_button.grab_focus()

func _append_process_entry(category: String, summary: String, details: Dictionary = {}):
	process_entries.append({
		"timestamp": Time.get_datetime_string_from_system(),
		"time": Time.get_time_string_from_system(),
		"category": category,
		"summary": summary,
		"details": details.duplicate(true)
	})
	if process_summary != null: process_summary.text = summary
	if process_expanded: _refresh_process_views()

func _command_process_label(command: String) -> String:
	return {
		"create": "创建任务",
		"step": "推进任务",
		"status": "查询状态",
		"cancel": "取消任务",
		"retry": "重试节点",
		"preview": "读取预览",
		"publish": "发布生成物",
		"service-check": "检测生成服务",
		"managed-comfy": "管理本机服务",
		"rigging-review": "AI 视觉审核",
		"rigging-text-review": "绑骨文本审核"
	}.get(command, command)

func _record_command_started(command: String, request: Dictionary):
	_append_process_entry("执行命令", "已开始：" + _command_process_label(command), {"command": command, "request": request})

func _record_command_completed(command: String, data: Dictionary, request: Dictionary):
	_append_process_entry("命令返回", "已完成：" + _command_process_label(command), {"command": command, "request": request, "result": data})

func _record_command_failed(command: String, failure: Dictionary):
	var code = str(failure.get("code", "unknown"))
	_append_process_entry("命令失败", "失败：" + _command_process_label(command) + "（" + code + "）", {"command": command, "failure": failure})

func _runtime_event_summary(event: Dictionary) -> String:
	var kind = str(event.get("kind", "progress"))
	var payload: Dictionary = event.get("payload", {})
	match kind:
		"run_started":
			return "已接收任务，冻结节点、模型和运行配置，开始执行"
		"text_delta":
			return "模型正在输出分析与执行说明"
		"tool_requested":
			return "模型请求调用工具，等待工具结果"
		"artifact_ready":
			return "节点 " + str(payload.get("node", "")) + " 已生成结果，准备校验与预览"
		"completed":
			return "全部执行步骤已完成，生成结果已就绪"
		"failed":
			return "任务执行失败，完整错误与诊断信息已保留"
		"cancelled":
			return "任务已取消，已生成的结果和日志仍然保留"
		"progress":
			var states: Dictionary = payload.get("nodes", {})
			if states.is_empty(): return "任务已创建，正在等待执行器返回节点进度"
			var parts = PackedStringArray()
			for node_id in states:
				var node_state: Dictionary = states[node_id]
				parts.append(str(node_id) + "：" + state_label(str(node_state.get("state", ""))) + "（第 " + str(node_state.get("attempt", 0)) + " 次尝试）")
			return "节点进度｜" + "；".join(parts)
	return "收到运行事件：" + kind

func _record_runtime_event(event: Dictionary):
	_append_process_entry("运行事件", _runtime_event_summary(event), event)

func _refresh_process_views():
	if process_steps == null or process_logs == null: return
	var step_lines = PackedStringArray()
	var log_lines = PackedStringArray()
	for entry in process_entries:
		var details: Dictionary = entry.get("details", {})
		step_lines.append("[" + str(entry.time) + "] " + str(entry.summary))
		if entry.category == "运行事件":
			var text = str(details.get("text", ""))
			if not text.is_empty(): step_lines.append("  模型输出：\n" + text)
			var tools: Array = details.get("tool_requests", [])
			if not tools.is_empty(): step_lines.append("  工具请求：\n" + JSON.stringify(tools, "  ", true, true))
		log_lines.append("[" + str(entry.timestamp) + "] [" + str(entry.category) + "] " + str(entry.summary))
		if not details.is_empty(): log_lines.append(JSON.stringify(details, "  ", true, true))
	if step_lines.is_empty():
		process_steps.text = "尚无运行记录。运行节点后，这里会按时间显示任务计划、模型输出、工具调用、节点状态、结果和错误。"
	else:
		process_steps.text = "\n\n".join(step_lines)
	var diagnostic_path = state_dir.path_join("diagnostics.log")
	if FileAccess.file_exists(diagnostic_path):
		log_lines.append("===== 本机诊断日志（包含本次及此前记录）=====\n" + FileAccess.get_file_as_string(diagnostic_path))
	if log_lines.is_empty():
		process_logs.text = "暂无日志。运行记录和本机诊断日志会完整显示在这里。"
	else:
		process_logs.text = "\n\n".join(log_lines)
	process_steps.scroll_vertical = max(0, process_steps.get_line_count() - 1)
	process_logs.scroll_vertical = max(0, process_logs.get_line_count() - 1)

func _copy_process_logs():
	if process_logs == null: return
	_refresh_process_views()
	if DisplayServer.has_feature(DisplayServer.FEATURE_CLIPBOARD):
		DisplayServer.clipboard_set(process_logs.text)
		process_summary.text = "已复制全部会话日志和本机诊断日志"
	else:
		process_summary.text = "当前环境不支持系统剪贴板，请在“完整日志”中选择文本复制"

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
	var details = {"summary": summary, "raw_details": str(raw_details), "path": path}
	var output = FileAccess.open(path,FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
	if output==null:
		_append_process_entry("诊断", "本机诊断日志无法写入", details)
		return summary.trim_suffix('。')+'。本机诊断日志无法写入。'
	output.seek_end()
	output.store_line(Time.get_datetime_string_from_system(true)+' '+summary+'\n'+str(raw_details))
	output.close()
	_append_process_entry("诊断", "已记录本机诊断详情", details)
	return summary.trim_suffix('。')+'。可在“本机设置”中打开诊断日志。'

func open_diagnostics():
	var path = state_dir.path_join('diagnostics.log')
	if FileAccess.file_exists(path): OS.shell_open(path)
	else: status.text = '暂无本机诊断日志。'

func _refresh_workflow_tabs():
	if workflow_tabs == null: return
	workflow_tabs.clear_tabs()
	workflow_tabs.add_tab("制作 Mesh")
	workflow_tabs.set_tab_metadata(0, "")
	for template_id in custom_templates:
		var index = workflow_tabs.tab_count
		workflow_tabs.add_tab(template_name(template_id))
		workflow_tabs.set_tab_metadata(index, template_id)
	for index in workflow_tabs.tab_count:
		if str(workflow_tabs.get_tab_metadata(index)) == active_template_id:
			workflow_tabs.current_tab = index
			break
	_sync_template_chrome()

func _sync_template_chrome():
	if template_name_edit == null: return
	var editing = not active_template_id.is_empty() and custom_templates.has(active_template_id)
	template_name_edit.visible = editing
	template_rename_button.visible = editing
	template_name_edit.text = template_name(active_template_id) if editing else ""

func _capture_active_document():
	document_histories[active_template_id] = preview_history
	if active_template_id.is_empty():
		main_graph = {"nodes": nodes, "edges": edges}
	elif custom_templates.has(active_template_id):
		custom_templates[active_template_id].nodes = nodes
		custom_templates[active_template_id].edges = edges

func _workflow_tab_selected(index: int):
	if workflow_tabs == null or index < 0 or index >= workflow_tabs.tab_count: return
	switch_workflow_document(str(workflow_tabs.get_tab_metadata(index)))

func switch_workflow_document(template_id: String) -> bool:
	if template_id != active_template_id and is_graph_busy():
		status.text = "请等待当前运行结束或先取消，再切换流程页签"
		_refresh_workflow_tabs()
		return false
	if not template_id.is_empty() and not custom_templates.has(template_id): return false
	if template_id == active_template_id:
		_sync_template_chrome()
		return true
	if not selected_id.is_empty() and not apply_fields(): return false
	_capture_active_document()
	active_template_id = template_id
	var document = main_graph if template_id.is_empty() else custom_templates[template_id]
	nodes = document.get("nodes", [])
	edges = document.get("edges", [])
	preview_history = document_histories.get(template_id, {})
	selected_id = ""
	clear_preview()
	source_edit.text = ""
	context_edit.text = ""
	text_edit.text = ""
	parameter_form.configure("copy", {})
	_refresh_workflow_tabs()
	rebuild()
	refresh_history()
	if not nodes.is_empty(): select_node(nodes[0].id)
	status.text = "正在编辑主流程" if template_id.is_empty() else "正在编辑自定义流程模板：“%s”" % template_name(template_id)
	return true

func create_custom_template():
	if is_graph_busy():
		status.text = "请等待当前运行结束或先取消，再创建模板"
		return
	var id = "template_" + str(Time.get_ticks_usec())
	while custom_templates.has(id): id += "x"
	var number = custom_templates.size() + 1
	var name = "自定义流程模板 " + str(number)
	while custom_templates.values().any(func(item): return str(item.get("name", "")) == name):
		number += 1
		name = "自定义流程模板 " + str(number)
	custom_templates[id] = WorkflowTemplate.create_definition(id, name)
	_refresh_workflow_tabs()
	switch_workflow_document(id)

func rename_active_template(new_name: String):
	if active_template_id.is_empty() or not custom_templates.has(active_template_id): return
	var normalized = new_name.strip_edges()
	if normalized.is_empty():
		template_name_edit.text = template_name(active_template_id)
		status.text = "模板名称不能为空"
		return
	if custom_templates.values().any(func(item): return item.id != active_template_id and str(item.get("name", "")).strip_edges().to_lower() == normalized.to_lower()):
		template_name_edit.text = template_name(active_template_id)
		status.text = "已存在同名模板，请使用其他名称"
		return
	custom_templates[active_template_id].name = normalized
	_refresh_workflow_tabs()
	rebuild(false)
	status.text = "模板已改名为“%s”；已有引用保持不变" % normalized

func open_custom_template(template_id: String):
	if custom_templates.has(template_id): switch_workflow_document(template_id)

func _template_depends_on(candidate: String, target: String, visited: Array = []) -> bool:
	if candidate == target: return true
	if candidate in visited or not custom_templates.has(candidate): return false
	var branch = visited + [candidate]
	for node in custom_templates[candidate].get("nodes", []):
		if node.get("type", "") == CUSTOM_TEMPLATE and _template_depends_on(str(node.get("template_id", "")), target, branch): return true
	return false

func _template_can_insert(template_id: String) -> bool:
	return custom_templates.has(template_id) and not _template_depends_on(template_id, active_template_id)

func add_node():
	var id = "n" + str(Time.get_ticks_usec())
	nodes.append({"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": "", "image_context": "", "text": "", "parameters": {"delay": 2, "fail": false}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45})
	rebuild()
	select_node(id)

func add_generator():
	var kind = generator_choice.get_item_metadata(generator_choice.selected)
	var id = "n" + str(Time.get_ticks_usec())
	var data = {"id": id, "type": kind, "version": _new_node_version(kind), "provider": _generator_provider(kind), "source": "", "image_context": "", "text": "", "parameters": human_shape_default_parameters() if kind == HUMAN_SHAPE else HumanoidRigNode.default_parameters() if kind == HUMANOID_RIG else garment_split_default_parameters() if kind == GARMENT_SPLIT else {"prompt": "" if kind in ["image_to_mesh", "model_adjust"] else "白色背景上的小型石雕", "seed": 1}, "x": 40 + nodes.size() * 70, "y": 60 + nodes.size() * 45}
	if kind not in ['copy',HUMANOID_RIG,GARMENT_SPLIT] and _service_mode() in ['api_modeling', 'api_sculpt']: data.model = ''
	_migrate_node_models(data, service_draft())
	nodes.append(data)
	rebuild()
	select_node(id)

func _migrate_node_models(data: Dictionary, legacy: Dictionary):
	var kind = str(data.get('type', 'copy'))
	var mode = _service_mode()
	# Nodes created before the first saved service inherit once on that first save.
	if kind in ['copy',HUMANOID_RIG,GARMENT_SPLIT,CUSTOM_TEMPLATE,TEMPLATE_INPUT,TEMPLATE_OUTPUT] or _retired_mesh_node(data) or _using_legacy_service() or (service_saved.is_empty() and not data.has('model')): return
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
	var generating = kind not in ['copy',HUMANOID_RIG,GARMENT_SPLIT,CUSTOM_TEMPLATE,TEMPLATE_INPUT,TEMPLATE_OUTPUT] and not _retired_mesh_node(data) and not _using_legacy_service()
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
	if kind in ["model_adjust",HUMAN_SHAPE,HUMANOID_RIG,GARMENT_SPLIT]: return PORT_MESH
	return PORT_DYNAMIC

func output_kind(data: Dictionary) -> int:
	var kind = str(data.get("type", "copy"))
	if kind == HUMANOID_RIG: return PORT_CHARACTER
	if _queue_only_node(data): return PORT_IMAGE_SET
	return PORT_MESH if _is_mesh_kind(kind) else PORT_DYNAMIC if kind == "copy" else PORT_IMAGE

func port_type_name(kind: int) -> String:
	return {PORT_DYNAMIC:"图片 / Mesh", PORT_IMAGE:"图片", PORT_MESH:"Mesh", PORT_TEXT:"文本", PORT_IMAGE_SET:"图片队列", PORT_CHARACTER:"人形角色（17骨＋root）"}.get(kind, "未知")

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

func _latest_character_entry(node_id: String) -> Dictionary:
	var history: Array = preview_history.get(node_id, [])
	if history.is_empty(): return {}
	var entry = history.back()
	if not entry is Dictionary or entry.get("type", "") != "character": return {}
	return entry

func _reusable_character_entry(node_id: String) -> Dictionary:
	var entry = _latest_character_entry(node_id)
	if entry.is_empty() or not FileAccess.file_exists(str(entry.get("path", ""))): return {}
	var fingerprint = str(entry.get("cache_fingerprint", ""))
	if not fingerprint.is_empty() and fingerprint != _cache_fingerprint(node_id): return {}
	return entry

func _character_entry(node_id: String, token: String) -> Dictionary:
	for entry in preview_history.get(node_id,[]):
		if entry is Dictionary and entry.get("type","")=="character" and str(entry.get("token",""))==token: return entry
	return {}

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
	# Maximize, save and rigging actions require the target to be ready immediately.
	_show_artifact_result(key, index, true)
	if artifact_nodes.has(key) and artifact_nodes[key].get("kind","")=="character": _open_preview_rigging()
	elif _displayed_preview() != null: toggle_preview_maximized()
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
	var is_garment = str(entry.get("provenance", {}).get("artifact_role", "")) == "garment"
	var garment_label = str(entry.get("label", entry.get("provenance", {}).get("garment_label", "衣服")))
	var artifact_id = "artifact_%s_garment_%03d" % [source_id, attempt] if is_garment else "artifact_%s_round_%03d" % [source_id, attempt]
	while nodes.any(func(item): return item.id == artifact_id): artifact_id += "_dynamic"
	var node = GraphNode.new()
	node.name = artifact_id
	node.title = "◇ 衣服生成物 · " + garment_label if is_garment else "◇ Mesh 生成物 · 第 %d 轮" % attempt
	node.position_offset = Vector2(data.x + 340, data.y + (attempt - 1) * 180)
	node.tooltip_text = "双击放大这件衣服；可独立保存并作为固定衣服输入连接到下游节点" if is_garment else "双击放大本轮 Mesh；可独立保存并作为固定轮次输入连接到下游节点"
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
	if is_garment:
		var review_state = str(entry.get("provenance", {}).get("review_state", "needs_review"))
		review_text = {"automatic":"自动识别 · 待视觉审核", "confirmed":"选择已确认 · 待视觉审核", "needs_review":"需要审核选择"}.get(review_state, "待视觉审核")
		summary.text = garment_label + " · " + review_text
	else:
		summary.text = "动态节点 · 来自 %s · %s" % [source_id, review_text]
	summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(summary)
	node.set_slot(0, true, PORT_DYNAMIC, PORT_COLORS[PORT_MESH], true, PORT_DYNAMIC, PORT_COLORS[PORT_MESH])
	var thumbnail = preload("res://addons/ainative/mesh_artifact_preview.gd").new()
	thumbnail.name = "ArtifactMeshPreview"
	thumbnail.mouse_filter = Control.MOUSE_FILTER_STOP
	thumbnail.tooltip_text = "双击放大这件衣服" if is_garment else "双击放大本轮 Mesh"
	node.add_child(thumbnail)
	thumbnail.gui_input.connect(_artifact_preview_input.bind(key, 0, thumbnail))
	var preview_text = "旋转 / 缩放衣服" if is_garment else "旋转 / 缩放第 %d 轮 Mesh" % attempt
	var preview_button = button(node, preview_text, _show_artifact_result.bind(key))
	preview_button.name = "PreviewMeshArtifact"
	preview_button.tooltip_text = "在右侧旋转和缩放；双击直接放大"
	preview_button.gui_input.connect(_artifact_preview_input.bind(key, 0, preview_button))
	var save_text = "保存衣服 GLB…" if is_garment else "保存本轮 GLB…"
	var save_button = button(node, save_text, _save_mesh_artifact.bind(key))
	save_button.name = "SaveMeshArtifact"
	save_button.tooltip_text = "另存这件衣服的原始 GLB，不覆盖其他产物" if is_garment else "另存本轮原始 GLB，不覆盖其他轮次"
	graph.add_child(node)
	thumbnail.show_mesh(str(entry.get("path", "")))
	node.gui_input.connect(_artifact_preview_input.bind(key, 0, node))
	node.node_selected.connect(_show_artifact_result.bind(key))
	artifact_nodes[key] = {"id": artifact_id, "entry": entry, "source": source_id, "kind": "mesh", "attempt": attempt, "artifact_role": "garment" if is_garment else "iteration"}

func _create_character_artifact_node(data: Dictionary, entry: Dictionary):
	var source_id = str(data.id)
	var key = _mesh_artifact_key(source_id,entry)
	var artifact_id = "artifact_%s_character" % source_id
	while nodes.any(func(item): return item.id == artifact_id): artifact_id += "_dynamic"
	var node = GraphNode.new()
	node.name = artifact_id
	node.title = "◇ 人形17骨骼生成物"
	node.position_offset = Vector2(data.x + 340,data.y)
	node.tooltip_text = "17 根解剖骨＋独立 root；双击进入骨骼绑定页签"
	node.set_meta("maliang_artifact",true)
	node.set_meta("artifact_source",source_id)
	node.set_meta("artifact_key",key)
	_style_artifact_node(node)
	var summary = Label.new()
	summary.name = "ArtifactSummary"
	var limited = entry.get("provenance",{}).get("capability_limited",false)
	summary.text = "能力受限 · 可编辑但 ROM 未全通过" if limited else "ROM 已验证 · 可继续绑定调整"
	summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(summary)
	node.set_slot(0,true,PORT_DYNAMIC,PORT_COLORS[PORT_CHARACTER],false,0,PORT_COLORS[PORT_CHARACTER])
	var thumbnail = preload("res://addons/ainative/mesh_artifact_preview.gd").new()
	thumbnail.name = "ArtifactCharacterPreview"
	node.add_child(thumbnail)
	thumbnail.gui_input.connect(_artifact_preview_input.bind(key,0,thumbnail))
	var edit_button = button(node,"双击进入骨骼绑定",_open_character_artifact.bind(key))
	edit_button.name = "EditCharacterRig"
	edit_button.gui_input.connect(_artifact_preview_input.bind(key,0,edit_button))
	var save_button = button(node,"下载角色 .tscn…",_save_character_artifact.bind(key))
	save_button.name = "SaveCharacterArtifact"
	graph.add_child(node)
	thumbnail.show_character(str(entry.get("path","")))
	node.gui_input.connect(_artifact_preview_input.bind(key,0,node))
	node.node_selected.connect(_show_artifact_result.bind(key))
	artifact_nodes[key] = {"id":artifact_id,"entry":entry,"source":source_id,"kind":"character"}

func _open_character_artifact(key: String):
	_show_artifact_result(key, 0, true)
	_open_preview_rigging()

func _save_character_artifact(key: String):
	if not artifact_nodes.has(key) or artifact_nodes[key].get("kind","")!="character": return
	_show_artifact_result(key, 0, true)
	open_save_dialog()

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

func _show_artifact_result(key: String, index: int = 0, immediate: bool = false):
	if artifact_nodes.has(key) and artifact_nodes[key].get("kind", "image") in ["mesh","character"]:
		var record: Dictionary = artifact_nodes[key]
		var entry: Dictionary = record.entry
		# Artifact selection must not restore the source's latest preview first.
		select_node(record.source, false)
		var suffix = ""
		if record.get("kind","")=="mesh":
			suffix = " · 衣服 " + str(entry.get("label", "")) if record.get("artifact_role", "") == "garment" else " · 第 %d 轮" % int(record.get("attempt", 1))
		if immediate:
			load_preview(entry, record.source, str(entry.get("run", "")))
			if is_instance_valid(preview_scene): call_deferred("_reveal_mesh_preview")
			status.text += suffix
		else:
			_queue_preview_load(entry, record.source, str(entry.get("run", "")), false, 0, suffix, true)
		return
	var entry = _latest_image_entry(key)
	if entry.is_empty(): return
	select_node(key, false)
	if immediate: load_preview(entry, key, str(entry.get("run", "")), false, index)
	else: _queue_preview_load(entry, key, str(entry.get("run", "")), false, index)

func _save_mesh_artifact(key: String):
	if not artifact_nodes.has(key) or artifact_nodes[key].get("kind", "") != "mesh": return
	_show_artifact_result(key, 0, true)
	if preview_source_path.is_empty(): return
	var attempt = int(artifact_nodes[key].get("attempt", 1))
	var record: Dictionary = artifact_nodes[key]
	var name = "garment-%s-%s.glb" % [str(record.entry.get("provenance", {}).get("garment_id", "item")), str(record.entry.get("artifact", {}).get("revision", "")).left(12)] if record.get("artifact_role", "") == "garment" else "mesh-round-%03d-%s.glb" % [attempt, str(record.entry.get("artifact", {}).get("revision", "")).left(12)]
	open_save_dialog(name.validate_filename())

func _open_artifact_download(key: String):
	if artifact_nodes.has(key) and artifact_nodes[key].get("kind", "image") == "character":
		_save_character_artifact(key)
		return
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

func rebuild(layout_artifacts: bool = true):
	graph.clear_connections()
	artifact_nodes.clear()
	for child in graph.get_children():
		if child is GraphNode:
			graph.remove_child(child)
			child.queue_free()
	for data in nodes:
		var node = GraphNode.new()
		node.name = data.id
		node.title = data.id + " / " + _template_display_name(data)
		node.position_offset = Vector2(data.x, data.y)
		node.set_meta("maliang_template_boundary", WorkflowTemplate.is_fixed_node(data))
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
		var kind = str(data.get("type", "copy"))
		node.set_slot(1, kind != TEMPLATE_INPUT and input_kind(data) != PORT_TEXT, input_kind(data), PORT_COLORS[input_kind(data)], kind != TEMPLATE_OUTPUT, output_kind(data), PORT_COLORS[output_kind(data)])
		graph.add_child(node)
		if not WorkflowTemplate.is_boundary_kind(kind):
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
		if str(data.get("type",""))==HUMANOID_RIG:
			var character_entry = _latest_character_entry(source_id)
			var character_key = _mesh_artifact_key(source_id,character_entry) if not character_entry.is_empty() else ""
			if not character_entry.is_empty() and dismissed_artifacts.get(character_key,"")!=str(character_entry.get("token","")):
				_create_character_artifact_node(data,character_entry)
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
		if record.get("artifact_role", "") == "garment":
			# Every garment is an independent member of the collection, not a
			# sequential generation round. The formal result remains the collection.
			graph.connect_node(source_id, 0, str(record.id), 0)
		elif chain_index > 0:
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
		elif not mesh_chains.get(edge.from, []).is_empty() and str(source.get("type", "")) != GARMENT_SPLIT:
			var chain: Array = mesh_chains[edge.from]
			graph.connect_node(str(artifact_nodes[chain.back()].id), 0, edge.to, 0)
		else:
			graph.connect_node(edge.from, from_port, edge.to, 0)
	if layout_artifacts: _schedule_artifact_layout()

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

func _sync_structural_inspector(kind: String):
	var boundary = WorkflowTemplate.is_boundary_kind(kind)
	var structural = boundary or kind == CUSTOM_TEMPLATE
	for control in node_editor_controls:
		if structural:
			control.hide()
		elif control not in [node_model_label, node_model_choice, node_model_edit, node_image_model_label, node_image_model_choice, node_image_model_edit, text_edit]:
			control.show()
	boundary_hint.visible = boundary
	context_row.visible = not structural and kind != GARMENT_SPLIT
	template_edit_button.visible = kind == CUSTOM_TEMPLATE

func select_node(id: String, restore_preview: bool = true):
	var changed = selected_id != id
	selected_id = id
	var selected_kind = "copy"
	for data in nodes:
		if data.id == id:
			_clear_image_mesh_text(data)
			selected_kind = data.get("type", "copy")
			if selected_kind == HUMAN_SHAPE:
				data.parameters.erase("confirmed")
				data.parameters.erase("prompt")
				data.text = ""
				var old_landmarks = data.parameters.get("landmarks", {})
				if old_landmarks is Dictionary and (old_landmarks.is_empty() or (old_landmarks.size() == 1 and str(old_landmarks.get("source_sha256", "")).is_empty())):
					data.parameters.erase("landmarks")
					data.parameters.erase("reference_pose")
			_sync_node_model_controls(data)
			_sync_node_files(data)
			source_edit.text = " ; ".join(_node_paths(data, "source"))
			context_edit.text = " ; ".join(_node_paths(data, "image_context"))
			text_edit.visible = selected_kind == "copy"
			if selected_kind == "copy":
				text_edit.text = str(data.get("text", ""))
				parameter_form.configure(selected_kind, data.parameters)
			elif selected_kind in [HUMAN_SHAPE, HUMANOID_RIG, GARMENT_SPLIT]:
				# These structured nodes have no prompt/text parameter. Do not
				# manufacture an empty prompt which their invocation schema rejects.
				parameter_form.configure(selected_kind, data.parameters, str(data.get("version", "1")))
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
	_sync_structural_inspector(selected_kind)
	refresh_history()
	if changed:
		if not restore_preview:
			_invalidate_preview_requests()
		elif preview_history.get(id, []).is_empty():
			clear_preview()
		else:
			var entry: Dictionary = preview_history[id].back()
			_queue_preview_load(entry, id, str(entry.get("run", "")))

func apply_fields() -> bool:
	var selected = nodes.filter(func(node): return node.id == selected_id)
	if not selected.is_empty():
		var kind = str(selected[0].get("type", "copy"))
		if kind == CUSTOM_TEMPLATE or WorkflowTemplate.is_boundary_kind(kind): return true
	var params = parameter_form.parameters()
	if not params is Dictionary or not safe(params):
		_show_run_problem(parameter_form.error_label.text if not params is Dictionary else "参数含有禁止填写的凭据字段")
		return false
	for data in nodes:
		if data.id == selected_id:
			if data.get('type', 'copy') not in ['copy',HUMANOID_RIG,GARMENT_SPLIT] and not _retired_mesh_node(data) and not _using_legacy_service():
				var primary_name = node_model_edit.text.strip_edges()
				if _service_mode() in ['api_modeling', 'api_sculpt']: primary_name = node_model_edit.text
				if data.has('model') or not primary_name.is_empty(): data.model = primary_name
				if data.get('type', '') == 'text_to_mesh':
					var secondary_name = node_image_model_edit.text.strip_edges()
					if data.has('image_model') or not secondary_name.is_empty(): data.image_model = secondary_name
			_sync_node_files(data)
			if data.get("type", "copy") == "copy":
				data.text = text_edit.text
			elif data.get("type","") not in [HUMANOID_RIG,HUMAN_SHAPE,GARMENT_SPLIT]:
				# Keep the hidden control compatible with existing automation while
				# storing prompt-based requirements in the canonical prompt field.
				params["prompt"] = _merged_requirements(str(params.get("prompt", "")), text_edit.text)
				data.text = ""
			else:
				# Structured rig/shape nodes do not declare prompt or text inputs.
				params.erase("prompt")
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
		if record.get("kind", "image") == "character":
			status.text = "人形角色是终端预览产物，请双击进入骨骼绑定或使用下载按钮"
			return
		if record.get("kind", "image") != "mesh":
			status.text = "图片生成物请从正式图片节点连接下游"
			return
		if target_kind not in ["copy", "model_adjust",HUMAN_SHAPE,HUMANOID_RIG,GARMENT_SPLIT,CUSTOM_TEMPLATE,TEMPLATE_INPUT]:
			status.text = "Mesh 生成物只能连接到 Mesh 输入"
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
	if output_kind(source_node[0])==PORT_CHARACTER:
		status.text = "人形角色是终端预览产物，不能继续连接到执行节点"
		return
	var output = "image_set" if _queue_only_node(source_node[0]) or (_image_queue_node(source_node[0]) and from_port == 1) else "result"
	if output == "image_set":
		if not _accepts_image_set(target_node[0]):
			status.text = "目标节点不支持图片列表输入；请连接单张图片或选择支持图片列表的节点"
			return
	elif target_kind not in ["copy", CUSTOM_TEMPLATE, TEMPLATE_INPUT] and str(source_node[0].get("type", "")) not in [CUSTOM_TEMPLATE, TEMPLATE_OUTPUT] and ((_accepts_image_set(target_node[0]) and not _accepts_single_image(source_node[0], target_node[0])) or (not _accepts_image_set(target_node[0]) and output_kind(source_node[0]) != input_kind(target_node[0]))):
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
	if nodes.any(func(node): return node.id == selected_id and WorkflowTemplate.is_fixed_node(node)):
		status.text = "模板的固定输入输出节点不能删除"
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

func serialized_workflow() -> Dictionary:
	var document = model().duplicate(true) if active_template_id.is_empty() else {"format": 1, "nodes": main_graph.get("nodes", []).duplicate(true), "edges": main_graph.get("edges", []).duplicate(true)}
	var templates: Array = []
	for template_id in custom_templates:
		var definition = custom_templates[template_id].duplicate(true)
		for data in definition.nodes:
			_clear_image_mesh_text(data)
			_sync_node_files(data)
		templates.append(definition)
	if not templates.is_empty(): document["custom_templates"] = templates
	return document

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

func _template_cache_definition(template_id: String, visited: Array = []) -> Dictionary:
	if template_id in visited or not custom_templates.has(template_id): return {}
	var definition = custom_templates[template_id]
	var cached_nodes: Array = []
	for node in definition.get("nodes", []):
		var copy: Dictionary = node.duplicate(true)
		copy.erase("x")
		copy.erase("y")
		if copy.get("type", "") == CUSTOM_TEMPLATE:
			copy["template_definition"] = _template_cache_definition(str(copy.get("template_id", "")), visited + [template_id])
		cached_nodes.append(copy)
	return {"nodes": cached_nodes, "edges": definition.get("edges", []).duplicate(true)}

func _cache_fingerprint(node_id: String, graph_model: Dictionary = {}, visiting: Array = []) -> String:
	if graph_model.is_empty(): graph_model = model().duplicate(true)
	if node_id in visiting: return ""
	var matching = graph_model.get("nodes", []).filter(func(node): return str(node.get("id", "")) == node_id)
	if matching.is_empty(): return ""
	var definition: Dictionary = matching[0].duplicate(true)
	definition.erase("x")
	definition.erase("y")
	if definition.get("type", "") == CUSTOM_TEMPLATE: definition["template_definition"] = _template_cache_definition(str(definition.get("template_id", "")))
	for field in ["source", "image_context"]:
		var snapshots: Array = definition.get(field + "_snapshots", []).duplicate(true)
		if snapshots.is_empty() and definition.get(field + "_snapshot", {}) is Dictionary and not definition.get(field + "_snapshot", {}).is_empty(): snapshots = [definition.get(field + "_snapshot")]
		var paths = _node_paths(definition, field)
		var normalized: Array = []
		for index in maxi(paths.size(), snapshots.size()):
			var snapshot: Dictionary = {}
			var path = str(paths[index]) if index < paths.size() else ""
			if not path.is_empty() and FileAccess.file_exists(path):
				var digest = FileAccess.get_sha256(path)
				if not digest.is_empty(): snapshot = {"content_sha256": digest, "extension": "." + path.get_extension().to_lower()}
			if snapshot.is_empty() and index < snapshots.size() and snapshots[index] is Dictionary: snapshot = snapshots[index]
			if not snapshot.is_empty(): normalized.append({"content_sha256": str(snapshot.get("content_sha256", "")), "extension": str(snapshot.get("extension", ""))})
		definition[field + "_snapshots"] = normalized
		definition.erase(field + "_snapshot")
	var branch = visiting.duplicate()
	branch.append(node_id)
	var dependencies: Array = []
	for edge in graph_model.get("edges", []):
		if str(edge.get("to", "")) != node_id: continue
		var dependency = {"input": str(edge.get("input", "source")), "output": str(edge.get("output", "result"))}
		if edge.has("artifact"):
			dependency["artifact"] = edge.artifact.duplicate(true)
		else:
			dependency["from"] = str(edge.get("from", ""))
			dependency["fingerprint"] = _cache_fingerprint(dependency.from, graph_model, branch)
		dependencies.append(dependency)
	var hash_context = HashingContext.new()
	if hash_context.start(HashingContext.HASH_SHA256) != OK or hash_context.update(JSON.stringify({"node": definition, "dependencies": dependencies}, "", true, true).to_utf8_buffer()) != OK: return ""
	return hash_context.finish().hex_encode()

func _cached_output_asset(entry: Dictionary, node_id: String) -> Dictionary:
	var kind = str(entry.get("type", ""))
	var token = str(entry.get("token", ""))
	if kind not in ["image", "mesh"] or token.is_empty(): return {}
	var snapshot: Dictionary = entry.get("snapshot", {}).duplicate(true)
	if snapshot.is_empty(): snapshot = _snapshot_file(str(entry.get("path", "")))
	if not _valid_input_snapshots([snapshot]): return {}
	var extension = str(snapshot.get("extension", "")).to_lower()
	if kind == "image" and extension not in [".png", ".jpg", ".jpeg"]: return {}
	if kind == "mesh" and extension not in [".glb", ".gltf"]: return {}
	var reference = {"id": "cached-%s-%s" % [node_id, token], "revision": str(snapshot.content_sha256)}
	var payload = snapshot.duplicate(true)
	payload["provenance"] = entry.get("provenance", {}).duplicate(true)
	return {"reference": reference, "asset": {"id": reference.id, "revision": reference.revision, "type": kind, "payload": payload}}

func _cached_output(node_id: String, output: String) -> Dictionary:
	var history: Array = preview_history.get(node_id, [])
	if history.is_empty() or not history.back() is Dictionary: return {}
	var entry: Dictionary = history.back()
	var fingerprint = str(entry.get("cache_fingerprint", ""))
	if not fingerprint.is_empty() and fingerprint != _cache_fingerprint(node_id): return {}
	if output == "result":
		var primary = _cached_output_asset(entry, node_id)
		if primary.is_empty(): return {}
		return {"reference": primary.reference, "artifacts": [primary.asset]}
	if output != "image_set" or not entry.get("images", []) is Array or entry.get("images", []).is_empty(): return {}
	var artifacts: Array = []
	var items: Array = []
	for index in entry.images.size():
		var member = entry.images[index]
		if not member is Dictionary: return {}
		var cached = _cached_output_asset(member, node_id)
		if cached.is_empty(): return {}
		artifacts.append(cached.asset)
		items.append({"artifact": cached.reference, "label": str(member.get("label", "独立图片")), "index": index})
	var body = {"schema_version": 1, "items": items, "count": items.size()}
	var hash_context = HashingContext.new()
	if hash_context.start(HashingContext.HASH_SHA256) != OK or hash_context.update(JSON.stringify(body, "", true, true).to_utf8_buffer()) != OK: return {}
	var reference = {"id": "cached-%s-%s-image-set" % [node_id, str(entry.get("token", ""))], "revision": hash_context.finish().hex_encode()}
	var collection = {"id": reference.id, "revision": reference.revision, "type": "image_set", "payload": body, "dependencies": items.map(func(item): return item.artifact)}
	artifacts.append(collection)
	return {"reference": reference, "artifacts": artifacts}

func _has_reusable_cache(data: Dictionary) -> bool:
	var node_id = str(data.get("id", ""))
	var output = "image_set" if _queue_only_node(data) else "result"
	return not _cached_output(node_id, output).is_empty()

func execution_model(reuse_cache: bool = true, rerun_node: String = "") -> Dictionary:
	var executable = model().duplicate(true)
	var expanded = WorkflowTemplate.expand(executable, custom_templates)
	if not expanded.error.is_empty():
		status.text = expanded.error
		return {}
	executable.nodes = expanded.nodes
	executable.edges = expanded.edges
	template_target_aliases = expanded.target_aliases.duplicate(true)
	var boundary_ids = executable.nodes.filter(func(node): return WorkflowTemplate.is_boundary_kind(str(node.get("type", "")))).map(func(node): return str(node.id))
	executable.nodes = executable.nodes.filter(func(node): return not WorkflowTemplate.is_boundary_kind(str(node.get("type", ""))))
	executable.edges = executable.edges.filter(func(edge): return not (edge.from in boundary_ids or edge.to in boundary_ids))
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
	if not reuse_cache: return executable
	var cached: Dictionary = {}
	for data in executable.nodes:
		var node_id = str(data.id)
		if node_id != rerun_node and data.get("type", "") != HUMANOID_RIG and _has_reusable_cache(data): cached[node_id] = true
	# A cached node is reusable only when its whole dependency chain is also reusable.
	# Otherwise an invalidated upstream would disappear while its stale downstream remained.
	var changed = true
	while changed:
		changed = false
		for edge in executable.edges:
			if edge.has("artifact"): continue
			var source = str(edge.from)
			var target = str(edge.to)
			if cached.has(source) and _cached_output(source, str(edge.get("output", "result"))).is_empty():
				cached.erase(source)
				changed = true
			if cached.has(target) and not cached.has(source):
				cached.erase(target)
				changed = true
	var remaining: Array = []
	var remaining_ids: Array = []
	for data in executable.nodes:
		if cached.has(str(data.id)): continue
		remaining.append(data)
		remaining_ids.append(str(data.id))
	var planned_edges: Array = []
	for edge in executable.edges:
		if not remaining_ids.has(str(edge.to)): continue
		if cached.has(str(edge.from)) and not edge.has("artifact"):
			edge["cached_input"] = _cached_output(str(edge.from), str(edge.get("output", "result")))
		planned_edges.append(edge)
	executable.nodes = remaining
	executable.edges = planned_edges
	executable["reused_nodes"] = cached.keys()
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
	if entry.has("cache_fingerprint"): saved["cache_fingerprint"] = str(entry.cache_fingerprint)
	if saved.type=="character":
		var source_snapshot = entry.get("source_snapshot",{}).duplicate(true)
		if source_snapshot.is_empty(): return {}
		saved["source_snapshot"] = source_snapshot
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
	primary["cache_fingerprint"] = _cache_fingerprint(node_id)
	if references.size() > 1 or not image_set.is_empty(): primary["images"] = images
	if primary.get("type", "") == "mesh":
		var iterations: Array = []
		for artifact in _result_mesh_iterations(manifest, outputs.result):
			var reference = {"id": str(artifact.id), "revision": str(artifact.revision)}
			var saved = _snapshot_result_artifact(run_id, node_id, reference, artifact)
			if saved.is_empty(): return {}
			var provenance: Dictionary = artifact.payload.provenance
			var is_garment = str(provenance.get("artifact_role", "")) == "garment"
			saved["label"] = str(provenance.get("garment_label", "衣服")) if is_garment else "第 %d 轮" % int(provenance.get("generation_iteration", iterations.size() + 1))
			saved["attempt"] = int(provenance.get("generation_iteration", iterations.size() + 1))
			saved["review_passed"] = provenance.get("visual_review_passed", null)
			iterations.append(saved)
		if not iterations.is_empty(): primary["iterations"] = iterations
	return primary

func _snapshot_outputs(history_source = null, graph_nodes: Array = [], include_current: bool = true):
	var source: Dictionary = preview_history if history_source == null else history_source
	var graph = nodes if graph_nodes.is_empty() else graph_nodes
	var saved: Dictionary = {}
	for node_id in source:
		if not graph.any(func(node): return node.id == node_id): continue
		var history: Array = []
		for entry in source[node_id]:
			if not entry is Dictionary: return null
			var snapshot = _snapshot_output_entry(entry, str(node_id))
			if snapshot.is_empty(): return null
			history.append(snapshot)
		saved[node_id] = history
	for node_id in current.get("nodes", {}) if include_current else []:
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
	_capture_active_document()
	if path_edit.text.get_extension().to_lower() != "json":
		status.text = "工作流文件必须以 .json 结尾"
		return
	var portable = serialized_workflow()
	var snapshot_nodes: Array = portable.nodes.duplicate()
	for definition in portable.get("custom_templates", []): snapshot_nodes.append_array(definition.nodes)
	for n in snapshot_nodes:
		for field in ["source", "image_context"]:
			for path in _node_paths(n, field):
				if not path.is_empty() and path.simplify_path() == path_edit.text.simplify_path():
					status.text = "不能覆盖输入资源"
					return
	for n in snapshot_nodes:
		for field in ["source", "image_context"]:
			if not _snapshot_inputs(n, field):
				status.text = "无法读取输入并建立有序快照，已保留原工作流"
				return
	var output_history = _snapshot_outputs(preview_history, portable.nodes) if active_template_id.is_empty() else _snapshot_outputs(document_histories.get("", {}), portable.nodes, false)
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

func _valid_input_snapshots(value, uncapped: bool = false, extra_extensions: Array = []) -> bool:
	if not value is Array or (not uncapped and value.size() > 8): return false
	var allowed_extensions = [".png", ".jpg", ".jpeg", ".glb", ".gltf"]
	allowed_extensions.append_array(extra_extensions)
	for snapshot in value:
		if not snapshot is Dictionary: return false
		for key in ["content_base64", "content_sha256", "extension"]:
			if not snapshot.get(key) is String: return false
		if snapshot.extension.to_lower() not in allowed_extensions: return false
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
	if entry.has("cache_fingerprint") and not entry.cache_fingerprint is String: return false
	if entry.has("provenance") and not entry.provenance is Dictionary: return false
	if entry.node != node_id or entry.preview_token.is_empty() or not _valid_artifact_reference(entry.artifact): return false
	if not _valid_input_snapshots([entry.snapshot],false,[".tscn"]): return false
	var image = entry.type == "image" and entry.snapshot.extension.to_lower() in [".png", ".jpg", ".jpeg"]
	var mesh = entry.type == "mesh" and entry.snapshot.extension.to_lower() in [".glb", ".gltf"]
	var character = entry.type == "character" and entry.snapshot.extension.to_lower()==".tscn"
	if character:
		if not entry.get("source_snapshot") is Dictionary or not _valid_input_snapshots([entry.source_snapshot]): return false
		if entry.source_snapshot.extension.to_lower() not in [".glb",".gltf"] or entry.has("images") or entry.has("iterations"): return false
	if not image and not mesh and not character: return false
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
	if saved.has("cache_fingerprint"): entry["cache_fingerprint"] = saved.cache_fingerprint
	if saved.type=="character":
		var source_directory = directory.path_join("inputs")
		if DirAccess.make_dir_recursive_absolute(source_directory)!=OK: return null
		var source_path = _materialize_output_snapshot(saved.source_snapshot,source_directory)
		if source_path.is_empty(): return null
		entry["source_path"] = source_path
		entry["source_snapshot"] = saved.source_snapshot.duplicate(true)
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
	var source_kind = by_id[edge.from].get("type", "copy")
	if target_kind.begins_with("text_") or target_kind == TEMPLATE_INPUT or source_kind == TEMPLATE_OUTPUT: return false
	var output = edge.get("output", "result")
	if output_kind(by_id[edge.from])==PORT_CHARACTER: return false
	if edge.has("artifact"):
		return (
			output == "result"
			and target_kind in ["copy", "model_adjust",HUMAN_SHAPE,HUMANOID_RIG,CUSTOM_TEMPLATE,TEMPLATE_INPUT]
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
	var flexible = target_kind in ["copy", CUSTOM_TEMPLATE, TEMPLATE_INPUT] or source_kind in [CUSTOM_TEMPLATE, TEMPLATE_OUTPUT]
	return output == "result" and (flexible or (_accepts_image_set(by_id[edge.to]) and _accepts_single_image(by_id[edge.from], by_id[edge.to])) or (not _accepts_image_set(by_id[edge.to]) and output_kind(by_id[edge.from]) == input_kind(by_id[edge.to])))

func _validated_node_ids(graph: Dictionary, allow_boundaries: bool):
	var by_id: Dictionary = {}
	for n in graph.get("nodes", []):
		if not n is Dictionary or not n.has_all(["id", "source", "image_context", "text", "parameters", "x", "y"]):
			status.text = "节点无效"
			return null
		for key in ["id", "source", "image_context", "text"]:
			if not n[key] is String:
				status.text = "节点字段类型无效"
				return null
		if n.id.is_empty() or not n.id.is_valid_identifier() or by_id.has(n.id) or not n.parameters is Dictionary or not (n.x is float or n.x is int) or not (n.y is float or n.y is int):
			status.text = "节点标识、参数或位置无效"
			return null
		for key in ["type", "version", "provider", "model", "image_model", "template_id"]:
			if n.has(key) and not n[key] is String:
				status.text = "节点定义字段无效"
				return null
		if n.get("type", "copy") not in NODE_KINDS:
			status.text = "节点类型无效"
			return null
		if n.get("type", "") == HUMAN_SHAPE:
			var height_cm = n.parameters.get("height_cm", null)
			if (height_cm is float or height_cm is int) and not height_cm is bool and is_finite(height_cm) and height_cm == floor(height_cm):
				n.parameters.height_cm = int(height_cm)
		if WorkflowTemplate.is_boundary_kind(str(n.get("type", ""))) and not allow_boundaries:
			status.text = "固定输入输出节点只能存在于自定义流程模板中"
			return null
		if n.get("type", "") == CUSTOM_TEMPLATE and str(n.get("template_id", "")).is_empty():
			status.text = "模板实例缺少模板标识"
			return null
		if n.get("type", "copy") in ["text_to_image", "image_to_image"] and not n.has("version"): n.version = "2"
		var reviewed_mesh = n.get("type", "") == "image_to_mesh" and n.get("version", "1") == "2"
		for field in ["source", "image_context"]:
			var paths = n.get(field + "_paths", [])
			if not paths is Array or (not reviewed_mesh and paths.size() > 8) or paths.any(func(path): return not path is String):
				status.text = "输入路径列表无效"
				return null
			if n.has(field + "_snapshots") and not _valid_input_snapshots(n[field + "_snapshots"], reviewed_mesh):
				status.text = "输入快照列表无效"
				return null
			if not paths.is_empty() and not n.get(field + "_snapshots", []).is_empty() and paths.size() != n[field + "_snapshots"].size():
				status.text = "输入路径与快照的数量不一致"
				return null
			if n.has(field + "_snapshot") and not _valid_input_snapshots([n[field + "_snapshot"]]):
				status.text = "输入快照无效"
				return null
		by_id[n.id] = n
	return by_id

func _template_reference_error(graph: Dictionary, definitions: Dictionary, stack: Array = []) -> String:
	for node in graph.get("nodes", []):
		if node.get("type", "") != CUSTOM_TEMPLATE: continue
		var template_id = str(node.get("template_id", ""))
		if not definitions.has(template_id): return "模板实例引用了不存在的模板：" + template_id
		if template_id in stack: return "自定义流程模板存在循环引用"
		var nested = _template_reference_error(definitions[template_id], definitions, stack + [template_id])
		if not nested.is_empty(): return nested
	return ""

func open_graph():
	_invalidate_context()
	if creating or auto_step or not jobs.is_empty():
		status.text = "请等待当前运行结束或先取消，再打开工作流"
		return
	var value = JSON.parse_string(FileAccess.get_file_as_string(path_edit.text))
	if not value is Dictionary or not safe(value) or value.get("format") != 1 or not value.get("nodes") is Array or not value.get("edges") is Array:
		status.text = "工作流无效"
		return
	var loaded_templates: Dictionary = {}
	var template_values = value.get("custom_templates", [])
	if not template_values is Array:
		status.text = "自定义流程模板列表无效"
		return
	for definition in template_values:
		if not definition is Dictionary or not definition.get("id") is String or not definition.get("name") is String or definition.id.is_empty() or not definition.id.is_valid_identifier() or definition.name.strip_edges().is_empty() or loaded_templates.has(definition.id) or not definition.get("nodes") is Array or not definition.get("edges") is Array:
			status.text = "自定义流程模板定义无效"
			return
		if not WorkflowTemplate.has_valid_boundaries(definition) or _validated_node_ids(definition, true) == null: return
		var template_by_id: Dictionary = _validated_node_ids(definition, true)
		var template_destinations: Array = []
		for edge in definition.edges:
			if not edge is Dictionary or edge.has("artifact") or not _valid_workflow_edge(edge, template_by_id) or edge.to in template_destinations:
				status.text = "模板“%s”的连接端点或端口无效" % definition.name
				return
			template_destinations.append(edge.to)
		loaded_templates[definition.id] = definition
	var by_id = _validated_node_ids(value, false)
	if by_id == null: return
	var destinations = []
	for e in value.edges:
		if not e is Dictionary or not _valid_workflow_edge(e, by_id) or e.to in destinations:
			status.text = "连接端点或端口无效"
			return
		destinations.append(e.to)
	var reference_error = _template_reference_error(value, loaded_templates)
	for template_id in loaded_templates:
		if reference_error.is_empty(): reference_error = _template_reference_error(loaded_templates[template_id], loaded_templates, [template_id])
	if not reference_error.is_empty():
		status.text = reference_error
		return
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
	for definition in loaded_templates.values():
		var restored_template_inputs = _restore_missing_input_paths(definition.nodes, path_edit.text)
		if restored_template_inputs < 0:
			status.text = "无法恢复模板输入文件，已保留当前工作流"
			return
		recovered_inputs += restored_template_inputs
	var restored_history = _restore_output_history(saved_outputs, path_edit.text)
	if restored_history == null:
		status.text = "无法恢复生成物，已保留当前工作流"
		return
	preview_history = restored_history
	artifact_preview_queue.clear()
	humanoid_waiting.clear()
	dismissed_artifacts.clear()
	controller.reset()
	clear_preview()
	active_template_id = ""
	custom_templates = loaded_templates
	main_graph = {"nodes": value.nodes, "edges": value.edges}
	document_histories = {"": restored_history}
	nodes = value.nodes
	var legacy = service_draft()
	for data in nodes:
		if data.get("type", "") != CUSTOM_TEMPLATE: _migrate_node_models(data, legacy)
	for definition in custom_templates.values():
		for data in definition.nodes:
			if data.get("type", "") != CUSTOM_TEMPLATE and not WorkflowTemplate.is_boundary_kind(str(data.get("type", ""))): _migrate_node_models(data, legacy)
	edges = value.edges
	_refresh_workflow_tabs()
	# Older workflows did not store a definition fingerprint. Bind their restored
	# results to the definition at open time so later edits still invalidate them.
	for node_id in preview_history:
		for entry in preview_history[node_id]:
			if entry is Dictionary and str(entry.get("cache_fingerprint", "")).is_empty(): entry["cache_fingerprint"] = _cache_fingerprint(str(node_id))
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

func _reject_missing_run_resources(target: String = "", reuse_cache: bool = true) -> bool:
	var pending: Array = nodes.map(func(node): return str(node.id)) if target.is_empty() else [target]
	var visited: Array = []
	var missing: Array = []
	while not pending.is_empty():
		var node_id = str(pending.pop_back())
		if node_id in visited: continue
		visited.append(node_id)
		var matching = nodes.filter(func(node): return node.id == node_id)
		if matching.is_empty(): continue
		var data: Dictionary = matching[0]
		var local_cache = _reusable_character_entry(node_id) if data.get("type", "") == HUMANOID_RIG else {}
		if reuse_cache and node_id != target and (_has_reusable_cache(data) or (not local_cache.is_empty() and FileAccess.file_exists(str(local_cache.get("path", ""))))): continue
		for edge in edges:
			if edge.to == node_id and not edge.has("artifact"): pending.append(str(edge.from))
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

func _queue_humanoid_target(id: String, upstream: String):
	var waiting: Array = humanoid_waiting.get(upstream,[])
	if not waiting.has(id): waiting.append(id)
	humanoid_waiting[upstream] = waiting

func _direct_humanoid_input(id: String) -> Dictionary:
	var matching = nodes.filter(func(node): return node.id==id)
	if matching.is_empty(): return {}
	var incoming = edges.filter(func(edge): return edge.to==id)
	if incoming.is_empty():
		var paths = _node_paths(matching[0],"source")
		if paths.is_empty(): return {}
		var path = str(paths[0])
		return {"type":"mesh","path":path,"artifact":{"id":id+"-source","revision":FileAccess.get_sha256(path)},"provenance":{}}
	var edge: Dictionary = incoming[0]
	if not edge.has("artifact"): return {}
	return _find_output_entry(str(edge.from),edge.artifact)

func _run_humanoid_target(id: String):
	var incoming = edges.filter(func(edge): return edge.to==id and not edge.has("artifact"))
	if not incoming.is_empty():
		var upstream = str(incoming[0].from)
		var executable = execution_model(true, upstream)
		if executable.is_empty(): return
		var history: Array = preview_history.get(upstream, [])
		var cached: Dictionary = history.back() if not history.is_empty() else {}
		if upstream in executable.get("reused_nodes", []) and cached.get("type", "") == "mesh":
			controller.reset()
			status.text = "已复用上游 Mesh 缓存，仅重新创建当前节点的 17 根骨骼…"
			_execute_humanoid(id, cached)
			return
		_queue_humanoid_target(id,upstream)
		status.text = "正在运行上游 Mesh，完成后将在本机创建 17 根骨骼并检查变形…"
		_configure_controller()
		controller.start(executable,_execution_target(upstream))
		return
	var input_entry = _direct_humanoid_input(id)
	if input_entry.is_empty():
		_show_failure_dialog("请选择 GLB 或连接一个已生成的 Mesh。")
		return
	controller.reset()
	_execute_humanoid(id,input_entry)

func _humanoid_capability_notice(id: String, entry: Dictionary):
	var provenance: Dictionary = entry.get("provenance",{})
	var validation: Dictionary = provenance.get("validation",{})
	var text_review: Dictionary = provenance.get("text_review",{})
	var lines := PackedStringArray()
	lines.append("角色文件已保留并可继续编辑，但未通过完整的本地实测与文本审核。")
	lines.append("已完成最多三轮拟合与修复；这不是验收通过标记。请双击生成物进入骨骼绑定页签调整细节。")
	if not str(text_review.get("summary","")).is_empty(): lines.append("文本审核："+str(text_review.summary))
	var problems: Array = validation.get("issues",[])+validation.get("unsupported",[])
	for problem in problems: lines.append("• "+str(problem))
	for issue in text_review.get("issues",[]):
		if issue is Dictionary and not problems.has(issue.get("message","")): lines.append("• "+str(issue.get("message","")))
	var key = str(entry.get("run",""))+"/"+id+"/"+str(entry.get("token",""))
	if capability_notices.has(key): return
	capability_notices[key] = true
	capability_notice_dialog.dialog_text = "\n".join(lines)
	capability_notice_dialog.popup_centered(Vector2i(760,480))

func _clear_humanoid_review():
	humanoid_review_node = ""
	humanoid_review_source = ""
	humanoid_review_directory = ""
	humanoid_review_input = {}

func _start_humanoid_ai_review(id: String, input_entry: Dictionary, source_path: String):
	humanoid_review_node = id
	humanoid_review_source = source_path
	humanoid_review_input = input_entry.duplicate(true)
	humanoid_review_directory = state_dir.path_join("rigging-review").path_join((id+"-"+str(Time.get_ticks_usec())).validate_filename())
	status.text = "正在渲染全身和头部多视角，并调用 AI 检查是否适合标准人形绑骨…"
	failure_dialog.hide()
	launch("rigging-review",{
		"source":source_path,
		"directory":humanoid_review_directory,
		"godot_path":OS.get_executable_path(),
		"render_script":ProjectSettings.globalize_path(get_script().resource_path.get_base_dir().path_join("mesh_review.gd"))
	})

func _complete_humanoid_ai_review(data: Dictionary, request: Dictionary):
	if humanoid_review_node.is_empty() or request.get("directory","")!=humanoid_review_directory: return
	var id = humanoid_review_node
	var source_path = humanoid_review_source
	var input_entry = humanoid_review_input.duplicate(true)
	_clear_humanoid_review()
	var expected_sha = str(input_entry.get("artifact",{}).get("revision",""))
	if not FileAccess.file_exists(source_path) or FileAccess.get_sha256(source_path)!=expected_sha or data.get("source_sha256","")!=expected_sha:
		_show_failure_dialog("源模型在 AI 审核过程中发生变化，请重新运行。")
		return
	var matching = nodes.filter(func(node): return node.id==id and node.get("type","")==HUMANOID_RIG)
	if matching.is_empty():
		_show_failure_dialog("等待 AI 审核的骨骼节点已不存在，请重新运行。")
		return
	if data.get("passed",false)!=true:
		var issues = data.get("issues",[])
		var summaries = _capability_issue_summaries(issues if issues is Array else [])
		var message = "AI 视觉审核未通过，已停止绑骨。请使用完整、正面朝向、双臂展开且四肢分离的标准人形模型。\n\n"+"\n".join(summaries)
		status.text = message
		_show_run_problem(message)
		return
	var review = data.get("head_review",{})
	if not review is Dictionary or review.get("mode","")!="automatic" or review.get("ai_reviewed",false)!=true or review.get("source_sha256","")!=expected_sha:
		_show_failure_dialog("AI 审核返回的来源绑定无效，已停止绑骨。")
		return
	var parameters: Dictionary = matching[0].get("parameters",{}).duplicate(true)
	parameters.head_review = review.duplicate(true)
	matching[0].parameters = parameters
	if selected_id==id: parameter_form.configure(HUMANOID_RIG,parameters,"1")
	status.text = "AI 多视角审核通过，继续检查骨骼和实际变形。"
	_execute_humanoid(id,input_entry)

func _discard_humanoid_text_review():
	if not humanoid_text_review.is_empty():
		var scene = humanoid_text_review.get("result",{}).get("scene")
		if is_instance_valid(scene) and scene != preview_scene: scene.free()
	humanoid_text_review = {}

func _fail_humanoid_text_result(result: Dictionary, message: String):
	var scene = result.get("scene")
	if is_instance_valid(scene) and scene != preview_scene: scene.free()
	status.text = message
	_show_failure_dialog(message)

func _start_humanoid_text_review(id: String, input_entry: Dictionary, result: Dictionary):
	var directory = state_dir.path_join("rigging-text-review").path_join((id+"-"+str(Time.get_ticks_usec())).validate_filename())
	humanoid_text_review = {"node":id,"input":input_entry.duplicate(true),"result":result,"directory":directory}
	result.scene.hide()
	var attempts: Array = []
	for attempt in result.get("attempts",[]):
		attempts.append({"attempt":attempt.get("attempt",0),"repair":attempt.get("repair",""),"validation":attempt.get("validation",{}).duplicate(true),"error":attempt.get("error","")})
	status.text = "骨骼候选已保存并重载；正在将实测 JSON 送入纯文本审核，不发送截图…"
	failure_dialog.hide()
	if not humanoid_text_review_fixture.is_empty():
		var synthetic = humanoid_text_review_fixture.duplicate(true)
		synthetic.source_sha256 = str(result.source_sha256)
		synthetic.candidate_sha256 = str(result.sha256)
		_complete_humanoid_text_review(synthetic,{"directory":directory})
		return
	launch("rigging-text-review",{
		"source":str(input_entry.get("path","")),
		"candidate":str(result.path),
		"directory":directory,
		"validation":result.validation.duplicate(true),
		"attempts":attempts,
		"retry_count":attempts.size(),
		"max_retries":int(result.get("max_repair_attempts",HumanoidRigNode.DEFAULT_MAX_ATTEMPTS))
	})

func _complete_humanoid_text_review(data: Dictionary, request: Dictionary):
	if humanoid_text_review.is_empty() or request.get("directory","")!=humanoid_text_review.get("directory",""): return
	var pending = humanoid_text_review
	humanoid_text_review = {}
	var id = str(pending.node)
	var input_entry: Dictionary = pending.input
	var result: Dictionary = pending.result
	var source_path = str(input_entry.get("path",""))
	var candidate_path = str(result.get("path",""))
	var matching = nodes.filter(func(node): return node.id==id and node.get("type","")==HUMANOID_RIG)
	if matching.is_empty():
		_fail_humanoid_text_result(result,"等待文本审核的骨骼节点已不存在，请重新运行。")
		return
	var shape_valid = data.get("text_only",false)==true and data.get("passed") is bool and data.get("summary","") is String and data.get("issues",[]) is Array and data.get("feedback",[]) is Array
	var hashes_valid = FileAccess.file_exists(source_path) and FileAccess.file_exists(candidate_path) and FileAccess.get_sha256(source_path)==str(result.source_sha256) and FileAccess.get_sha256(candidate_path)==str(result.sha256)
	if not shape_valid or not hashes_valid or data.get("source_sha256","")!=str(result.source_sha256) or data.get("candidate_sha256","")!=str(result.sha256):
		_fail_humanoid_text_result(result,"文本审核回执无效，或候选在审核期间发生变化；本次结果未加入工作流。")
		return
	if not data.passed:
		var problems: Array = []
		for issue in data.get("issues",[]): problems.append(str(issue.get("message",issue)))
		var message = "纯文本审核未通过，已阻断正常角色交付；候选未加入工作流。\n"+str(data.get("summary",""))
		if not problems.is_empty(): message += "\n未解决问题：\n"+"\n".join(problems)
		_fail_humanoid_text_result(result,message)
		return
	result.capability_limited = false
	result.passed = result.get("validation",{}).get("passed",false)
	result.text_review = data.duplicate(true)
	_finish_humanoid(id,input_entry,result)

func _execute_humanoid(id: String, input_entry: Dictionary):
	var matching = nodes.filter(func(node): return node.id==id)
	if matching.is_empty(): return
	var source_path = str(input_entry.get("path",""))
	if input_entry.get("type","")!="mesh" or source_path.get_extension().to_lower() not in ["glb","gltf"] or not FileAccess.file_exists(source_path):
		var problem = "人形骨骼节点的输入必须是仍存在的 GLB／内嵌 glTF Mesh；请重新选择资源或运行上游 Mesh。"
		status.text = problem
		_show_failure_dialog(problem)
		return
	var parameters: Dictionary = matching[0].get("parameters",{}).duplicate(true)
	if parameters.has("head_review") and not parameters.head_review is Dictionary:
		_show_failure_dialog("AI 头脸验收记录格式无效，请清除后重新审核。")
		return
	var source_sha = FileAccess.get_sha256(source_path)
	var supplied_review = parameters.get("head_review",{})
	var invalidate_supplied = supplied_review is Dictionary and (supplied_review.get("mode","")=="manual" or supplied_review.get("manual_confirmation",false) or (supplied_review.get("ai_reviewed",false) and supplied_review.get("source_sha256","")!=source_sha))
	if invalidate_supplied:
		parameters.erase("head_review")
		matching[0].parameters = parameters
		if selected_id==id: parameter_form.configure(HUMANOID_RIG,parameters,"1")
		supplied_review = {}
	var contract = Rig.defaults(source_path)
	if supplied_review is Dictionary and not supplied_review.is_empty(): contract.head_review = supplied_review.duplicate(true)
	var existing_review = contract.get("head_review",{})
	if existing_review is Dictionary and existing_review.get("mode","")=="manual": existing_review = {}
	if not existing_review is Dictionary or existing_review.is_empty():
		_start_humanoid_ai_review(id,input_entry,source_path)
		return
	var head_problem = Rig.head_contract_error(contract)
	if not head_problem.is_empty():
		status.text = head_problem
		_show_failure_dialog(head_problem)
		return
	var directory = state_dir.path_join("humanoid-rig")
	if DirAccess.make_dir_recursive_absolute(directory)!=OK:
		_show_failure_dialog("无法创建本机角色输出目录："+directory)
		return
	var output_path = directory.path_join((id+"-"+str(Time.get_ticks_usec())+".tscn").validate_filename())
	status.text = "正在检查正视角人形、拟合 17 根解剖骨并执行抬臂／下蹲／转身验收…"
	var result = HumanoidRigNode.run(source_path,matching[0].get("parameters",{}),preview_root,output_path)
	if result.has("error"):
		status.text = str(result.error)
		_show_failure_dialog(status.text)
		return
	_start_humanoid_text_review(id,input_entry,result)

func _finish_humanoid(id: String, input_entry: Dictionary, result: Dictionary):
	var matching = nodes.filter(func(node): return node.id==id)
	if matching.is_empty():
		_fail_humanoid_text_result(result,"骨骼节点已不存在，无法发布文本审核候选。")
		return
	if result.get("capability_limited",false) or not result.get("passed",false) or not result.get("validation",{}).get("passed",false):
		_fail_humanoid_text_result(result,"本地实测或文本审核未通过，已阻断正常角色交付；候选未加入工作流。")
		return
	var source_path = str(input_entry.get("path",""))
	var source_snapshot = _snapshot_file(source_path)
	if source_snapshot.is_empty():
		_fail_humanoid_text_result(result,"无法保存源 GLB 快照，角色结果未加入工作流。")
		return
	var attempt_summaries: Array = []
	for attempt in result.get("attempts",[]):
		attempt_summaries.append({"attempt":attempt.get("attempt",0),"repair":attempt.get("repair",""),"validation":attempt.get("validation",{}).duplicate(true)})
	var result_run = run_id if not run_id.is_empty() else "local-"+str(result.sha256).left(12)
	var artifact = {"id":id+"-character","revision":str(result.sha256)}
	var entry = {
		"type":"character",
		"token":str(result.sha256),
		"path":str(result.path),
		"source_path":source_path,
		"source_snapshot":source_snapshot,
		"run":result_run,
		"node":id,
		"description":JSON.stringify(matching[0].get("parameters",{}),"  ",true,true),
		"artifact":artifact,
		"provenance":{
			"algorithm":"anatomical-segments-v1",
			"anatomical_bone_count":17,
			"independent_root":true,
			"source_sha256":str(result.source_sha256),
			"capability_limited":result.capability_limited,
			"passed":result.get("passed",false),
			"review_mode":"text_only",
			"validation":result.validation.duplicate(true),
			"text_review":result.get("text_review",{}).duplicate(true),
			"attempts":attempt_summaries,
			"original_model_not_overwritten":true
		}
	}
	remember_preview(entry,id,result_run)
	if selected_id==id:
		clear_preview()
		result.scene.show()
		preview_scene = result.scene
		preview_token = entry.token
		preview_run = result_run
		preview_node = id
		preview_source_path = entry.path
		preview_artifact = artifact.duplicate(true)
		rigging_panel.set_source(source_path)
		mesh_container.show()
		frame_mesh()
		_update_preview_maximize_controls()
	else:
		result.scene.free()
	status.text = "已生成 17 根解剖骨＋独立 root，并通过本地实测、保存重载与纯文本审核；双击角色进入绑定调整。"

func _execution_target(id: String) -> String:
	return str(template_target_aliases.get(id, id))

func _display_node_id(execution_id: String) -> String:
	for instance_id in template_target_aliases:
		if str(template_target_aliases[instance_id]) == execution_id: return str(instance_id)
	return execution_id

func run_node_preview(id: String):
	cache_full_run = false
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
	humanoid_waiting.clear()
	var selected = nodes.filter(func(node): return node.id==id)[0]
	if selected.get("type","")==HUMANOID_RIG:
		_run_humanoid_target(id)
		return
	var executable = execution_model(true, id)
	if executable.is_empty(): return
	var reused = executable.get("reused_nodes", []).size()
	var execution_target = _execution_target(id)
	for data in executable.nodes:
		if str(data.id) == execution_target: data["ignore_cache"] = true
	status.text = "正在运行选中节点，已复用 %d 个上游缓存结果…" % reused if reused > 0 else "正在运行选中节点及必要的上游节点…"
	_configure_controller()
	controller.start(executable, execution_target)

func request_run_all():
	if is_graph_busy():
		status.text = "正在运行，请等待结果或先取消"
		return
	if nodes.is_empty():
		status.text = "请先添加节点"
		return
	if not apply_fields(): return
	run_all_dialog.popup_centered(Vector2i(540, 220))

func confirm_run_all():
	if is_graph_busy(): return
	controller.reset()
	preview_history.clear()
	dismissed_artifacts.clear()
	artifact_preview_queue.clear()
	humanoid_waiting.clear()
	clear_preview()
	rebuild()
	start_run(true)

func start_run(force_rerun: bool = false):
	cache_full_run = true
	if is_graph_busy() or not apply_fields(): return
	if nodes.is_empty():
		status.text = "请先添加节点"
		return
	if _reject_missing_run_resources("", not force_rerun): return
	for data in nodes:
		if WorkflowTemplate.is_boundary_kind(str(data.get("type", ""))): continue
		var local_cache = _reusable_character_entry(str(data.id)) if data.get("type", "") == HUMANOID_RIG else {}
		if not force_rerun and (_has_reusable_cache(data) or (not local_cache.is_empty() and FileAccess.file_exists(str(local_cache.get("path", ""))))): continue
		var blocker = node_run_blocker(data.id)
		if not blocker.is_empty():
			_show_run_problem(blocker)
			return
	if service_config_link != null: service_config_link.hide()
	preview_token = ""
	artifact_preview_queue.clear()
	humanoid_waiting.clear()
	var executable = execution_model(not force_rerun)
	if executable.is_empty(): return
	var reused_nodes: Array = executable.get("reused_nodes", [])
	var local_inputs: Array = []
	for data in nodes:
		if data.get("type","")!=HUMANOID_RIG: continue
		var local_cache = _reusable_character_entry(str(data.id))
		if not force_rerun and not local_cache.is_empty(): continue
		var incoming = edges.filter(func(edge): return edge.to==data.id and not edge.has("artifact"))
		if not incoming.is_empty():
			var upstream = str(incoming[0].from)
			var upstream_entry: Dictionary = preview_history.get(upstream, []).back() if not preview_history.get(upstream, []).is_empty() else {}
			if not force_rerun and upstream in reused_nodes and upstream_entry.get("type", "") == "mesh":
				local_inputs.append([str(data.id), upstream_entry])
			else:
				_queue_humanoid_target(str(data.id),upstream)
		else:
			var input_entry = _direct_humanoid_input(str(data.id))
			if not input_entry.is_empty(): local_inputs.append([str(data.id),input_entry])
	var reused = reused_nodes.size()
	var local_node_ids = executable.nodes.filter(func(node): return node.get("type","")==HUMANOID_RIG).map(func(node): return str(node.id))
	executable.nodes = executable.nodes.filter(func(node): return node.get("type","")!=HUMANOID_RIG)
	executable.edges = executable.edges.filter(func(edge): return edge.from not in local_node_ids and edge.to not in local_node_ids)
	if force_rerun:
		for data in executable.nodes: data["ignore_cache"] = true
	_configure_controller()
	if not executable.nodes.is_empty():
		status.text = "正在运行 %d 个未缓存节点，已复用 %d 个缓存结果…" % [executable.nodes.size(), reused] if reused > 0 else "正在运行全部节点…" if force_rerun else "正在运行工作流…"
		controller.start(executable)
	else:
		controller.reset()
		if local_inputs.is_empty() and humanoid_waiting.is_empty(): status.text = "所有节点均已有结果缓存，本次运行直接完成，未重新生成。"
	for item in local_inputs: _execute_humanoid(item[0],item[1])

func resume_run():
	_configure_controller()
	controller.resume()

func cancel_run():
	preview_token = ""
	artifact_preview_queue.clear()
	humanoid_waiting.clear()
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
	controller.retry(_execution_target(selected_id))

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
	if data.get("state", "") not in ["succeeded", "failed"]: return
	for upstream in humanoid_waiting:
		var execution_id = _execution_target(str(upstream))
		var upstream_state = data.get("nodes",{}).get(execution_id,{})
		var already_loading = jobs.values().any(func(job): return job.command=="preview" and job.spec.get("node","")==execution_id)
		if upstream_state.get("state","")=="succeeded" and not artifact_preview_queue.has(execution_id) and not already_loading: artifact_preview_queue.append(execution_id)
	for data_node in nodes:
		var kind = str(data_node.get("type", ""))
		if (kind != "copy" or not cache_full_run) and not _is_image_kind(kind) and not _is_mesh_kind(kind) and kind != CUSTOM_TEMPLATE: continue
		var node_id = str(data_node.id)
		var execution_id = _execution_target(node_id)
		var state = data.get("nodes", {}).get(execution_id, {})
		if state.get("state", "") != "succeeded" or artifact_preview_queue.has(execution_id): continue
		var outputs = state.get("job", {}).get("outputs", {})
		if not outputs is Dictionary or (not outputs.has("image_set") and not outputs.has("result")): continue
		var already_loading = jobs.values().any(func(job): return job.command == "preview" and job.spec.get("node", "") == execution_id)
		if not already_loading: artifact_preview_queue.append(execution_id)

func _process(delta):
	controller.tick()
	_tick_preview_loading(delta)
	# Full-workflow runs also refresh every image artifact, not only a preview target.
	if not artifact_preview_queue.is_empty() and jobs.is_empty() and not creating and not auto_step and not run_id.is_empty():
		var node_id = str(artifact_preview_queue.pop_front())
		launch("preview", {"run": run_id, "node": node_id})

func _controller_failed(command: String, failure: Dictionary):
	if command in ["create","step","preview","retry"]: humanoid_waiting.clear()
	if command=="rigging-review":
		_clear_humanoid_review()
		if failure.code in ["api_key_missing","kimi_key_missing"]: failure.message = "AI 视觉审核需要可用的 KIMI_API_KEY。请在本机配置后重启马良；不会回退到人工确认。"
		elif failure.code=="review_render_failed": failure.message = "无法生成 AI 审核所需的多视角图像，请检查模型和当前引擎渲染环境。"
		elif failure.code in ["vision_output_invalid","api_output_invalid"]: failure.message = "AI 视觉审核返回的内容不完整或无效，请显式重试。"
	elif command=="rigging-text-review":
		_discard_humanoid_text_review()
		if failure.code in ["api_key_missing","kimi_key_missing"]: failure.message = "绑骨后的文本审核需要可用的 KIMI_API_KEY。请配置后显式重试；不会回退到简单检测判定。"
		elif failure.code in ["text_review_output_invalid","api_output_invalid"]: failure.message = "绑骨后的文本审核返回内容不完整或无效，候选未加入工作流。"
		elif failure.code in ["source_missing","candidate_missing","source_changed"]: failure.message = "文本审核所需的源模型或角色候选已不存在，请重新运行。"
		else: failure.message = "绑骨后的文本审核未完成，候选未加入工作流；请检查服务后显式重试。"
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
	elif command == "rigging-review":
		_complete_humanoid_ai_review(data,request)
	elif command == "rigging-text-review":
		_complete_humanoid_text_review(data,request)
	elif command == "preview":
		if request.run == run_id:
			var display_node = _display_node_id(str(request.node))
			remember_preview(data, display_node, request.run)
			if display_node == selected_id: load_preview(data, display_node, request.run)
			var targets: Array = humanoid_waiting.get(display_node,[]).duplicate()
			humanoid_waiting.erase(display_node)
			for target in targets: _execute_humanoid(str(target),data)
	elif command == "publish":
		status.text = "已发布新文件：" + data.path
		if Engine.is_editor_hint(): EditorInterface.get_resource_filesystem().scan()
	elif command != "create":
		if data.get("state","") in ["failed","cancelled"]: humanoid_waiting.clear()
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
	if not _latest_character_entry(selected_id).is_empty():
		show_history(preview_history[selected_id].size()-1)
		return
	if run_id.is_empty() or selected_id.is_empty():
		status.text = "请先点击节点的“运行并预览”"
		return
	if controller.has_command("preview"): return
	var execution_target = _execution_target(selected_id)
	if not current.get("nodes", {}).has(execution_target) or current.nodes[execution_target].state != "succeeded":
		status.text = "选中节点尚未生成成功，请点击“运行并预览”"
		return
	launch("preview", {"run": run_id, "node": execution_target})

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
		entry["cache_fingerprint"] = _cache_fingerprint(node_id)
		if str(entry.get("description","")).is_empty(): entry["description"] = JSON.stringify(current.get("nodes", {}).get(node_id, {}).get("request", {}), "  ", true, true)
		history.append(entry)
		preview_history[node_id] = history
	if node_id == selected_id: refresh_history()
	# An explicit new run restores previously dismissed result nodes.
	for key in dismissed_artifacts.keys():
		if key == node_id or str(key).begins_with(node_id + "::"): dismissed_artifacts.erase(key)
	if data.get("type", "") in ["image", "mesh","character"] or artifact_nodes.has(node_id): rebuild()

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
	_request_preview_redraw()
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
	_request_preview_redraw()
	_update_preview_maximize_controls()

func _image_preview_input(event: InputEvent):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and event.double_click:
		toggle_preview_maximized()
		texture.accept_event()

func _invalidate_preview_requests():
	preview_request_serial += 1
	preview_pending_request = {}
	preview_request_delay = 0.0

func is_preview_loading() -> bool:
	return not preview_pending_request.is_empty() or preview_worker_task >= 0

func _preview_is_current(data: Dictionary, node_id: String) -> bool:
	return preview_node == node_id and preview_token == str(data.get("token", "")) and preview_source_path == str(data.get("path", "")) and (preview_resource != null or is_instance_valid(preview_scene))

func _queue_preview_load(data: Dictionary, node_id: String, result_run: String = "", preserve_set: bool = false, image_index: int = 0, status_suffix: String = "", reveal_mesh: bool = false):
	_invalidate_preview_requests()
	var target = data
	var images: Array = data.get("images", [])
	if not preserve_set and image_index >= 0 and image_index < images.size(): target = images[image_index]
	if _preview_is_current(target, node_id):
		if not current_images.is_empty(): result_choice.select(image_index)
		if reveal_mesh and is_instance_valid(preview_scene): call_deferred("_reveal_mesh_preview")
		return
	preview_pending_request = {"serial": preview_request_serial, "data": data, "node_id": node_id, "result_run": result_run, "preserve_set": preserve_set, "image_index": image_index, "status_suffix": status_suffix, "reveal_mesh": reveal_mesh}
	# Coalesce click/drag bursts instead of starting one expensive decode per click.
	preview_request_delay = 0.04
	status.text = "正在加载预览…"

func _decode_preview(request: Dictionary) -> Dictionary:
	var data: Dictionary = request.data
	var kind = str(data.get("type", ""))
	var path = str(data.get("path", ""))
	if kind == "image":
		var image = Image.load_from_file(path)
		return {"image": image} if image != null else {"error": "图像预览失败"}
	if kind == "character":
		var packed = ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
		return {"packed": packed} if packed is PackedScene else {"error": "角色预览失败"}
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(path, state) != OK: return {"error": "网格预览失败"}
	return {"document": document, "state": state}

func _decode_preview_task(request: Dictionary):
	preview_worker_result = _decode_preview(request)

func _tick_preview_loading(delta: float):
	if preview_worker_task >= 0 and WorkerThreadPool.is_task_completed(preview_worker_task):
		WorkerThreadPool.wait_for_task_completion(preview_worker_task)
		preview_worker_task = -1
		var request = preview_active_request
		var decoded = preview_worker_result
		preview_active_request = {}
		preview_worker_result = {}
		if int(request.get("serial", -1)) == preview_request_serial:
			if decoded.has("error"):
				status.text = str(decoded.error)
			else:
				_present_preview(request.data, request.node_id, request.result_run, request.preserve_set, request.image_index, decoded, request.status_suffix)
				if request.get("reveal_mesh", false) and is_instance_valid(preview_scene): call_deferred("_reveal_mesh_preview")
	if not preview_pending_request.is_empty() and preview_worker_task < 0:
		preview_request_delay -= delta
		if preview_request_delay <= 0.0:
			preview_active_request = preview_pending_request
			preview_pending_request = {}
			preview_decode_count += 1
			preview_worker_task = WorkerThreadPool.add_task(_decode_preview_task.bind(preview_active_request), false, "Maliang preview decode")

func clear_preview():
	_invalidate_preview_requests()
	_clear_preview_view()

func _clear_preview_view():
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
	preview_continuous_render = false
	texture.texture = null
	texture.hide()
	mesh_container.hide()
	if is_instance_valid(viewport): viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	_update_preview_maximize_controls()

func show_result(index: int):
	if index < 0 or index >= current_images.size(): return
	var entry: Dictionary = current_images[index]
	result_choice.select(index)
	load_preview(entry, preview_node, preview_run, true)

func load_preview(data: Dictionary, node_id: String, result_run: String = "", preserve_set: bool = false, image_index: int = 0):
	_invalidate_preview_requests()
	var target = data
	var images: Array = data.get("images", [])
	if not preserve_set and image_index >= 0 and image_index < images.size(): target = images[image_index]
	if _preview_is_current(target, node_id): return
	_present_preview(data, node_id, result_run, preserve_set, image_index)

func _present_preview(data: Dictionary, node_id: String, result_run: String = "", preserve_set: bool = false, image_index: int = 0, decoded: Dictionary = {}, status_suffix: String = ""):
	if decoded.has("error"):
		status.text = str(decoded.error)
		return
	if not preserve_set:
		_clear_preview_view()
		current_images = data.get("images", []).duplicate(true)
		preview_run = run_id if result_run.is_empty() else result_run
		preview_node = node_id
		for index in current_images.size():
			var item: Dictionary = current_images[index]
			result_choice.add_item("%d. %s" % [index + 1, str(item.get("label", "独立图片"))])
		result_choice.visible = current_images.size() > 1
		if not current_images.is_empty():
			image_index = clampi(image_index, 0, current_images.size() - 1)
			data = current_images[image_index]
			result_choice.select(image_index)
	if decoded.is_empty(): preview_decode_count += 1
	if data.type == "image":
		var image: Image = decoded.get("image") if decoded.has("image") else Image.load_from_file(data.path)
		if image == null: status.text = "图像预览失败"; return
		preview_resource = ImageTexture.create_from_image(image)
		texture.texture = preview_resource
		texture.show()
	elif data.type=="character":
		var packed: PackedScene = decoded.get("packed") if decoded.has("packed") else ResourceLoader.load(str(data.path),"PackedScene",ResourceLoader.CACHE_MODE_IGNORE)
		if packed == null: status.text = "角色预览失败"; return
		preview_scene = packed.instantiate() as Node3D
		if preview_scene == null: return
		preview_root.add_child(preview_scene)
		rigging_panel.set_source(str(data.get("source_path","")))
		mesh_container.tooltip_text = "左键拖动旋转 · 中键拖动平移 · 滚轮缩放 · 双击进入骨骼绑定页签"
		mesh_container.show()
		preview_continuous_render = true
		frame_mesh()
	else:
		var document: GLTFDocument = decoded.get("document")
		var state: GLTFState = decoded.get("state")
		if document == null:
			document = GLTFDocument.new()
			state = GLTFState.new()
			if document.append_from_file(data.path, state) != OK: status.text = "网格预览失败"; return
		preview_scene = preload('res://addons/ainative/runtime_mesh.gd').generate(document,state)
		if preview_scene == null: return
		preview_root.add_child(preview_scene)
		rigging_panel.set_source(data.path)
		mesh_container.tooltip_text = "左键拖动旋转 · 中键拖动平移 · 滚轮缩放 · 双击最大化 / 还原预览"
		mesh_container.show()
		preview_continuous_render = false
		frame_mesh()
	preview_token = data.token
	preview_source_path = str(data.path)
	# Keep the exact result or iteration identity for save confirmation and publishing.
	preview_artifact = data.get("artifact", {}).duplicate(true)
	preview_run = run_id if result_run.is_empty() else result_run
	preview_node = node_id
	status.text = "已加载" + {"image":"图像", "mesh":"网格", "character":"人形角色（双击进入骨骼绑定）"}.get(data.type,data.type) + "预览，请检查后再发布" + status_suffix
	if not current_images.is_empty(): status.text += "；当前为“" + str(data.get("label", "独立图片")) + "”，共 " + str(current_images.size()) + " 张"
	_update_preview_maximize_controls()

func _open_preview_rigging():
	var character = _character_entry(preview_node,preview_token)
	if character.is_empty() or str(character.get("token",""))!=preview_token:
		status.text = "当前预览不是可编辑的人形角色"
		return
	var source_path = str(character.get("source_path",""))
	if source_path.is_empty():
		status.text = "角色缺少源 GLB，请重新打开工作流快照"
		return
	var character_path = preview_source_path
	show_native_section("rig")
	rigging_panel.open_character(character_path,source_path)

func _request_preview_redraw():
	if not is_instance_valid(viewport) or not is_instance_valid(mesh_container): return
	if not mesh_container.is_visible_in_tree():
		viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	else:
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS if preview_continuous_render else SubViewport.UPDATE_ONCE

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
	_request_preview_redraw()

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
			var character = _character_entry(preview_node,preview_token)
			if not character.is_empty() and str(character.get("token",""))==preview_token: _open_preview_rigging()
			else:
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
	_request_preview_redraw()
	mesh_container.accept_event()

func set_owners(node: Node, root: Node):
	for child in node.get_children():
		child.owner = root
		set_owners(child, root)

func open_save_dialog(suggested_name: String = ""):
	if preview_source_path.is_empty() or not FileAccess.file_exists(preview_source_path):
		status.text = "请先预览要保存的图像或网格"
		return
	var extension = preview_source_path.get_extension().to_lower()
	if extension.is_empty(): extension = "png" if preview_resource != null else "glb"
	save_picker.filters = ["*." + extension + " ; " + ("图像" if preview_resource != null else "人形角色" if extension=="tscn" and not _latest_character_entry(preview_node).is_empty() else "网格") + "生成物"]
	var project_dir = ProjectSettings.globalize_path("res://")
	var filename = preview_source_path.get_file() if suggested_name.is_empty() else suggested_name
	var directory = DirAccess.open(project_dir)
	if directory != null and directory.is_equivalent(preview_source_path, project_dir.path_join(filename)):
		filename = filename.get_basename() + "-export." + extension
	save_picker.current_dir = project_dir
	save_picker.current_file = filename
	save_picker.popup_centered_ratio(0.7)

func save_preview_to(path: String):
	if preview_source_path.is_empty() or not FileAccess.file_exists(preview_source_path):
		status.text = "生成物源文件已不可用，请重新预览后再保存"
		return
	var target = path
	if target.get_extension().is_empty(): target += "." + preview_source_path.get_extension().to_lower()
	var directory = DirAccess.open(preview_source_path.get_base_dir())
	if directory != null and directory.is_equivalent(preview_source_path, target):
		status.text = "所选位置是生成物源文件，请选择其他文件名或目录"
		return
	var err = DirAccess.copy_absolute(preview_source_path, target)
	if err != OK:
		status.text = "保存生成物失败：" + error_string(err)
		return
	status.text = "已保存生成物：" + target

func review_publish():
	if not _latest_character_entry(preview_node).is_empty():
		status.text = "人形角色已保存为 .tscn；请使用“保存生成物…”下载，或双击进入骨骼绑定后另存新版本"
		return
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
	_invalidate_preview_requests()
	if preview_worker_task >= 0:
		WorkerThreadPool.wait_for_task_completion(preview_worker_task)
		preview_worker_task = -1
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
	context_history_menu.visibility_changed.connect(_fit_history_menu)
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
		var local_cache = _reusable_character_entry(next_id) if data.get("type", "") == HUMANOID_RIG else {}
		if next_id != id and (_has_reusable_cache(data) or (not local_cache.is_empty() and FileAccess.file_exists(str(local_cache.get("path", ""))))): continue
		_clear_image_mesh_text(data)
		var kind: String = data.get("type", "copy")
		if WorkflowTemplate.is_boundary_kind(kind):
			if not active_template_id.is_empty() and next_id == WorkflowTemplate.INPUT_ID: continue
			return "固定输入输出节点只负责模板连接，不能单独运行"
		if kind == CUSTOM_TEMPLATE:
			if not custom_templates.has(str(data.get("template_id", ""))): return "引用的自定义流程模板不存在"
			var expanded = WorkflowTemplate.expand(model(), custom_templates)
			if not expanded.error.is_empty(): return expanded.error
		if _retired_mesh_node(data): return RETIRED_GPT_MESH_NOTICE
		var incoming = edges.filter(func(edge): return edge.to == next_id)
		for edge in incoming:
			if not edge.has("artifact"): pending.append(edge.from)
		if kind == CUSTOM_TEMPLATE: continue
		var has_images = not incoming.is_empty() or not _node_paths(data, "source").is_empty() or not _node_paths(data, "image_context").is_empty()
		if kind != GENERATE_IMAGE and not kind.begins_with("text_") and incoming.is_empty() and _node_paths(data, "source").is_empty():
			return "请先设置源文件或连接上游节点（" + str(next_id) + "）"
		for field in ["source", "image_context"]:
			for path in _node_paths(data, field):
				if not path.is_empty() and not FileAccess.file_exists(path):
					return ("源文件" if field == "source" else "参考图像") + "不存在（" + str(next_id) + "）"
		if kind==HUMANOID_RIG:
			for path in _node_paths(data,"source"):
				if not path.is_empty() and path.get_extension().to_lower() not in ["glb","gltf"]: return "创建人形17根骨骼需要 GLB／内嵌 glTF 模型（"+str(next_id)+"）"
		if kind==HUMAN_SHAPE:
			for path in _node_paths(data,"source"):
				if not path.is_empty() and path.get_extension().to_lower()!="glb": return "人形体态调整 V1 只接受绑骨前的静态 GLB（"+str(next_id)+"）"
		if kind==GARMENT_SPLIT:
			for path in _node_paths(data,"source"):
				if not path.is_empty() and path.get_extension().to_lower()!="glb": return "衣服拆分需要自包含 GLB；已绑骨和静态模型均可（"+str(next_id)+"）"
			var split_items = data.get("parameters", {}).get("items", [])
			if not split_items is Array or split_items.is_empty(): return "请在衣服拆分节点中配置至少一件衣服及其 component_id 或审核三角面"
		var reviewed_mesh = kind == "image_to_mesh" and data.get("version", "1") == "2"
		if not reviewed_mesh and (_is_image_kind(kind) or _accepts_image_set(data)) and _node_paths(data, "source").size() + _node_paths(data, "image_context").size() > 8:
			return "源图与参考图合计每次最多 8 张（" + str(next_id) + "）"
		var prompt = str(data.get("parameters", {}).get("prompt", "")) + "\n" + str(data.get("text", ""))
		if kind == GENERATE_IMAGE and not has_images and prompt.strip_edges().is_empty():
			return "请至少选择图片或填写生成提示词（" + str(next_id) + "）"
		if kind != GENERATE_IMAGE and not kind in ["copy", "image_to_mesh", "model_adjust",HUMAN_SHAPE,HUMANOID_RIG,GARMENT_SPLIT] and prompt.strip_edges().is_empty():
			return "请先填写生成提示词（" + str(next_id) + "）"
		var service_reason = _service_blocker(kind, data)
		if not service_reason.is_empty(): return service_reason
	return ""

func _retry_blocker(id: String) -> String:
	if is_graph_busy(): return "正在运行，请等待结束或先取消"
	if nodes.any(func(node): return node.id == id and _retired_mesh_node(node)): return RETIRED_GPT_MESH_NOTICE
	var state: Dictionary = current.get("nodes", {}).get(_execution_target(id), {})
	var job = state.get("job")
	if run_id.is_empty() or state.get("state") != "failed" or not job is Dictionary or job.get("state") != "failed":
		return "仅可重试原运行中已确认失败的节点"
	return ""

func _graph_menu_bounds() -> Rect2i:
	if get_viewport().gui_embed_subwindows:
		return Rect2i(get_viewport_rect())
	var host := get_window()
	return Rect2i(host.position, host.size)

func _fit_history_menu():
	if not context_history_menu.visible:
		return
	var bounds := _graph_menu_bounds()
	var pos := context_history_menu.position
	var left := context_menu.position.x - context_history_menu.size.x
	var right := context_menu.position.x + context_menu.size.x
	if pos.x + context_history_menu.size.x > bounds.end.x and left >= bounds.position.x:
		pos.x = left
	elif pos.x < bounds.position.x and right + context_history_menu.size.x <= bounds.end.x:
		pos.x = right
	context_history_menu.position = pos.clamp(bounds.position, bounds.end - context_history_menu.size)

func _popup_graph_menu(local_position: Vector2):
	var bounds := _graph_menu_bounds()
	context_menu.max_size = bounds.size
	context_history_menu.max_size = bounds.size
	context_menu.popup(Rect2i(Vector2i(graph.get_screen_transform() * local_position), Vector2i.ZERO))
	# PopupMenu applies its content scale and shadow during popup().
	var fitted := context_menu.position.clamp(bounds.position, bounds.end - context_menu.size)
	if fitted != context_menu.position:
		context_menu.position = fitted

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
			var character_artifact = artifact_nodes.has(context_artifact_source) and artifact_nodes[context_artifact_source].get("kind", "image") == "character"
			_context_item("下载角色 .tscn…" if character_artifact else "保存本轮 GLB…" if mesh_artifact else "下载全部到项目…", CONTEXT_ARTIFACT_DOWNLOAD)
			_context_item("删除生成物节点", CONTEXT_ARTIFACT_DELETE, "请等待当前运行结束或先取消" if is_graph_busy() else "")
			context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
			_popup_graph_menu(local_position)
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
		var has_result = not preview_history.get(id, []).is_empty() or current.get("nodes", {}).get(_execution_target(id), {}).get("state") == "succeeded"
		_context_item("查看已有结果", CONTEXT_PREVIEW, "该节点尚无成功结果" if not has_result else "")
		var history: Array = preview_history.get(id, [])
		for i in history.size():
			context_history_menu.add_item("版本 " + str(i + 1) + ("（最新）" if i == history.size() - 1 else ""), i)
			context_history_menu.set_item_tooltip(i, history[i].get("description", ""))
		context_menu.add_submenu_item("预览历史", "ContextHistory", CONTEXT_HISTORY)
		context_menu.set_item_disabled(context_menu.item_count - 1, history.is_empty())
		if history.is_empty(): context_menu.set_item_tooltip(context_menu.item_count - 1, "本次会话暂无该节点的预览版本")
		var context_data: Dictionary = nodes.filter(func(n): return n.id == id)[0]
		var context_kind = str(context_data.get("type", "copy"))
		var fixed_reason = "模板的固定输入输出节点不能编辑参数、复制或删除" if WorkflowTemplate.is_fixed_node(context_data) else ""
		_context_item("编辑自定义模板" if context_kind == CUSTOM_TEMPLATE else "编辑参数" if context_kind == "image_to_mesh" else "编辑提示词与参数", CONTEXT_EDIT, fixed_reason)
		_context_item("重试节点", CONTEXT_RETRY, fixed_reason if not fixed_reason.is_empty() else _retry_blocker(id))
		context_menu.add_separator()
		_context_item("复制节点", CONTEXT_DUPLICATE, busy_reason if fixed_reason.is_empty() else fixed_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_MASK_CMD_OR_CTRL | KEY_D)
		_context_item("删除节点", CONTEXT_DELETE, busy_reason if fixed_reason.is_empty() else fixed_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
	elif context_node_ids.size() > 1:
		context_menu.add_separator("已选择 " + str(context_node_ids.size()) + " 个节点")
		var fixed_reason = "选择中包含固定的模板输入输出节点，不能批量复制或删除" if nodes.any(func(node): return node.id in context_node_ids and WorkflowTemplate.is_fixed_node(node)) else ""
		_context_item("复制选中节点", CONTEXT_DUPLICATE, busy_reason if fixed_reason.is_empty() else fixed_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_MASK_CMD_OR_CTRL | KEY_D)
		_context_item("删除选中节点", CONTEXT_DELETE, busy_reason if fixed_reason.is_empty() else fixed_reason)
		context_menu.set_item_accelerator(context_menu.item_count - 1, KEY_DELETE)
	elif not context_connection.is_empty():
		_context_item("断开连接", CONTEXT_DISCONNECT, busy_reason)
	else:
		_context_item("添加节点…", CONTEXT_ADD, busy_reason)
		context_menu.add_separator()
		_context_item("保存工作流…", CONTEXT_SAVE)
		_context_item("打开工作流…", CONTEXT_OPEN, busy_reason)
		_context_item("运行整个工作流", CONTEXT_RUN_ALL, busy_reason if not busy_reason.is_empty() else ("请先添加节点" if nodes.is_empty() else ""))
	_popup_graph_menu(local_position)

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
				if not creating and current.get("nodes", {}).get(_execution_target(id), {}).get("state") == "succeeded": request_preview()
				elif not preview_history.get(id, []).is_empty(): show_history(preview_history[id].size() - 1)
		CONTEXT_HISTORY:
			if context_node_ids.size() == 1 and not preview_history.get(context_node_ids[0], []).is_empty():
				history_choice.grab_focus()
				status.text = "在预览历史子菜单或右侧版本列表选择结果"
		CONTEXT_EDIT:
			if context_node_ids.size() == 1:
				var selected = nodes.filter(func(node): return node.id == context_node_ids[0])[0]
				if selected.get("type", "") == CUSTOM_TEMPLATE:
					open_custom_template(str(selected.get("template_id", "")))
					return
				if WorkflowTemplate.is_fixed_node(selected): return
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
	for group in [["图像生成", [GENERATE_IMAGE]], ["网格生成", ["image_to_mesh", "text_to_mesh"]], ["模型处理", ["model_adjust", HUMAN_SHAPE, GARMENT_SPLIT]], ["骨骼工具", [HUMANOID_RIG]], ["离线工具", ["copy"]]]:
		var matches: Array = []
		for kind in group[1]:
			if search.is_empty() or search in (node_label(kind) + " " + kind + " " + group[0]).to_lower(): matches.append(kind)
		if matches.is_empty(): continue
		node_picker_list.add_item(group[0])
		node_picker_list.set_item_selectable(node_picker_list.item_count - 1, false)
		for kind in matches:
			node_picker_list.add_item("  " + node_label(kind))
			node_picker_list.set_item_metadata(node_picker_list.item_count - 1, kind)
	var template_matches: Array = []
	for template_id in custom_templates:
		if _template_can_insert(template_id) and (search.is_empty() or search in (template_name(template_id) + " 自定义流程模板 " + template_id).to_lower()): template_matches.append(template_id)
	if not template_matches.is_empty():
		node_picker_list.add_item("自定义流程模板")
		node_picker_list.set_item_selectable(node_picker_list.item_count - 1, false)
		for template_id in template_matches:
			node_picker_list.add_item("  " + template_name(template_id))
			node_picker_list.set_item_metadata(node_picker_list.item_count - 1, CUSTOM_TEMPLATE + ":" + template_id)
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
	var template_id = ""
	if kind.begins_with(CUSTOM_TEMPLATE + ":"):
		template_id = kind.trim_prefix(CUSTOM_TEMPLATE + ":")
		kind = CUSTOM_TEMPLATE
		if not _template_can_insert(template_id):
			status.text = "不能把模板添加到自身或形成循环引用"
			return
	if not kind in NODE_KINDS or WorkflowTemplate.is_boundary_kind(kind) or is_graph_busy() or not _context_is_current(): return
	if kind == CUSTOM_TEMPLATE and template_id.is_empty(): return
	if not selected_id.is_empty() and not apply_fields(): return
	var position = (context_position + graph.scroll_offset) / graph.zoom
	var id = "n" + str(Time.get_ticks_usec())
	while not nodes.filter(func(n): return n.id == id).is_empty(): id += "x"
	var data = {"id": id, "type": kind, "version": _new_node_version(kind), "provider": "workflow-template" if kind == CUSTOM_TEMPLATE else _generator_provider(kind), "source": "", "image_context": "", "text": "", "parameters": {} if kind == CUSTOM_TEMPLATE else human_shape_default_parameters() if kind==HUMAN_SHAPE else HumanoidRigNode.default_parameters() if kind==HUMANOID_RIG else garment_split_default_parameters() if kind==GARMENT_SPLIT else {"delay": 2, "fail": false} if kind == "copy" else {"prompt": "" if kind in ["image_to_mesh", "model_adjust"] else "白色背景上的小型石雕", "seed": 1}, "x": position.x, "y": position.y}
	if kind == CUSTOM_TEMPLATE: data.template_id = template_id
	if kind not in ['copy',HUMANOID_RIG,GARMENT_SPLIT,CUSTOM_TEMPLATE] and _service_mode() in ['api_modeling', 'api_sculpt']: data.model = ''
	if kind != CUSTOM_TEMPLATE: _migrate_node_models(data, service_draft())
	nodes.append(data)
	node_picker.hide()
	context_menu.hide()
	# Adding a formal node must not re-layout existing artifacts and move it away from the pointer.
	rebuild(false)
	for child in graph.get_children():
		if child is GraphNode: child.selected = str(child.name) == id
	select_node(id)
	status.text = "已在右键位置添加“" + _template_display_name(data) + "”节点"

func duplicate_context_nodes() -> Array:
	if is_graph_busy() or not _context_is_current() or context_node_ids.is_empty(): return []
	if nodes.any(func(node): return node.id in context_node_ids and WorkflowTemplate.is_fixed_node(node)):
		status.text = "模板的固定输入输出节点不能复制"
		return []
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
	if nodes.any(func(node): return node.id in context_node_ids and WorkflowTemplate.is_fixed_node(node)):
		status.text = "模板的固定输入输出节点不能删除"
		return
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
	service_status.text = "请选择生成服务；本机复制、人形骨骼和衣服拆分节点始终可用，配置草稿会自动保存。"
	service_fields.add_child(service_status)
	for kind in NODE_KINDS:
		if kind in [HUMANOID_RIG,GARMENT_SPLIT]: continue
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
	if kind == CUSTOM_TEMPLATE: return '可复用流程 · 点击右侧按钮独立编辑'
	if kind == TEMPLATE_INPUT: return '连接模板外部输入 · 固定节点'
	if kind == TEMPLATE_OUTPUT: return '连接模板最终输出 · 固定节点'
	if _retired_mesh_node(data): return node_label(kind) + ' · GPT CLI 网格已下线'
	if kind == HUMANOID_RIG: return '本机解剖模板 · 17 根解剖骨＋root · 实际 ROM 检查'
	if kind == GARMENT_SPLIT: return '本机几何提取 · 已绑骨优先 · 保留原骨架和蒙皮'
	if kind == 'copy': return '本机离线复制'
	var selected_model = str(data.get('model', '')) if not _using_legacy_service() else '高级自定义服务'
	var description = node_label(kind) + ' · ' + (selected_model if not selected_model.is_empty() else 'CLI 默认／待选择模型')
	if _service_mode() in ['api_modeling', 'api_sculpt']: description += ' · 自选 API 语义规划'
	elif _service_mode() == 'local_mesh': description += ' · 本机网格'
	elif _service_mode() == 'kimi_native': description += ' · 本地绑骨前几何形变' if kind == HUMAN_SHAPE else ' · Tripo API 直接 3D' if _is_mesh_kind(kind) else ' · Kimi Work 图像服务'
	return description

func _generator_provider(kind: String) -> String:
	if kind == 'copy': return 'local-copy'
	if kind == HUMANOID_RIG: return 'local-humanoid-rig'
	if kind == GARMENT_SPLIT: return 'garment-split'
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
	if kind in ["copy",HUMANOID_RIG,GARMENT_SPLIT] or _using_legacy_service(): return ""
	if _is_mesh_kind(kind) and managed_comfy_panel != null and _service_mode() in ['codex', 'local_mesh']:
		var bundle_problem: String = managed_comfy_panel.bundled_mesh_blocker()
		if not bundle_problem.is_empty(): return bundle_problem
	if _service_mode() not in SERVICE_PROFILE_MODES:
		return "请选择一种生成服务，再保存配置。"
	if kind == 'model_adjust' and _service_mode() != 'kimi_native':
		return '模型调整目前使用 Kimi Native / Tripo API，请先在 AI 设置中选择 Kimi Native。'
	if kind == HUMAN_SHAPE and _service_mode() != 'kimi_native':
		return '人形体态调整复用 Kimi Native 的本地几何运行时，不调用 Tripo API；请先选择并配置 Kimi Native。'
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
