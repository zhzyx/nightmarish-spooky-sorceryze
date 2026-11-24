@tool
extends VBoxContainer

var detail: Node
var session: Node
var status := Label.new()
var current := Label.new()
var input := LineEdit.new()
var attach := Button.new()
var detach := Button.new()
var expected_parent: Variant
var generation := 0


func _ready() -> void:
	detail = get_parent()
	session = detail.get_parent()
	current.name = "IssueHierarchyCurrent"
	current.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(current)
	var row := HBoxContainer.new()
	add_child(row)
	input.name = "ParentIssueNumber"
	input.placeholder_text = "父工单编号"
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(input)
	attach.name = "SetIssueParent"
	attach.text = "设置父工单"
	attach.pressed.connect(_change.bind(false))
	row.add_child(attach)
	detach.name = "RemoveIssueParent"
	detach.text = "解除上级"
	detach.pressed.connect(_change.bind(true))
	row.add_child(detach)
	status.name = "IssueHierarchyStatus"
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(status)
	detail.detail_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	generation += 1
	current.text = ""
	status.text = ""
	input.clear()
	expected_parent = null
	attach.disabled = true
	detach.disabled = true
	var issue: Dictionary = detail.get_detail()
	visible = not issue.is_empty()
	if not visible:
		return
	var active := generation
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, _route(issue))
	if active != generation:
		return
	if reply.status == 200:
		_render(reply.data)
	else:
		status.text = "无法读取工单层级（%d）" % reply.status


func _route(issue: Dictionary) -> String:
	return "/api/v1/issues/%s/hierarchy" % str(issue.id).uri_encode()


func _render(data: Dictionary) -> void:
	var parent: Variant = data.get("parent")
	expected_parent = parent.id if parent is Dictionary else null
	var children := PackedStringArray()
	for child in data.get("children", []):
		children.append("#%d %s" % [child.number, child.title])
	var parent_label := "#%d %s" % [parent.number, parent.title] if parent is Dictionary else "无"
	current.text = "父工单　%s\n子工单　%s" % [parent_label, "、".join(children) if not children.is_empty() else "无"]
	attach.disabled = false
	detach.disabled = expected_parent == null


func _change(remove: bool) -> void:
	var issue: Dictionary = detail.get_detail()
	if issue.is_empty() or attach.disabled:
		return
	var number: Variant = null
	if not remove:
		var raw := input.text.strip_edges().trim_prefix("#")
		if not raw.is_valid_int() or raw.to_int() <= 0 or str(raw.to_int()) != raw:
			status.text = "请输入有效的父工单编号"
			return
		number = raw.to_int()
	attach.disabled = true
	detach.disabled = true
	var active := generation
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_PUT, _route(issue), {"parent_number": number, "expected_parent_id": expected_parent})
	if active != generation:
		return
	if reply.status == 200:
		# The parent is part of the I02 content revision. Refresh both views.
		await detail.open_issue(int(issue.number))
		if detail.get_detail().get("id") == issue.id:
			status.text = "已解除父子关系" if remove else "已保存父子关系"
		return
	var feedback := "无法更改工单层级（%d）" % reply.status
	if reply.status == 409:
		feedback = "关系发生冲突或会形成循环，已重新读取"
	elif reply.status == 403:
		feedback = "没有修改父子关系的权限"
	elif reply.status == 404:
		feedback = "当前项目中未找到父工单"
	await _refresh()
	if active + 1 == generation:
		status.text = feedback
