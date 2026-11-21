extends SceneTree

var detail: Node
var panel: Node
var trace := []
var status: Label


func _initialize() -> void:
	run.call_deferred()


func wait_for(condition: Callable) -> bool:
	var until := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < until:
		await process_frame
	return condition.call()


func check(ok: bool, reason: String) -> bool:
	if not ok:
		printerr("U11: " + reason)
		quit(1)
	return ok


func open_from_detail(number: int, previous_chat: Variant) -> bool:
	var input := detail.find_child("IssueDetailNumber", true, false) as LineEdit
	var action := detail.find_child("ConsultIssueDetail", true, false) as Button
	input.text = str(number)
	input.text_changed.emit(input.text)
	if not check(not action.is_visible_in_tree(), "stale action after editing number"):
		return false
	detail.find_child("ReadIssueDetail", true, false).pressed.emit()
	if not check(await wait_for(func(): return action.is_visible_in_tree()), "missing detail consultation action"):
		return false
	if not check(panel.conversation.get("id") == previous_chat, "reading details changed the chat before click"):
		return false
	action.pressed.emit()
	if not check(await wait_for(func(): return not panel.busy), "consultation open timed out"):
		return false
	var source: Dictionary = detail.get_detail()
	var preview := panel.find_child("IssueConsultationBinding", true, false) as Label
	var chat: String = panel.conversation.get("id", "")
	if not check(not chat.is_empty() and panel.location.issue_id == source.id and panel.module_id == source.module_id and preview.is_visible_in_tree(), "incorrect binding: " + status.text):
		return false
	for field in ["只咨询", "#%d" % number, source.title, source.id, source.revision, chat]:
		if not check(preview.text.contains(field), "preview missing " + str(field)):
			return false
	trace.append({"issue":source.id, "chat":chat, "revision":source.revision, "preview":preview.text, "draft":panel.composer.text})
	return true


func select_module(id: String) -> bool:
	var picker: OptionButton = panel.picker
	for i in picker.item_count:
		if picker.get_item_metadata(i) == id:
			picker.select(i)
			picker.item_selected.emit(i)
			return check(await wait_for(func(): return not panel.busy) and panel.module_id == id, "module switch failed")
	return check(false, "module absent")


func send_turn(body: String) -> bool:
	panel.composer.text = body
	panel.find_child("ModuleSend", true, false).pressed.emit()
	return check(await wait_for(func(): return not panel.busy) and panel.composer.text.is_empty() and panel.history.text.contains(body), "consultation send failed: " + status.text)


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	if not check(results.get_selected().get_metadata(0) == search.text, "command missing"):
		return
	results.item_activated.emit()
	await process_frame
	panel = dock.find_child("WorkbenchBusinessModules", true, false)
	detail = dock.find_child("WorkbenchIssueDetail", true, false)
	var session := detail.get_parent()
	if not check(await wait_for(func(): return not session.get_identity().is_empty()), "identity unavailable"):
		return
	status = panel.get_node("ModuleStatus")
	var fixtures: Dictionary = JSON.parse_string(OS.get_environment("U11_FIXTURES"))
	var a := int(fixtures.numbers[0])
	var b := int(fixtures.numbers[1])
	panel.picker.item_selected.emit(1)
	if not check(await wait_for(func(): return not panel.busy), "module list"):
		return
	panel.picker.get_popup().hide()
	if not await select_module(fixtures.module_id):
		return
	var b_chat: String = fixtures.prior_chat
	if not check(panel.conversation.id == b_chat, "B needs to be current initially"):
		return
	panel.composer.text = "B unsent"
	detail.find_child("OpenIssueDetail", true, false).pressed.emit()
	if not await open_from_detail(a, b_chat):
		return
	var a_chat: String = panel.conversation.id
	if not check(a_chat != b_chat and not panel.history.text.contains("B previous"), "A inherited B"):
		return
	if not await send_turn("A first"):
		return
	panel.composer.text = "A unsent"
	if not await open_from_detail(b, a_chat):
		return
	if not check(panel.conversation.id == b_chat and panel.composer.text == "B unsent" and panel.history.text.contains("B previous") and not panel.history.text.contains("A first"), "B history or draft crossed"):
		return
	if not await send_turn("B first"):
		return
	panel.composer.text = "B next"
	if not await select_module("default") or not await open_from_detail(a, null):
		return
	if not check(panel.conversation.id == a_chat and panel.composer.text == "A unsent" and panel.history.text.contains("A first"), "A lost its room or draft"):
		return
	if not await send_turn("A next"):
		return
	if not await open_from_detail(b, a_chat):
		return
	if not check(panel.conversation.id == b_chat and panel.composer.text == "B next", "B failed to restore after cross-module navigation"):
		return
	await detail.open_issue(99999)
	if not check(not detail.find_child("ConsultIssueDetail", true, false).is_visible_in_tree(), "missing detail offered consultation"):
		return
	print("U11_REPORT=" + JSON.stringify(trace))
	quit(0)
