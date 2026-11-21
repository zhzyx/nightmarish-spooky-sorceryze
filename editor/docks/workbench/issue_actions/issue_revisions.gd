@tool
extends VBoxContainer

var detail: Node
var session: Node
var generation := 0
var revision_generation := 0
var module := LineEdit.new()
var reference := LineEdit.new()
var link := Button.new()
var status := Label.new()
var links := VBoxContainer.new()
var revision_view := AcceptDialog.new()
var revision_fields := Label.new()
var work_orders := VBoxContainer.new()


func _ready() -> void:
	detail = get_parent()
	session = detail.get_parent()
	module.name = "RevisionModule"
	module.placeholder_text = "多宝模块"
	add_child(module)
	reference.name = "RevisionReference"
	reference.placeholder_text = "完整修订号，或 tag:标签名"
	add_child(reference)
	link.name = "LinkIssueRevision"
	link.text = "关联多宝提交"
	link.pressed.connect(_link)
	add_child(link)
	status.name = "RevisionLinkStatus"
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(status)
	links.name = "LinkedRevisions"
	add_child(links)
	revision_view.title = "多宝提交详情"
	revision_view.get_ok_button().text = "关闭"
	add_child(revision_view)
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = 480
	revision_view.add_child(box)
	revision_fields.name = "RevisionFields"
	revision_fields.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	box.add_child(revision_fields)
	work_orders.name = "RevisionIssues"
	box.add_child(work_orders)
	detail.detail_changed.connect(_refresh)
	session.identity_changed.connect(_close_revision)
	_refresh()


func _empty(box: Container) -> void:
	for child in box.get_children():
		box.remove_child(child)
		child.queue_free()


func _close_revision() -> void:
	revision_generation += 1
	revision_view.hide()
	revision_fields.text = ""
	_empty(work_orders)


func _route(issue: Dictionary) -> String:
	return "/api/v1/native/issues/%s/revisions" % str(issue.id).uri_encode()


func _refresh() -> void:
	generation += 1
	var attempt := generation
	_empty(links)
	status.text = ""
	module.clear()
	reference.clear()
	var issue: Dictionary = detail.get_detail()
	visible = not issue.is_empty()
	if not visible:
		return
	link.disabled = session.get_identity().get("role") == "viewer"
	var result: Dictionary = await session.api_request(HTTPClient.METHOD_GET, _route(issue))
	if generation != attempt:
		return
	if result.status != 200:
		status.text = "读取关联失败（%d）" % result.status
		return
	for row in result.data.links:
		var open := Button.new()
		open.text = "%s @ %s" % [row.module, str(row.revision).left(12)]
		open.tooltip_text = str(row.revision)
		if row.tag is String:
			open.text += " · " + row.tag
		open.pressed.connect(open_revision.bind(str(row.module), str(row.revision)))
		links.add_child(open)


func _link() -> void:
	var issue: Dictionary = detail.get_detail()
	var source := module.text.strip_edges()
	var ref_name := reference.text.strip_edges()
	if source.is_empty() or ref_name.is_empty() or issue.is_empty():
		status.text = "请填写模块及完整修订号或标签"
		return
	link.disabled = true
	var attempt := generation
	var body := {"module": source, "revision": ref_name}
	if ref_name.begins_with("tag:"):
		var tag := ref_name.trim_prefix("tag:")
		var tag_path := "/api/v1/native/modules/%s/tags/%s" % [source.uri_encode(), tag.uri_encode()]
		var resolved: Dictionary = await session.api_request(HTTPClient.METHOD_GET, tag_path)
		if generation != attempt:
			return
		if resolved.status != 200:
			status.text = "无法读取标签（%d）" % resolved.status
			link.disabled = false
			return
		body.tag = tag
		body.revision = resolved.data.revision
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, _route(issue), body)
	if generation != attempt:
		return
	if reply.status == 200:
		_refresh()
	else:
		status.text = "标签已移动，请重新核对" if reply.status == 409 else "关联提交失败（%d）" % reply.status
		link.disabled = false


func open_revision(source: String, revision: String) -> void:
	_close_revision()
	var attempt := revision_generation
	revision_fields.text = "正在读取提交…"
	revision_view.popup_centered()
	var route := "/api/v1/native/modules/%s/revisions/%s/issue-context" % [source.uri_encode(), revision.uri_encode()]
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
	if revision_generation != attempt:
		return
	if reply.status != 200 or reply.data.get("module") != source or reply.data.get("revision") != revision:
		revision_fields.text = "无法打开提交（%d）" % reply.status
		return
	revision_fields.text = "模块　%s\n修订　%s\n父修订　%s\n文件数　%d" % [source, revision, reply.data.parent if reply.data.parent else "无", reply.data.objects]
	if reply.data.issues.is_empty():
		revision_fields.text += "\n当前项目没有可查看的关联工单"
	for issue in reply.data.issues:
		var open := Button.new()
		open.text = "#%d %s" % [issue.number, issue.title]
		open.pressed.connect(_open_issue.bind(int(issue.number)))
		work_orders.add_child(open)


func _open_issue(number: int) -> void:
	_close_revision()
	var open_sidebar: Callable = detail.get_meta("open_workbench_sidebar")
	open_sidebar.call()
	detail.open_issue(number)
