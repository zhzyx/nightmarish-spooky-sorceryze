extends SceneTree

var detail: Node
var session: Node
var view: Node
var open: Button
var field: OptionButton
var value: LineEdit
var stage: OptionButton
var save: Button
var advance: Button
var message: Label


func _initialize() -> void:
	run.call_deferred()


func require(ok: bool, note: String) -> bool:
	if not ok:
		printerr("I09: " + note + (" · " + message.text if message else ""))
		quit(1)
	return ok


func wait_for(test: Callable) -> bool:
	var until := Time.get_ticks_msec() + 15000
	while not test.call() and Time.get_ticks_msec() < until:
		await process_frame
	return test.call()


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
	if not require(results.get_selected().get_metadata(0) == search.text, "palette command missing"):
		return
	results.item_activated.emit()
	await process_frame
	session = root.find_child("WorkbenchBusinessSession", true, false)
	detail = session.find_child("WorkbenchIssueDetail", true, false)
	view = detail.get_node_or_null("WorkbenchIssueCustomFields")
	if not require(view != null and await wait_for(func(): return not session.get_identity().is_empty()), "session or detail attachment missing"):
		return
	open = view.find_child("OpenIssueCustomFields", true, false)
	field = view.find_child("IssueProjectField", true, false)
	value = view.find_child("IssueFieldValue", true, false)
	stage = view.find_child("IssueFlowStage", true, false)
	save = view.find_child("SaveIssueField", true, false)
	advance = view.find_child("AdvanceIssueStage", true, false)
	message = view.find_child("IssueFieldMessage", true, false)
	var samples: Array = JSON.parse_string(OS.get_environment("I09_CASES"))
	var observed := []
	for index in samples.size():
		var sample: Dictionary = samples[index]
		if index:
			session.find_child("ChooseAccount", true, false).pressed.emit()
			session.find_child("AccountSecret", true, false).text = OS.get_environment("TIANXUAN_TOKEN")
			session.find_child("BusinessProject", true, false).text = sample.project
			session.find_child("Authenticate", true, false).pressed.emit()
			if not require(not view.visible and field.item_count == 0 and value.text.is_empty(), "old project values retained"):
				return
			if not require(await wait_for(func(): return session.get_identity().get("project") == sample.project), "project switch"):
				return
		await detail.open_issue(int(sample.number))
		if not require(open.is_visible_in_tree(), "field action missing"):
			return
		open.pressed.emit()
		if not require(await wait_for(func(): return value.editable), "project field load"):
			return
		if not require(field.item_count == 1 and field.get_item_text(0) == sample.label and value.text == sample.old, "project isolation"):
			return
		if not require(stage.item_count == 2 and stage.get_item_metadata(1) == sample.target, "stage edges mismatch"):
			return
		value.text = sample.new
		value.text_changed.emit(value.text)
		if not require(not save.disabled and advance.disabled, "field edit unavailable"):
			return
		save.pressed.emit()
		if not require(await wait_for(func(): return message.text == "已保存字段"), "missing plan receipt"):
			return
		stage.select(1)
		stage.item_selected.emit(1)
		if not require(not advance.disabled, "stage cannot advance"):
			return
		advance.pressed.emit()
		if not require(await wait_for(func(): return detail.get_detail().get("status") == sample.target), "I02 did not refresh its stage"):
			return
		open.pressed.emit()
		if not require(await wait_for(func(): return value.editable) and value.text == sample.new and stage.get_item_text(0) == "当前阶段　" + sample.target, "authority readback"):
			return
		observed.append({"project": sample.project, "field": field.get_item_text(0), "value": value.text, "stage": detail.get_detail().status})
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(not view.visible and value.text.is_empty() and field.item_count == 0 and stage.item_count == 0, "logout retained values"):
		return
	print("I09_REPORT=" + JSON.stringify(observed))
	quit(0)
