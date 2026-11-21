@tool
extends VBoxContainer

var detail: Node
var session: Node
var generation := 0
var query_generation := 0
var edit := VBoxContainer.new()
var kind := LineEdit.new()
var labels := TextEdit.new()
var save := Button.new()
var query := LineEdit.new()
var find_button := Button.new()
var matches := VBoxContainer.new()
var feedback := Label.new()
var lookup_status := Label.new()


func _ready() -> void:
	detail = get_parent()
	session = detail.get_parent()
	add_child(edit)
	var caption := Label.new()
	caption.text = "工单类型"
	edit.add_child(caption)
	kind.name = "IssueType"
	edit.add_child(kind)
	var label_caption := Label.new()
	label_caption.text = "工单标签（每行一个）"
	edit.add_child(label_caption)
	labels.name = "IssueLabels"
	labels.custom_minimum_size.y = 64
	edit.add_child(labels)
	save.name = "SaveIssueClassification"
	save.text = "保存分类"
	save.pressed.connect(_save)
	edit.add_child(save)
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	edit.add_child(feedback)
	query.name = "IssueLabelQuery"
	query.placeholder_text = "项目内的标签名"
	query.text_changed.connect(func(_text: String): _clear_matches())
	query.text_submitted.connect(func(_text: String): _search())
	add_child(query)
	find_button.name = "FindIssuesByLabel"
	find_button.text = "按标签查找工单"
	find_button.pressed.connect(_search)
	add_child(find_button)
	add_child(lookup_status)
	add_child(matches)
	session.identity_changed.connect(_reset_search)
	detail.detail_changed.connect(_refresh)
	_reset_search()
	_refresh()


func _reset_search() -> void:
	query.clear()
	_clear_matches()
	visible = not session.get_identity().is_empty()


func _clear_matches() -> void:
	query_generation += 1
	for child in matches.get_children():
		matches.remove_child(child)
		child.queue_free()
	lookup_status.text = ""


func _refresh() -> void:
	generation += 1
	feedback.text = ""
	var issue: Dictionary = detail.get_detail()
	edit.visible = not issue.is_empty()
	kind.text = str(issue.get("type", ""))
	labels.text = "\n".join(issue.get("labels", []))
	var writable: bool = issue.get("can_classify", false)
	kind.editable = writable
	labels.editable = writable
	save.disabled = not writable


func _save() -> void:
	var issue: Dictionary = detail.get_detail()
	if issue.is_empty() or save.disabled:
		return
	var names: Array[String] = []
	for line in labels.text.split("\n", false):
		var label_name := line.strip_edges()
		if not label_name.is_empty() and not names.has(label_name):
			names.append(label_name)
	if kind.text.strip_edges().is_empty():
		feedback.text = "请输入工单类型"
		return
	save.disabled = true
	kind.editable = false
	labels.editable = false
	var active := generation
	var payload := {"type": kind.text.strip_edges(), "labels": names, "expected_type": issue.type, "expected_labels": issue.labels}
	var route := "/api/v1/issues/%s/classification" % str(issue.id).uri_encode()
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_PUT, route, payload)
	if active != generation:
		return
	if reply.status in [200, 403, 409]:
		_clear_matches()
		await detail.open_issue(int(issue.number))
		if detail.get_detail().get("id") == issue.id:
			match int(reply.status):
				200: feedback.text = "已保存分类"
				403: feedback.text = "没有修改权限"
				409: feedback.text = "分类已变化，已重新读取"
	else:
		save.disabled = false
		kind.editable = true
		labels.editable = true
		feedback.text = "保存分类失败（%d）" % reply.status


func _search() -> void:
	_clear_matches()
	var name_to_find := query.text.strip_edges()
	if name_to_find.is_empty():
		lookup_status.text = "请输入标签名"
		return
	var active := query_generation
	var route := "/api/v1/issues?label=" + name_to_find.uri_encode()
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
	if active != query_generation:
		return
	if reply.status != 200 or not reply.data.get("issues") is Array:
		lookup_status.text = "查询失败（%d）" % reply.status
		return
	# Older servers accept unknown query parameters and return the unfiltered list.
	if reply.data.get("label_filter") != {"name": name_to_find, "project": session.get_identity().project}:
		lookup_status.text = "服务未确认项目和标签筛选"
		return
	for issue in reply.data.issues:
		var result := Button.new()
		result.text = "#%d %s" % [issue.number, issue.title]
		result.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		result.tooltip_text = result.text
		result.pressed.connect(detail.open_issue.bind(int(issue.number)))
		matches.add_child(result)
	lookup_status.text = "找到 %d 张工单" % matches.get_child_count()
