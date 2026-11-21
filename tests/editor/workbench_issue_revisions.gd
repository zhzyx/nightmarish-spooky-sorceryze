extends SceneTree

var report := {}
var expected := OS.get_environment("G12_REVISION")
var number := OS.get_environment("G12_ISSUE")


func _initialize() -> void:
	run.call_deferred()


func wait_for(predicate: Callable) -> bool:
	var end := Time.get_ticks_msec() + 25000
	while not predicate.call() and Time.get_ticks_msec() < end:
		await create_timer(0.04).timeout
	return predicate.call()


func check(ok: bool, message: String) -> bool:
	if not ok:
		printerr("G12 failure: " + message)
		quit(1)
	return ok


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var detail = dock.find_child("WorkbenchIssueDetail", true, false)
	var action = detail.find_child("issue_revisions", true, false)
	var session = detail.get_parent()
	if not check(action != null and await wait_for(func(): return not session.get_identity().is_empty()), "controls or session unavailable"):
		return
	var links := action.find_child("LinkedRevisions", true, false)
	var issues := action.find_child("RevisionIssues", true, false)
	var fields := action.find_child("RevisionFields", true, false) as Label
	if OS.get_environment("G12_PHASE") == "link":
		var palette := EditorInterface.get_command_palette()
		var key := InputEventShortcut.new()
		key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
		root.push_input(key)
		await process_frame
		var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
		var results := palette.find_children("*", "Tree", true, false).front() as Tree
		search.text = "editor/open_ai_workbench"
		search.text_changed.emit(search.text)
		if not check(results.get_selected().get_metadata(0) == search.text, "missing sidebar command"):
			return
		results.item_activated.emit()
		await process_frame
		detail.find_child("OpenIssueDetail", true, false).pressed.emit()
		var input := detail.find_child("IssueDetailNumber", true, false) as LineEdit
		input.text = number
		input.text_changed.emit(number)
		detail.find_child("ReadIssueDetail", true, false).pressed.emit()
		if not check(await wait_for(func(): return action.is_visible_in_tree()), "issue detail failed"):
			return
		action.module.text = "game"
		action.reference.text = "tag:review"
		action.link.pressed.emit()
		if not check(await wait_for(func(): return links.get_child_count() == 1), action.status.text):
			return
	else:
		var chat = root.find_child("AI Chat", true, false)
		if not check(chat.set_runtime_field("workflow_python", OS.get_environment("G12_PYTHON")).is_empty(), "G11 runtime"):
			return
		EditorInterface.set_main_screen_editor("天枢")
		await process_frame
		var panel = root.find_child("DaqianWorkspace", true, false)
		if not check(panel.duobao_commit_button.is_visible_in_tree(), "G11 button hidden"):
			return
		panel.duobao_commit_button.pressed.emit()
		await process_frame
		var dialog = panel.duobao_commit_dialog
		if not check(await wait_for(func(): return not dialog.busy) and dialog.inspect.is_visible_in_tree() and dialog.inspect.tooltip_text == expected, "G11 checkout: " + dialog.status.text):
			return
		dialog.inspect.pressed.emit()
		if not check(await wait_for(func(): return issues.get_child_count() == 1) and issues.get_child(0).is_visible_in_tree(), "G11 reverse view: " + fields.text):
			return
		report.reverse_revision = fields.text
		report.reverse_button = issues.get_child(0).text
		issues.get_child(0).pressed.emit()
		if not check(await wait_for(func(): return links.get_child_count() == 1) and action.is_visible_in_tree(), "I02 reverse navigation: %d links, visible=%s, issue=%s" % [links.get_child_count(), action.is_visible_in_tree(), detail.get_detail().get("number", 0)]):
			return
		report.issue_detail = detail.find_child("IssueDetailFields", true, false).text
	var opened: Button = links.get_child(0)
	if not check(opened.is_visible_in_tree() and opened.tooltip_text == expected, "wrong linked revision"):
		return
	opened.pressed.emit()
	if not check(await wait_for(func(): return issues.get_child_count() == 1) and fields.is_visible_in_tree() and expected in fields.text, "forward revision: " + fields.text):
		return
	report.forward_revision = fields.text
	report.forward_button = opened.text
	print("G12_REPORT=", JSON.stringify(report))
	quit()
