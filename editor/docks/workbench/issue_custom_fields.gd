@tool
extends VBoxContainer

var _detail: Node
var _session: Node
var _generation := 0
var _open := Button.new()
var _form := VBoxContainer.new()
var _field := OptionButton.new()
var _value := LineEdit.new()
var _save := Button.new()
var _stage := OptionButton.new()
var _advance := Button.new()
var _message := Label.new()
var _plan := {}
var _flow := {}
var _route := ""
var _busy := false


func _ready() -> void:
	_detail = get_parent()
	_session = _detail.get_parent()
	_open.name = "OpenIssueCustomFields"
	_open.text = "字段与阶段"
	_open.pressed.connect(_toggle)
	add_child(_open)
	add_child(_form)
	_field.name = "IssueProjectField"
	_field.item_selected.connect(_select_field)
	_form.add_child(_field)
	_value.name = "IssueFieldValue"
	_value.placeholder_text = "字段值"
	_value.max_length = 2000
	_value.text_changed.connect(func(_text: String): _controls())
	_form.add_child(_value)
	_save.name = "SaveIssueField"
	_save.text = "保存字段"
	_save.pressed.connect(_save_field)
	_form.add_child(_save)
	_stage.name = "IssueFlowStage"
	_stage.item_selected.connect(func(_index: int): _controls())
	_form.add_child(_stage)
	_advance.name = "AdvanceIssueStage"
	_advance.text = "保存阶段"
	_advance.pressed.connect(_save_stage)
	_form.add_child(_advance)
	_message.name = "IssueFieldMessage"
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_form.add_child(_message)
	_detail.detail_changed.connect(_reset)
	move_to_front.call_deferred()
	_reset()


func _reset() -> void:
	_generation += 1
	_form.hide()
	_field.clear()
	_value.clear()
	_stage.clear()
	_plan.clear()
	_flow.clear()
	_message.text = ""
	_route = ""
	_busy = false
	visible = not _detail.get_detail().is_empty()


func _toggle() -> void:
	if _form.visible:
		_reset()
		return
	var record: Dictionary = _detail.get_detail()
	if record.is_empty():
		return
	_form.show()
	_busy = true
	_controls()
	_message.text = "正在读取项目字段与工单阶段…"
	var attempt := _generation
	_route = "/api/v1/issues/%s/work" % str(record.id).uri_encode()
	var definitions: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/work/field-definitions")
	if attempt != _generation:
		return
	if definitions.status != 200 or definitions.data.get("project") != record.project or not definitions.data.get("fields") is Array:
		_message.text = "无法读取项目字段定义，请重新打开。"
		return
	var work: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route)
	if attempt != _generation:
		return
	if work.status != 200 or work.data.get("id") != record.id or not work.data.has("version") or not work.data.get("plan", {}).get("custom_fields") is Dictionary:
		_message.text = "无法读取工单字段值，请重新打开。"
		return
	var flow: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route + "/flow")
	if attempt != _generation:
		return
	if flow.status != 200 or flow.data.get("id") != record.id or not flow.data.has_all(["version", "status", "edges", "stages"]):
		_message.text = "无法读取工单阶段，请重新打开。"
		return
	_plan = work.data
	_flow = flow.data
	for item in definitions.data.fields:
		_field.add_item(item.label)
		_field.set_item_metadata(_field.item_count - 1, item.key)
	if _field.item_count > 0:
		_select_field(0)
	_stage.add_item("当前阶段　" + str(_flow.status))
	for item in _flow.stages:
		if item.id == _flow.status and item.human:
			_stage.set_item_text(0, "需人工裁定　" + str(_flow.status))
			break
		if item.id == _flow.status:
			for edge in _flow.edges:
				if edge.from == _flow.status:
					_stage.add_item(str(edge.to))
					_stage.set_item_metadata(_stage.item_count - 1, edge.to)
			break
	_busy = false
	_message.text = "" if _field.item_count else "此项目尚未定义文本字段"
	_controls()


func _select_field(index: int) -> void:
	var key: String = _field.get_item_metadata(index)
	_value.text = str(_plan.plan.custom_fields.get(key, ""))
	_controls()


func _controls() -> void:
	var writable: bool = _session.get_identity().get("role", "viewer") != "viewer"
	var changed := false
	if not _plan.is_empty() and _field.selected >= 0:
		var key: String = _field.get_item_metadata(_field.selected)
		changed = str(_plan.plan.custom_fields.get(key, "")) != _value.text
	_field.disabled = _busy or changed or _field.item_count == 0
	_value.editable = writable and not _busy and _field.item_count > 0
	_save.disabled = not _value.editable or not changed
	_stage.disabled = not writable or _busy or changed or _stage.item_count <= 1
	_advance.disabled = _stage.disabled or _stage.selected <= 0


func _save_field() -> void:
	if _save.disabled:
		return
	var key: String = _field.get_item_metadata(_field.selected)
	await _submit("/plan", {"expected_version": int(_plan.version), "field_update": {"key": key, "value": _value.text}})


func _save_stage() -> void:
	if _advance.disabled:
		return
	await _submit("/flow/advance", {"expected_version": int(_flow.version), "to_status": _stage.get_item_metadata(_stage.selected)})


func _submit(suffix: String, body: Dictionary) -> void:
	var attempt := _generation
	var record: Dictionary = _detail.get_detail()
	_busy = true
	_controls()
	_message.text = "正在保存…"
	body.call_id = Crypto.new().generate_random_bytes(16).hex_encode()
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, _route + suffix, body)
	if attempt != _generation:
		return
	if reply.status != 200 or reply.data.get("id") != record.id or int(reply.data.get("version", -1)) != body.expected_version + 1:
		_message.text = "保存结果待核实，请重新打开并读取。" if reply.status == 0 or reply.status >= 500 else "保存未确认（%d），请重新打开并读取。" % reply.status
		return
	if suffix == "/plan":
		if reply.data.get("plan", {}).get("custom_fields", {}).get(body.field_update.key) != body.field_update.value:
			_message.text = "字段回执与提交值不一致，请重新打开并读取。"
			return
		_plan = reply.data
		_busy = false
		_message.text = "已保存字段"
		_controls()
	else:
		# Refresh the I02 status and revision for all consumers.
		await _detail.open_issue(int(record.number))
