extends SceneTree

var view: Node
var report := {}


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I01: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	if not require(dock != null, "sidebar missing"):
		return
	var palette := EditorInterface.get_command_palette()
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not require(results.get_selected().get_metadata(0) == search.text, "command not selected"):
		return
	results.item_activated.emit()
	await process_frame
	view = dock.find_child("WorkbenchIssueCreation", true, false)
	if not require(view != null, "issue adapter missing"):
		return
	var open := view.find_child("OpenIssueCreation", true, false) as Button
	if not require(await wait_for(func(): return not open.disabled) and open.is_visible_in_tree(), "session not ready"):
		return
	open.pressed.emit()
	var modules := view.find_child("IssueModule", true, false) as OptionButton
	var expected_module := OS.get_environment("I01_MODULE")
	if not require(await wait_for(func(): return modules.item_count == 2), "modules not loaded"):
		return
	for index in modules.item_count:
		if modules.get_item_metadata(index) == expected_module:
			modules.select(index)
	if not require(modules.get_selected_metadata() == expected_module, "test module missing"):
		return
	var title := view.find_child("IssueTitle", true, false) as LineEdit
	title.text = "检查建单回执"
	var submit := view.find_child("CreateIssue", true, false) as Button
	var status := view.find_child("IssueReceipt", true, false) as Label
	submit.pressed.emit()
	if not require(await wait_for(func(): return submit.text == "重试同一请求"), "committed failure missing"):
		return
	report["first_response"] = status.text
	submit.pressed.emit()
	if not require(await wait_for(func(): return status.text.begins_with("#")), "retry did not return verified number"):
		printerr(status.text)
		return
	report["visible_receipt"] = status.text
	var number := int(status.text.get_slice(" ", 0).trim_prefix("#"))
	var readback: Dictionary = await view.read_issue(number)
	if not require(readback.status == 200 and readback.data.module_id == expected_module and readback.data.title == title.text, "number readback mismatch"):
		return
	report["authority"] = {"id": readback.data.id, "number": number, "module_id": readback.data.module_id, "project": readback.data.project}
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(open.disabled and title.text.is_empty() and status.text.is_empty(), "logout retained private content"):
		return
	print("I01_REPORT=" + JSON.stringify(report))
	quit(0)
