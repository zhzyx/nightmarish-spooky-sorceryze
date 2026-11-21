extends SceneTree

var thread: ItemList


func _initialize() -> void:
	run.call_deferred()


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func check(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I05: " + message)
		quit(1)
	return ok


func choose(index: int) -> void:
	thread.select(index)
	thread.item_selected.emit(index)


func selection() -> int:
	var selected := thread.get_selected_items()
	return -1 if selected.is_empty() else selected[0]


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var palette := EditorInterface.get_command_palette()
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not check(results.get_selected().get_metadata(0) == search.text, "palette command missing"):
		return
	results.item_activated.emit()
	await process_frame
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var view := dock.find_child("WorkbenchIssueDetail", true, false)
	var widget := view.get_node_or_null("issue_comments") as Control
	if not check(widget != null and not widget.visible, "initial comment widget"):
		return
	if not check(await wait_for(func(): return not session.get_identity().is_empty()), "authentication timeout: " + session.find_child("SessionStatus", true, false).text):
		return
	thread = widget.find_child("IssueCommentThread", true, false)
	var status := widget.find_child("IssueCommentStatus", true, false) as Label
	var body := widget.find_child("IssueCommentDraft", true, false) as TextEdit
	var original := widget.find_child("LocateOriginalComment", true, false) as Button
	var phase := int(OS.get_environment("I05_PHASE"))
	var expected := mini(phase, 3)
	await view.open_issue(int(OS.get_environment("I05_NUMBER")))
	if not check(await wait_for(func(): return widget.is_visible_in_tree() and status.text != "正在读取评论…" and thread.item_count == expected), "thread readback"):
		return
	var restored := selection()
	var expected_restored := [-1, -1, 0, 1]
	if not check(restored == expected_restored[phase], "restored %s in phase %s" % [restored, phase]):
		return
	if phase < 3:
		var button: Button
		if phase > 0:
			choose(phase - 1)
			button = widget.find_child("ReplyToIssueComment", true, false)
		else:
			button = widget.find_child("PostIssueComment", true, false)
		body.text = ["入口截图已更新", "请补上验收步骤" + "\n复核入口和返回路径".repeat(9), "已补充第二步"][phase]
		body.text_changed.emit()
		if not check(not button.disabled and button.is_visible_in_tree(), "post or reply button"):
			return
		button.pressed.emit()
		if phase == 0:
			if not check(await wait_for(func(): return status.text == "未确认发布结果，可重试同一条评论" and not button.disabled), "lost receipt"):
				return
			button.pressed.emit()
		if not check(await wait_for(func(): return thread.item_count == phase + 1 and selection() == phase), "reply did not appear"):
			return
	if phase >= 2:
		if not check(original.is_visible_in_tree(), "original comment button"):
			return
		original.pressed.emit()
		if not check(selection() == (1 if phase == 2 else 0), "original comment not selected"):
			return
	if phase == 2:
		await process_frame
		var full := widget.find_child("SelectedCommentBody", true, false) as RichTextLabel
		if not check(full != null and full.text == thread.get_item_metadata(1).body and full.get_content_height() > full.size.y, "long comment text did not scroll"):
			return
	var rows := []
	for index in thread.item_count:
		rows.append({"data": thread.get_item_metadata(index), "display": thread.get_item_text(index)})
	var record := {"phase": phase, "restored": restored, "selected": selection(), "rows": rows}
	view.find_child("OpenIssueDetail", true, false).pressed.emit()
	if not check(not widget.visible and thread.item_count == 0 and body.text.is_empty(), "close retained issue data"):
		return
	print("I05_REPORT=" + JSON.stringify(record))
	quit(0)
