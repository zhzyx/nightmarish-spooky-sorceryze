@tool
extends Node
## Shared hosted repository, review and merge-queue state.

signal changed

var workspace: Node
var repository_owner := ""
var repository := ""
var pull_number := 0
var release_id := 0
var queue_id := ""
var filter := "open"
var page := 1
var data := {}
var errors := {}
var status := ""
var saving := false
var _generation := 0
var _selection := 0
var _serial := {}
var _pending := {}


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(_workspace_changed)


func _workspace_changed(topic: String) -> void:
	if topic == "identity":
		_generation += 1
		_selection += 1
		repository_owner = ""
		repository = ""
		pull_number = 0
		release_id = 0
		queue_id = ""
		filter = "open"
		page = 1
		data.clear()
		errors.clear()
		_pending.clear()
		_serial.clear()
		status = ""
		saving = false
		changed.emit()
		if not workspace.identity().is_empty():
			load_catalog.call_deferred()
	elif topic.begins_with("draft:repository-collaboration:"):
		changed.emit()


func base() -> String:
	return "/api/v1/repos/" + repository_owner.uri_encode() + "/" + repository.uri_encode()


func key(section: String) -> String:
	var record := ":%d" % release_id if section == "update_release" else (":%d" % pull_number if section in ["review_pull", "merge_pull"] else "")
	return "repository-collaboration:" + repository_owner + "/" + repository + ":" + section + record


func draft(section: String) -> Dictionary:
	return workspace.load_draft(key(section))


func edit(section: String, values: Dictionary) -> void:
	if not saving and draft("pending").is_empty():
		var retained := values.duplicate(true)
		if section in ["review_pull", "merge_pull", "update_release"]:
			retained["_baseline"] = draft(section).get("_baseline", revision(section))
		workspace.save_draft(key(section), retained)


func busy(topic: String) -> bool:
	return _pending.has(topic)


func writable() -> bool:
	return workspace.can_edit() and not saving and draft("pending").is_empty()


func read(topic: String, route: String, scoped := true) -> Dictionary:
	var generation := _generation
	var selection := _selection
	_serial[topic] = int(_serial.get(topic, 0)) + 1
	var serial: int = _serial[topic]
	_pending[topic] = serial
	changed.emit()
	var response: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route)
	if generation != _generation or (scoped and selection != _selection) or serial != _serial.get(topic):
		return {"status": 0, "data": {}, "stale": true}
	_pending.erase(topic)
	if response.status == 200:
		data[topic] = response.data
		errors.erase(topic)
	else:
		data.erase(topic)
		errors[topic] = workspace.error_message(response.status)
	changed.emit()
	return response


func load_catalog() -> void:
	var generation := _generation
	await read("configuration", "/api/v1/gitea/status", false)
	if generation != _generation:
		return
	if data.get("configuration", {}).get("configured", false):
		await read("repositories", "/api/v1/repos", false)
	if generation != _generation:
		return
	await read("links", "/api/v1/repo-links", false)


func select(selected_owner: String, name: String) -> void:
	if saving:
		return
	_selection += 1
	repository_owner = selected_owner.strip_edges()
	repository = name.strip_edges()
	pull_number = 0
	release_id = 0
	page = 1
	_pending.clear()
	status = ""
	for topic in ["branches", "pulls", "releases", "reviews"]:
		data.erase(topic)
		errors.erase(topic)
	changed.emit()
	if not repository_owner.is_empty() and not repository.is_empty():
		await refresh_repository()


func refresh_repository() -> void:
	if repository_owner.is_empty() or repository.is_empty():
		return
	var selection := _selection
	var generation := _generation
	for topic in ["branches", "pulls", "releases"]:
		var route: String = base() + "/" + topic
		if topic == "pulls":
			route += "?state=" + filter.uri_encode() + "&page=%d&limit=20" % page
		await read(topic, route)
		if selection != _selection or generation != _generation:
			return
	if pull_number > 0:
		await select_pull(pull_number)


func select_pull(number: int) -> void:
	if saving:
		return
	pull_number = number
	data.erase("reviews")
	changed.emit()
	if number > 0:
		await read("reviews", base() + "/pulls/%d/reviews" % number)


func load_queue() -> void:
	var generation := _generation
	for topic in ["queue", "queue_status", "workers"]:
		var suffix: String = {"queue": "?limit=200", "queue_status": "/status", "workers": "/workers"}[topic]
		await read(topic, "/api/v1/merge-queue" + suffix, false)
		if generation != _generation:
			return


func revision(operation: String) -> Dictionary:
	if operation in ["review_pull", "merge_pull"]:
		for pull in data.get("pulls", {}).get("pulls", []):
			if int(pull.number) == pull_number:
				return {"head_sha": pull.get("head_sha", ""), "state": pull.get("state", ""), "base": pull.get("base", "")}
	elif operation == "update_release":
		for release in data.get("releases", {}).get("releases", []):
			if int(release.id) == release_id:
				var result := {}
				for field in ["id", "tag_name", "name", "body", "draft", "prerelease"]:
					result[field] = release[field]
				return result
	return {}


func snapshot() -> Dictionary:
	return {"pull_revision": revision("review_pull"), "release_revision": revision("update_release"),"scope": workspace.session.scope_key(), "owner": repository_owner, "repository": repository, "pull": pull_number, "release": release_id, "queue": queue_id}


func execute(operation: String, values: Dictionary, expected: Dictionary) -> void:
	if expected != snapshot():
		status = "仓库或所选记录已经变化，请重新核对。"
		changed.emit()
		return
	if not writable():
		return
	if operation == "discard_form":
		if values.get("section", "") in ["review_pull", "merge_pull", "update_release"]:
			workspace.clear_draft(key(values.section))
			changed.emit()
		return
	var route := ""
	var method := HTTPClient.METHOD_POST
	var payload := values.duplicate(true)
	var section := operation
	payload.erase("_baseline")
	if operation in ["review_pull", "merge_pull", "update_release"]:
		var baseline := revision(operation)
		var retained := draft(operation)
		if baseline.is_empty() or (not retained.is_empty() and retained.get("_baseline", {}) != baseline):
			status = "内容已经变化；本机草稿已保留。请核对当前记录后重新填写。"
			changed.emit()
			return
		if not data.get("configuration", {}).get("revision_guards", false):
			status = "请升级天璇服务以启用修订校验后再提交。"
			changed.emit()
			return
		if operation == "update_release":
			payload.expected_release = baseline
		else:
			if str(baseline.get("head_sha", "")).is_empty():
				return
			payload.expected_head_sha = baseline.head_sha
			payload.expected_base = baseline.base
	match operation:
		"create_repository":
			route = "/api/v1/repos"
		"create_pull":
			route = base() + "/pulls"
		"review_pull":
			if pull_number < 1:
				return
			route = base() + "/pulls/%d/reviews" % pull_number
		"merge_pull":
			if pull_number < 1:
				return
			route = base() + "/pulls/%d/merge" % pull_number
		"create_release":
			route = base() + "/releases"
		"update_release":
			if release_id < 1:
				return
			route = base() + "/releases/%d" % release_id
			method = HTTPClient.METHOD_PATCH
		"link_repository":
			route = "/api/v1/repo-links"
		"unlink_repository":
			route = "/api/v1/repo-links/" + str(values.get("id", "")).uri_encode()
			method = HTTPClient.METHOD_DELETE
			payload = {}
		"enqueue":
			route = "/api/v1/merge-queue"
		"process_queue":
			route = "/api/v1/merge-queue/process?limit=5"
			payload = {}
		"retry_queue", "cancel_queue":
			if queue_id.is_empty():
				return
			route = "/api/v1/merge-queue/" + queue_id.uri_encode() + ("/retry" if operation == "retry_queue" else "/cancel")
			payload = {}
		_:
			return
	if not workspace.save_draft(key("pending"), {"operation": operation, "route": route, "method": method, "payload": payload, "expected": expected}):
		status = "无法保存请求记录，请检查草稿存储。"
		changed.emit()
		return
	var generation := _generation
	var selection := _selection
	var pending_key := key("pending")
	var form_key := key(section)
	saving = true
	status = "正在提交…"
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(method, route, payload, 60.0)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft(pending_key)
		workspace.clear_draft(form_key)
		status = "操作已接收，请核对刷新后的记录。"
		if operation in ["enqueue", "process_queue", "retry_queue", "cancel_queue"]:
			await load_queue()
		else:
			if operation in ["link_repository", "unlink_repository", "create_repository"]:
				await load_catalog()
			if generation == _generation and selection == _selection:
				await refresh_repository()
	elif result.status >= 400 and result.status < 500 and not (result.status == 400 and operation in ["create_repository", "create_pull", "review_pull", "merge_pull", "create_release", "update_release"]):
		workspace.clear_draft(pending_key)
		status = workspace.error_message(result.status, true)
		if result.status == 409:
			await refresh_repository()
	else:
		status = "写入结果待核对。请刷新服务记录后确认；表单与原请求已保留。"
	changed.emit()


func acknowledge_unknown() -> void:
	if not saving:
		workspace.clear_draft(key("pending"))
		status = "已保留表单，请依据刚核对的服务记录决定后续操作。"
		changed.emit()
