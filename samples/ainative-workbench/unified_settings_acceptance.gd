extends SceneTree
# Synthetic controls/configuration only: never launches a host, CLI or model.
var panel
var failures = 0
var checks: Array = []
var requests: Array = []
var central: VBoxContainer
var state_path = ''

func check(ok: bool, label: String):
	checks.append({'passed':ok, 'label':label})
	print(('PASS ' if ok else 'FAIL ') + label)
	if not ok: failures += 1

func _initialize(): run.call_deferred()

func settle():
	for i in 4: await process_frame

func write_text(path: String, value: String):
	var file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(value)
	file.close()

func find_button(control: Node, text: String) -> Button:
	for child in control.get_children():
		if child is Button and child.text == text: return child
		var found = find_button(child, text)
		if found != null: return found
	return null

func new_panel(builtin: bool = true):
	panel = load('res://addons/ainative/workbench.gd').new()
	panel.state_dir = state_path
	panel.set_meta('ainative_builtin', builtin)
	panel.set_meta('ainative_tools_dir', state_path.path_join('bundled-tools'))
	panel.settings_requested.connect(func(section): requests.append(section))
	root.add_child(panel)
	await settle()

func mount_sections() -> Dictionary:
	var sections: Dictionary = panel.get_settings_sections()
	for control in sections.values():
		control.reparent(central)
		control.show()
	return sections

func run():
	state_path = OS.get_environment('AINATIVE_SETTINGS_TEST_DIR').replace('\\', '/')
	if state_path.is_empty():
		check(false, 'an explicit isolated fixture directory is required')
		finish()
		return
	DirAccess.make_dir_recursive_absolute(state_path)
	var local = ConfigFile.new()
	local.set_value('host', 'python', 'fixture-old-maliang-python')
	local.set_value('host', 'script', 'fixture-old-editor-host.py')
	local.set_value('host', 'use_bundled_script', false)
	local.set_value('host', 'factory', 'editor_demo:factory')
	local.set_value('service', 'cli_path', 'fixture-old-local-cli')
	local.set_value('managed_comfy', 'runtime_root', state_path.path_join('fixture-runtime'))
	local.set_value('managed_comfy', 'autostart', false)
	local.save(state_path.path_join('local.cfg'))
	var saved = {'schema_version':1, 'mode':'codex', 'endpoint':'http://127.0.0.1:8188', 'image_model':'builtin', 'mesh_model':'fixture-mesh', 'cli_path':'fixture-old-service-cli'}
	write_text(state_path.path_join('generation-service.json'), JSON.stringify(saved))
	central = VBoxContainer.new()
	root.add_child(central)
	await new_panel()
	check(panel.python_edit.text == 'fixture-old-maliang-python' and panel.host_edit.text == 'fixture-old-editor-host.py', 'existing host Python and script values survive without storage migration')
	check(panel.cli_path_edit.text == 'fixture-old-service-cli', 'existing Codex task-service snapshot retains precedence over local fallback')
	check(panel.managed_comfy_panel.runtime_path.text == state_path.path_join('fixture-runtime'), 'existing managed runtime value survives')
	check(panel.serial == 0 and panel.jobs.is_empty(), 'loading restored settings launches no subprocess or model')
	var ai_id = panel.service_fields.get_instance_id()
	var python_id = panel.python_edit.get_instance_id()
	var managed = panel.managed_comfy_panel
	var lease = state_path.path_join('fixture-lease')
	write_text(lease, '1')
	managed.lease_path = lease
	var sections = mount_sections()
	await settle()
	check(sections.keys().size() == 2 and sections.has('ai') and sections.has('environment'), 'native contract exposes exactly AI and environment sections')
	check(sections.ai == panel.service_fields and sections.ai.get_instance_id() == ai_id, 'central AI uses the existing service form instance')
	check(sections.ai.is_ancestor_of(panel.service_choice) and sections.ai.is_ancestor_of(panel.endpoint_edit), 'service mode and endpoint are grouped in AI')
	check(not panel.image_model_choice.is_visible_in_tree() and not panel.mesh_model_choice.is_visible_in_tree() and not panel.kimi_model_edit.is_visible_in_tree(), 'legacy global model selectors stay hidden in access settings')
	check(not sections.ai.is_ancestor_of(panel.node_model_edit) and not sections.ai.is_ancestor_of(panel.node_image_model_edit), 'node model editors are not duplicated into central settings')
	check(sections.environment.is_ancestor_of(panel.python_edit) and sections.environment.is_ancestor_of(panel.cli_path_edit) and sections.environment.is_ancestor_of(managed), 'Python, CLI and local runtime manager are grouped in environment')
	check(panel.get_settings_sections().environment == sections.environment and panel.python_edit.get_instance_id() == python_id, 'repeated API reads return stable controls without duplicate forms')
	check(not panel.is_ancestor_of(sections.ai) and not panel.is_ancestor_of(sections.environment), 'native business tree no longer owns editable settings while centrally mounted')
	check(FileAccess.file_exists(lease) and managed.lease_path == lease, 'moving environment into central settings preserves the managed runtime lease')
	var checked = panel.service_draft().duplicate(true)
	var report = {'connected':true, 'message':'synthetic discovery report', 'models':{'image':['builtin'], 'mesh':['fixture-mesh']}, 'capabilities':{}}
	panel._apply_service_check(report, checked)
	var report_draft = panel.service_report_draft
	panel.show_native_section('rig')
	sections.ai.hide()
	sections.environment.hide()
	sections.ai.show()
	sections.environment.show()
	sections.environment.reparent(root)
	sections.environment.reparent(central)
	await settle()
	check(panel.service_report.get('connected', false) and panel.service_report_draft == report_draft, 'business and central page switches preserve discovery state')
	check(FileAccess.file_exists(lease) and managed.lease_path == lease, 'central page switches and repeated reparent preserve the runtime lease')
	panel.native_buttons.settings.pressed.emit()
	check(requests.back() == 'environment' and panel.native_buttons.rig.button_pressed and not panel.native_sections.machine.visible, 'old local-settings button requests central environment without switching business section')
	panel.service_settings_section = 'ai'
	panel.service_config_link.pressed.emit()
	check(requests.back() == 'ai', 'service configuration entry requests central AI')
	var service_before = FileAccess.get_file_as_string(panel.service_config_path)
	panel.creating = true
	panel.run_id = 'fixture-in-flight-task'
	find_button(sections.ai, '保存生成服务设置').pressed.emit()
	panel.show_native_section('settings')
	check(panel.creating and panel.run_id == 'fixture-in-flight-task' and FileAccess.get_file_as_string(panel.service_config_path) == service_before, 'central navigation and save preserve the in-flight task and stored service snapshot')
	panel.creating = false
	panel.python_edit.text = 'fixture-new-maliang-python'
	find_button(sections.environment, '保存高级运行环境').pressed.emit()
	local.load(state_path.path_join('local.cfg'))
	check(local.get_value('host', 'python') == panel.python_edit.text and local.get_value('host', 'script') == 'fixture-old-editor-host.py', 'central environment save writes the existing local keys')
	panel.cli_path_edit.text = 'fixture-new-service-cli'
	panel.cli_path_edit.text_changed.emit(panel.cli_path_edit.text)
	find_button(sections.environment, '保存 CLI 与生成服务设置').pressed.emit()
	var current_saved = JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path))
	check(current_saved.cli_path == 'fixture-new-service-cli' and panel.service_saved.cli_path == current_saved.cli_path, 'central save updates the actual CLI task-service source and consumer snapshot')
	panel.python_edit.text = ''
	var serial = panel.serial
	panel.launch('service-check', {'service':panel.service_draft()})
	panel.service_config_link.pressed.emit()
	check(panel.serial == serial and requests.back() == 'environment', 'missing Python blocks before subprocess launch and routes to central environment')
	panel.python_edit.text = 'fixture-new-maliang-python'
	check(panel.serial == 0 and panel.jobs.is_empty(), 'all central settings actions remain free of host, CLI and model execution')
	panel.reclaim_settings_sections()
	panel.reclaim_settings_sections()
	check(sections.ai.get_parent() == panel and sections.environment.get_parent() == panel and not sections.ai.visible and not sections.environment.visible, 'host teardown can reclaim unique settings controls idempotently')
	check(FileAccess.file_exists(lease), 'reclaiming controls does not release the live host lease')
	panel.queue_free()
	await settle()
	check(not FileAccess.file_exists(lease) and not is_instance_valid(managed) and not is_instance_valid(sections.ai), 'host exit releases the lease and destroys reclaimed controls')
	await new_panel()
	check(panel.python_edit.text == 'fixture-new-maliang-python' and panel.cli_path_edit.text == 'fixture-new-service-cli', 'reopening restores values saved by the central forms')
	check(JSON.parse_string(JSON.stringify(panel.service_saved)) == current_saved and panel.serial == 0, 'reopening retains the real consumer snapshot without launching generation')
	panel.queue_free()
	await settle()
	await new_panel(false)
	panel.open_service_settings()
	check(panel.native_sections.is_empty() and panel.service_choice.is_visible_in_tree(), 'standalone sample retains self-contained settings compatibility')
	panel.queue_free()
	await settle()
	finish()

func finish():
	var receipt = {'ok':failures == 0, 'failures':failures, 'checks':checks, 'scope':'isolated real controls, synthetic configuration/discovery/lease only; no host, CLI, network or inference'}
	var path = OS.get_environment('AINATIVE_SETTINGS_REPORT')
	if not path.is_empty(): write_text(path, JSON.stringify(receipt, '  '))
	print('AINATIVE_UNIFIED_SETTINGS failures=' + str(failures))
	quit(0 if failures == 0 else 1)
