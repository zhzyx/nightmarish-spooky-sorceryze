extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var detail := dock.find_child("WorkbenchIssueDetail", true, false)
	var widget := detail.find_child("WorkbenchIssueArtifacts", true, false)
	if not require(widget != null and await wait_for(func(): return not session.get_identity().is_empty()), "artifact adapter or identity missing"):
		return
	await detail.open_issue(OS.get_environment("I14_NUMBER").to_int())
	var versions := widget.find_child("IssueArtifactVersions", true, false) as OptionButton
	var save := widget.find_child("SaveIssueArtifact", true, false) as Button
	var picker := widget.find_child("IssueArtifactDestination", true, false) as FileDialog
	var status := widget.find_child("IssueArtifactStatus", true, false) as Label
	if not require(await wait_for(func(): return versions.item_count == 3) and save.is_visible_in_tree(), "expected three saved submissions"):
		return
	var records := []
	for index in [2, 1, 0]:
		versions.select(index)
		versions.item_selected.emit(index)
		save.pressed.emit()
		if not require(picker.visible and picker.current_file == "hero.bin", "save dialog missing filename"):
			return
		var destination := OS.get_environment("I14_OUTPUT").path_join("selected-%d.bin" % index)
		picker.hide()
		picker.file_selected.emit(destination)
		if not require(await wait_for(func(): return status.text != "正在读取所选版本…"), "download timed out"):
			return
		records.append({"reference": versions.get_item_metadata(index), "label": versions.get_item_text(index), "message": status.text})
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(not widget.visible and versions.item_count == 0 and not picker.visible, "logout retained artifact controls"):
		return
	print("WORKBENCH_REPORT=" + JSON.stringify(records))
	quit(0)
