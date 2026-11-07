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
	for kind in ["text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh"]:
		panel.generator_choice.selected = kind_index
		panel.add_generator()
		var image_stage = kind != "image_to_mesh"
		check(form.prompt_edit.visible == image_stage and form.rows.width.visible == image_stage and form.rows.height.visible == image_stage, "type-specific prompt and image sizes: " + kind)
		check(not form.advanced_box.visible and not panel.params_edit.is_visible_in_tree(), "advanced and developer fields start folded: " + kind)
		form.advanced_toggle.button_pressed = true
		check(form.rows.mesh_steps.visible == kind.ends_with("mesh") and form.rows.denoise.visible == (kind == "image_to_image"), "advanced fields follow node capabilities: " + kind)
		kind_index += 1
	# Real widget signals, not editing the backing JSON.
	panel.generator_choice.selected = 1
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
	# Switching nodes must not leak another type's values or reopen advanced UI.
	panel.select_node(panel.nodes[0].id)
	check(form.copy_hint.visible and not form.advanced_box.visible and JSON.parse_string(JSON.stringify(panel.nodes[0].parameters)) == JSON.parse_string(JSON.stringify(original)), "node switching restores independent parameters and collapsed UI")
	var report = {"ok":failures == 0, "checks":checks, "failures":failures, "real_inference":false}
	var report_path = OS.get_environment("AINATIVE_PARAMETER_FORM_REPORT")
	if not report_path.is_empty():
		var file = FileAccess.open(report_path, FileAccess.WRITE)
		file.store_string(JSON.stringify(report, "  "))
	panel.queue_free()
	await process_frame
	print("AINATIVE_PARAMETER_FORM failures=" + str(failures))
	quit(1 if failures else 0)
