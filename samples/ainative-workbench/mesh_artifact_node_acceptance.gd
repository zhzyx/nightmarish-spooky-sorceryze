extends SceneTree
# Dynamic per-round Mesh artifacts, fixed-iteration inputs and durable GLB saves.
var panel
var failures = 0
var checks: Array = []
var state_path = ""
var round_paths: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func settle():
	for i in 6: await process_frame

func double_click(control: Control):
	var event = InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = true
	control.gui_input.emit(event)

func formal_node(id: String, kind: String) -> Dictionary:
	return {"id": id, "type": kind, "version": panel._new_node_version(kind), "provider": "local-copy" if kind == "copy" else "kimi_native", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "three round fixture", "seed": 1}, "x": 0.0, "y": 0.0}

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

func mesh_entry(path: String, attempt: int) -> Dictionary:
	var revision = FileAccess.get_sha256(path)
	return {"type": "mesh", "path": path, "label": "第 %d 轮" % attempt, "token": "round-token-%d" % attempt, "run": "mesh-artifact-fixture", "node": "generate", "description": "", "attempt": attempt, "review_passed": attempt == 3, "artifact": {"id": "mesh-iteration-%03d" % attempt, "revision": revision}, "provenance": {"task_id": "synthetic-round-%d" % attempt, "visual_review_passed": attempt == 3}}

func connected(from_id: String, to_id: String) -> bool:
	for edge in panel.graph.get_connection_list():
		if str(edge.from_node) == from_id and str(edge.to_node) == to_id: return true
	return false

func artifact_key(attempt: int) -> String:
	for key in panel.artifact_nodes:
		var record: Dictionary = panel.artifact_nodes[key]
		if record.get("kind", "") == "mesh" and int(record.get("attempt", 0)) == attempt: return str(key)
	return ""

func run():
	root.size = Vector2i(1800, 1000)
	state_path = OS.get_environment("AINATIVE_MESH_ARTIFACT_STATE")
	if state_path.is_empty(): state_path = ProjectSettings.globalize_path("user://mesh-artifact-node-test")
	state_path = state_path.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	for attempt in range(1, 4):
		var path = state_path.path_join("round-%d.glb" % attempt)
		make_mesh(path, attempt)
		round_paths.append(path)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = state_path
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.nodes = [formal_node("generate", "text_to_mesh"), formal_node("adjust", "model_adjust"), formal_node("consumer", "copy")]
	panel.edges = []
	panel.selected_id = ""
	var iterations: Array = []
	for attempt in range(1, 4): iterations.append(mesh_entry(round_paths[attempt - 1], attempt))
	var primary: Dictionary = iterations[2].duplicate(true)
	primary.erase("label")
	primary.erase("attempt")
	primary.erase("review_passed")
	primary["token"] = "final-token"
	primary["artifact"] = {"id": "mesh-final", "revision": FileAccess.get_sha256(round_paths[2])}
	primary["iterations"] = iterations
	panel.preview_history["generate"] = [primary]
	panel.rebuild()
	await settle()
	check(panel.artifact_nodes.size() == 3, "one Mesh run creates one dynamic output node per generation round")
	var first_key = artifact_key(1)
	var second_key = artifact_key(2)
	var third_key = artifact_key(3)
	check(not first_key.is_empty() and not second_key.is_empty() and not third_key.is_empty(), "all three round identities are available")
	if first_key.is_empty() or second_key.is_empty() or third_key.is_empty():
		await finish()
		return
	var first_id = str(panel.artifact_nodes[first_key].id)
	var second_id = str(panel.artifact_nodes[second_key].id)
	var third_id = str(panel.artifact_nodes[third_key].id)
	check(connected("generate", first_id) and connected(first_id, second_id) and connected(second_id, third_id), "round nodes are chained in generation order")
	check(panel.graph.get_node(NodePath(second_id)).title.contains("第 2 轮"), "each dynamic node displays its generation round")
	var actual_thumbnails = true
	for id in [first_id, second_id, third_id]:
		var thumbnail = panel.graph.get_node(NodePath(id)).get_node("ArtifactMeshPreview")
		if thumbnail.mesh_count < 1 or thumbnail.rendering.get_texture() == null: actual_thumbnails = false
	check(actual_thumbnails, "every round node embeds an actual rendered GLB thumbnail")
	panel.graph.get_node(NodePath(first_id)).get_node("PreviewMeshArtifact").pressed.emit()
	await settle()
	check(panel.preview_source_path == round_paths[0] and panel.preview_artifact == iterations[0].artifact, "round preview opens that exact GLB and artifact identity")
	check(panel.mesh_container.is_visible_in_tree() and panel.mesh_container.get_global_rect().intersects(panel.native_scroll.get_global_rect()), "interactive Mesh preview is scrolled into the visible workbench area")
	double_click(panel.graph.get_node(NodePath(first_id)).get_node("ArtifactMeshPreview"))
	check(panel.preview_maximized and panel.preview_window.visible and panel.mesh_container.get_parent() == panel.preview_window_host and panel.preview_source_path == round_paths[0], "double-clicking a Mesh thumbnail maximizes that exact round")
	var maximized_screenshot = OS.get_environment("AINATIVE_MESH_MAXIMIZED_SCREENSHOT")
	if not maximized_screenshot.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(panel.preview_window.get_texture().get_image().save_png(maximized_screenshot) == OK, "save actual double-click maximized Mesh evidence")
	panel.restore_preview()
	check(not panel.preview_maximized and panel.mesh_container.get_parent() == panel.inspector_fields, "Mesh artifact preview restores with the shared inline preview logic")
	double_click(panel.graph.get_node(NodePath(second_id)))
	check(panel.preview_maximized and panel.preview_source_path == round_paths[1], "double-clicking a different round node switches the maximized result to that round")
	panel.restore_preview()
	panel.save_picker.use_native_dialog = false
	panel.graph.get_node(NodePath(first_id)).get_node("SaveMeshArtifact").pressed.emit()
	var expected_name = "mesh-round-001-%s.glb" % str(iterations[0].artifact.revision).left(12)
	check(panel.save_picker.current_file == expected_name, "round save suggests the selected revision filename")
	check(DirAccess.open("res://").is_equivalent(panel.save_picker.current_dir, ProjectSettings.globalize_path("res://")), "round save opens in the current project")
	panel.save_picker.hide()
	var original_hash = FileAccess.get_sha256(round_paths[0])
	panel.save_preview_to(round_paths[0])
	check(panel.status.text == "所选位置是生成物源文件，请选择其他文件名或目录" and FileAccess.get_sha256(round_paths[0]) == original_hash, "selecting the source keeps the original and asks for a different destination")
	var saved_path = state_path.path_join("saved-round-1.glb")
	panel.save_preview_to(saved_path)
	check(FileAccess.get_sha256(saved_path) == FileAccess.get_sha256(round_paths[0]) and FileAccess.get_sha256(round_paths[1]) != FileAccess.get_sha256(saved_path), "saving round one preserves only round one bytes")
	panel.edges = [{"from": "generate", "to": "adjust", "input": "source", "output": "result"}]
	panel.rebuild()
	await settle()
	check(connected(third_id, "adjust"), "an ordinary downstream edge defaults to the final generation round")
	panel.edges = []
	panel.rebuild()
	await settle()
	panel.connect_nodes(first_id, 0, "adjust", 0)
	await settle()
	check(panel.edges.size() == 1 and panel.edges[0].get("artifact", {}) == iterations[0].artifact and int(panel.edges[0].get("iteration", 0)) == 1, "dragging from round one records an explicit fixed-iteration edge")
	check(connected(first_id, "adjust") and not connected(third_id, "adjust"), "the selected round not the final round feeds the downstream node")
	var executable = panel.execution_model()
	check(not executable.is_empty() and executable.edges[0].has("artifact_snapshot"), "execution model is available for the selected round")
	if not executable.is_empty():
		var snapshot: Dictionary = executable.edges[0].get("artifact_snapshot", {})
		check(snapshot.get("content_sha256", "") == FileAccess.get_sha256(round_paths[0]) and snapshot.get("provenance", {}).get("task_id", "") == "synthetic-round-1", "execution snapshot carries round one bytes and generation provenance")
	check(not panel.model().edges[0].has("artifact_snapshot"), "workflow serialization keeps runtime-only snapshot payloads out of formal edges")
	panel.path_edit.text = state_path.path_join("mesh-artifact-workflow.json")
	panel.save_graph()
	var saved = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	check(saved.nodes.size() == 3 and saved.output_history.generate[0].iterations.size() == 3, "workflow save embeds every round while excluding dynamic nodes")
	panel.open_graph()
	await settle()
	first_key = artifact_key(1)
	check(panel.artifact_nodes.size() == 3 and not first_key.is_empty(), "reopening restores every round without rerunning generation")
	check(connected(str(panel.artifact_nodes[first_key].id), "adjust"), "reopening restores the selected round connection")
	var restored_executable = panel.execution_model()
	check(not restored_executable.is_empty() and restored_executable.edges[0].artifact_snapshot.content_sha256 == FileAccess.get_sha256(round_paths[0]), "restored downstream input still uses the original selected round")
	panel._keyboard_delete([str(panel.artifact_nodes[artifact_key(2)].id)])
	await settle()
	check(artifact_key(2).is_empty() and panel.artifact_nodes.size() == 2 and FileAccess.file_exists(round_paths[1]), "deleting one round node preserves its GLB and generation history")
	panel.rebuild()
	check(artifact_key(2).is_empty(), "ordinary layout does not resurrect a dismissed round node")
	panel.remember_preview(primary, "generate", "new-fixture-run")
	await settle()
	check(not artifact_key(2).is_empty() and panel.artifact_nodes.size() == 3, "an explicit new result restores dismissed round nodes")
	var screenshot = OS.get_environment("AINATIVE_MESH_ARTIFACT_SCREENSHOT")
	if not screenshot.is_empty() and DisplayServer.get_name() != "headless":
		await create_timer(0.2).timeout
		check(root.get_texture().get_image().save_png(screenshot) == OK, "save actual per-round Mesh workbench visual evidence")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_MESH_ARTIFACT_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Godot dynamic per-round Mesh controls, fixed inputs and persistence; no model inference"}, "  "))
			report.close()
	print("AINATIVE_MESH_ARTIFACT failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
