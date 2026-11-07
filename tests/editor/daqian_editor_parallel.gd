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
	settings.set_setting("gonggong/python",OS.get_environment("DAQIAN_TEST_PYTHON"))
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
	var img = graph.add_node("image",Vector2.ZERO)
	var image := Image.create_empty(8,4,false,Image.FORMAT_RGB8)
	image.fill(Color.HOT_PINK)
	graph.set_image(img,image)
	var a = graph.add_node("task",Vector2(300,-100))
	var b = graph.add_node("task",Vector2(300,200))
	var join = graph.add_node("join",Vector2(650,0))
	await process_frame
	for id in [a,b]:
		graph.connect_ports("requirement",0,id,0)
		graph.connect_ports(img,0,id,0)
		graph.connect_ports(id,0,join,0)
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
