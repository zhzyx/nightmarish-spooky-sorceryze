@tool
extends Node

signal changed

var workspace: Node
var kind := "native"
var repository := ""
var revision := ""
var branch := ""
var directory := ""
var path := ""
var catalog := {}
var state := {}
var file := {}
var status := ""
var errors := {}
var loading := false
var saving := false
var _generation := 0
var _selection := 0
var _file_serial := 0
var _catalog_pending := {}
var _inspect_serial := {}
var import_jobs: Array = []
var import_status := ""
var import_loading := false
var import_saving := false
var _import_watchers := {}
var _import_retry := 0.0
var _import_backoff := 2.0
var _import_failures := 0
var _import_invalid_source := false


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(_workspace_changed)


func _workspace_changed(topic: String) -> void:
	if topic == "identity":
		_generation += 1
		_selection += 1
		_file_serial += 1
		kind = "native"
		repository = ""
		revision = ""
		branch = ""
		directory = ""
		path = ""
		catalog.clear()
		state.clear()
		file.clear()
		errors.clear()
		_catalog_pending.clear()
		_inspect_serial.clear()
		loading = false
		saving = false
		status = ""
		import_jobs.clear()
		import_status = ""
		import_loading = false
		import_saving = false
		_import_retry = 0.0
		_import_backoff = 2.0
		_import_failures = 0
		_import_invalid_source = false
		changed.emit()
	elif topic.begins_with("draft:repository:"):
		changed.emit()


func route(suffix := "") -> String:
	return ("/api/v1/native/modules/" if kind == "native" else "/api/v1/git/repos/") + repository.uri_encode() + suffix


func draft_key() -> String:
	return "repository:" + kind + ":" + repository + ":" + branch + ":" + path


func draft() -> Dictionary:
	return workspace.load_draft(draft_key())


func editable() -> bool:
	return workspace.can_edit() and not repository.is_empty() and not path.is_empty() and not saving and not loading and file.has("content") and not draft().has("submission") and (kind != "native" or not repository.begins_with("requirement-"))


func update_draft(content: String, message: String) -> void:
	if not editable():
		return
	var current := draft()
	if current.is_empty():
		current = {"base_revision": revision, "base_blob": file.get("sha", ""), "base_content": file.get("content", "")}
	current.content = content
	current.message = message
	workspace.save_draft(draft_key(), current)


func review_draft() -> void:
	if not editable() or draft().is_empty():
		return
	var current := draft()
	current.base_revision = revision
	current.base_blob = file.get("sha", "")
	current.base_content = file.get("content", "")
	workspace.save_draft(draft_key(), current)
	status = "已保留草稿并对齐核对过的版本，尚未提交。"
	changed.emit()


func load_catalog(mode: String, more := false) -> void:
	if mode not in ["native", "git"] or _catalog_pending.has(mode):
		return
	var generation := _generation
	_catalog_pending[mode] = true
	changed.emit()
	var url := "/api/v1/workspace/modules" if mode == "native" else "/api/v1/git/repos"
	var previous: Dictionary = catalog.get(mode, {})
	if more and mode == "native" and previous.get("next_cursor") is String:
		url += "/after/" + str(previous.next_cursor).uri_encode()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, url)
	if generation != _generation:
		return
	_catalog_pending.erase(mode)
	if result.status == 200:
		catalog[mode] = result.data
		if more and mode == "native":
			var combined: Array = previous.get("modules", []).duplicate(true)
			for item in result.data.get("modules", []):
				if not item in combined:
					combined.append(item)
			catalog[mode].modules = combined
		errors.erase(mode)
	else:
		catalog.erase(mode)
		errors[mode] = "此服务尚未配置本地 Git 仓库，或当前配置不可用。" if mode == "git" and result.status == 400 else workspace.error_message(result.status)
	changed.emit()


func select(mode: String, name: String, ref := "") -> void:
	if saving or mode not in ["native", "git"]:
		return
	_selection += 1
	_file_serial += 1
	kind = mode
	repository = name
	revision = ref if mode == "native" else ""
	branch = ref if mode == "git" else ""
	directory = ""
	path = ""
	file.clear()
	state.clear()
	status = ""
	loading = false
	changed.emit()
	if not name.is_empty():
		await refresh()


func refresh() -> void:
	if loading or saving or repository.is_empty():
		return
	var generation := _generation
	var selection := _selection
	loading = true
	changed.emit()
	if kind == "native":
		var head: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("/head"))
		if generation != _generation or selection != _selection:
			return
		if head.status != 200:
			state.clear()
			file.clear()
			loading = false
			status = workspace.error_message(head.status)
			changed.emit()
			return
		state.head = head.data.get("revision")
		if revision.is_empty():
			revision = str(head.data.revision) if head.data.get("revision") is String else ""
		if not revision.is_empty():
			var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("/revisions/" + revision.uri_encode()))
			if generation != _generation or selection != _selection:
				return
			if result.status == 200:
				state.revision = result.data
				status = ""
			else:
				state.erase("revision")
				file.clear()
				status = workspace.error_message(result.status)
	else:
		for entry in [["branches", "/branches"], ["tags", "/tags"]]:
			var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route(entry[1]))
			if generation != _generation or selection != _selection:
				return
			if result.status == 200:
				state[entry[0]] = result.data.get(entry[0], [])
			else:
				errors[entry[0]] = workspace.error_message(result.status)
		if branch.is_empty() and not state.get("branches", []).is_empty():
			branch = str(state.branches[0])
		if not branch.is_empty():
			for entry in [["commits", "/log?limit=50&ref=" + branch.uri_encode()], ["tree", "/tree?ref=" + branch.uri_encode() + "&path=" + directory.uri_encode()]]:
				var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route(entry[1]))
				if generation != _generation or selection != _selection:
					return
				if result.status == 200:
					state[entry[0]] = result.data
					errors.erase(entry[0])
				else:
					state.erase(entry[0])
					errors[entry[0]] = workspace.error_message(result.status)
	loading = false
	changed.emit()


func open_directory(value: String) -> void:
	if kind != "git" or loading or saving:
		return
	directory = value
	await refresh()


func open_file(value: String) -> void:
	if saving or loading:
		return
	_file_serial += 1
	var serial := _file_serial
	var selection := _selection
	var generation := _generation
	path = value
	file.clear()
	status = "正在读取文件…"
	changed.emit()
	if kind == "native":
		if not state.get("revision", {}).get("objects", {}).has(path):
			status = "当前修订不包含此文件。"
			changed.emit()
			return
		DirAccess.make_dir_recursive_absolute(workspace.storage_root)
		var temporary: String = workspace.storage_root.path_join("repository-" + workspace.new_id() + ".tmp")
		var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("/revisions/" + revision.uri_encode() + "/objects/" + path.uri_encode()), {}, 30.0, temporary)
		if generation != _generation or selection != _selection or serial != _file_serial:
			DirAccess.remove_absolute(temporary)
			return
		if result.status == 200 and FileAccess.get_sha256(temporary) == state.get("revision", {}).get("objects", {}).get(path):
			var bytes := FileAccess.get_file_as_bytes(temporary)
			file = {"size": bytes.size(), "path": path, "sha": FileAccess.get_sha256(temporary)}
			if bytes.size() <= 1024 * 1024 and not bytes.has(0):
				var content := bytes.get_string_from_utf8()
				if content.to_utf8_buffer() == bytes:
					file.content = content
			status = "" if file.has("content") else "此文件为二进制内容，可保存原件。"
		else:
			status = "原件摘要不匹配，未显示或保存此文件。" if result.status == 200 else workspace.error_message(result.status)
		DirAccess.remove_absolute(temporary)
	else:
		var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("/file?branch=" + branch.uri_encode() + "&path=" + path.uri_encode()))
		if generation != _generation or selection != _selection or serial != _file_serial:
			return
		if result.status == 200:
			file = result.data
			status = ""
		else:
			status = "此文件不能作为文本打开，请选择普通文本文件（最大 1 MB）。" if result.status in [413, 415] else workspace.error_message(result.status)
	changed.emit()


func save() -> void:
	if not editable():
		return
	var current := draft()
	if not current.has("content") or str(current.content) == str(current.get("base_content", "")):
		return
	if str(current.content).to_utf8_buffer().size() > 1000000:
		status = "文件超过 1 MB，请缩小后提交。"
		changed.emit()
		return
	if kind == "native":
		current.submission = {"request_key": workspace.new_id(), "changes": [{"module": repository, "base": current.base_revision, "reads": null, "edits": {path: Marshalls.raw_to_base64(str(current.content).to_utf8_buffer())}}]}
	else:
		if str(current.get("message", "")).strip_edges().is_empty():
			status = "请填写提交说明。"
			changed.emit()
			return
		current.submission = {"branch": branch, "path": path, "expected_blob": current.base_blob, "content": current.content, "message": current.message}
	if not workspace.save_draft(draft_key(), current):
		status = "无法保存请求记录，请检查草稿存储。"
		changed.emit()
		return
	await _send()


func retry_native() -> void:
	if kind != "native" or saving or not draft().has("submission"):
		return
	await _send(true)


func acknowledge_unknown_git() -> void:
	if kind != "git" or saving:
		return
	var current := draft()
	current.erase("submission")
	workspace.save_draft(draft_key(), current)
	status = "已保留草稿，请在分支和提交记录中核对上次写入后再决定是否提交。"
	changed.emit()


func _send(check_receipt := false) -> void:
	var current := draft()
	if not current.has("submission") or not workspace.can_edit():
		return
	var generation := _generation
	var selection := _selection
	var key := draft_key()
	var selected_path := path
	saving = true
	status = "正在提交…"
	changed.emit()
	var result := {}
	if check_receipt and kind == "native":
		var receipt: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, "/api/v1/native/batches/" + str(current.submission.request_key).uri_encode())
		if generation != _generation or selection != _selection:
			return
		if receipt.status != 200:
			saving = false
			status = "暂时无法核对原请求回执，请稍后刷新重试。"
			changed.emit()
			return
		if receipt.data.get("receipt") is Dictionary:
			result = {"status": 200, "data": receipt.data.receipt}
	if result.is_empty():
		result = await workspace.session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches" if kind == "native" else route("/file"), current.submission)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft(key)
		if kind == "native":
			revision = str(result.data.get("revisions", {}).get(repository, revision))
			status = "已保存新的原生修订。"
		else:
			branch = str(result.data.get("branch", branch))
			status = tr("已保存至新分支：") + branch
			state.last_commit = result.data
		var receipt := status
		await refresh()
		if generation != _generation or selection != _selection:
			return
		await open_file(selected_path)
		if generation == _generation and selection == _selection:
			status = receipt
		load_catalog(kind)
	elif result.status >= 400 and result.status < 500:
		current.erase("submission")
		workspace.save_draft(key, current)
		status = workspace.error_message(result.status, true)
	else:
		status = "未收到明确回执。原请求已保留，可以重试同一请求。" if kind == "native" else "写入结果待核对，请先刷新分支及提交记录。草稿已保留。"
	changed.emit()


func inspect(topic: String, query := "", other := "") -> void:
	if kind != "git" or repository.is_empty() or branch.is_empty():
		return
	var suffix := ""
	match topic:
		"search": suffix = "/search?ref=" + branch.uri_encode() + "&q=" + query.uri_encode()
		"diff": suffix = "/diff?a=" + query.uri_encode() + "&b=" + other.uri_encode()
		"blame": suffix = "/blame?ref=" + branch.uri_encode() + "&path=" + path.uri_encode()
		_: return
	var generation := _generation
	var selection := _selection
	_inspect_serial[topic] = int(_inspect_serial.get(topic, 0)) + 1
	var serial: int = _inspect_serial[topic]
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route(suffix))
	if generation != _generation or selection != _selection or serial != _inspect_serial.get(topic):
		return
	if result.status == 200:
		state[topic] = result.data
		errors.erase(topic)
	else:
		state.erase(topic)
		errors[topic] = workspace.error_message(result.status)
	changed.emit()


func download_native(destination: String) -> void:
	if kind != "native" or file.is_empty():
		return
	var generation := _generation
	var selection := _selection
	var serial := _file_serial
	var digest := str(file.sha)
	var temporary: String = destination.get_base_dir().path_join(".tianxuan-" + workspace.new_id() + ".tmp")
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route("/revisions/" + revision.uri_encode() + "/objects/" + path.uri_encode()), {}, 60.0, temporary)
	if generation != _generation or selection != _selection or serial != _file_serial:
		DirAccess.remove_absolute(temporary)
		return
	if result.status != 200 or FileAccess.get_sha256(temporary) != digest:
		status = "无法取得摘要一致的原件。"
	else:
		var install: Callable = workspace.get_meta("install_asset_if_absent", Callable())
		var error: int = install.call(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(destination)) if install.is_valid() else ERR_UNAVAILABLE
		if error == OK or (error == ERR_ALREADY_EXISTS and FileAccess.get_sha256(destination) == digest):
			status = "原件已保存。"
		elif error == ERR_ALREADY_EXISTS:
			status = "目标已有不同内容，已保留。请选择新文件名。"
		else:
			status = "无法写入目标目录。"
	DirAccess.remove_absolute(temporary)
	changed.emit()


func git_snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "repository": repository, "branch": branch, "branches": state.get("branches", []).duplicate(), "tags": state.get("tags", []).duplicate(true)}


func management_key() -> String:
	return "repository:operations:" + kind + ":" + repository


func manage_git(operation: String, values: Dictionary, expected: Dictionary) -> void:
	if expected != git_snapshot():
		status = "仓库选择或分支记录已经变化，请重新核对后操作。"
		changed.emit()
		return
	if kind != "git" or repository.is_empty() or saving or loading or not workspace.can_edit() or not workspace.load_draft(management_key()).is_empty():
		return
	var method := HTTPClient.METHOD_POST
	var suffix := ""
	var payload := {}
	match operation:
		"create_branch":
			suffix = "/branches"
			payload = {"name": values.get("name", ""), "start": values.get("ref", branch)}
		"delete_branch":
			suffix = "/branches/" + str(values.get("name", "")).uri_encode()
			method = HTTPClient.METHOD_DELETE
		"create_tag":
			suffix = "/tags"
			payload = {"name": values.get("name", ""), "ref": values.get("ref", branch), "message": values.get("message", "")}
		"delete_tag":
			suffix = "/tags/" + str(values.get("name", "")).uri_encode()
			method = HTTPClient.METHOD_DELETE
		_:
			return
	var generation := _generation
	var selection := _selection
	var key := management_key()
	if not workspace.save_draft(key, {"operation": operation, "values": values, "expected": expected}):
		return
	saving = true
	changed.emit()

	var result: Dictionary = await workspace.session.api_request(method, route(suffix), payload)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft(key)
		if operation == "delete_branch" and values.get("name") == branch:
			branch = ""
			path = ""
			file.clear()
		await refresh()
		if generation == _generation and selection == _selection:
			status = "操作已接收，分支与标签已重新读取。"
	elif result.status >= 400 and result.status < 500:
		workspace.clear_draft(key)
		status = workspace.error_message(result.status, true)
	else:
		status = "分支或标签操作结果待核对，请刷新记录后确认。"
	changed.emit()

func import_draft() -> Dictionary:
	return workspace.load_draft("repository:import-form")


func import_pending() -> Dictionary:
	return workspace.load_draft("repository:import-pending")


func can_import() -> bool:
	return workspace.identity().get("role") == "admin" and not import_saving and not import_loading and import_pending().is_empty()


func edit_import(name: String, source: String) -> void:
	if workspace.identity().get("role") == "admin" and not import_saving and import_pending().is_empty():
		_import_invalid_source = "://" in source and "@" in source.split("://", true, 1)[1].get_slice("/", 0)
		if _import_invalid_source:
			import_status = "来源地址不能包含凭据，请由服务端配置仓库访问身份。"
			changed.emit()
			return
		workspace.save_draft("repository:import-form", {"name": name, "source": source})


func import_error() -> String:
	if _import_invalid_source:
		return "来源地址不能包含凭据。"
	var values := import_draft()
	var name := str(values.get("name", "")).strip_edges()
	var source := str(values.get("source", "")).strip_edges()
	if name.is_empty() or source.is_empty():
		return "请填写目标仓库名称与来源。"
	if "/" in name or "\\" in name or name in [".", ".."]:
		return "仓库名称不能包含路径。"
	if "://" in source and "@" in source.split("://", true, 1)[1].get_slice("/", 0):
		return "来源地址不能包含凭据，请由服务端配置仓库访问身份。"
	return ""


func start_import(expected: Dictionary, scope: String) -> void:
	if not can_import() or expected != import_draft() or scope != workspace.session.scope_key():
		return
	import_status = import_error()
	if not import_status.is_empty():
		changed.emit()
		return
	var values := {"name": str(expected.name).strip_edges(), "source": str(expected.source).strip_edges()}
	if not workspace.save_draft("repository:import-pending", values):
		import_status = "无法保存导入意图，请检查本机草稿存储。"
		changed.emit()
		return
	var generation := _generation
	import_saving = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_POST, "/api/v1/git/import-jobs", values)
	if generation != _generation:
		return
	import_saving = false
	if result.status == 200 and result.data.get("id") is String:
		workspace.clear_draft("repository:import-pending")
		workspace.clear_draft("repository:import-form")
		import_status = "导入任务已创建；切换或关闭页面不会停止服务器任务。"
		await refresh_imports()
	elif result.status >= 400 and result.status < 500:
		workspace.clear_draft("repository:import-pending")
		import_status = workspace.error_message(result.status, true)
	else:
		import_status = "导入是否创建尚未确认。请刷新任务列表核对名称与来源，避免重复创建。"
	changed.emit()


func refresh_imports() -> void:
	if import_loading or workspace.identity().is_empty():
		return
	var generation := _generation
	import_loading = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, "/api/v1/git/import-jobs?limit=100")
	if generation != _generation:
		return
	import_loading = false
	if result.status == 200:
		var jobs: Array = result.data.get("jobs", [])
		_import_backoff = minf(20.0, _import_backoff * 1.5) if jobs == import_jobs else 2.0
		var completed := jobs.any(func(job: Dictionary): return job.get("status") == "succeeded" and not import_jobs.any(func(previous: Dictionary): return previous.id == job.id and previous.status == "succeeded"))
		import_jobs = jobs
		_import_failures = 0
		if completed:
			load_catalog("git")
	else:
		_import_failures += 1
		_import_backoff = minf(20.0, _import_backoff * 2)
		import_status = workspace.error_message(result.status)
		if result.status in [401, 403]:
			import_jobs.clear()
			_import_failures = 5
	_import_retry = _import_backoff
	changed.emit()


func acknowledge_import() -> void:
	if not import_saving and not import_loading:
		workspace.clear_draft("repository:import-pending")
		import_status = "已保留表单，请依据已核对的任务记录决定后续操作。"
		changed.emit()


func observe_imports(view: Node, enabled: bool) -> void:
	if enabled:
		_import_watchers[view.get_instance_id()] = weakref(view)
		_import_retry = 0.0
		_import_failures = 0
	else:
		_import_watchers.erase(view.get_instance_id())


func _process(delta: float) -> void:
	for id in _import_watchers.keys():
		if _import_watchers[id].get_ref() == null:
			_import_watchers.erase(id)
	if _import_watchers.is_empty() or workspace.identity().is_empty() or import_loading or import_saving or _import_failures >= 5 or not import_jobs.any(func(job: Dictionary): return job.get("status") in ["queued", "running"]):
		return
	_import_retry -= delta
	if _import_retry <= 0:
		_import_retry = _import_backoff
		refresh_imports()
