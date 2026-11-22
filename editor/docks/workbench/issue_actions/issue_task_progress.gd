@tool
extends VBoxContainer

const STATE_LABELS := {
	"ready": "等待调度", "reserved": "已预约", "running": "运行中", "held": "等待核对",
	"produced": "已生成产物", "failed": "执行失败", "stage-reached": "已到达目标阶段",
	"stage-unmet": "阶段核验未通过", "accepted": "已验收", "stopped": "已停止",
	"closed-unresolved": "进程已关闭，待核对", "superseded": "已有后续运行",
}

var session: Node
var view: Node
var open := Button.new()
var dialog := AcceptDialog.new()
var receipt := TextEdit.new()
var refresh := Button.new()
var generation := 0
var number := 0
var issue_id := ""


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	open.name = "OpenIssueTaskProgress"
	open.text = "运行进度"
	open.pressed.connect(_open_from_issue)
	add_child(open)
	dialog.name = "TaskProgressDialog"
	dialog.get_ok_button().text = "关闭"
	dialog.visibility_changed.connect(_visibility_changed)
	add_child(dialog)
	var box := VBoxContainer.new()
	dialog.add_child(box)
	receipt.name = "TaskProgressReceipt"
	receipt.custom_minimum_size = Vector2(490, 320) * EditorInterface.get_editor_scale()
	receipt.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	receipt.editable = false
	box.add_child(receipt)
	refresh.name = "RefreshTaskProgress"
	refresh.text = "刷新进度"
	refresh.pressed.connect(_read)
	box.add_child(refresh)
	view.detail_changed.connect(_detail_changed)
	_detail_changed()


func _detail_changed() -> void:
	dialog.hide()
	var detail: Dictionary = view.get_detail()
	open.visible = detail.has("execution_progress")


func _visibility_changed() -> void:
	if not dialog.visible:
		generation += 1
		receipt.clear()
		issue_id = ""
		number = 0


func _open_from_issue() -> void:
	var detail: Dictionary = view.get_detail()
	if not detail.is_empty():
		open_task(int(detail.number), detail.id)


func open_task(issue_number: int, id: String) -> void:
	if id.is_empty() or issue_number < 1 or session.get_identity().is_empty():
		return
	number = issue_number
	issue_id = id
	dialog.title = "#%d · 运行进度" % number
	dialog.popup_centered()
	_read()


func _read() -> void:
	generation += 1
	var attempt := generation
	receipt.text = "正在读取运行进度…"
	var detail: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues/by-number/%d/detail" % number)
	if attempt != generation:
		return
	if detail.status != 200 or detail.data.get("id") != issue_id or detail.data.get("project") != session.get_identity().project:
		receipt.text = "无法读取此工单的运行进度"
		return
	var active: Variant = detail.data.get("execution_progress")
	if active == null:
		receipt.text = "当前没有可读取的运行记录"
		return
	if not active is Dictionary or active.get("issue") != issue_id or not active.get("id") is String or active.id.is_empty() or not active.get("events") is Array:
		receipt.text = "工单运行回执不完整"
		return
	# Viewers receive the authorized progress projection with the issue detail.
	if session.get_identity().get("role") == "viewer":
		receipt.text = _format_receipt(active, {})
		return
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/status", {"key": active.id})
	if attempt != generation:
		return
	var progress: Variant = reply.data.get("progress")
	if reply.status != 200 or not progress is Dictionary or progress.get("id") != active.id or progress.get("issue") != issue_id or not progress.get("events") is Array:
		receipt.text = "无法核对该次运行的最新回执"
		return
	receipt.text = _format_receipt(progress, reply.data)


func _format_receipt(progress: Dictionary, status: Dictionary) -> String:
	var stage: Variant = progress.get("stage")
	var state: String = progress.state
	var lines := PackedStringArray([
		"运行号　" + str(progress.id),
		"目标阶段　" + (str(stage) if stage != null else "未指定"),
		"运行状态　" + str(STATE_LABELS.get(state, state)),
	])
	if progress.get("candidate") != null:
		lines.append("产物候选　" + str(progress.candidate))
	if status.get("stage_result") is Dictionary and status.stage_result.has("reason"):
		lines.append("阶段核验　" + str(status.stage_result.reason))
	if progress.state == "failed" and status.get("terminal") is String:
		var terminal: Variant = JSON.parse_string(status.terminal)
		if terminal is Dictionary:
			if terminal.get("exit_code") != null:
				lines.append("进程退出码　%d" % int(terminal.exit_code))
			for reason in terminal.get("reasons", []):
				lines.append("阻塞原因　" + str(reason))
	lines.append("")
	lines.append("运行回执（从新到旧）")
	for index in range(progress.events.size() - 1, -1, -1):
		var event: Dictionary = progress.events[index]
		lines.append("#%d　%s　%s　%s" % [int(event.sequence), event.recorded_at, event.step, event.state])
		if not event.details.is_empty():
			lines.append(JSON.stringify(event.details))
	return "\n".join(lines)
