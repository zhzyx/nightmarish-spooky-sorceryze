extends SceneTree

var view: Node
var panel: Node

func _initialize() -> void:
	_run.call_deferred()

func check(ok: bool, message: String) -> bool:
	if not ok:
		printerr("U11: ", message)
		quit(1)
	return ok

func wait_for(condition: Callable) -> bool:
	var until := Time.get_ticks_msec() + 12000
	while not condition.call() and Time.get_ticks_msec() < until:
		await process_frame
	return condition.call()

func open_detail(number: int) -> bool:
	var input := view.find_child("IssueDetailNumber", true, false) as LineEdit
	var consult := view.find_child("ConsultIssueDetail", true, false) as Button
	input.text = str(number)
	input.text_changed.emit(input.text)
	if not check(not consult.is_visible_in_tree(), "stale consultation action on number change"):
		return false
	view.find_child("ReadIssueDetail", true, false).pressed.emit()
	if not check(await wait_for(func(): return consult.is_visible_in_tree()), "detail unavailable"):
		return false
	consult.pressed.emit()
	if not check(await wait_for(func(): return not panel.busy), "open timed out"):
		return false
	return check(panel.conversation.has("id") and panel.location.issue_id == view.get_detail().id and panel.page.text.begins_with("仅咨询") and panel.composer.is_visible_in_tree(), "wrong consultation: " + panel.feedback.text)

func _run() -> void:
	await create_timer(1).timeout
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not check(results.get_selected().get_metadata(0) == search.text, "workbench command unavailable"):
		return
	results.item_activated.emit()
	await process_frame
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	panel = dock.find_child("WorkbenchBusinessModules", true, false)
	if not check(await wait_for(func(): return panel.managed_identity and not panel.session.get_identity().is_empty()), "identity unavailable"):
		return
	var identity: Dictionary = panel.session.get_identity()
	var open := view.find_child("OpenIssueDetail", true, false) as Button
	if not check(open.is_visible_in_tree(), "I02 entry unavailable"):
		return
	open.pressed.emit()
	var fixtures: Array = JSON.parse_string(OS.get_environment("U11_NUMBERS"))
	var trace := []
	for i in fixtures.size():
		if not await open_detail(int(fixtures[i])):
			return
		if not check(panel.conversation.turns.is_empty() and panel.composer.text.is_empty(), "prior issue leaked"):
			return
		var detail: Dictionary = view.get_detail()
		panel.composer.text = "咨询 " + str(i)
		panel.send.pressed.emit()
		if not check(await wait_for(func(): return not panel.busy) and panel.conversation.turns.size() == 1 and panel.composer.text.is_empty(), "turn failed: " + panel.feedback.text):
			return
		if not check(not panel.design_action.is_visible_in_tree(), "write action exposed in consultation"):
			return
		trace.append({"chat": panel.conversation.id, "issue": detail.id, "revision": detail.revision, "mode_label": panel.page.text, "turn": panel.conversation.turns[0].id})
	if not await open_detail(int(fixtures[0])):
		return
	if not check(panel.conversation.id == trace[0].chat and panel.conversation.turns[0].id == trace[0].turn and trace[0].chat != trace[1].chat, "reopening A mixed conversations"):
		return
	panel.session.find_child("SignOut", true, false).pressed.emit()
	if not check(panel.conversation.is_empty() and not panel.content.visible and not view.find_child("ConsultIssueDetail", true, false).is_visible_in_tree(), "sign-out retained issue consultation"):
		return
	print("U11_NATIVE=", JSON.stringify({"records": trace, "identity": identity, "reopened_first": true, "logout_cleared": true}))
	quit()
