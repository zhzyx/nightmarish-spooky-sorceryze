@tool
extends VBoxContainer

var view: Node
var session: Node
var summary := Label.new()
var actions := HFlowContainer.new()
var notice := Label.new()
var generation := 0


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	summary.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)
	add_child(actions)
	add_child(notice)
	view.detail_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	generation += 1
	for child in actions.get_children():
		actions.remove_child(child)
		child.queue_free()
	var detail: Dictionary = view.get_detail()
	var progress: Variant = detail.get("execution_progress")
	visible = progress is Dictionary and progress.get("control") is Dictionary
	notice.text = ""
	if not visible:
		return
	var control: Dictionary = progress.control
	summary.text = "本机运行 %s\n%s" % [progress.id, control.summary]
	var operations: Array = detail.get("execution_control_actions", [])
	for operation: String in operations:
		var button := Button.new()
		button.name = operation
		button.text = {"pause": "完成当前步骤后暂停", "resume": "已核对，恢复运行", "cancel": "取消此运行"}[operation]
		actions.add_child(button)
		button.pressed.connect(_send.bind(operation, detail, progress))
	if control.state in ["pausing", "canceling"]:
		var refresh := Button.new()
		refresh.text = "重新读取运行"
		actions.add_child(refresh)
		refresh.pressed.connect(view.open_issue.bind(int(detail.number), str(detail.id)))


func _send(operation: String, detail: Dictionary, progress: Dictionary) -> void:
	var attempt := generation
	for child in actions.get_children():
		child.disabled = true
	var payload := {"issue": detail.id, "key": progress.id, "expected": int(progress.control.revision)}
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/" + operation, payload)
	if generation != attempt:
		return
	await view.open_issue(int(detail.number), str(detail.id))
	if view.get_detail().get("id") == detail.id:
		notice.text = "操作已接收。" if reply.status == 200 else "操作未获确认，请核对当前运行与授权。"
