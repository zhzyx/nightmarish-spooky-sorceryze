extends SceneTree
# Explicit opt-in real inference acceptance. Uses the same controls as the UI.
var panel
var config: Dictionary
var results: Array = []
var failed := false

func check(condition: bool, message: String) -> bool:
	if condition:
		return true
	failed = true
	push_error(message)
	if config.get('output') is String and DirAccess.dir_exists_absolute(config.output):
		var file = FileAccess.open(config.output.path_join('failure.json'), FileAccess.WRITE)
		if file:
			file.store_string(JSON.stringify({'ok':false, 'message':message, 'completed_results':results}, '  '))
			file.close()
	quit(1)
	return false

func _initialize(): run.call_deferred()

func idle(seconds: float = 420.0):
	var deadline = Time.get_ticks_msec() + int(seconds * 1000)
	while panel.is_graph_busy() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	if panel.is_graph_busy():
		panel.cancel_run()
		var cancel_deadline = Time.get_ticks_msec() + 20000
		while panel.is_graph_busy() and Time.get_ticks_msec() < cancel_deadline:
			await create_timer(0.1).timeout
		check(false, 'Timed out; cancellation requested, preserve task receipts before retrying: ' + panel.status.text)

func add_kind(kind: String, prompt: String, source: String = '') -> String:
	for index in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(index) == kind: panel.generator_choice.select(index)
	panel.add_generator()
	panel.source_edit.text = source
	panel.text_edit.text = '白色背景，不要文字。' if kind != 'image_to_mesh' else ''
	var parameters = {'prompt':prompt, 'width':512, 'height':512}
	if kind.ends_with('mesh'):
		parameters.merge({'mesh_steps':5, 'mesh_resolution':128, 'octree_resolution':64})
	panel.parameter_form.configure(kind, parameters)
	if not check(panel.apply_fields(), panel.status.text): return ''
	return panel.selected_id

func generate(id: String) -> Dictionary:
	print('REAL_GENERATE ' + id)
	panel.run_node_preview(id)
	await idle()
	if failed: return {}
	if not check(panel.current.get('nodes', {}).has(id), panel.status.text): return {}
	if not check(panel.current.nodes[id].state == 'succeeded', panel.status.text): return {}
	if not check(not panel.preview_token.is_empty(), panel.status.text): return {}
	var history: Array = panel.preview_history.get(id, [])
	if not check(not history.is_empty(), 'Missing preview history'): return {}
	var result: Dictionary = history.back().duplicate(true)
	result['content_sha256'] = FileAccess.get_sha256(result.path)
	result['kind'] = panel.nodes.filter(func(n): return n.id == id)[0].type
	results.append(result)
	return result

func publish(name: String):
	var path = config.output.path_join(name)
	if not check(not FileAccess.file_exists(path), 'Publication already exists'): return
	panel.target_edit.text = path
	panel.review_publish()
	if not check(not panel.confirmation.is_empty(), panel.status.text): return
	panel.confirm_publish()
	await idle(30.0)
	if failed: return
	if not check(FileAccess.file_exists(path), panel.status.text): return
	if not check(load(path) != null, 'Published asset cannot be loaded'): return
	results.back()['published_sha256'] = FileAccess.get_sha256(path)

func run():
	if not check(OS.get_cmdline_user_args().size() == 1, 'Pass an explicit private config to enable real inference'): return
	var loaded = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	if not check(loaded is Dictionary, 'Configuration must be a JSON object'): return
	config = loaded
	if not check(config.get('real_inference_authorized') == true, 'Real inference was not authorized'): return
	for field in ['output', 'state_dir', 'python', 'host', 'cli', 'runtime_root']:
		if not check(config.get(field) is String and not str(config.get(field)).is_empty(), 'Missing or invalid configuration field: ' + field): return
	if not check(config.output.is_absolute_path(), 'Output directory must be absolute'): return
	if not check(not FileAccess.file_exists(config.output.path_join('acceptance.json')), 'Acceptance already exists'): return
	if not check(DirAccess.make_dir_recursive_absolute(config.output) == OK, 'Cannot create output directory'): return
	panel = load('res://addons/ainative/workbench.gd').new()
	panel.state_dir = config.state_dir
	root.add_child(panel)
	await process_frame
	panel.python_edit.text = config.python
	panel.host_edit.text = config.host
	panel.service_choice.select(3)
	panel.cli_path_edit.text = config.cli
	panel._service_settings_changed()
	panel.managed_comfy_panel.runtime_path.text = config.runtime_root
	panel.managed_comfy_panel.operate('start')
	await idle(180.0)
	if failed: return
	print('SERVICE_STATE ' + JSON.stringify({'state_dir':panel.state_dir, 'state_exists':DirAccess.dir_exists_absolute(panel.state_dir), 'manager':panel.managed_comfy_panel.notice.text, 'manager_report':panel.managed_comfy_panel.last_report, 'status':panel.status.text}))
	if not check(panel.service_report.get('connected', false), panel.service_status.text + ' / ' + panel.managed_comfy_panel.notice.text): return
	if not check(panel.service_saved.get('mode') == 'codex', 'Service configuration was not saved'): return
	panel.nodes.clear()
	panel.edges.clear()
	panel.rebuild()
	var image_id = add_kind('text_to_image', 'A small blue stone owl sculpture, centered, isolated on a clean white background, no text.')
	if failed: return
	var image = await generate(image_id)
	if failed: return
	await publish('blue-owl.tres')
	if failed: return
	var edit_id = add_kind('image_to_image', 'Change only the owl material to red stone. Preserve its shape, camera view and white background.', image.path)
	var edited = await generate(edit_id)
	if failed: return
	if not check(edited.content_sha256 != image.content_sha256, 'Editing did not change the image'): return
	await publish('red-owl.tres')
	if failed: return
	var mesh_id = add_kind('image_to_mesh', '', edited.path)
	await generate(mesh_id)
	if failed: return
	await publish('owl-mesh.tscn')
	if failed: return
	panel.path_edit.text = config.output.path_join('workflow.json')
	panel.save_graph()
	if not check(FileAccess.file_exists(panel.path_edit.text), 'Workflow was not saved'): return
	var workflow = FileAccess.get_file_as_string(panel.path_edit.text)
	if not check(not workflow.contains(config.cli) and not workflow.contains(config.runtime_root), 'Workflow contains machine configuration'): return
	var receipt = {'ok':true, 'scope':'Actual CLI text-to-image and image editing followed by local Mesh; shared workbench controls, preview and publication. Native compiled entry is validated separately.', 'results':results, 'service':panel.service_saved}
	var file = FileAccess.open(config.output.path_join('acceptance.json'), FileAccess.WRITE)
	if not check(file != null, 'Cannot open acceptance receipt'): return
	file.store_string(JSON.stringify(receipt, '  '))
	file.flush()
	var write_error = file.get_error()
	file.close()
	if not check(write_error == OK, 'Cannot write acceptance receipt'): return
	print('CODEX_CLI_REAL_ACCEPTANCE_OK')
	panel.free()
	quit()
