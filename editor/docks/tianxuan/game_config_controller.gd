@tool
extends Node
## Versioned configuration, private text drafts and live consumer receipts.

signal changed

const ROOT := "/api/v1/game-config/projects"
const TYPES := ["number", "integer", "boolean", "string", "enum", "json", "reference"]
var workspace: Node
var selected := ""
var project := {}
var projects: Array = []
var clients: Array = []
var versions: Array = []
var status := ""
var connection := "未连接"
var validation: Array[String] = []
var conflicts: Array = []
var saving := false
var loading := false
var _generation := 0
var _selection := 0
var _list_serial := 0
var _room: WebSocketPeer
var _subscribed := false
var _retry := 0.0
var _ping := 0.0
var _forbidden := false


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(_workspace_changed)


func _workspace_changed(topic: String) -> void:
	if topic == "identity":
		_generation += 1
		_selection += 1
		selected = ""
		project.clear()
		projects.clear()
		clients.clear()
		versions.clear()
		validation.clear()
		conflicts.clear()
		status = ""
		saving = false
		loading = false
		_forbidden = false
		_close_room()
		changed.emit()
	elif topic == "draft:" + key():
		changed.emit()


func key() -> String:
	return "game-config:" + (selected if not selected.is_empty() else "new")


func draft() -> Dictionary:
	return workspace.load_draft(key())


func editable() -> bool:
	var current := draft()
	var base: Variant = current.get("base") if not current.is_empty() else project
	var has_base: bool = selected.is_empty() or (base is Dictionary and base.get("id") == selected and int(base.get("version", 0)) > 0)
	# A retained offline draft is editable only with its actual server baseline.
	# Background refreshes may proceed while edits retain that same baseline.
	return workspace.can_edit() and has_base and not saving and not _forbidden and not current.has("submission")


func to_draft(value: Dictionary) -> Dictionary:
	var result := {"title": value.get("title", ""), "features": value.get("features", []).duplicate(true)}
	for feature in result.features:
		feature.description = feature.get("description", "")
		feature.document_id = str(feature.get("document_id") if feature.get("document_id") != null else "")
		for entry in feature.entries:
			entry.description = entry.get("description", "")
			for field in ["value", "default"]:
				entry[field] = JSON.stringify(entry[field]) if entry.type in ["json", "reference"] else str(entry[field]).to_lower() if entry.type == "boolean" else str(entry[field])
			entry.min = str(entry.get("min", ""))
			entry.max = str(entry.get("max", ""))
			entry.options = "\n".join(entry.get("options", []))
	return result


func values() -> Dictionary:
	return draft().get("values", to_draft(project)).duplicate(true)


func edit(value: Dictionary) -> void:
	if not editable():
		return
	var current := draft()
	if current.is_empty():
		current = {"base": project.duplicate(true)}
	current.values = value.duplicate(true)
	validation.clear()
	if not workspace.save_draft(key(), current):
		status = "无法保存本机草稿，请先复制内容。"
	changed.emit()


func field(feature_id: String, entry_id: String, name: String, value: Variant) -> void:
	var current := values()
	if feature_id.is_empty():
		current[name] = value
	else:
		for feature in current.features:
			if feature.id != feature_id:
				continue
			if entry_id.is_empty():
				feature[name] = value
			else:
				for entry in feature.entries:
					if entry.id == entry_id:
						entry[name] = value
	edit(current)


func add_item(feature_id: String, id: String, title: String) -> void:
	var current := values()
	var id_check := RegEx.create_from_string("^[A-Za-z][A-Za-z0-9_-]{0,63}$")
	if not id_check.search(id) or title.strip_edges().is_empty():
		status = "请填写名称；ID 以字母开头，可包含字母、数字、下划线或连字符，最多 64 位。"
		changed.emit()
		return
	var rows: Array = current.features
	if not feature_id.is_empty():
		rows = []
		for feature in current.features:
			if feature.id == feature_id:
				rows = feature.entries
	for row in rows:
		if row.id == id:
			status = "这个 ID 已存在。"
			changed.emit()
			return
	if feature_id.is_empty():
		rows.append({"id": id, "name": title, "description": "", "document_id": "", "entries": []})
	else:
		rows.append({"id": id, "name": title, "kind": "parameter", "type": "number", "value": "0", "default": "0", "description": "", "min": "", "max": "", "options": ""})
	edit(current)


func remove_item(feature_id: String, entry_id: String) -> void:
	var current := values()
	for index in range(current.features.size() - 1, -1, -1):
		var feature: Dictionary = current.features[index]
		if feature.id == feature_id:
			if entry_id.is_empty():
				current.features.remove_at(index)
			else:
				feature.entries = feature.entries.filter(func(entry: Dictionary): return entry.id != entry_id)
	edit(current)


func _portable(value: Variant) -> bool:
	if value is float or value is int:
		return is_finite(float(value)) and (float(value) != floor(float(value)) or absf(float(value)) <= 9007199254740991.0)
	if value is Array or value is Dictionary:
		for item in (value.values() if value is Dictionary else value):
			if not _portable(item):
				return false
	return true


func _same_json(first: Variant, second: Variant) -> bool:
	# JSON responses use floats in Variant; typed outgoing integers remain integers.
	if (first is int or first is float) and (second is int or second is float):
		return float(first) == float(second)
	if first is Dictionary and second is Dictionary:
		if first.size() != second.size():
			return false
		for name in first:
			if not second.has(name) or not _same_json(first[name], second[name]):
				return false
		return true
	if first is Array and second is Array:
		if first.size() != second.size():
			return false
		for index in first.size():
			if not _same_json(first[index], second[index]):
				return false
		return true
	return typeof(first) == typeof(second) and first == second


func parse() -> Dictionary:
	validation.clear()
	var result := values()
	if str(result.title).strip_edges().is_empty() or str(result.title).length() > 200:
		validation.append("项目名称不能为空，且最多 200 字。")
	var references := {}
	for feature in result.features:
		for entry in feature.entries:
			references[feature.id + "/" + entry.id] = true
	for feature in result.features:
		feature.document_id = null if str(feature.document_id).is_empty() else feature.document_id
		if str(feature.name).strip_edges().is_empty():
			validation.append(feature.id + tr("：功能名称不能为空。"))
		for entry in feature.entries:
			var path: String = feature.id + "/" + entry.id
			if str(entry.name).strip_edges().is_empty():
				validation.append(path + tr("：条目名称不能为空。"))
			var options: Array = Array(str(entry.options).split("\n", false))
			for bound in ["min", "max"]:
				var text := str(entry.get(bound, "")).strip_edges()
				entry.erase(bound)
				if entry.type in ["number", "integer"] and not text.is_empty():
					if text.is_valid_float() and _portable(float(text)):
						entry[bound] = float(text)
					else:
						validation.append(path + tr("：数值边界不合法。"))
			if entry.has("min") and entry.has("max") and entry.min > entry.max:
				validation.append(path + tr("：最小值不能大于最大值。"))
			entry.erase("options")
			if entry.type == "enum":
				entry.options = options
				var unique := {}
				for option in options:
					unique[option] = true
				if options.is_empty() or options.size() > 200 or unique.size() != options.size():
					validation.append(path + tr("：枚举选项必须非空且互不重复。"))
			for name in ["value", "default"]:
				var text := str(entry[name])
				var valid := true
				match str(entry.type):
					"number", "integer":
						valid = text.is_valid_float() and _portable(float(text))
						if entry.type == "integer":
							valid = valid and float(text) == floor(float(text))
						entry[name] = (int(float(text)) if valid else 0) if entry.type == "integer" else float(text)
						valid = valid and (not entry.has("min") or entry[name] >= entry.min) and (not entry.has("max") or entry[name] <= entry.max)
					"boolean":
						valid = text in ["true", "false"]
						entry[name] = text == "true"
					"json", "reference":
						var parser := JSON.new()
						valid = parser.parse(text) == OK and _portable(parser.data)
						entry[name] = parser.data
						if entry.type == "reference":
							valid = valid and parser.data is Dictionary and parser.data.size() == 2 and references.has(str(parser.data.get("feature_id", "")) + "/" + str(parser.data.get("entry_id", "")))
					"enum": valid = text in options
					"string": pass
					_: valid = false
				if not valid:
					validation.append(path + (tr("：当前值") if name == "value" else tr("：默认值")) + tr("不符合类型、范围或引用约束。"))
	if JSON.stringify(result).to_utf8_buffer().size() > 1048576:
		validation.append("配置超过 1 MiB。")
	return result if validation.is_empty() else {}


func refresh_list() -> void:
	var generation := _generation
	_list_serial += 1
	var serial := _list_serial
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, ROOT)
	if generation != _generation or serial != _list_serial:
		return
	if result.status == 200:
		projects = result.data.get("projects", [])
	else:
		status = workspace.error_message(result.status)
	changed.emit()


func open(id: String) -> void:
	if saving or draft().has("submission"):
		return
	_selection += 1
	_close_room()
	selected = id
	project.clear()
	clients.clear()
	versions.clear()
	conflicts.clear()
	validation.clear()
	status = ""
	_forbidden = false
	loading = false
	changed.emit()
	if not id.is_empty():
		await refresh()


func _receive(value: Dictionary) -> void:
	if value.get("id") != selected or int(value.get("version", 0)) < int(project.get("version", 0)):
		return
	project = value.duplicate(true)
	changed.emit()


func outdated() -> bool:
	return not draft().is_empty() and int(draft().get("base", {}).get("version", 0)) < int(project.get("version", 0))


func refresh() -> void:
	if selected.is_empty() or loading:
		return
	var generation := _generation
	var selection := _selection
	loading = true
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, ROOT + "/" + selected.uri_encode())
	if generation != _generation or selection != _selection:
		return
	loading = false
	if result.status == 200:
		_forbidden = false
		_receive(result.data)
		connection = "定期同步"
		if not _room:
			_room = workspace.session.join_room("/api/v1/ws/game-config/" + selected.uri_encode())
		if draft().has("submission") and not saving:
			await _sync_submission()
		if generation != _generation or selection != _selection:
			return
		var consumers: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, ROOT + "/" + selected.uri_encode() + "/clients")
		if generation != _generation or selection != _selection:
			return
		if consumers.status == 200:
			clients = consumers.data.get("clients", [])
	else:
		status = workspace.error_message(result.status)
		connection = "离线 · 本机草稿保留"
		if result.status in [403, 404]:
			_forbidden = true
			project.clear()
			clients.clear()
			_close_room()
	changed.emit()


func save() -> void:
	if not editable() or draft().is_empty():
		return
	if outdated():
		status = "协作者已更新配置，请比较并解决冲突后保存。"
		changed.emit()
		return
	var payload := parse()
	if payload.is_empty():
		changed.emit()
		return
	var current := draft()
	if not selected.is_empty():
		payload.expected_version = int(current.base.version)
	current.submission = {"method": HTTPClient.METHOD_POST if selected.is_empty() else HTTPClient.METHOD_PUT, "route": ROOT + ("" if selected.is_empty() else "/" + selected.uri_encode()), "payload": payload, "kind": "create" if selected.is_empty() else "save"}
	if workspace.save_draft(key(), current):
		await _send_submission()


func _send_submission() -> void:
	if saving or not workspace.can_edit() or not draft().has("submission"):
		return
	var generation := _generation
	var selection := _selection
	var original_key := key()
	var submission: Dictionary = draft().submission
	saving = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(int(submission.method), submission.route, submission.payload)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft(original_key)
		status = "已保存；客户端实际应用后显示生效。"
		if submission.kind == "create":
			await open(str(result.data.id))
		elif submission.kind == "restore":
			await refresh()
		else:
			_receive(result.data)
		refresh_list()
	elif result.status >= 400 and result.status < 500:
		var current := draft()
		current.erase("submission")
		workspace.save_draft(original_key, current)
		status = workspace.error_message(result.status, true)
		if result.status == 409:
			await refresh()
	else:
		status = "保存回执待核对。原请求和草稿已保留；重连后先读取服务版本。"
	changed.emit()


func _sync_submission() -> void:
	var submission: Dictionary = draft().get("submission", {})
	if submission.is_empty() or saving or submission.kind == "create" or project.is_empty():
		return
	var expected := int(submission.payload.expected_version)
	if int(project.version) == expected:
		await _send_submission()
	elif int(project.version) > expected:
		var current := draft()
		current.erase("submission")
		if submission.kind == "save" and project.title == submission.payload.title and _same_json(project.features, submission.payload.features):
			workspace.clear_draft(key())
			status = "已核对服务版本，保存成功。"
		else:
			workspace.save_draft(key(), current)
			status = "服务已产生新版本；请比较本机内容与当前版本。"
		changed.emit()


func acknowledge_create() -> void:
	if not saving and selected.is_empty():
		var current := draft()
		current.erase("submission")
		workspace.save_draft(key(), current)
		status = "已保留新项目表单，请根据项目列表核对是否已创建。"
		changed.emit()


func discard() -> void:
	if editable():
		workspace.clear_draft(key())
		conflicts.clear()
		validation.clear()
		changed.emit()


func _merge(base: Variant, local: Variant, remote: Variant, path: Array, choices: Dictionary) -> Variant:
	if local == base:
		return remote
	if remote == base or local == remote:
		return local
	if base is Array and local is Array and remote is Array:
		var ids: Array = []
		var maps := [{}, {}, {}]
		var arrays := [base, local, remote]
		for index in 3:
			for item in arrays[index]:
				maps[index][item.id] = item
		for item in remote + local:
			if not item.id in ids:
				ids.append(item.id)
		var result: Array = []
		for id in ids:
			var item: Variant = _merge(maps[0].get(id), maps[1].get(id), maps[2].get(id), path + [id], choices)
			if item != null:
				result.append(item)
		return result
	if base is Dictionary and local is Dictionary and remote is Dictionary:
		var result := {}
		for name in base.keys() + local.keys() + remote.keys():
			if result.has(name):
				continue
			result[name] = _merge(base.get(name), local.get(name), remote.get(name), path + [name], choices)
		return result
	var id := "/".join(path)
	conflicts.append({"path": id, "local": local, "remote": remote})
	return remote if choices.get(id) == "remote" else local


func compare(choices := {}, apply := false) -> Dictionary:
	conflicts.clear()
	if not outdated() or not editable():
		return {}
	var current := draft()
	var merged: Dictionary = _merge(to_draft(current.base), current.values, to_draft(project), [], choices)
	if apply:
		for conflict in conflicts:
			if choices.get(conflict.path) not in ["local", "remote"]:
				status = "请逐项选择保留本机或服务端内容。"
				changed.emit()
				return merged
		current.base = project.duplicate(true)
		current.values = merged
		workspace.save_draft(key(), current)
		conflicts.clear()
		status = "已合并核对后的草稿；保存后生成新版本。"
	changed.emit()
	return merged


func history() -> void:
	if selected.is_empty():
		return
	var generation := _generation
	var selection := _selection
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + selected.uri_encode() + "/versions")
	if generation != _generation or selection != _selection:
		return
	if result.status == 200:
		versions = result.data.get("versions", [])
	else:
		status = workspace.error_message(result.status)
	changed.emit()


func snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "id": selected, "version": project.get("version", 0), "draft": draft()}


func restore(version: int, expected: Dictionary) -> void:
	if expected != snapshot() or not editable() or selected.is_empty() or not draft().is_empty():
		status = "请先处理当前草稿，再核对版本进行恢复。"
		changed.emit()
		return
	var current := {"base": project.duplicate(true), "values": to_draft(project), "submission": {"method": HTTPClient.METHOD_POST, "route": "/api/v1/docs/" + selected.uri_encode() + "/versions/%d/restore" % version, "payload": {"expected_version": int(project.version)}, "kind": "restore"}}
	if workspace.save_draft(key(), current):
		await _send_submission()


func _close_room() -> void:
	if _room:
		_room.close()
	_room = null
	_subscribed = false
	_retry = 2.0
	_ping = 0.0
	connection = "未连接"


func _process(delta: float) -> void:
	if selected.is_empty() or workspace == null or workspace.identity().is_empty() or _forbidden:
		return
	_retry -= delta
	if _retry <= 0 and draft().has("submission") and not saving:
		_retry = 5.0
		refresh()
	if not _room:
		if _retry <= 0:
			_retry = 5.0
			refresh()
		return
	_room.poll()
	if _room.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		_close_room()
		connection = "重连中 · 本机草稿保留"
		changed.emit()
		return
	if _room.get_ready_state() == WebSocketPeer.STATE_OPEN:
		if not _subscribed:
			_room.send_text(JSON.stringify({"type": "subscribe", "name": "Godot · 天璇"}))
			_subscribed = true
			connection = "实时同步"
			changed.emit()
		_ping -= delta
		if _ping <= 0:
			_room.send_text(JSON.stringify({"type": "ping"}))
			_ping = 10.0
	while _room and _room.get_available_packet_count() > 0:
		var event: Variant = JSON.parse_string(_room.get_packet().get_string_from_utf8())
		if not event is Dictionary:
			continue
		if event.get("type") == "snapshot" and event.get("project") is Dictionary:
			_receive(event.project)
		elif event.get("type") == "clients":
			clients = event.get("clients", [])
			changed.emit()


func _exit_tree() -> void:
	_close_room()
