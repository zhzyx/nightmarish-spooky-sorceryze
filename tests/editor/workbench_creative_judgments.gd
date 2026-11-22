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
		var assets := detail.get_node("WorkbenchIssueArtifacts")
		if not require(await wait_for(func(): return not assets.compare.disabled), "comparison entry"):
			return
		assets.compare.pressed.emit()
		if not require(assets.comparison.visible and "不同" in assets.difference.text and assets.design.visible, "design or difference missing"):
			return
		report.comparison = []
		for index in 2:
			var column: Node = assets.sides.get_child(index)
			var open: Button = column.get_child(2)
			open.pressed.emit()
			if not require(await wait_for(func(): return assets.previews[index].texture != null), "original preview "+str(index)):
				return
			if not require(index == 1 or assets.previews[1].texture == null, "opening A targeted B"):
				return
			var original: String = assets.content[index].text
			var output := OS.get_environment("JUDGMENT_EXPORT").path_join("original%d.png" % index)
			column.get_child(3).pressed.emit()
			assets.destinations[index].file_selected.emit(output)
			assets.destinations[index].hide()
			if not require(await wait_for(func(): return FileAccess.file_exists(output)), "full original not saved"):
				return
			if not require(FileAccess.get_sha256(output) == fixture.digests[index], "saved other original"):
				return
			report.comparison.append({"field": assets.fields[index].text, "original": original, "saved_sha256": FileAccess.get_sha256(output), "design": assets.design.text, "color": assets.previews[index].texture.get_image().get_pixel(0, 0).to_html(false)})
		assets.sides.get_child(1).get_node("ReviewCandidate").pressed.emit()
		if not require(await wait_for(func(): return int(widget.selected.get("submission_version", 0)) == 2), "second candidate was not selected"):
			return
		report.switched = widget.description.text
		assets.compare.pressed.emit()
		assets.sides.get_child(0).get_node("ReviewCandidate").pressed.emit()
		if not require(await wait_for(func(): return int(widget.selected.get("submission_version", 0)) == 1 and not widget.transfer.disabled), "first candidate was not restored"):
			return
		for i in widget.recipients.item_count:
			if widget.recipients.get_item_metadata(i) == fixture.target:
				widget.recipients.select(i)
		widget.note.text = "请检查旧修订轮廓"
		widget.transfer.pressed.emit()
		if not require(await wait_for(func(): return widget.rows.get_child_count() == 1 and widget.selected.is_empty()), "sender list after handoff"):
			return
		report.after = widget.rows.get_child(0).tooltip_text
	else:
		var assets := detail.get_node("WorkbenchIssueArtifacts")
		if not require(await wait_for(func(): return not assets.compare.disabled), "missing comparison"):
			return
		report.handoff = widget.description.text
		var accepting := mode == "recipient"
		var target_side := 0 if accepting else 1
		assets.compare.pressed.emit()
		assets.sides.get_child(1 - target_side).get_node("ReviewCandidate").pressed.emit()
		var other_status := "待 " if accepting else "已采纳"
		if not require(await wait_for(func(): return other_status in widget.status.text and widget.selected.is_empty()), "other signing authority"):
			return
		report.other = widget.status.text
		assets.compare.pressed.emit()
		assets.sides.get_child(target_side).get_node("ReviewCandidate").pressed.emit()
		if not require(await wait_for(func(): return widget.selected.get("revision") == fixture.revision and widget.panel.visible), "comparison chose wrong version"):
			return
		report.target = widget.description.text
		widget.note.text = "采纳原始轮廓" if accepting else "请调整对比度"
		var button: Button = widget.approve if accepting else widget.revise
		button.pressed.emit()
		button.pressed.emit()
		if not require(await wait_for(func(): return "签认人" in widget.status.text and widget.selected.is_empty()), "missing signature receipt"):
			return
		report.receipt = widget.status.text
		if accepting:
			if not require(widget.rows.get_child_count() == 1, "recipient list after decision"):
				return
			report.after = widget.rows.get_child(0).tooltip_text
		else:
			if not require(widget.rows.get_child_count() == 0, "returned candidate still pending"):
				return
	print("WORKBENCH_REPORT=", JSON.stringify(report))
	quit()
