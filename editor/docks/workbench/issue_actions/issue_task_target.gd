@tool
extends VBoxContainer

var view: Node
var session: Node
var detail := {}
var generation := 0
var open := Button.new()
var dialog := ConfirmationDialog.new()
var stage := LineEdit.new()
var criteria := TextEdit.new()
var status := Label.new()


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	open.text = "任务阶段目标"
	open.pressed.connect(_show_target)
	add_child(open)
	dialog.title = "任务阶段目标"
	dialog.dialog_hide_on_ok = false
	dialog.get_ok_button().text = "保存目标"
	dialog.confirmed.connect(_save)
	add_child(dialog)
	var form := VBoxContainer.new()
	form.custom_minimum_size.x = 400
	dialog.add_child(form)
	stage.placeholder_text = "目标阶段，例如可运行原型或动画预览"
	stage.max_length = 128
	form.add_child(stage)
	criteria.placeholder_text = "写下可验证的到达条件"
	criteria.custom_minimum_size.y = 90
	criteria.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	form.add_child(criteria)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	form.add_child(status)
	view.detail_changed.connect(_reset)
	_reset()


func _reset() -> void:
	generation += 1
	dialog.hide()
	detail = view.get_detail()
	visible = detail.get("design_source") is Dictionary


func _show_target() -> void:
	var target: Dictionary = detail.task_target if detail.get("task_target") is Dictionary else {}
	stage.text = target.get("stage", "")
	criteria.text = target.get("criteria", "")
	var owner: String = detail.assignee.id if detail.assignee is Dictionary else detail.created_by
	var identity: Dictionary = session.get_identity()
	var writable: bool = identity.get("id") == owner and identity.get("role") != "viewer" and detail.get("can_classify", false)
	stage.editable = writable
	criteria.editable = writable
	dialog.get_ok_button().disabled = not writable
	status.text = target.get("return_reason", "")
	if not writable:
		status.text += " 仅负责用户可以修改目标。"
	elif status.text.is_empty() and not target.is_empty():
		status.text = "已保存目标 · 来源设计 v%d · 目标修订 %d" % [int(detail.design_source.version), int(target.revision)]
	dialog.popup_centered()


func _save() -> void:
	if dialog.get_ok_button().disabled:
		return
	if stage.text.strip_edges().is_empty():
		status.text = "请填写目标阶段"
		return
	var attempt := generation
	var target: Dictionary = detail.task_target if detail.get("task_target") is Dictionary else {}
	var payload := {"document_id": detail.design_source.document_id, "version": int(detail.design_source.version),
		"stage": stage.text, "criteria": criteria.text, "expected_revision": int(target.get("revision", 0))}
	dialog.get_ok_button().disabled = true
	stage.editable = false
	criteria.editable = false
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_PUT, "/api/v1/issues/%s/task-target" % str(detail.id).uri_encode(), payload)
	if attempt != generation:
		return
	if reply.status != 200:
		status.text = "保存未获确认，请重新读取工单"
		return
	var number := int(detail.number)
	await view.open_issue(number)
	if detail.get("number") == number and detail.get("task_target") is Dictionary:
		_show_target()
