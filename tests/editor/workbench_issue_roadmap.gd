extends SceneTree

var tree: Tree
var detail: Node
var status: Label


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I08: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func expand_path(path: Array) -> TreeItem:
	var parent := tree.get_root()
	for caption: String in path:
		var match_item: TreeItem = null
		for child: TreeItem in parent.get_children():
			if child.get_text(0) == caption:
				match_item = child
				break
		if match_item == null:
			return null
		if parent != tree.get_root():
			if not require(parent.collapsed, "ancestor already expanded: " + parent.get_text(0)):
				return null
			parent.collapsed = false
		parent = match_item
	return parent


func run() -> void:
	await create_timer(1).timeout
	var palette := EditorInterface.get_command_palette()
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not require(results.get_selected().get_metadata(0) == search.text, "command unavailable"):
		return
	results.item_activated.emit()
	await process_frame
	var view := root.find_child("WorkbenchIssueRoadmap", true, false)
	if not require(view != null, "roadmap not mounted"):
		return
	var open := view.find_child("OpenIssueRoadmap", true, false) as Button
	tree = view.find_child("IssueRoadmapTree", true, false)
	status = view.find_child("IssueRoadmapStatus", true, false)
	detail = view.get_parent().get_node("WorkbenchIssueDetail")
	var open_selected := view.find_child("OpenRoadmapIssue", true, false) as Button
	var membership := detail.find_child("IssuePlanCounts", true, false) as Label
	var milestone := detail.find_child("IssueMilestone", true, false) as LineEdit
	var targets: Array = JSON.parse_string(OS.get_environment("I08_TARGETS"))
	if not require(await wait_for(func(): return not open.disabled) and open.is_visible_in_tree(), "session unavailable"):
		return
	var observed := []
	for target: Dictionary in targets:
		open.pressed.emit()
		if not require(await wait_for(func(): return status.text == "studio/game · 6 张工单"), "unexpected projection: " + status.text):
			return
		var item := expand_path(target.path)
		if not require(item != null and item.get_metadata(0) == int(target.number), "incorrect path: " + str(target.path)):
			return
		item.select(0)
		if not require(not open_selected.disabled, "selected issue is unavailable"):
			return
		if observed.size() % 2 == 0:
			open_selected.pressed.emit()
		else:
			tree.item_activated.emit()
		if not require(await wait_for(func(): return detail.get_detail().get("id") == target.id and not membership.text.is_empty()), "I02 or I07 missing"):
			return
		var row: Dictionary = detail.get_detail()
		var milestone_caption := "未设置" if milestone.text.is_empty() else milestone.text
		var count := 4 if milestone.text == "预览" else 1
		if not require(membership.text.ends_with("里程碑「%s」　%d 单" % [milestone_caption, count]), "I07 counts diverged"):
			return
		observed.append({"path": target.path, "number": row.number, "id": row.id, "title": row.title, "milestone": milestone.text})
	view.get_parent().find_child("SignOut", true, false).pressed.emit()
	if not require(open.disabled and tree.get_root() == null, "signed-out roadmap retained"):
		return
	print("I08_REPORT=" + JSON.stringify(observed))
	quit(0)
