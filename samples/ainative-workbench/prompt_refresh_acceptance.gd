extends SceneTree
# Full-workflow prompt changes and deletable artifact nodes; local fixture only.
var panel
var failures = 0
var checks: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func wait_idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating or not panel.artifact_preview_queue.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating and panel.artifact_preview_queue.is_empty(), "full workflow and artifact preview queue finish")

func set_prompt(value: String):
	panel.parameter_form.prompt_edit.text = value
	panel.parameter_form.prompt_edit.text_changed.emit()

func run():
	root.size = Vector2i(1400, 900)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.state_dir = OS.get_environment("AINATIVE_PROMPT_REFRESH_STATE")
	if panel.state_dir.is_empty(): panel.state_dir = ProjectSettings.globalize_path("user://prompt-refresh-test")
	panel.state_dir = panel.state_dir.path_join(str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	root.add_child(panel)
	await process_frame
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "test_prompt_refresh_factory:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.db = panel.state_dir.path_join("jobs.sqlite")
	panel.nodes = [{"id": "image", "type": "generate_image", "version": "2", "provider": "prompt_fixture", "source": "", "image_context": "", "text": "", "parameters": {"prompt": "red stone owl", "seed": 1}, "x": 40.0, "y": 60.0}]
	panel.edges = []
	panel.rebuild()
	panel.select_node("image")
	set_prompt("red stone owl")
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state") == "succeeded", "full workflow succeeds with the local image provider")
	check(panel.artifact_nodes.has("image") and panel.preview_history.get("image", []).size() == 1, "full workflow automatically creates and populates the artifact node")
	var first = panel._latest_image_entry("image")
	var first_sha = FileAccess.get_sha256(str(first.get("path", "")))
	set_prompt("blue glass tree")
	panel.start_run()
	await wait_idle()
	var second = panel._latest_image_entry("image")
	var second_sha = FileAccess.get_sha256(str(second.get("path", "")))
	check(panel.current.get("nodes", {}).get("image", {}).get("request", {}).get("parameters", {}).get("prompt") == "blue glass tree", "edited prompt reaches the new full-workflow request")
	check(panel.preview_history.get("image", []).size() == 2 and first_sha != second_sha, "changed prompt refreshes the gallery with different image bytes")
	check(panel.artifact_nodes["image"].entry.get("token") == second.get("token") and panel.preview_source_path == second.get("path"), "dynamic node and selected preview both show the latest result")
	var artifact_id = str(panel.artifact_nodes["image"].id)
	panel._keyboard_delete([artifact_id])
	await process_frame
	check(not panel.artifact_nodes.has("image") and panel.nodes.size() == 1 and panel.preview_history["image"].size() == 2, "Delete removes only the dynamic node and preserves formal state and history")
	check(FileAccess.file_exists(first.path) and FileAccess.file_exists(second.path), "deleting the presentation node preserves generated image files")
	panel.rebuild()
	check(not panel.artifact_nodes.has("image"), "ordinary graph rebuild does not resurrect a dismissed artifact")
	panel.run_node_preview("image")
	await wait_idle()
	check(panel.artifact_nodes.has("image") and panel.preview_history["image"].size() == 3, "an explicit new run restores the result node and records its run version")
	await finish()

func finish():
	var report_path = OS.get_environment("AINATIVE_PROMPT_REFRESH_REPORT")
	if not report_path.is_empty():
		var report = FileAccess.open(report_path, FileAccess.WRITE)
		if report != null:
			report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks, "scope": "Local prompt-sensitive provider; no external inference"}, "  "))
			report.close()
	print("AINATIVE_PROMPT_REFRESH failures=" + str(failures))
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
