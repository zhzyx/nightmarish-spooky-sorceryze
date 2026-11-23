@tool
extends Node
## Document state, transport and durable edits survive either View being closed.

signal changed

var workspace: Node
var session: Node
var active_id := ""
var document := {}
var documents: Array = []
var detail := {}
var status := ""
var conflict := {}
var saving := false
var collaborators: Array = []
var _generation := 0
var _selection := 0
var _room: WebSocketPeer
var _retry := 0.0
var _backoff := 1.0
var _refreshing := false
var _refresh_again := false
var _ping := 0.0
var _forbidden := false


func _ready() -> void:
	workspace = get_meta("workspace")
	session = workspace.session
	session.identity_changed.connect(_identity_changed)
	workspace.changed.connect(_workspace_changed)
	_identity_changed()


func _identity_changed() -> void:
	_generation += 1
	_selection += 1
	active_id = ""
	document.clear()
	documents.clear()
	detail.clear()
	conflict.clear()
	collaborators.clear()
	_forbidden = false
	saving = false
	status = ""
	_close_room()
	changed.emit()
	if not session.get_identity().is_empty():
		var saved: Dictionary = workspace.load_draft("document-selection")
		open(str(saved.get("id", "")))
		if active_id.is_empty() and draft().has("submission"):
			_sync_submission()


func _workspace_changed(topic: String) -> void:
	if topic in ["draft:" + draft_key(), "draft:comment:" + active_id]:
		changed.emit()


func route(id := "") -> String:
	return "/api/v1/docs/" + (active_id if id.is_empty() else id).uri_encode()


func draft_key() -> String:
	return "document:" + ("new" if active_id.is_empty() else active_id)


func draft() -> Dictionary:
	return workspace.load_draft(draft_key())


func editable() -> bool:
	return workspace.can_edit() and not _forbidden and (active_id.is_empty() or not document.is_empty()) and not saving and not draft().has("submission")


func update_draft(title: String, body: String) -> void:
	if not editable():
		return
	var value := draft()
	if value.is_empty():
		value = {"base_version": document.get("version", 0), "base_md": document.get("body_md", ""), "base_title": document.get("title", "")}
	value.title = title
	value.body_md = body
	if not workspace.save_draft(draft_key(), value):
		status = "无法保存本机草稿，请先复制内容。"
		changed.emit()


func refresh_list() -> void:
	var attempt := _generation
	var result: Dictionary = await workspace.read("documents", "/api/v1/docs")
	if attempt != _generation:
		return
	if result.status == 200:
		documents = result.data.get("docs", []).duplicate(true)
	else:
		status = workspace.error_message(result.status)
	changed.emit()


func open(id: String) -> void:
	if saving or (draft().has("submission") and id != active_id):
		status = "当前文档的保存回执仍待核对，完成同步后可切换文档。"
		changed.emit()
		return
	_selection += 1
	_close_room()
	active_id = id
	workspace.save_draft("document-selection", {"id": id})
	document = {}
	detail = {}
	conflict = {}
	_forbidden = false
	status = "新建文档 · 草稿保存在此设备" if id.is_empty() else "正在读取文档…"
	changed.emit()
	if not id.is_empty():
		await refresh()


func refresh() -> void:
	if active_id.is_empty():
		return
	if _refreshing:
		_refresh_again = true
		return
	var attempt := _generation
	var selection := _selection
	_refreshing = true
	var result: Dictionary = await workspace.read("document:" + active_id, route())
	if attempt != _generation or selection != _selection:
		return
	_refreshing = false
	if result.status == 200:
		_apply_head(result.data)
		if not _room:
			_room = session.join_document_room(active_id)
		if draft().has("submission") and not saving:
			_sync_submission()
	else:
		status = workspace.error_message(result.status)
		if result.status in [403, 404]:
			_forbidden = true
			document.clear()
			detail.clear()
			_close_room()
	changed.emit()
	if _refresh_again:
		_refresh_again = false
		refresh.call_deferred()


func _apply_head(value: Dictionary) -> void:
	if value.get("id") != active_id or int(value.get("version", 0)) < int(document.get("version", 0)):
		return
	document = value.duplicate(true)
	_forbidden = false
	var local := draft()
	status = tr("v%d · 已同步") % int(document.version)
	if not local.is_empty():
		status += tr(" · 本机有未提交草稿")
		if int(local.get("base_version", 0)) != int(document.version):
			status += tr("，保存时将比较双方修改")
	changed.emit()


func save() -> void:
	if not editable() or not conflict.is_empty():
		return
	var value := draft()
	if str(value.get("title", "")).strip_edges().is_empty():
		status = "请填写文档标题。"
		changed.emit()
		return
	var payload := {"title": value.title, "body_md": value.body_md, "call_id": workspace.new_id()}
	if active_id.is_empty():
		payload.lang = workspace.language
	if not active_id.is_empty():
		payload.expected_version = value.base_version
	value.submission = payload
	if not workspace.save_draft(draft_key(), value):
		status = "无法记录提交，请先复制草稿再重试。"
		changed.emit()
		return
	await _sync_submission()


func _sync_submission() -> void:
	if saving or session.get_identity().is_empty():
		return
	var value := draft()
	if not value.has("submission"):
		return
	var attempt := _generation
	var selection := _selection
	var key := draft_key()
	var creating := active_id.is_empty()
	saving = true
	status = "正在同步文档…"
	changed.emit()
	# The persisted call_id and exact payload use the service's receipt replay contract.
	var reply: Dictionary = await workspace.write("document-save", HTTPClient.METHOD_POST if creating else HTTPClient.METHOD_PATCH, "/api/v1/docs" if creating else route(), value.submission)
	if attempt != _generation or selection != _selection:
		return
	saving = false
	if reply.status == 200 and reply.data.has("id"):
		workspace.clear_draft(key)
		active_id = str(reply.data.id)
		workspace.save_draft("document-selection", {"id": active_id})
		conflict.clear()
		_apply_head(reply.data)
		refresh_list()
		if not _room:
			_room = session.join_document_room(active_id)
	elif reply.status == 409 and not creating:
		saving = true
		await _merge(value)
		if attempt != _generation or selection != _selection:
			return
		saving = false
	elif reply.status == 0 or reply.status >= 500:
		status = "保存回执待核对；草稿和提交编号已保留，连接恢复后继续同步。"
		_retry = _backoff
		_backoff = minf(30.0, _backoff * 2.0)
	else:
		value.erase("submission")
		workspace.save_draft(key, value)
		status = workspace.error_message(reply.status, true)
	changed.emit()


func _merge(value: Dictionary) -> void:
	var attempt := _generation
	var selection := _selection
	var head: Dictionary = await workspace.read("document-head", route())
	if attempt != _generation or selection != _selection:
		return
	value.erase("submission")
	workspace.save_draft(draft_key(), value)
	if head.status != 200:
		status = workspace.error_message(head.status)
		return
	_apply_head(head.data)
	var preview: Dictionary = await workspace.write("document-merge", HTTPClient.METHOD_POST, route() + "/merge/preview", {"base_md": value.base_md, "local_md": value.body_md, "expected_version": value.base_version})
	if attempt != _generation or selection != _selection:
		return
	if preview.status == 200 and int(preview.data.remote_version) != int(head.data.version):
		# The title and body must come from one server revision. Preserve the old
		# draft baseline so the next save compares both fields again.
		status = workspace.error_message(409, true)
		return
	var title_conflict: bool = head.data.title != value.base_title and value.title != value.base_title and head.data.title != value.title
	if preview.status == 200 and not title_conflict:
		value.base_md = preview.data.remote_md
		value.base_version = preview.data.remote_version
		value.body_md = preview.data.body_md
		if value.title == value.base_title:
			value.title = head.data.title
		value.base_title = head.data.title
		workspace.save_draft(draft_key(), value)
		status = "已合并互不冲突的修改；请预览并再次保存。"
	elif preview.status == 409 or title_conflict:
		conflict = head.data.duplicate(true)
		status = "同一内容已被他人修改。请比较服务器版本，编辑草稿后确认解决冲突。"
	else:
		status = workspace.error_message(preview.status, true)


func resolve_conflict() -> void:
	if conflict.is_empty() or not editable():
		return
	var value := draft()
	value.base_md = conflict.body_md
	value.base_title = conflict.title
	value.base_version = conflict.version
	workspace.save_draft(draft_key(), value)
	conflict.clear()
	status = "已采用核对后的草稿；点击保存提交新版本。"
	changed.emit()


func discard_draft() -> void:
	if not editable():
		return
	workspace.clear_draft(draft_key())
	conflict.clear()
	status = "已放弃此设备上的草稿。"
	changed.emit()


func load_details(kind: String) -> void:
	if active_id.is_empty() or kind not in ["versions", "comments", "shares", "external-links", "links"]:
		return
	var attempt := _generation
	var selection := _selection
	var result: Dictionary = await workspace.read("document-detail:" + kind, route() + "/" + kind)
	if attempt != _generation or selection != _selection:
		return
	if result.status == 200:
		detail[kind] = result.data.duplicate(true)
	else:
		status = workspace.error_message(result.status)
	changed.emit()


func action(method: int, suffix: String, payload: Dictionary, refresh_kind := "") -> Dictionary:
	if active_id.is_empty() or workspace.busy("document-action"):
		return {"status": 0, "data": {}}
	var attempt := _generation
	var selection := _selection
	var result: Dictionary = await workspace.write("document-action", method, route() + suffix, payload)
	if attempt != _generation or selection != _selection:
		return {"status": 0, "data": {}, "stale": true}
	status = "已保存" if result.status >= 200 and result.status < 300 else workspace.error_message(result.status, true)
	if result.status >= 200 and result.status < 300:
		if not refresh_kind.is_empty():
			load_details(refresh_kind)
		if result.data.get("id") == active_id and result.data.has("body_md"):
			_apply_head(result.data)
	changed.emit()
	return result


func compare_versions(from_version: int, to_version: int) -> void:
	var attempt := _generation
	var selection := _selection
	var result: Dictionary = await workspace.read("document-diff", route() + "/diff?from_version=%d&to_version=%d" % [from_version, to_version])
	if attempt != _generation or selection != _selection:
		return
	if result.status == 200:
		detail.diff = str(result.data.get("diff", ""))
	else:
		status = workspace.error_message(result.status)
	changed.emit()


func resolve_comment(id: String, resolved: bool) -> void:
	var attempt := _generation
	var selection := _selection
	var result: Dictionary = await workspace.write("document-comment", HTTPClient.METHOD_PATCH, "/api/v1/comments/" + id.uri_encode(), {"resolved": resolved})
	if attempt != _generation or selection != _selection:
		return
	status = "评论已更新" if result.status == 200 else workspace.error_message(result.status, true)
	load_details("comments")
	changed.emit()


func export_file(format: String, path: String) -> void:
	if active_id.is_empty() or format not in ["md", "html", "docx", "pdf"]:
		return
	var attempt := _generation
	var temporary: String = path + "." + workspace.new_id() + ".part"
	var result: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route() + "/export/file?format=" + format, {}, 60.0, temporary)
	if attempt != _generation or result.status != 200:
		DirAccess.remove_absolute(temporary)
		if attempt == _generation:
			status = workspace.error_message(result.status)
	elif DirAccess.rename_absolute(temporary, path) == OK:
		status = "文档已导出。"
	else:
		DirAccess.remove_absolute(temporary)
		status = "无法写入所选位置，请检查目录权限。"
	changed.emit()


func _close_room() -> void:
	if _room:
		_room.close()
	_room = null
	_refreshing = false
	_refresh_again = false
	collaborators.clear()
	_ping = 0.0
	_retry = 1.0
	_backoff = 1.0


func _process(delta: float) -> void:
	if session == null or session.get_identity().is_empty():
		return
	_retry -= delta
	if _retry <= 0 and draft().has("submission") and not saving:
		_retry = _backoff
		_sync_submission()
	if active_id.is_empty():
		return
	if not _room:
		if _retry <= 0:
			_retry = _backoff
			_backoff = minf(30.0, _backoff * 2.0)
			refresh()
		return
	_room.poll()
	_ping -= delta
	if _room.get_ready_state() == WebSocketPeer.STATE_OPEN and _ping <= 0:
		_room.send_text(JSON.stringify({"type": "ping"}))
		_ping = 15.0
	if _room.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		var code := _room.get_close_code()
		_room = null
		if code in [4401, 4403, 4404]:
			# Re-read HTTP authority; local drafts remain private and are never sent anonymously.
			refresh()
		return
	while _room and _room.get_available_packet_count() > 0:
		var event: Variant = JSON.parse_string(_room.get_packet().get_string_from_utf8())
		if event is Dictionary and event.get("type") in ["snapshot", "updated"] and event.get("doc") is Dictionary:
			_backoff = 1.0
			_apply_head(event.doc)
		elif event is Dictionary and event.get("type") == "changed":
			refresh()
		elif event is Dictionary and event.get("type") == "presence":
			collaborators = event.get("actors", []).duplicate()
			changed.emit()


func _exit_tree() -> void:
	_close_room()
