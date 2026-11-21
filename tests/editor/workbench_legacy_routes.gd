extends SceneTree

var phase := OS.get_environment("U13_PHASE")
var fixtures: Array = JSON.parse_string(OS.get_environment("U13_ISSUES"))
var observations := {}
var view: Node
var panel: Node


func _initialize() -> void:
	_run.call_deferred()


func check(ok: bool, message: String) -> bool:
	if not ok:
		printerr("U13 ", phase, ": ", message)
		quit(1)
	return ok


func wait_for(predicate: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return predicate.call()


func matched(row: Dictionary) -> bool:
	return not panel.busy and panel.conversation.get("id") == row.chat and panel.location.get("issue_id") == row.issue and panel.conversation.turns.size() == 1 and panel.conversation.turns[0].id == row.turn and panel.page.text.begins_with("仅咨询") and panel.composer.is_visible_in_tree()


func _run() -> void:
	root.size = Vector2i(1600, 900)
	await create_timer(1.2).timeout
	var chat := root.find_child("AI Chat", true, false)
	var tabs := chat.get_parent() as TabContainer
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	view = sidebar.find_child("WorkbenchIssueDetail", true, false)
	panel = root.find_child("WorkbenchBusinessModules", true, false)
	var title_button := root.find_child("OpenAIWorkbench", true, false) as Button
	var entries := []
	for i in tabs.get_tab_count():
		if not tabs.is_tab_hidden(i):
			entries.append(tabs.get_tab_control(i).get_effective_layout_key() if tabs.get_tab_control(i).has_method("get_effective_layout_key") else str(tabs.get_tab_control(i).name))
	var daqian := root.find_child("Daqian", true, false)
	if not check(tabs.is_tab_hidden(tabs.get_tab_idx_from_control(daqian)) and tabs.is_tab_hidden(tabs.get_tab_idx_from_control(chat)) and title_button.is_visible_in_tree() and root.find_children("OpenAIWorkbench", "Button", true, false).size() == 1, "duplicate or missing AI entry"):
		return
	var full := chat.find_child("RestoreWorkbenchSidebar", true, false) as Button
	observations = {"selected": str(tabs.get_current_tab_control().name), "top_button": str(title_button.name), "visible_tabs": entries, "sidebar": sidebar.is_visible_in_tree(), "expanded": full.is_visible_in_tree()}
	if phase.begins_with("legacy_"):
		if not check(full.is_visible_in_tree() and tabs.get_current_tab_control() == chat and chat.is_ancestor_of(panel), "layout did not restore full workbench: " + str(observations)):
			return
	elif phase in ["restart", "other_project"]:
		if not check(tabs.get_current_tab_control().name == &"Script" and sidebar.is_visible_in_tree() and sidebar.is_ancestor_of(panel), "saved sidebar was lost: " + str(observations)):
			return
	elif not check(tabs.get_current_tab_control().name == &"Script" and not sidebar.is_visible_in_tree(), "non-AI layout changed: " + str(observations)):
		return
	if phase == "legacy_chat" or phase == "unchanged":
		finish()
		return
	if not check(await wait_for(func(): return panel.managed_identity and not panel.session.get_identity().is_empty()), "missing session: " + str(panel.managed_identity) + " " + view.get_parent()._status.text):
		return
	if phase == "other_project":
		if not check(panel.conversation.is_empty() and view.get_detail().is_empty() and panel.project == "u13/other", "copied layout exposed another project"):
			return
		observations["foreign_project_cleared"] = true
		finish()
		return
	if phase == "restart":
		if not check(await wait_for(func(): return matched(fixtures[0])), "restart lost previously active consultation: " + view._status.text):
			return
		observations["restored_turn"] = panel.conversation.turns[0].id
	if full.is_visible_in_tree():
		full.pressed.emit()
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	if not check(tabs.get_current_tab_control() == daqian and daqian.is_visible_in_tree(), "existing Tianshu caller lost its board"):
		return
	var workspace := daqian.find_child("DaqianWorkspace", true, false)
	workspace.board = {"repo": "old/studio"}
	var row: Dictionary = fixtures[1]
	var item := {"number": row.old_number, "url": row.url, "title": "核对入口", "owners": []}
	var card: GraphNode = workspace._add_board_card(item, "in-progress", "", PackedStringArray(), "")
	var link: LinkButton = card.get_titlebar_hbox().find_children("*", "LinkButton", false, false)[0]
	if not check(link.tooltip_text == row.url and link.uri.is_empty(), "old board did not produce its canonical internal link"):
		return
	link.pressed.emit()
	if not check(await wait_for(func(): return matched(row)), "card did not recover B: " + view._status.text + " / " + panel.feedback.text):
		return
	var trace := [{"link": link.tooltip_text, "chat": panel.conversation.id, "turn": panel.conversation.turns[0].id}]
	var input := view.find_child("IssueDetailNumber", true, false) as LineEdit
	for index in [0, 1, 0]:
		row = fixtures[index]
		var path: String = "/issues/" + str(row.issue) if index == 0 else row.url
		input.text = path
		input.text_submitted.emit(path)
		if not check(await wait_for(func(): return matched(row)), "pasted link lost conversation: " + path + " / " + view._status.text):
			return
		trace.append({"link": path, "chat": panel.conversation.id, "turn": panel.conversation.turns[0].id})
	var rejected := []
	for invalid in ["https://github.com/old/studio/issues/9998", "https://github.com/old/studio/issues/9999", "https://unrelated.invalid/issues/" + str(row.issue)]:
		input.text = invalid
		input.text_submitted.emit(invalid)
		if not check(await wait_for(func(): return view._status.text in ["当前项目没有唯一关联的天璇工单", "工单链接无效"]) and view.get_detail().is_empty(), "unmapped or ambiguous deep link selected a target"):
			return
		rejected.append({"link": invalid, "feedback": view._status.text})
	observations["rejected"] = rejected
	observations["trace"] = trace
	EditorInterface.set_main_screen_editor("Script")
	title_button.pressed.emit()
	await process_frame
	finish()


func finish() -> void:
	print("U13_NATIVE=", JSON.stringify(observations))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
