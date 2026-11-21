@tool
extends VBoxContainer

var session: Node
var view
var room: WebSocketPeer
var document_id := ""
var base_md := ""
var notified_version := 0
var refreshing := false
var refresh_again := false
var remote_panel := VBoxContainer.new()
var remote_caption := Label.new()
var remote_body := TextEdit.new()
var review := Button.new()
var confirm := ConfirmationDialog.new()
var conflict := {}
var prepared := {}
var draft_path := ""
var last_revision := {}
var interrupted := false
var had_room_snapshot := false
var checking_head := false
var compare_on_snapshot := false
var retry_in := 0.0
var retry_delay := 1.0
var discard := Button.new()
var discard_confirmation := ConfirmationDialog.new()


func _ready() -> void:
	set_process(false)
	attach.call_deferred()


func attach() -> void:
	session = get_parent()
	view = session.get_node("WorkbenchDocuments")
	view.collaboration = self
	view.visibility_changed.connect(_visibility_changed)
	view.composer.visibility_changed.connect(_draft_visibility_changed)
	view.draft_body.text_changed.connect(_persist_draft)
	view.draft_body.text_set.connect(_persist_draft)
	discard.text = "放弃本地草稿"
	discard.hide()
	discard.pressed.connect(func(): discard_confirmation.popup_centered())
	view.draft_status.get_parent().add_child(discard)
	discard_confirmation.dialog_text = "放弃这份本地草稿？"
	discard_confirmation.get_ok_button().text = "放弃草稿"
	discard_confirmation.confirmed.connect(_discard_draft)
	view.composer.add_child(discard_confirmation)
	view.draft_status.get_parent().add_child(remote_panel)
	remote_panel.hide()
	remote_panel.add_child(remote_caption)
	remote_body.editable = false
	remote_body.custom_minimum_size.y = 90 * EditorInterface.get_editor_scale()
	remote_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	remote_panel.add_child(remote_body)
	review.text = "核对两份正文…"
	review.pressed.connect(func(): confirm.popup_centered())
	remote_panel.add_child(review)
	confirm.title = "确认解决修订冲突"
	confirm.dialog_text = "继续使用上方已编辑的完整草稿作为解决结果？确认后仍需点击保存。"
	confirm.get_ok_button().text = "使用已编辑的草稿"
	confirm.confirmed.connect(_accept_resolution)
	view.composer.add_child(confirm)
	set_process(false)


func begin_draft() -> void:
	var identity: Dictionary = session.get_identity()
	var scope := JSON.stringify([session._origin, identity.id, identity.project, document_id])
	var directory := EditorInterface.get_editor_paths().get_data_dir().path_join("document-drafts")
	var path := directory.path_join(scope.sha256_text() + ".json")
	view.composer.get_cancel_button().text = "保留并关闭"
	discard.show()
	if FileAccess.file_exists(path):
		var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if saved is Dictionary and saved.get("body_md") is String and saved.get("base_md") is String and int(saved.get("version", 0)) > 0:
			view.editing.base_md = saved.base_md
			view.editing.version = int(saved.version)
			view.composer.title = "编辑正文 · 草稿基于 v%d" % int(saved.version)
			view.draft_body.text = saved.body_md
			compare_on_snapshot = true
	draft_path = path
	if (interrupted and had_room_snapshot) or (compare_on_snapshot and last_revision.is_empty()):
		_wait_for_connection()
		_check_http_head()
	elif compare_on_snapshot:
		_compare_draft(last_revision)


func _persist_draft() -> void:
	if draft_path.is_empty():
		return
	var content: String = view.draft_body.text
	if content == str(view.editing.base_md).replace("\r\n", "\n"):
		remove_draft_file()
		return
	var error := DirAccess.make_dir_recursive_absolute(draft_path.get_base_dir())
	if error == OK:
		var temp := draft_path + "." + Crypto.new().generate_random_bytes(8).hex_encode() + ".tmp"
		var file := FileAccess.open(temp, FileAccess.WRITE)
		if file:
			var stored := file.store_string(JSON.stringify({
				"version": view.editing.version, "base_md": view.editing.base_md, "body_md": content,
			}))
			file.flush()
			error = file.get_error()
			file.close()
			if stored and error == OK and DirAccess.rename_absolute(temp, draft_path) == OK:
				return
			DirAccess.remove_absolute(temp)
	view.draft_status.text = "无法写入本机草稿，请先复制正文再关闭。"


func remove_draft_file() -> bool:
	if not draft_path.is_empty() and FileAccess.file_exists(draft_path) and DirAccess.remove_absolute(draft_path) != OK:
		view.draft_status.text = "无法删除本机草稿。"
		return false
	return true


func remove_draft() -> void:
	remove_draft_file()
	draft_path = ""


func _discard_draft() -> void:
	if remove_draft_file():
		draft_path = ""
		view._clear_draft()


func end_draft() -> void:
	_persist_draft()
	draft_path = ""
	compare_on_snapshot = false
	checking_head = false
	discard.hide()
	view.composer.get_cancel_button().text = "取消"


func _wait_for_connection() -> void:
	compare_on_snapshot = true
	view.draft_body.editable = true
	view.composer.get_ok_button().disabled = true
	view.draft_status.text = "等待连接天璇。可继续编辑，本机保留草稿。"


func _check_http_head() -> void:
	if checking_head or not compare_on_snapshot or draft_path.is_empty():
		return
	var attempt: String = view.call_id
	var id := document_id
	checking_head = true
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + id.uri_encode())
	if attempt != view.call_id or id != document_id:
		return
	checking_head = false
	if not compare_on_snapshot:
		return
	if reply.status in [403, 404]:
		view.reset_view()
	elif reply.status == 200 and reply.data.get("id") == id:
		_compare_draft(reply.data)
		_new_revision(reply.data, true)


func _compare_draft(doc: Dictionary) -> void:
	if doc.get("id") != document_id or not doc.get("body_md") is String:
		return
	compare_on_snapshot = false
	checking_head = false
	if draft_path.is_empty():
		return
	prepared.clear()
	view.call_id = Crypto.new().generate_random_bytes(16).hex_encode()
	view.draft_body.editable = true
	if int(doc.version) != int(view.editing.version) or doc.body_md != view.editing.base_md:
		show_conflict({"remote_version": doc.version, "remote_md": doc.body_md})
		view.draft_status.text = "天璇现为 v%d，草稿基于 v%d。请核对两份正文后再保存。" % [doc.version, view.editing.version]
	else:
		view.composer.get_ok_button().disabled = false
		view.draft_status.text = "已核对服务器 v%d，草稿基于此修订。点击保存提交。" % int(doc.version)


func _visibility_changed() -> void:
	if not view.visible:
		view.generation += 1
		leave()


func _draft_visibility_changed() -> void:
	if not view.composer.visible:
		prepared.clear()
		conflict.clear()
		remote_body.clear()
		remote_panel.hide()
		confirm.hide()
		discard_confirmation.hide()


func leave() -> void:
	if room:
		room.close()
	room = null
	document_id = ""
	base_md = ""
	notified_version = 0
	refreshing = false
	refresh_again = false
	last_revision.clear()
	interrupted = false
	had_room_snapshot = false
	checking_head = false
	retry_delay = 1.0
	retry_in = 0.0
	set_process(false)


func watch(id: String, version: int, markdown: String) -> void:
	base_md = markdown
	if room and id == document_id and room.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		return
	notified_version = version
	document_id = id
	room = session.join_document_room(id)
	set_process(true)


func _process(delta: float) -> void:
	if not room:
		retry_in -= delta
		if retry_in <= 0:
			retry_in = retry_delay
			retry_delay = minf(retry_delay * 2.0, 15.0)
			room = session.join_document_room(document_id)
			_check_http_head()
			if not room:
				_disconnected()
		return
	room.poll()
	if room.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		if room.get_close_code() in [4401, 4403, 4404]:
			view.reset_view()
			return
		room = null
		_disconnected()
		return
	while room and room.get_available_packet_count() > 0:
		var event: Variant = JSON.parse_string(room.get_packet().get_string_from_utf8())
		if not event is Dictionary:
			continue
		if event.get("type") == "changed":
			_refresh()
		elif event.get("type") in ["snapshot", "updated"]:
			var doc: Dictionary = event.get("doc", {})
			if doc.get("id") != document_id:
				continue
			var reconnected: bool = interrupted and event.type == "snapshot"
			if event.type == "snapshot":
				if interrupted:
					view.status.text = "%s · v%d · 已重新连接" % [document_id, int(doc.version)]
				interrupted = false
				had_room_snapshot = true
				retry_delay = 1.0
				retry_in = 0.0
				if compare_on_snapshot:
					_compare_draft(doc)
			_new_revision(doc, reconnected)


func _disconnected() -> void:
	if not interrupted:
		interrupted = true
		refreshing = false
		refresh_again = false
		last_revision.clear()
		view.status.text = "%s · 修订通知已断开，正在重新连接。" % document_id
		if not draft_path.is_empty() and had_room_snapshot:
			view.call_id = Crypto.new().generate_random_bytes(16).hex_encode()
			prepared.clear()
			conflict.clear()
			remote_body.clear()
			remote_panel.hide()
			confirm.hide()
			_wait_for_connection()


func _refresh() -> void:
	if refreshing:
		refresh_again = true
		return
	var source := room
	refreshing = true
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + document_id.uri_encode())
	if source != room:
		return
	refreshing = false
	if reply.status == 200:
		_new_revision(reply.data)
	elif reply.status in [403, 404]:
		view.reset_view()
	if source == room and refresh_again:
		refresh_again = false
		_refresh()


func _new_revision(doc: Dictionary, reconnected: bool = false) -> void:
	var latest := int(doc.get("version", 0))
	if doc.get("id") != document_id:
		return
	if reconnected or latest >= int(last_revision.get("version", 0)):
		last_revision = doc.duplicate()
	if reconnected:
		if latest == int(view.reference.get("version", 0)) and doc.get("body_md") == view.raw_body:
			return
	elif latest <= maxi(notified_version, int(view.reference.get("version", 0))):
		return
	notified_version = latest
	for index in view.documents.item_count:
		if view.documents.get_item_metadata(index).id == document_id:
			view._document_row(doc, index)
			break
	if view.composer.visible and view.draft_body.editable and conflict.is_empty():
		view.draft_status.text = "对方已保存 v%d。保存时将核对双方修改。" % latest
	view.open_document(document_id, latest, 1, true)


func save(route: String, payload: Dictionary, editing: Dictionary, attempt: String) -> Dictionary:
	# Retain the exact optimistic write across a lost acknowledgement.
	if "\r\n" in editing.base_md and "\n" not in str(editing.base_md).replace("\r\n", ""):
		payload.body_md = str(payload.body_md).replace("\r\n", "\n").replace("\n", "\r\n")
	if prepared.get("attempt") != attempt:
		prepared = {"attempt": attempt, "payload": payload}
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_PATCH, route, prepared.payload)
	if reply.status != 409 or view.call_id != attempt:
		return reply
	var preview: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/merge/preview", {
		"base_md": editing.base_md, "local_md": payload.body_md, "expected_version": editing.version,
	})
	if view.call_id != attempt or preview.status != 200:
		return preview
	if preview.data.get("status") != "ready" or not preview.data.get("body_md") is String:
		return {"status": 502, "data": {}}
	prepared.payload = {
		"expected_version": preview.data.remote_version,
		"body_md": preview.data.body_md,
		"call_id": Crypto.new().generate_random_bytes(16).hex_encode(),
	}
	return await session.api_request(HTTPClient.METHOD_PATCH, route, prepared.payload)


func show_conflict(data: Dictionary) -> void:
	conflict = data
	remote_caption.text = "对方保存的完整正文 · v%d" % int(data.remote_version)
	remote_body.text = data.remote_md
	view.draft_status.text = "同一段落的修订发生冲突。上方保留你的草稿，下方可复制对方正文。编辑后核对两份正文。"
	view.composer.get_ok_button().disabled = true
	remote_panel.show()


func _accept_resolution() -> void:
	if conflict.is_empty() or not view.composer.visible:
		return
	view.editing.base_md = conflict.remote_md
	view.editing.version = conflict.remote_version
	view.composer.title = "编辑正文 · v%d" % int(conflict.remote_version)
	_persist_draft()
	view.draft_status.text = "已核对 v%d。点击保存将提交上方的完整草稿。" % int(conflict.remote_version)
	conflict.clear()
	remote_panel.hide()
	remote_body.clear()
	view.composer.get_ok_button().disabled = false
