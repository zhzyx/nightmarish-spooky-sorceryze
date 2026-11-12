extends SceneTree
# Real Godot controls and immutable workflow snapshots; no model inference.
var panel
var state_path = ""
var failures = 0
var checks: Array = []
var front = ""
var side = ""
var reference = ""

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed":ok, "label":label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func add_kind(kind: String) -> String:
	for index in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(index) == kind:
			panel.generator_choice.select(index)
			panel.add_generator()
			return panel.nodes.back().id
	check(false, "generator kind exists: " + kind)
	return ""

func node(id: String) -> Dictionary:
	for data in panel.nodes:
		if data.id == id: return data
	return {}

func find_node(model: Dictionary, id: String) -> Dictionary:
	for data in model.nodes:
		if data.id == id: return data
	return {}

func write_model(model: Dictionary):
	var file = FileAccess.open(panel.path_edit.text, FileAccess.WRITE)
	file.store_string(JSON.stringify(model, "\t", true, true))
	file.close()

func reject_model(model: Dictionary, label: String):
	var before = JSON.stringify(panel.model())
	write_model(model)
	panel.open_graph()
	check(JSON.stringify(panel.model()) == before and panel.status.text.contains("无效") or panel.status.text.contains("不一致"), label)

func make_source(path: String, color: Color, size: Vector2i):
	var image = Image.create_empty(size.x, size.y, false, Image.FORMAT_RGBA8)
	image.fill(color)
	check(image.save_png(path) == OK, "test source is created without external assets: " + path.get_file())

func run():
	root.size = Vector2i(1440, 1000)
	state_path = OS.get_environment("AINATIVE_MULTI_IMAGE_STATE")
	if state_path.is_empty(): state_path = ProjectSettings.globalize_path("user://multi-image-" + str(Time.get_ticks_usec()))
	state_path = state_path.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	front = state_path.path_join("front.png")
	side = state_path.path_join("side.png")
	reference = state_path.path_join("reference.png")
	make_source(front, Color("b84732"), Vector2i(96, 64))
	make_source(side, Color("3264b8"), Vector2i(64, 96))
	make_source(reference, Color("4b9b66"), Vector2i(64, 64))
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.state_dir = state_path
	panel.set_meta("ainative_builtin", true)
	root.add_child(panel)
	await process_frame
	var upstream = add_kind("text_to_image")
	var downstream = add_kind("image_to_image")
	var mesh = add_kind("image_to_mesh")
	panel.select_node(downstream)
	var data = node(downstream)
	if data.is_empty():
		await finish()
		return
	check(panel.source_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES and panel.context_picker.file_mode == FileDialog.FILE_MODE_OPEN_FILES, "both image input pickers accept multiple local files")
	panel.source_picker.files_selected.emit(PackedStringArray([front, side]))
	panel.context_picker.files_selected.emit(PackedStringArray([reference]))
	check(data.source_paths == [front, side] and data.image_context_paths == [reference], "file dialog preserves source and reference ordering")
	panel.source_picker.files_selected.emit(PackedStringArray([front, side, front, side, front, side, front, side]))
	check(data.source_paths.size() == 2 and panel.status.text.contains("最多 8"), "source plus reference cannot exceed eight images")
	panel.source_picker.files_selected.emit(PackedStringArray([front, side]))
	panel.parameter_form.outputs_edit.text = "正面\n三分之四侧面"
	panel.parameter_form.outputs_edit.text_changed.emit()
	check(panel.apply_fields() and data.parameters.output_count == 2 and data.parameters.output_labels == ["正面", "三分之四侧面"], "two named outputs are stored as independent output specifications")
	check(panel.model().nodes.all(func(item): return item.version == "2" if item.type in ["text_to_image", "image_to_image"] else item.version == "1"), "multi-image version applies only to image generation nodes")
	var before_invalid = data.parameters.duplicate(true)
	for invalid in ["0", "9", "正面\n正面"]:
		panel.parameter_form.outputs_edit.text = invalid
		panel.parameter_form.outputs_edit.text_changed.emit()
		check(not panel.apply_fields() and data.parameters == before_invalid, "invalid output draft blocks applying stale specifications: " + invalid.replace("\n", "/"))
	panel.parameter_form.outputs_edit.text = "正面\n三分之四侧面"
	panel.parameter_form.outputs_edit.text_changed.emit()
	check(panel.apply_fields(), "corrected output specifications become applicable")
	panel.connect_nodes(upstream, 1, downstream, 0)
	check(panel.edges.size() == 1 and panel.edges[0].get("output") == "image_set", "ordered collection has a distinct graph port")
	panel.connect_nodes(upstream, 1, mesh, 0)
	check(panel.edges.size() == 1 and panel.status.text.contains("只能连接到图生图"), "collection cannot silently become a single Mesh input")
	panel.connect_nodes(upstream, 0, mesh, 0)
	check(panel.edges.size() == 2 and panel.edges[1].get("output") == "result", "primary image remains available to Mesh")
	panel.path_edit.text = state_path.path_join("multi-image.json")
	panel.save_graph()
	var saved = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	var saved_node = find_node(saved, downstream)
	check(saved_node.source_paths == ["", ""] and saved_node.source_snapshots.size() == 2 and saved_node.image_context_snapshots.size() == 1, "save embeds all ordered source and reference snapshots")
	check(saved_node.source_snapshots[0].content_sha256 == FileAccess.get_sha256(front) and saved_node.source_snapshots[1].content_sha256 == FileAccess.get_sha256(side) and saved_node.image_context_snapshots[0].content_sha256 == FileAccess.get_sha256(reference), "snapshot identities match original bytes in the chosen order")
	var original = saved.duplicate(true)
	var corrupt = original.duplicate(true)
	find_node(corrupt, downstream).source_paths = [front, 2]
	reject_model(corrupt, "non-string paths cannot enter the graph")
	corrupt = original.duplicate(true)
	find_node(corrupt, downstream).source_paths = [front]
	reject_model(corrupt, "path and snapshot count mismatch is rejected")
	corrupt = original.duplicate(true)
	find_node(corrupt, downstream).source_snapshots[1].content_sha256 = "0".repeat(64)
	reject_model(corrupt, "tampered snapshot bytes are rejected before model execution")
	corrupt = original.duplicate(true)
	corrupt.edges[0].to = mesh
	reject_model(corrupt, "saved collection-to-Mesh edge is rejected")
	write_model(original)
	panel.open_graph()
	panel.select_node(downstream)
	data = node(downstream)
	check(panel.selected_id == downstream and data.source_paths == ["", ""] and data.source_snapshots.size() == 2 and data.image_context_snapshots.size() == 1, "reopen restores ordered snapshots without source files or new generation")
	check(data.parameters.output_labels == ["正面", "三分之四侧面"] and panel.parameter_form.outputs_edit.text == "正面\n三分之四侧面", "reopen restores named independent outputs")
	check(panel.edges == original.edges and panel.run_id.is_empty() and panel.preview_token.is_empty(), "reopen preserves valid ports but clears old execution authority")
	# Preview fixtures only test Godot's member selector. Host membership, publication
	# and restore are exercised by the Python Executor integration test.
	panel.run_id = "preview-fixture"
	panel.load_preview({"type":"image", "path":front, "token":"first-token", "artifact":{"id":"first", "revision":"1".repeat(64)}, "images":[
		{"type":"image", "path":front, "label":"正面", "token":"first-token", "artifact":{"id":"first", "revision":"1".repeat(64)}},
		{"type":"image", "path":side, "label":"三分之四侧面", "token":"second-token", "artifact":{"id":"second", "revision":"2".repeat(64)}}
	]}, downstream, "preview-fixture")
	check(panel.current_images.size() == 2 and panel.result_choice.item_count == 2 and panel.result_choice.is_visible_in_tree(), "two independent images have individual preview choices")
	panel.show_result(1)
	check(panel.preview_artifact.id == "second" and panel.preview_token == "second-token" and panel.texture.texture != null, "selecting the second member updates bytes, identity and confirmation token")
	panel.show_native_section("other")
	check(not panel.result_choice.is_visible_in_tree(), "image member selector stays on the generation page")
	panel.show_native_section("mesh")
	check(panel.result_choice.is_visible_in_tree() and panel.result_choice.selected == 1, "returning to generation preserves the selected member")
	await finish()

func finish():
	var report = OS.get_environment("AINATIVE_MULTI_IMAGE_REPORT")
	if not report.is_empty():
		var file = FileAccess.open(report, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify({"ok":failures == 0, "checks":checks, "failures":failures, "scope":"Godot workflow controls and immutable snapshots; no model inference"}, "  "))
			file.close()
	print("AINATIVE_MULTI_IMAGE failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
