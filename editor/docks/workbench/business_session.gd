@tool
extends VBoxContainer

signal identity_resetting
signal identity_changed
signal authenticated

var _controller: Node:
	get:
		return get_meta("session_controller", null)
var _origin: String:
	get:
		return _controller.origin if is_instance_valid(_controller) else ""
var _status := Label.new()
var _form := VBoxContainer.new()
var _email := LineEdit.new()
var _secret := LineEdit.new()
var _project := LineEdit.new()
var _sign_out := Button.new()


func _ready() -> void:
	if not is_instance_valid(_controller):
		push_error("Native workbench requires the editor-owned Tianxuan session")
		return
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
	_controller.identity_resetting.connect(func(): identity_resetting.emit())
	_controller.identity_changed.connect(_identity_updated)
	_controller.authenticated.connect(func(): authenticated.emit())
	_controller.status_changed.connect(_update_status)
	_identity_updated()


func install_paragraph_suggestion(script: Script) -> void:
	if not is_node_ready():
		await ready
	get_node("WorkbenchDocuments").install_paragraph_suggestion(script)


func redact_credentials(text: String) -> String:
	return _controller.redact_credentials(text)


func get_identity() -> Dictionary:
	return _controller.get_identity()


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


func _update_status() -> void:
	_status.text = _controller.status_text
	if "重新认证" in _status.text:
		_form.show()


func _identity_updated() -> void:
	_update_status()
	var identity := get_identity()
	_sign_out.visible = not identity.is_empty()
	if not identity.is_empty():
		_project.text = identity.project
		_email.clear()
		_form.hide()
	identity_changed.emit()


func _reset(message: String) -> void:
	_controller.reset(message)


func _authenticate(email: String, secret: String, project: String) -> void:
	await _controller.authenticate(email, secret, project)


func api_request(method: int, route: String, payload: Dictionary = {}, timeout_seconds: float = 12.0, download_path := "") -> Dictionary:
	return await _controller.api_request(method, route, payload, timeout_seconds, download_path)


func join_document_room(id: String) -> WebSocketPeer:
	return _controller.join_document_room(id)


class DocumentView extends AcceptDialog:
	signal target_changed
	signal revision_cleared

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
	var history := Button.new()
	var signoff := Button.new()
	var progress := Button.new()
	var composer := ConfirmationDialog.new()
	var draft_title := LineEdit.new()
	var draft_body := TextEdit.new()
	var draft_status := Label.new()
	var collaboration: Node
	var live_document := false
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
		history.text = "版本历史"
		history.name = "OpenDocumentHistory"
		history.disabled = true
		actions.add_child(history)
		signoff.text = "设计签认"
		signoff.disabled = true
		actions.add_child(signoff)
		progress.text = "查看偃师设计阶段"
		progress.disabled = true
		box.add_child(progress)
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
		if collaboration:
			collaboration.end_draft()
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
		if existing and live_document:
			editing.base_md = collaboration.base_md
		call_id = Crypto.new().generate_random_bytes(16).hex_encode()
		composer.title = "编辑正文 · v%d" % editing.version if existing else "新建设计"
		composer.get_ok_button().disabled = false
		draft_title.visible = not existing
		draft_title.editable = true
		draft_body.editable = true
		draft_body.text = body.text if existing else ""
		composer.popup_centered()
		if existing and live_document:
			collaboration.begin_draft()
		if existing:
			draft_body.grab_focus()
		else:
			draft_title.grab_focus()

	func edit_selected_paragraph() -> void:
		var paragraph := selected_paragraph()
		if paragraph <= 0:
			return
		var span := ranges[paragraph - 1]
		_compose(true)
		draft_body.set_caret_line(span.x)
		draft_body.select(span.x, 0, span.y, draft_body.get_line(span.y).length())
		draft_body.center_viewport_to_caret()

	func _save_draft() -> void:
		if call_id.is_empty() or composer.get_ok_button().disabled:
			return
		if editing.is_empty() and draft_title.text.strip_edges().is_empty():
			draft_status.text = "请填写文档标题。"
			return
		var attempt := call_id
		var panel = get_tree().root.find_child("WorkbenchBusinessModules", true, false)
		var scope: Array = panel.document_edit_scope() if is_instance_valid(panel) else []
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
		var reply: Dictionary
		if editing.has("base_md"):
			reply = await collaboration.save(route, payload, editing, attempt)
		else:
			reply = await session.api_request(method, route, payload)
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
			if reply.status == 409 and reply.data.get("status") == "conflict":
				collaboration.show_conflict(reply.data)
			elif reply.status == 409:
				draft_status.text = "文档修订发生冲突。请复制草稿，重开最新修订再编辑。"
			return
		var saved: Dictionary = reply.data
		if str(saved.get("id", "")).is_empty() or int(saved.get("version", 0)) < 1:
			draft_status.text = "保存回执不完整。再次点击保存可核对此次提交。"
			return
		if not editing.is_empty() and saved.id == editing.document_id and int(saved.version) > int(editing.version):
			if is_instance_valid(panel) and not scope.is_empty():
				panel.stage_document_edit(saved.id, int(saved.version), scope)
		if collaboration:
			collaboration.remove_draft()
		_clear_draft()
		await open_saved(saved, 1)

	func open_saved(saved: Dictionary, paragraph: int = 1) -> void:
		var row := -1
		for index in documents.item_count:
			if documents.get_item_metadata(index).id == saved.id:
				row = index
				break
		if collaboration and collaboration.document_id == saved.id:
			saved.version = maxi(int(saved.version), collaboration.notified_version)
		row = _document_row(saved, row)
		documents.select(row)
		await open_document(saved.id, int(saved.version), paragraph, true)

	func _document_row(item: Dictionary, index: int = -1) -> int:
		var label := "%s · v%d · %s" % [item.title, item.version, item.id]
		if index == -1:
			index = documents.add_item(label)
		else:
			documents.set_item_text(index, label)
		documents.set_item_metadata(index, {"id": str(item.id), "version": int(item.version)})
		return index

	func _clear_body() -> void:
		revision_cleared.emit()
		progress.disabled = true
		signoff.disabled = true
		history.disabled = true
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
		if collaboration:
			collaboration.leave()
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
		open_document(selected.id, selected.version, 1, true)

	# Paragraph numbers refer to non-blank blocks in this exact Markdown revision.
	func open_document(id: String, version: int, paragraph: int, follow: bool = false) -> void:
		live_document = false
		if collaboration and (not follow or id != collaboration.document_id):
			if composer.visible and editing.has("base_md"):
				_clear_draft()
			collaboration.leave()
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
		if follow and collaboration:
			live_document = true
			collaboration.watch(id, version, reply.data.body_md)
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
		history.disabled = false
		progress.disabled = false
		signoff.disabled = false
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
