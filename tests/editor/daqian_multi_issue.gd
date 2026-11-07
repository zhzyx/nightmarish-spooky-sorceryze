@tool
extends SceneTree

func _initialize():
	run.call_deferred()


func add_work(panel,model):
	panel._new_requirement()
	var graph=panel.editor
	graph.draft.nodes.requirement.value="检查本工单"
	# Both issues deliberately contain identically named nodes.
	graph.draft.nodes.question={"kind":"question","title":"选择输入","value":"请给出文本"}
	graph.draft.nodes.worker={"kind":"task","title":"独立工作","value":""}
	graph.draft.edges=[{"from":"question","to":"worker","kind":"data"}]
	graph.debug_models.worker=model
	graph.draw_graph()
	var id=panel.current
	await panel._start_debug()
	return id


func fail(text):
	push_error(text)
	quit(1)


func run():
	root.size=Vector2i(1600,900)
	await create_timer(1.5).timeout
	var settings=EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace",OS.get_environment("DAQIAN_TEST_REPO"))
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	settings.set_setting("ai_chat/cli_node",OS.get_environment("DAQIAN_TEST_NODE"))
	var dock=root.find_child("Daqian",true,false)
	dock.get_parent().current_tab=dock.get_parent().get_tab_idx_from_control(dock)
	var panel=dock.find_child("DaqianWorkspace",true,false)
	await panel.refresh()
	var first=await add_work(panel,"调试 · Claude")
	var coordinator=panel.debug_process.get("pid",-1)
	var second=await add_work(panel,"调试 · Gemini")
	if not panel.debug_sessions.has(first) or not panel.debug_sessions.has(second) or panel.debug_process.pid!=coordinator:
		fail("Independent issue graphs were not registered with the same coordinator")
		return
	var a=panel.debug_sessions[first]
	var b=panel.debug_sessions[second]
	var deadline=Time.get_ticks_msec()+30000
	while (a.states.get("question",{}).get("state")!="waiting" or b.states.get("question",{}).get("state")!="waiting") and Time.get_ticks_msec()<deadline:
		await create_timer(0.04).timeout
	panel._debug_command("answer","question","第二单输入")
	panel._show_issue(first,{"revision":"","plan":panel.rules.new_plan(),"context":{}})
	panel._debug_command("answer","question","第一单输入")
	deadline=Time.get_ticks_msec()+30000
	while (a.states.get("worker",{}).get("state")!="running" or b.states.get("worker",{}).get("state")!="running") and Time.get_ticks_msec()<deadline:
		await create_timer(0.02).timeout
	if a.states.get("worker",{}).get("state")!="running" or b.states.get("worker",{}).get("state")!="running":
		fail("No overlapping workers across issue graphs: "+str([a.history,b.history]))
		return
	if a.states.worker.worker==b.states.worker.worker or a.states.worker.model==b.states.worker.model:
		fail("Different issue graphs shared an execution identity or forced a single model")
		return
	panel._stop_debug()
	if panel.debug_sessions.has(first) or not panel.debug_sessions.has(second):
		fail("Stopping one graph removed the other session")
		return
	deadline=Time.get_ticks_msec()+30000
	while b.states.get("worker",{}).get("state")!="completed" and Time.get_ticks_msec()<deadline:
		await create_timer(0.06).timeout
	if b.states.get("worker",{}).get("state")!="completed" or b.states.worker.issue!=second:
		fail("Unrelated issue did not finish with its own receipt")
		return
	panel._show_issue(second,{"revision":"","plan":panel.rules.new_plan(),"context":{}})
	if not panel.editor.debug_active or panel.editor.debug_states.worker.state!="completed":
		fail("Returning to the second issue lost its terminal result")
		return
	panel._stop_debug()
	if not panel.saved.get("debug_receipts",{}).has(first) or not panel.saved.debug_receipts.has(second):
		fail("Stopping the graphs discarded their separate receipt histories")
		return
	print("DAQIAN_MULTI_ISSUE_OK different_issues=true same_node_ids=true overlapping=true cancel_isolated=true")
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
