@tool
extends AcceptDialog

var execute: Callable
var repository := LineEdit.new()
var source := LineEdit.new()
var target := LineEdit.new()
var candidate := LineEdit.new()
var request_id := LineEdit.new()
var status := Label.new()
var target_tip := Label.new()
var actions: Array[Button] = []
var busy := false


func _ready() -> void:
	title = "多宝合入请求"
	exclusive = true
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = 570
	add_child(box)
	for field in [[repository, "多宝仓库"], [source, "来源分支"], [target, "目标分支"], [candidate, "候选（完整提交）"], [request_id, "合入请求编号"]]:
		var label := Label.new()
		label.text = field[1]
		box.add_child(label)
		box.add_child(field[0])
		field[0].text_changed.connect(_clear_readback)
	repository.text = OS.get_environment("TIANXUAN_GIT_REPO")
	var row := HBoxContainer.new()
	box.add_child(row)
	for action in [["读取来源候选", _read_source], ["发起合入请求", _create], ["刷新检查", _refresh], ["读取目标分支", _read_target]]:
		var button := Button.new()
		button.text = action[0]
		button.pressed.connect(action[1])
		row.add_child(button)
		actions.append(button)
	for label in [status, target_tip]:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(label)
	get_ok_button().text = "关闭"


func _clear_readback(_value: String) -> void:
	status.text = ""
	target_tip.text = ""


func _command(arguments: Array) -> Dictionary:
	busy = true
	for button in actions:
		button.disabled = true
	for field in [repository, source, target, candidate, request_id]:
		field.editable = false
	var result: Dictionary = await execute.call(arguments + ["--repo-name", repository.text.strip_edges()])
	busy = false
	for button in actions:
		button.disabled = false
	for field in [repository, source, target, candidate, request_id]:
		field.editable = true
	return result


func _read_source() -> void:
	if busy:
		return
	var result := await _command(["branch-tip", "--branch", source.text.strip_edges()])
	if result.get("ok", false):
		candidate.text = str(result.data.sha)
		request_id.clear()
		status.text = "已读取来源候选 " + candidate.text
	else:
		status.text = str(result.get("error", "无法读取来源分支"))


func _create() -> void:
	if busy:
		return
	var result := await _command(["merge-request", "--source", source.text.strip_edges(), "--target", target.text.strip_edges(), "--candidate", candidate.text.strip_edges()])
	_show_request(result)


func _refresh() -> void:
	if busy:
		return
	var result := await _command(["merge-request-status", "--request-id", request_id.text.strip_edges()])
	_show_request(result)


func _show_request(result: Dictionary) -> void:
	if not result.get("ok", false):
		status.text = str(result.get("error", "无法读取合入请求"))
		return
	var data: Dictionary = result.data
	request_id.text = str(data.id)
	source.text = str(data.source)
	target.text = str(data.target)
	candidate.text = str(data.candidate)
	target_tip.text = ""
	var states := {"queued": "等待检查", "validating": "检查中", "checked": "检查通过，等待合入", "stale": "检查已失效，分支发生变化", "rejected": "检查未通过", "conflict": "存在合入冲突", "cancelled": "请求已取消"}
	var summary: String = states.get(data.check_state, data.check_state)
	if data.check_state == "checked" and data.checks.is_empty():
		summary = "合并预检通过，未配置额外检查"
	status.text = "%s\n%s @ %s → %s @ %s" % [summary, data.source, data.candidate, data.target, data.target_base]
	if data.check_state == "stale" and not data.checks.is_empty():
		status.text += "\n原候选的历史检查"
	for check in data.checks:
		status.text += "\n%s（退出码 %s）" % [check.command, int(check.exit_code)]


func _read_target() -> void:
	if busy:
		return
	var result := await _command(["branch-tip", "--branch", target.text.strip_edges()])
	if result.get("ok", false):
		target_tip.text = "当前目标 %s @ %s" % [result.data.branch, result.data.sha]
	else:
		target_tip.text = str(result.get("error", "无法读取目标分支"))
