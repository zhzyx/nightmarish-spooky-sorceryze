extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, message: String) -> bool:
	if not ok:
		printerr("I10: " + message)
		quit(1)
	return ok


func wait_for(condition: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()


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
	if not require(results.get_selected().get_metadata(0) == search.text, "command missing"):
		return
	results.item_activated.emit()
	await process_frame
	var view := root.find_child("WorkbenchIssueDetail", true, false)
	var session := view.get_parent()
	var time := view.find_child("WorkbenchIssueTime", true, false)
	if not require(time != null and await wait_for(func(): return not session.get_identity().is_empty()), "editor session missing"):
		return
	var open := view.find_child("OpenIssueDetail", true, false) as Button
	var number := view.find_child("IssueDetailNumber", true, false) as LineEdit
	var read := view.find_child("ReadIssueDetail", true, false) as Button
	var open_time := time.find_child("OpenIssueTime", true, false) as Button
	var estimate := time.find_child("IssueEstimatedMinutes", true, false) as LineEdit
	var actual := time.find_child("IssueActualMinutes", true, false) as LineEdit
	var note := time.find_child("IssueTimeNote", true, false) as LineEdit
	var save := time.find_child("SaveIssueEstimate", true, false) as Button
	var log_time := time.find_child("LogIssueTime", true, false) as Button
	var status := time.find_child("IssueTimeStatus", true, false) as Label
	var summary := time.find_child("IssueTimeSummary", true, false) as Label
	var records := time.find_child("IssueTimeRecords", true, false) as Label
	open.pressed.emit()
	number.text = OS.get_environment("I10_NUMBER")
	number.text_changed.emit(number.text)
	read.pressed.emit()
	if not require(await wait_for(func(): return open_time.is_visible_in_tree()), "detail missing"):
		return
	open_time.pressed.emit()
	if not require(await wait_for(func(): return save.is_visible_in_tree() and not save.disabled), "work read failed"):
		return
	var report := {"before": summary.text}
	actual.text = "0"
	log_time.pressed.emit()
	if not require(status.text.begins_with("请输入 1 至") and not log_time.disabled, "zero actual minutes accepted"):
		return
	estimate.text = "-1"
	save.pressed.emit()
	if not require(status.text.begins_with("请输入 0 至") and not save.disabled, "negative estimate accepted"):
		return
	estimate.text = "75"
	save.pressed.emit()
	if not require(await wait_for(func(): return status.text == "已保存"), "estimate save failed"):
		return
	actual.text = "12"
	note.text = "核对草图"
	log_time.pressed.emit()
	if not require(await wait_for(func(): return status.text == "已保存"), "first log failed"):
		return
	report["after_first"] = summary.text
	actual.text = "23"
	note.text = "调整模型"
	log_time.pressed.emit()
	if not require(await wait_for(func(): return log_time.text == "重试登记本次工时"), "ambiguous receipt missing"):
		return
	report["ambiguous_status"] = status.text
	if not require(save.disabled and not actual.editable and not note.editable and not log_time.disabled, "retry controls"):
		return
	log_time.pressed.emit()
	if not require(await wait_for(func(): return status.text == "已保存"), "retry failed"):
		return
	report["after_retry"] = [summary.text, records.text]
	open.pressed.emit()
	if not require(not open_time.is_visible_in_tree() and summary.text.is_empty() and records.text.is_empty(), "stale data after closing detail"):
		return
	open.pressed.emit()
	read.pressed.emit()
	if not require(await wait_for(func(): return open_time.is_visible_in_tree()), "reopened detail missing"):
		return
	open_time.pressed.emit()
	if not require(await wait_for(func(): return not log_time.disabled), "reopened time missing"):
		return
	report["reopened"] = [summary.text, records.text]
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(not open_time.is_visible_in_tree() and estimate.text.is_empty() and records.text.is_empty(), "stale data after logout"):
		return
	print("I10_REPORT=" + JSON.stringify(report))
	quit(0)
