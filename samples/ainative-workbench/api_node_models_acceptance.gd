extends SceneTree

var panel
var checks: Array = []

func check(value, label):
	checks.append({'label': label, 'ok': bool(value)})
	print(('PASS ' if value else 'FAIL ') + label)

func _initialize():
	run.call_deferred()

func run():
	panel = load('res://addons/ainative/workbench.gd').new()
	panel.state_dir = OS.get_environment('AINATIVE_UI_STATE')
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.set_meta('ainative_builtin', true)
	panel.set_meta('ainative_tools_dir', OS.get_environment('AINATIVE_UI_TOOLS'))
	root.add_child(panel)
	for i in 4: await process_frame
	for mode in ['api_modeling', 'api_sculpt']:
		panel.nodes.clear()
		panel.edges.clear()
		panel.selected_id = ''
		panel.select_service_mode(mode)
		panel.endpoint_edit.text = 'https://example.test/v1'
		panel.blender_path_edit.text = OS.get_environment('AINATIVE_PYTHON')
		panel.service_saved = {'api_key_env': 'AINATIVE_NODE_FIXTURE_KEY'}
		panel._update_service_summary()
		panel.save_service_settings()
		check(panel.service_saved.mode == mode and not panel.service_saved.has('api_model'), mode + ' saves connection without model')
		check(not panel.kimi_model_edit.visible and not panel.kimi_model_label.visible, mode + ' no global model control')
		panel._restore_service_settings(ConfigFile.new())
		check(panel.service_draft() == panel.service_saved, mode + ' restores connection without hidden model dependency')
		panel.check_service()
		var deadline = Time.get_ticks_msec() + 15000
		while not panel.jobs.is_empty() and Time.get_ticks_msec() < deadline:
			await process_frame
		check(panel.jobs.is_empty() and panel.service_report.get('connected', false), mode + ' real host connection check works without model')
		check(panel.service_report.get('capabilities', {}).get('text_to_mesh', {}).get('ready', false), mode + ' real host capability reaches UI')
		for i in panel.generator_choice.item_count:
			if panel.generator_choice.get_item_metadata(i) == 'text_to_mesh': panel.generator_choice.select(i)
		panel.add_generator()
		var first = panel.nodes[-1]
		check(first.model == '', mode + ' new node explicitly requires choice')
		check('节点检查器' in panel._service_blocker('text_to_mesh', first), mode + ' empty node blocked at node entry')
		check(not panel.node_image_model_edit.visible and not panel.node_model_choice.visible, mode + ' manual API entry without nonexistent catalog or auxiliary model')
		panel.node_model_edit.text = 'model-a'
		check(panel.apply_fields(), mode + ' first inspector choice saves')
		panel.add_generator()
		var second = panel.nodes[-1]
		panel.node_model_edit.text = 'model-b'
		check(panel.apply_fields(), mode + ' second inspector choice saves')
		panel.select_node(first.id)
		check(panel.node_model_edit.text == 'model-a', mode + ' switching nodes restores own choice')
		check('model-a' in panel._generator_description(first) and 'model-b' in panel._generator_description(second), mode + ' summaries show independent models')
		check(panel._service_blocker('text_to_mesh', first).is_empty(), mode + ' valid node not blocked by absent global model')
		for invalid in ['', 'bad\nmodel', 'gpt-4o', 'x'.repeat(257), 'openai/other']:
			var bad = first.duplicate(true)
			bad.model = invalid
			check('节点检查器' in panel._service_blocker('text_to_mesh', bad), mode + ' invalid node rejected: ' + str(invalid.length()))
		panel.context_node_ids = [first.id]
		panel.context_model = JSON.stringify(panel.model(), "", true, true)
		panel.context_run = panel.run_id
		panel.context_selection = panel._graph_selected_ids()
		panel.context_inspected_id = panel.selected_id
		var copied = panel.duplicate_context_nodes()
		check(copied.size() == 1 and panel.nodes[-1].model == 'model-a', mode + ' copied node retains own model')
		panel.path_edit.text = panel.state_dir.path_join(mode + '.json')
		panel.save_graph()
		panel.open_graph()
		check(panel.nodes[0].model == 'model-a' and panel.nodes[1].model == 'model-b', mode + ' save and reopen preserve selections')
		var portable = panel.model().duplicate(true)
		portable.nodes[0].erase('model')
		portable.nodes[1].model = ''
		var output = FileAccess.open(panel.path_edit.text, FileAccess.WRITE)
		output.store_string(JSON.stringify(portable))
		output.close()
		panel.service_saved.api_model = 'legacy-a'
		panel.save_service_settings()
		check(panel.service_saved.api_model == 'legacy-a', mode + ' connection save retains unopened legacy migration source')
		panel._restore_service_settings(ConfigFile.new())
		panel.open_graph()
		check(panel.nodes[0].model == 'legacy-a' and panel.nodes[1].model == '', mode + ' legacy import migrates only absent field')
		panel.save_graph()
		panel.service_saved.api_model = 'legacy-b'
		panel.save_service_settings()
		panel.open_graph()
		check(panel.nodes[0].model == 'legacy-a' and panel.nodes[1].model == '', mode + ' persisted migration runs once')
		panel.add_generator()
		check(panel.nodes[-1].model == '', mode + ' new node never inherits retained migration source')
		check(not 'api_key_env' in FileAccess.get_file_as_string(panel.path_edit.text), mode + ' workflow contains no connection credentials')
		for invalid in [123, 1.5, true, null, [], {}]:
			var legacy_bad = first.duplicate(true)
			legacy_bad.erase('model')
			panel._migrate_node_models(legacy_bad, {'mode': mode, 'api_model': invalid})
			check(legacy_bad.model == '', mode + ' invalid legacy type requires explicit correction: ' + str(typeof(invalid)))
			panel.nodes = [legacy_bad]
			panel.select_node(legacy_bad.id)
			panel.apply_fields()
			check(not panel._service_blocker('text_to_mesh', legacy_bad).is_empty(), mode + ' applying untouched legacy inspector remains blocked: ' + str(typeof(invalid)))
			legacy_bad.model = invalid
			panel.select_node(legacy_bad.id)
			panel.apply_fields()
			check(legacy_bad.model == '' and not panel._service_blocker('text_to_mesh', legacy_bad).is_empty(), mode + ' explicit invalid node type never becomes a model string: ' + str(typeof(invalid)))
		var padded = first.duplicate(true)
		padded.model = ' padded '
		panel.nodes = [padded]
		panel.select_node(padded.id)
		panel.apply_fields()
		check(padded.model == ' padded ' and not panel._service_blocker('text_to_mesh', padded).is_empty(), mode + ' untouched padded model remains invalid')
		panel.node_model_edit.text = 'corrected-model'
		panel.apply_fields()
		check(padded.model == 'corrected-model' and panel._service_blocker('text_to_mesh', padded).is_empty(), mode + ' explicit valid correction recovers invalid imported node')
	var ok = checks.all(func(item): return item.ok)
	var report = FileAccess.open(OS.get_environment('AINATIVE_API_NODE_REPORT'), FileAccess.WRITE)
	report.store_string(JSON.stringify({'ok': ok, 'checks': checks}, '  '))
	report.close()
	panel.queue_free()
	await process_frame
	quit(0 if ok else 1)
