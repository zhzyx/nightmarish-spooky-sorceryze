extends SceneTree
# Selection responsiveness, asynchronous preview ownership and static redraw contracts.
var panel
var failures = 0
var checks: Array = []
var state_path = ""
var round_paths: Array = []
var image_paths: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func settle():
	for index in 6: await process_frame

func wait_preview(label: String = "asynchronous preview completes"):
	var deadline = Time.get_ticks_msec() + 10000
	while panel.is_preview_loading() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(not panel.is_preview_loading(), label)

func formal_node(id: String, kind: String) -> Dictionary:
	return {"id": id, "type": kind, "version": panel._new_node_version(kind), "provider": "local-copy" if kind == "copy" else "kimi_native", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "preview interaction fixture", "seed": 1}, "x": 0.0, "y": 0.0}

func make_mesh(path: String, round_number: int):
	var source = FileAccess.get_file_as_bytes(ProjectSettings.globalize_path("res://fixtures/sample.glb"))
	var json_length = source.decode_u32(12)
	var document = JSON.parse_string(source.slice(20, 20 + json_length).get_string_from_utf8())
	document.asset["extras"] = {"fixture_round": round_number}
	var chunk = JSON.stringify(document).to_utf8_buffer()
	while chunk.size() % 4 != 0: chunk.append(32)
	var remainder = source.slice(20 + json_length)
	var output = PackedByteArray()
	output.resize(20)
	output.encode_u32(0, 0x46546C67)
	output.encode_u32(4, 2)
	output.encode_u32(8, 20 + chunk.size() + remainder.size())
	output.encode_u32(12, chunk.size())
	output.encode_u32(16, 0x4E4F534A)
	output.append_array(chunk)
	output.append_array(remainder)
	var file = FileAccess.open(path, FileAccess.WRITE)
	check(file != null, "create Mesh fixture: " + path.get_file())
	if file != null:
		file.store_buffer(output)
		file.close()

func make_image(path: String, color: Color):
	var image = Image.create_empty(96, 64, false, Image.FORMAT_RGBA8)
	image.fill(color)
	check(image.save_png(path) == OK, "create image fixture: " + path.get_file())

func mesh_entry(path: String, attempt: int) -> Dictionary:
	return {"type": "mesh", "path": path, "label": "第 %d 轮" % attempt, "token": "round-token-%d" % attempt, "run": "preview-interaction", "node": "generate", "description": "", "attempt": attempt, "artifact": {"id": "round-%d" % attempt, "revision": FileAccess.get_sha256(path)}}

func image_entry(path: String, label: String, token: String) -> Dictionary:
	return {"type": "image", "path": path, "label": label, "token": token, "run": "preview-interaction", "node": "image", "description": "", "artifact": {"id": token, "revision": token.sha256_text()}}

func artifact_key(attempt: int) -> String:
	for key in panel.artifact_nodes:
		var record: Dictionary = panel.artifact_nodes[key]
		if record.get("kind", "") == "mesh" and int(record.get("attempt", 0)) == attempt: return str(key)
	return ""

func run():
	root.size = Vector2i(1600, 1000)
	state_path = OS.get_environment("AINATIVE_PREVIEW_INTERACTION_STATE")
	if state_path.is_empty(): state_path = ProjectSettings.globalize_path("user://preview-interaction-test")
	state_path = state_path.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	for attempt in range(1, 4):
		var path = state_path.path_join("round-%d.glb" % attempt)
		make_mesh(path, attempt)
		round_paths.append(path)
	for index in 2:
		var path = state_path.path_join("image-%d.png" % index)
		make_image(path, [Color("b84732"), Color("3264b8")][index])
		image_paths.append(path)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = state_path
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.nodes = [formal_node("generate", "text_to_mesh"), formal_node("image", "generate_image"), formal_node("other", "copy")]
	panel.edges = []
	var iterations: Array = []
	for attempt in range(1, 4): iterations.append(mesh_entry(round_paths[attempt - 1], attempt))
	var primary: Dictionary = iterations[2].duplicate(true)
	primary["token"] = "final-token"
	primary["artifact"] = {"id": "mesh-final", "revision": FileAccess.get_sha256(round_paths[2])}
	primary["iterations"] = iterations
	panel.preview_history["generate"] = [primary]
	var first_image = image_entry(image_paths[0], "正面", "image-token-0")
	var second_image = image_entry(image_paths[1], "侧面", "image-token-1")
	var image_set = first_image.duplicate(true)
	image_set["images"] = [first_image, second_image]
	panel.preview_history["image"] = [image_set]
	panel.selected_id = ""
	panel.rebuild(false)
	await settle()
	panel.select_node("other")
	var first_key = artifact_key(1)
	var second_key = artifact_key(2)
	check(not first_key.is_empty() and not second_key.is_empty(), "Mesh artifact fixtures are available")
	var decodes = panel.preview_decode_count
	panel._show_artifact_result(first_key)
	check(panel.selected_id == "generate" and panel.is_preview_loading() and panel.preview_source_path != round_paths[2], "artifact selection updates the inspector without synchronously restoring the latest Mesh")
	await wait_preview("selected artifact finishes one background decode")
	check(panel.preview_source_path == round_paths[0] and panel.preview_decode_count == decodes + 1, "artifact selection decodes only the requested result once")
	decodes = panel.preview_decode_count
	panel._show_artifact_result(first_key)
	check(not panel.is_preview_loading(), "reselecting the displayed artifact reuses it without a worker")
	await settle()
	check(panel.preview_decode_count == decodes, "reselecting the displayed artifact performs no decode")
	decodes = panel.preview_decode_count
	var formal = panel.graph.get_node("generate") as GraphNode
	formal.position_offset += Vector2(120, 80)
	check(panel.nodes[0].x == formal.position_offset.x and panel.nodes[0].y == formal.position_offset.y and panel.preview_decode_count == decodes and not panel.is_preview_loading(), "drag position updates only persist coordinates and never decode previews")
	panel.select_node("other")
	decodes = panel.preview_decode_count
	panel._show_artifact_result(first_key)
	panel._show_artifact_result(second_key)
	await wait_preview("latest rapid selection completes")
	check(panel.preview_source_path == round_paths[1] and panel.preview_decode_count == decodes + 1, "rapid artifact selections coalesce to one decode and present only the latest target")
	check(panel.viewport.render_target_update_mode != SubViewport.UPDATE_ALWAYS, "static Mesh preview does not render continuously")
	panel.viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	var motion = InputEventMouseMotion.new()
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	motion.relative = Vector2(12, 4)
	panel.mesh_container.gui_input.emit(motion)
	check(panel.viewport.render_target_update_mode == SubViewport.UPDATE_ONCE, "camera interaction explicitly requests one static redraw")
	panel.select_node("other")
	decodes = panel.preview_decode_count
	panel._show_artifact_result("image", 1)
	await wait_preview("selected image-set member completes")
	check(panel.preview_source_path == image_paths[1] and panel.preview_token == "image-token-1" and panel.current_images.size() == 2 and panel.result_choice.selected == 1 and panel.preview_decode_count == decodes + 1, "image artifact selection decodes only the chosen member once")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_PREVIEW_INTERACTION_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Godot asynchronous selection previews, coalescing, identity reuse and static redraw; no model inference"}, "  "))
			report.close()
	print("AINATIVE_PREVIEW_INTERACTION failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
