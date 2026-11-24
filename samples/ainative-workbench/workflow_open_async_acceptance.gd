extends SceneTree

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

func node_data(id: String) -> Dictionary:
	return {"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": "", "image_context": "", "text": "", "parameters": {"delay": 0.0, "fail": false}, "x": 30.0, "y": 40.0}

func write_workflow(path: String, id: String):
	var output = FileAccess.open(path, FileAccess.WRITE)
	output.store_string(JSON.stringify({"format": 1, "nodes": [node_data(id)], "edges": []}))
	output.close()

func wait_open():
	var deadline = Time.get_ticks_msec() + 30000
	while is_instance_valid(panel) and panel.is_workflow_opening() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(is_instance_valid(panel) and not panel.is_workflow_opening(), "asynchronous workflow open completes")

func run():
	state_path = ProjectSettings.globalize_path("user://workflow-open-async-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(state_path)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = state_path
	root.add_child(panel)
	panel.nodes = [node_data("current")]
	panel.edges = []
	panel.rebuild()
	var original = JSON.stringify(panel.model())
	var invalid_path = state_path.path_join("invalid.json")
	var invalid = FileAccess.open(invalid_path, FileAccess.WRITE)
	invalid.store_string("{not valid json")
	invalid.close()
	var invalid_hash = FileAccess.get_sha256(invalid_path)
	panel.path_edit.text = invalid_path
	check(panel.open_graph_async(), "asynchronous open accepts a background request")
	check(panel.is_workflow_opening() and panel.workflow_open_apply_count == 0, "asynchronous open returns before applying the decoded graph")
	panel.start_run()
	check(panel.jobs.is_empty() and panel.run_id.is_empty(), "workflow opening blocks execution from replacing the live graph")
	panel.save_graph()
	check(FileAccess.get_sha256(invalid_path) == invalid_hash, "workflow opening blocks saving over the selected file")
	await wait_open()
	check(JSON.stringify(panel.model()) == original and panel.status.text == "工作流无效", "invalid asynchronous input preserves the current graph")
	var first_path = state_path.path_join("first.json")
	var second_path = state_path.path_join("second.json")
	write_workflow(first_path, "first")
	write_workflow(second_path, "second")
	var applies_before = panel.workflow_open_apply_count
	panel.path_edit.text = first_path
	check(panel.open_graph_async(), "first path starts asynchronous opening")
	panel.path_edit.text = second_path
	check(panel.open_graph_async(), "newer path supersedes the pending open")
	await wait_open()
	check(panel.nodes.size() == 1 and panel.nodes[0].id == "second", "only the latest requested workflow replaces the graph")
	check(panel.workflow_open_apply_count == applies_before + 1, "superseded workflow is never applied")
	check(panel.workflow_open_last_prepare_usec >= 0 and panel.workflow_open_last_apply_usec >= 0, "main-thread open stages are measurable")
	panel.path_edit.text = first_path
	check(panel.open_graph_async(), "open can be restarted before workbench disposal")
	panel.queue_free()
	await process_frame
	check(not is_instance_valid(panel), "workbench disposal invalidates pending asynchronous work")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_WORKFLOW_OPEN_ASYNC_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks}, "\t"))
			report.close()
	print("AINATIVE_WORKFLOW_OPEN_ASYNC failures=" + str(failures))
	quit(0 if failures == 0 else 1)
