extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if not dock:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "account"):
		return
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	var doc := session.get_node("WorkbenchDocuments")
	var suggestion := doc.get_node("WorkbenchParagraphSuggestion")
	var history := session.get_node("WorkbenchDocumentHistory")
	var base := "目标：保持剪影\n\n步伐：两拍\n\n镜头不动"
	doc.create.pressed.emit()
	doc.draft_title.text = "过桥"
	doc.draft_body.text = base
	doc.composer.get_ok_button().pressed.emit()
	if not require(await wait_for(func(): return doc.reference.get("version") == 1 and doc.raw_body == base), "create"):
		return
	var id: String = doc.reference.document_id
	doc.paragraphs.select(1)
	doc.paragraphs.item_selected.emit(1)
	await process_frame
	suggestion.open_button.pressed.emit()
	suggestion.instruction.text = "补充第二拍的落点"
	suggestion.instruction.text_changed.emit(suggestion.instruction.text)
	suggestion.generate.pressed.emit()
	if not require(await wait_for(func(): return suggestion.visible and not suggestion.get_ok_button().disabled), "candidate: " + suggestion.status.text + " / " + doc.status.text):
		return
	suggestion.get_ok_button().pressed.emit()
	var expanded := base.replace("两拍", "两拍，第二拍落在桥面中心")
	if not require(await wait_for(func(): return doc.reference.get("version") == 2 and doc.raw_body == expanded), "AI save"):
		return
	doc.edit.pressed.emit()
	doc.draft_body.text = expanded.replace("镜头不动", "镜头保持三秒")
	doc.composer.get_ok_button().pressed.emit()
	if not require(await wait_for(func(): return doc.reference.get("version") == 3), "author save"):
		return
	var seen := []
	doc.history.pressed.emit()
	if not require(await wait_for(func(): return history.dialog.visible and history.changes.get_child_count() == 1), "open diff"):
		return
	for pair: Array in [[1, 2, 2], [2, 3, 3]]:
		history.source.select(history.source.get_item_index(pair[0]))
		history.comparison.select(history.comparison.get_item_index(pair[1]))
		history.comparison.item_selected.emit(history.comparison.selected)
		var location := "第 %d 段" % pair[2]
		if not require(await wait_for(func(): return history.changes.get_child_count() == 1 and location in history.changes.get_child(0).text), "wrong changed paragraph"):
			return
		seen.append({"from": pair[0], "to": pair[1], "row": history.changes.get_child(0).text, "diff": history.diff.text})
	print("Q14=", JSON.stringify({"id": id, "diffs": seen, "final": doc.raw_body}))
	quit()
