@tool
extends SceneTree

func _initialize():
	run.call_deferred()


func fail(message: String):
	push_error(message)
	quit(1)


func run():
	root.size=Vector2i(1600,900)
	await create_timer(1.5).timeout
	var settings=EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace",OS.get_environment("DAQIAN_TEST_REPO"))
	settings.set_setting("gonggong/python",OS.get_environment("DAQIAN_TEST_PYTHON"))
	settings.set_setting("ai_chat/cli_node",OS.get_environment("DAQIAN_TEST_NODE"))
	var dock=root.find_child("Daqian",true,false)
	dock.get_parent().current_tab=dock.get_parent().get_tab_idx_from_control(dock)
	var panel=dock.find_child("DaqianWorkspace",true,false)
	await panel.refresh()
	panel._new_requirement()
	var graph=panel.editor
	graph.draft.nodes.requirement.value="校验图片和待答分支"
	var first=graph.add_node("task",Vector2(350,20))
	var waiting=graph.add_node("task",Vector2(350,400))
	var question=graph.add_node("question",Vector2(10,400))
	graph.draft.nodes[question].value="请选择强调色"
	var picture=graph.add_image_for_task(first)
	var png:=Image.create_empty(12,7,false,Image.FORMAT_RGB8)
	png.fill(Color.TEAL)
	var path=ProjectSettings.globalize_path("res://daqian-input.png")
	if png.save_png(path)!=OK:
		fail("Cannot prepare image input")
		return
	graph.picker.file_selected.emit(path)
	var encoded=graph.draft.nodes[picture].value
	if encoded.is_empty() or graph.draft.edges.size()!=1:
		fail("Picker did not fill the image automatically linked to the requesting task")
		return
	graph.clipboard_image=func():return png
	var pasted=graph.add_node("image",Vector2(5,125))
	for button in graph.canvas.get_node(pasted).find_children("*","Button",true,false):
		if button.text=="粘贴截图":
			button.pressed.emit()
	var count=graph.draft.nodes.size()
	panel.insert_dropped_images(PackedStringArray([path]),Vector2(8,180))
	if graph.draft.nodes[pasted].value!=encoded or graph.draft.nodes.size()!=count+1:
		fail("Paste or drop entry did not create the expected image")
		return
	await process_frame
	graph.connect_ports(question,0,waiting,0)
	graph.connect_ports(picture,0,waiting,0)
	graph.debug_models[first]="调试 · Claude"
	graph.debug_models[waiting]="调试 · Gemini"
	await panel._start_debug()
	var deadline=Time.get_ticks_msec()+30000
	while panel.debug_states.get(first,{}).get("state","")!="running" and Time.get_ticks_msec()<deadline:
		await create_timer(0.02).timeout
	panel._debug_command("cancel",first,"")
	while panel.debug_states.get(first,{}).get("state","")!="cancelled" and Time.get_ticks_msec()<deadline:
		await create_timer(0.04).timeout
	if panel.debug_states.get(first,{}).get("state","")!="cancelled":
		fail("No terminal cancellation receipt")
		return
	panel._debug_command("retry",first,"调试 · GPT")
	deadline=Time.get_ticks_msec()+30000
	while panel.debug_states.get(first,{}).get("state","")!="completed" and Time.get_ticks_msec()<deadline:
		await create_timer(0.1).timeout
	if panel.debug_states.get(question,{}).get("state","")!="waiting" or panel.debug_states.has(waiting):
		fail("Unanswered branch did not wait independently")
		return
	await panel._answer_question(question,"青色")
	deadline=Time.get_ticks_msec()+30000
	while panel.debug_states.get(waiting,{}).get("state","")!="completed" and Time.get_ticks_msec()<deadline:
		await create_timer(0.1).timeout
	if panel.debug_states.get(waiting,{}).get("state","")!="completed" or panel.debug_states[first].run!=2 or panel.debug_states[first].model!="调试 · GPT":
		fail("Accepted answer did not resume only the dependent branch")
		return
	panel._stop_debug()
	var case_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/127"
	panel.board.issues=[{"url":case_url,"number":127,"request":"daqian-ai-entry-pig-20261105"}]
	panel._show_issue(case_url,{"revision":"fixture-case","plan":graph.rules.new_plan(),"context":{}})
	await panel._chat_action("discuss")
	var bindings=settings.get_project_metadata("daqian","bindings",{})
	var bound=false
	for entry in bindings.values():
		if entry.source==case_url and entry.issue_number=="127" and entry.request_id=="daqian-ai-entry-pig-20261105":
			bound=true
	if not bound:
		fail("Daqian context was not carried into the associated chat")
		return
	dock.get_parent().current_tab=dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	if panel.current!=case_url:
		fail("Returning to Daqian lost the originating issue")
		return
	print("DAQIAN_NATIVE_INPUTS_OK picker=true paste_fixture=true drop_route=true fan_out=true answer_resume=true")
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
