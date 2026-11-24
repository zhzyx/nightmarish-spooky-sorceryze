extends SceneTree

var session: Node
var detail: Node
var panel: Control
var status: Label
var list: ItemList
var add: Button
var remove: Button
var refresh: Button
var input: LineEdit


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I04: %s (status: %s)" % [message, status.text if status else "unmounted"])
		quit(1)
	return ok


func wait_for(check: Callable) -> bool:
	var until := Time.get_ticks_msec() + 15000
	while not check.call() and Time.get_ticks_msec() < until:
		await process_frame
	return check.call()


func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var palette := EditorInterface.get_command_palette()
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not require(results.get_selected().get_metadata(0) == search.text, "command not selected"):
		return
	results.item_activated.emit()
	await process_frame
	session = dock.find_child("WorkbenchBusinessSession", true, false)
	detail = dock.find_child("WorkbenchIssueDetail", true, false)
	panel = detail.find_child("issue_dependencies", true, false)
	if not require(panel != null and not panel.visible, "initial empty detail"):
		return
	status = panel.find_child("DependencyStatus", true, false)
	list = panel.find_child("DependencyList", true, false)
	input = panel.find_child("DependencyNumber", true, false)
	add = panel.find_child("AddDependency", true, false)
	remove = panel.find_child("RemoveDependency", true, false)
	refresh = panel.find_child("RefreshDependencies", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "sign in"):
		return
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("I04_ISSUES"))
	await detail.open_issue(int(fixture.downstream))
	if not require(await wait_for(func(): return panel.is_visible_in_tree() and status.text == "尚未登记上游"), "read dependencies"):
		return
	var route := "/api/v1/issues/%s/work/flow" % str(detail.get_detail().id).uri_encode()
	# Emulate an edit from a second client after the panel read version zero.
	var external: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/dependencies", {
		"expected_version": 0, "dependencies": [fixture.other], "call_id": "other-client"
	})
	if not require(external.status == 200, "concurrent writer"):
		return
	input.text = str(int(fixture.upstream))
	add.pressed.emit()
	if not require(await wait_for(func(): return "版本已变化" in status.text and list.item_count == 1), "stale edit readback"):
		return
	if not require(list.get_item_metadata(0) == fixture.other, "concurrent dependency preserved"):
		return
	list.select(0)
	list.item_selected.emit(0)
	remove.pressed.emit()
	if not require(await wait_for(func(): return status.text == "尚未登记上游"), "remove selected"):
		return
	input.text = str(int(fixture.upstream))
	add.pressed.emit()
	if not require(await wait_for(func(): return status.text == "1 项上游尚未验收" and list.item_count == 1), "add produced prerequisite"):
		return
	var blocked_row := list.get_item_text(0)
	if not require("未验收，阻塞推进" in blocked_row, "visible blocker"):
		return
	input.text = str(int(fixture.upstream))
	add.pressed.emit()
	if not require(await wait_for(func(): return "重复" in status.text), "duplicate"):
		return
	var blocked: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/advance", {
		"expected_version": 3, "to_status": "in-progress", "call_id": "before-acceptance"
	})
	if not require(blocked.status == 409 and blocked.data.get("detail") == "prerequisite has not been accepted", "blocked advance"):
		return
	var until := Time.get_ticks_msec() + 15000
	while status.text != "全部上游已验收" and Time.get_ticks_msec() < until:
		refresh.pressed.emit()
		await wait_for(func(): return not refresh.disabled)
		await create_timer(0.1).timeout
	if not require(status.text == "全部上游已验收" and list.item_count == 1, "accepted upstream refresh"):
		return
	var accepted_row := list.get_item_text(0)
	var advanced: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/advance", {
		"expected_version": 3, "to_status": "in-progress", "call_id": "after-acceptance"
	})
	if not require(advanced.status == 200 and advanced.data.get("status") == "in-progress", "advance accepted work"):
		return
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(not panel.visible and list.item_count == 0 and status.text.is_empty() and input.text.is_empty(), "clear on logout"):
		return
	print("I04_REPORT=" + JSON.stringify({"blocked_row": blocked_row, "accepted_row": accepted_row, "before": blocked.status, "after": advanced.status}))
	quit(0)
