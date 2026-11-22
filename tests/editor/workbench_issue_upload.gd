extends "res://workbench_issue_detail.gd"

var upload: Button
var source: FileDialog
var versions: OptionButton
var status: Label


func choose(directory: String) -> bool:
	if not require(not upload.disabled and upload.is_visible_in_tree(), "upload control unavailable"):
		return false
	upload.pressed.emit()
	if not require(source.visible and source.file_mode == FileDialog.FILE_MODE_OPEN_FILE, "single-file picker missing"):
		return false
	source.current_dir = directory
	var ready := await wait_for(func(): return not file_item(source, "角色.bin").is_empty())
	if not require(ready, "source filename missing in picker"):
		return false
	var item := file_item(source, "角色.bin")
	var list: ItemList = item.list
	list.select(item.index)
	list.item_selected.emit(item.index)
	if not require(source.current_file == "角色.bin" and not source.get_ok_button().disabled, "file selection mismatch"):
		return false
	source.get_ok_button().pressed.emit()
	return require(not source.visible, "file picker did not confirm")


func file_item(dialog: FileDialog, filename: String) -> Dictionary:
	for list: ItemList in dialog.find_children("*", "ItemList", true, false):
		for index in list.item_count:
			var entry: Variant = list.get_item_metadata(index)
			if entry is Dictionary and entry.get("name") == filename and not entry.get("dir", true):
				return {"list": list, "index": index}
	return {}


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var detail := dock.find_child("WorkbenchIssueDetail", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "session not ready"):
		return
	await detail.open_issue(OS.get_environment("I18_NUMBER").to_int())
	upload = detail.find_child("UploadIssueArtifact", true, false)
	source = detail.find_child("IssueArtifactSource", true, false)
	versions = detail.find_child("IssueArtifactVersions", true, false)
	status = detail.find_child("IssueArtifactStatus", true, false)
	var save := detail.find_child("SaveIssueArtifact", true, false) as Button
	var destination := detail.find_child("IssueArtifactDestination", true, false) as FileDialog
	if not require(upload != null and await wait_for(func(): return not upload.disabled), "upload capability missing"):
		return
	var base := OS.get_environment("I18_BASE")
	var original := base.path_join("first")
	if not await choose(original):
		return
	if not require(await wait_for(func(): return status.text.begins_with("尚未收到上传回执")), "missing uncertain receipt feedback"):
		return
	var retry_feedback := status.text
	var selections := []
	for step: Array in [["first", 1], ["first", 1], ["second", 2], ["first", 2]]:
		if not await choose(base.path_join(step[0])):
			return
		if not require(await wait_for(func(): return not upload.disabled and versions.item_count == step[1]), "upload readback timeout: " + status.text):
			return
		var ref: Dictionary = versions.get_item_metadata(versions.selected)
		if not require(ref.digest in status.text and ref.digest in versions.tooltip_text and str(ref.revision) in versions.tooltip_text, "incomplete visible pointer"):
			return
		selections.append(ref)
	var downloads := []
	for index in versions.item_count:
		versions.select(index)
		versions.item_selected.emit(index)
		var ref: Dictionary = versions.get_item_metadata(index)
		save.pressed.emit()
		if not require(destination.visible and destination.current_file == "角色.bin", "missing save destination"):
			return
		destination.current_path = base.path_join("saved-%d.bin" % int(ref.version))
		destination.get_ok_button().pressed.emit()
		if not require(await wait_for(func(): return status.text.begins_with("已保存所选版本")), "save failed: " + status.text):
			return
		downloads.append({"version": ref.version, "message": status.text})
	session.find_child("SignOut", true, false).pressed.emit()
	if not require(versions.item_count == 0 and not upload.is_visible_in_tree() and not source.visible, "logout retained upload"):
		return
	print("WORKBENCH_REPORT=" + JSON.stringify({"retry_feedback": retry_feedback, "selections": selections, "downloads": downloads}))
	quit(0)
