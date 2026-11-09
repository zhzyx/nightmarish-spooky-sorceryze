@tool
extends SceneTree

func _initialize():
	run.call_deferred()

func fail(message: String):
	push_error(message)
	quit(1)

func run():
	root.size = Vector2i(1440,900)
	await create_timer(1.5).timeout
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace",OS.get_environment("DAQIAN_TEST_REPO"))
	settings.set_setting("ai_chat/cli_node",OS.get_environment("DAQIAN_TEST_NODE"))
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian",true,false)
	if not dock:
		fail("Missing Tianshu tab")
		return
	var tabs = dock.get_parent()
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	await process_frame
	var panel = dock.find_child("DaqianWorkspace",true,false)
	await panel.refresh()
	panel._new_requirement()
	var graph = panel.editor
	graph.draft.nodes.requirement.value = "结合截图核对 AI 对话入口是否有猪头和醒目配色"
	var img := "screenshot"
	var a := "inspect"
	var b := "assess"
	var join := "summary"
	graph.draft.nodes.merge({
		img: {"kind":"image", "title":"Screenshot", "value":""},
		a: {"kind":"task", "title":"Inspect", "value":""},
		b: {"kind":"task", "title":"Assess", "value":""},
		join: {"kind":"join", "title":"Summary", "value":""},
	})
	for id in [a, b]:
		graph.draft.edges.append_array([
			{"from":"requirement", "to":id, "kind":"data"},
			{"from":img, "to":id, "kind":"data"},
			{"from":id, "to":join, "kind":"data"},
		])
	graph.draw_graph()
	var image := Image.create_empty(8,4,false,Image.FORMAT_RGB8)
	image.fill(Color.HOT_PINK)
	graph.set_image(img,image)
	await process_frame
	graph.debug_models[a] = "调试 · Claude"
	graph.debug_models[b] = "调试 · Gemini"
	await panel._start_debug()
	if panel.debug_process.is_empty():
		fail("Tianshu debug launch failed: " + panel.notice.text + " · " + graph.notice.text)
		return
	var diagnostic_pipe: FileAccess = panel.debug_process.stderr
	var deadline = Time.get_ticks_msec()+45000
	while panel.debug_states.get(join,{}).get("state","") != "completed" and Time.get_ticks_msec()<deadline:
		await create_timer(0.1).timeout
	var runs = {}
	for event in panel.debug_history:
		if event.id not in [a,b]:
			continue
		if not runs.has(event.id):
			runs[event.id]={}
		runs[event.id][event.state]=event
	var passed = runs.get(a,{}).has("completed") and runs.get(b,{}).has("completed") and panel.debug_states.get(join,{}).get("state","")=="completed"
	if passed:
		passed = maxf(runs[a].running.at,runs[b].running.at)<minf(runs[a].completed.at,runs[b].completed.at) and runs[a].running.worker!=runs[b].running.worker and "8×4" in runs[a].completed.result and "8×4" in runs[b].completed.result
	if not passed:
		var errors := ""
		if diagnostic_pipe.get_length() > 0:
			errors = diagnostic_pipe.get_buffer(mini(4096,diagnostic_pipe.get_length())).get_string_from_utf8()
		fail("No native overlapping model workers and join: " + str(panel.debug_history) + " " + panel.notice.text + " " + errors)
		return
	print("DAQIAN_NATIVE_PARALLEL_OK ",JSON.stringify({"records":panel.debug_history,"scope":"synthetic_loopback","live_calls":0}))
	panel._stop_debug()
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
