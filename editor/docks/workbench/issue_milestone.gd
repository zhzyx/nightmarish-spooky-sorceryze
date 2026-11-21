@tool
extends VBoxContainer

var _detail: Node
var _session: Node
var _generation := 0
var _version := -1
var _original := {}
var _iteration := LineEdit.new()
var _milestone := LineEdit.new()
var _counts := Label.new()
var _save := Button.new()
var _status := Label.new()


func _ready() -> void:
	_detail = get_parent()
	_session = _detail.get_parent()
	_add_field("迭代", "IssueIteration", _iteration)
	_add_field("里程碑", "IssueMilestone", _milestone)
	_counts.name = "IssuePlanCounts"
	_counts.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_counts)
	_save.name = "SaveIssueMilestone"
	_save.text = "保存迭代与里程碑"
	_save.pressed.connect(_submit)
	add_child(_save)
	_status.name = "IssueMilestoneStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_detail.detail_changed.connect(_changed)
	_changed()


func _add_field(caption: String, node_name: String, field: LineEdit) -> void:
	var label := Label.new()
	label.text = caption
	add_child(label)
	field.name = node_name
	field.placeholder_text = "未设置"
	field.max_length = 512
	field.text_changed.connect(func(_value: String): _update_save())
	add_child(field)


func _update_save() -> void:
	var unchanged: bool = _iteration.text == _original.get("iteration", "") and _milestone.text == _original.get("milestone", "")
	_save.disabled = not _iteration.editable or unchanged


func _editable(enabled: bool) -> void:
	_iteration.editable = enabled
	_milestone.editable = enabled
	_update_save()


func _changed() -> void:
	_generation += 1
	_version = -1
	_original.clear()
	_iteration.clear()
	_milestone.clear()
	_counts.text = ""
	_status.text = ""
	_editable(false)
	var issue: Dictionary = _detail.get_detail()
	visible = not issue.is_empty()
	if visible:
		_status.text = "正在读取计划…"
		_read(str(issue.id), _generation)


func _read(issue_id: String, attempt: int, feedback: String = "") -> void:
	var route := "/api/v1/issues/%s/work/plan" % issue_id.uri_encode()
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, route)
	if attempt != _generation:
		return
	var data: Dictionary = reply.data
	if reply.status != 200 or data.get("id") != issue_id or not _valid_membership(data):
		_iteration.clear()
		_milestone.clear()
		_counts.text = ""
		_status.text = "计划回读失败，请重新读取详情"
		return
	_version = int(data.version)
	_original = data.plan
	_iteration.text = data.plan.iteration
	_milestone.text = data.plan.milestone
	_counts.text = "迭代「%s」　%d 单\n里程碑「%s」　%d 单" % [
		"未设置" if _iteration.text.is_empty() else _iteration.text, int(data.counts.iteration),
		"未设置" if _milestone.text.is_empty() else _milestone.text, int(data.counts.milestone),
	]
	_editable(_session.get_identity().role != "viewer")
	_status.text = feedback


func _valid_membership(data: Dictionary) -> bool:
	if not data.get("plan") is Dictionary or not data.get("counts") is Dictionary:
		return false
	for key in ["iteration", "milestone"]:
		if not data.plan.get(key) is String or int(data.counts.get(key, 0)) < 1:
			return false
	return int(data.get("version", -1)) >= 0


func _submit() -> void:
	if _save.disabled or _version < 0:
		return
	var issue_id := str(_detail.get_detail().id)
	var attempt := _generation
	var fields := {}
	if _original.iteration != _iteration.text:
		fields.iteration = _iteration.text
	if _original.milestone != _milestone.text:
		fields.milestone = _milestone.text
	_editable(false)
	_status.text = "正在保存计划…"
	var route := "/api/v1/issues/%s/work/plan" % issue_id.uri_encode()
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, route, {
		"expected_version": _version, "plan": fields, "call_id": Crypto.new().generate_random_bytes(16).hex_encode(),
	})
	if attempt != _generation:
		return
	var feedback := "保存结果待核对，已重新读取当前计划"
	if reply.status == 200:
		feedback = "已保存并读取当前计划"
	elif reply.status == 409:
		feedback = "计划版本已变化，已读取最新计划，请核对后编辑"
	elif reply.status == 403:
		feedback = "没有权限修改此工单计划"
	elif reply.status >= 400 and reply.status < 500:
		feedback = "天璇拒绝保存（%d），已读取当前计划" % reply.status
	await _read(issue_id, attempt, feedback)
