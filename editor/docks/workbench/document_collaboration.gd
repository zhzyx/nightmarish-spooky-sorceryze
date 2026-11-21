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


func _ready() -> void:
	set_process(false)
	attach.call_deferred()


func attach() -> void:
	session = get_parent()
	view = session.get_node("WorkbenchDocuments")
	view.collaboration = self
	view.visibility_changed.connect(_visibility_changed)
	view.composer.visibility_changed.connect(_draft_visibility_changed)
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


func leave() -> void:
	if room:
		room.close()
	room = null
	document_id = ""
	base_md = ""
	notified_version = 0
	refreshing = false
	refresh_again = false
	set_process(false)


func watch(id: String, version: int, markdown: String) -> void:
	base_md = markdown
	if room and id == document_id and room.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		return
	notified_version = version
	document_id = id
	room = session.join_document_room(id)
	set_process(room != null)


func _process(_delta: float) -> void:
	room.poll()
	if room.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		set_process(false)
		if room.get_close_code() in [4401, 4403, 4404]:
			view.reset_view()
			return
		view.status.text += " · 修订通知已断开，重开文档可重新连接。"
		return
	while room and room.get_available_packet_count() > 0:
		var event: Variant = JSON.parse_string(room.get_packet().get_string_from_utf8())
		if not event is Dictionary:
			continue
		if event.get("type") == "changed":
			_refresh()
		elif event.get("type") in ["snapshot", "updated"]:
			_new_revision(event.get("doc", {}))


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


func _new_revision(doc: Dictionary) -> void:
	var latest := int(doc.get("version", 0))
	if doc.get("id") != document_id or latest <= maxi(notified_version, int(view.reference.get("version", 0))):
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
	view.draft_status.text = "已核对 v%d。点击保存将提交上方的完整草稿。" % int(conflict.remote_version)
	conflict.clear()
	remote_panel.hide()
	remote_body.clear()
	view.composer.get_ok_button().disabled = false
