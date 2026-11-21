@tool
extends VBoxContainer

var _detail: Node
var _session: Node
var _issue_id := ""
var _generation := 0
var _version := -1
var _busy := false
var _pending := {}
var _open := Button.new()
var _form := VBoxContainer.new()
var _estimate := LineEdit.new()
var _save := Button.new()
var _minutes := LineEdit.new()
var _note := LineEdit.new()
var _log := Button.new()
var _summary := Label.new()
var _records := Label.new()
var _status := Label.new()


func _ready() -> void:
	_detail = get_parent()
	_session = _detail.get_parent()
	_open.name = "OpenIssueTime"
	_open.text = "工时"
	_open.pressed.connect(_toggle)
	add_child(_open)
	add_child(_form)
	_summary.name = "IssueTimeSummary"
	_form.add_child(_summary)
	_estimate.name = "IssueEstimatedMinutes"
	_estimate.placeholder_text = "预计工时（分钟）"
	_form.add_child(_estimate)
	_save.name = "SaveIssueEstimate"
	_save.pressed.connect(_submit.bind("plan"))
	_form.add_child(_save)
	_minutes.name = "IssueActualMinutes"
	_minutes.placeholder_text = "本次实际工时（分钟）"
	_form.add_child(_minutes)
	_note.name = "IssueTimeNote"
	_note.placeholder_text = "工作内容（选填）"
	_note.max_length = 4000
	_form.add_child(_note)
	_log.name = "LogIssueTime"
	_log.pressed.connect(_submit.bind("log"))
	_form.add_child(_log)
	_records.name = "IssueTimeRecords"
	_records.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_records.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var history := ScrollContainer.new()
	history.custom_minimum_size.y = 64
	history.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	history.add_child(_records)
	_form.add_child(history)
	_status.name = "IssueTimeStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_form.add_child(_status)
	_detail.detail_changed.connect(_detail_changed)
	_detail_changed()


func _detail_changed() -> void:
	_generation += 1
	_issue_id = str(_detail.get_detail().get("id", ""))
	_version = -1
	_busy = false
	_pending.clear()
	_estimate.clear()
	_minutes.clear()
	_note.clear()
	_status.text = ""
	_summary.text = ""
	_records.text = ""
	_form.hide()
	visible = not _issue_id.is_empty()
	_update_controls()


func _update_controls() -> void:
	var waiting := not _pending.is_empty()
	var locked := _busy or _version < 0
	_save.disabled = locked or (waiting and _pending.operation != "plan")
	_log.disabled = locked or (waiting and _pending.operation != "log")
	_estimate.editable = not (locked or waiting)
	_minutes.editable = _estimate.editable
	_note.editable = _estimate.editable
	_save.text = "重试保存预计工时" if not locked and waiting and _pending.operation == "plan" else "保存预计工时"
	_log.text = "重试登记本次工时" if not locked and waiting and _pending.operation == "log" else "登记本次工时"


func _toggle() -> void:
	_form.visible = not _form.visible
	if _form.visible and not _busy and _pending.is_empty():
		await _read()


func _read() -> void:
	var generation := _generation
	_busy = true
	_update_controls()
	_status.text = "正在读取工时…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route())
	if generation != _generation:
		return
	_busy = false
	if reply.status == 200 and _display(reply.data):
		_status.text = ""
	else:
		_version = -1
		_summary.text = ""
		_records.text = ""
		_estimate.clear()
		_status.text = "读取工时失败，请重新打开工时"
	_update_controls()


func _route() -> String:
	return "/api/v1/issues/%s/work" % _issue_id.uri_encode()


func _display(state: Dictionary) -> bool:
	if state.get("id") != _issue_id or not state.has_all(["version", "plan", "logged_minutes", "logs"]):
		return false
	_version = int(state.version)
	var estimate := int(state.plan.estimated_minutes)
	_estimate.text = str(estimate)
	_summary.text = "预计 %d 分钟 · 已登记 %d 分钟" % [estimate, int(state.logged_minutes)]
	var lines := PackedStringArray()
	for entry: Dictionary in state.logs:
		lines.append("%d 分钟　%s" % [int(entry.minutes), str(entry.note)])
	_records.text = "\n".join(lines)
	return true


func _submit(operation: String) -> void:
	if _busy or _version < 0:
		return
	if _pending.is_empty():
		var value := (_estimate.text if operation == "plan" else _minutes.text).strip_edges()
		var minimum := 0 if operation == "plan" else 1
		if not value.is_valid_int() or value.to_int() < minimum or value.to_int() > 100000000 or value.length() > 9:
			_status.text = "请输入 %d 至 100000000 之间的整数分钟数" % minimum
			return
		var body := {"expected_version": _version, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
		if operation == "plan":
			body.plan = {"estimated_minutes": value.to_int()}
		else:
			body.minutes = value.to_int()
			body.note = _note.text
		_pending = {"operation": operation, "body": body}
	elif _pending.operation != operation:
		return
	var generation := _generation
	_busy = true
	_update_controls()
	_status.text = "正在保存工时…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, _route() + "/" + operation, _pending.body)
	if generation != _generation:
		return
	_busy = false
	if reply.status == 200 and _display(reply.data):
		_pending.clear()
		if operation == "log":
			_minutes.clear()
			_note.clear()
		_status.text = "已保存"
	elif reply.status in [0, 200] or reply.status >= 500:
		_status.text = "工时回执待确认，请重试同一请求"
	else:
		_pending.clear()
		if reply.status == 409:
			await _read()
			if generation != _generation:
				return
			if _version >= 0:
				_status.text = "工时版本已更新，请核对后提交"
		else:
			_status.text = "天璇拒绝保存工时（%d）" % int(reply.status)
	_update_controls()
