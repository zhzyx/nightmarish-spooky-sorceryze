@tool
extends VBoxContainer

signal detail_changed
signal consultation_requested

var _session: Node
var _generation := 0
var _detail := {}
var _open := Button.new()
var _form := VBoxContainer.new()
var _number := LineEdit.new()
var _status := Label.new()
var _fields := Label.new()
var _consult := Button.new()


func _ready() -> void:
	_session = get_parent()
	_open.name = "OpenIssueDetail"
	_open.text = "工单详情"
	_open.pressed.connect(_toggle)
	add_child(_open)
	add_child(_form)
	move_child(_open, 0)
	move_child(_form, 1)
	_number.name = "IssueDetailNumber"
	_number.placeholder_text = "天璇工单编号"
	_number.text_changed.connect(func(_value: String): _clear())
	_number.text_submitted.connect(_lookup)
	_form.add_child(_number)
	var lookup := Button.new()
	lookup.name = "ReadIssueDetail"
	lookup.text = "读取详情"
	lookup.pressed.connect(func(): _lookup(_number.text))
	_form.add_child(lookup)
	_status.name = "IssueDetailStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_form.add_child(_status)
	_fields.name = "IssueDetailFields"
	_fields.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_form.add_child(_fields)
	_consult.name = "ConsultIssueDetail"
	_consult.text = "就此工单咨询"
	_consult.pressed.connect(func(): consultation_requested.emit())
	_form.add_child(_consult)
	_session.identity_changed.connect(_reset)
	_reset()


func get_detail() -> Dictionary:
	return _detail.duplicate(true)


func _clear() -> void:
	_generation += 1
	_detail.clear()
	_consult.hide()
	_fields.text = ""
	_status.text = ""
	detail_changed.emit()


func _reset() -> void:
	_clear()
	_number.clear()
	_form.hide()
	_open.tooltip_text = "请先登录天璇" if _session.get_identity().is_empty() else ""


func _toggle() -> void:
	if _form.visible:
		_clear()
		_form.hide()
	else:
		_form.show()
		if _session.get_identity().is_empty():
			_status.text = "请先登录天璇"
		_number.grab_focus()


func _lookup(text: String) -> void:
	var value := text.strip_edges().trim_prefix("#")
	var number := value.to_int()
	if not value.is_valid_int() or number < 1 or str(number) != value:
		_clear()
		_status.text = "请输入有效的正整数工单编号"
		return
	open_issue(number)


func open_issue(number: int) -> void:
	_clear()
	_form.show()
	_number.text = str(number)
	if _session.get_identity().is_empty():
		_status.text = "请先登录天璇"
		return
	if number < 1:
		_status.text = "请输入有效的正整数工单编号"
		return
	var attempt := _generation
	_status.text = "正在读取工单…"
	var route := "/api/v1/issues/by-number/%d/detail" % number
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, route)
	if attempt != _generation:
		return
	match int(reply.status):
		403:
			_status.text = "没有权限查看此工单"
		404:
			_status.text = "当前项目中不存在此编号的工单"
		200:
			var data: Dictionary = reply.data
			if int(data.get("number", 0)) != number or data.get("project") != _session.get_identity().project or not data.has_all(["id", "title", "status", "revision", "assignee"]):
				_status.text = "工单回读不完整，请重新读取"
				return
			var owner := "未分配"
			if data.assignee is Dictionary:
				owner = str(data.assignee.name)
				if owner.is_empty():
					owner = str(data.assignee.id)
			_detail = data.duplicate(true)
			_consult.show()
			_fields.text = "标题　%s\n负责人　%s\n状态　%s\n内容版本　%s" % [data.title, owner, data.status, data.revision]
			_status.text = "#%d" % number
			detail_changed.emit()
		_:
			_status.text = "读取工单失败，请重试"
