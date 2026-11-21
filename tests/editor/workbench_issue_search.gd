extends SceneTree

var view: Node
var modules: OptionButton
var assignee: LineEdit
var states: OptionButton
var keyword: LineEdit
var search: Button
var results: ItemList
var status: Label
var observations := {}


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I11: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func select_value(picker: OptionButton, value: Variant) -> void:
	for index in picker.item_count:
		if picker.get_item_metadata(index) == value:
			picker.select(index)
			picker.item_selected.emit(index)
			return


func observed(key: String, expected: Array) -> bool:
	if not require(await wait_for(func(): return status.text.begins_with("共 ") or status.text == "没有符合条件的工单"), key + ": " + status.text):
		return false
	var numbers := []
	for index in results.item_count:
		numbers.append(results.get_item_metadata(index))
	observations[key] = numbers
	return require(PackedInt64Array(numbers) == PackedInt64Array(expected), "%s: %s, expected %s" % [key, numbers, expected])


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var palette := EditorInterface.get_command_palette()
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var box := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var commands := palette.find_children("*", "Tree", true, false).front() as Tree
	box.text = "editor/open_ai_workbench"
	box.text_changed.emit(box.text)
	if not require(commands.get_selected().get_metadata(0) == box.text, "open sidebar command missing"):
		return
	commands.item_activated.emit()
	await process_frame
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	view = session.get_node_or_null("WorkbenchIssueSearch")
	if not require(view != null, "search control not mounted"):
		return
	var open: Button = view.get_node("OpenIssueSearch")
	if not require(await wait_for(func(): return not open.disabled) and open.is_visible_in_tree(), "session unavailable"):
		return
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("I11_FIXTURE"))
	modules = view.find_child("IssueSearchModule", true, false)
	assignee = view.find_child("IssueSearchAssignee", true, false)
	states = view.find_child("IssueSearchState", true, false)
	keyword = view.find_child("IssueSearchKeyword", true, false)
	search = view.find_child("SearchIssues", true, false)
	results = view.find_child("IssueSearchResults", true, false)
	status = view.find_child("IssueSearchStatus", true, false)
	open.pressed.emit()
	if not await observed("initial", fixture.visible):
		return
	for module in ["left", "right"]:
		select_value(modules, fixture[module])
		assignee.text = fixture.owner_name
		select_value(states, "planned")
		keyword.text = fixture.keyword
		search.pressed.emit()
		if not await observed(module, [fixture[module + "_number"]]):
			return
		if not require(results.get_item_text(0).contains(fixture.title), "same-title row label missing"):
			return
		if module == "left":
			results.item_activated.emit(0)
		else:
			results.select(0)
			results.item_selected.emit(0)
			var open_selected := view.find_child("OpenSearchResult", true, false) as Button
			if not require(not open_selected.disabled, "selected issue cannot be opened"):
				return
			open_selected.pressed.emit()
		var detail: Node = session.get_node("WorkbenchIssueDetail")
		if not require(await wait_for(func(): return detail.get_detail().get("id") == fixture[module + "_id"]), "detail ID mismatch"):
			return
		if not require(detail.get_detail().module_id == fixture[module], "detail module mismatch"):
			return
		observations[module + "_detail_id"] = detail.get_detail().id
		open.pressed.emit()
		if not await observed("reopened", fixture.visible):
			return
	select_value(modules, fixture.left)
	assignee.text = fixture.owner_id
	select_value(states, "done")
	keyword.text = fixture.keyword
	search.pressed.emit()
	if not await observed("empty", []):
		return
	var clear := view.find_child("ClearIssueFilters", true, false) as Button
	if not require(clear.is_visible_in_tree() and not clear.disabled, "empty state lacks clear"):
		return
	clear.pressed.emit()
	if not await observed("cleared", fixture.visible):
		return
	if not require(modules.selected == 0 and states.selected == 0 and assignee.text.is_empty() and keyword.text.is_empty(), "clear retained filters"):
		return
	keyword.text = "legacy-filter"
	search.pressed.emit()
	if not require(await wait_for(func(): return status.text.contains("请更新天璇服务")) and results.item_count == 0, "legacy unfiltered reply displayed"):
		return
	observations["legacy_feedback"] = status.text
	keyword.text = "slow-request"
	search.pressed.emit()
	if not require(await wait_for(func(): return FileAccess.file_exists("res://slow-started")), "delayed request never started"):
		return
	session.find_child("SignOut", true, false).pressed.emit()
	await create_timer(1.5).timeout
	if not require(open.disabled and results.item_count == 0 and not results.is_visible_in_tree() and status.text.is_empty(), "old identity repopulated results"):
		return
	print("I11_REPORT=" + JSON.stringify(observations))
	quit(0)
