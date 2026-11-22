@tool
extends AcceptDialog

var execute: Callable
var repository := LineEdit.new()
var source := LineEdit.new()
var target := LineEdit.new()
var candidate := LineEdit.new()
var request_id := LineEdit.new()
var issue := LineEdit.new()
var conflict_box := VBoxContainer.new()
var conflict_path := OptionButton.new()
var versions := TextEdit.new()
var resolved_text := TextEdit.new()
var conflicts: Array = []
var choices := {}
var loaded_request := ""
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
	for field in [[repository, "多宝仓库"], [source, "来源分支"], [target, "目标分支"], [candidate, "候选（完整提交）"], [request_id, "合入请求编号"], [issue, "天璇工单 ID（交付时必填）"]]:
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
	var review_row := HBoxContainer.new()
	box.add_child(review_row)
	for action in [["查看冲突差异", _load_conflicts], ["批准候选", _review.bind("APPROVED")], ["要求修改", _review.bind("REQUEST_CHANGES")], ["交付并回写工单", _deliver]]:
		_action(review_row, action[0], action[1])
	box.add_child(conflict_box)
	conflict_box.hide()
	conflict_box.add_child(conflict_path)
	conflict_path.item_selected.connect(_select_conflict)
	versions.editable = false
	versions.custom_minimum_size.y = 80
	conflict_box.add_child(versions)
	resolved_text.placeholder_text = "输入解决后的完整文件内容"
	resolved_text.custom_minimum_size.y = 60
	conflict_box.add_child(resolved_text)
	var choices_row := HBoxContainer.new()
	conflict_box.add_child(choices_row)
	for choice in [["采用来源版本", "source"], ["采用目标版本", "target"], ["采用编辑内容", "text"]]:
		_action(choices_row, choice[0], _choose.bind(choice[1]))
	_action(choices_row, "重建并检查候选", _resolve)
	for label in [status, target_tip]:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(label)
	get_ok_button().text = "关闭"


func _action(row: Container, caption: String, callback: Callable) -> void:
	var button := Button.new()
	button.text = caption
	button.pressed.connect(callback)
	row.add_child(button)
	actions.append(button)


func _clear_readback(_value: String) -> void:
	conflict_box.hide()
	loaded_request = ""
	choices.clear()
	status.text = ""
	target_tip.text = ""


func _command(arguments: Array) -> Dictionary:
	busy = true
	for button in actions:
		button.disabled = true
	for field in [repository, source, target, candidate, request_id, issue]:
		field.editable = false
	var result: Dictionary = await execute.call(arguments + ["--repo-name", repository.text.strip_edges()])
	busy = false
	for button in actions:
		button.disabled = false
	for field in [repository, source, target, candidate, request_id, issue]:
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
	var args := ["merge-request", "--source", source.text.strip_edges(), "--target", target.text.strip_edges(), "--candidate", candidate.text.strip_edges()]
	if not issue.text.strip_edges().is_empty():
		args.append_array(["--issue-id", issue.text.strip_edges()])
	var result := await _command(args)
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
	if request_id.text != str(data.id) or data.check_state != "conflict":
		conflict_box.hide()
		loaded_request = ""
	request_id.text = str(data.id)
	issue.text = str(data.get("issue_id", ""))
	source.text = str(data.source)
	target.text = str(data.target)
	candidate.text = str(data.candidate)
	target_tip.text = ""
	var states := {"queued": "等待检查", "validating": "检查中", "checked": "检查通过，等待合入", "stale": "检查已失效，分支发生变化", "rejected": "检查未通过", "conflict": "存在合入冲突", "cancelled": "请求已取消", "merged": "已合入目标分支"}
	var summary: String = states.get(data.check_state, data.check_state)
	if data.check_state == "checked" and data.checks.is_empty():
		summary = "合并预检通过，未配置额外检查"
	status.text = "%s\n%s @ %s → %s @ %s" % [summary, data.source, data.candidate, data.target, data.target_base]
	if not str(data.get("resolved_from", "")).is_empty():
		status.text += "\n原冲突请求 " + str(data.resolved_from)
	if data.check_state == "stale" and not data.checks.is_empty():
		status.text += "\n原候选的历史检查"
	for reviewer in data.get("reviews", {}):
		status.text += "\n%s · %s" % [reviewer, "已批准" if data.reviews[reviewer] == "APPROVED" else "要求修改"]
	if not str(data.get("merge_sha", "")).is_empty():
		status.text += "\n%s · %s" % [data.merge_sha, data.issue_id]
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

func _load_conflicts() -> void:
	if busy:
		return
	var reply := await _command(["merge-conflicts", "--request-id", request_id.text.strip_edges()])
	if not reply.get("ok", false):
		status.text = str(reply.get("error", "无法读取冲突"))
		return
	conflicts = reply.data.files
	loaded_request = request_id.text
	choices.clear()
	conflict_path.clear()
	for entry in conflicts:
		conflict_path.add_item(entry.path)
	if not conflicts.is_empty():
		conflict_box.show()
		_select_conflict(0)
		reset_size()


func _select_conflict(index: int) -> void:
	var file: Dictionary = conflicts[index]
	versions.text = "来源\n%s\n目标\n%s" % [_version(file.source), _version(file.target)]
	resolved_text.text = choices.get(file.path, {}).get("text", str(file.source.text) if file.source.text != null else "")


func _version(value: Dictionary) -> String:
	if value.oid == null:
		return "（已删除）"
	return str(value.text) if value.text != null else "对象 " + str(value.oid)


func _choose(side: String) -> void:
	if busy or conflict_path.selected < 0:
		return
	var file: Dictionary = conflicts[conflict_path.selected]
	choices[file.path] = {"choice": side, "text": resolved_text.text} if side == "text" else {"choice": side}
	status.text = "已选择 %d / %d 个冲突文件" % [choices.size(), conflicts.size()]


func _resolve() -> void:
	if busy or request_id.text != loaded_request or choices.size() != conflicts.size():
		return
	_show_request(await _command(["merge-resolve", "--request-id", loaded_request, "--files", JSON.stringify(choices)]))


func _review(decision: String) -> void:
	if not busy:
		_show_request(await _command(["merge-review", "--request-id", request_id.text.strip_edges(), "--decision", decision]))


func _deliver() -> void:
	if busy:
		return
	var reply := await _command(["merge-deliver", "--request-id", request_id.text.strip_edges()])
	_show_request(reply)
	if reply.get("ok", false):
		target_tip.text = "目标 %s @ %s · 工单 %s · 回执 %s" % [reply.data.target, reply.data.target_tip, reply.data.issue_id, reply.data.comment_id]
