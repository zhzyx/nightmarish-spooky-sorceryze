@tool
extends SceneTree
# Synthetic fixtures exercise the real editor/provider/publication code. No AI inference.

var panel
var failures: Array = []
var passed: Array = []
var details: Dictionary = {'fixture_kind':'synthetic test assets; no AI inference'}

func _initialize():
	run.call_deferred()

func check(condition: bool, label: String) -> bool:
	print(('PASS ' if condition else 'FAIL ')+label)
	if condition: passed.append(label)
	else: failures.append(label)
	return condition

func finish():
	var receipt = {'ok':failures.is_empty(),'checks':passed,'failures':failures,'details':details}
	var path = OS.get_environment('AINATIVE_TEST_RECEIPT')
	if not path.is_empty():
		var output = FileAccess.open(path,FileAccess.WRITE)
		if output: output.store_string(JSON.stringify(receipt,'  ')); output.close()
	print('AINATIVE_BUILTIN_OK' if failures.is_empty() else 'AINATIVE_BUILTIN_FAILED')
	if is_instance_valid(panel):
		panel.queue_free()
		panel = null
		await process_frame
	quit(0 if failures.is_empty() else 1)

func wait_idle():
	var deadline = Time.get_ticks_msec()+45000
	while (not panel.jobs.is_empty() or panel.auto_step) and Time.get_ticks_msec()<deadline:
		await create_timer(.02).timeout
	return check(panel.jobs.is_empty() and not panel.auto_step,'real host subprocess completed')

func run():
	if OS.get_environment('AINATIVE_TEST_MODE')=='runtime':
		await verify_portable_runtime()
		finish()
		return
	root.size = Vector2i(1440,1000)
	var deadline = Time.get_ticks_msec()+30000
	var dock
	while dock==null and Time.get_ticks_msec()<deadline:
		dock = root.find_child('AINative',true,false)
		await process_frame
	if not check(dock!=null and ClassDB.class_exists('AINativeEditorPlugin'),'native AINative editor plugin is registered'):
		finish(); return
	if not check(dock.get_parent() is TabContainer,'AINative is an editor main-screen tab'):
		finish(); return
	var tabs: TabContainer = dock.get_parent()
	await create_timer(1).timeout
	check(dock.title=='马良','native workbench is displayed as 马良')
	var chat = root.find_child('AI Chat',true,false)
	check(chat!=null and tabs.get_tab_idx_from_control(dock)==tabs.get_tab_idx_from_control(chat)+1,'马良 is immediately after AI Chat')
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	deadline = Time.get_ticks_msec()+30000
	while panel==null and Time.get_ticks_msec()<deadline:
		panel = dock.find_child('AINativeWorkbench',true,false)
		await process_frame
	if not check(panel!=null and panel.get_meta('ainative_builtin',false),'native tab opens the bundled workbench without addons'):
		finish(); return
	await process_frame
	check(panel.process_button != null and panel.get_child(panel.get_child_count() - 1) == panel.process_button, 'native MaLiang keeps the view-process button at the bottom')
	panel.process_button.pressed.emit()
	await process_frame
	check(panel.process_panel.visible and panel.process_steps != null and panel.process_logs != null, 'native process panel exposes reasoning steps and full logs')
	panel.find_child('MinimizeProcessButton', true, false).pressed.emit()
	await process_frame
	check(not panel.process_panel.visible and panel.process_button.text == '查看具体过程', 'native process panel minimizes without leaving MaLiang')
	await verify_workspace(dock,tabs)
	if OS.get_environment('AINATIVE_TEST_MODE')=='sample':
		await create_timer(.3).timeout
		var copies = 0
		for candidate in root.find_children('*','VBoxContainer',true,false):
			var attached = candidate.get_script()
			if attached!=null and str(attached.resource_path).ends_with('/workbench.gd'): copies += 1
		check(copies==1,'enabled legacy sample addon does not create a second workbench')
		var docks = 0
		for candidate in root.find_children('AINative','',true,false):
			if candidate.is_class('EditorDock'): docks += 1
		check(docks==1,'sample project retains exactly one native AINative editor dock')
		finish(); return
	check(not DirAccess.dir_exists_absolute('res://addons'),'test project has no addons directory')
	check(panel.native_buttons.keys().size()==5,'five direct navigation buttons are available')
	for section in ['mesh','rig','character','other','settings']:
		check(panel.native_buttons.has(section),'navigation: '+section)
	check(panel.native_buttons.mesh.button_pressed and panel.graph.is_visible_in_tree(),'Mesh generation is the default native page')
	var kinds = []
	for i in panel.generator_choice.item_count: kinds.append(panel.generator_choice.get_item_metadata(i))
	check(kinds==['generate_image','image_to_mesh','text_to_mesh','model_adjust','human_shape_adjust','humanoid_rig','garment_split'],'unified image generation, Mesh processing, pre-rig human shape adjustment, local humanoid rig and garment surface split nodes are available')
	for i in panel.generator_choice.item_count:
		panel.generator_choice.select(i)
		panel.add_generator()
		check(panel.nodes.back().type==kinds[i],'Chinese generator option preserves protocol: '+kinds[i])
		if kinds[i]=='human_shape_adjust':
			check(panel.parameter_form.rows.height_cm.visible and not panel.parameter_form.rows.height_m.visible and panel.parameter_form.rows.head_ratio.visible and not panel.parameter_form.landmarks_edit.visible and not panel.parameter_form.pose_row.visible and not panel.parameter_form.prompt_edit.visible,'bundled human shape node exposes five controls with centimeter height and automatic AINative pose and landmark fitting')
			check(panel.apply_fields() and not panel.nodes.back().parameters.has('prompt') and not panel.nodes.back().parameters.has('landmarks') and not panel.nodes.back().parameters.has('confirmed'),'bundled human shape apply adds neither prompt, manual landmarks nor human confirmation')
		panel.delete_node()
	panel.generator_choice.select(2)
	panel.select_node(panel.nodes[0].id)
	await verify_context_controls()
	verify_file_pickers()
	verify_chinese_controls()
	await verify_settings_navigation(dock)
	await verify_generation_service_controls()
	verify_capability_notice()
	verify_failure_dialog()
	check(panel.rigging_panel.source_field!=null,'rigging exposes a local Mesh browser/input')
	var tools = str(panel.get_meta('ainative_tools_dir',''))
	check(panel.host_edit.text==tools.path_join('editor_host.py') and FileAccess.file_exists(panel.host_edit.text),'host comes from the engine bundle')
	details.state_key = panel.state_dir.get_file()
	details.state_root = panel.state_dir
	details.host_sha256 = FileAccess.get_sha256(panel.host_edit.text)
	var bundle = tools.get_base_dir()
	details.bundle_root = bundle
	details.bundle_version = bundle.get_file()
	details.bundle_sha256 = {'manifest.json':FileAccess.get_sha256(bundle.path_join('manifest.json'))}
	for folder in ['scripts', 'tools']:
		for filename in DirAccess.get_files_at(bundle.path_join(folder)):
			details.bundle_sha256[folder + '/' + filename] = FileAccess.get_sha256(bundle.path_join(folder).path_join(filename))
	panel.save_settings()
	var settings = ConfigFile.new()
	settings.load(panel.state_dir.path_join('local.cfg'))
	check(settings.get_value('host','use_bundled_script',false) and not settings.has_section_key('host','script'),'default local settings retain the bundled-host choice without a cached absolute script path')
	# Reopening the same project state after an engine bundle upgrade chooses the new bundle.
	var upgraded = panel.get_script().new()
	var new_tools = panel.state_dir.path_join('simulated-next-bundle/tools')
	upgraded.state_dir = panel.state_dir
	upgraded.set_meta('ainative_builtin',true)
	upgraded.set_meta('ainative_tools_dir',new_tools)
	root.add_child(upgraded)
	upgraded.hide()
	await process_frame
	check(upgraded.host_edit.text==new_tools.path_join('editor_host.py'),'saved default follows the current engine bundle after an upgrade')
	upgraded.queue_free()
	await process_frame
	if OS.get_environment('AINATIVE_TEST_MODE')=='entry':
		finish(); return
	verify_importer_conversion()
	await verify_mesh()
	await verify_garment_node()
	await verify_rigging()
	await prepare_portable_runtime()
	var capture = OS.get_environment('AINATIVE_TEST_CAPTURE')
	if not capture.is_empty():
		panel.native_buttons.rig.pressed.emit()
		panel.process_button.pressed.emit()
		await process_frame
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture)==OK,'native workbench screenshot saved')
	finish()

func verify_generation_service_controls():
	if not check(panel.get("service_choice") is OptionButton and panel.has_method("check_service"), 'bundled editor exposes generation service setup controls'): return
	var service_modes: Array = []
	for i in panel.service_choice.item_count: service_modes.append(panel.service_choice.get_item_metadata(i))
	check(service_modes == ["comfy", "legacy", "codex", "kimi_native", "local_mesh", "api_modeling", "api_sculpt"], 'bundled service picker removes offline and preserves seven supported choices')
	check(panel.get('cli_path_edit') is LineEdit and panel.get('managed_comfy_panel') is VBoxContainer, 'bundled CLI and local Mesh management controls are installed')
	check(panel.service_config_path.get_base_dir() == panel.state_dir and panel.service_config_path.get_file() == "generation-service.json", 'bundled service configuration is private machine state')
	check(panel._service_mode() == "comfy" and panel.service_saved.is_empty(), 'fresh native project does not claim a real generation service')
	panel.endpoint_edit.text = 'http://127.0.0.1:1'
	var serial = panel.serial
	panel.check_service()
	if not await wait_idle(): return
	check(panel.serial == serial + 1 and panel.service_report.get("mode") == "comfy" and not panel.service_report.get("connected", true), 'bundled read-only service check reaches its Python implementation')
	check(not panel.service_report.get("capabilities", {}).get("text_to_image", {}).get("ready", true) and not FileAccess.file_exists(panel.service_config_path), 'checking an unconfigured service neither invents readiness nor activates configuration')
	panel.select_service_mode('kimi_native')
	panel.service_choice.item_selected.emit(panel.service_choice.selected)
	panel.kimi_model_edit.text = 'obsolete-language-model'
	panel.endpoint_edit.text = 'https://obsolete.invalid/v1'
	panel.model3d_tool_edit.text = 'fixture-3d/model3d_generation_tool.py'
	panel.model3d_pythonw_edit.text = 'fixture-3d/pythonw.exe'
	panel.kimi_image_tool_edit.text = ''
	panel.kimi_image_pythonw_edit.text = ''
	var draft = panel.service_draft()
	check(draft.get('mode') == 'kimi_native' and draft.get('model3d_model') == 'v3.1', 'Kimi Native uses direct Tripo API generation')
	check(not draft.has('cli_path') and not draft.has('blender_path') and draft.image_model.is_empty() and draft.mesh_model.is_empty(), 'Kimi Native does not require Codex, Blender or ComfyUI model settings')
	check(panel.kimi_model3d_fields.visible and not panel.kimi_model_edit.visible and not panel.endpoint_edit.visible and not panel.endpoint_edit.editable and draft.endpoint.is_empty() and not draft.has('kimi_model'), 'Kimi Native exposes direct 3D settings and discards obsolete language model routing')
	check(panel._generator_provider('text_to_mesh') == 'kimi_native' and panel._generator_provider('image_to_mesh') == 'kimi_native' and panel._generator_provider('model_adjust') == 'kimi_native' and panel._generator_provider('human_shape_adjust') == 'kimi_native', 'Mesh generation, model adjustment and local human shape adjustment route to Kimi Native')
	check(panel._generator_provider('generate_image') == 'kimi_work_image' and panel._generator_provider('text_to_image') == 'kimi_work_image' and panel._generator_provider('image_to_image') == 'kimi_work_image', 'unified and legacy 2D kinds route to the independent Kimi Work image service')
	check(panel.get('model3d_tool_edit') is LineEdit and panel.get('model3d_pythonw_edit') is LineEdit and panel.get('kimi_image_tool_edit') is LineEdit and panel.get('kimi_image_pythonw_edit') is LineEdit, 'native settings expose independent 3D and 2D tools')
	panel.save_service_settings()
	check(not panel._service_blocker('text_to_mesh').is_empty(), 'Mesh generation requires an explicit per-node model selection')
	check(panel._service_blocker('text_to_mesh', {'model':draft.model3d_model}).is_empty() and panel._service_blocker('generate_image').contains('Kimi Work') and panel._service_blocker('image_to_image').contains('pythonw'), 'missing image tools leave Mesh available and explain the 2D setup')
	var stored = FileAccess.get_file_as_string(panel.service_config_path)
	check(panel.service_saved == draft and not stored.contains('api_key') and not stored.contains('authorization') and not stored.contains('secret') and not stored.contains('password'), 'Kimi Native saves settings without API credentials')
	var restored = panel.get_script().new()
	restored.state_dir = panel.state_dir
	restored.set_meta('ainative_builtin', true)
	restored.set_meta('ainative_tools_dir', panel.get_meta('ainative_tools_dir', ''))
	root.add_child(restored)
	restored.hide()
	await process_frame
	check(restored._service_mode() == 'kimi_native' and restored.service_saved == draft and restored.service_saved.endpoint.is_empty() and not restored.service_saved.has('kimi_model') and not restored.endpoint_edit.visible and restored.model3d_tool_edit.text == draft.model3d_tool_path and restored.model3d_pythonw_edit.text == draft.model3d_pythonw_path, 'Kimi Native settings survive a real Workbench reopen')
	restored.select_service_mode('codex')
	restored.service_choice.item_selected.emit(restored.service_choice.selected)
	restored.cli_path_edit.text = 'unsaved-native-codex'
	restored.select_service_mode('comfy')
	restored.service_choice.item_selected.emit(restored.service_choice.selected)
	restored.endpoint_edit.text = 'http://127.0.0.1:65432'
	restored.select_service_mode('kimi_native')
	restored.service_choice.item_selected.emit(restored.service_choice.selected)
	check(restored.model3d_tool_edit.text == draft.model3d_tool_path and restored.model3d_pythonw_edit.text == draft.model3d_pythonw_path and restored.service_saved == draft, 'native service switching restores Kimi without replacing the active saved provider')
	var profiles = JSON.parse_string(FileAccess.get_file_as_string(restored.service_profiles_path))
	check(profiles is Dictionary and profiles.get('profiles', {}).get('codex', {}).get('cli_path') == 'unsaved-native-codex' and profiles.get('profiles', {}).get('comfy', {}).get('endpoint') == 'http://127.0.0.1:65432', 'native unsaved provider settings persist before service startup')
	restored.queue_free()
	await process_frame
	panel.service_choice.select(0)
	panel.service_choice.item_selected.emit(0)
	# Changing the draft picker does not replace the saved provider used by jobs.
	# Save a controlled local configuration before the Mesh Copy execution.
	panel.save_service_settings()
	var active = JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path))
	check(panel._service_mode() == 'comfy' and panel.service_saved.get('mode') == 'comfy' and active is Dictionary and active.get('mode') == 'comfy', 'service setup saves a real provider choice without an offline mode')

func verify_context_controls():
	check(panel.get("context_menu") is PopupMenu and panel.has_method("show_context_menu"), 'bundled editor exposes contextual editing')
	if not panel.has_method("show_context_menu"): return
	var toolbar_labels: Array = []
	for child in panel.native_sections.bar.get_children():
		if child is Button and child.visible: toolbar_labels.append(child.text)
	check(not toolbar_labels.has("+ 离线复制节点") and not toolbar_labels.has("+ 生成节点") and not toolbar_labels.has("删除选中节点") and not toolbar_labels.has("重试选中节点"), 'bundled toolbar moves object editing into context menus')
	check(not panel.path_edit.is_visible_in_tree() and not panel.generator_choice.is_visible_in_tree(), 'bundled path and generator selectors no longer occupy the toolbar')
	var before = panel.nodes.size()
	var serial = panel.serial
	panel.graph.popup_request.emit(panel.graph.size - Vector2(20, 20))
	check(panel.context_menu.visible and panel.serial == serial, 'bundled blank-canvas context opens without executing providers')
	panel.context_menu.hide()
	panel.create_context_node("copy")
	await process_frame
	var added = panel.nodes.back().id
	check(panel.nodes.size() == before + 1 and panel.nodes.back().type == "copy", 'bundled context creates the requested machine node')
	panel.delete_node()
	check(panel.nodes.size() == before and not panel.nodes.any(func(n): return n.id == added), 'bundled context-created node retains normal delete behavior')
	panel.select_node(panel.nodes[0].id)
	await process_frame

func verify_file_pickers():
	check(panel.source_picker is FileDialog and panel.context_picker is FileDialog, 'source and reference inputs provide file pickers')
	if not panel.source_picker is FileDialog or not panel.context_picker is FileDialog: return
	check(panel.source_picker.access == FileDialog.ACCESS_FILESYSTEM and panel.context_picker.access == FileDialog.ACCESS_FILESYSTEM, 'source and reference pickers browse the machine filesystem')
	check(panel.source_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILE and panel.context_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILE, 'offline Copy keeps single-file source and reference pickers')
	check(panel.source_picker.use_native_dialog and panel.context_picker.use_native_dialog, 'source and reference pickers use the system resource manager')
	check(not panel.source_edit.editable and not panel.context_edit.editable, 'image inputs no longer require manually typing paths')
	check(str(panel.source_picker.filters).contains('*.glb') and str(panel.source_picker.filters).contains('*.gltf'), 'offline Copy retains Mesh file selection')
	var original = panel.selected_id
	panel.generator_choice.select(0)
	panel.add_generator()
	var data = panel.nodes.back()
	check(data.type == 'generate_image' and panel.source_browse.text == '选择图片…', 'image generation presents an image selection action')
	check(panel.source_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES and panel.context_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES, 'image generation source and reference pickers accept ordered multiple files')
	check(str(panel.source_picker.filters).contains('*.png') and str(panel.source_picker.filters).contains('*.jpg') and str(panel.source_picker.filters).contains('*.jpeg') and not str(panel.source_picker.filters).contains('*.glb'), 'image generation filters the source picker to supported images')
	check(str(panel.context_picker.filters).contains('*.png') and not str(panel.context_picker.filters).contains('*.glb'), 'reference picker only accepts supported images')
	var source = ProjectSettings.globalize_path('res://fixture.png')
	data.source_snapshot = {'content_base64':'old'}
	data.image_context_snapshot = {'content_base64':'old'}
	panel.source_picker.file_selected.emit(source)
	check(panel.source_edit.text == source and data.source == source and not data.has('source_snapshot'), 'picked source image updates the existing node contract and replaces its stale snapshot')
	panel.context_picker.file_selected.emit(source)
	check(panel.context_edit.text == source and data.image_context == source and not data.has('image_context_snapshot'), 'picked reference image updates the existing node contract and replaces its stale snapshot')
	panel.source_picker.files_selected.emit(PackedStringArray([source, source]))
	check(data.source_paths.size() == 2 and data.source == source and panel.source_edit.text.contains(' ; '), 'multiple picked sources retain ordered paths and the primary source')
	check(panel.apply_fields() and panel.model().nodes.back().source == source and panel.model().nodes.back().image_context == source, 'picked images flow through the existing apply and serialization path')
	panel.source_clear.pressed.emit()
	panel.context_clear.pressed.emit()
	check(data.source.is_empty() and data.image_context.is_empty() and data.source_paths.is_empty() and data.image_context_paths.is_empty() and panel.source_edit.text.is_empty() and panel.context_edit.text.is_empty(), 'clear actions remove picked source and reference images without legacy fallback restoring them')
	panel.delete_node()
	panel.generator_choice.select(1)
	panel.add_generator()
	data = panel.nodes.back()
	check(data.type == 'image_to_mesh' and data.version == '2' and panel.source_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES, 'image-to-Mesh accepts multiple source images')
	data.parameters.prompt = 'legacy hidden requirement'
	data.text = 'legacy hidden node text'
	panel.select_node(data.id)
	check(not panel.parameter_form.prompt_edit.is_visible_in_tree() and not panel.node_image_model_edit.is_visible_in_tree() and data.parameters.prompt.is_empty() and data.text.is_empty(), 'bundled image-to-Mesh is image-only and clears legacy text without a redraw model')
	panel.source_picker.files_selected.emit(PackedStringArray([source, source]))
	check(data.source_paths.size() == 2, 'image-to-Mesh preserves picked source ordering')
	panel.delete_node()
	panel.generator_choice.select(2)
	panel.add_generator()
	var upstream = panel.nodes.back()
	panel.generator_choice.select(3)
	panel.add_generator()
	data = panel.nodes.back()
	check(data.type == 'model_adjust' and data.version == '2' and data.parameters.prompt.is_empty() and panel.output_kind(data) == 2, 'model adjustment starts with optional guidance, local-operation V2 support and a Mesh output')
	check(panel.source_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILE and panel.context_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES, 'model adjustment takes one source model and ordered reference images')
	check(str(panel.source_picker.filters).contains('*.glb') and str(panel.source_picker.filters).contains('*.gltf') and not str(panel.source_picker.filters).contains('*.png'), 'model adjustment source picker accepts models rather than images')
	var model_source = ProjectSettings.globalize_path('res://fixture.glb')
	panel.source_picker.file_selected.emit(model_source)
	panel.context_picker.files_selected.emit(PackedStringArray([source, source, source, source]))
	check(data.source == model_source and data.image_context_paths.size() == 4, 'source model and four optional guidance images update the node')
	panel.connect_nodes(str(upstream.id), 0, str(data.id), 0)
	check(panel.edges.any(func(edge): return edge.from == upstream.id and edge.to == data.id), 'generated Mesh output can feed model adjustment')
	var adjustment_id = data.id
	panel.path_edit.text = ProjectSettings.globalize_path('user://model-adjustment-workflow.json')
	panel.save_graph()
	panel.open_graph()
	panel.select_node(adjustment_id)
	data = panel.nodes.filter(func(node): return node.id == adjustment_id)[0]
	check(data.source_snapshots.size() == 1 and data.image_context_snapshots.size() == 4 and data.parameters.prompt.is_empty(), 'model and guidance snapshots survive workflow save and reopen with optional text intact')
	check(panel.edges.any(func(edge): return edge.from == upstream.id and edge.to == adjustment_id), 'Mesh to model adjustment connection survives save and reopen')
	panel.select_node(original)

func settle():
	for i in 8: await process_frame

func verify_workspace(dock: Control,tabs: TabContainer):
	var scenes = root.find_children('*','SceneTreeDock',true,false)
	var inspectors = root.find_children('*','InspectorDock',true,false)
	var scene = scenes[0] as Control if scenes.size()==1 else null
	var inspector = inspectors[0] as Control if inspectors.size()==1 else null
	var scene_tabs = root.find_children('*','EditorSceneTabs',true,false)
	var bottom = root.find_children('*','EditorBottomPanel',true,false)
	details.layout_lookup = {'scene':scene!=null,'inspector':inspector!=null,'scene_tabs':scene_tabs.size(),'bottom':bottom.size()}
	check(scene!=null and inspector!=null and scene_tabs.size()==1 and bottom.size()==1,'real editor layout controls are available for geometry checks')
	if scene==null or inspector==null or scene_tabs.size()!=1 or bottom.size()!=1: return
	for screen in ['2D','3D','Script']:
		EditorInterface.set_main_screen_editor(screen)
		await settle()
		check(scene.is_visible_in_tree() and inspector.is_visible_in_tree() and scene_tabs[0].is_visible_in_tree() and bottom[0].is_visible_in_tree(),'normal editor layout restored on '+screen)
		tabs.current_tab = tabs.get_tab_idx_from_control(dock)
		await settle()
		check(not scene.is_visible_in_tree() and not inspector.is_visible_in_tree() and not scene_tabs[0].is_visible_in_tree() and not bottom[0].is_visible_in_tree(),'马良 hides side docks, scene tabs and bottom panel after '+screen)
		var rect = dock.get_global_rect()
		check(rect.position.x<20 and rect.size.x>root.size.x-40 and rect.end.y>root.size.y-20,'马良 fills the available editor workspace after '+screen)
	EditorInterface.set_main_screen_editor('AI Chat')
	await settle()
	check(not scene.is_visible_in_tree() and not inspector.is_visible_in_tree() and not bottom[0].is_visible_in_tree(),'AI Chat keeps its full workspace')
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting('interface/editor/behavior/separate_distraction_mode',true)
	for key in ['AINativeMainScreen','DaqianMainScreen','AIChatMainScreen','AINativeMainScreen']:
		for i in tabs.get_tab_count():
			if tabs.get_tab_control(i).get_layout_key()==key: tabs.current_tab = i; break
		await settle()
		check(not scene.is_visible_in_tree() and not inspector.is_visible_in_tree() and not scene_tabs[0].is_visible_in_tree() and not bottom[0].is_visible_in_tree(),'direct full-workspace switch with separate distraction settings: '+key)
	settings.set_setting('interface/editor/behavior/separate_distraction_mode',false)
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	await settle()

func verify_settings_navigation(dock: Control):
	var settings_page = root.find_child('UnifiedSettings',true,false)
	var sections: Dictionary = panel.get_settings_sections()
	check(settings_page!=null and sections.keys().size()==2 and sections.has('ai') and sections.has('environment'),'马良 exposes the two native settings categories')
	if settings_page==null or sections.size()!=2: return
	var categories = settings_page.find_child('UnifiedSettingsCategories',true,false)
	check(settings_page.is_ancestor_of(sections.ai) and settings_page.is_ancestor_of(sections.environment) and not panel.is_ancestor_of(sections.ai),'native settings owns the unique 马良 forms')
	panel.native_buttons.settings.pressed.emit()
	await settle()
	check(settings_page.is_visible_in_tree() and categories.get_current_tab_control().name=='ArtEnvironmentSettingsPage' and sections.environment.is_visible_in_tree() and sections.environment.is_ancestor_of(panel.cli_path_edit) and sections.environment.is_ancestor_of(panel.python_edit) and not panel.native_sections.machine.visible,'local settings action navigates to central art environment')
	var advanced_visible = panel.service_advanced.visible
	panel.service_advanced.show()
	check(panel.python_edit.is_visible_in_tree(), 'advanced art runtime reveals the existing Python control')
	panel.service_advanced.visible = advanced_visible
	panel.service_settings_section = 'ai'
	panel.open_service_settings()
	await settle()
	check(settings_page.is_visible_in_tree() and categories.get_current_tab_control().name=='ArtAISettingsPage' and panel.service_choice.is_visible_in_tree() and sections.ai==panel.service_fields,'service configuration navigates to the existing art AI form')
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await settle()
	check(panel.graph.is_visible_in_tree() and panel.native_buttons.mesh.button_pressed and not settings_page.is_visible_in_tree(),'returning from settings preserves the active business section')

func verify_chinese_controls():
	var han = RegEx.new()
	han.compile('\\p{Han}')
	var leftovers: Array = []
	var proper_names = ['UE4','Manny','Mixamo','UE5 Manny','UE5 Quinn']
	var controls = panel.find_children('*','Control',true,false)
	for section in panel.get_settings_sections().values():
		for control in section.find_children('*','Control',true,false):
			if not controls.has(control): controls.append(control)
	for control in controls:
		var ancestor = control.get_parent()
		var engine_popup = false
		while ancestor!=panel and ancestor!=null:
			if ancestor is FileDialog or ancestor is PopupMenu: engine_popup = true; break
			ancestor = ancestor.get_parent()
		if engine_popup: continue
		var texts: Array = []
		if control is Label or control is Button: texts.append(control.text)
		if control is LineEdit or control is TextEdit: texts.append(control.placeholder_text)
		if control is OptionButton:
			for i in control.item_count: texts.append(control.get_item_text(i))
		for value in texts:
			var text = str(value).strip_edges()
			if not text.is_empty() and han.search(text)==null and not text in proper_names and not text.trim_suffix('%').is_valid_float():
				leftovers.append(text)
	details.untranslated_controls = leftovers
	check(leftovers.is_empty(),'workbench-owned labels, actions and placeholders are Chinese or proper names')
	var error = panel.diagnostic_error('测试操作失败','FileNotFoundError: synthetic diagnostic')
	check(error.contains('失败') and not error.contains('FileNotFoundError') and FileAccess.get_file_as_string(panel.state_dir.path_join('diagnostics.log')).contains('FileNotFoundError'),'raw external failure details are retained locally behind a Chinese summary')

func verify_capability_notice():
	var artifact = {
		'id':'capability-test','revision':'a'.repeat(64),'type':'mesh',
		'payload':{'provenance':{'capability_limited':true,'visual_review_passed':false,'unresolved_issues':['Body proportions require unsupported geometry editing','Hair is too tall']}}
	}
	var state = {'state':'succeeded','result':{'artifacts':[artifact]}}
	check(panel._capability_limited_artifact(state)==artifact,'capability-limited success is detected from mesh provenance')
	var notice = panel._capability_notice_text(artifact)
	check(notice.contains('成功结果交付') and notice.contains('视觉审核未完全通过') and notice.contains('整体或局部比例') and notice.contains('发型'),'capability notice distinguishes delivery from full review and lists Chinese issue summaries')
	check(not notice.contains('review') and not notice.contains('SHA256') and not notice.contains('Body proportions') and not notice.contains('Hair is'),'capability dialog and status do not expose English review prose')
	panel._show_capability_notice('synthetic-node',artifact)
	check(panel.capability_notice_dialog.visible and panel.capability_notices.size()==1,'capability-limited delivery opens one native warning dialog')
	panel.capability_notice_dialog.hide()
	panel._show_capability_notice('synthetic-node',artifact)
	check(panel.capability_notices.size()==1,'same run, node and model do not repeatedly open the warning')
	state.result.artifacts[0].payload.provenance.capability_limited = false
	check(panel._capability_limited_artifact(state).is_empty(),'ordinary fully reviewed success does not open a capability warning')

func verify_failure_dialog():
	var previous_run = panel.run_id
	var previous_link = panel.service_config_link.visible
	panel.run_id = 'synthetic-failure-run'
	var reason = 'Kimi 视觉理解与复核缺少 KIMI_API_KEY；合成测试未提交生成。'
	var failed = {'state':'failed','nodes':{'broken':{'state':'failed','attempt':0,'error':'provider_failed','public_error':reason,'job':{'error':'provider_failed'}}}}
	panel._controller_completed('status',failed,{})
	check(panel.failure_dialog.visible and panel.failure_text.text.contains(reason) and panel.failure_text.text.contains('broken'),'failed node opens a dialog containing the actual provider reason')
	check(not panel.failure_text.editable and panel.failure_text.selecting_enabled and panel.failure_copy_button.text=='复制全部报错','failure dialog provides selectable text and an explicit copy action')
	var notice_count = panel.failure_notices.size()
	panel._controller_completed('status',failed,{})
	check(panel.failure_notices.size()==notice_count,'automatic polling does not repeatedly open the same node failure')
	panel.failure_copy_button.pressed.emit()
	if DisplayServer.has_feature(DisplayServer.FEATURE_CLIPBOARD):
		check(DisplayServer.clipboard_get()==panel.failure_text.text and panel.failure_copy_hint.text.contains('已复制'),'copy action places the complete failure on the clipboard')
	else:
		check(panel.failure_copy_hint.text.contains('手动选择文本复制'),'unsupported display offers manual selection instead of a false clipboard success')
	panel.failure_dialog.hide()
	panel._show_run_problem('服务配置无效：合成测试','ai')
	check(panel.failure_dialog.visible and panel.failure_text.text.contains('服务配置无效'),'service and validation failures use the same copyable dialog')
	panel.failure_dialog.hide()
	panel.run_id = previous_run
	panel.service_config_link.visible = previous_link

func verify_importer_conversion():
	var converter = load(panel.get_script().resource_path.get_base_dir().path_join('runtime_mesh.gd'))
	if not check(converter!=null,'bundled local GLTF runtime converter loads'): return
	var holder = Node3D.new()
	var imported = ImporterMeshInstance3D.new()
	imported.name = 'Imported'
	var primitive = BoxMesh.new()
	var material = StandardMaterial3D.new()
	primitive.material = material
	imported.mesh = ImporterMesh.from_mesh(primitive)
	imported.mesh.set_meta('source_mesh_revision','fixture')
	var skin = Skin.new()
	skin.add_bind(0,Transform3D.IDENTITY)
	imported.skin = skin
	imported.skeleton_path = NodePath('../Skeleton3D')
	var transform = Transform3D(Basis.from_euler(Vector3(.1,.2,.3)),Vector3(1,2,3))
	imported.transform = transform
	imported.visible = false
	imported.layer_mask = 4
	imported.visibility_range_end = 20
	imported.set_meta('source_node_revision','fixture')
	imported.add_to_group('ainative_conversion_fixture',true)
	holder.add_child(imported)
	imported.owner = holder
	var child = Node3D.new()
	child.name = 'Child'
	child.position = Vector3(0,.5,0)
	imported.add_child(child)
	child.owner = imported
	var animation = Animation.new()
	var track = animation.add_track(Animation.TYPE_POSITION_3D)
	animation.track_set_path(track,NodePath('Imported/Child'))
	converter.convert_scene(holder)
	var converted = holder.get_node('Imported')
	check(converted is MeshInstance3D and converted.mesh.get_surface_count()==1,'local conversion produces actual runtime Mesh geometry')
	check(converted.transform.is_equal_approx(transform) and converted.skin==skin and converted.skeleton==NodePath('../Skeleton3D'),'local conversion preserves transforms, Skin and skeleton binding')
	check(converted.get_meta('source_node_revision')=='fixture' and converted.mesh.get_meta('source_mesh_revision')=='fixture','local conversion preserves node and mesh provenance metadata')
	check(converted.owner==holder and child.owner==converted and child.get_parent()==converted,'local conversion preserves child relationships and scene ownership')
	check(not converted.visible and converted.layers==4 and converted.visibility_range_end==20 and converted.is_in_group('ainative_conversion_fixture'),'local conversion preserves visibility, rendering layers and groups')
	check(converted.mesh.surface_get_material(0)==material,'local conversion preserves surface materials')
	check(holder.get_node(animation.track_get_path(track))==child,'animation target NodePaths still resolve after local conversion')
	holder.free()
	var imported_root = ImporterMeshInstance3D.new()
	imported_root.name = 'DetachedImporterRoot'
	imported_root.mesh = ImporterMesh.from_mesh(BoxMesh.new())
	var branch = Node3D.new()
	branch.name = 'Branch'
	imported_root.add_child(branch)
	branch.owner = imported_root
	var nested = ImporterMeshInstance3D.new()
	nested.name = 'NestedMesh'
	nested.mesh = ImporterMesh.from_mesh(BoxMesh.new())
	branch.add_child(nested)
	nested.owner = imported_root
	var descendant = Node3D.new()
	descendant.name = 'Descendant'
	nested.add_child(descendant)
	descendant.owner = imported_root
	var converted_root = converter.convert_scene(imported_root)
	check(converted_root is MeshInstance3D and converted_root.get_parent()==null,'local conversion supports an unparented importer root')
	check(branch.owner==converted_root and converted_root.get_node('Branch/NestedMesh').owner==converted_root and descendant.owner==converted_root,'root-owned descendants retain scene ownership through nested conversion')
	converted_root.free()

func verify_mesh():
	var source = ProjectSettings.globalize_path('res://fixture.glb')
	var before = FileAccess.get_sha256(source)
	# Source fields are display-only; the picker owns the node's source paths.
	panel.source_picker.file_selected.emit(source)
	check(panel.nodes[0].source == source and panel.source_edit.text == source, 'offline Mesh fixture is selected through the real source picker')
	panel.params_edit.text = '{"delay":0.15,"fail":false}'
	panel.factory_edit.text = 'editor_demo:factory'
	var heartbeat = panel.heartbeat
	var node_action: Button
	for action in panel.graph.get_node(panel.selected_id).find_children("*", "Button", true, false):
		if action.text == "运行并预览": node_action = action
	if not check(node_action != null, "bundled graph has explicit node preview action"): return
	node_action.pressed.emit()
	if not await wait_idle(): return
	details.mesh_execution = {'current':panel.current.duplicate(true), 'status':panel.status.text, 'selected':panel.selected_id, 'nodes':panel.nodes.duplicate(true)}
	if not check(panel.current.get('state')=='succeeded','offline Copy Mesh run reaches real Executor success'): return
	check(panel.heartbeat>heartbeat+5,'editor heartbeat advances during provider execution')
	check(panel.preview_node == panel.selected_id and panel.preview_history.get(panel.selected_id, []).size() == 1, "bundled node action automatically previews and records its result")
	panel.request_preview()
	if not await wait_idle(): return
	if not check(is_instance_valid(panel.preview_scene),'actual GLB preview is decoded'): return
	var meshes = panel.preview_scene.find_children('*','MeshInstance3D',true,false)
	if panel.preview_scene is MeshInstance3D: meshes.append(panel.preview_scene)
	check(not meshes.is_empty(),'decoded preview contains Mesh geometry')
	panel.target_edit.text = panel.state_dir.path_join('mesh-v1.tscn')
	panel.review_publish()
	check(not FileAccess.file_exists(panel.target_edit.text) and not panel.confirmation.is_empty(),'publication waits for explicit confirmation')
	panel.confirm_publish()
	panel.dialog.hide()
	if not await wait_idle(): return
	check(ResourceLoader.load(panel.target_edit.text,'PackedScene',ResourceLoader.CACHE_MODE_IGNORE) is PackedScene,'confirmed Mesh publication reloads')
	var published = FileAccess.get_sha256(panel.target_edit.text)
	panel.review_publish()
	panel.confirm_publish()
	panel.dialog.hide()
	if not await wait_idle(): return
	check(FileAccess.get_sha256(panel.target_edit.text)==published and panel.status.text.contains('失败'),'Mesh publication cannot overwrite an existing version')
	check(FileAccess.get_sha256(source)==before,'offline run and publication preserve source Mesh bytes')
	var result_node = panel.selected_id
	panel.path_edit.text = panel.state_dir.path_join('generated-workflow.json')
	panel.save_graph()
	var saved_workflow = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	check(saved_workflow.get('output_history',{}).get(result_node,[]).size()==1,'builtin workflow embeds the generated GLB after execution')
	panel.open_graph()
	panel.select_node(result_node)
	print('OUTPUT_PERSISTENCE_STATUS ',panel.status.text,' RUN ',panel.run_id,' HISTORY ',panel.preview_history.keys(),' PATH ',panel.preview_source_path)
	check(panel.run_id.is_empty() and panel.preview_history.get(result_node,[]).size()==1,'builtin workflow restores generated-result history without another Executor run')
	check(panel.preview_source_path.begins_with(panel.path_edit.text+'.assets/') and FileAccess.get_sha256(panel.preview_source_path)==before,'builtin restored GLB is a durable byte-identical content-addressed file')
	check(is_instance_valid(panel.preview_scene),'builtin restored GLB decodes into the existing Mesh preview')
	panel.native_buttons.other.pressed.emit()
	await process_frame
	check(panel.native_sections.split.is_visible_in_tree() and panel.mesh_container.is_visible_in_tree(),'other tools retain the shared Mesh preview viewport')
	check(panel.viewport.render_target_update_mode!=SubViewport.UPDATE_DISABLED,'shared preview rendering remains enabled')
	panel.native_buttons.rig.pressed.emit()
	await process_frame
	check(not panel.graph.visible and panel.rigging_panel.is_visible_in_tree(),'rigging navigation opens its controls directly')

func make_humanoid(path: String, include_review: bool = true) -> bool:
	var scene = Node3D.new()
	scene.name = 'SyntheticTPoseFixtureNotAI'
	for box in [
		[Vector3(0,1.05,0),Vector3(.38,.62,.22)],
		[Vector3(0,1.6,0),Vector3(.25,.35,.25)],
		[Vector3(0,1.405,0),Vector3(.12,.12,.12)],
		[Vector3(-.05,1.63,.126),Vector3(.04,.025,.015)],
		[Vector3(.05,1.63,.126),Vector3(.04,.025,.015)],
		[Vector3(0,1.585,.14),Vector3(.04,.06,.04)],
		[Vector3(0,1.52,.127),Vector3(.075,.014,.012)],
		[Vector3(0,1.46,.126),Vector3(.1,.035,.02)],
		[Vector3(.55,1.28,0),Vector3(.8,.16,.16)],
		[Vector3(-.55,1.28,0),Vector3(.8,.16,.16)],
		[Vector3(.11,.38,0),Vector3(.16,.76,.18)],
		[Vector3(-.11,.38,0),Vector3(.16,.76,.18)]]:
		var mesh = BoxMesh.new()
		mesh.size = box[1]
		mesh.subdivide_width = 2
		mesh.subdivide_height = 2
		mesh.subdivide_depth = 2
		var instance = MeshInstance3D.new()
		instance.mesh = mesh
		instance.position = box[0]
		scene.add_child(instance)
		instance.owner = scene
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	var error = document.append_from_scene(scene,state)
	if error==OK: error = document.write_to_filesystem(state,path)
	scene.free()
	if error != OK: return check(false,'synthetic T-pose GLB fixture is encoded without AI inference')
	if not include_review: return true
	# This fixture has explicit eyes, nose, mouth, chin and an overlapping neck.
	# Record only that synthetic geometry review, not a human identity verdict.
	var file = FileAccess.open(path,FileAccess.READ)
	if file == null: return check(false,'synthetic fixture GLB can be reopened')
	var geometry_sha = FileAccess.get_sha256(path)
	file.seek(12)
	var length = file.get_32()
	file.seek(20)
	var json_document = JSON.parse_string(file.get_buffer(length).get_string_from_utf8())
	var binary_size = file.get_32()
	file.get_32()
	var binary = file.get_buffer(binary_size)
	file.close()
	if not json_document is Dictionary: return check(false,'synthetic fixture GLB JSON is valid')
	json_document.asset['extras'] = json_document.asset.get('extras',{})
	json_document.asset.extras['maliang_head_review'] = {
		'schema_version':1,
		'mode':'automatic',
		'ai_reviewed':true,
		'geometry_sha256':geometry_sha,
		'head_geometry_mode':'integrated',
		'passed':true,
		'head_gate':{
			'applicable':true,
			'complete_face':true,
			'neck_join_pass':true,
			'observation':'Explicit synthetic eyes, nose, mouth, chin and overlapping neck; not a human identity assessment.'
		},
		'head_views':{'head_front':true,'head_three_quarter':true,'head_side':true},
		'evidence':'synthetic_fixture_explicit_geometry_not_identity',
		'rigging_verified':false,
		'animation_verified':false
	}
	var encoded = JSON.stringify(json_document).to_utf8_buffer()
	while encoded.size()%4 != 0: encoded.append(32)
	var output = FileAccess.open(path,FileAccess.WRITE)
	if output == null: return check(false,'synthetic fixture metadata can be written')
	output.store_string('glTF')
	output.store_32(2)
	output.store_32(28+encoded.size()+binary_size)
	output.store_32(encoded.size())
	output.store_string('JSON')
	output.store_buffer(encoded)
	output.store_32(binary_size)
	output.store_32(0x004E4942)
	output.store_buffer(binary)
	output.close()
	return check(output.get_error()==OK,'synthetic T-pose GLB fixture is encoded without AI inference')

func verify_garment_node():
	var source = ProjectSettings.globalize_path('res://rigged.glb')
	var before = FileAccess.get_sha256(source)
	panel.generator_choice.select(6)
	panel.add_generator()
	var data: Dictionary = panel.nodes.back()
	data.parameters = {"items":[{"id":"cloth","label":"测试衣服","category":"garment","slot":"other","behavior":"skinned","confidence":1.0,"review_state":"confirmed","selection":{"mode":"reviewed_triangles","primitives":[{"node":0,"primitive":0,"triangles":[0]}]}}]}
	panel.select_node(str(data.id))
	panel.source_picker.file_selected.emit(source)
	check(panel.parameter_form.garment_items_edit.visible and panel.apply_fields(),'bundled garment node applies its structured item selection')
	panel.run_node_preview(str(data.id))
	if not await wait_idle(): return
	details.garment_execution = {'current':panel.current.duplicate(true),'failure':panel.failure_text.text,'status':panel.status.text,'host':panel.host_edit.text,'selected':str(data.id)}
	check(panel.current.get('state')=='succeeded','bundled garment node executes through its installed local Provider')
	var entry: Dictionary = panel._latest_mesh_entry(str(data.id))
	check(not entry.is_empty() and entry.get('iterations',[]).size()==1,'bundled garment node publishes collection and independent garment GLB')
	check(entry.get('provenance',{}).get('rigged',false) and entry.get('provenance',{}).get('skeleton_preserved',false) and entry.get('provenance',{}).get('skin_weights_preserved',false),'bundled garment node preserves the original skeleton and skin weights')
	check(panel.host_edit.text.contains('/ainative/bundles/'),'garment node host is the actual installed bundle')
	await settle()
	var cards = panel.artifact_nodes.values().filter(func(record): return record.get('artifact_role','')=='garment')
	check(cards.size()==1 and cards[0].entry.get('provenance',{}).get('garment_id','')=='cloth','bundled garment node creates its semantic independent artifact card')
	if not entry.is_empty():
		panel.load_preview(entry,str(data.id),str(entry.get('run','')))
		await settle()
		var garment_meshes: Array = []
		if is_instance_valid(panel.preview_scene):
			garment_meshes = panel.preview_scene.find_children('*','MeshInstance3D',true,false)
			if panel.preview_scene is MeshInstance3D: garment_meshes.append(panel.preview_scene)
		check(not garment_meshes.is_empty(),'bundled garment collection preview decodes into actual Mesh geometry')
		details.garment_execution = {'host':panel.host_edit.text,'collection':entry.get('artifact',{}).duplicate(true),'status':panel.current.get('state',''),'source_sha256':before}
	check(FileAccess.get_sha256(source)==before,'bundled garment extraction preserves source GLB bytes')

func verify_rigging():
	var rig = panel.rigging_panel
	check(not rig.advanced_panel.visible,'rigging defaults to the simple one-click interface')
	rig.set_source(ProjectSettings.globalize_path('res://fixture.glb'))
	check(not rig.bind_button.disabled and rig.check_button.disabled and rig.save_button.disabled,'one-click source selection enables only binding')
	rig.confirm.button_pressed = true
	rig.fit()
	if is_instance_valid(rig.built):
		check(rig.built.get_meta('rigging',{}).get('status')=='needs_landmarks','triangle fixture is not falsely accepted as a humanoid')
		rig.target.text = panel.state_dir.path_join('must-not-publish.tscn')
		rig.save_version()
		check(not FileAccess.file_exists(rig.target.text),'unreviewed anatomy cannot be published')
	else:
		check(not rig.message.text.is_empty(),'unsuitable source is rejected with a diagnostic')
	var source = panel.state_dir.path_join('synthetic-tpose.glb')
	if not make_humanoid(source): return
	var source_hash = FileAccess.get_sha256(source)
	rig.set_source(source)
	rig.bind_one_click()
	if not check(is_instance_valid(rig.built),'synthetic T-pose builds an actual bound character through one-click binding'):
		details.rig_diagnostic = rig.message.text
		print('RIG_DIAGNOSTIC ',rig.message.text)
		return
	check(rig.params.one_click and not rig.confirm.button_pressed,'one-click binding needs no manual confirmation or advanced parameters')
	check(rig.built.get_meta('rigging',{}).get('status')=='reviewed_template','automatic anatomy checks allow a suitable T-pose to be saved')
	check(not rig.check_button.disabled and not rig.save_button.disabled,'successful one-click binding exposes deformation checking and saving')
	var skeleton = rig.built.get_node('Skeleton3D') as Skeleton3D
	var body = rig.built.get_node('Body') as MeshInstance3D
	check(skeleton.get_bone_count()==18 and body.skin.get_bind_count()==18,'binding creates 18 real bones and Skin bind poses')
	var max_rest_error = 0.0
	var valid_weights = true
	for surface in body.mesh.get_surface_count():
		var arrays = body.mesh.surface_get_arrays(surface)
		for i in arrays[Mesh.ARRAY_VERTEX].size():
			var vertex: Vector3 = arrays[Mesh.ARRAY_VERTEX][i]
			var rest = Vector3.ZERO
			var total = 0.0
			for j in 4:
				var index: int = arrays[Mesh.ARRAY_BONES][i*4+j]
				var weight: float = arrays[Mesh.ARRAY_WEIGHTS][i*4+j]
				valid_weights = valid_weights and index>=0 and index<18 and is_finite(weight) and weight>=0
				total += weight
				rest += (skeleton.get_bone_global_rest(index)*body.skin.get_bind_pose(index)*vertex)*weight
			valid_weights = valid_weights and absf(total-1)<.0001
			max_rest_error = maxf(max_rest_error,rest.distance_to(vertex))
	check(valid_weights and max_rest_error<.0002,'Skin indices, normalized weights and rest geometry are valid')
	var animation = rig.built.get_node('AnimationPlayer') as AnimationPlayer
	var movement = {}
	for motion in ['raise_arms','squat','turn']:
		rig.play(motion)
		animation.advance(1.0)
		skeleton.force_update_all_bone_transforms()
		var maximum = 0.0
		for surface in body.mesh.get_surface_count():
			var arrays = body.mesh.surface_get_arrays(surface)
			for i in arrays[Mesh.ARRAY_VERTEX].size():
				var vertex: Vector3 = arrays[Mesh.ARRAY_VERTEX][i]
				var deformed = Vector3.ZERO
				for j in 4:
					var index: int = arrays[Mesh.ARRAY_BONES][i*4+j]
					deformed += (skeleton.get_bone_global_pose(index)*body.skin.get_bind_pose(index)*vertex)*arrays[Mesh.ARRAY_WEIGHTS][i*4+j]
				maximum = maxf(maximum,deformed.distance_to(vertex))
		movement[motion] = maximum
		check(animation.current_animation==motion and maximum>.01,'actual skinned ROM deformation: '+motion)
	details.rom_maximum_displacement = movement
	rig.check_deformations()
	check(animation.current_animation=='raise_arms' and rig.deformation_queue.size()==3,'deformation check starts the automatic motion sequence')
	rig._process(2.1)
	check(animation.current_animation=='squat','deformation check advances to squat')
	rig._process(2.1)
	check(animation.current_animation=='turn','deformation check advances to turn')
	rig._process(2.1)
	check(rig.deformation_queue.is_empty() and animation.current_animation.is_empty(),'deformation check restores the rest pose')
	rig.target.text = panel.state_dir.path_join('rig-v1.tscn')
	rig.save_version()
	if not check(FileAccess.file_exists(rig.target.text),'reviewed rig publishes a new character version'): return
	var saved = FileAccess.get_sha256(rig.target.text)
	rig.save_version()
	check(FileAccess.get_sha256(rig.target.text)==saved,'rig publication cannot overwrite an existing version')
	rig.source = ''
	rig.source_field.text = ''
	rig.reopen()
	check(is_instance_valid(rig.built) and rig.source==source and rig.source_field.text==source,'reopening a bound version restores both source model state and visible source input')
	check(FileAccess.get_sha256(source)==source_hash,'binding, animation and publication preserve source GLB bytes')
	verify_humanoid_node(source)
	rig.target.text = panel.state_dir.path_join('rig-v1.tscn')
	rig.reopen()

func synthetic_ai_receipt(source_sha: String) -> Dictionary:
	return {'passed':true,'source_sha256':source_sha,'head_review':{
		'schema_version':2,'mode':'automatic','ai_reviewed':true,'passed':true,
		'geometry_sha256':source_sha,'source_sha256':source_sha,'head_geometry_mode':'integrated',
		'head_gate':{'applicable':true,'complete_face':true,'neck_join_pass':true,'identity_pass':true,'face_proportions_pass':true,'animation_geometry_pass':true,'observation':'synthetic AI adapter receipt'},
		'head_views':{'head_front':true,'head_three_quarter':true,'head_side':true},
		'acceptance':{'top_view':'approximate_allowed','face':'recognizable_identity_normal_proportions','animation':'geometry_readiness_only_rig_unverified'},
		'animation_geometry_ready':true,'rigging_verified':false,'animation_verified':false}}

func verify_humanoid_node(source: String):
	panel.humanoid_text_review_fixture = {
		'schema_version':1,'text_only':true,'synthetic':true,'passed':true,'local_passed':true,
		'summary':'合成文本回执：本地实测证据完整。','issues':[],'feedback':[],
		'repair':{'command':'none','parameters':{}},'retry_count':1,'max_retries':3,
		'review_document':{'schema_version':1,'passed':true},'api_receipt':{'provider':'synthetic_fixture'}
	}
	var id = 'humanoid_node'
	panel.nodes.append({'id':id,'type':'humanoid_rig','version':'1','provider':'local-humanoid-rig','source':source,'image_context':'','text':'','parameters':{'height_m':1.8},'x':40.0,'y':60.0})
	panel.rebuild()
	panel.select_node(id)
	check(panel.node_run_blocker(id).is_empty(),'bundled humanoid node runs without a generation service')
	panel.run_node_preview(id)
	var entry = panel._latest_character_entry(id)
	check(not entry.is_empty() and not entry.get('provenance',{}).get('capability_limited',true),'bundled humanoid node produces a fully ROM-validated character')
	if entry.is_empty():
		details.humanoid_node_diagnostic = panel.status.text
		return
	check(entry.provenance.get('anatomical_bone_count',0)==17 and entry.provenance.get('validation',{}).get('bone_count',0)==18,'bundled node output has seventeen anatomical bones plus independent root')
	check(FileAccess.file_exists(entry.path) and FileAccess.get_sha256(entry.path)==entry.artifact.revision,'bundled character artifact is durable and digest-bound')
	panel._open_preview_rigging()
	check(panel.rigging_panel.visible and is_instance_valid(panel.rigging_panel.built) and panel.rigging_panel.source==source,'double-click action enters bundled rigging with the matching source')
	var unreviewed = panel.state_dir.path_join('synthetic-unreviewed.glb')
	if not make_humanoid(unreviewed,false): return
	panel.show_native_section('mesh')
	panel.select_node(id)
	panel._set_node_file('source',unreviewed)
	var before = panel.preview_history.get(id,[]).size()
	check(panel.has_method('_start_humanoid_ai_review') and not panel.has_method('_confirm_head_review'),'bundled node exposes AI review and no manual confirmation callback')
	var input_entry = panel._direct_humanoid_input(id)
	panel.humanoid_review_node = id
	panel.humanoid_review_source = unreviewed
	panel.humanoid_review_directory = 'synthetic-native-ai-review'
	panel.humanoid_review_input = input_entry.duplicate(true)
	panel._complete_humanoid_ai_review(synthetic_ai_receipt(FileAccess.get_sha256(unreviewed)),{'directory':'synthetic-native-ai-review'})
	var reviewed = panel._latest_character_entry(id)
	check(not reviewed.is_empty() and panel.preview_history.get(id,[]).size()>before and reviewed.get('provenance',{}).get('source_sha256','')==FileAccess.get_sha256(unreviewed),'accepted synthetic AI receipt resumes the bundled rig and binds the new source')

func prepare_portable_runtime():
	var rig = panel.rigging_panel
	if not is_instance_valid(rig.built): return
	var portable = rig.built.duplicate()
	var controller = Node.new()
	controller.name = 'LayeringPlayer'
	var scripts = panel.get_script().resource_path.get_base_dir()
	controller.set_script(load(scripts.path_join('layering_player.gd')))
	controller.set('playing',false)
	controller.set('player_path',NodePath('../AnimationPlayer'))
	controller.set('skeleton_path',NodePath('../Skeleton3D'))
	portable.add_child(controller)
	controller.owner = portable
	var packed = PackedScene.new()
	var stage = panel.state_dir.path_join('portable-runtime-stage.tscn')
	var error = packed.pack(portable)
	if error==OK: error = ResourceSaver.save(packed,stage)
	portable.free()
	if not check(error==OK,'character with a real built-in runtime script stages successfully'): return
	var directory = OS.get_environment('AINATIVE_TEST_TRANSFER')
	DirAccess.make_dir_recursive_absolute(directory)
	var target = directory.path_join('character.tscn')
	var output = []
	var code = OS.execute(panel.python_edit.text,[str(panel.get_meta('ainative_tools_dir')).path_join('interop_publish.py'),stage,target],output,true)
	check(code==0 and FileAccess.file_exists(target),'bundled publisher creates a portable runtime dependency directory')
	if code==0:
		var scene_text = FileAccess.get_file_as_string(target)
		check(not scene_text.contains(scripts) and scene_text.contains('.ainative-'),'portable scene uses relative script paths without an editor-cache reference')

func verify_portable_runtime():
	var packed = load('res://portable/character.tscn')
	if not check(packed is PackedScene,'portable character loads in a different project without editor bundles'): return
	var character = packed.instantiate()
	root.add_child(character)
	await process_frame
	var controller = character.get_node_or_null('LayeringPlayer')
	check(controller!=null and controller.get_script()!=null,'published runtime script and its preload dependencies load')
	if controller:
		check(controller.get_script().resource_path.begins_with('res://portable/'),'runtime script resolves from the copied artifact directory')
		check(not controller.get('playing'),'runtime exported properties survive publication and relocation')
	check(character.get_node('Skeleton3D').get_bone_count()==18,'relocated character retains actual skeleton data')
	character.queue_free()
	await process_frame
