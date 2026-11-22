extends SceneTree

const BASE := "第一段\n\n设计原文"
const LOCAL := "离线时人的文字\n\n第二段草稿"
const REMOTE := "在线协作者的修订\n\n设计原文"
const RESOLVED := "在线协作者的修订\n\n离线时人的文字"
var view
var session
var stage := OS.get_environment("D08_STAGE")
var scenario := OS.get_environment("D08_SCENARIO")
var doc_id := OS.get_environment("D08_DOC")
var observed := {}


func _initialize() -> void:
	run.call_deferred()


func wait_for(test: Callable, name_of_step: String) -> bool:
	var deadline := Time.get_ticks_msec() + 30000
	while not test.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if test.call():
		return true
	push_error("%s / %s: %s (%s; %s)" % [scenario, stage, name_of_step, view.status.text if view else "", view.draft_status.text if view else ""])
	quit(1)
	return false


func mark(step: String) -> void:
	var file := FileAccess.open(OS.get_environment("D08_SYNC").path_join(step), FileAccess.WRITE)
	file.store_string("ready")


func replace_text(text: String) -> void:
	view.draft_body.select_all()
	view.draft_body.insert_text_at_caret(text)


func check(value: bool, description: String) -> bool:
	if not value:
		push_error(description)
		quit(1)
	return value


func edit_document(target: String) -> bool:
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	if not await wait_for(func(): return view.documents.item_count >= 2, "document list"):
		return false
	for i in view.documents.item_count:
		if view.documents.get_item_metadata(i).id == target:
			view.documents.select(i)
			view.documents.item_selected.emit(i)
			break
	if not await wait_for(func(): return view.reference.get("document_id") == target and not view.collaboration.last_revision.is_empty(), "authenticated live document"):
		return false
	view.edit.pressed.emit()
	return true


func check_other_scope(name_of_scope: String, token: String, project: String, target: String) -> bool:
	view.get_ok_button().pressed.emit()
	session.find_child("SignOut", true, false).pressed.emit()
	if not check(view.draft_body.text == "" and view.collaboration.remote_body.text == "", "old identity data still visible"):
		return false
	session.find_child("ChooseAccount", true, false).pressed.emit()
	session.find_child("AccountSecret", true, false).text = token
	session.find_child("BusinessProject", true, false).text = project
	session.find_child("Authenticate", true, false).pressed.emit()
	if not await wait_for(func(): return session.get_identity().get("project") == project, "switch account/project"):
		return false
	if not await edit_document(target):
		return false
	if not check(not FileAccess.file_exists(view.collaboration.draft_path) and view.draft_body.text == view.body.text and view.draft_body.text != LOCAL, "draft restored outside original scope"):
		return false
	observed[name_of_scope] = {"account": session.get_identity().id, "project": project, "document": target, "body_md": view.draft_body.text}
	view.composer.get_cancel_button().pressed.emit()
	return true


func run() -> void:
	await create_timer(0.8).timeout
	var opener = root.find_child("OpenAIWorkbenchButton", true, false)
	if opener:
		opener.pressed.emit()
	else:
		var palette = EditorInterface.get_command_palette()
		var shortcut := InputEventShortcut.new()
		shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
		root.push_input(shortcut)
		await process_frame
		var search = palette.find_children("*", "LineEdit", true, false)[0]
		var results = palette.find_children("*", "Tree", true, false)[0]
		search.text = "editor/open_ai_workbench"
		search.text_changed.emit(search.text)
		results.item_activated.emit()
	session = root.find_child("WorkbenchBusinessSession", true, false)
	if not await wait_for(func(): return session and not session.get_identity().is_empty(), "login"):
		return
	view = session.get_node("WorkbenchDocuments")
	if not await edit_document(doc_id):
		return
	var adapter = view.collaboration
	var advanced := scenario == "advanced"
	var version := 2 if advanced else 1
	var server_text := REMOTE if advanced else BASE
	if stage == "disconnect":
		mark("connected")
		if not await wait_for(func(): return adapter.interrupted and view.composer.get_ok_button().disabled, "server stopped"):
			return
		var unavailable: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + doc_id, {}, 2)
		if not check(unavailable.status == 0 and view.draft_body.editable, "HTTP service still available or offline editing unavailable"):
			return
		replace_text(LOCAL)
		await process_frame
		var record: Variant = JSON.parse_string(FileAccess.get_file_as_string(adapter.draft_path))
		if not check(record is Dictionary and record.body_md == LOCAL and record.version == 1 and record.base_md == BASE, "persisted draft differs"):
			return
		observed.offline = {"http_status": unavailable.status, "draft": record}
		mark("typed")
		if not await wait_for(func(): return adapter.interrupted == (scenario == "http_only") and not adapter.compare_on_snapshot and view.reference.get("version") == version and view.body.text == server_text and not adapter.last_revision.is_empty(), "reconnected revision"):
			return
		observed.websocket_reconnected = not adapter.interrupted
	if not check(view.draft_body.text == LOCAL and adapter.remote_panel.visible == advanced and view.composer.get_ok_button().disabled == advanced, "draft or review gate after reconnect/restart differs"):
		return
	var read: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + doc_id)
	if not check(read.status == 200 and read.data.version == version and read.data.body_md == server_text, "server changed before explicit save"):
		return
	observed.comparison = {"version": read.data.version, "server": read.data.body_md, "local": view.draft_body.text, "requires_review": adapter.remote_panel.visible}
	if advanced and not check(adapter.remote_body.text == server_text, "comparison does not display full remote text"):
		return
	if stage == "disconnect" and advanced:
		view.composer.get_cancel_button().pressed.emit()
		if not await check_other_scope("other_account", OS.get_environment("D08_PEER"), "studio/game", doc_id):
			return
		if not await check_other_scope("other_project", OS.get_environment("TIANXUAN_TOKEN"), "studio/other", doc_id):
			return
		if not await check_other_scope("other_document", OS.get_environment("TIANXUAN_TOKEN"), "studio/game", OS.get_environment("D08_OTHER")):
			return
	else:
		if advanced:
			replace_text(RESOLVED)
			adapter.review.pressed.emit()
			adapter.confirm.get_ok_button().pressed.emit()
		view.composer.get_ok_button().pressed.emit()
		var expected := RESOLVED if advanced else LOCAL
		if not await wait_for(func(): return not view.composer.visible and view.reference.get("version") == version + 1 and view.body.text == expected, "explicit save"):
			return
		view.edit.pressed.emit()
		if not check(not FileAccess.file_exists(adapter.draft_path) and view.draft_body.text == expected, "stale draft after acknowledged save"):
			return
		observed.saved = {"version": version + 1, "body_md": view.draft_body.text}
	print("D08_OBSERVED=", JSON.stringify(observed))
	quit()
