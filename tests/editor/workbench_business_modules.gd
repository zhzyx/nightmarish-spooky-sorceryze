extends SceneTree

# Isolated-card contract fixture for the D14 authority. A combined editor uses the actual node.
class SessionProbe extends VBoxContainer:
	signal identity_changed
	signal finish_request
	var identity := {"id": "first", "project": "c06/studio", "role": "editor"}
	var started := false

	func get_identity() -> Dictionary:
		return identity

	func api_request(_method: int, _path: String, _body: Dictionary) -> Dictionary:
		started = true
		await finish_request
		return {"status": 200, "data": {"modules": [{"name": "Old account", "id": "old"}]}}


var panel: Control
var picker: OptionButton
var trace := []


func _initialize() -> void:
	_run.call_deferred()


func _fail(detail: String) -> void:
	push_error(detail)
	quit(1)


func _choose(index: int) -> bool:
	picker.select(index)
	picker.item_selected.emit(index)
	var deadline := Time.get_ticks_msec() + 20000
	while picker.disabled and Time.get_ticks_msec() < deadline:
		await process_frame
	if picker.disabled or panel.get_node("ModuleStatus").visible:
		_fail("Selector failed: " + str(panel.get_node("ModuleStatus").text))
		return false
	picker.get_popup().hide()
	return true


func _index(id: String) -> int:
	for i in picker.item_count:
		if picker.get_item_metadata(i) == id:
			return i
	return -1


func _observe(expected: Dictionary, draft: String) -> bool:
	var issue := panel.find_child("ModuleIssue", true, false) as OptionButton
	var history := panel.find_child("ModuleConversation", true, false) as TextEdit
	var input := panel.find_child("ModuleChatInput", true, false) as TextEdit
	var actual := {"module_id": picker.get_item_metadata(picker.selected),
		"issue_id": issue.get_item_metadata(issue.selected), "conversation_id": panel.conversation.get("id"),
		"position": panel.find_child("ModulePagePosition", true, false).text,
		"history": history.text, "draft": input.text}
	if actual.module_id != expected.module_id or actual.issue_id != expected.issue_id or actual.conversation_id != expected.conversation_id or actual.position != expected.position or actual.draft != draft or not actual.history.contains(expected.message) or not actual.history.contains(expected.design) or not actual.history.contains(expected.issue_body) or not actual.history.contains(expected.comment) or not input.is_visible_in_tree():
		_fail("Incorrect module view: " + JSON.stringify(actual))
		return false
	trace.append(actual)
	return true


func _run() -> void:
	for i in 12:
		await process_frame
	EditorInterface.set_main_screen_editor("2D")
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false)[0] as LineEdit
	var results := palette.find_children("*", "Tree", true, false)[0] as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not results.get_selected() or results.get_selected().get_metadata(0) != search.text:
		_fail("Open AI Workbench command missing")
		return
	results.item_activated.emit()
	await process_frame
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false) as Control
	panel = sidebar.find_child("WorkbenchBusinessModules", true, false)
	if not panel or not panel.is_visible_in_tree():
		_fail("Native sidebar module selector is missing")
		return
	picker = panel.get_node("BusinessModuleSelector")
	var local := sidebar.find_child("ChatInput", true, false) as TextEdit
	local.text = "local pending"
	if not await _choose(1):
		return
	var fixture: Array = JSON.parse_string(OS.get_environment("C06_FIXTURE"))
	var ai := _index(fixture[0].module_id)
	var bi := _index(fixture[1].module_id)
	if ai < 1 or bi < 1 or ai == bi or picker.get_item_text(ai) == picker.get_item_text(bi):
		_fail("Same-name modules cannot be distinguished")
		return
	var input := panel.find_child("ModuleChatInput", true, false) as TextEdit
	if not await _choose(ai) or not _observe(fixture[0], ""):
		return
	input.insert_text_at_caret("A pending")
	if not await _choose(bi) or not _observe(fixture[1], ""):
		return
	input.insert_text_at_caret("B pending")
	if not await _choose(ai) or not _observe(fixture[0], "A pending"):
		return
	if not await _choose(bi) or not _observe(fixture[1], "B pending"):
		return
	var issue := panel.find_child("ModuleIssue", true, false) as OptionButton
	issue.select(0)
	issue.item_selected.emit(0)
	if not await _choose(0) or not local.is_visible_in_tree() or local.text != "local pending":
		_fail("Returning to local chat lost the original draft")
		return
	var fresh := _index("default")
	if fresh < 0 or not await _choose(fresh) or not input.text.is_empty():
		_fail("Fresh default module did not start with an empty composer")
		return
	input.insert_text_at_caret("Explicit consultation")
	panel.find_child("ModuleSend", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 20000
	while picker.disabled and Time.get_ticks_msec() < deadline:
		await process_frame
	if picker.disabled or not input.text.is_empty() or not panel.find_child("ModuleConversation", true, false).text.contains("Explicit consultation"):
		_fail("Explicit module consultation failed: " + str(panel.get_node("ModuleStatus").text))
		return
	if not panel.managed_identity:
		var session := SessionProbe.new()
		session.name = "WorkbenchBusinessSession"
		sidebar.add_child(session)
		panel._bind_session()
		if not panel.managed_identity or not input.text.is_empty() or not local.is_visible_in_tree() or not panel.drafts.is_empty() or not panel.conversation.is_empty():
			_fail("Identity change did not clear the module context")
			return
		picker.select(1)
		picker.item_selected.emit(1)
		if not session.started:
			_fail("Previous identity's read did not start")
			return
		session.identity = {"id": "second", "project": "other", "role": "viewer"}
		session.identity_changed.emit()
		session.finish_request.emit()
		await process_frame
		if picker.item_count != 2 or picker.disabled or panel.project != "other" or not panel.module_id.is_empty():
			_fail("A late reply repopulated the new account's controls")
			return
		print("C06_ISOLATED_IDENTITY_RACE=passed")
	else:
		var account = sidebar.find_child("WorkbenchBusinessSession", true, false)
		input.insert_text_at_caret("private unsent first-account draft")
		account.find_child("ChooseAccount", true, false).pressed.emit()
		account.find_child("AccountEmail", true, false).text = "reviewer@example.invalid"
		account.find_child("AccountSecret", true, false).text = OS.get_environment("C06_SECOND_PASSWORD")
		account.find_child("BusinessProject", true, false).text = panel.project
		account.find_child("Authenticate", true, false).pressed.emit()
		if not panel.module_id.is_empty() or not input.text.is_empty() or not panel.drafts.is_empty() or not panel.history.text.is_empty():
			_fail("Old account data survived the account change")
			return
		var until := Time.get_ticks_msec() + 10000
		while account.get_identity().get("id", "") != OS.get_environment("C06_SECOND_ID") and Time.get_ticks_msec() < until:
			await process_frame
		if account.get_identity().get("id", "") != OS.get_environment("C06_SECOND_ID") or not await _choose(1):
			_fail("Second real business account unavailable")
			return
		var second_default := _index("default")
		if second_default < 1 or not await _choose(second_default) or panel.page.text != "second-account-private-position" or not input.text.is_empty() or not panel.conversation.is_empty() or not panel.history.text.is_empty():
			_fail("Second account received incorrect module state: " + panel.page.text + " / " + panel.history.text)
			return
		print("C06_REAL_ACCOUNT_SWITCH=passed")
	print("C06_NATIVE=" + JSON.stringify(trace))
	quit()
