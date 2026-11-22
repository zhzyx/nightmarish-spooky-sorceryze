extends SceneTree

var session
var view
var dialog
var fixture: Dictionary
var observations := []


func _initialize() -> void:
	run.call_deferred()


func require(value: bool, message: String) -> bool:
	if not value:
		if is_instance_valid(dialog):
			message += " [visible=%s, selected=%s, status=%s, doc_status=%s]" % [dialog.visible, view.selected_paragraph(), dialog.status.text, view.status.text]
		push_error(message)
		quit(1)
	return value


func wait_for(test: Callable, message: String) -> bool:
	var until := Time.get_ticks_msec() + 42000
	while not test.call() and Time.get_ticks_msec() < until:
		await process_frame
	return require(test.call(), message)


func request(instruction: String) -> void:
	dialog.instruction.text = instruction
	dialog.instruction.text_changed.emit(instruction)
	dialog.generate.pressed.emit()


func start_preview(instruction: String) -> void:
	dialog.open_button.pressed.emit()
	request(instruction)


func capture(window: Window, filename: String) -> bool:
	if not OS.has_environment("D05_IMAGES"):
		return true
	await RenderingServer.frame_post_draw
	var image := window.get_texture().get_image()
	return require(image != null and not image.is_empty() and image.save_png(OS.get_environment("D05_IMAGES").path_join(filename)) == OK, "Native window capture failed")


func run() -> void:
	fixture = JSON.parse_string(OS.get_environment("D05_FIXTURE"))
	await create_timer(0.8).timeout
	if OS.has_environment("D05_SOURCE_CONTROLS"):
		session = load("res://business_session.gd").new()
		root.add_child(session)
		session.install_paragraph_suggestion(load("res://paragraph_suggestion.gd"))
	else:
		var entry = root.find_child("OpenAIWorkbenchButton", true, false)
		if entry:
			entry.pressed.emit()
		else:
			var palette = EditorInterface.get_command_palette()
			var shortcut := InputEventShortcut.new()
			shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
			root.push_input(shortcut)
			await process_frame
			var search = palette.find_children("*", "LineEdit", true, false)[0]
			search.text = "editor/open_ai_workbench"
			search.text_changed.emit(search.text)
			palette.find_children("*", "Tree", true, false)[0].item_activated.emit()
		await process_frame
		session = root.find_child("AIWorkbenchSidebar", true, false).find_child("WorkbenchBusinessSession", true, false)
	if not await wait_for(func(): return not session.get_identity().is_empty(), "Account login failed"):
		return
	var opener: Button = session.find_child("OpenWorkbenchDocuments", true, false)
	if not require(opener.is_visible_in_tree(), "Native document entry unavailable"):
		return
	opener.pressed.emit()
	view = session.find_child("WorkbenchDocuments", true, false)
	dialog = view.find_child("WorkbenchParagraphSuggestion", true, false)
	if not require(is_instance_valid(dialog), "Paragraph suggestion control missing"):
		return
	if not await wait_for(func(): return view.documents.item_count == 2, "List did not load"):
		return
	for row in view.documents.item_count:
		if view.documents.get_item_metadata(row).id == fixture.id:
			view.documents.select(row)
			view.documents.item_selected.emit(row)
	if not await wait_for(func(): return view.reference.get("document_id") == fixture.id, "Selected document missing"):
		return
	# A partial selection must not accidentally use the paragraph picker's previous index.
	view.body.select(2, 1, 2, 3)
	dialog.open_button.pressed.emit()
	if not require(not dialog.visible, "Partial selection accepted"):
		return
	# Select the second of two identical paragraphs by dragging/selecting the native TextEdit range.
	await view.open_document(fixture.id, 1, 1)
	var span: Vector2i = view.ranges[2]
	view.body.grab_focus()
	view.body.select(span.x, 0, span.y, view.body.get_line(span.y).length())
	view.body.center_viewport_to_caret()
	if not await wait_for(func(): return view.paragraphs.selected == 2 and view.reference.paragraph == 3, "Native selection and paragraph picker disagreed"):
		return
	if not await capture(view, "paragraph-selection.png"):
		return
	dialog.open_button.grab_focus()
	dialog.open_button.pressed.emit()
	if not require(dialog.visible and dialog.paragraph == 3 and view.body.get_selected_text() == fixture.original.replace("\r\n", "\n"), "Exact native selection was lost on focus transfer"):
		return
	request("取消")
	if not await wait_for(func(): return not dialog.get_ok_button().disabled, "No cancellation preview"):
		return
	dialog.get_cancel_button().pressed.emit()
	await process_frame
	if not require(not dialog.visible and view.raw_body == fixture.body, "Cancel changed revision"):
		return
	start_preview("越界回执")
	if not await wait_for(func(): return dialog.status.text.contains("以外"), "Corrupt candidate not rejected"):
		return
	if not require(dialog.get_ok_button().disabled, "Out-of-paragraph change could be accepted"):
		return
	request("更明确")
	if not await wait_for(func(): return not dialog.get_ok_button().disabled, "No valid preview: " + dialog.status.text):
		return
	if not require(dialog.preview.text == fixture.replacement.replace("\r\n", "\n") and view.raw_body == fixture.body and view.reference.version == 1, "Preview changed source or displayed wrong paragraph"):
		return
	if not await capture(dialog, "paragraph-preview.png"):
		return
	observations.append({"paragraph": dialog.paragraph, "selected": view.body.get_selected_text(), "preview": dialog.preview.text, "version_before_accept": view.reference.version})
	dialog.get_ok_button().pressed.emit()
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return dialog.status.text.contains("尚未收到保存回执"), "Lost SAVE receipt not recoverable"):
		return
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return view.reference.get("version") == 2, "Accepted revision was not reopened"):
		return
	if not require(view.reference.paragraph == 3 and view.raw_body == fixture.candidate and view.body.get_selected_text() == fixture.replacement.replace("\r\n", "\n"), "Wrong revision, bytes or native selection after acceptance"):
		return
	start_preview("并发修订")
	if not await wait_for(func(): return not dialog.get_ok_button().disabled, "No concurrent edit preview"):
		return
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return dialog.status.text.contains("冲突"), "Stale write did not surface conflict"):
		return
	if not require(dialog.get_ok_button().disabled, "Could accept conflicting candidate again"):
		return
	dialog.get_cancel_button().pressed.emit()
	await process_frame
	await view.open_document(fixture.other, 1, 3, true)
	start_preview("独立修改")
	if not await wait_for(func(): return dialog.visible and not dialog.get_ok_button().disabled, "Independent candidate preview missing"):
		return
	await create_timer(0.5).timeout
	if not require(dialog.visible and view.reference.version == 1, "Live updates discarded the candidate base"):
		return
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return dialog.status.text.contains("合并期间有新修订") and not dialog.get_ok_button().disabled, "Second independent change discarded the candidate"):
		return
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return dialog.status.text.contains("尚未收到保存回执"), "Missing rebased write acknowledgement"):
		return
	dialog.get_ok_button().pressed.emit()
	if not await wait_for(func(): return view.reference.get("version") == 4 and view.reference.get("paragraph") == 3 and view.raw_body == fixture.merged, "Merged revision or surrounding Markdown changed"):
		return
	await view.open_document(fixture.id, 3, 3)
	start_preview("切换段落")
	view.paragraphs.select(1)
	view.paragraphs.item_selected.emit(1)
	await create_timer(0.5).timeout
	if not require(not dialog.visible and dialog.preview.text.is_empty(), "Old selection restored a delayed preview"):
		return
	start_preview("切换文档")
	await view.open_document(fixture.other, 4, 1)
	await create_timer(0.5).timeout
	if not require(not dialog.visible and dialog.preview.text.is_empty() and view.reference.document_id == fixture.other, "Old document restored a delayed preview"):
		return
	start_preview("切换身份")
	var started := OS.get_environment("D05_IDENTITY_PREVIEW_STARTED")
	if not await wait_for(func(): return FileAccess.file_exists(started), "Identity preview never reached the model"):
		return
	session.find_child("SignOut", true, false).pressed.emit()
	await create_timer(0.5).timeout
	if not require(not dialog.visible and not view.visible and dialog.preview.text.is_empty() and view.reference.is_empty(), "Signed-out identity retained a preview"):
		return
	print("D05_CHECKS=", JSON.stringify(observations))
	quit()
