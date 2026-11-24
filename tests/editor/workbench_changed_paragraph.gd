extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "identity"):
		return
	var docs := session.get_node("WorkbenchDocuments")
	var history := session.get_node("WorkbenchDocumentHistory")
	var id := OS.get_environment("V02_DOC")
	await docs.open_document(id, 2, 1)
	docs.history.pressed.emit()
	if not require(await wait_for(func(): return history.changes.get_child_count() == 1), "expected one changed paragraph"):
		return
	var row: Button = history.changes.get_child(0)
	var report := {"label": row.text, "action": row.tooltip_text, "highlighted": row.has_theme_color_override("font_color"), "diff": history.diff.text}
	var colored_lines := []
	for line in history.diff.get_line_count():
		if history.diff.get_line_background_color(line).a > 0:
			colored_lines.append(history.diff.get_line(line))
	report.colored_lines = colored_lines
	if not require(colored_lines == ["-白色灯塔", "+蓝色灯塔"], "historical diff did not highlight only the change"):
		return
	if not require(report.highlighted and "v2 第 2 段" in row.text and row.tooltip_text == "编辑此段", "highlight or edit target"):
		return
	row.pressed.emit()
	if not require(await wait_for(func(): return docs.composer.visible and docs.draft_body.has_selection()), "editable selection"):
		return
	report.selection = docs.draft_body.get_selected_text()
	report.reference = docs.reference.duplicate()
	if not require(docs.draft_body.editable and report.selection == "蓝色灯塔\n保留灯光", "wrong selected text"):
		return
	docs.draft_body.insert_text_at_caret("海岸灯塔\n调高灯光")
	docs.composer.confirmed.emit()
	if not require(await wait_for(func(): return docs.reference.get("version") == 3), "save confirmation"):
		return
	report.saved = docs.raw_body
	print("WORKBENCH_REPORT=", JSON.stringify(report))
	quit()
