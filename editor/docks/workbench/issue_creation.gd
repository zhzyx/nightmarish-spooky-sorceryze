@tool
extends VBoxContainer

var _session: Node
var _generation := 0
var _call_id := ""
var _open := Button.new()
var _form := VBoxContainer.new()
var _title := LineEdit.new()
var _modules := OptionButton.new()
var _submit := Button.new()
var _new := Button.new()
var _status := Label.new()
var _busy := false


func _ready() -> void:
	_session = get_parent()
	_open.name = "OpenIssueCreation"
	_open.text = "新建天璇工单"
	_open.pressed.connect(_toggle)
	add_child(_open)
	add_child(_form)
	_title.name = "IssueTitle"
	_title.placeholder_text = "工单标题"
	_form.add_child(_title)
	_modules.name = "IssueModule"
	_modules.tooltip_text = "业务模块"
	_form.add_child(_modules)
	_submit.name = "CreateIssue"
	_submit.text = "创建工单"
	_submit.pressed.connect(_create)
	_form.add_child(_submit)
	_new.text = "另建工单"
	_new.name = "NewIssueDraft"
	_new.pressed.connect(_clear_draft)
	_form.add_child(_new)
	_status.name = "IssueReceipt"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_form.add_child(_status)
	_session.identity_changed.connect(_identity_changed)
	_identity_changed()


func _identity_changed() -> void:
	_generation += 1
	_form.hide()
	_modules.clear()
	_clear_draft()
	_open.disabled = _session.get_identity().is_empty()


func _clear_draft() -> void:
	_call_id = ""
	_title.clear()
	_title.editable = true
	_busy = false
	_modules.disabled = false
	_submit.disabled = _modules.item_count == 0
	_submit.text = "创建工单"
	_new.hide()
	_status.text = ""


func _toggle() -> void:
	_form.visible = not _form.visible
	if not _form.visible or _modules.item_count > 0 or _busy:
		return
	var attempt := _generation
	_busy = true
	_status.text = "正在读取业务模块…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/business-modules")
	if attempt != _generation:
		return
	_busy = false
	for module: Dictionary in reply.data.get("modules", []):
		_modules.add_item(str(module.name))
		_modules.set_item_metadata(_modules.item_count - 1, module.id)
	_submit.disabled = _modules.item_count == 0
	_status.text = "无法读取模块，请重新打开后重试" if _submit.disabled else ""


# A caller supplies its stable logical request ID. The service owns allocation and replay.
func create_issue(request_id: String, title: String, module_id: String) -> Dictionary:
	var identity: Dictionary = _session.get_identity()
	if identity.is_empty() or request_id.is_empty() or title.strip_edges().is_empty() or module_id.is_empty():
		return {"status": 400, "data": {}}
	var payload := {"title": title.strip_edges(), "project": identity.project, "module_id": module_id}
	return await _session.api_request(HTTPClient.METHOD_POST, "/api/v1/tools", {
		"name": "issue.create", "call_id": request_id, "payload": payload,
	})


func read_issue(number: int) -> Dictionary:
	return await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues/by-number/%d" % number)


func _create() -> void:
	if _busy or _modules.selected < 0:
		return
	if _title.text.strip_edges().is_empty():
		_status.text = "请输入工单标题"
		return
	if _call_id.is_empty():
		_call_id = Crypto.new().generate_random_bytes(16).hex_encode()
	var attempt := _generation
	var module_id := str(_modules.get_selected_metadata())
	var title := _title.text.strip_edges()
	_busy = true
	_title.editable = false
	_modules.disabled = true
	_submit.disabled = true
	_new.hide()
	_status.text = "正在创建工单…"
	var reply := await create_issue(_call_id, title, module_id)
	if attempt != _generation:
		return
	var created: Dictionary = reply.data
	var number := int(created.get("number", 0))
	if reply.status == 200 and number > 0:
		var readback := await read_issue(number)
		if attempt != _generation:
			return
		var issue: Dictionary = readback.data
		var same_issue: bool = not str(created.get("id", "")).is_empty() and issue.get("id") == created.get("id")
		var same_project: bool = issue.get("project") == _session.get_identity().project
		if readback.status == 200 and same_issue and same_project and int(issue.get("number", 0)) == number:
			var module_label := str(issue.module_id)
			if module_id == module_label:
				module_label = "%s（%s）" % [_modules.get_item_text(_modules.selected), module_label]
			_status.text = "#%d · %s · %s" % [number, module_label, issue.title]
			_busy = false
			_new.show()
			return
		_status.text = "天璇已返回 #%d，按编号回读失败，请重试" % number
	else:
		_status.text = "创建结果待确认，请重试同一请求" if reply.status in [0, 200] or reply.status >= 500 else "天璇拒绝创建（%d）" % reply.status
	_busy = false
	_submit.disabled = false
	_submit.text = "重试同一请求"
	_new.show()
