extends "res://workbench_issue_detail.gd"

var panel: Node
var dialog: AcceptDialog
var receipt: TextEdit


func choose(control: OptionButton, value: Variant) -> bool:
	for index in control.item_count:
		if control.get_item_metadata(index) == value:
			control.select(index)
			control.item_selected.emit(index)
			var finished := await wait_for(func(): return not panel.busy)
			control.get_popup().hide()
			return require(finished and control.get_item_metadata(control.selected) == value, "Selection failed: " + panel.feedback.text)
	return require(false, "Missing choice: " + str(value))


func capture(button: Button) -> String:
	if not require(button.is_visible_in_tree() and not button.disabled, "Cannot open " + str(button.name)):
		return ""
	button.pressed.emit()
	if not require(await wait_for(func(): return dialog.visible and receipt.is_visible_in_tree() and not receipt.text.is_empty() and receipt.text != "正在读取运行进度…"), "No visible progress"):
		return ""
	return receipt.text


func run() -> void:
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("S07_TASK"))
	var dock := await open_workbench()
	if dock == null:
		return
	panel = dock.find_child("WorkbenchBusinessModules", true, false)
	if not require(await wait_for(func(): return panel.managed_identity and not panel.session.get_identity().is_empty()), "Sign-in failed"):
		return
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	dialog = view.find_child("TaskProgressDialog", true, false)
	if not require(dialog != null, "Run progress control missing"):
		return
	receipt = dialog.find_child("TaskProgressReceipt", true, false)
	var module_button := panel.find_child("OpenModuleTaskProgress", true, false) as Button
	var issue_button := view.find_child("OpenIssueTaskProgress", true, false) as Button
	panel.picker.item_selected.emit(1)
	if not require(await wait_for(func(): return not panel.busy), "Could not list modules"):
		return
	panel.picker.get_popup().hide()
	if not await choose(panel.picker, "default") or not await choose(panel.issues, fixture.issue):
		return
	var running_module := await capture(module_button)
	if not require(fixture.run in running_module and "workspace.materialize" in running_module, "Module running receipt: " + running_module):
		return
	dialog.hide()
	view.find_child("OpenIssueDetail", true, false).pressed.emit()
	var field := view.find_child("IssueDetailNumber", true, false) as LineEdit
	field.text = str(int(fixture.number))
	field.text_changed.emit(field.text)
	view.find_child("ReadIssueDetail", true, false).pressed.emit()
	if not require(await wait_for(func(): return view.get_detail().get("id") == fixture.issue), "Issue unavailable"):
		return
	var running_issue := await capture(issue_button)
	if not require(running_module == running_issue, "Entries disagree on running task"):
		return
	var signal_file := FileAccess.open(fixture.release, FileAccess.WRITE)
	if not require(signal_file != null, "Cannot release fixture process"):
		return
	signal_file.close()
	if not require(await wait_for(func(): return FileAccess.file_exists(fixture.settled)), "Fixture process did not settle"):
		return
	var final_issue := await capture(dialog.find_child("RefreshTaskProgress", true, false))
	dialog.hide()
	dock.find_child("ExpandWorkbench", true, false).pressed.emit()
	await process_frame
	var restore := root.find_child("RestoreWorkbenchSidebar", true, false) as Button
	if not require(restore.is_visible_in_tree(), "Full workbench did not open"):
		return
	var final_module := await capture(module_button)
	if not require(final_module == final_issue and final_module != running_module and "process.closed" in final_module, "Latest receipt mismatch: " + final_module):
		return
	dialog.hide()
	restore.pressed.emit()
	await process_frame
	if not await choose(panel.issues, fixture.sibling):
		return
	var empty := await capture(module_button)
	if not require(empty == "当前没有可读取的运行记录", "Previous task leaked into sibling: " + empty):
		return
	panel.session.find_child("SignOut", true, false).pressed.emit()
	if not require(not dialog.visible and receipt.text.is_empty(), "Signed-out progress remained visible"):
		return
	print("S07_NATIVE=" + JSON.stringify({"running_module": running_module, "running_issue": running_issue, "final_module": final_module, "final_issue": final_issue, "sibling": empty}))
	quit(0)
