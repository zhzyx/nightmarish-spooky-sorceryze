@tool
extends SceneTree

# Run the packaged editor headless with a fresh, isolated project and user
# directory. After -- pass the source image and an empty output directory.
# An optional third argument "connect" checks discovery without inference.
var panel
var output = ''
var receipt = {'ok':false, 'checks':[]}

func _initialize(): run.call_deferred()

func verify(condition: bool, label: String) -> bool:
	receipt.checks.append({'passed':condition, 'label':label})
	print(('PASS ' if condition else 'FAIL ') + label)
	if not condition: finish(false)
	return condition

func finish(success: bool):
	receipt.ok = success
	if is_instance_valid(panel):
		receipt['status'] = panel.status.text
		receipt['manager'] = panel.managed_comfy_panel.notice.text
		panel.managed_comfy_panel.release_connection()
	if not output.is_empty():
		var file = FileAccess.open(output.path_join('acceptance.json'), FileAccess.WRITE)
		if file == null: success = false
		else:
			file.store_string(JSON.stringify(receipt, '  '))
			file.flush()
			success = success and file.get_error() == OK
			file.close()
	print('BUNDLED_HUNYUAN_ACCEPTANCE_OK' if success else 'BUNDLED_HUNYUAN_ACCEPTANCE_FAILED')
	quit(0 if success else 1)

func wait_idle(seconds: int) -> bool:
	var deadline = Time.get_ticks_msec() + seconds * 1000
	while panel.is_graph_busy() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	return verify(not panel.is_graph_busy(), 'Workbench operation completed within the time limit')

func vertices(scene: Node) -> int:
	var total = 0
	var meshes = scene.find_children('*', 'MeshInstance3D', true, false)
	if scene is MeshInstance3D: meshes.append(scene)
	for instance in meshes:
		if instance.mesh == null: continue
		for surface in instance.mesh.get_surface_count():
			var arrays = instance.mesh.surface_get_arrays(surface)
			if not arrays.is_empty() and arrays[Mesh.ARRAY_VERTEX] != null:
				total += arrays[Mesh.ARRAY_VERTEX].size()
	return total

func run():
	var args = OS.get_cmdline_user_args()
	if args.size() not in [2, 3] or (args.size() == 3 and args[2] != 'connect'):
		push_error('Pass an absolute PNG/JPEG path and a new output directory, optionally followed by connect.')
		quit(2)
		return
	var image_path = args[0]
	var destination = args[1]
	if not verify(image_path.is_absolute_path() and FileAccess.file_exists(image_path), 'Input image exists'): return
	if not verify(destination.is_absolute_path() and DirAccess.make_dir_recursive_absolute(destination) == OK, 'Isolated output directory available'): return
	if not verify(DirAccess.get_files_at(destination).is_empty() and DirAccess.get_directories_at(destination).is_empty(), 'Output directory is empty'): return
	output = destination
	var connect_only = args.size() == 3
	receipt['scope'] = 'native editor discovery and connection' if connect_only else 'native editor image-to-mesh, preview, publication and reload'
	receipt['platform'] = OS.get_name()
	receipt['architecture'] = Engine.get_architecture_name()
	receipt['engine_version'] = Engine.get_version_info().string
	if not verify(Engine.is_editor_hint(), 'Test is running in the native editor'): return
	var project_key = ProjectSettings.globalize_path('res://').trim_suffix('/').sha256_text()
	var state = EditorInterface.get_editor_paths().get_data_dir().path_join('ainative/projects').path_join(project_key)
	var saved = FileAccess.file_exists(state.path_join('generation-service.json'))
	receipt['initial_configuration'] = 'saved' if saved else 'fresh'
	if connect_only or not saved:
		if not verify(not saved and not FileAccess.file_exists(state.path_join('local.cfg')), 'First-use check began with empty editor settings'): return
	else:
		var previous = ConfigFile.new()
		previous.load(state.path_join('local.cfg'))
		if not verify(previous.get_value('managed_comfy', 'use_bundled_runtime', false) and previous.get_value('host', 'use_bundled_python', false), 'Reopen began with saved bundled selections'): return
	var executable = OS.get_executable_path().replace('\\', '/')
	var directory = executable.get_base_dir()
	var runtime = directory.path_join('../Resources/maliang-hunyuan').simplify_path() if OS.get_name() == 'macOS' else directory.path_join('maliang-hunyuan')
	var interpreter = runtime.path_join('python/bin/python3.12' if OS.get_name() == 'macOS' else 'python/python.exe')
	var model = 'hunyuan3d-mini.safetensors'
	var weight = runtime.path_join('models/checkpoints').path_join(model)
	if not verify(FileAccess.file_exists(interpreter) and FileAccess.file_exists(weight), 'Distribution contains the platform Python and Hunyuan3D weights'): return
	receipt['model_sha256'] = FileAccess.get_sha256(weight)
	if not verify(receipt.model_sha256 == '3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b', 'Installed weights match the pinned Hunyuan3D-2mini digest'): return
	var deadline = Time.get_ticks_msec() + 30000
	var dock
	while dock == null and Time.get_ticks_msec() < deadline:
		dock = root.find_child('AINative', true, false)
		await process_frame
	if not verify(dock != null and dock.get_parent() is TabContainer, 'Native Ma Liang editor tab exists'): return
	var tabs: TabContainer = dock.get_parent()
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	deadline = Time.get_ticks_msec() + 30000
	while panel == null and Time.get_ticks_msec() < deadline:
		panel = dock.find_child('AINativeWorkbench', true, false)
		await process_frame
	if not verify(panel != null and panel.get_meta('ainative_builtin', false) and panel.state_dir == state, 'Opened the compiled editor workbench for the isolated project'): return
	if not await wait_idle(340): return
	var manager = panel.managed_comfy_panel
	receipt['runtime_root'] = manager.runtime_path.text
	receipt['python'] = panel.python_edit.text
	receipt['devices'] = manager.last_report.get('devices', [])
	receipt['model_log'] = manager.last_report.get('log_path', '')
	if not verify(manager.runtime_path.text == runtime and panel.python_edit.text == interpreter, 'Both paths resolved from the running executable'): return
	if not verify(manager.last_report.get('connected', false) and manager.last_report.get('owned', false) and not manager.lease_path.is_empty(), 'The packaged runtime started and its session owns the local connection'): return
	if not verify(panel.service_saved.get('mode') == 'codex' and panel.service_saved.get('mesh_model') == model, 'Selected the shipped model without editing service settings'): return
	if not verify(panel.service_report.get('capabilities', {}).get('image_to_mesh', {}).get('ready', false), 'Direct image-to-mesh capability ready'): return
	receipt['cli_connected'] = panel.service_report.get('cli', {}).get('connected', false)
	var local = ConfigFile.new()
	local.load(panel.state_dir.path_join('local.cfg'))
	if not verify(local.get_value('managed_comfy', 'runtime_root', '') == '' and local.get_value('host', 'python', '') == '', 'Settings store the bundled choices without absolute paths'): return
	if connect_only:
		finish(true)
		return
	for index in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(index) == 'image_to_mesh':
			panel.generator_choice.select(index)
			break
	panel.add_generator()
	var id: String = panel.selected_id
	panel.source_edit.text = image_path
	var parameters = {'prompt':'', 'mesh_steps':5, 'mesh_resolution':128, 'octree_resolution':64}
	panel.parameter_form.configure('image_to_mesh', parameters)
	if not verify(panel.apply_fields() and panel.node_run_blocker(id).is_empty(), 'An existing image with no prompt is runnable'): return
	receipt['source_sha256'] = FileAccess.get_sha256(image_path)
	receipt['parameters'] = parameters
	panel.run_node_preview(id)
	if not await wait_idle(1800): return
	receipt['run_id'] = panel.run_id
	if not verify(panel.current.get('nodes', {}).get(id, {}).get('state') == 'succeeded' and is_instance_valid(panel.preview_scene), 'Image-to-mesh inference finished and loaded a preview'): return
	var vertex_count = vertices(panel.preview_scene)
	if not verify(vertex_count > 0, 'Preview contains mesh vertices'): return
	var path = output.path_join('mesh.tscn')
	panel.target_edit.text = path
	panel.review_publish()
	if not verify(not panel.confirmation.is_empty(), 'Preview is ready to publish'): return
	panel.confirm_publish()
	if not await wait_idle(60): return
	var packed = ResourceLoader.load(path, 'PackedScene', ResourceLoader.CACHE_MODE_IGNORE)
	if not verify(packed is PackedScene, 'Published mesh scene reopens from disk'): return
	var reopened: Node = packed.instantiate()
	var saved_vertices = vertices(reopened)
	reopened.free()
	if not verify(saved_vertices == vertex_count, 'Reloaded mesh retains the preview vertex count'): return
	receipt['vertices'] = vertex_count
	receipt['mesh_sha256'] = FileAccess.get_sha256(path)
	finish(true)
