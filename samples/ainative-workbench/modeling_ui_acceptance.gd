extends SceneTree
# Maintained by the Maliang editor integration: local widget-only acceptance.
# No model requests, ComfyUI service, native desktop control or generated code.
var panel
var reopened
var checks: Array = []
var failures = 0
var folder = ''
func _initialize(): run.call_deferred()
func check(ok: bool, label: String):
	checks.append({'passed':ok,'label':label})
	print(('PASS ' if ok else 'FAIL ') + label)
	if not ok: failures += 1
func select_mode(mode: String):
	for i in panel.service_choice.item_count:
		if panel.service_choice.get_item_metadata(i) == mode:
			panel.service_choice.select(i)
			panel.service_choice.item_selected.emit(i)
			return
func run():
	folder = ProjectSettings.globalize_path('user://modeling-ui-' + str(Time.get_ticks_usec()))
	panel = load('res://addons/ainative/workbench.gd').new()
	panel.state_dir = folder
	root.add_child(panel)
	await process_frame
	var modes: Array = []
	for i in panel.service_choice.item_count: modes.append(panel.service_choice.get_item_metadata(i))
	check(modes == ['offline','comfy','legacy','codex','codex_modeling'], 'new modeling mode preserves all existing service identifiers and indices')
	select_mode('codex_modeling')
	panel.endpoint_edit.text = 'invalid ignored address'
	panel.cli_path_edit.text = 'codex-test-program'
	check(panel._service_mode() == 'codex_modeling' and panel.cli_fields.visible, 'real mode signal selects GPT CLI modeling controls')
	check(not panel.managed_comfy_panel.visible and panel.managed_comfy_panel.lease_path.is_empty(), 'modeling mode hides local Comfy manager and has no lease')
	check(not panel.endpoint_edit.visible and not panel.image_model_choice.visible and not panel.mesh_model_choice.visible, 'modeling does not ask for an endpoint or installed model selectors')
	check(not panel.image_model_label.visible and not panel.mesh_model_label.visible, 'unused model labels are hidden with their controls')
	var draft = panel.service_draft()
	check(draft.endpoint == '' and draft.image_model == 'builtin' and draft.mesh_model == '', 'modeling draft ignores stale endpoint and model selections')
	check(draft.godot_path == OS.get_executable_path() and draft.builder_path == ProjectSettings.globalize_path('res://addons/ainative/modeling_builder.gd'), 'modeling draft resolves current Godot and trusted sibling builder as local paths')
	check(draft.cli_path == 'codex-test-program', 'modeling draft retains selected local CLI path')
	panel.save_service_settings()
	check(panel.service_saved == draft and FileAccess.file_exists(panel.service_config_path), 'modeling settings save without service address validation')
	check(JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path)) == JSON.parse_string(JSON.stringify(draft)), 'saved provider configuration contains the exact local modeling snapshot')
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, 'selecting and saving modeling never starts generation or ComfyUI')
	var local = ConfigFile.new()
	local.load(folder.path_join('local.cfg'))
	local.set_value('managed_comfy','runtime_root','not-a-real-runtime')
	local.set_value('managed_comfy','autostart',true)
	local.save(folder.path_join('local.cfg'))
	for index in panel.generator_choice.item_count:
		panel.generator_choice.select(index)
		panel.add_generator()
		var kind = panel.nodes.back().type
		var form = panel.parameter_form
		var mesh = kind.ends_with('mesh')
		check(form.prompt_edit.visible and form.rows.width.visible == not mesh and form.rows.height.visible == not mesh, 'modeling form shows useful prompt and image-size controls: ' + kind)
		check(not form.advanced_toggle.visible and not form.rows.seed.visible and not form.rows.steps.visible and not form.rows.denoise.visible, 'modeling form hides sampling controls: ' + kind)
		var samplers_hidden = true
		for key in ['mesh_steps','mesh_resolution','octree_resolution','mesh_threshold','mesh_algorithm']:
			samplers_hidden = samplers_hidden and not form.rows[key].visible
		check(samplers_hidden, 'modeling form hides three-dimensional inference sampler controls: ' + kind)
		check(not form.developer_box.visible and not panel.params_edit.is_visible_in_tree(), 'normal modeling form keeps JSON hidden: ' + kind)
		check(panel.nodes.back().provider == ('codex-modeling' if mesh else 'codex'), 'new graph node records correct modeling or image provider: ' + kind)
		if kind == 'image_to_mesh':
			check(form.rows.prompt.text.contains('建模要求') and not form.rows.prompt.text.contains('重绘'), 'image-to-mesh prompt describes modeling constraints without image redraw')
			panel.service_report = {'capabilities':{'image_to_mesh':{'ready':true},'image_to_image':{'ready':false}}}
			panel.service_report_draft = JSON.stringify(panel.service_draft())
			check(panel._service_blocker(kind, {'parameters':{'prompt':'Use red plastic'}}).is_empty(), 'image-to-mesh constraints require no image redraw or installed mesh model')
			panel.service_report = {'capabilities':{'image_to_mesh':{'ready':false,'message':'Modeling CLI unavailable'}}}
			check(panel._service_blocker(kind).contains('Modeling CLI unavailable'), 'reported modeling capability failures block node execution explicitly')
			panel.service_report = {}
		var node_button
		for button in panel.graph.get_node(panel.selected_id).find_children('*','Button',true,false):
			if button.text == '运行并预览': node_button = button
		check(node_button != null, 'node retains explicit run-and-preview action: ' + kind)
	var ids: Array = []
	for node in panel.nodes: ids.append(node.id)
	panel.nodes[0].source = ProjectSettings.globalize_path('res://fixtures/sample.png')
	panel.edges = [{'from':ids[0],'to':ids[1]}]
	panel.path_edit.text = folder.path_join('modeling-workflow.json')
	check(panel.apply_fields(), 'editing modeling nodes keeps parameter validation')
	panel.save_graph()
	var workflow = FileAccess.get_file_as_string(panel.path_edit.text)
	check(not workflow.contains('godot_path') and not workflow.contains('builder_path') and not workflow.contains('codex-test-program'), 'shareable workflow never includes local executables or builder paths')
	panel.open_graph()
	check(panel.nodes.size() == 5 and panel.edges == [{'from':ids[0],'to':ids[1]}], 'workflow serialization preserves all node types and graph connections')
	check(panel.nodes[0].has('source_snapshot'), 'workflow retains embedded input snapshots')
	reopened = load('res://addons/ainative/workbench.gd').new()
	reopened.state_dir = folder
	root.add_child(reopened)
	await process_frame
	check(reopened._service_mode() == 'codex_modeling' and reopened.service_saved == draft and reopened.service_draft() == draft, 'reopening restores selected modeling service and exact machine snapshot')
	check(not reopened.managed_comfy_panel.visible and reopened.jobs.is_empty() and reopened.managed_comfy_panel.lease_path.is_empty(), 'old saved Comfy autostart cannot start a service in modeling mode')
	select_mode('codex')
	panel.select_node(ids[4])
	check(panel.managed_comfy_panel.visible and panel.mesh_model_choice.visible and not panel.endpoint_edit.visible, 'legacy Codex local-model settings remain available')
	check(panel.parameter_form.rows.mesh_steps.visible and panel.parameter_form.rows.seed.visible and panel.parameter_form.advanced_toggle.visible, 'legacy Codex mesh sampling controls return after switching modes')
	select_mode('comfy')
	check(panel.endpoint_edit.visible and panel.endpoint_edit.editable and panel.image_model_choice.visible, 'Comfy settings remain compatible and independent')
	check(panel.parameter_form.rows.steps.visible and panel.parameter_form.rows.denoise.visible == false, 'standard sampler controls return after leaving modeling mode')
	var receipt = OS.get_environment('AINATIVE_TEST_RECEIPT')
	if not receipt.is_empty():
		var output=FileAccess.open(receipt,FileAccess.WRITE)
		output.store_string(JSON.stringify({'ok':failures==0,'checks':checks},'  '));output.close()
	panel.queue_free();reopened.queue_free()
	await process_frame
	print('MODELING_UI_OK' if failures==0 else 'MODELING_UI_FAILED')
	quit(0 if failures==0 else 1)
