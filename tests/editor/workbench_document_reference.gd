extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func choose(panel, index: int) -> bool:
	if index < 0:
		return false
	panel.picker.select(index)
	panel.picker.item_selected.emit(index)
	var until := Time.get_ticks_msec() + 20000
	while panel.picker.disabled and Time.get_ticks_msec() < until:
		await process_frame
	panel.picker.get_popup().hide()
	return not panel.picker.disabled and not panel.feedback.visible

func run() -> void:
	await create_timer(0.8).timeout
	var palette := EditorInterface.get_command_palette()
	var chord := InputEventShortcut.new()
	chord.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(chord)
	await process_frame
	var search = palette.find_children("*","LineEdit",true,false)[0]
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	palette.find_children("*","Tree",true,false)[0].item_activated.emit()
	await process_frame
	var sidebar = root.find_child("AIWorkbenchSidebar",true,false)
	var session = sidebar.find_child("WorkbenchBusinessSession",true,false)
	var panel = sidebar.find_child("WorkbenchBusinessModules",true,false)
	var until := Time.get_ticks_msec() + 15000
	while session.get_identity().is_empty() and Time.get_ticks_msec() < until:
		await process_frame
	if not await choose(panel,1):
		push_error("Could not load authenticated modules")
		quit(1)
		return
	var idx := -1
	for i in panel.picker.item_count:
		if panel.picker.get_item_metadata(i) == "default":
			idx = i
	if not await choose(panel,idx):
		push_error("Default module unavailable")
		quit(1)
		return
	var view = session.find_child("WorkbenchDocuments",true,false)
	session.find_child("OpenWorkbenchDocuments",true,false).pressed.emit()
	until = Time.get_ticks_msec()+15000
	while view.documents.item_count<1 and Time.get_ticks_msec()<until:
		await process_frame
	if view.documents.item_count != 1:
		push_error("Document listing failed")
		quit(1)
		return
	view.documents.select(0)
	view.documents.item_selected.emit(0)
	until = Time.get_ticks_msec()+15000
	while view.reference.is_empty() and Time.get_ticks_msec()<until:
		await process_frame
	view.paragraphs.select(1)
	view.paragraphs.item_selected.emit(1)
	var id := OS.get_environment("U10_DOC")
	if view.body.get_selected_text()!="原始目标段落" or view.reference.document_id!=id:
		push_error("Incorrect source paragraph")
		quit(1)
		return
	view.find_child("CiteDocumentParagraph",true,false).pressed.emit()
	var locator := "<tianxuan-doc://%s/1/2>" % id
	if view.visible or not panel.composer.text.contains(locator):
		push_error("Selected paragraph not inserted")
		quit(1)
		return
	panel.send.pressed.emit()
	until=Time.get_ticks_msec()+20000
	while panel.picker.disabled and Time.get_ticks_msec()<until:
		await process_frame
	var links: MenuButton = panel.find_child("SentDocumentReferences",true,false)
	if panel.conversation.get("turns",[]).size()!=1 or not links.is_visible_in_tree() or links.get_popup().item_count!=1:
		push_error("Sent paragraph unavailable: "+panel.feedback.text)
		quit(1)
		return
	var before: Dictionary = panel.conversation.turns[0].context_snapshot.references[0]
	var latest: Dictionary = await session.api_request(HTTPClient.METHOD_GET,"/api/v1/docs/"+id.uri_encode())
	if latest.status!=200 or int(latest.data.version)!=2 or not str(latest.data.body_md).ends_with("原始目标段落"):
		push_error("Fixture failed to move the paragraph")
		quit(1)
		return
	links.get_popup().id_pressed.emit(links.get_popup().get_item_id(0))
	until=Time.get_ticks_msec()+15000
	while view.reference.is_empty() and Time.get_ticks_msec()<until:
		await process_frame
	if not view.visible or view.reference.get("version")!=1 or view.reference.get("paragraph")!=2 or view.body.get_selected_text()!="原始目标段落":
		push_error("Sent reference did not open the pinned version")
		quit(1)
		return
	print("U10_RESULT=",JSON.stringify({"sent":before,"opened":view.reference,"current_version":latest.data.version,"conversation":panel.conversation.id}))
	quit()
