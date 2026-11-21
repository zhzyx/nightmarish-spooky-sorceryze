@tool
extends VBoxContainer

var _detail: Node
var _session: Node
var _issue := {}
var _flow := {}
var _generation := 0
var _busy := false
var _status := Label.new()
var _list := ItemList.new()
var _number := LineEdit.new()
var _add := Button.new()
var _remove := Button.new()
var _refresh := Button.new()


func _ready() -> void:
	_detail = get_parent()
	_session = _detail.get_parent()
	var heading := Label.new()
	heading.text = "上游工单"
	add_child(heading)
	_status.name = "DependencyStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_list.name = "DependencyList"
	_list.hide()
	_list.item_selected.connect(func(_index: int): _controls())
	add_child(_list)
	_number.name = "DependencyNumber"
	_number.placeholder_text = "当前项目的上游工单编号"
	_number.text_submitted.connect(func(_text: String): _add_dependency())
	add_child(_number)
	var actions := HFlowContainer.new()
	add_child(actions)
	_add.name = "AddDependency"
	_add.text = "添加上游"
	_add.pressed.connect(_add_dependency)
	actions.add_child(_add)
	_remove.name = "RemoveDependency"
	_remove.text = "移除选中上游"
	_remove.pressed.connect(_remove_selected)
	actions.add_child(_remove)
	_refresh.name = "RefreshDependencies"
	_refresh.text = "刷新依赖"
	_refresh.pressed.connect(_load_flow)
	actions.add_child(_refresh)
	_detail.detail_changed.connect(_on_detail)
	_on_detail()


func _on_detail() -> void:
	_generation += 1
	_issue = _detail.get_detail()
	_flow.clear()
	_list.clear()
	_number.clear()
	_status.text = ""
	_busy = false
	visible = not _issue.is_empty()
	if visible:
		_load_flow()


func _route() -> String:
	return "/api/v1/issues/%s/work/flow" % str(_issue.id).uri_encode()


func _controls() -> void:
	var editable: bool = not _busy and not _flow.is_empty() and _flow.status not in ["done", "cancelled"] and _session.get_identity().get("role", "") != "viewer"
	_number.editable = editable
	_add.disabled = not editable
	_remove.disabled = not editable or _list.get_selected_items().is_empty()
	_refresh.disabled = _busy


func _loading(message: String) -> void:
	_busy = true
	_status.text = message
	_controls()


func _show_flow(reply: Dictionary) -> void:
	_busy = false
	_flow.clear()
	_list.clear()
	_list.hide()
	var state: Dictionary = reply.data
	if reply.status == 200 and state.get("id") == _issue.id and state.has_all(["version", "status", "dependencies"]):
		_flow = state
		var blocked := 0
		for dep: Dictionary in state.dependencies:
			var reason := "已验收" if dep.accepted else "未验收，阻塞推进"
			var index := _list.add_item("%s　%s　%s" % [dep.title, dep.status, reason])
			_list.set_item_metadata(index, dep.id)
			_list.set_item_tooltip(index, "%s · %s" % [dep.title, dep.id])
			if not dep.accepted:
				blocked += 1
		_list.visible = _list.item_count > 0
		_list.custom_minimum_size.y = mini(_list.item_count, 3) * (_list.get_theme_font_size("font_size") + 8) + 8
		if state.dependencies.is_empty():
			_status.text = "尚未登记上游"
		elif blocked:
			_status.text = "%d 项上游尚未验收" % blocked
		else:
			_status.text = "全部上游已验收"
	elif reply.status == 403:
		_status.text = "没有权限读取工单依赖"
	else:
		_status.text = "无法确认依赖，请刷新重试"
	_controls()


func _load_flow() -> void:
	if _busy or _issue.is_empty():
		return
	var attempt := _generation
	_loading("正在读取依赖…")
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route())
	if attempt == _generation:
		_show_flow(reply)


func _ids() -> Array:
	var ids := []
	for dep: Dictionary in _flow.dependencies:
		ids.append(dep.id)
	return ids


func _add_dependency() -> void:
	if _add.disabled:
		return
	var text := _number.text.strip_edges().trim_prefix("#")
	var number := text.to_int()
	if not text.is_valid_int() or str(number) != text or number < 1:
		_status.text = "请输入有效的正整数上游工单编号"
		return
	var attempt := _generation
	_loading("正在查找上游…")
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues/by-number/%d" % number)
	if attempt != _generation:
		return
	_busy = false
	_controls()
	if reply.status != 200 or int(reply.data.get("number", 0)) != number or reply.data.get("project") != _issue.project or str(reply.data.get("id", "")).is_empty():
		_status.text = "无法读取此上游，请核对编号和权限"
		return
	var ids := _ids()
	if reply.data.id == _issue.id or reply.data.id in ids:
		_status.text = "不能添加自身或重复的上游"
		return
	ids.append(reply.data.id)
	_save(ids)


func _remove_selected() -> void:
	if _remove.disabled or _list.get_selected_items().is_empty():
		return
	var ids := _ids()
	ids.erase(_list.get_item_metadata(_list.get_selected_items()[0]))
	_save(ids)


func _save(ids: Array) -> void:
	var attempt := _generation
	_loading("正在保存依赖…")
	var payload := {"expected_version": int(_flow.version), "dependencies": ids, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, _route() + "/dependencies", payload)
	if attempt != _generation:
		return
	if reply.status == 200:
		_number.clear()
		_show_flow(reply)
		return
	# A lost write reply or concurrent edit needs a fresh version before another edit.
	_busy = false
	await _load_flow()
	if attempt != _generation or _flow.is_empty():
		return
	var detail := str(reply.data.get("detail", ""))
	var message := "保存未确认，请核对当前依赖"
	if reply.status == 403:
		message = "没有权限修改此工单的依赖"
	elif detail == "cyclic dependency":
		message = "无法保存，上游关系形成循环"
	elif detail == "flow version changed":
		message = "依赖版本已变化，请核对后重试"
	elif detail == "native workflow owns this issue":
		message = "此工单的依赖由原生工作流管理"
	_status.text = "%s。%s" % [message, _status.text]
