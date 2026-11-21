extends RefCounted

var tree: SceneTree

func wait_for(test: Callable, description: String) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not test.call() and Time.get_ticks_msec() < deadline:
		await tree.process_frame
	if not test.call():
		push_error(description)
		return false
	return true

func run(scene, view, opener: Button, author: String) -> bool:
	tree = scene
	var first := "设定与目标\n保留换行\n\n第二段 · 手写"
	var revised := first + "\n\n第三段 · 复审"
	var save: Button = view.composer.get_ok_button()
	view.create.pressed.emit()
	if not scene.check(view.composer.visible and view.draft_title.visible and view.draft_body.editable, "New design composer unavailable"):
		return false
	view.draft_title.text = "手工设计"
	view.draft_body.text = first
	save.pressed.emit()
	save.pressed.emit() # A second activation while the first request is outstanding.
	if not await wait_for(func(): return not view.composer.visible and view.body.text == first, "First save failed: " + view.draft_status.text):
		return false
	var id: String = view.reference.document_id
	var observations := []
	for version in [1, 2]:
		view.get_ok_button().pressed.emit()
		if not scene.check(not view.visible, "Document window did not close"):
			return false
		opener.pressed.emit()
		if not await wait_for(func(): return view.documents.item_count == 3, "Reopen did not reload list"):
			return false
		var row := -1
		for index in view.documents.item_count:
			if view.documents.get_item_metadata(index).id == id:
				row = index
		if not scene.check(row >= 0 and view.documents.get_item_metadata(row).version == version, "Saved revision missing from document list"):
			return false
		view.documents.select(row)
		view.documents.item_selected.emit(row)
		if not await wait_for(func(): return view.reference.get("version") == version, "Reopen did not read exact revision"):
			return false
		view.paragraphs.select(version)
		view.paragraphs.item_selected.emit(version)
		var selected: String = view.body.get_selected_text()
		if not scene.check(view.status.text.ends_with("作者 " + author) and view.body.text == (first if version == 1 else revised) and selected == ("第二段 · 手写" if version == 1 else "第三段 · 复审"), "Saved paragraphs or revision author mismatch"):
			return false
		observations.append({"version": version, "body": view.body.text, "author": author, "selected": selected, "paragraph": view.reference.paragraph})
		if version == 1:
			view.edit.pressed.emit()
			if not scene.check(view.composer.visible and view.draft_body.text == first, "Edit failed to load first revision"):
				return false
			view.draft_body.text = revised
			save.pressed.emit()
			if not await wait_for(func(): return view.draft_status.text.contains("尚未收到保存回执"), "Missing retry state"):
				return false
			if not scene.check(view.draft_body.text == revised and not view.draft_body.editable, "Unexpected mutation of pending save"):
				return false
			save.pressed.emit()
			if not await wait_for(func(): return view.reference.get("version") == 2, "Retry did not read back v2"):
				return false
	await view.open_document(id, 1, 1)
	view.edit.pressed.emit()
	view.draft_body.text = "旧版草稿"
	save.pressed.emit()
	if not await wait_for(func(): return view.draft_status.text.contains("修订发生冲突"), "Stale revision did not report conflict"):
		return false
	if not scene.check(view.composer.visible and view.draft_body.text == "旧版草稿" and view.draft_body.editable, "Conflict discarded draft"):
		return false
	view.composer.get_cancel_button().pressed.emit()
	print("D04_CHECKS=", JSON.stringify({"document_id": id, "reopened": observations, "stale_draft_retained": true}))
	return true
