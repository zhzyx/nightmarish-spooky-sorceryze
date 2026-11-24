@tool
extends Node
## Observations and exact accepted-release rollback share the verified session.

signal changed
var workspace: Node
var selected := ""
var observation := {}
var releases := {}
var status := ""
var action_status := ""
var release_error := ""
var receipt := ""
var loading := false
var saving := false
var _generation := 0
var _selection := 0
var _watchers := {}
var _retry := 0.0
var _backoff := 3.0
var _failures := 0


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(func(topic: String):
		if topic == "identity":
			_generation += 1
			_selection += 1
			selected = ""
			observation.clear()
			releases.clear()
			status = ""
			action_status = ""
			release_error = ""
			receipt = ""
			loading = false
			saving = false
			_failures = 0
			changed.emit()
	)


func route() -> String:
	return "/api/v1/native/entry/" + selected.uri_encode()


func pending() -> Dictionary:
	return workspace.load_draft("execution:rollback:" + selected)


func select(id: String) -> void:
	if saving or (id != selected and not pending().is_empty()):
		status = "请先核对当前发布回退的回执。"
		changed.emit()
		return
	_selection += 1
	selected = id
	observation.clear()
	releases.clear()
	release_error = ""
	receipt = ""
	action_status = ""
	loading = false
	_failures = 0
	_backoff = 3.0
	status = "选择一个执行记录查看进度与内容发布。" if id.is_empty() else "正在读取执行状态…"
	changed.emit()
	if not id.is_empty():
		await refresh()


func settled() -> bool:
	if observation.get("state") != "delivered" or observation.get("tasks", []).is_empty():
		return false
	for task in observation.tasks:
		if task.get("state") not in ["accepted", "failed", "stopped", "superseded", "closed-unresolved"]:
			return false
	return true


func observe(view: Node, enabled: bool) -> void:
	if enabled:
		_watchers[view.get_instance_id()] = weakref(view)
		_retry = 0.0
		_failures = 0
	else:
		_watchers.erase(view.get_instance_id())


func refresh() -> void:
	if selected.is_empty() or loading:
		return
	var generation := _generation
	var selection := _selection
	loading = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route())
	if generation != _generation or selection != _selection:
		return
	if result.status == 200 and result.data.get("entry") == selected:
		_backoff = minf(48.0, _backoff * 2.0) if result.data == observation else 3.0
		observation = result.data
		_failures = 0
		status = ""
	else:
		_failures += 1
		_backoff = minf(48.0, _backoff * 2.0)
		status = "执行状态响应不匹配，未显示。" if result.status == 200 else workspace.error_message(result.status)
		if result.status in [401, 403, 404]:
			observation.clear()
			releases.clear()
			_failures = 5
	if result.status == 200 and result.data.get("entry") == selected:
		await _load_releases(generation, selection)
	if generation != _generation or selection != _selection:
		return
	loading = false
	_retry = _backoff
	changed.emit()


func _load_releases(generation: int, selection: int) -> void:
	var after := 0
	var events: Array = []
	var release_head: Variant = null
	var first := true
	while true:
		var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route() + "/releases?limit=100&after=%d" % after)
		if generation != _generation or selection != _selection:
			return
		if result.status != 200:
			release_error = workspace.error_message(result.status)
			releases.clear()
			return
		if first:
			release_head = result.data.get("head")
			first = false
		elif release_head != result.data.get("head"):
			release_error = "发布版本在读取期间变化，请刷新后重新核对。"
			releases.clear()
			return
		var page: Array = result.data.get("events", [])
		for event in page:
			if event.get("channel") == "stable":
				events.append(event)
		if page.size() < 100:
			events.reverse()
			releases = {"head": release_head, "events": events}
			release_error = ""
			return
		var next := int(page[-1].get("sequence", 0))
		if next <= after:
			release_error = "发布历史游标未前进，请重新读取。"
			releases.clear()
			return
		after = next


func snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "entry": selected, "head": releases.get("head"), "events": releases.get("events", []).duplicate(true)}


func rollback(target: String, expected: Dictionary) -> void:
	if expected != snapshot() or saving or loading or not workspace.can_edit() or not pending().is_empty():
		return
	var accepted := false
	for event in releases.get("events", []):
		if event.get("selection") == target and event.get("accepted", false) and target != releases.get("head"):
			accepted = true
	if not accepted or not releases.get("head") is String:
		return
	var payload := {"call_id": workspace.new_id(), "expected": releases.head, "selection": target}
	if workspace.save_draft("execution:rollback:" + selected, payload):
		await retry_rollback()


func retry_rollback() -> void:
	if saving or loading or not workspace.can_edit() or pending().is_empty():
		return
	var generation := _generation
	var selection := _selection
	saving = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_POST, route() + "/rollback", pending(), 60.0)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status == 200:
		workspace.clear_draft("execution:rollback:" + selected)
		receipt = str(result.data.get("selection", ""))
		action_status = "回退已接收，请核对当前稳定版本与回执。"
		await refresh()
	elif result.status >= 400 and result.status < 500:
		workspace.clear_draft("execution:rollback:" + selected)
		action_status = workspace.error_message(result.status, true)
		await refresh()
	else:
		action_status = "回退结果未确认。原请求已保留，重试会核对同一请求回执。"
	changed.emit()


func _process(delta: float) -> void:
	for id in _watchers.keys():
		if _watchers[id].get_ref() == null:
			_watchers.erase(id)
	if _watchers.is_empty() or selected.is_empty() or workspace.identity().is_empty() or saving or loading or settled() or _failures >= 5:
		return
	_retry -= delta
	if _retry <= 0:
		_retry = _backoff
		refresh()
