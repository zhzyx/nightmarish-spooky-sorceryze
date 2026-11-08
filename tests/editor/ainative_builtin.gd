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
	check(kinds==['text_to_image','image_to_image','image_to_mesh','text_to_mesh'],'all four generation node kinds are available')
	for i in panel.generator_choice.item_count:
		panel.generator_choice.select(i)
		panel.add_generator()
		check(panel.nodes.back().type==kinds[i],'Chinese generator option preserves protocol: '+kinds[i])
		panel.delete_node()
	panel.generator_choice.select(2)
	panel.select_node(panel.nodes[0].id)
	await verify_context_controls()
	verify_chinese_controls()
	await verify_settings_navigation(dock)
	await verify_generation_service_controls()
	check(panel.rigging_panel.source_field!=null,'rigging exposes a local Mesh browser/input')
	var tools = str(panel.get_meta('ainative_tools_dir',''))
	check(panel.host_edit.text==tools.path_join('editor_host.py') and FileAccess.file_exists(panel.host_edit.text),'host comes from the engine bundle')
	details.state_key = panel.state_dir.get_file()
	details.host_sha256 = FileAccess.get_sha256(panel.host_edit.text)
	var bundle = tools.get_base_dir()
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
	await verify_rigging()
	await prepare_portable_runtime()
	var capture = OS.get_environment('AINATIVE_TEST_CAPTURE')
	if not capture.is_empty():
		panel.native_buttons.rig.pressed.emit()
		await process_frame
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(capture)==OK,'native workbench screenshot saved')
	finish()

func verify_generation_service_controls():
	if not check(panel.get("service_choice") is OptionButton and panel.has_method("check_service"), 'bundled editor exposes generation service setup controls'): return
	var service_modes: Array = []
	for i in panel.service_choice.item_count: service_modes.append(panel.service_choice.get_item_metadata(i))
	check(service_modes == ["offline", "comfy", "legacy", "codex", "codex_modeling", "codex_sculpt"], 'bundled service picker preserves existing modes and adds current-login CLI generation')
	check(panel.get('cli_path_edit') is LineEdit and panel.get('managed_comfy_panel') is VBoxContainer, 'bundled CLI and local Mesh management controls are installed')
	check(panel.service_config_path.get_base_dir() == panel.state_dir and panel.service_config_path.get_file() == "generation-service.json", 'bundled service configuration is private machine state')
	check(panel._service_mode() == "offline" and panel.service_saved.is_empty(), 'fresh native project does not claim a real generation service')
	var serial = panel.serial
	panel.check_service()
	if not await wait_idle(): return
	check(panel.serial == serial + 1 and panel.service_report.get("mode") == "offline" and not panel.service_report.get("connected", true), 'bundled read-only service check reaches its Python implementation')
	check(not panel.service_report.get("capabilities", {}).get("text_to_image", {}).get("ready", true) and not FileAccess.file_exists(panel.service_config_path), 'checking offline mode neither invents generation readiness nor writes configuration')

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
	check(settings_page.is_visible_in_tree() and categories.current_tab==1 and panel.python_edit.is_visible_in_tree() and sections.environment.is_ancestor_of(panel.cli_path_edit) and not panel.native_sections.machine.visible,'old local settings action navigates to central environment')
	panel.service_settings_section = 'ai'
	panel.open_service_settings()
	await settle()
	check(settings_page.is_visible_in_tree() and categories.current_tab==0 and panel.service_choice.is_visible_in_tree() and sections.ai==panel.service_fields,'service configuration navigates to the existing AI form')
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
	panel.source_edit.text = source
	panel.params_edit.text = '{"delay":0.15,"fail":false}'
	panel.factory_edit.text = 'editor_demo:factory'
	var heartbeat = panel.heartbeat
	var node_action: Button
	for action in panel.graph.get_node(panel.selected_id).find_children("*", "Button", true, false):
		if action.text == "运行并预览": node_action = action
	if not check(node_action != null, "bundled graph has explicit node preview action"): return
	node_action.pressed.emit()
	if not await wait_idle(): return
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
	panel.native_buttons.other.pressed.emit()
	await process_frame
	check(panel.native_sections.split.is_visible_in_tree() and panel.mesh_container.is_visible_in_tree(),'other tools retain the shared Mesh preview viewport')
	check(panel.viewport.render_target_update_mode!=SubViewport.UPDATE_DISABLED,'shared preview rendering remains enabled')
	panel.native_buttons.rig.pressed.emit()
	await process_frame
	check(not panel.graph.visible and panel.rigging_panel.is_visible_in_tree(),'rigging navigation opens its controls directly')

func make_humanoid(path: String) -> bool:
	var scene = Node3D.new()
	scene.name = 'SyntheticTPoseFixtureNotAI'
	for box in [
		[Vector3(0,1.05,0),Vector3(.38,.62,.22)],
		[Vector3(0,1.6,0),Vector3(.25,.35,.25)],
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
	return check(error==OK,'synthetic T-pose GLB fixture is encoded without AI inference')

func verify_rigging():
	var rig = panel.rigging_panel
	rig.set_source(ProjectSettings.globalize_path('res://fixture.glb'))
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
	rig.confirm.button_pressed = true
	rig.fit()
	if not check(is_instance_valid(rig.built),'synthetic T-pose builds an actual bound character'):
		details.rig_diagnostic = rig.message.text
		print('RIG_DIAGNOSTIC ',rig.message.text)
		return
	check(rig.built.get_meta('rigging',{}).get('status')=='reviewed_template','suitable confirmed T-pose reaches the reviewed binding state')
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
	rig.rest()
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
