extends SceneTree

var detail: Node
var iteration: LineEdit
var milestone: LineEdit
var counts: Label
var save: Button
var status: Label


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I07: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


func read_issue(number: int) -> bool:
	var field := detail.find_child("IssueDetailNumber", true, false) as LineEdit
	field.text = str(number)
	field.text_changed.emit(field.text)
	if not require(not counts.is_visible_in_tree() and counts.text == "" and iteration.text == "" and milestone.text == "" and save.disabled, "stale detail after changing number"):
		return false
	detail.find_child("ReadIssueDetail", true, false).pressed.emit()
	return require(await wait_for(func(): return iteration.editable) and counts.is_visible_in_tree(), "read failed: " + status.text)


func observed() -> Dictionary:
	return {"iteration": iteration.text, "milestone": milestone.text, "counts": counts.text}


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
	detail = root.find_child("WorkbenchIssueDetail", true, false)
	var plan := detail.get_node("WorkbenchIssueMilestone")
	if not require(plan != null, "plan controls missing from detail"):
		return
	iteration = plan.find_child("IssueIteration", true, false)
	milestone = plan.find_child("IssueMilestone", true, false)
	counts = plan.find_child("IssuePlanCounts", true, false)
	save = plan.find_child("SaveIssueMilestone", true, false)
	status = plan.find_child("IssueMilestoneStatus", true, false)
	var session := detail.get_parent()
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "session not ready"):
		return
	detail.find_child("OpenIssueDetail", true, false).pressed.emit()
	var numbers: Array = JSON.parse_string(OS.get_environment("I07_NUMBERS"))
	var before := []
	for number in numbers:
		if not await read_issue(int(number)):
			return
		before.append(observed())
	if not await read_issue(int(numbers.front())):
		return
	iteration.text = "第二轮"
	iteration.text_changed.emit(iteration.text)
	milestone.text = "发布"
	milestone.text_changed.emit(milestone.text)
	if not require(not save.disabled and save.is_visible_in_tree(), "cannot save"):
		return
	save.pressed.emit()
	if not require(await wait_for(func(): return iteration.editable) and status.text == "已保存并读取当前计划" and save.disabled, "save readback failed: " + status.text):
		return
	var saved := observed()
	var after := []
	for number in numbers:
		if not await read_issue(int(number)):
			return
		after.append(observed())
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(not plan.visible and counts.text.is_empty() and iteration.text.is_empty() and save.disabled, "logout retained plan"):
		return
	print("I07_REPORT=" + JSON.stringify({"before": before, "saved": saved, "after": after}))
	quit(0)
