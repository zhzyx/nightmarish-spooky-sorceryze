extends SceneTree
## Bottom execution-process panel regression using the real offline Executor.
var panel
var failures := 0

func check(passed: bool, label: String):
	print(("PASS " if passed else "FAIL ") + label)
	if not passed: failures += 1

func _initialize():
	call_deferred("run")

func wait_idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, "offline run reaches an idle state")

func run():
	panel = load("res://addons/ainative/workbench.gd").new()
	root.size = Vector2i(1400, 900)
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	check(panel.process_button != null and panel.get_child(panel.get_child_count() - 1) == panel.process_button, "view-process button stays at the bottom of MaLiang")
	check(not panel.process_panel.visible and panel.process_button.text == "查看具体过程", "process panel starts minimized")
	panel.process_button.pressed.emit()
	await process_frame
	check(panel.process_panel.visible and panel.process_button.text == "收起具体过程", "bottom button opens the process panel")
	panel.get_node("ExecutionProcessPanel").find_child("MinimizeProcessButton", true, false).pressed.emit()
	await process_frame
	check(not panel.process_panel.visible and panel.process_button.text == "查看具体过程", "header minimize collapses the panel without closing the workbench")

	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.state_dir = ProjectSettings.globalize_path("user://process-panel-test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("executor.sqlite")
	panel._set_node_file("source", ProjectSettings.globalize_path("res://fixtures/sample.png"))
	panel.params_edit.text = '{"delay":0.1,"fail":false}'
	panel.run_node_preview(panel.selected_id)
	await wait_idle()
	check(panel.current.get("state") == "succeeded", "real offline node succeeds while process recording is connected")
	var summaries: Array = panel.process_entries.map(func(entry): return str(entry.summary))
	check(summaries.any(func(text): return "已接收任务" in text), "run-started reasoning step is recorded")
	check(summaries.any(func(text): return "全部执行步骤已完成" in text), "completion reasoning step is recorded")
	check(summaries.any(func(text): return "已开始：创建任务" in text) and summaries.any(func(text): return "已完成：读取预览" in text), "command requests and results are recorded")

	panel.process_button.pressed.emit()
	await process_frame
	check("已接收任务" in panel.process_steps.text and "全部执行步骤已完成" in panel.process_steps.text, "reasoning tab renders the chronological execution process")
	check('"command": "create"' in panel.process_logs.text and '"command": "preview"' in panel.process_logs.text, "full log tab includes raw command envelopes")
	panel.get_node("ExecutionProcessPanel").find_child("MinimizeProcessButton", true, false).pressed.emit()
	panel._append_process_entry("测试", "最小化后仍记录", {"marker": "minimized-recording"})
	check(panel.process_entries.back().summary == "最小化后仍记录", "minimizing does not stop event recording")
	panel.process_button.pressed.emit()
	panel._refresh_process_views()
	check("minimized-recording" in panel.process_logs.text, "events recorded while minimized appear after reopening")

	panel.diagnostic_error("过程面板测试诊断", {"marker": "process-panel-diagnostic"})
	panel._refresh_process_views()
	check("process-panel-diagnostic" in panel.process_logs.text and "本机诊断日志" in panel.process_logs.text, "full log includes the persisted local diagnostic record")

	if "--capture" in OS.get_cmdline_user_args():
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://process-panel-preview.png"))
	print("AINATIVE_PROCESS_PANEL failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
