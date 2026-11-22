@tool
extends VBoxContainer

const ROUTE := "/api/v1/workspace/conversations/"
const STAGES := {"direction": "方向", "plan": "策划", "design": "详设"}

var dialog := AcceptDialog.new()
var summary := TextEdit.new()
var stage := OptionButton.new()
var revisions := OptionButton.new()
var body := TextEdit.new()
var event := TextEdit.new()
var reason := LineEdit.new()
var confirm := Button.new()
var send_back := Button.new()
var reload_button := Button.new()
var notice := Label.new()
var view
var panel
var generation := 0
var chat_id := ""
var doc_id := ""
var doc_version := 0
var record := {}
var signoff := ""
var busy := false
var choose_current := false


func _ready() -> void:
	hide()
	var session := get_parent()
	if not session.is_node_ready():
		await session.ready
	view = session.get_node("WorkbenchDocuments")
	view.progress.pressed.connect(_open_document)
	view.revision_cleared.connect(_document_cleared)
	view.visibility_changed.connect(_view_visibility_changed)
	session.identity_changed.connect(dialog.hide)
	session.add_child(dialog)
	dialog.exclusive = true
	dialog.title = "偃师设计阶段"
	dialog.get_ok_button().text = "关闭"
	dialog.visibility_changed.connect(_visibility_changed)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(530, 380) * EditorInterface.get_editor_scale()
	dialog.add_child(box)
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for field: TextEdit in [summary, event, body]:
		field.editable = false
		field.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	summary.custom_minimum_size.y = 100 * EditorInterface.get_editor_scale()
	event.custom_minimum_size.y = 60 * EditorInterface.get_editor_scale()
	box.add_child(summary)
	var selection := HBoxContainer.new()
	box.add_child(selection)
	selection.add_child(stage)
	selection.add_child(revisions)
	for key in STAGES:
		stage.add_item(STAGES[key])
		stage.set_item_metadata(stage.item_count - 1, key)
	stage.item_selected.connect(_show_stage)
	revisions.item_selected.connect(_show_revision)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(body)
	box.add_child(event)
	box.add_child(reason)
	reason.placeholder_text = "填写本修订的退回意见"
	reason.max_length = 8000
	reason.text_changed.connect(func(_value): _actions())
	var actions := HBoxContainer.new()
	box.add_child(actions)
	confirm.pressed.connect(_decide.bind(false))
	send_back.pressed.connect(_decide.bind(true))
	reload_button.text = "刷新"
	reload_button.pressed.connect(_read)
	for button: Button in [confirm, send_back, reload_button]:
		actions.add_child(button)
	box.add_child(notice)


func _view_visibility_changed() -> void:
	if not view.visible:
		_document_cleared()


func _document_cleared() -> void:
	if not doc_id.is_empty():
		dialog.hide()


func _visibility_changed() -> void:
	if not dialog.visible:
		generation += 1
		panel = null
		chat_id = ""
		doc_id = ""
		doc_version = 0
		record = {}
		_clear()


func _clear() -> void:
	summary.text = ""
	body.clear()
	event.text = ""
	notice.text = ""
	signoff = ""
	reason.clear()
	revisions.clear()
	_actions()


func _open_document() -> void:
	if view.reference.is_empty() or dialog.visible:
		return
	doc_id = view.reference.document_id
	doc_version = int(view.reference.version)
	_open(view)


func open_chat(id: String, from_panel: Control) -> void:
	if dialog.visible:
		return
	panel = from_panel
	chat_id = id
	_open(get_parent())


func _open(host: Node) -> void:
	if dialog.get_parent() != host:
		dialog.reparent(host)
	choose_current = true
	stage.select(0)
	dialog.popup_centered()
	_read()


func _read() -> void:
	generation += 1
	var attempt := generation
	busy = true
	record = {}
	_clear()
	notice.text = "正在读取阶段记录…"
	var session := get_parent()
	var path := ROUTE + chat_id.uri_encode()
	if not doc_id.is_empty():
		path = ROUTE + "for-document/%s/versions/%d" % [doc_id.uri_encode(), doc_version]
		var stamp: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/%s/versions/%d/signoff" % [doc_id.uri_encode(), doc_version])
		if attempt != generation:
			return
		signoff = "文档 v%d 签认回执读取失败" % doc_version
		if stamp.status == 200 and stamp.data.has("signoff"):
			var receipt = stamp.data.signoff
			if receipt == null:
				signoff = "文档 v%d 尚未签认" % doc_version
			elif receipt is Dictionary and receipt.get("document_id") == doc_id and int(receipt.get("version", 0)) == doc_version:
				signoff = "文档 v%d 签认 · %s · %s\n验收条件：%s" % [doc_version, receipt.confirmed_by, receipt.confirmed_at, receipt.acceptance]
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, path)
	if attempt != generation:
		return
	busy = false
	var data: Dictionary = reply.data
	if not doc_id.is_empty() and reply.status == 200 and data.get("document_id") == doc_id and int(data.get("version", 0)) == doc_version:
		summary.text = signoff
		if data.get("conversation") == null:
			notice.text = "这版文档没有此账号可读取的偃师阶段关联。"
			_actions()
			return
		chat_id = data.conversation
	elif reply.status != 200 or chat_id.is_empty() or data.get("id") != chat_id or not doc_id.is_empty():
		notice.text = "阶段记录读取失败（%d）。" % reply.status
		_actions()
		return
	record = data
	if is_instance_valid(panel) and panel.conversation.get("id") == chat_id:
		panel.conversation = data
		panel._render()
	_render()


func _render() -> void:
	var lines := PackedStringArray(["来源会话 " + chat_id])
	for key in STAGES:
		var active := _active(key)
		var state := "未开始" if active.is_empty() else "%s · r%d" % [_state(active), active.revision]
		lines.append("%s：%s" % [STAGES[key], state])
	if not signoff.is_empty():
		lines.append(signoff)
	if choose_current:
		for index in stage.item_count:
			stage.select(index)
			if not _active(stage.get_item_metadata(index)).get("confirmed_at"):
				break
		choose_current = false
	summary.text = "\n".join(lines)
	notice.text = ""
	_show_stage(stage.selected)


func _state(item: Dictionary) -> String:
	if item.get("returned_at"):
		return "已退回"
	if item.get("confirmed_at"):
		return "已确认"
	return "待确认"


func _active(key: String) -> Dictionary:
	for item in record.get("revisions", []):
		if item.stage == key and item.revision == record.current.get(key):
			return item
	return {}


func _show_stage(index: int) -> void:
	revisions.clear()
	var key: String = stage.get_item_metadata(index)
	for item in record.get("revisions", []):
		if item.stage != key:
			continue
		var current: bool = item.revision == record.current.get(key)
		revisions.add_item("r%d · %s%s" % [item.revision, _state(item), "（当前）" if current else "（历史）"])
		revisions.set_item_metadata(revisions.item_count - 1, item)
		if current:
			revisions.select(revisions.item_count - 1)
	_show_revision(revisions.selected)


func _selected() -> Dictionary:
	return revisions.get_item_metadata(revisions.selected) if revisions.selected >= 0 else {}


func _show_revision(_index: int) -> void:
	var item := _selected()
	body.text = item.get("body", "")
	if item.get("title"):
		body.text = "%s\n\n%s\n\n验收条件：%s" % [item.title, body.text, item.acceptance]
	reason.clear()
	event.text = ""
	if item.get("returned_at"):
		event.text = "退回人 %s · %s\n退回意见：%s" % [item.returned_by, item.returned_at, item.return_reason]
	elif item.get("confirmed_at"):
		event.text = "确认人 %s · %s" % [item.confirmed_by, item.confirmed_at]
	elif not item.is_empty():
		event.text = "草稿保存 · %s · %s" % [item.get("created_by", "未记录作者"), item.created_at]
	_actions()


func _actions() -> void:
	var item := _selected()
	var writable := false
	if not item.is_empty():
		writable = get_parent().get_identity().get("role") != "viewer" and doc_id.is_empty() and record.get("requirement_id") == null and item == _active(item.stage) and _state(item) == "待确认"
	var target := "" if item.is_empty() else " %s r%d" % [STAGES[item.stage], item.revision]
	confirm.text = "确认" + target
	send_back.text = "退回" + target
	stage.disabled = busy or record.is_empty()
	revisions.disabled = busy or item.is_empty()
	reload_button.disabled = busy
	confirm.disabled = busy or not writable
	reason.editable = not busy and writable
	send_back.disabled = confirm.disabled or reason.text.strip_edges().is_empty()


func _decide(returning: bool) -> void:
	if (send_back.disabled if returning else confirm.disabled) or not dialog.visible:
		return
	var item := _selected()
	var payload := {"expected_version": int(record.version), "revision": int(item.revision)}
	if returning:
		payload.reason = reason.text.strip_edges()
	busy = true
	_actions()
	var attempt := generation
	var endpoint := "return" if returning else "confirm"
	var path := ROUTE + "%s/design/%s/%s" % [chat_id.uri_encode(), item.stage, endpoint]
	var reply: Dictionary = await get_parent().api_request(HTTPClient.METHOD_POST, path, payload)
	if attempt != generation:
		return
	# A conflict or a lost reply can follow a committed decision. Read before enabling another write.
	await _read()
	if generation == attempt + 1 and reply.status != 200:
		notice.text = "决策请求返回 %d，请核对已读回的阶段修订。" % reply.status if not record.is_empty() else "决策结果待核对，请刷新。"
