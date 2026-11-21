@tool
extends VBoxContainer

var _session: Node
var _generation := 0
var _open := Button.new()
var _dialog := AcceptDialog.new()
var _tree := Tree.new()
var _status := Label.new()
var _detail := Button.new()


func _ready() -> void:
	_session = get_parent()
	_open.name = "OpenIssueRoadmap"
	_open.text = "模块路线图"
	_open.pressed.connect(_browse)
	add_child(_open)
	_dialog.title = "模块路线图"
	_dialog.get_ok_button().text = "关闭"
	_dialog.visibility_changed.connect(_visibility_changed)
	add_child(_dialog)
	var fields := VBoxContainer.new()
	fields.custom_minimum_size = Vector2(440, 360) * EditorInterface.get_editor_scale()
	_dialog.add_child(fields)
	_status.name = "IssueRoadmapStatus"
	fields.add_child(_status)
	_tree.name = "IssueRoadmapTree"
	_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tree.hide_root = true
	_tree.item_selected.connect(_selection_changed)
	_tree.item_activated.connect(_open_issue)
	fields.add_child(_tree)
	_detail.name = "OpenRoadmapIssue"
	_detail.text = "打开工单详情"
	_detail.pressed.connect(_open_issue)
	fields.add_child(_detail)
	_session.identity_changed.connect(_identity_changed)
	_identity_changed()


func _clear() -> void:
	_generation += 1
	_tree.clear()
	_status.text = ""
	_detail.disabled = true


func _visibility_changed() -> void:
	if not _dialog.visible:
		_clear()


func _identity_changed() -> void:
	_dialog.hide()
	_clear()
	_open.disabled = _session.get_identity().is_empty()


func _browse() -> void:
	_clear()
	_dialog.popup_centered()
	var attempt := _generation
	_status.text = "正在读取路线图…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/work/roadmap")
	if attempt != _generation:
		return
	var data: Dictionary = reply.data
	if reply.status != 200 or data.get("project") != _session.get_identity().project or not data.get("items") is Array or not data.get("modules") is Array:
		_status.text = "无法读取当前项目的路线图，请重新打开"
		return
	_render(data)


func _group(parent: TreeItem, caption: String) -> TreeItem:
	var group := parent.create_child()
	group.set_text(0, caption)
	group.collapsed = true
	return group


func _render(data: Dictionary) -> void:
	var root_item := _tree.create_item()
	var by_id := {}
	var names := {}
	var totals := {}
	for module: Dictionary in data.modules:
		names[module.id] = module.name
	for issue: Dictionary in data.items:
		by_id[issue.id] = issue
		var milestone: String = issue.plan.milestone
		totals[milestone] = totals.get(milestone, 0) + 1
	var modules := {}
	var milestones := {}
	var branches := {}
	for issue: Dictionary in data.items:
		var module_id: String = issue.module_id
		if not modules.has(module_id):
			modules[module_id] = _group(root_item, names.get(module_id, module_id))
			milestones[module_id] = {}
			branches[module_id] = {}
		var milestone: String = issue.plan.milestone
		if not milestones[module_id].has(milestone):
			var caption := "未设置里程碑" if milestone.is_empty() else milestone
			milestones[module_id][milestone] = _group(modules[module_id], "%s（项目共 %d 单）" % [caption, totals[milestone]])
			branches[module_id][milestone] = {}
		_add_path(issue, by_id, milestones[module_id][milestone], branches[module_id][milestone])
	_status.text = "%s · %d 张工单" % [data.project, data.items.size()]


func _add_path(issue: Dictionary, by_id: Dictionary, group: TreeItem, nodes: Dictionary) -> void:
	# Cache each ancestor once per module and milestone, including parents planned in other groups.
	var path: Array[Dictionary] = []
	var current := issue
	var visited := {}
	while not nodes.has(current.id):
		if visited.has(current.id):
			return
		visited[current.id] = true
		path.append(current)
		if not by_id.has(current.parent_id):
			break
		current = by_id[current.parent_id]
	var parent: TreeItem = nodes.get(current.id, group)
	path.reverse()
	for entry: Dictionary in path:
		var contextual: bool = entry.module_id != issue.module_id or entry.plan.milestone != issue.plan.milestone
		var caption := "%s#%d · %s" % ["上级 · " if contextual else "", int(entry.number), entry.title]
		parent = _group(parent, caption)
		parent.set_metadata(0, int(entry.number))
		nodes[entry.id] = parent


func _selection_changed() -> void:
	var item := _tree.get_selected()
	_detail.disabled = item == null or not item.get_metadata(0) is int


func _open_issue() -> void:
	var selected := _tree.get_selected()
	if selected != null and selected.get_metadata(0) is int:
		var number: int = selected.get_metadata(0)
		_dialog.hide()
		_session.get_node("WorkbenchIssueDetail").open_issue(number)
