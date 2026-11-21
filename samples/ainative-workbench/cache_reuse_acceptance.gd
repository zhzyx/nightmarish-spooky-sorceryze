extends SceneTree
# Offline cache-reuse checks using the real Godot controls, subprocess host and copy provider.
var panel
var failures = 0
var checks: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func wait_idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, "cache operation finishes: " + panel.status.text)

func copy_node(id: String, source: String) -> Dictionary:
	return {"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": source, "image_context": "", "text": "", "parameters": {"delay": 0.05, "fail": false}, "x": 30, "y": 40}

func node(id: String) -> Dictionary:
	for data in panel.nodes:
		if data.id == id: return data
	return {}

func _initialize():
	call_deferred("run")

func run():
	panel = load("res://addons/ainative/workbench.gd").new()
	root.size = Vector2i(1400, 900)
	root.add_child(panel)
	await process_frame
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.state_dir = ProjectSettings.globalize_path("user://cache-reuse-test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("jobs.sqlite")
	var image = ProjectSettings.globalize_path("res://fixtures/sample.png")
	panel.nodes = [copy_node("upstream", image), copy_node("target", "")]
	panel.edges = [{"from": "upstream", "to": "target"}]
	panel.rebuild()
	panel.select_node("target")
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.current.get("nodes", {}).size() == 2, "initial workflow executes both uncached nodes")
	check(panel.preview_history.get("upstream", []).size() == 1 and panel.preview_history.get("target", []).size() == 1, "initial results populate both node caches")
	if failures > 0:
		await finish()
		return
	var upstream_job = str(panel.current.nodes.upstream.job.job_id)
	var target_job = str(panel.current.nodes.target.job.job_id)

	# The execution plan proves that the unchanged upstream is not scheduled again.
	panel.run_node_preview("target")
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.current.get("nodes", {}).size() == 1 and panel.current.nodes.has("target"), "single-node preview reuses upstream bytes without scheduling the upstream node")
	if not panel.current.get("nodes", {}).has("target"):
		await finish()
		return
	check(str(panel.current.nodes.target.job.job_id) != target_job, "single-node preview really reruns its own logic instead of returning the invocation cache")
	check(panel.preview_history.upstream.size() == 1 and panel.preview_history.target.size() == 2, "single-node rerun retains upstream cache and appends only its own result")
	target_job = str(panel.current.nodes.target.job.job_id)

	var serial = panel.serial
	panel.start_run()
	check(panel.serial == serial and panel.jobs.is_empty() and not panel.auto_step and panel.current.is_empty(), "fully cached global run completes synchronously without creating a process")
	check(panel.status.text.contains("直接完成") and panel.preview_history.upstream.size() == 1 and panel.preview_history.target.size() == 2, "fully cached global run preserves every result and explains immediate completion")

	# Saved histories are sufficient cache data after execution authority is reset.
	panel.path_edit.text = panel.state_dir.path_join("cached-workflow.json")
	panel.save_graph()
	var legacy = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	for history in legacy.get("output_history", {}).values():
		for entry in history: entry.erase("cache_fingerprint")
	var legacy_file = FileAccess.open(panel.path_edit.text, FileAccess.WRITE)
	legacy_file.store_string(JSON.stringify(legacy))
	legacy_file.close()
	panel.open_graph()
	check(panel.preview_history.upstream[0].get("cache_fingerprint", "") != "", "legacy caches receive a definition fingerprint when the workflow opens")
	serial = panel.serial
	panel.start_run()
	check(panel.serial == serial and panel.status.text.contains("直接完成") and panel.preview_history.target.size() == 2, "reopened legacy output snapshots support a fully cached global run")
	panel.select_node("target")
	panel.run_node_preview("target")
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.current.nodes.size() == 1 and panel.preview_history.target.size() == 3, "reopened upstream snapshot feeds a target-only preview")
	target_job = str(panel.current.nodes.target.job.job_id)

	panel.preview_history.erase("target")
	panel.refresh_history()
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.current.nodes.size() == 1 and panel.current.nodes.has("target"), "partial global run executes only the node whose cache was removed")
	check(panel.preview_history.upstream.size() == 1 and panel.preview_history.target.size() == 1, "partial global run retains cached upstream history and rebuilds the missing result")
	target_job = str(panel.current.nodes.target.job.job_id)

	panel.request_run_all()
	check(panel.run_all_dialog.visible and panel.run_all_dialog.dialog_text.contains("清空所有节点") and panel.preview_history.target.size() == 1, "run-all button opens an explicit destructive confirmation without clearing results")
	panel.run_all_dialog.hide()
	check(panel.preview_history.upstream.size() == 1 and panel.preview_history.target.size() == 1 and not panel.creating, "dismissing the confirmation preserves caches and starts nothing")
	check(panel.run_all_button.text == "全部重跑", "workflow toolbar exposes the run-all action")
	panel.run_all_button.pressed.emit()
	check(panel.run_all_dialog.visible, "toolbar run-all button opens the same confirmation")
	panel.run_all_dialog.confirmed.emit()
	panel.run_all_dialog.hide()
	check(panel.preview_history.is_empty(), "confirmation clears every existing result cache before rerunning")
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.current.nodes.size() == 2, "confirmed run-all executes the complete workflow again")
	check(str(panel.current.nodes.upstream.job.job_id) != upstream_job and str(panel.current.nodes.target.job.job_id) != target_job, "confirmed run-all bypasses old invocation receipts for every node")
	check(panel.preview_history.upstream.size() == 1 and panel.preview_history.target.size() == 1, "run-all replaces cleared caches with one fresh result per node")

	node("upstream").parameters.delay = 0.06
	var invalidated = panel.execution_model()
	check(invalidated.get("nodes", []).size() == 2 and invalidated.get("reused_nodes", []).is_empty(), "changing an upstream definition invalidates both its cache and the downstream cache")
	node("upstream").parameters.delay = 0.05
	var restored = panel.execution_model()
	check(restored.get("nodes", []).is_empty() and restored.get("reused_nodes", []).size() == 2, "restoring the original definition makes the immutable caches reusable again")

	panel.preview_history["queue"] = [{"type": "image", "path": image, "token": "queue-primary", "images": [
		{"type": "image", "path": image, "token": "queue-first", "label": "正面"},
		{"type": "image", "path": image, "token": "queue-second", "label": "侧面"}
	]}]
	var queued = panel._cached_output("queue", "image_set")
	check(queued.get("artifacts", []).size() == 3 and queued.get("reference", {}).get("id", "").ends_with("image-set"), "ordered image-set cache reconstructs members and one collection artifact")
	if not queued.is_empty():
		var collection: Dictionary = queued.artifacts.back()
		check(collection.payload.items.map(func(item): return item.label) == ["正面", "侧面"] and collection.payload.items.map(func(item): return item.index) == [0, 1], "ordered image-set cache preserves member labels and indexes")
	panel.preview_history.erase("queue")
	await finish()

func finish():
	if OS.has_environment("AINATIVE_CACHE_REUSE_REPORT"):
		var report = FileAccess.open(OS.get_environment("AINATIVE_CACHE_REUSE_REPORT"), FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks}, "  "))
			report.close()
	print("AINATIVE_CACHE_REUSE failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
