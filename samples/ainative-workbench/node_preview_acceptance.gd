extends SceneTree
# Offline end-to-end checks exercise the real Python transport and Godot previews.
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
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, "node operation finishes while the editor frame loop advances")

func copy_node(id: String, source: String, delay: float = 0.0, fail: bool = false) -> Dictionary:
	return {"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": source, "image_context": "", "text": "", "parameters": {"delay": delay, "fail": fail}, "x": 30, "y": 40}

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
	panel.state_dir = ProjectSettings.globalize_path("user://node-preview-test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("jobs.sqlite")
	var image = ProjectSettings.globalize_path("res://fixtures/sample.png")
	var mesh = ProjectSettings.globalize_path("res://fixtures/sample.glb")
	var image_sha = FileAccess.get_sha256(image)
	var mesh_sha = FileAccess.get_sha256(mesh)
	panel.nodes = [copy_node("upstream", image, 0.15), copy_node("target", "", 0.15), copy_node("downstream", "", 0.0, true), copy_node("unrelated", panel.state_dir.path_join("missing.png"))]
	panel.edges = [{"from": "upstream", "to": "target"}, {"from": "target", "to": "downstream"}]
	panel.rebuild()
	panel.select_node("target")
	var node_button: Button
	for action in panel.graph.get_node("target").find_children("*", "Button", true, false):
		if action.text == "运行并预览": node_button = action
	check(node_button != null, "each graph node exposes an explicit run-and-preview button")
	if node_button == null:
		await finish()
		return
	var ticks = panel.heartbeat
	node_button.pressed.emit()
	var serial_after_start = panel.serial
	panel.run_node_preview("target")
	check(panel.serial == serial_after_start, "a second click during an active run does not start duplicate work")
	await wait_idle()
	check(panel.current.get("state") == "succeeded", "target preview succeeds despite a broken unrelated branch")
	check(panel.current.get("nodes", {}).size() == 2 and panel.current.nodes.has("upstream") and panel.current.nodes.has("target"), "only target and transitive upstream execute; downstream and unrelated nodes are excluded")
	check(panel.heartbeat > ticks + 5, "provider work leaves the editor responsive")
	check(panel.preview_node == "target" and panel.texture.texture != null, "successful target automatically opens the decoded image")
	check(panel.preview_history.get("target", []).size() == 1, "first successful result is recorded once in this node's history")
	var original_run = panel.run_id
	var original_token = panel.preview_token
	panel.text_edit.text = "a revised instruction, awaiting an explicit click"
	await create_timer(0.15).timeout
	check(panel.run_id == original_run and panel.jobs.is_empty() and not panel.auto_step, "editing instructions never triggers a model run")
	# Change a required upstream input to produce a visibly different output type.
	panel.select_node("upstream")
	panel._set_node_file("source", mesh)
	panel.text_edit.text = "new upstream mesh revision"
	panel.apply_fields()
	panel.run_node_preview("target")
	await wait_idle()
	check(panel.preview_scene != null and panel.preview_node == "target", "node preview decodes a real GLB mesh")
	check(panel.preview_history.get("target", []).size() == 2 and panel.history_choice.item_count == 2, "a rerun retains both old and new node results for comparison")
	check(panel.preview_token != original_token, "new input yields a distinct immutable preview version")
	panel.show_history(0)
	check(panel.preview_token == original_token and panel.preview_resource is ImageTexture, "selecting the earlier version restores the previous image")
	panel.show_history(1)
	check(panel.preview_scene != null, "selecting the new version restores the mesh")
	# Give upstream its own result, then leave a target run before its reply arrives.
	panel.select_node("upstream")
	panel.run_node_preview("upstream")
	await wait_idle()
	var upstream_token = panel.preview_token
	check(panel.preview_node == "upstream" and panel.preview_history.get("upstream", []).size() == 1, "history is independent for each node")
	panel.select_node("target")
	panel.text_edit.text = "target run while browsing another node"
	panel.run_node_preview("target")
	panel.select_node("upstream")
	panel.show_history(0)
	await wait_idle()
	check(panel.selected_id == "upstream" and panel.preview_node == "upstream" and panel.preview_token == upstream_token, "a late target reply cannot replace another selected node's preview")
	check(panel.preview_history.get("target", []).size() == 3, "the completed target result is still retained while viewing another node")
	# Failures and cancellation must not replace a successful version.
	panel.params_edit.text = '{"delay":0,"fail":true}'
	panel.text_edit.text = "confirmed failure revision"
	panel.run_node_preview("upstream")
	await wait_idle()
	check(panel.current.get("state") == "failed" and panel.preview_history.get("upstream", []).size() == 1, "a failed rerun does not add or overwrite a successful history entry")
	panel.params_edit.text = '{"delay":1,"fail":false}'
	panel.text_edit.text = "cancelled revision"
	panel.run_node_preview("upstream")
	panel.cancel_run()
	await wait_idle()
	check(panel.current.get("state") == "cancelled" and panel.preview_history.get("upstream", []).size() == 1, "immediate cancellation leaves successful history intact")
	check(FileAccess.get_sha256(image) == image_sha and FileAccess.get_sha256(mesh) == mesh_sha, "previews and reruns preserve original source bytes")
	# Reopening a different workflow with the same node ID must not alias old results.
	panel.path_edit.text = panel.state_dir.path_join("replacement.json")
	var replacement = FileAccess.open(panel.path_edit.text, FileAccess.WRITE)
	replacement.store_string(JSON.stringify({"format": 1, "nodes": [copy_node("upstream", image)], "edges": []}))
	replacement.close()
	panel.params_edit.text = '{"delay":0.3,"fail":false}'
	panel.text_edit.text = "busy workflow replacement regression"
	panel.run_node_preview("upstream")
	var model_before_open = JSON.stringify(panel.model())
	panel.open_graph()
	check(JSON.stringify(panel.model()) == model_before_open and panel.nodes.size() == 4 and not panel.preview_history.is_empty(), "opening a workflow during an active run preserves the live graph and its history")
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and not panel.preview_history.is_empty(), "the guarded run completes with its original graph and result")
	panel.open_graph()
	check(panel.nodes.size() == 1 and panel.selected_id == "upstream" and panel.run_id.is_empty() and panel.current.is_empty(), "valid workflow reopen resets run identity and executor status even when a node ID is reused")
	check(panel.preview_history.is_empty() and panel.preview_token.is_empty() and panel.preview_resource == null and panel.preview_scene == null and panel.history_choice.disabled, "workflow reopen invalidates all old previews and version choices")
	var serial_before_old_preview = panel.serial
	panel.request_preview()
	check(panel.jobs.is_empty() and panel.serial == serial_before_old_preview, "a reopened workflow cannot request results from the previous run")
	# A failed process launch must release the run guard so the user can fix settings.
	var working_python = panel.python_edit.text
	panel.python_edit.text = panel.state_dir.path_join("missing-python-executable")
	panel.run_node_preview("upstream")
	await wait_idle()
	check(not panel.creating and not panel.auto_step and panel.jobs.is_empty() and panel.preview_target.is_empty(), "failed Python launch releases creating and automatic execution state")
	panel.python_edit.text = working_python
	panel.run_node_preview("upstream")
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.preview_history.get("upstream", []).size() == 1 and panel.preview_resource is ImageTexture, "correcting the Python setting allows a fresh run without stale history")
	await finish()

func finish():
	if OS.has_environment("AINATIVE_NODE_PREVIEW_REPORT"):
		var report = FileAccess.open(OS.get_environment("AINATIVE_NODE_PREVIEW_REPORT"), FileAccess.WRITE)
		report.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks}, "  "))
	print("AINATIVE_NODE_PREVIEW failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
