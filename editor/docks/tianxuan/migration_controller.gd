@tool
extends Node
## Published history stays read-only; new tasks have their own explicit intent.

signal changed
var workspace: Node
var publication := {}
var requirement := ""
var entry := ""
var data := {}
var errors := {}
var status := ""
var saving := false
var _generation := 0
var _selection := 0
var _serial := {}
var _record_id := ""
var _status_serial := 0


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(func(topic: String):
		if topic == "identity":
			_generation += 1
			_selection += 1
			publication.clear()
			data.clear()
			errors.clear()
			_serial.clear()
			_record_id = ""
			requirement = ""
			entry = ""
			status = ""
			saving = false
			changed.emit()
		elif topic == "draft:" + key():
			changed.emit()
	)


func key() -> String:
	return "migration:new-task:" + requirement


func draft() -> Dictionary:
	return workspace.load_draft(key())


func edit(title: String) -> void:
	if not saving and not draft().has("submission"):
		workspace.save_draft(key(), {"title": title})


func route(operation: String, args: Dictionary) -> String:
	var query := "revision=" + str(publication.get("catalog_revision", "")).uri_encode()
	for name in args:
		query += "&" + str(name).uri_encode() + "=" + str(args[name]).uri_encode()
	return "/api/v1/migration/history/" + operation + "?" + query


func read(operation: String, args := {}) -> void:
	if not publication.get("available", false) or operation not in ["search", "detail", "body", "commits", "file", "branches", "tags", "commit", "tag_object"]:
		return
	if operation == "detail" and str(args.get("source_id", "")) != _record_id:
		_record_id = str(args.get("source_id", ""))
		_serial.body = int(_serial.get("body", 0)) + 1
		data.erase("body")
		data.erase("detail")
	if operation == "body" and args.get("source_id") != _record_id:
		return
	var generation := _generation
	var selection := _selection
	_serial[operation] = int(_serial.get(operation, 0)) + 1
	var serial: int = _serial[operation]
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route(operation, args))
	if generation != _generation or selection != _selection or serial != _serial.get(operation):
		return
	if result.status == 200:
		data[operation] = result.data
		errors.erase(operation)
	else:
		data.erase(operation)
		errors[operation] = workspace.error_message(result.status)
	changed.emit()


func refresh() -> void:
	var generation := _generation
	var selection := _selection
	_status_serial += 1
	var serial := _status_serial
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, "/api/v1/migration/status")
	if generation != _generation or selection != _selection or serial != _status_serial:
		return
	if result.status == 200:
		if publication.get("catalog_revision") != result.data.get("catalog_revision"):
			_selection += 1
			data.clear()
			errors.clear()
		publication = result.data
	else:
		publication.clear()
		data.clear()
		status = workspace.error_message(result.status)
	changed.emit()
	await load_entry(requirement)


func load_entry(id: String) -> void:
	if saving or draft().has("submission"):
		return
	if id != requirement:
		_selection += 1
		requirement = id.strip_edges()
		data.erase("task")
	entry = ""
	var generation := _generation
	var selection := _selection
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, "/api/v1/migration/entry" + ("?requirement=" + requirement.uri_encode() if not requirement.is_empty() else ""))
	if generation != _generation or selection != _selection:
		return
	if result.status == 200:
		entry = str(result.data.get("entry", ""))
		errors.erase("entry")
	else:
		errors.entry = workspace.error_message(result.status)
	changed.emit()


func snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "requirement": requirement, "entry": entry, "revision": publication.get("catalog_revision", ""), "draft": draft()}


func set_entry(value: String, expected: Dictionary) -> void:
	if saving or expected != snapshot() or workspace.identity().get("role") != "admin" or value not in ["existing", "tianxuan"]:
		return
	saving = true
	var generation := _generation
	var selection := _selection
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_PUT, "/api/v1/migration/entry" + ("?requirement=" + requirement.uri_encode() if not requirement.is_empty() else ""), {"entry": value})
	if generation != _generation or selection != _selection:
		return
	saving = false
	status = "入口已保存。" if result.status == 200 else "入口保存结果未确认，请核对重新读取的当前值。"
	await load_entry(requirement)


func start(expected: Dictionary) -> void:
	if saving or expected != snapshot() or not workspace.can_edit() or entry.is_empty() or str(draft().get("title", "")).strip_edges().is_empty():
		return
	var current := draft()
	if not current.has("submission"):
		current.submission = {"title": str(current.title).strip_edges(), "project": workspace.identity().get("project", "workspace"), "call_id": workspace.new_id()}
		if not requirement.is_empty():
			current.submission.requirement = requirement
		if not workspace.save_draft(key(), current):
			return
	var generation := _generation
	var selection := _selection
	saving = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_POST, "/api/v1/migration/tasks", current.submission)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status == 200:
		data.task = result.data
		workspace.clear_draft(key())
		status = "新任务入口已就绪。"
	elif result.status >= 400 and result.status < 500:
		current.erase("submission")
		workspace.save_draft(key(), current)
		status = workspace.error_message(result.status, true)
	else:
		status = "结果待核对。重试会使用原请求编号，避免重复创建任务。"
	changed.emit()


func download(source_id: String, destination: String, expected: Dictionary) -> void:
	if expected != snapshot():
		return
	var temporary: String = destination.get_base_dir().path_join(".tianxuan-archive-" + workspace.new_id() + ".tmp")
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("attachment", {"source_id": source_id}), {}, 60.0, temporary)
	if expected != snapshot():
		DirAccess.remove_absolute(temporary)
		return
	if result.status == 200:
		var digest := FileAccess.get_sha256(temporary)
		var install: Callable = workspace.get_meta("install_asset_if_absent", Callable())
		var error: int = install.call(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(destination)) if install.is_valid() else ERR_UNAVAILABLE
		if error == OK or (error == ERR_ALREADY_EXISTS and FileAccess.get_sha256(destination) == digest):
			status = "已保存归档原件。"
		elif error == ERR_ALREADY_EXISTS:
			status = "目标已有不同内容，已保留；请选择新文件名。"
		else:
			status = "无法写入目标目录。"
	else:
		status = workspace.error_message(result.status)
	DirAccess.remove_absolute(temporary)
	changed.emit()
