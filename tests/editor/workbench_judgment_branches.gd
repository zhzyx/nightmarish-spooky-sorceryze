extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var detail := session.get_node("WorkbenchIssueDetail")
	var widget := detail.get_node("creative_judgments")
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "identity missing"):
		return
	widget.browse.pressed.emit()
	if not require(await wait_for(func(): return widget.rows.get_child_count() == 2), "drafts missing"):
		return
	var revision := OS.get_environment("H06_REVISION")
	for row: Button in widget.rows.get_children():
		if revision in row.tooltip_text:
			row.pressed.emit()
			break
	if not require(await wait_for(func(): return widget.panel.visible and widget.selected.get("revision") == revision), "draft revision mismatch"):
		return
	widget.note.text = "选定此版动作"
	widget.approve.pressed.emit()
	widget.approve.pressed.emit()
	if not require(await wait_for(func(): return "签认人" in widget.status.text), "missing decision receipt"):
		return
	print("H06_DECISION=" + widget.status.text.split("\n")[0])
	quit(0)
