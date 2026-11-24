@tool
extends VBoxContainer

var view: Node
var session: Node
var open := Button.new()
var dialog := AcceptDialog.new()
var rows := VBoxContainer.new()
var status := Label.new()
var generation := 0


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	open.text = "逐项确认启动"
	open.pressed.connect(_show_tasks)
	add_child(open)
	dialog.title = "逐项确认启动"
	dialog.get_ok_button().text = "关闭"
	dialog.visibility_changed.connect(func(): generation += 1)
	add_child(dialog)
	var form := VBoxContainer.new()
	dialog.add_child(form)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(460, 320)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	form.add_child(scroll)
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(rows)
	form.add_child(status)
	view.detail_changed.connect(_reset)
	_reset()


func _reset() -> void:
	generation += 1
	dialog.hide()
	visible = view.get_detail().get("design_source") is Dictionary


func _show_tasks() -> void:
	for child in rows.get_children():
		rows.remove_child(child)
		child.queue_free()
	status.text = "正在读取任务…"
	dialog.popup_centered()
	var attempt := generation
	var source: Dictionary = view.get_detail().design_source
	var path := "/api/v1/docs/%s/versions/%d/tasks" % [str(source.document_id).uri_encode(), int(source.version)]
	var list: Dictionary = await session.api_request(HTTPClient.METHOD_GET, path)
	if generation != attempt:
		return
	if list.status != 200 or not list.data.get("tasks") is Array:
		status.text = "读取失败，请关闭并重新打开。"
		return
	for task: Dictionary in list.data.tasks:
		var detail := await _read_task(int(task.number))
		if attempt != generation:
			return
		if detail.get("id") != task.id or detail.get("design_source") == null:
			status.text = "工单来源已变更，请关闭并重新打开。"
			return
		var row := VBoxContainer.new()
		rows.add_child(row)
		_fill(row, detail, false)
	status.text = "勾选要核对的任务，再点击该项的确认按钮。"


func _read_task(number: int) -> Dictionary:
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues/by-number/%d/detail" % number)
	return reply.data if reply.status == 200 else {}


func _fill(row: VBoxContainer, detail: Dictionary, selected: bool) -> void:
	for child in row.get_children():
		row.remove_child(child)
		child.queue_free()
	var toggle := CheckBox.new()
	toggle.name = "SelectTask"
	toggle.text = "#%d %s" % [int(detail.number), detail.title]
	toggle.button_pressed = selected
	row.add_child(toggle)
	var info := Label.new()
	info.name = "Target"
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(info)
	var target: Variant = detail.get("task_target")
	var confirmation: Variant = detail.get("task_confirmation")
	if not target is Dictionary or not confirmation is Dictionary:
		info.text = "尚未定义目标"
		toggle.disabled = true
		return
	var states := {"confirmed": "已确认启动", "pending": "待确认", "revoked": "已撤销"}
	info.text = "%s · %s\n%s" % [target.stage, states[confirmation.status], target.criteria]
	if confirmation.status == "confirmed":
		info.text += "\n确认人：" + str(confirmation.confirmed_by)
	var owner: String = confirmation.responsible_user
	var identity: Dictionary = session.get_identity()
	var writable: bool = identity.get("id") == owner and identity.get("role") != "viewer" and detail.can_classify and target.status == "defined"
	if confirmation.status != "confirmed" and detail.status in ["done", "cancelled"]:
		writable = false
	if target.status != "defined":
		info.text += "\n请由当前负责人补全目标。"
	var act := Button.new()
	act.name = "ConfirmTask"
	var desired := "revoked" if confirmation.status == "confirmed" else "confirmed"
	act.text = "撤销本项确认" if desired == "revoked" else "确认启动本项"
	act.disabled = not selected or not writable
	row.add_child(act)
	toggle.toggled.connect(func(on: bool): act.disabled = not (on and writable))
	act.pressed.connect(func(): _save(row, detail, desired))


func _save(row: VBoxContainer, detail: Dictionary, desired: String) -> void:
	if row.get_node("ConfirmTask").disabled:
		return
	row.get_node("SelectTask").disabled = true
	row.get_node("ConfirmTask").disabled = true
	var attempt := generation
	var record: Dictionary = detail.task_confirmation
	var payload := {"document_id": record.document_id, "version": int(record.version),
		"issue_revision": record.issue_revision, "target_revision": int(record.target_revision), "expected_revision": int(record.revision), "status": desired}
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_PUT, "/api/v1/issues/%s/task-confirmation" % str(detail.id).uri_encode(), payload)
	if attempt != generation:
		return
	var fresh := await _read_task(int(detail.number))
	if attempt != generation:
		return
	if fresh.get("id") != detail.id:
		status.text = "回执待核对，请重新打开。"
		return
	_fill(row, fresh, true)
	if reply.status == 200 and reply.data == fresh.get("task_confirmation"):
		status.text = "已从天璇回读 #%d 的记录。" % int(detail.number)
	else:
		status.text = "本次写入未获确认，请核对当前记录。"
