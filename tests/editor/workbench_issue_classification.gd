extends SceneTree

var view: Node


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I17: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func run() -> void:
	root.size = Vector2i(960, 640)
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
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	if not require(view != null, "detail adapter missing"):
		return
	var open := view.find_child("OpenIssueDetail", true, false) as Button
	if not require(await wait_for(func(): return not session.get_identity().is_empty()) and open.is_visible_in_tree(), "session not ready"):
		return
	var panel := view.find_child("issue_classification", true, false)
	if not require(panel != null and panel.get_parent() == view, "Embedded classification controls missing"):
		return
	var ticket: Dictionary = JSON.parse_string(OS.get_environment("I17_TICKET"))
	var label_name := "声音 & 音效"
	var reader: bool = session.get_identity().role == "viewer"
	var kind: LineEdit = panel.find_child("IssueType", true, false)
	var labels: TextEdit = panel.find_child("IssueLabels", true, false)
	var save: Button = panel.find_child("SaveIssueClassification", true, false)
	if not reader:
		open.pressed.emit()
		var number: LineEdit = view.find_child("IssueDetailNumber", true, false)
		number.text = str(int(ticket.number))
		number.text_submitted.emit(number.text)
		if not require(await wait_for(func(): return kind.is_visible_in_tree() and not save.disabled), "Issue not editable"):
			return
		if not require(kind.text == "task" and labels.text == "", "Unexpected initial classification"):
			return
		kind.text = "bug"
		labels.text = label_name + "\n临时"
		save.pressed.emit()
		if not require(await wait_for(func(): return panel.feedback.text == "已保存分类" and view.get_detail().type == "bug"), "Issue type and labels did not save"):
			return
		labels.text = label_name
		save.pressed.emit()
		if not require(await wait_for(func(): return view.get_detail().get("labels") == [label_name] and panel.feedback.text == "已保存分类"), "Label removal did not persist"):
			return
	panel.query.text = "legacy"
	panel.find_button.pressed.emit()
	if not require(await wait_for(func(): return panel.lookup_status.text == "服务未确认项目和标签筛选" and panel.matches.get_child_count() == 0), "Older service presented unfiltered issues as matches"):
		return
	if not require(await lookup(panel, "临时", 0), "Removed or absent label returned issues"):
		return
	if not require(await lookup(panel, label_name, 1), "Expected exactly one issue in this project"):
		return
	var match_button := panel.matches.get_child(0) as Button
	if not require(match_button.text == "#%d %s" % [ticket.number, ticket.title], "Incorrect result"):
		return
	match_button.pressed.emit()
	if not require(await wait_for(func(): return view.get_detail().get("id") == ticket.id and kind.is_visible_in_tree()), "Result did not reopen original UUID"):
		return
	if not require(kind.text == "bug" and labels.text == label_name, "Reopened controls lost classification"):
		return
	if not require(save.disabled == reader and kind.editable != reader and labels.editable != reader, "Read-only controls incorrect"):
		return
	print("I17_REPORT=", JSON.stringify({"project": ticket.project, "role": session.get_identity().role, "reopened_id": view.get_detail().id, "number": int(ticket.number), "type": kind.text, "label": labels.text, "result_count": panel.matches.get_child_count(), "absent_count": 0, "legacy_filter_rejected": true, "save_disabled": save.disabled}))
	quit()


func lookup(panel: Node, label_name: String, count: int) -> bool:
	var field: LineEdit = panel.find_child("IssueLabelQuery", true, false)
	var find_button: Button = panel.find_child("FindIssuesByLabel", true, false)
	if not field.is_visible_in_tree() or not find_button.is_visible_in_tree():
		return false
	field.text = label_name
	field.text_changed.emit(field.text)
	find_button.pressed.emit()
	return await wait_for(func(): return panel.lookup_status.text == "找到 %d 张工单" % count and panel.matches.get_child_count() == count)
