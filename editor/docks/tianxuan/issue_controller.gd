@tool
extends Node
## Shared, editor-owned issue state. Views never own mutations or request receipts.

signal changed

var workspace: Node
var selected := ""
var detail := {}
var sections := {}
var items: Array = []
var catalog := {}
var filters := {}
var status := ""
var section_errors := {}
var loading := false
var listing := false
var saving := false
var _generation := 0
var _selection := 0
var _query := 0
var previews := {}
var _preview_pending := {}
const ROOT := "/api/v1/issues"


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(_workspace_changed)


func _workspace_changed(topic: String) -> void:
	if topic == "identity":
		_generation += 1
		_selection += 1
		_query += 1
		selected = ""
		detail.clear()
		sections.clear()
		items.clear()
		catalog.clear()
		filters.clear()
		section_errors.clear()
		previews.clear()
		_preview_pending.clear()
		loading = false
		listing = false
		saving = false
		status = ""
		changed.emit()
	elif topic.begins_with("draft:issue:"):
		changed.emit()


func route(suffix := "", id := "") -> String:
	return ROOT + "/" + (selected if id.is_empty() else id).uri_encode() + suffix


func draft_key(section: String) -> String:
	return "issue:" + ("new" if selected.is_empty() else selected) + ":" + section


func draft(section: String) -> Dictionary:
	return workspace.load_draft(draft_key(section))


func edit(section: String, values: Dictionary) -> void:
	if saving or not pending().is_empty():
		return
	var previous := draft(section)
	var base: Dictionary = previous.get("base", {"detail": detail.duplicate(true), "sections": sections.duplicate(true)})
	workspace.save_draft(draft_key(section), {"base": base, "values": values.duplicate(true)})


func pending() -> Dictionary:
	return workspace.load_draft(draft_key("pending"))


func draft_outdated(section: String) -> bool:
	var saved := draft(section)
	if saved.is_empty() or detail.is_empty():
		return false
	var previous: Dictionary = saved.get("base", {}).get("detail", {})
	var state: Dictionary = saved.get("base", {}).get("sections", {})
	match section:
		"flow":
			return state.get("flow", {}).get("version") != sections.get("flow", {}).get("version")
		"plan", "log", "field", "asset":
			return state.get("work", {}).get("version") != sections.get("work", {}).get("version")
		"classification":
			return previous.get("type") != detail.get("type") or previous.get("labels") != detail.get("labels")
		"assignee":
			return previous.get("assignee") != detail.get("assignee")
		"hierarchy":
			return previous.get("parent_id") != detail.get("parent_id")
		"target":
			return previous.get("task_target") != detail.get("task_target") or previous.get("design_source") != detail.get("design_source")
	return false


func review_draft(section: String) -> void:
	if not editable() or not draft_outdated(section):
		return
	var saved := draft(section)
	saved.base = {"detail": detail.duplicate(true), "sections": sections.duplicate(true)}
	workspace.save_draft(draft_key(section), saved)
	status = "草稿已对齐核对过的服务器版本，尚未提交。"
	changed.emit()


func editable() -> bool:
	return workspace.can_edit() and not loading and not saving and pending().is_empty() and (selected.is_empty() or detail.get("can_classify", false))


func refresh_list(values: Dictionary = {}) -> void:
	filters = values.duplicate(true)
	_query += 1
	var query := _query
	var generation := _generation
	var url := ROOT
	var params: Array[String] = []
	for key in ["q", "status", "assignee", "module_id", "label", "requirement_id"]:
		if not str(filters.get(key, "")).strip_edges().is_empty():
			params.append(key + "=" + str(filters[key]).strip_edges().uri_encode())
	if not params.is_empty():
		url += "?" + "&".join(params)
	listing = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, url)
	if query != _query or generation != _generation:
		return
	listing = false
	if result.status == 200:
		items = result.data.get("issues", [])
		section_errors.erase("list")
	else:
		items.clear()
		section_errors.list = workspace.error_message(result.status)
	changed.emit()


func load_catalog() -> void:
	var generation := _generation
	for entry in [["modules", "/api/v1/business-modules"], ["users", "/api/v1/users"], ["fields", "/api/v1/work/field-definitions"], ["roadmap", "/api/v1/work/roadmap"], ["judgments", "/api/v1/work/my-judgments"]]:
		var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, entry[1])
		if generation != _generation:
			return
		if result.status == 200:
			catalog[entry[0]] = result.data
			section_errors.erase(entry[0])
		else:
			catalog.erase(entry[0])
			section_errors[entry[0]] = workspace.error_message(result.status)
		changed.emit()


func open(id: String) -> void:
	if saving:
		return
	_selection += 1
	selected = id
	detail.clear()
	sections.clear()
	previews.clear()
	_preview_pending.clear()
	status = ""
	loading = false
	changed.emit()
	if not id.is_empty():
		await refresh()


func refresh() -> void:
	if selected.is_empty() or loading or saving:
		return
	var selection := _selection
	var generation := _generation
	var id := selected
	loading = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route())
	if selection != _selection or generation != _generation:
		return
	if result.status == 200 and result.data.get("project") == workspace.identity().get("project"):
		result = await workspace.session.api_request(HTTPClient.METHOD_GET, ROOT + "/by-number/%d/detail" % int(result.data.number))
		if selection != _selection or generation != _generation:
			return
	if result.status != 200 or result.data.get("id") != id or result.data.get("project") != workspace.identity().get("project"):
		detail.clear()
		sections.clear()
		loading = false
		previews.clear()
		status = workspace.error_message(result.status if result.status != 200 else 404)
		changed.emit()
		return
	detail = result.data
	changed.emit()
	for entry in [["work", "/work"], ["flow", "/work/flow"], ["hierarchy", "/hierarchy"], ["comments", "/comments"], ["lifecycle", "/lifecycle"], ["external", "/external-links"], ["artifacts", "artifacts"]]:
		var url := artifact_route() if entry[0] == "artifacts" else route(entry[1], id)
		result = await workspace.session.api_request(HTTPClient.METHOD_GET, url)
		if selection != _selection or generation != _generation:
			return
		if result.status == 200:
			sections[entry[0]] = result.data
			section_errors.erase(entry[0])
		else:
			sections.erase(entry[0])
			section_errors[entry[0]] = workspace.error_message(result.status)
	loading = false
	changed.emit()


func create() -> void:
	if not selected.is_empty() or not editable():
		return
	var values: Dictionary = draft("create").get("values", {})
	if str(values.get("title", "")).strip_edges().is_empty() or str(values.get("module_id", "")).is_empty():
		status = "请填写工单标题并选择业务模块。"
		changed.emit()
		return
	var payload := values.duplicate(true)
	payload.project = workspace.identity().project
	await _start("create", HTTPClient.METHOD_POST, "/api/v1/tools", {"name": "issue.create", "call_id": workspace.new_id(), "payload": payload}, true)


func submit(section: String) -> void:
	if not editable() or detail.is_empty():
		return
	var saved := draft(section)
	if saved.is_empty():
		return
	var values: Dictionary = saved.get("values", {})
	var base: Dictionary = saved.get("base", {"detail": detail, "sections": sections})
	var previous: Dictionary = base.get("detail", {})
	var state: Dictionary = base.get("sections", {})
	var method := HTTPClient.METHOD_POST
	var suffix := ""
	var payload := {}
	var replayable := true
	match section:
		"asset":
			if not state.has("work") or values.get("kind") not in ["concept", "model"]:
				return
			payload = {"kind": values.kind, "module": str(values.get("module", "")).strip_edges(), "revision": str(values.get("revision", "")).strip_edges(), "path": str(values.get("path", "")).strip_edges(), "expected_version": int(state.work.version), "call_id": workspace.new_id()}
			suffix = "/work/submit_asset"
		"flow":
			var error := flow_error(values)
			if not error.is_empty() or draft_outdated("flow"):
				status = "流程版本已变化，请先比较当前内容与草稿。" if draft_outdated("flow") else error
				changed.emit()
				return
			suffix = "/work/flow/configure"
			payload = {"expected_version": int(state.flow.version), "call_id": workspace.new_id(), "stages": values.stages, "edges": values.edges}
		"classification":
			method = HTTPClient.METHOD_PUT
			suffix = "/classification"
			payload = {"type": values.get("type", "task"), "labels": values.get("labels", []), "expected_type": previous.get("type", ""), "expected_labels": previous.get("labels", [])}
		"assignee":
			method = HTTPClient.METHOD_PUT
			suffix = "/assignee"
			payload = {"assignee_id": values.get("assignee_id"), "expected_assignee_id": previous.assignee.id if previous.get("assignee") is Dictionary else null}
		"hierarchy":
			method = HTTPClient.METHOD_PUT
			suffix = "/hierarchy"
			payload = {"parent_number": values.get("parent_number"), "expected_parent_id": previous.get("parent_id")}
		"module":
			method = HTTPClient.METHOD_PUT
			suffix = "/module"
			payload = {"module_id": values.get("module_id", "")}
			replayable = false
		"target":
			if not previous.get("design_source") is Dictionary:
				return
			method = HTTPClient.METHOD_PUT
			suffix = "/task-target"
			var target: Dictionary = previous.task_target if previous.get("task_target") is Dictionary else {}
			payload = {"document_id": previous.design_source.document_id, "version": int(previous.design_source.version), "expected_revision": int(target.get("revision", 0)), "stage": values.get("stage", ""), "criteria": values.get("criteria", "")}
			replayable = false
		"plan", "log", "field":
			if not state.has("work"):
				return
			suffix = "/work/" + ("plan" if section == "field" else section)
			payload = {"expected_version": int(state.work.version), "call_id": workspace.new_id()}
			if section == "plan":
				payload.plan = values
			elif section == "field":
				payload.field_update = values
			else:
				payload.merge(values)
		"comment":
			if str(values.get("body", "")).strip_edges().is_empty():
				status = "请输入评论内容。"
				changed.emit()
				return
			suffix = "/comments"
			payload = {"body": values.get("body", ""), "parent_id": values.get("parent_id"), "call_id": workspace.new_id()}
		_:
			return
	await _start(section, method, route(suffix), payload, replayable)


func flow_values() -> Dictionary:
	var current: Dictionary = sections.get("flow", {})
	return draft("flow").get("values", {"stages": current.get("stages", []), "edges": current.get("edges", [])}).duplicate(true)


func flow_error(values: Dictionary) -> String:
	if not sections.has("flow") or sections.get("lifecycle", {}).get("managed", false) or detail.get("status") in ["done", "cancelled"]:
		return "当前工单不能修改流程。"
	var stages: Array = values.get("stages", [])
	var edges: Array = values.get("edges", [])
	if stages.size() < 2 or stages.size() > 64 or edges.is_empty() or edges.size() > 512:
		return "流程需要 2–64 个阶段和 1–512 条路径。"
	var by_id := {}
	for stage in stages:
		var id := str(stage.get("id", ""))
		var progress := float(stage.get("progress", -1))
		if id.is_empty() or id.length() > 64 or id != id.strip_edges() or by_id.has(id) or not is_finite(progress) or progress != floor(progress) or progress < 0 or progress > 100:
			return "阶段名称须唯一且不超过 64 字，进度须为 0–100 的整数。"
		if (id == "done" and progress != 100) or (id != "done" and progress == 100):
			return "只有完成阶段 done 的进度可以且必须为 100%。"
		by_id[id] = stage
	if not by_id.has("done") or not by_id.has(sections.flow.status):
		return "请保留当前阶段与完成阶段 done。"
	var seen := {}
	var outgoing := {}
	for edge in edges:
		var source := str(edge.get("from", ""))
		var target := str(edge.get("to", ""))
		var pair := JSON.stringify([source, target])
		if not by_id.has(source) or not by_id.has(target) or source == target or source in ["done", "cancelled"] or seen.has(pair):
			return "路径须连接不同的有效阶段，不可重复，也不能从终态出发。"
		seen[pair] = true
		outgoing[source] = true
	for id in by_id:
		if by_id[id].get("human", false) and not outgoing.has(id):
			return "人工判断阶段必须有可选择的下一阶段。"
	return ""


func action(operation: String, values: Dictionary, expected: Dictionary) -> void:
	if not editable() or detail.is_empty() or expected != action_snapshot():
		status = "工单版本已变化，请重新核对后操作。"
		changed.emit()
		return
	var payload := values.duplicate(true)
	var suffix := ""
	var method := HTTPClient.METHOD_POST
	var replayable := true
	if operation in ["accept", "close", "reopen"] and sections.has("lifecycle"):
		var current: Dictionary = sections.lifecycle
		payload.merge({"expected_version": int(current.version), "asset_version": int(current.asset_version), "revision": current.revision, "call_id": workspace.new_id()})
		suffix = "/lifecycle/" + operation
	elif operation in ["advance", "judge", "dependencies", "configure"] and sections.has("flow"):
		payload.expected_version = int(sections.flow.version)
		payload.call_id = workspace.new_id()
		suffix = "/work/flow/" + operation
	elif operation in ["confirm_task", "revoke_task"] and detail.get("task_confirmation") is Dictionary:
		var confirmation: Dictionary = detail.task_confirmation
		payload = {"document_id": confirmation.document_id, "version": int(confirmation.version), "issue_revision": confirmation.issue_revision, "target_revision": int(confirmation.target_revision), "expected_revision": int(confirmation.revision), "status": "confirmed" if operation == "confirm_task" else "revoked"}
		suffix = "/task-confirmation"
		method = HTTPClient.METHOD_PUT
		replayable = false
	elif operation in ["pause", "resume", "cancel"] and detail.get("execution_progress") is Dictionary and operation in detail.get("execution_control_actions", []):
		var progress: Dictionary = detail.execution_progress
		if not progress.get("control") is Dictionary:
			return
		payload = {"issue": detail.id, "key": progress.id, "expected": int(progress.control.revision)}
		await _start("action", HTTPClient.METHOD_POST, "/api/v1/native/workflow/" + operation, payload, false)
		return
	else:
		return
	await _start("action", method, route(suffix), payload, replayable)


func action_snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "id": selected, "revision": detail.get("revision"), "flow": sections.get("flow", {}).get("version"), "work": sections.get("work", {}).get("version"), "lifecycle": sections.get("lifecycle", {}), "target": detail.get("task_target"), "confirmation": detail.get("task_confirmation"), "execution": detail.get("execution_progress")}


func add_dependency(number: int, expected: Dictionary) -> void:
	if not editable() or number < 1 or expected != action_snapshot():
		return
	var generation := _generation
	var selection := _selection
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, ROOT + "/by-number/%d" % number)
	if generation != _generation or selection != _selection or expected != action_snapshot():
		return
	if result.status != 200 or result.data.get("project") != workspace.identity().get("project"):
		status = workspace.error_message(result.status if result.status != 200 else 404)
		changed.emit()
		return
	var ids: Array = []
	for dependency in sections.get("flow", {}).get("dependencies", []):
		ids.append(dependency.id)
	if result.data.id == selected or result.data.id in ids:
		status = "不能添加自身或重复的上游工单。"
		changed.emit()
		return
	ids.append(result.data.id)
	await action("dependencies", {"dependencies": ids}, expected)


func define_field() -> void:
	if not editable():
		return
	var values: Dictionary = draft("definition").get("values", {})
	var key := str(values.get("key", "")).strip_edges()
	var label := str(values.get("label", "")).strip_edges()
	if key.is_empty() or label.is_empty():
		return
	await _start("definition", HTTPClient.METHOD_PUT, "/api/v1/work/field-definitions/" + key.uri_encode(), {"label": label}, false)


func artifact_route() -> String:
	return ROOT + "/by-number/%d/artifacts" % int(detail.get("number", 0))


func upload_artifact(path: String) -> void:
	if not editable() or detail.is_empty():
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if not file or file.get_length() > 1024 * 1024:
		status = "无法读取文件，单个附件最大为 1 MiB。"
		changed.emit()
		return
	var length := file.get_length()
	var bytes := file.get_buffer(length)
	var complete := bytes.size() == length and file.get_length() == length
	file.close()
	if not complete:
		status = "文件读取期间发生变化，请重新选择。"
		changed.emit()
		return
	# The service deduplicates the exact name and immutable content before binding.
	await _start("upload", HTTPClient.METHOD_POST, artifact_route(), {"name": path.get_file(), "content": Marshalls.raw_to_base64(bytes)}, true)


func artifact_available(reference: Dictionary) -> bool:
	return not detail.is_empty() and reference in sections.get("artifacts", {}).get("artifacts", [])


func inspect_artifact(reference: Dictionary) -> void:
	var key := str(reference.get("version", ""))
	if not artifact_available(reference) or _preview_pending.has(key):
		return
	var generation := _generation
	var selection := _selection
	_preview_pending[key] = true
	previews[key] = {"loading": true}
	changed.emit()
	DirAccess.make_dir_recursive_absolute(workspace.storage_root)
	var temporary: String = workspace.storage_root.path_join("preview-" + workspace.new_id() + ".tmp")
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, artifact_route() + "/" + key, {}, 30.0, temporary, 32 * 1024 * 1024)
	if generation != _generation or selection != _selection:
		DirAccess.remove_absolute(temporary)
		return
	_preview_pending.erase(key)
	var preview := {"loading": false, "error": "无法读取或校验所选原件。"}
	if result.status == 200 and FileAccess.get_sha256(temporary) == reference.get("digest"):
		var file := FileAccess.open(temporary, FileAccess.READ)
		if file:
			var length := file.get_length()
			preview = {"loading": false, "size": length, "reference": reference.duplicate(true)}
			if length <= 32 * 1024 * 1024:
				var bytes := file.get_buffer(length)
				var extension := str(reference.path).get_extension().to_lower()
				if length <= 1024 * 1024 and extension in ["txt", "md", "json", "gd", "gdshader", "tscn", "tres", "py", "cpp", "h", "glsl", "csv", "yaml", "yml", "toml", "ini", "cfg"] and not bytes.has(0):
					var text := bytes.get_string_from_utf8()
					if text.to_utf8_buffer() == bytes:
						preview.text = text
				if workspace.has_meta("asset_decoder_script"):
					var dimensions: Vector2i = workspace.get_meta("asset_decoder_script").image_dimensions(bytes)
					if dimensions.x > 0 and dimensions.y > 0 and dimensions.x <= 8192 and dimensions.y <= 8192 and int(dimensions.x) * int(dimensions.y) <= 16777216:
						var picture := Image.new()
						var decoded := picture.load_png_from_buffer(bytes) if bytes[0] == 0x89 else picture.load_jpg_from_buffer(bytes)
						if decoded == OK:
							preview.texture = ImageTexture.create_from_image(picture)
				if extension == "glb" and workspace.has_meta("asset_decoder_script"):
					preview.merge(workspace.get_meta("asset_decoder_script").decode_glb(bytes))
			file.close()
	DirAccess.remove_absolute(temporary)
	previews[key] = preview
	changed.emit()


func download_artifact(reference: Dictionary, destination: String) -> void:
	if not artifact_available(reference):
		return
	var generation := _generation
	var selection := _selection
	var temporary: String = destination.get_base_dir().path_join(".tianxuan-" + workspace.new_id() + ".tmp")
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, artifact_route() + "/%d" % int(reference.version), {}, 60.0, temporary, 128 * 1024 * 1024)
	if generation != _generation or selection != _selection:
		DirAccess.remove_absolute(temporary)
		return
	if result.status != 200 or FileAccess.get_sha256(temporary) != reference.digest:
		status = "未能读取并校验原件，未写入目标文件。"
	else:
		var install: Callable = workspace.get_meta("install_asset_if_absent", Callable())
		var error: int = install.call(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(destination)) if install.is_valid() else ERR_UNAVAILABLE
		if error == OK or (error == ERR_ALREADY_EXISTS and FileAccess.get_sha256(destination) == reference.digest):
			status = tr("已保存并校验原件：") + destination.get_file()
		elif error == ERR_ALREADY_EXISTS:
			status = "目标已有不同内容，已保留。请选择新文件名保存此版本。"
		else:
			status = "无法写入目标目录，请选择其他保存位置。"
	DirAccess.remove_absolute(temporary)
	changed.emit()


func judge_artifact(reference: Dictionary, operation: String, note: String, recipient: String, expected: Dictionary) -> void:
	if not editable() or not artifact_available(reference) or expected != action_snapshot() or operation not in ["approved", "changes_requested", "transfer"]:
		return
	var chosen := {}
	for judgment in sections.get("work", {}).get("creative_judgments", []):
		if int(judgment.submission_version) == int(reference.get("version", 0)):
			chosen = judgment
	if chosen.is_empty() or chosen.responsible != workspace.identity().get("id") or chosen.decision != "pending":
		status = "此候选当前不等待本人判断，请刷新核对。"
		changed.emit()
		return
	var payload := {"kind": chosen.kind, "module": chosen.module, "revision": chosen.revision, "path": chosen.path, "submission_version": int(chosen.submission_version), "expected_version": int(sections.work.version), "note": note, "call_id": workspace.new_id()}
	if operation == "transfer":
		payload.target = recipient
	else:
		payload.decision = operation
	await _start("judgment", HTTPClient.METHOD_POST, route("/work/" + ("transfer" if operation == "transfer" else "decide")), payload, true)


func edit_artifact(reference: Dictionary, text: String, expected: Dictionary) -> void:
	if not editable() or expected != action_snapshot() or not artifact_available(reference) or text.to_utf8_buffer().size() > 1024 * 1024:
		return
	var payload := {"expected_version": int(sections.work.version), "revision": reference.revision, "content": Marshalls.raw_to_base64(text.to_utf8_buffer()), "call_id": workspace.new_id()}
	await _start("original", HTTPClient.METHOD_POST, artifact_route() + "/%d/edit" % int(reference.version), payload, true)


func _start(section: String, method: int, url: String, payload: Dictionary, replayable: bool) -> void:
	if not pending().is_empty() or saving:
		return
	if not workspace.save_draft(draft_key("pending"), {"section": section, "method": method, "url": url, "payload": payload, "replayable": replayable}):
		status = "无法保存请求记录，请检查草稿存储后再提交。"
		changed.emit()
		return
	await _send_pending()


func retry() -> void:
	if saving or pending().is_empty() or not pending().get("replayable", false) or not workspace.can_edit():
		return
	# Stable call IDs and compare-and-set requests preserve the original version.
	await _send_pending()


func acknowledge_unknown() -> void:
	if saving or pending().is_empty() or pending().get("replayable", false):
		return
	workspace.clear_draft(draft_key("pending"))
	status = "已保留编辑内容，请核对服务器状态后再保存。"
	changed.emit()


func _send_pending() -> void:
	var pending_request := pending()
	if pending_request.is_empty():
		return
	var generation := _generation
	var selection := _selection
	var pending_key := draft_key("pending")
	var content_key := draft_key(pending_request.section)
	saving = true
	status = "正在保存…"
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(int(pending_request.method), pending_request.url, pending_request.payload)
	if generation != _generation or selection != _selection:
		return
	saving = false
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft(pending_key)
		workspace.clear_draft(content_key)
		status = "已保存，正在读取最新状态。"
		if pending_request.section == "create" and result.data.get("id") is String:
			await open(result.data.id)
		else:
			await refresh()
		if generation != _generation:
			return
		if pending_request.section == "definition":
			load_catalog()
		refresh_list(filters)
	elif result.status >= 400 and result.status < 500:
		workspace.clear_draft(pending_key)
		status = workspace.error_message(result.status, true)
		await refresh()
	else:
		status = "未收到明确回执。已保留原请求；刷新核对后可重试同一请求。" if pending_request.replayable else "写入结果待核对。请刷新并确认服务器状态后恢复编辑。"
	changed.emit()
