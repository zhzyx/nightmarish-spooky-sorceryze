extends SceneTree


class Workspace extends "res://editor/docks/daqian/workspace.gd":
	func _repo() -> String: return "fixture"
	func _sync_workflow(_redraw := true) -> void: pass
	func _exit_tree() -> void: pass


func _initialize() -> void:
	var original_orphans := Node.get_orphan_node_ids()
	var panel := Workspace.new()
	var graph := preload("res://editor/docks/daqian/issue_graph.gd").new()
	var pid := OS.create_process(OS.get_environment("DAQIAN_TEST_PYTHON"), ["-c", "import time; time.sleep(15)"])
	var directory := OS.get_user_data_dir().path_join("stage-" + Crypto.new().generate_random_bytes(8).hex_encode())
	var request := "daqian-direct-00000000000000000001"
	var folder := directory.path_join("daqian-direct").path_join(request)
	var source := {"number":518, "request_id":request, "url":"https://github.com/test/repo/issues/518",
		"revision":"revision", "actor":"actor", "source_sha256":"source".sha256_text()}
	var row := {"number":518, "request":request, "url":source.url, "updated":source.revision, "source_sha256":source.source_sha256}
	panel.actor = {"user_id":"actor"}
	panel.fresh_progress = true
	panel.progress_directory = directory
	var key := panel._routing_key(row)
	panel.routing_in_flight[key] = pid
	var ok := pid > 0 and DirAccess.make_dir_recursive_absolute(folder) == OK
	var path := folder.path_join("route-" + JSON.stringify(source).sha256_text() + ".json")
	var attempt := {"pid":pid, "agent":"sinan"}
	var journal := {"binding":source, "calls":{"call":{"attempts":[attempt]}}}
	for stage in ["sinan", "yanshi"]:
		attempt.agent = stage
		var f := FileAccess.open(path, FileAccess.WRITE)
		f.store_string(JSON.stringify(journal))
		f.close()
		panel._read_routing_stage(row)
		ok = ok and panel._routing_stage(row) == stage
		graph.draft = {"nodes":{"requirement":{"kind":"text"}}, "edges":[]}
		graph.workflow = {"phase":"routing", "direct":true, "judging":true, "design":{}, "item":{}, "routing_stage":stage}
		var plan := graph._display_plan()
		ok = ok and (plan.nodes.has("wf-analysis") == (stage == "yanshi"))
		if stage == "yanshi":
			ok = ok and graph._node_state("wf-analysis") == "running" and graph._node_state("wf-routing") == "completed"

	panel.routing_stages.clear()
	var linked := row.duplicate()
	linked.erase("source_sha256")
	panel._read_routing_stage(linked)
	ok = ok and panel._routing_stage(linked) == "yanshi"
	for field in ["number", "url", "request", "updated", "source_sha256"]:
		var different := row.duplicate()
		different[field] = 999 if field == "number" else "wrong"
		panel.routing_stages.clear()
		panel.routing_in_flight[panel._routing_key(different)] = pid
		panel._read_routing_stage(different)
		ok = ok and panel._routing_stage(different).is_empty()
	panel.actor.user_id = "different"
	panel.routing_in_flight[panel._routing_key(row)] = pid
	panel._read_routing_stage(row)
	ok = ok and panel._routing_stage(row).is_empty()
	panel.actor.user_id = "actor"
	attempt.outcome = "decision_received"
	var completed := FileAccess.open(path, FileAccess.WRITE)
	completed.store_string(JSON.stringify(journal))
	completed.close()
	row.judgment_attempt = {"pid":pid,"agent":"yanshi"} # Older board snapshot.
	panel._read_routing_stage(row)
	ok = ok and panel._routing_stage(row).is_empty() and panel.saved.get("routing", {}).is_empty()
	row.erase("judgment_attempt")
	attempt.erase("outcome")
	attempt.pid = pid + 1
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(journal))
	f.close()
	panel._read_routing_stage(row)
	ok = ok and panel._routing_stage(row).is_empty() and panel.saved.get("routing", {}).is_empty()
	if pid > 0: OS.kill(pid)
	DirAccess.remove_absolute(path)
	DirAccess.remove_absolute(folder)
	DirAccess.remove_absolute(folder.get_base_dir())
	DirAccess.remove_absolute(directory)
	panel.free()
	graph.free()
	for id in Node.get_orphan_node_ids():
		if not original_orphans.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent(): node.free()
	if ok: print("DAQIAN_ROUTING_STAGE_OK")
	else: push_error("Route stage was missing or escaped its live binding")
	quit(0 if ok else 1)
