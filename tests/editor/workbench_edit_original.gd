extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if not dock:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var detail := dock.find_child("WorkbenchIssueDetail", true, false)
	var widget := detail.get_node("creative_judgments")
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "identity missing"):
		return
	widget.browse.pressed.emit()
	if not require(await wait_for(func(): return widget.rows.get_child_count() == 1), "initial list"):
		return
	widget.rows.get_child(0).pressed.emit()
	if not require(await wait_for(func(): return not widget.selected.is_empty()), "initial judgment"):
		return
	var before: Dictionary = widget.selected.duplicate(true)
	detail.get_node("issue_revisions").revision_view.hide()
	widget.edit_original.pressed.emit()
	if not require(await wait_for(func(): return widget.save_original.visible), "native original editor: " + widget.status.text):
		return
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	if not require(code != null and "#ff0000" in code.text, "SVG source missing from native CodeEdit"):
		return
	var editor_class := code.get_class()
	code.set_line(0, code.get_line(0).replace("#ff0000", "#0000ff"))
	EditorInterface.get_script_editor().save_current_script()
	var saved := FileAccess.get_file_as_bytes(widget.local_original)
	widget.save_original.pressed.emit()
	if not require(await wait_for(func(): return not widget.selected.is_empty() and widget.selected.revision != before.revision), "return to new judgment: " + widget.status.text):
		return
	if not require(await wait_for(func(): return "已保存并返回" in widget.status.text) and not detail.get_node("issue_revisions").revision_view.visible, "return covered by another window"):
		return
	var after: Dictionary = widget.selected.duplicate(true)
	if not require(widget.rows.get_child_count() == 1 and widget.panel.visible and not widget.save_original.visible and after.issue_id == before.issue_id, "return selected another issue"):
		return
	print("WORKBENCH_REPORT=", JSON.stringify({"before": before, "after": after, "saved_source": saved.get_string_from_utf8(), "editor": editor_class, "display_server": DisplayServer.get_name(), "description": widget.description.text}))
	quit()
