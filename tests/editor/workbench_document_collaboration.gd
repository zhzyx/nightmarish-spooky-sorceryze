extends SceneTree

const BASE := "设计目标\n约束条件\n\n交付清单"
const FIRST := "设计目标 A\n约束条件\n\n交付清单"
const SECOND := "设计目标\n约束条件\n\n交付清单 B"
const BOTH := "设计目标 A\n约束条件\n\n交付清单 B"
const REMOTE := "设计目标 A2\n约束条件\n\n交付清单 B"
const LOCAL := "设计目标 A\n约束条件 B2\n\n交付清单 B"
const RESOLVED := "设计目标 A2\n约束条件 B2\n\n交付清单 B"

var view
var session
var role := OS.get_environment("D07_ROLE")
var shared := OS.get_environment("D07_SYNC")
var id := OS.get_environment("D07_DOC")
var observations := {}


func _initialize() -> void:
	run.call_deferred()


func wait_for(test: Callable, description: String) -> bool:
	var deadline := Time.get_ticks_msec() + 30000
	while not test.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	if test.call():
		return true
	push_error("%s timed out: %s (view: %s, draft: %s)" % [
		role, description, view.status.text if view else "", view.draft_status.text if view else "",
	])
	quit(1)
	return false


func mark_file(step: String) -> void:
	var file := FileAccess.open(shared.path_join(step), FileAccess.WRITE)
	file.store_string(role)


func marked(step: String) -> bool:
	return FileAccess.file_exists(shared.path_join(step))


func save() -> void:
	view.composer.get_ok_button().pressed.emit()


func version_is(number: int, body: String) -> bool:
	return view.reference.get("version") == number and view.body.text == body


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
	if not await wait_for(func(): return not session.get_identity().is_empty(), "authenticated account"):
		return
	view = session.find_child("WorkbenchDocuments", true, false)
	session.find_child("OpenWorkbenchDocuments", true, false).pressed.emit()
	if not await wait_for(func(): return view.documents.item_count == 1, "shared document in list"):
		return
	view.documents.select(0)
	view.documents.item_selected.emit(0)
	if not await wait_for(func(): return version_is(1, BASE) and view.collaboration.room.get_ready_state() == WebSocketPeer.STATE_OPEN, "selected v1 live room"):
		return
	view.edit.pressed.emit()
	view.draft_body.text = FIRST if role == "A" else SECOND
	mark_file("editing_" + role)
	if role == "A":
		if not await wait_for(func(): return marked("editing_B"), "B has its own draft"):
			return
		save()
	else:
		if not await wait_for(func(): return version_is(2, FIRST) and view.draft_body.text == SECOND, "A revision notification with B draft intact"):
			return
		save()
		if not await wait_for(func(): return view.draft_status.text.contains("尚未收到保存回执"), "ambiguous merged save"):
			return
		save()
	if not await wait_for(func(): return version_is(3, BOTH) and not view.composer.visible, "both paragraphs in native view"):
		return
	observations["different_paragraphs"] = {"version": 3, "body_md": view.body.text}
	view.edit.pressed.emit()
	view.draft_body.text = REMOTE if role == "A" else LOCAL
	mark_file("overlap_" + role)
	if role == "A":
		if not await wait_for(func(): return marked("overlap_B"), "B editing same multiline paragraph"):
			return
		save()
	else:
		if not await wait_for(func(): return version_is(4, REMOTE) and view.draft_body.text == LOCAL, "same-paragraph peer edit visible"):
			return
		save()
		var adapter = view.collaboration
		if not await wait_for(func(): return adapter.remote_panel.visible, "visible conflict with two texts"):
			return
		if not await wait_for(func(): return view.draft_status.text.contains("同一段落") and adapter.remote_body.text == REMOTE and view.draft_body.text == LOCAL and view.composer.get_ok_button().disabled, "retained local and remote texts"):
			return
		save()
		adapter.review.pressed.emit()
		adapter.confirm.get_cancel_button().pressed.emit()
		var read: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + id)
		if read.data.get("version") != 4 or read.data.get("body_md") != REMOTE:
			push_error("Unconfirmed conflict modified the document")
			quit(1)
			return
		observations["conflict"] = {"remote": adapter.remote_body.text, "local": view.draft_body.text, "unchanged_server_version": read.data.version}
		view.draft_body.text = RESOLVED
		adapter.review.pressed.emit()
		adapter.confirm.get_ok_button().pressed.emit()
		save()
	if not await wait_for(func(): return version_is(5, RESOLVED) and not view.composer.visible, "confirmed resolution in both views"):
		return
	observations["resolved"] = {"version": 5, "body_md": view.body.text}
	observations["account"] = session.get_identity().id
	print("D07_OBSERVED=", JSON.stringify(observations))
	session.find_child("SignOut", true, false).pressed.emit()
	if view.collaboration.room or view.visible or view.body.text or view.collaboration.remote_body.text:
		push_error("Previous session data remained in the document window")
		quit(1)
		return
	quit()
