extends SceneTree
# Dynamic image artifacts, project downloads and layout; no model inference.
var panel
var failures = 0
var checks: Array = []
var state_path = ""
var image_paths: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func settle():
	for i in 6: await process_frame
	var deadline = Time.get_ticks_msec() + 10000
	while panel.is_preview_loading() and Time.get_ticks_msec() < deadline: await process_frame
	check(not panel.is_preview_loading(), "asynchronous artifact preview completes")

func double_click(control: Control):
	var event = InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = true
	control.gui_input.emit(event)

func make_image(path: String, color: Color):
	var image = Image.create_empty(160, 100, false, Image.FORMAT_RGBA8)
	image.fill(color)
	check(image.save_png(path) == OK, "create image fixture: " + path.get_file())

func formal_node(id: String, kind: String) -> Dictionary:
	return {"id": id, "type": kind, "version": panel._new_node_version(kind), "provider": "comfy", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "", "seed": 1}, "x": 0.0, "y": 0.0}

func image_entry(path: String, label: String, id: String, token: String) -> Dictionary:
	return {"type": "image", "path": path, "label": label, "token": token, "run": "artifact-fixture", "node": "image", "description": "", "artifact": {"id": id, "revision": token.sha256_text()}}

func connected(from_id: String, to_id: String) -> bool:
	for edge in panel.graph.get_connection_list():
		if str(edge.from_node) == from_id and str(edge.to_node) == to_id: return true
	return false

func check_no_overlap() -> bool:
	var placed: Array = []
	for node in panel.graph.get_children():
		if not node is GraphNode: continue
		var rect = Rect2(node.position_offset, node.size)
		for other in placed:
			if rect.intersects(other): return false
		placed.append(rect)
	return true

func run():
	root.size = Vector2i(1600, 1000)
	state_path = OS.get_environment("AINATIVE_ARTIFACT_STATE")
	if state_path.is_empty(): state_path = ProjectSettings.globalize_path("user://artifact-node-test")
	state_path = state_path.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	for index in 3:
		var path = state_path.path_join("image-%d.png" % index)
		make_image(path, [Color("b84732"), Color("3264b8"), Color("4b9b66")][index])
		image_paths.append(path)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = state_path
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.nodes = [formal_node("image", "generate_image"), formal_node("mesh", "image_to_mesh"), formal_node("unrelated", "text_to_mesh")]
	panel.edges = [{"from": "image", "to": "mesh", "input": "source", "output": "image_set"}]
	panel.selected_id = ""
	var members: Array = []
	for index in 3:
		members.append(image_entry(image_paths[index], ["正面", "侧面", "背面"][index], "artifact-%d" % index, "token-%d" % index))
	var result = image_entry(image_paths[0], "", "artifact-0", "token-0")
	result["images"] = members
	panel.preview_history["image"] = [result]
	panel.rebuild()
	await settle()
	check(panel.artifact_nodes.has("image"), "successful image history creates a dynamic artifact node")
	var artifact_id = str(panel.artifact_nodes["image"].id)
	var artifact = panel.graph.get_node(NodePath(artifact_id)) as GraphNode
	check(panel.model().nodes.size() == 3 and panel.model().edges.size() == 1, "artifact presentation does not alter the executable DAG")
	check(artifact.get_meta("maliang_artifact", false) and artifact.get_node("ArtifactGallery").get_child_count() == 3, "one dynamic node displays every generated image thumbnail")
	var style = artifact.get_theme_stylebox("panel") as StyleBoxFlat
	check(style != null and style.corner_radius_top_left >= 12 and style.border_width_top >= 2, "rounded bordered artifact shape differs from formal process nodes")
	check(connected("image", artifact_id) and connected(artifact_id, "mesh") and not connected("image", "mesh"), "referenced artifact is inserted between image generation and Mesh")
	artifact.get_node("ArtifactGallery").get_child(2).get_node("ArtifactImage2").pressed.emit()
	await settle()
	check(panel.current_images.size() == 3 and panel.preview_artifact.get("id") == "artifact-2" and panel.preview_token == "token-2", "gallery selection previews the chosen image and artifact identity")
	double_click(artifact.get_node("ArtifactGallery").get_child(2).get_node("ArtifactThumbnail2"))
	check(panel.preview_maximized and panel.preview_window.visible and panel.texture.get_parent() == panel.preview_window_host and panel.preview_artifact.get("id") == "artifact-2", "double-clicking an image thumbnail maximizes that exact image")
	panel.restore_preview()
	check(not panel.preview_maximized and panel.texture.get_parent() == panel.inspector_fields, "image artifact preview restores with the shared inline preview logic")
	double_click(artifact)
	check(panel.preview_maximized and panel.preview_artifact.get("id") == "artifact-0", "double-clicking the image artifact node maximizes its primary result")
	panel.restore_preview()
	var download_dir = state_path.path_join("project/generated")
	panel._download_artifact_images(download_dir, "image")
	var downloaded = DirAccess.get_files_at(download_dir)
	check(downloaded.size() == 3 and panel.status.text.contains("已下载 3 张图片"), "download action writes all images into the selected project directory")
	var hashes_match = true
	for index in 3:
		var target = download_dir.path_join("%02d-artifact-%d.png" % [index + 1, index])
		if not FileAccess.file_exists(target) or FileAccess.get_sha256(target) != FileAccess.get_sha256(image_paths[index]): hashes_match = false
	check(hashes_match, "downloaded files preserve every original image byte")
	check(check_no_overlap(), "automatic layout leaves no overlapping formal or dynamic nodes")
	check(panel.graph.get_node("image").position_offset.x < artifact.position_offset.x and artifact.position_offset.x < panel.graph.get_node("mesh").position_offset.x, "layout follows image, artifact, Mesh dependency order")
	var screenshot = OS.get_environment("AINATIVE_ARTIFACT_SCREENSHOT")
	if not screenshot.is_empty() and DisplayServer.get_name() != "headless":
		await create_timer(0.2).timeout
		check(root.get_texture().get_image().save_png(screenshot) == OK, "save actual workbench visual evidence")
	panel.path_edit.text = state_path.path_join("artifact-workflow.json")
	panel.save_graph()
	var saved = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	check(saved.nodes.size() == 3 and saved.edges.size() == 1 and saved.nodes.all(func(node): return not str(node.id).begins_with("artifact_")), "workflow serialization excludes dynamic presentation nodes")
	panel.open_graph()
	await settle()
	check(panel.artifact_nodes.has("image") and panel._artifact_images(panel._latest_image_entry("image")).size() == 3, "reopening restores the artifact gallery without rerunning generation")
	artifact_id = str(panel.artifact_nodes["image"].id)
	check(connected(artifact_id, "mesh"), "reopening restores the automatic downstream reference")
	panel.disconnect_nodes(artifact_id, 0, "mesh", 0)
	await settle()
	check(panel.edges.is_empty() and connected("image", str(panel.artifact_nodes["image"].id)), "disconnecting the dynamic consumer removes only the formal downstream edge")
	check(check_no_overlap(), "layout remains non-overlapping after removing a reference")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_ARTIFACT_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Godot dynamic artifact controls and layout; no model inference"}, "  "))
			report.close()
	print("AINATIVE_ARTIFACT failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
