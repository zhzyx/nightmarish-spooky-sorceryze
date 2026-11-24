extends SceneTree

var session: Node
var view: Node
var action: Node
var owner: OptionButton
var stage: OptionButton
var save_owner: Button
var save_stage: Button
var edit: Button
var feedback: Label
var observations := []


func _initialize() -> void:
	run.call_deferred()


func wait_for(condition: Callable, description: String) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if condition.call():
		return true
	printerr("I06 timeout: " + description)
	quit(1)
	return false


func open_properties() -> bool:
	edit.pressed.emit()
	return await wait_for(func(): return not save_owner.disabled and not save_stage.disabled, "editable fields")


func select_stage(value: String) -> bool:
	for index in stage.item_count:
		if stage.get_item_text(index) == value:
			stage.select(index)
			return true
	printerr("I06 missing stage: " + value)
	quit(1)
	return false


func record() -> void:
	var detail: Dictionary = view.get_detail()
	observations.append({"status": detail.status, "owner": detail.assignee.name if detail.assignee else null,
			"visible": view.find_child("IssueDetailFields", true, false).text, "revision": detail.revision})


func run() -> void:
	await create_timer(1).timeout
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if results.get_selected().get_metadata(0) != search.text:
		quit(1)
		return
	results.item_activated.emit()
	await process_frame
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	session = dock.find_child("WorkbenchBusinessSession", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	action = view.find_child("issue_assignment", true, false)
	if not await wait_for(func(): return action != null and not session.get_identity().is_empty(), "session and compiled controls"):
		return
	edit = action.find_child("EditIssueProperties", true, false)
	save_owner = action.find_child("ApplyIssueOwner", true, false)
	save_stage = action.find_child("ApplyIssueStage", true, false)
	owner = action.find_child("IssueOwnerChoice", true, false)
	stage = action.find_child("IssueStageChoice", true, false)
	feedback = action.find_child("IssuePropertyFeedback", true, false)
	await view.open_issue(int(OS.get_environment("I06_NUMBER")))
	if not edit.is_visible_in_tree():
		quit(1)
		return
	record()
	var mode := OS.get_environment("I06_MODE")
	if mode == "write":
		if not await open_properties():
			return
		var found := false
		for index in owner.item_count:
			if owner.get_item_metadata(index) == OS.get_environment("I06_ASSIGNEE"):
				found = true
				owner.select(index)
		if not found:
			printerr("assignee missing")
			quit(1)
			return
		save_owner.pressed.emit()
		if not await wait_for(func(): return view.get_detail().get("assignee") is Dictionary, "assignee readback"):
			return
		record()
		if not await open_properties() or not select_stage("planned"):
			return
		save_stage.pressed.emit()
		if not await wait_for(func(): return view.get_detail().get("status") == "planned", "status readback"):
			return
		record()
	elif mode == "acl":
		if not await open_properties():
			return
		owner.select(0)
		save_owner.pressed.emit()
		if not await wait_for(func(): return feedback.text == "没有权限修改此工单", "owner denied"):
			return
		await view.open_issue(int(OS.get_environment("I06_NUMBER")))
		if not await open_properties() or not select_stage("in-progress"):
			return
		save_stage.pressed.emit()
		if not await wait_for(func(): return feedback.text == "没有权限修改此工单", "status denied"):
			return
		await view.open_issue(int(OS.get_environment("I06_NUMBER")))
		record()
	else:
		edit.pressed.emit()
		if feedback.text != "当前账号仅可查看工单" or not save_owner.disabled or not save_stage.disabled or not owner.disabled or not stage.disabled:
			quit(1)
			return
	session.find_child("SignOut", true, false).pressed.emit()
	if action.visible or owner.item_count or stage.item_count or not view.get_detail().is_empty():
		quit(1)
		return
	print("I06_REPORT=" + JSON.stringify(observations))
	quit(0)
