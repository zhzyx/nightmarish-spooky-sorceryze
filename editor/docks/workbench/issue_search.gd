@tool
extends VBoxContainer

var _session: Node
var _generation := 0
var _open := Button.new()
var _dialog := AcceptDialog.new()
var _modules := OptionButton.new()
var _assignee := LineEdit.new()
var _states := OptionButton.new()
var _keyword := LineEdit.new()
var _search := Button.new()
var _clear := Button.new()
var _status := Label.new()
var _results := ItemList.new()
var _detail := Button.new()
var _module_names := {}


func _ready() -> void:
	_session = get_parent()
	_open.name = "OpenIssueSearch"
	_open.text = "检索工单"
	_open.pressed.connect(_browse)
	add_child(_open)
	_dialog.title = "检索天璇工单"
	_dialog.exclusive = true
	_dialog.get_ok_button().text = "关闭"
	_dialog.visibility_changed.connect(_visibility_changed)
	add_child(_dialog)
	var fields := VBoxContainer.new()
	fields.custom_minimum_size = Vector2(400, 340) * EditorInterface.get_editor_scale()
	_dialog.add_child(fields)
	_modules.name = "IssueSearchModule"
	_modules.tooltip_text = "业务模块"
	fields.add_child(_modules)
	_assignee.name = "IssueSearchAssignee"
	_assignee.placeholder_text = "负责人姓名或 ID"
	fields.add_child(_assignee)
	_states.name = "IssueSearchState"
	_states.add_item("全部状态")
	for state in ["backlog", "planned", "in-progress", "blocked", "in-review", "done", "cancelled"]:
		_states.add_item(state)
		_states.set_item_metadata(_states.item_count - 1, state)
	fields.add_child(_states)
	_keyword.name = "IssueSearchKeyword"
	_keyword.placeholder_text = "搜索工单标题、正文或验收条件"
	fields.add_child(_keyword)
	var actions := HBoxContainer.new()
	fields.add_child(actions)
	_search.text = "查询"
	_search.name = "SearchIssues"
	_search.pressed.connect(_query)
	actions.add_child(_search)
	_clear.text = "清除筛选"
	_clear.name = "ClearIssueFilters"
	_clear.pressed.connect(_reset_filters)
	actions.add_child(_clear)
	_status.name = "IssueSearchStatus"
	fields.add_child(_status)
	_results.name = "IssueSearchResults"
	_results.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_results.item_activated.connect(_open_result)
	_results.item_selected.connect(func(_index: int): _detail.disabled = false)
	fields.add_child(_results)
	_detail.name = "OpenSearchResult"
	_detail.text = "打开工单详情"
	_detail.pressed.connect(_open_selected)
	fields.add_child(_detail)
	for input: LineEdit in [_assignee, _keyword]:
		input.text_changed.connect(func(_text: String): _filters_changed())
		input.text_submitted.connect(func(_text: String): _query())
	for picker: OptionButton in [_modules, _states]:
		picker.item_selected.connect(func(_index: int): _filters_changed())
	_session.identity_changed.connect(_identity_changed)
	_identity_changed()


func _filters_changed() -> void:
	_generation += 1
	_results.clear()
	_status.text = ""
	_detail.disabled = true


func _visibility_changed() -> void:
	if not _dialog.visible:
		_filters_changed()


func _identity_changed() -> void:
	_dialog.hide()
	_filters_changed()
	_modules.clear()
	_module_names.clear()
	_assignee.clear()
	_states.select(0)
	_keyword.clear()
	_open.disabled = _session.get_identity().is_empty()


func _browse() -> void:
	_dialog.popup_centered()
	_filters_changed()
	_modules.clear()
	_module_names.clear()
	_modules.add_item("全部模块")
	_modules.disabled = true
	_assignee.editable = false
	_states.disabled = true
	_keyword.editable = false
	_search.disabled = true
	_clear.disabled = true
	_status.text = "正在读取业务模块…"
	var attempt := _generation
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/business-modules")
	if attempt != _generation:
		return
	if reply.status != 200 or not reply.data.get("modules") is Array:
		_status.text = "无法读取模块，请重新打开检索"
		return
	for module: Dictionary in reply.data.modules:
		_module_names[module.id] = module.name
		_modules.add_item("%s · %s" % [module.name, module.id])
		_modules.set_item_metadata(_modules.item_count - 1, module.id)
	_modules.disabled = false
	_assignee.editable = true
	_states.disabled = false
	_keyword.editable = true
	_search.disabled = false
	_clear.disabled = false
	_reset_filters()


func _reset_filters() -> void:
	_modules.select(0)
	_assignee.clear()
	_states.select(0)
	_keyword.clear()
	_query()


func _query() -> void:
	if _search.disabled:
		return
	_filters_changed()
	var attempt := _generation
	var owner := _assignee.text.strip_edges()
	var keyword := _keyword.text.strip_edges()
	var params := PackedStringArray()
	if _modules.selected > 0:
		params.append("module_id=" + str(_modules.get_selected_metadata()).uri_encode())
	if not owner.is_empty():
		params.append("assignee=" + owner.uri_encode())
	if _states.selected > 0:
		params.append("status=" + str(_states.get_selected_metadata()).uri_encode())
	if not keyword.is_empty():
		params.append("q=" + keyword.uri_encode())
	_status.text = "正在查询…"
	var route := "/api/v1/issues" + ("" if params.is_empty() else "?" + "&".join(params))
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, route)
	if attempt != _generation:
		return
	if reply.status != 200 or not reply.data.get("issues") is Array:
		_status.text = "查询失败，请重试"
		return
	# Older services ignore unknown query parameters and return unfiltered rows with HTTP 200.
	if (not owner.is_empty() or not keyword.is_empty()) and reply.data.get("applied_search") != {"assignee": owner, "q": keyword}:
		_status.text = "服务未确认负责人或关键字筛选，请更新天璇服务"
		return
	for issue: Dictionary in reply.data.issues:
		var index := _results.add_item("#%d · %s · %s" % [int(issue.number), _module_names.get(issue.module_id, issue.module_id), issue.title])
		_results.set_item_metadata(index, int(issue.number))
	_status.text = "没有符合条件的工单" if _results.item_count == 0 else "共 %d 张工单" % _results.item_count


func _open_selected() -> void:
	var selected := _results.get_selected_items()
	if not selected.is_empty():
		_open_result(selected[0])


func _open_result(index: int) -> void:
	var number := int(_results.get_item_metadata(index))
	_dialog.hide()
	_session.get_node("WorkbenchIssueDetail").open_issue(number)
