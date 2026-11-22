extends SceneTree
# Real local Executor node run in the native workbench; synthetic GLB only.
var panel
var failures = 0
var checks: Array = []
var state_path = ""

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func settle():
	for i in 5: await process_frame

func idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (panel.creating or panel.auto_step or not panel.jobs.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(not panel.creating and not panel.auto_step and panel.jobs.is_empty(), "garment node local execution completes")

func garment_key(id: String) -> String:
	for key in panel.artifact_nodes:
		var record: Dictionary = panel.artifact_nodes[key]
		if record.get("artifact_role", "") == "garment" and str(record.entry.get("provenance", {}).get("garment_id", "")) == id:
			return str(key)
	return ""

func connected(from_id: String, to_id: String) -> bool:
	for edge in panel.graph.get_connection_list():
		if str(edge.from_node) == from_id and str(edge.to_node) == to_id: return true
	return false

func run():
	root.size = Vector2i(1700, 1000)
	var source = OS.get_environment("AINATIVE_GARMENT_NODE_SOURCE")
	var items_path = OS.get_environment("AINATIVE_GARMENT_NODE_ITEMS")
	if source.is_empty() or items_path.is_empty():
		check(false, "synthetic source and reviewed component fixture are supplied")
		await finish()
		return
	var items = JSON.parse_string(FileAccess.get_file_as_string(items_path))
	state_path = OS.get_environment("AINATIVE_GARMENT_NODE_STATE")
	if state_path.is_empty(): state_path = ProjectSettings.globalize_path("user://garment-node-" + str(Time.get_ticks_usec()))
	state_path = state_path.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	var source_sha = FileAccess.get_sha256(source)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.set_meta("ainative_tools_dir", ProjectSettings.globalize_path("res://../../tools/ainative"))
	panel.state_dir = state_path
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.db = state_path.path_join("jobs.sqlite")
	var split = {"id":"split", "type":"garment_split", "version":"1", "provider":"garment-split", "source":source, "image_context":"", "text":"", "parameters":{"items":items}, "x":40.0, "y":60.0}
	var consumer = {"id":"consumer", "type":"copy", "version":"1", "provider":"local-copy", "source":"", "image_context":"", "text":"", "parameters":{"delay":0.0,"fail":false}, "x":700.0, "y":60.0}
	panel.nodes = [split, consumer]
	panel.edges = []
	panel.rebuild()
	panel.select_node("split")
	check(panel.node_label("garment_split") == "衣服拆分" and panel._generator_provider("garment_split") == "garment-split", "creation menu exposes the local garment split node")
	check(panel.input_kind(split) == panel.PORT_MESH and panel.output_kind(split) == panel.PORT_MESH, "node declares Mesh input and Mesh collection output")
	check(panel.parameter_form.garment_items_edit.visible and not panel.parameter_form.prompt_edit.visible and not panel.node_model_edit.visible, "structured editor shows garment items without prompt or remote model")
	check(not panel.context_row.visible and str(panel.source_picker.filters).contains("*.glb"), "garment node accepts one static GLB and no image context")
	check(panel.apply_fields() and not split.parameters.has("prompt"), "applying garment items adds no generation prompt")
	check(panel.node_run_blocker("split").is_empty() and panel._service_blocker("garment_split").is_empty(), "local node needs neither generation service nor prompt")
	panel.run_node_preview("split")
	await idle()
	await settle()
	if panel.failure_dialog.visible:
		print(panel.failure_text.text)
	var entry: Dictionary = panel._latest_mesh_entry("split")
	check(not entry.is_empty() and entry.get("iterations", []).size() == items.size(), "real run stores collection preview and one entry per garment")
	check(panel.artifact_nodes.values().filter(func(record): return record.get("artifact_role", "") == "garment").size() == items.size(), "real run creates one dynamic node per garment")
	var cape_key = garment_key("cape")
	var armor_key = garment_key("armor")
	check(not cape_key.is_empty() and not armor_key.is_empty(), "cape and armor have independent persistent artifact identities")
	if entry.is_empty() or cape_key.is_empty() or armor_key.is_empty():
		print(panel.status.text)
		await finish()
		return
	var cape_card = panel.graph.get_node(NodePath(str(panel.artifact_nodes[cape_key].id)))
	check(cape_card.title.contains("披风") and not cape_card.title.contains("第 1 轮"), "garment card uses semantic name rather than generation round")
	check(cape_card.get_node("ArtifactMeshPreview").mesh_count > 0, "garment card renders actual extracted GLB")
	panel.edges = [{"from":"split","to":"consumer","input":"source","output":"result"}]
	panel.rebuild()
	await settle()
	var armor_id = str(panel.artifact_nodes[armor_key].id)
	check(connected("split", "consumer") and not connected(armor_id, "consumer"), "ordinary downstream edge uses the collection rather than the last garment")
	panel.edges = []
	panel._save_mesh_artifact(cape_key)
	check(panel.save_picker.current_file.begins_with("garment-cape-"), "save action names the selected garment and revision")
	panel.save_picker.hide()
	var saved_path = state_path.path_join("saved-cape.glb")
	panel.save_preview_to(saved_path)
	var cape_entry: Dictionary = panel.artifact_nodes[cape_key].entry
	check(FileAccess.get_sha256(saved_path) == FileAccess.get_sha256(cape_entry.path), "saved garment preserves exact selected GLB bytes")
	panel.connect_nodes(str(panel.artifact_nodes[cape_key].id), 0, "consumer", 0)
	await settle()
	check(panel.edges.size() == 1 and panel.edges[0].get("artifact", {}) == cape_entry.artifact, "dragging a garment fixes that artifact as downstream input")
	var executable = panel.execution_model()
	check(not executable.is_empty() and executable.edges[0].get("artifact_snapshot", {}).get("content_sha256", "") == cape_entry.artifact.revision, "fixed garment connection carries immutable bytes into Executor")
	panel.path_edit.text = state_path.path_join("workflow.json")
	panel.save_graph()
	panel.open_graph()
	await settle()
	check(not garment_key("cape").is_empty() and not garment_key("armor").is_empty(), "workflow reopen restores every garment without rerunning")
	check(panel.edges.size() == 1 and panel.edges[0].get("artifact", {}).get("revision", "") == cape_entry.artifact.revision, "workflow reopen preserves selected garment connection")
	check(panel.nodes.filter(func(node): return node.id == "split")[0].parameters.items == items, "workflow reopen preserves garment item JSON")
	check(FileAccess.get_sha256(source) == source_sha, "source GLB remains byte-identical after run, save and reopen")
	var screenshot = OS.get_environment("AINATIVE_GARMENT_NODE_SCREENSHOT")
	if not screenshot.is_empty() and DisplayServer.get_name() != "headless":
		panel.show_native_section("mesh")
		panel.select_node("split")
		await settle()
		await create_timer(0.2).timeout
		check(root.get_texture().get_image().save_png(screenshot) == OK, "save actual garment node workbench evidence")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_GARMENT_NODE_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed":failures == 0,"failures":failures,"checks":checks,"scope":"real local Executor and native workbench with synthetic GLB; no AI, visual or cloth acceptance"}, "  "))
			report.close()
	print("AINATIVE_GARMENT_NODE failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
