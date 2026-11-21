extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, message: String) -> bool:
	if not value:
		push_error(message)
		quit(1)
	return value

func run() -> void:
	await create_timer(0.8).timeout
	var sidebar = root.find_child("AIWorkbenchSidebar",true,false)
	var entry = root.find_child("OpenAIWorkbenchButton",true,false)
	if entry:
		entry.pressed.emit()
	else:
		var palette = EditorInterface.get_command_palette()
		var shortcut := InputEventShortcut.new()
		shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
		root.push_input(shortcut)
		await process_frame
		var search = palette.find_children("*","LineEdit",true,false)[0]
		var results = palette.find_children("*","Tree",true,false)[0]
		search.text = "editor/open_ai_workbench"
		search.text_changed.emit(search.text)
		results.item_activated.emit()
	await process_frame
	var session = sidebar.find_child("WorkbenchBusinessSession",true,false)
	var until := Time.get_ticks_msec() + 12000
	while session.get_identity().is_empty() and Time.get_ticks_msec() < until:
		await process_frame
	var opener = session.find_child("OpenWorkbenchDocuments",true,false)
	if not check(opener != null and opener.is_visible_in_tree(), "Document entry unavailable"):
		return
	opener.pressed.emit()
	var view = session.find_child("WorkbenchDocuments",true,false)
	var list: ItemList = view.find_child("DocumentList",true,false)
	until = Time.get_ticks_msec() + 12000
	while list.item_count < 2 and Time.get_ticks_msec() < until:
		await process_frame
	if not check(list.item_count == 2 and view.visible, "Document list unavailable: " + view.status.text):
		return
	var items: Array = JSON.parse_string(OS.get_environment("D02_EXPECT"))
	var trace := []
	for item in items:
		var slot := -1
		for i in list.item_count:
			if list.get_item_metadata(i).id == item.id:
				slot = i
		if not check(slot >= 0 and list.get_item_text(slot).contains("同名设计"),"Duplicate title identity lost"):
			return
		list.select(slot)
		list.item_selected.emit(slot)
		until = Time.get_ticks_msec() + 12000
		while view.reference.get("document_id") != item.id and Time.get_ticks_msec() < until:
			await process_frame
		if not check(view.reference.get("version") == item.version and view.paragraphs.item_count == 3, "Revision mismatch: " + view.status.text):
			return
		view.paragraphs.select(1)
		view.paragraphs.item_selected.emit(1)
		if not check(view.reference.paragraph == 2 and view.body.get_selected_text() == item.text and not view.body.editable, "Incorrect selected paragraph"):
			return
		var observed: Dictionary = view.reference.duplicate()
		observed["selected_text"] = view.body.get_selected_text()
		trace.append(observed)
	await view.open_document(items[1].id, 1, 2)
	if not check(view.reference.version==1 and view.body.get_selected_text()=="原始段落", "Pinned revision changed"):
		return
	var historical: Dictionary = view.reference.duplicate()
	historical["selected_text"] = view.body.get_selected_text()
	trace.append(historical)
	await view.open_document(items[1].id, 99, 2)
	if not check(view.reference.is_empty() and view.body.text.is_empty(),"Missing revision showed old body"):
		return
	await view.open_document(items[0].id, 1, 40)
	if not check(view.reference.is_empty() and view.body.text.is_empty(),"Missing paragraph showed old body"):
		return
	await view.open_document(items[0].id, 1, 1)
	session.find_child("SignOut",true,false).pressed.emit()
	if not check(not view.visible and view.reference.is_empty() and view.body.text.is_empty() and list.item_count == 0,"Previous account's document remained visible"):
		return
	print("D02_CHECKS=",JSON.stringify(trace))
	quit()
