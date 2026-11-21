extends SceneTree

var view: Node


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I03: " + message)
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
	open.pressed.emit()
	var panel := view.find_child("issue_hierarchy", true, false)
	if not require(panel != null and panel.get_parent() == view, "Hierarchy control missing from the native detail"):
		return
	var attach: Button = panel.find_child("SetIssueParent", true, false)
	var detach: Button = panel.find_child("RemoveIssueParent", true, false)
	var input: LineEdit = panel.find_child("ParentIssueNumber", true, false)
	var numbers: Array = JSON.parse_string(OS.get_environment("I03_NUMBERS"))
	await view.open_issue(int(numbers[1]))
	if not require(await wait_for(func(): return not attach.disabled), "Child hierarchy missing"):
		return
	var before: String = view.get_detail().revision
	var scroll := dock.find_child("WorkbenchSidebarScroll", true, false) as ScrollContainer
	if not require(scroll != null, "Sidebar scroll container missing"):
		return
	for frame in 5:
		await process_frame
	var bar := scroll.get_v_scroll_bar()
	var close := dock.find_child("CloseWorkbench", true, false) as Button
	scroll.ensure_control_visible(close)
	await process_frame
	var bounds := scroll.get_global_rect()
	if not require(bar.max_value > bar.page and scroll.scroll_vertical > 0 and bounds.encloses(close.get_global_rect()), "Close control unreachable in narrow sidebar: %s, %s, %s" % [bounds, close.get_global_rect(), bar.max_value - bar.page]):
		return
	scroll.ensure_control_visible(attach)
	await process_frame
	if not require(bounds.encloses(attach.get_global_rect()) and bounds.encloses(detach.get_global_rect()), "Hierarchy buttons clipped"):
		return
	var geometry := {"window": str(root.size), "visible": str(bounds), "max_scroll": bar.max_value - bar.page, "close_reachable": true, "actions_reachable": true}
	input.text = str(int(numbers[0]))
	attach.pressed.emit()
	if not require(await wait_for(func(): return not detach.disabled), "Attach failed"):
		return
	var attached: Variant = panel.expected_parent
	var attached_revision: String = view.get_detail().revision
	if not require(before != attached_revision, "Details retained stale revision after attach"):
		return
	await view.open_issue(int(numbers[0]))
	if not require(await wait_for(func(): return not attach.disabled and panel.current.text.contains("待归类的设计")), "Parent did not list child"):
		return
	input.text = str(int(numbers[1]))
	attach.pressed.emit()
	if not require(await wait_for(func(): return panel.status.text.contains("循环") and not attach.disabled), "Cycle not rejected"):
		return
	var cycle_parent: Variant = panel.expected_parent
	await view.open_issue(int(numbers[1]))
	if not require(await wait_for(func(): return not detach.disabled), "Child no longer points to parent"):
		return
	detach.pressed.emit()
	if not require(await wait_for(func(): return panel.status.text == "已解除父子关系" and not attach.disabled and detach.disabled), "Detach failed"):
		return
	if not require(view.get_detail().revision == before and panel.expected_parent == null, "Child revision/parent not restored"):
		return
	await view.open_issue(int(numbers[0]))
	if not require(await wait_for(func(): return not attach.disabled and not panel.current.text.contains("待归类的设计")), "Parent retained detached child"):
		return
	print("I03_REPORT=", JSON.stringify({"attached": attached, "cycle_parent": cycle_parent, "detached": panel.expected_parent, "original_revision": before, "attached_revision": attached_revision, "geometry": geometry}))
	quit()
