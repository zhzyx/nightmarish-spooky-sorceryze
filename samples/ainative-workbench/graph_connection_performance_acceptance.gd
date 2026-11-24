extends SceneTree
# Connecting and disconnecting must not reconstruct existing nodes or decode Mesh previews again.
var panel
var failures = 0
var checks: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func settle():
	for index in 6: await process_frame

func formal_node(id: String, kind: String) -> Dictionary:
	var parameters = {"delay": 0, "fail": false} if kind == "copy" else {"items": []} if kind == panel.GARMENT_SPLIT else {"prompt": "connection fixture", "seed": 1}
	var provider = "local-copy" if kind == "copy" else "garment-split" if kind == panel.GARMENT_SPLIT else "kimi_native"
	return {"id": id, "type": kind, "version": panel._new_node_version(kind), "provider": provider, "source": "", "image_context": "", "text": "", "parameters": parameters, "x": 40.0, "y": 60.0}

func snapshot_graph() -> Dictionary:
	var instances: Dictionary = {}
	var decode_counts: Dictionary = {}
	for child in panel.graph.get_children():
		if not child is GraphNode: continue
		instances[str(child.name)] = child.get_instance_id()
		var thumbnail = child.get_node_or_null("ArtifactMeshPreview")
		if thumbnail != null: decode_counts[str(child.name)] = thumbnail.decode_count
	return {"instances": instances, "decode_counts": decode_counts}

func check_preserved(before: Dictionary, label: String):
	var preserved = true
	var decode_preserved = true
	for id in before.instances:
		var current = panel.graph.get_node_or_null(NodePath(id))
		if current == null or current.get_instance_id() != before.instances[id]:
			preserved = false
			if before.decode_counts.has(id): decode_preserved = false
		if before.decode_counts.has(id) and current != null:
			var thumbnail = current.get_node_or_null("ArtifactMeshPreview")
			if thumbnail == null or thumbnail.decode_count != before.decode_counts[id]: decode_preserved = false
	check(preserved, label + " preserves every existing node and artifact instance")
	check(decode_preserved, label + " does not decode existing Mesh previews again")

func connected(from_id: String, to_id: String) -> bool:
	return panel.graph.get_connection_list().any(func(edge): return str(edge.from_node) == from_id and str(edge.to_node) == to_id)

func wait_for_previews():
	var deadline = Time.get_ticks_msec() + 10000
	var loading = true
	while loading and Time.get_ticks_msec() < deadline:
		loading = false
		for thumbnail in panel.graph.find_children("*", "SubViewportContainer", true, false):
			if thumbnail.has_method("is_loading") and thumbnail.is_loading(): loading = true
		if loading: await process_frame
	check(not loading, "Mesh preview fixture finishes its initial decode")

func run():
	root.size = Vector2i(1440, 1000)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = ProjectSettings.globalize_path("user://graph-connection-performance-" + str(Time.get_ticks_usec()))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.nodes = [formal_node("mesh", "text_to_mesh"), formal_node("split", panel.GARMENT_SPLIT), formal_node("consumer", "copy"), formal_node("sink", "copy")]
	panel.edges = []
	var mesh_path = ProjectSettings.globalize_path("res://fixtures/sample.glb")
	var iteration = {"type": "mesh", "path": mesh_path, "label": "第 1 轮", "token": "connection-round-1", "run": "connection-test", "node": "mesh", "description": "", "attempt": 1, "artifact": {"id": "connection-round", "revision": FileAccess.get_sha256(mesh_path)}}
	var result = iteration.duplicate(true)
	result["iterations"] = [iteration]
	panel.preview_history["mesh"] = [result]
	panel.selected_id = ""
	panel.rebuild(false)
	await wait_for_previews()
	await settle()
	check(panel.artifact_nodes.size() == 1, "Mesh artifact fixture is available")
	var artifact_id = str(panel.artifact_nodes.values()[0].id)

	var before = snapshot_graph()
	panel.connect_nodes(artifact_id, 0, "split", 0)
	await settle()
	check(panel.edges.size() == 1 and panel.edges[0].get("artifact", {}) == iteration.artifact, "artifact connection records the selected immutable Mesh")
	check(connected(artifact_id, "split"), "artifact connection adds only the artifact-to-garment wire")
	check_preserved(before, "artifact connection")

	before = snapshot_graph()
	panel.connect_nodes("split", 0, "sink", 0)
	await settle()
	check(connected("split", "sink"), "garment collection connection uses the formal output")
	check_preserved(before, "garment collection connection")

	before = snapshot_graph()
	panel.connect_nodes("mesh", 0, "consumer", 0)
	await settle()
	check(connected(artifact_id, "consumer") and not connected("mesh", "consumer"), "ordinary Mesh connection retains latest-artifact routing")
	check_preserved(before, "ordinary Mesh connection")

	before = snapshot_graph()
	panel.disconnect_nodes("split", 0, "sink", 0)
	await settle()
	check(not connected("split", "sink") and not panel.edges.any(func(edge): return edge.from == "split" and edge.to == "sink"), "disconnect removes only the requested logical and visual wire")
	check_preserved(before, "disconnect")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_GRAPH_CONNECTION_PERFORMANCE_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Incremental graph connections preserve existing nodes, artifact previews and Mesh decode counts; no model inference"}, "  "))
			report.close()
	print("AINATIVE_GRAPH_CONNECTION_PERFORMANCE failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
