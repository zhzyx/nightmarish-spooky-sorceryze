extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	var detail := session.get_node("WorkbenchIssueDetail")
	var widget := detail.get_node("creative_judgments")
	var mode := OS.get_environment("JUDGMENT_MODE")
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("JUDGMENT_FIXTURE"))
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "session missing"):
		return
	widget.browse.pressed.emit()
	if not require(await wait_for(func(): return widget.rows.get_child_count() == fixture.count), "personal list"):
		return
	var report := {"list": [], "actor": session.get_identity().id}
	for row in widget.rows.get_children():
		report.list.append(row.tooltip_text)
	var choice: Button = widget.rows.get_child(int(fixture.index))
	choice.pressed.emit()
	var revision := detail.get_node("issue_revisions")
	if not require(await wait_for(func(): return revision.revision_view.visible and fixture.revision in revision.revision_fields.text and not widget.transfer.disabled), "exact revision or recipient missing"):
		return
	report.revision = revision.revision_fields.text
	report.item = widget.selected.duplicate(true)
	revision.revision_view.hide()
	var comments := detail.find_child("IssueCommentThread", true, false) as ItemList
	if not require(await wait_for(func(): return comments.item_count == 1), "missing prior feedback"):
		return
	report.comment = comments.get_item_metadata(0).body
	report.design = detail.get_detail().design_source
	if mode == "stale":
		var marker := FileAccess.open(fixture.ready, FileAccess.WRITE)
		marker.close()
		if not require(await wait_for(func(): return FileAccess.file_exists(fixture.transferred)), "handoff timed out"):
			return
		widget.approve.pressed.emit()
		if not require(await wait_for(func(): return "已变化" in widget.status.text), "stale decision accepted"):
			return
		report.rejection = widget.status.text
	elif mode == "transfer":
		for i in widget.recipients.item_count:
			if widget.recipients.get_item_metadata(i) == fixture.target:
				widget.recipients.select(i)
		widget.note.text = "请检查旧修订轮廓"
		widget.transfer.pressed.emit()
		if not require(await wait_for(func(): return widget.rows.get_child_count() == 1 and widget.selected.is_empty()), "sender list after handoff"):
			return
		report.after = widget.rows.get_child(0).tooltip_text
	else:
		report.handoff = widget.description.text
		widget.approve.pressed.emit()
		if not require(await wait_for(func(): return widget.rows.get_child_count() == 1 and widget.selected.is_empty()), "recipient list after decision"):
			return
		report.after = widget.rows.get_child(0).tooltip_text
	print("WORKBENCH_REPORT=", JSON.stringify(report))
	quit()
