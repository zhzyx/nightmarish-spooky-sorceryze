@tool
extends VBoxContainer

signal identity_changed

var _origin: String
var _token := ""
var _owned_session := false
var _identity := {}
var _generation := 0
var _status := Label.new()
var _form := VBoxContainer.new()
var _email := LineEdit.new()
var _secret := LineEdit.new()
var _project := LineEdit.new()
var _sign_out := Button.new()


func _ready() -> void:
	_origin = OS.get_environment("TIANXUAN_API").strip_edges().trim_suffix("/")
	if _origin.is_empty():
		_origin = "http://127.0.0.1:8000"
	_status.name = "SessionStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	var actions := HBoxContainer.new()
	add_child(actions)
	var choose := Button.new()
	choose.name = "ChooseAccount"
	choose.text = "天璇账号"
	choose.pressed.connect(_toggle_form)
	actions.add_child(choose)
	var document_view := DocumentView.new()
	document_view.name = "WorkbenchDocuments"
	document_view.session = self
	add_child(document_view)
	var open_docs := Button.new()
	open_docs.name = "OpenWorkbenchDocuments"
	open_docs.text = "设计文档"
	open_docs.pressed.connect(document_view.browse)
	actions.add_child(open_docs)
	_sign_out.name = "SignOut"
	_sign_out.text = "退出"
	_sign_out.pressed.connect(_sign_out_pressed)
	actions.add_child(_sign_out)
	add_child(_form)
	var service := Label.new()
	service.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service.text = "服务地址 " + _origin
	_form.add_child(service)
	_email.name = "AccountEmail"
	_email.placeholder_text = "账号邮箱（使用个人密钥时留空）"
	_form.add_child(_email)
	_secret.name = "AccountSecret"
	_secret.placeholder_text = "密码或个人访问密钥"
	_secret.secret = true
	_form.add_child(_secret)
	_project.name = "BusinessProject"
	_project.placeholder_text = "业务项目"
	_project.text = OS.get_environment("TIANXUAN_PROJECT").strip_edges()
	if _project.text.is_empty():
		_project.text = "workspace"
	_form.add_child(_project)
	var submit := Button.new()
	submit.name = "Authenticate"
	submit.text = "登录此项目"
	submit.pressed.connect(_submit)
	_form.add_child(submit)
	_form.hide()
	_reset("尚未登录天璇")
	var supplied := OS.get_environment("TIANXUAN_TOKEN")
	if not supplied.is_empty():
		_authenticate("", supplied, _project.text)


func install_paragraph_suggestion(script: Script) -> void:
	if not is_node_ready():
		await ready
	get_node("WorkbenchDocuments").install_paragraph_suggestion(script)


func redact_credentials(text: String) -> String:
	return text if _token.is_empty() else text.replace(_token, "[REDACTED]")


func get_identity() -> Dictionary:
	return _identity.duplicate()


func _toggle_form() -> void:
	_form.visible = not _form.visible
	if _form.visible:
		_email.grab_focus()
	else:
		_secret.clear()


func _submit() -> void:
	var secret := _secret.text
	_secret.clear()
	_authenticate(_email.text.strip_edges(), secret, _project.text.strip_edges())


func _sign_out_pressed() -> void:
	_reset("已退出天璇")
	_secret.clear()
	_email.clear()
	_form.hide()


func _reset(message: String) -> void:
	_generation += 1
	var old_token := _token
	var revoke := _owned_session
	_token = ""
	_owned_session = false
	_identity.clear()
	_sign_out.hide()
	_status.text = message
	identity_changed.emit()
	if revoke:
		_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", old_token, {})


func _matches(value: String, pattern: String) -> bool:
	var expression := RegEx.new()
	return expression.compile(pattern) == OK and expression.search(value) != null


func _authenticate(email: String, secret: String, project: String) -> void:
	_reset("正在验证天璇账号…")
	var attempt := _generation
	var secure_origin := _matches(_origin, "^https://([A-Za-z0-9.-]+|\\[[0-9A-Fa-f:]+\\])(:[0-9]{1,5})?$")
	var loopback := _matches(_origin, "^http://(127\\.0\\.0\\.1|localhost|\\[::1\\])(:[0-9]{1,5})?$")
	if not (secure_origin or loopback):
		_status.text = "天璇服务需要 HTTPS 或本机回环地址"
		return
	if not _matches(project, "^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}(/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})?$"):
		_status.text = "请输入有效的业务项目"
		return
	if secret.is_empty() or (email.is_empty() and ("\r" in secret or "\n" in secret)):
		_status.text = "请输入有效凭据以重新认证"
		return
	var credential := secret
	if not email.is_empty():
		var login := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/session", "", {"email": email, "password": secret})
		credential = str(login.data.get("token", ""))
		if attempt != _generation:
			if not credential.is_empty():
				_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", credential, {})
			return
		if login.status != 200 or credential.is_empty():
			_status.text = "登录失败，请重新认证" if login.status in [401, 403] else "无法登录天璇，请检查服务后重试"
			return
	_token = credential
	_owned_session = not email.is_empty()
	var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", credential, {})
	if attempt != _generation:
		return
	if me.status != 200 or str(me.data.get("id", "")).is_empty() or str(me.data.get("role", "")).is_empty():
		_reset("凭据失效，请重新认证" if me.status in [401, 403] else "无法核实天璇身份，请重试")
		_form.show()
		return
	_identity = {"id": me.data.id, "name": me.data.get("name", ""), "role": me.data.role, "project": project}
	_status.text = "%s · %s · %s" % [_identity.name, _identity.role, project]
	_sign_out.show()
	_email.clear()
	_form.hide()
	identity_changed.emit()


# Routes belong to the configured deployment. Each request captures its verified session.
func api_request(method: int, route: String, payload: Dictionary = {}, timeout_seconds: float = 12.0) -> Dictionary:
	if _identity.is_empty():
		return {"status": 401, "data": {}}
	if not route.begins_with("/api/v1/") or "#" in route or "\\" in route or "\n" in route or "\r" in route:
		return {"status": 0, "data": {}}
	for parameter in route.get_slice("?", 1).split("&", false):
		if parameter.get_slice("=", 0).uri_decode() == "project":
			return {"status": 0, "data": {}}
	var scoped_route := route + ("&" if "?" in route else "?") + "project=" + str(_identity.project).uri_encode()
	var attempt := _generation
	var reply := await _exchange(method, scoped_route, _token, payload, timeout_seconds)
	if attempt != _generation:
		return {"status": 0, "data": {}}
	if reply.status == 401:
		_reset("凭据失效，请重新认证")
		_form.show()
	return reply


func _exchange(method: int, route: String, credential: String, payload: Dictionary, timeout_seconds: float = 12.0) -> Dictionary:
	var http := HTTPRequest.new()
	http.max_redirects = 0
	http.timeout = timeout_seconds
	http.body_size_limit = 8 * 1024 * 1024
	add_child(http)
	var headers := PackedStringArray(["Accept: application/json"])
	if not credential.is_empty():
		headers.append("Authorization: Bearer " + credential)
	var body := ""
	if method not in [HTTPClient.METHOD_GET, HTTPClient.METHOD_HEAD]:
		headers.append("Content-Type: application/json")
		body = JSON.stringify(payload)
	var reply := {"status": 0, "data": {}}
	if http.request(_origin + route, headers, method, body) == OK:
		var response: Array = await http.request_completed
		if response[0] == HTTPRequest.RESULT_SUCCESS:
			reply.status = int(response[1])
			var bytes: PackedByteArray = response[3]
			if not bytes.is_empty():
				var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
				if parsed is Dictionary:
					reply.data = parsed
	http.queue_free()
	return reply


class DocumentView extends AcceptDialog:
	signal target_changed

	var session: Node
	var actions := HBoxContainer.new()
	var raw_body := ""
	var raw_spans: Array[Vector2i] = []
	var documents := ItemList.new()
	var paragraphs := OptionButton.new()
	var body := TextEdit.new()
	var status := Label.new()
	var reference := {}
	var cite := Button.new()
	var ranges: Array[Vector2i] = []
	var generation := 0
	var create := Button.new()
	var edit := Button.new()
	var composer := ConfirmationDialog.new()
	var draft_title := LineEdit.new()
	var draft_body := TextEdit.new()
	var draft_status := Label.new()
	var editing := {}
	var call_id := ""

	func _ready() -> void:
		title = "设计文档"
		var box := VBoxContainer.new()
		box.custom_minimum_size = Vector2(510,360) * EditorInterface.get_editor_scale()
		add_child(box)
		documents.name = "DocumentList"
		documents.custom_minimum_size.y = 95 * EditorInterface.get_editor_scale()
		documents.item_selected.connect(_select_document)
		box.add_child(documents)
		box.add_child(actions)
		create.text = "新建设计"
		create.pressed.connect(_compose.bind(false))
		actions.add_child(create)
		edit.text = "编辑正文"
		edit.disabled = true
		edit.pressed.connect(_compose.bind(true))
		actions.add_child(edit)
		_setup_composer()
		status.name = "DocumentStatus"
		box.add_child(status)
		paragraphs.name = "DocumentParagraph"
		paragraphs.item_selected.connect(_jump)
		box.add_child(paragraphs)
		body.name = "DocumentBody"
		body.editable = false
		body.selecting_enabled = true
		body.deselect_on_focus_loss_enabled = false
		body.caret_changed.connect(sync_selected_paragraph)
		body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		body.size_flags_vertical = Control.SIZE_EXPAND_FILL
		box.add_child(body)
		cite.name = "CiteDocumentParagraph"
		cite.text = "引用此段"
		cite.disabled = true
		cite.pressed.connect(_cite)
		box.add_child(cite)
		get_ok_button().text = "关闭"
		session.identity_changed.connect(reset_view)

	func install_paragraph_suggestion(script: Script) -> void:
		var dialog = script.new()
		dialog.view = self
		add_child(dialog)

	func selected_paragraph() -> int:
		if body.get_caret_count() != 1 or not body.has_selection() or body.get_selection_from_column() != 0:
			return 0
		var lines := Vector2i(body.get_selection_from_line(), body.get_selection_to_line())
		if body.get_selection_to_column() != body.get_line(lines.y).length():
			return 0
		return ranges.find(lines) + 1

	func sync_selected_paragraph() -> int:
		var selected := selected_paragraph()
		if selected > 0 and not reference.is_empty() and reference.paragraph != selected:
			paragraphs.select(selected - 1)
			reference.paragraph = selected
			target_changed.emit()
		return selected

	func _setup_composer() -> void:
		composer.dialog_hide_on_ok = false
		composer.get_ok_button().text = "保存"
		composer.get_cancel_button().text = "取消"
		composer.confirmed.connect(_save_draft)
		composer.canceled.connect(_clear_draft)
		add_child(composer)
		var fields := VBoxContainer.new()
		fields.custom_minimum_size = Vector2(480, 310) * EditorInterface.get_editor_scale()
		composer.add_child(fields)
		draft_title.placeholder_text = "文档标题"
		fields.add_child(draft_title)
		draft_body.placeholder_text = "编写设计正文，使用空行分段"
		draft_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		draft_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
		fields.add_child(draft_body)
		draft_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		fields.add_child(draft_status)

	func _clear_draft() -> void:
		composer.hide()
		draft_title.clear()
		draft_body.clear()
		draft_status.text = ""
		editing.clear()
		call_id = ""

	func _compose(existing: bool) -> void:
		if session.get_identity().is_empty() or (existing and reference.is_empty()):
			return
		_clear_draft()
		editing = reference.duplicate() if existing else {}
		call_id = Crypto.new().generate_random_bytes(16).hex_encode()
		composer.title = "编辑正文 · v%d" % editing.version if existing else "新建设计"
		composer.get_ok_button().disabled = false
		draft_title.visible = not existing
		draft_title.editable = true
		draft_body.editable = true
		draft_body.text = body.text if existing else ""
		composer.popup_centered()
		if existing:
			draft_body.grab_focus()
		else:
			draft_title.grab_focus()

	func _save_draft() -> void:
		if call_id.is_empty() or composer.get_ok_button().disabled:
			return
		if editing.is_empty() and draft_title.text.strip_edges().is_empty():
			draft_status.text = "请填写文档标题。"
			return
		var attempt := call_id
		var payload := {"body_md": draft_body.text, "call_id": call_id}
		var method := HTTPClient.METHOD_POST
		var route := "/api/v1/docs"
		if editing.is_empty():
			payload.title = draft_title.text.strip_edges()
		else:
			method = HTTPClient.METHOD_PATCH
			route += "/" + str(editing.document_id).uri_encode()
			payload.expected_version = editing.version
		composer.get_ok_button().disabled = true
		draft_title.editable = false
		draft_body.editable = false
		draft_status.text = "正在保存…"
		var reply: Dictionary = await session.api_request(method, route, payload)
		if attempt != call_id:
			return
		composer.get_ok_button().disabled = false
		if reply.status == 0 or reply.status >= 500:
			draft_status.text = "尚未收到保存回执。再次点击保存可核对此次提交。"
			return
		if reply.status != 200:
			draft_title.editable = true
			draft_body.editable = true
			call_id = Crypto.new().generate_random_bytes(16).hex_encode()
			draft_status.text = "保存失败，请检查文档权限。" if reply.status == 403 else "保存失败（%d）。草稿已保留。" % reply.status
			if reply.status == 409:
				draft_status.text = "文档修订发生冲突。请复制草稿，重开最新修订再编辑。"
			return
		var saved: Dictionary = reply.data
		if str(saved.get("id", "")).is_empty() or int(saved.get("version", 0)) < 1:
			draft_status.text = "保存回执不完整。再次点击保存可核对此次提交。"
			return
		_clear_draft()
		await open_saved(saved, 1)

	func open_saved(saved: Dictionary, paragraph: int) -> void:
		var row := -1
		for index in documents.item_count:
			if documents.get_item_metadata(index).id == saved.id:
				row = index
				break
		row = _document_row(saved, row)
		documents.select(row)
		await open_document(saved.id, int(saved.version), paragraph)

	func _document_row(item: Dictionary, index: int = -1) -> int:
		var label := "%s · v%d · %s" % [item.title, item.version, item.id]
		if index == -1:
			index = documents.add_item(label)
		else:
			documents.set_item_text(index, label)
		documents.set_item_metadata(index, {"id": str(item.id), "version": int(item.version)})
		return index

	func _clear_body() -> void:
		edit.disabled = true
		cite.disabled = true
		reference.clear()
		body.clear()
		ranges.clear()
		raw_body = ""
		raw_spans.clear()
		target_changed.emit()
		paragraphs.clear()
		paragraphs.disabled = true

	func reset_view() -> void:
		generation += 1
		_clear_draft()
		create.disabled = session.get_identity().is_empty()
		documents.clear()
		_clear_body()
		status.text = ""
		hide()

	func browse() -> void:
		reset_view()
		popup_centered()
		if session.get_identity().is_empty():
			status.text = "请先登录天璇。"
			return
		var request := generation
		status.text = "正在读取文档…"
		var result: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs")
		if request != generation:
			return
		if result.status != 200 or not result.data.get("docs") is Array:
			status.text = "无法读取此账号的文档。"
			return
		for item in result.data.docs:
			_document_row(item)
		status.text = "请选择文档。" if documents.item_count else "此账号没有可读取的文档。"

	func _select_document(index: int) -> void:
		var selected: Dictionary = documents.get_item_metadata(index)
		open_document(selected.id, selected.version, 1)

	# Paragraph numbers refer to non-blank blocks in this exact Markdown revision.
	func open_document(id: String, version: int, paragraph: int) -> void:
		generation += 1
		var request := generation
		_clear_body()
		if not visible:
			popup_centered()
		status.text = "正在读取指定修订…"
		if id.is_empty() or version < 1 or paragraph < 1 or session.get_identity().is_empty():
			status.text = "文档、修订、段落或登录身份无效。"
			return
		var route := "/api/v1/docs/" + id.uri_encode() + "/versions/" + str(version)
		var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
		if request != generation:
			return
		if reply.status != 200 or int(reply.data.get("version",0)) != version or not reply.data.get("body_md") is String:
			status.text = "无法读取指定文档修订。"
			return
		raw_body = reply.data.body_md
		var lines := raw_body.split("\n")
		var offset := 0
		var start_offset := 0
		var end_offset := 0
		body.text = raw_body.replace("\r\n","\n")
		var start := -1
		for line in range(body.get_line_count() + 1):
			var blank := line == body.get_line_count() or body.get_line(line).strip_edges().is_empty()
			if not blank and start < 0:
				start = line
				start_offset = offset
			elif blank and start >= 0:
				ranges.append(Vector2i(start, line - 1))
				raw_spans.append(Vector2i(start_offset, end_offset))
				paragraphs.add_item("%d · %s" % [ranges.size(),body.get_line(start).strip_edges().left(54)])
				start = -1
			if line < lines.size():
				end_offset = offset + lines[line].trim_suffix("\r").length()
				offset += lines[line].length() + 1
		if paragraph > ranges.size() and not (ranges.is_empty() and paragraph == 1):
			_clear_body()
			status.text = "此修订没有指定段落。"
			return
		reference = {"document_id": id, "version": version, "paragraph": 0}
		edit.disabled = false
		status.text = "%s · v%d · 作者 %s" % [id, version, reply.data.get("author", "未知")]
		paragraphs.disabled = ranges.is_empty()
		if not ranges.is_empty():
			paragraphs.select(paragraph - 1)
			_jump(paragraph - 1)

	func _jump(index: int) -> void:
		if index < 0 or index >= ranges.size():
			return
		target_changed.emit()
		var span := ranges[index]
		body.set_caret_line(span.x)
		body.select(span.x,0,span.y,body.get_line(span.y).length())
		body.center_viewport_to_caret()
		reference.paragraph = index + 1
		cite.disabled = false

	func _cite() -> void:
		if reference.is_empty() or cite.disabled:
			return
		var panel = get_tree().root.find_child("WorkbenchBusinessModules", true, false)
		if not is_instance_valid(panel) or not panel.stage_document_reference(reference):
			status.text = "无法向当前会话加入段落引用。"
			return
		hide()
