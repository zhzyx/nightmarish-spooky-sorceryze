extends "res://edits.gd"


func select_version(control: OptionButton, version: int) -> void:
	var index := control.get_item_index(version)
	control.select(index)
	control.item_selected.emit(index)


func exercise(scene, view, other: Dictionary) -> bool:
	tree = scene
	var widget = view.session.get_node("WorkbenchDocumentHistory")
	var id: String = view.reference.document_id
	view.history.pressed.emit()
	if not await wait_for(func(): return not widget.restore.disabled, "History did not load v1 vs v2"):
		return false
	if not scene.check(widget.restore.text == "将 v1 恢复为新修订 v3", "Restore action did not identify source and new revision"):
		return false
	var initial_diff: String = widget.diff.text
	if not scene.check(initial_diff.contains("--- v1") and initial_diff.contains("+++ v2") and initial_diff.contains("+第三段 · 复审") and not widget.diff.editable, "Expected service diff missing"):
		return false
	select_version(widget.source, 2)
	select_version(widget.comparison, 1)
	if not await wait_for(func(): return widget.diff.text.contains("-第三段 · 复审"), "Reverse diff missing"):
		return false
	if not scene.check(widget.restore.disabled, "Historical comparison allowed stale restore"):
		return false
	select_version(widget.source, 1)
	select_version(widget.comparison, 2)
	if not await wait_for(func(): return not widget.restore.disabled, "Current comparison unavailable"):
		return false
	widget.restore.pressed.emit()
	widget.restore.pressed.emit()
	if not await wait_for(func(): return widget.status.text.contains("回执待确认"), "Lost response did not offer retry"):
		return false
	if not scene.check(widget.source.disabled and widget.comparison.disabled and not widget.restore.disabled, "Retry changed its inputs"):
		return false
	widget.restore.pressed.emit()
	if not await wait_for(func(): return view.reference.get("version") == 3, "Restored revision not loaded"):
		return false
	var chain := []
	for version in [1, 2, 3]:
		view.history.pressed.emit()
		if not await wait_for(func(): return widget.source.item_count == 3, "Full version list missing"):
			return false
		select_version(widget.source, version)
		widget.read.pressed.emit()
		if not await wait_for(func(): return view.reference.get("version") == version and not widget.dialog.visible, "Revision could not be opened"):
			return false
		chain.append({"version": version, "body": view.body.text})
	await view.open_document(other.id, other.version, 1)
	view.history.pressed.emit()
	if not await wait_for(func(): return not widget.restore.disabled, "Stale-version fixture missing"):
		return false
	widget.restore.pressed.emit()
	if not await wait_for(func(): return widget.status.text.contains("文档已更新"), "Restore conflict missing"):
		return false
	if not scene.check(widget.restore.disabled, "Stale restore still enabled"):
		return false
	widget.dialog.get_ok_button().pressed.emit()
	print("D06_CHECKS=", JSON.stringify({"document_id": id, "revisions": chain, "diff": initial_diff}))
	return true
