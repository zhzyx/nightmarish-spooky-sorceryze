extends SceneTree
# Adding a formal node must preserve existing graph and artifact instances.
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
	return {"id": id, "type": kind, "version": panel._new_node_version(kind), "provider": "local-copy" if kind == "copy" else "kimi_native", "source": "", "image_context": "", "text": "", "parameters": {"delay": 0, "fail": false} if kind == "copy" else {"prompt": "node creation fixture", "seed": 1}, "x": 40.0, "y": 60.0}

func snapshot_graph() -> Dictionary:
	var instances: Dictionary = {}
	for child in panel.graph.get_children():
		if child is GraphNode: instances[str(child.name)] = child
	return {"instances": instances, "connections": panel.graph.get_connection_list()}

func check_preserved(before: Dictionary, label: String):
	var preserved = true
	for id in before.instances:
		var current = panel.graph.get_node_or_null(NodePath(id))
		if current != before.instances[id]: preserved = false
	check(preserved, label + " preserves every existing node and artifact instance")
	check(panel.graph.get_connection_list() == before.connections, label + " preserves all existing graph connections")

func run():
	root.size = Vector2i(1440, 1000)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = ProjectSettings.globalize_path("user://node-creation-performance-" + str(Time.get_ticks_usec()))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.nodes = [formal_node("mesh", "text_to_mesh"), formal_node("sink", "copy")]
	panel.edges = [{"from": "mesh", "to": "sink", "input": "source", "output": "result"}]
	var mesh_path = ProjectSettings.globalize_path("res://fixtures/sample.glb")
	var iteration = {"type": "mesh", "path": mesh_path, "label": "第 1 轮", "token": "creation-round-1", "run": "creation-test", "node": "mesh", "description": "", "attempt": 1, "artifact": {"id": "creation-round", "revision": FileAccess.get_sha256(mesh_path)}}
	var result = iteration.duplicate(true)
	result["iterations"] = [iteration]
	panel.preview_history["mesh"] = [result]
	panel.selected_id = ""
	panel.rebuild(false)
	await settle()
	check(panel.artifact_nodes.size() == 1, "Mesh artifact fixture is available")
	panel.select_node("sink")
	await settle()

	var before = snapshot_graph()
	var artifact_id = str(panel.artifact_nodes.values()[0].id)
	var artifact = panel.graph.get_node(NodePath(artifact_id))
	panel._remember_context()
	panel.create_context_node(panel.GARMENT_SPLIT)
	await settle()
	var created: Dictionary = panel.nodes.back()
	check(created.get("type", "") == panel.GARMENT_SPLIT and panel.selected_id == created.id, "context creation adds and selects the garment split node")
	check(panel.graph.get_node_or_null(NodePath(str(created.id))) is GraphNode, "context creation creates only the new graph node")
	check_preserved(before, "context creation")
	check(panel.graph.get_node(NodePath(artifact_id)) == artifact, "context creation does not decode or reconstruct the Mesh artifact")

	before = snapshot_graph()
	panel.add_node()
	await settle()
	created = panel.nodes.back()
	check(created.get("type", "") == "copy" and panel.selected_id == created.id, "legacy copy creation still selects the new node")
	check_preserved(before, "legacy copy creation")

	before = snapshot_graph()
	for index in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(index) == panel.GARMENT_SPLIT:
			panel.generator_choice.select(index)
			break
	panel.add_generator()
	await settle()
	created = panel.nodes.back()
	check(created.get("type", "") == panel.GARMENT_SPLIT and created.get("parameters", {}).get("items", null) == [], "legacy generator creation retains garment split defaults")
	check_preserved(before, "legacy generator creation")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_NODE_CREATION_PERFORMANCE_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Incremental node creation preserves existing graph objects, artifact previews and connections; no model inference"}, "  "))
			report.close()
	print("AINATIVE_NODE_CREATION_PERFORMANCE failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
