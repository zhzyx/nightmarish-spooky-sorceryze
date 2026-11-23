extends SceneTree
var panel
var checks: Array = []
var failures = 0
func check(ok: bool, label: String):
	checks.append({"passed":ok, "label":label})
	print(("PASS " if ok else "FAIL ") + label)
	if not ok: failures += 1
func _initialize(): call_deferred("run")
func run():
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = ProjectSettings.globalize_path("user://parameter-form-" + str(Time.get_ticks_usec()))
	panel.set_meta("ainative_tools_dir", ProjectSettings.globalize_path("res://../../tools/ainative"))
	root.add_child(panel)
	await process_frame
	var form = panel.parameter_form
	check(form.is_visible_in_tree(), "parameter form is visible in the native mesh workspace")
	check(not panel.params_edit.is_visible_in_tree() and not form.developer_box.visible, "normal mode hides raw JSON")
	check(form.copy_hint.is_visible_in_tree() and not form.prompt_edit.visible and not form.advanced_toggle.visible, "offline copy has no generation or delay/fail controls")
	var original = panel.nodes[0].parameters.duplicate(true)
	check(panel.apply_fields() and JSON.parse_string(JSON.stringify(panel.nodes[0].parameters)) == JSON.parse_string(JSON.stringify(original)), "opening and applying the copy form preserves legacy parameters")
	var kind_index = 0
	for kind in ["generate_image", "image_to_mesh", "text_to_mesh"]:
		panel.generator_choice.selected = kind_index
		panel.add_generator()
		var prompt_stage = kind != "image_to_mesh"
		check(form.prompt_edit.visible == prompt_stage and form.rows.width.visible and form.rows.height.visible, "type-specific prompt and image sizes: " + kind)
		check(not form.advanced_box.visible and not panel.params_edit.is_visible_in_tree(), "advanced and developer fields start folded: " + kind)
		form.advanced_toggle.button_pressed = true
		check(form.rows.mesh_steps.visible == kind.ends_with("mesh") and form.rows.denoise.visible == (kind in ["generate_image", "image_to_mesh"]), "advanced fields follow node capabilities: " + kind)
		if kind == "image_to_mesh":
			panel.nodes[-1].parameters.prompt = "旧工作流提示词"
			panel.nodes[-1].text = "旧版文字说明"
			panel.select_node(panel.nodes[-1].id)
			check(not form.prompt_edit.is_visible_in_tree() and panel.nodes[-1].parameters.prompt.is_empty() and panel.nodes[-1].text.is_empty(), "image-to-Mesh hides text and clears both legacy prompt fields")
			check(panel.apply_fields() and panel.nodes[-1].parameters.prompt.is_empty(), "applying image-to-Mesh keeps its request image-only")
		kind_index += 1
	# Real widget signals, not editing the backing JSON.
	panel.generator_choice.selected = 0
	panel.add_generator()
	var selected = panel.nodes[-1]
	form.prompt_edit.text = "红色石雕猫头鹰"
	form.prompt_edit.text_changed.emit()
	form.controls.width.value = 768
	form.controls.height.value = 1024
	form.advanced_toggle.button_pressed = true
	form.controls.seed.text = "2147483648"
	form.controls.seed.text_changed.emit("2147483648")
	form.controls.denoise.value = 0.75
	await process_frame
	check(panel.apply_fields() and selected.parameters.prompt == "红色石雕猫头鹰", "prompt widget updates the model without JSON editing")
	selected.text = "保持人脸和服装特征"
	panel.select_node(selected.id)
	check(not panel.text_edit.is_visible_in_tree() and form.prompt_edit.text == "红色石雕猫头鹰\n保持人脸和服装特征", "generation nodes merge legacy text and prompt into one visible requirement")
	check(panel.apply_fields() and selected.text.is_empty() and selected.parameters.prompt == "红色石雕猫头鹰\n保持人脸和服装特征", "applying merged requirements stores one canonical prompt without legacy duplication")
	panel.select_node(panel.nodes[0].id)
	panel.select_node(selected.id)
	check(form.prompt_edit.text == "红色石雕猫头鹰\n保持人脸和服装特征", "switching nodes does not duplicate the merged requirement")
	check(selected.parameters.width == 768 and selected.parameters.height == 1024 and selected.parameters.seed == 2147483648 and selected.parameters.denoise == 0.75, "size, large seed and strength widgets update their contract keys")
	check(panel.jobs.is_empty() and not panel.auto_step, "editing form fields never triggers model execution")
	var desired = selected.parameters.duplicate(true)
	panel.path_edit.text = panel.state_dir.path_join("form-workflow.json")
	panel.save_graph()
	panel.open_graph()
	panel.select_node(selected.id)
	check(panel.nodes[-1].parameters == desired and form.prompt_edit.text == desired.prompt and form.controls.width.value == 768, "save and reopen preserve parameters and rebuild the form")
	# Raw editing is an explicit local developer setting and remains interoperable.
	panel.developer_mode.button_pressed = true
	form.developer_toggle.button_pressed = true
	check(panel.params_edit.is_visible_in_tree(), "explicit developer mode and disclosure reveal JSON")
	panel.params_edit.text = '{"prompt":"来自旧工作流","seed":9007199254740991,"denoise":0.001,"extra":{"v":3}}'
	panel.params_edit.text_changed.emit()
	await process_frame
	check(form.prompt_edit.text == "来自旧工作流" and form.controls.seed.text == "9007199254740991", "developer JSON updates human controls without losing safe-integer precision")
	check(form.controls.denoise.value == 0.001 and form.controls.denoise.get_line_edit().text.to_float() == 0.001, "valid fractional legacy values are shown accurately rather than snapped to the arrow step")
	check(panel.apply_fields() and panel.nodes[-1].parameters.extra.v == 3 and panel.nodes[-1].parameters.denoise == 0.001, "unrepresented keys and valid non-default fractional values survive round trip")
	form.prompt_edit.text = "仅修改提示词"
	form.prompt_edit.text_changed.emit()
	check(panel.apply_fields() and panel.nodes[-1].parameters.extra.v == 3 and panel.nodes[-1].parameters.seed == 9007199254740991, "editing a form field preserves other keys and precise seed")
	panel.save_graph()
	panel.open_graph()
	panel.select_node(selected.id)
	check(panel.nodes[-1].parameters.seed == 9007199254740991 and form.controls.seed.text == "9007199254740991", "maximum safe seed survives full workflow serialization")
	panel.developer_mode.button_pressed = true
	form.developer_toggle.button_pressed = true
	var before = panel.nodes[-1].parameters.duplicate(true)
	panel.params_edit.text = "{broken"
	panel.params_edit.text_changed.emit()
	await process_frame
	check(not panel.apply_fields() and panel.nodes[-1].parameters == before, "malformed raw JSON blocks apply without corrupting the node")
	panel.params_edit.text = '{"prompt":"safe","width":65}'
	panel.params_edit.text_changed.emit()
	await process_frame
	check(not panel.apply_fields() and panel.nodes[-1].parameters == before, "unsupported image dimensions are rejected without mutation")
	panel.params_edit.text = '{"prompt":"safe","seed":9007199254740992}'
	panel.params_edit.text_changed.emit()
	await process_frame
	check(not panel.apply_fields() and panel.nodes[-1].parameters == before, "unsafe seed integers are rejected")
	panel.params_edit.text = '{"prompt":"safe","seed":true}'
	panel.params_edit.text_changed.emit()
	await process_frame
	check(not panel.apply_fields(), "booleans cannot masquerade as numeric options")
	panel.params_edit.text = '{"prompt":"safe","credentials":"fixture-only"}'
	panel.params_edit.text_changed.emit()
	await process_frame
	check(not panel.apply_fields() and panel.nodes[-1].parameters == before, "existing credential guard remains enforced")
	panel.params_edit.text = '{"prompt":"safe"}'
	panel.params_edit.text_changed.emit()
	await process_frame
	form.controls.width.get_line_edit().text = "not a number"
	form.controls.width.get_line_edit().text_changed.emit("not a number")
	check(not panel.apply_fields(), "uncommitted invalid numeric text cannot run with a stale value")
	panel.params_edit.text = '{"prompt":"safe","width":512}'
	panel.params_edit.text_changed.emit()
	await process_frame
	form.controls.width.get_line_edit().text = "896"
	form.controls.width.get_line_edit().text_changed.emit("896")
	check(panel.apply_fields() and panel.nodes[-1].parameters.width == 896, "apply captures a typed numeric draft before focus loss")
	panel.developer_mode.button_pressed = false
	check(not form.developer_box.visible and not panel.params_edit.visible, "leaving developer mode immediately hides JSON")
	panel.save_settings()
	var config = ConfigFile.new()
	config.load(panel.state_dir.path_join("local.cfg"))
	check(config.get_value("interface", "developer_mode", true) == false, "developer visibility is a machine setting")
	check(not panel.model().has("developer_mode"), "developer visibility is excluded from portable workflows")
	# The body-shape node exposes only five controls and AINative fits landmarks.
	panel.generator_choice.selected = 4
	panel.add_generator()
	var shape = panel.nodes[-1]
	var shape_id = str(shape.id)
	check(shape.type == "human_shape_adjust" and not form.prompt_edit.visible and not form.landmarks_edit.visible and not form.pose_row.visible, "human shape node uses its automatic five-control pre-rig form")
	check(form.rows.height_cm.visible and not form.rows.height_m.visible and form.rows.head_ratio.visible and form.rows.arm_length_scale.visible and form.rows.leg_length_scale.visible and form.rows.build.visible, "all five human shape controls are visible with centimeter height")
	check(shape.parameters.height_cm == 180 and shape.parameters.height_cm is int and not shape.parameters.has("height_m"), "new human shape nodes store integer centimeters")
	check(panel.apply_fields() and not shape.parameters.has("prompt") and not shape.parameters.has("landmarks") and not shape.parameters.has("reference_pose"), "default node delegates pose and landmark fitting without manufacturing an empty prompt")
	shape.parameters.confirmed = false
	shape.parameters.prompt = ""
	shape.parameters.reference_pose = "T"
	shape.parameters.landmarks = {"source_sha256":""}
	shape.parameters.height_m = 1.9
	shape.parameters.erase("height_cm")
	panel.select_node(shape_id)
	check(not shape.parameters.has("confirmed") and not shape.parameters.has("prompt") and not shape.parameters.has("landmarks") and not shape.parameters.has("reference_pose"), "legacy prompt, confirmation and empty landmarks migrate to automatic AINative fitting")
	check(form.controls.height_cm.get_line_edit().text == "190" and shape.parameters.has("height_m"), "legacy meter values migrate in the form without mutating the node before apply")
	form.controls.head_ratio.value = 9.0
	form.controls.arm_length_scale.value = 1.2
	form.controls.leg_length_scale.value = 1.1
	form.controls.build.value = 0.4
	check(panel.apply_fields() and shape.parameters.height_cm == 190 and shape.parameters.height_cm is int and not shape.parameters.has("height_m") and shape.parameters.head_ratio == 9.0 and shape.parameters.arm_length_scale == 1.2 and shape.parameters.leg_length_scale == 1.1 and shape.parameters.build == 0.4, "human shape widgets update all five contract values without manual landmarks")
	check(not shape.parameters.has("confirmed") and not shape.parameters.has("landmarks"), "automatic mode preserves neither manufactured confirmation nor manual landmarks")
	for height_cm in [170, 180, 190]:
		var height_input = form.controls.height_cm.get_line_edit()
		height_input.text = str(height_cm)
		height_input.text_changed.emit(str(height_cm))
		check(panel.apply_fields() and shape.parameters.height_cm == height_cm and shape.parameters.height_cm is int, "typed whole centimeters parse as integers: " + str(height_cm))
	panel.add_generator()
	var other_shape = panel.nodes[-1]
	var other_shape_id = str(other_shape.id)
	form.controls.height_cm.get_line_edit().text = "190"
	form.controls.height_cm.get_line_edit().text_changed.emit("190")
	check(panel.apply_fields() and other_shape.parameters.height_cm == 190, "second human shape node accepts an independent height")
	panel.select_node(shape_id)
	form.controls.height_cm.get_line_edit().text = "170"
	form.controls.height_cm.get_line_edit().text_changed.emit("170")
	check(panel.apply_fields() and shape.parameters.height_cm == 170 and other_shape.parameters.height_cm == 190, "changing one node does not overwrite another node")
	panel.path_edit.text = panel.state_dir.path_join("height-cm-workflow.json")
	panel.save_graph()
	panel.open_graph()
	panel.select_node(shape_id)
	shape = panel.nodes.filter(func(node): return node.id == shape_id)[0]
	other_shape = panel.nodes.filter(func(node): return node.id == other_shape_id)[0]
	check(shape.parameters.height_cm == 170 and other_shape.parameters.height_cm == 190 and shape.parameters.height_cm is int and other_shape.parameters.height_cm is int, "save and reopen preserve independent integer heights")
	var last_valid = shape.parameters.duplicate(true)
	for invalid_height in ["173", "180.5", "170.1", "", "not-a-number", "10", "410"]:
		var height_input = form.controls.height_cm.get_line_edit()
		height_input.text = invalid_height
		height_input.text_changed.emit(invalid_height)
		panel.run_node_preview(shape_id)
		check(not panel.apply_fields() and shape.parameters == last_valid and height_input.text == invalid_height and form.error_label.text == form.HEIGHT_CM_ERROR and panel.jobs.is_empty(), "invalid height preserves draft and last valid configuration without running: " + invalid_height)
	form.controls.height_cm.get_line_edit().text = "180"
	form.controls.height_cm.get_line_edit().text_changed.emit("180")
	check(panel.apply_fields() and shape.parameters.height_cm == 180 and other_shape.parameters.height_cm == 190, "valid correction after an invalid draft updates only the selected node")
	# Switching nodes must not leak another type's values or reopen advanced UI.
	panel.select_node(panel.nodes[0].id)
	check(form.copy_hint.visible and not form.advanced_box.visible and JSON.parse_string(JSON.stringify(panel.nodes[0].parameters)) == JSON.parse_string(JSON.stringify(original)), "node switching restores independent parameters and collapsed UI")
	# Garment splitting is a structured local Mesh node with an item-array editor.
	panel.generator_choice.selected = 6
	panel.add_generator()
	var garment = panel.nodes[-1]
	check(garment.type == "garment_split" and garment.provider == "garment-split" and garment.parameters.items.is_empty(), "garment split node starts with an explicit empty item list and local provider")
	check(form.garment_items_edit.visible and form.garment_items_label.visible and not form.prompt_edit.visible and not form.advanced_toggle.visible and not panel.node_model_edit.visible, "garment form shows item JSON without generation or remote model controls")
	check(panel.input_kind(garment) == panel.PORT_MESH and panel.output_kind(garment) == panel.PORT_MESH and not panel.context_row.visible, "garment node has Mesh input/output and no image context")
	check(form.parameters() == null and form.error_label.text.contains("非空"), "empty garment item list is rejected before execution")
	var garment_items = [{"id":"cape","label":"披风","category":"garment","slot":"back","behavior":"cloth","confidence":0.9,"review_state":"needs_review","selection":{"mode":"components","component_ids":["cmp_fixture"]}}]
	form.garment_items_edit.text = JSON.stringify(garment_items, "  ", true, true)
	form.garment_items_edit.text_changed.emit()
	check(panel.apply_fields() and garment.parameters.items == garment_items and not garment.parameters.has("prompt") and garment.text.is_empty(), "garment item editor updates the exact contract without manufacturing a prompt")
	var garment_id = str(garment.id)
	panel.path_edit.text = panel.state_dir.path_join("garment-form-workflow.json")
	panel.save_graph()
	panel.open_graph()
	panel.select_node(garment_id)
	garment = panel.nodes.filter(func(node): return node.id == garment_id)[0]
	check(garment.parameters.items == garment_items and form.garment_items_edit.visible and JSON.parse_string(form.garment_items_edit.text) == garment_items, "garment item JSON and form visibility survive workflow save and reopen")
	var valid_garment = garment.parameters.duplicate(true)
	form.garment_items_edit.text = "[1]"
	form.garment_items_edit.text_changed.emit()
	check(not panel.apply_fields() and garment.parameters == valid_garment, "non-object garment entries are rejected without replacing the last valid list")
	panel.failure_dialog.hide()
	var report = {"ok":failures == 0, "checks":checks, "failures":failures, "real_inference":false}
	var report_path = OS.get_environment("AINATIVE_PARAMETER_FORM_REPORT")
	if not report_path.is_empty():
		var file = FileAccess.open(report_path, FileAccess.WRITE)
		file.store_string(JSON.stringify(report, "  "))
	panel.queue_free()
	await process_frame
	print("AINATIVE_PARAMETER_FORM failures=" + str(failures))
	quit(1 if failures else 0)
