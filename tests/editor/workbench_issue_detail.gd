extends SceneTree

var view: Node


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I02: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func open_workbench() -> Node:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	if not require(dock != null, "sidebar missing"):
		return null
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
		return null
	results.item_activated.emit()
	await process_frame
	return dock


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	if not require(view != null, "detail adapter missing"):
		return
	var open := view.find_child("OpenIssueDetail", true, false) as Button
	if not require(await wait_for(func(): return not session.get_identity().is_empty()) and open.is_visible_in_tree(), "session not ready"):
		return
	open.pressed.emit()
	var status := view.find_child("IssueDetailStatus", true, false) as Label
	var fields := view.find_child("IssueDetailFields", true, false) as Label
	var input := view.find_child("IssueDetailNumber", true, false) as LineEdit
	var read := view.find_child("ReadIssueDetail", true, false) as Button
	var records := []
	var numbers: Array = JSON.parse_string(OS.get_environment("I02_NUMBERS"))
	for number in numbers:
		input.text = str(int(number))
		input.text_changed.emit(input.text)
		if not require(fields.text.is_empty() and view.get_detail().is_empty(), "editing number retained previous record"):
			return
		read.pressed.emit()
		if not require(await wait_for(func(): return status.text != "正在读取工单…"), "detail reply timeout"):
			return
		if not require(status.is_visible_in_tree() and fields.is_visible_in_tree(), "detail fields not visible"):
			return
		records.append({"status": status.text, "visible": fields.text, "detail": view.get_detail()})
	await view.open_issue(int(numbers[0]))
	if not require(not view.get_detail().is_empty() and not fields.text.is_empty(), "could not refresh after 404"):
		return
	session.find_child("SignOut", true, false).pressed.emit()
	open.pressed.emit()
	if not require(input.text.is_empty() and fields.text.is_empty() and view.get_detail().is_empty() and status.text == "请先登录天璇", "signed-out state"):
		return
	print("WORKBENCH_REPORT=" + JSON.stringify(records))
	quit(0)
