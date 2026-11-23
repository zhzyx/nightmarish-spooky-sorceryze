@tool
extends Node
## Local inference and durable results are independent of business-service sync.

var workspace: Node
var host: Node
var records := {}
var job := {}
var syncing := {}
var generation := 0
var resetting := false
var recovering := false
const INDEX := "local-conversation-index"


func _ready() -> void:
	workspace = get_meta("workspace")
	host = workspace.get_meta("model_host", null)
	if is_instance_valid(host):
		host.finished.connect(_finished)
	workspace.session.authenticated.connect(_recover)
	workspace.session.connection_changed.connect(_connection_changed)


func reset() -> void:
	resetting = true
	cancel()
	generation += 1
	resetting = false
	recovering = false
	records.clear()
	syncing.clear()


func busy() -> bool:
	return not job.is_empty()


func configuration() -> Dictionary:
	return host.configuration() if is_instance_valid(host) else {"ok": false, "error": "本机模型入口尚未准备完成。"}


func _key(id: String) -> String:
	return "local-conversation:" + id


func _record(id: String) -> Dictionary:
	if not records.has(id):
		var stored: Dictionary = workspace.load_draft(_key(id))
		if not stored.is_empty():
			# A closed editor cannot still own an in-flight inference.
			for turn in stored.get("turns", []):
				if turn.state == "pending":
					turn.state = "unanswered"
					turn.local_error = "上次本机调用已中断，消息已保留；请核对后重新发送。"
			records[id] = stored
	return records.get(id, {}).duplicate(true)


func _save(id: String, record: Dictionary) -> bool:
	var index: Dictionary = workspace.load_draft(INDEX)
	var ids: Array = index.get("ids", []).duplicate()
	if not ids.has(id):
		ids.append(id)
		if not workspace.save_draft(INDEX, {"ids": ids}):
			workspace._drafts[INDEX] = index
			workspace.errors.chat = "无法保存本机回复，请先复制内容并检查存储空间。"
			workspace.changed.emit("chat")
			return false
	var previous: Dictionary = workspace.load_draft(_key(id))
	if not workspace.save_draft(_key(id), record):
		workspace._drafts[_key(id)] = previous
		workspace.errors.chat = "无法保存本机回复，请先复制内容并检查存储空间。"
		workspace.changed.emit("chat")
		return false
	records[id] = record.duplicate(true)
	return true


func overlay(id: String, remote: Dictionary) -> Dictionary:
	var record := _record(id)
	if record.is_empty():
		return remote
	var result: Dictionary = remote.duplicate(true) if not remote.is_empty() else record.base.duplicate(true)
	var known := {}
	for turn in result.get("turns", []):
		known[turn.id] = true
	var anchor := ""
	var local_turns: Array = record.get("turns", []).duplicate()
	local_turns.reverse()
	for turn in local_turns:
		if not known.has(turn.id):
			var position: int = result.turns.size()
			for index in result.turns.size():
				if result.turns[index].id == anchor:
					position = index
					break
			result.turns.insert(position, turn.duplicate(true))
		anchor = turn.id
	if str(result.get("title", "")).is_empty():
		result.title = record.base.get("title", "")
	result.local_sync = record.get("sync_status", "")
	return result


func summaries(remote: Array) -> Array:
	var result := remote.duplicate(true)
	var known := {}
	for item in result:
		known[item.id] = true
	for id in workspace.load_draft(INDEX).get("ids", []):
		var record := _record(str(id))
		if not record.is_empty() and not known.has(id):
			result.push_front({"id": id, "title": record.base.get("title", "未命名对话"), "updated_at": record.get("updated_at", "")})
	return result


func observe(id: String, remote: Dictionary) -> void:
	var record := _record(id)
	if not record.is_empty():
		record.base = remote.duplicate(true)
		_save(id, record)


func _publish(id: String) -> void:
	var record := _record(id)
	if not record.is_empty():
		workspace.cache["conversation:" + id] = overlay(id, record.base)
	var listing: Dictionary = workspace.cache.get("conversations", {"conversations": [], "next": null})
	listing.conversations = summaries(listing.get("conversations", []))
	workspace.cache.conversations = listing
	workspace.changed.emit("conversation:" + id)


func messages(current: Dictionary) -> Array:
	var result := []
	for turn in current.get("turns", []).slice(-12):
		var content := str(turn.content)
		if turn.get("context_snapshot") is Dictionary:
			content += "\n\n编辑器引用：\n" + JSON.stringify(turn.context_snapshot)
		result.append({"role": "user", "content": content})
		if turn.state == "answered":
			result.append({"role": "assistant", "content": str(turn.answer)})
	return result


func send(text: String, references: Dictionary) -> void:
	if busy() or not workspace.can_edit() or text.strip_edges().is_empty() or text.length() > 8000:
		return
	var id: String = workspace.active_conversation
	var current: Dictionary = workspace.conversation()
	if id.is_empty():
		id = workspace.new_id()
	if current.is_empty():
		current = {"id": id, "title": text.split("\n")[0].left(90), "version": 0, "turns": [], "revisions": [], "current": {}, "requirement_id": null, "execution": null}
	for existing in current.get("turns", []):
		if existing.state == "pending":
			return
	if current.get("turns", []).size() >= 100:
		workspace.errors.chat = "此会话已达到消息上限，请新建对话。"
		workspace.changed.emit("chat")
		return
	var record := _record(id)
	if record.is_empty():
		record = {"base": current.duplicate(true), "turns": [], "outbox": {}, "sync_status": ""}
	var turn_id: String = workspace.new_id()
	var model := configuration()
	var turn := {"model_snapshot": model.duplicate(true), "id": turn_id, "content": text, "state": "pending", "answer": null, "model": null, "error": null, "reply_source": "editor-local"}
	if not references.is_empty():
		turn.context_snapshot = references.duplicate(true)
	record.turns.append(turn)
	record.updated_at = Time.get_datetime_string_from_system(true)
	if not _save(id, record):
		return
	var previous: String = workspace.active_conversation
	workspace.active_conversation = id
	if previous.is_empty() and workspace.editor_context:
		workspace.editor_context.move_new_conversation(id)
	workspace.clear_draft(workspace.chat_draft_key(previous))
	job = {"request_id": turn_id, "conversation": id, "kind": "chat", "generation": generation}
	workspace.errors.erase("chat")
	_publish(id)
	workspace.changed.emit("conversation_selection")
	var input := messages(overlay(id, record.base))
	var started: Dictionary = host.start(workspace.session.scope_key(), turn_id, input) if is_instance_valid(host) else {"ok": false, "error": "本机模型入口尚未准备完成。"}
	if not started.get("ok", false):
		_finished(turn_id, started)


func _finished(request_id: String, result: Dictionary) -> void:
	if job.is_empty() or job.request_id != request_id or job.generation != generation:
		return
	var pending := job.duplicate(true)
	job.clear()
	if pending.kind == "design":
		_finish_design(pending, result)
		return
	var id: String = pending.conversation
	var record := _record(id)
	for turn in record.get("turns", []):
		if turn.id != request_id:
			continue
		var text := str(result.get("text", ""))
		if result.get("ok", false) and not text.strip_edges().is_empty() and text.length() <= 16000:
			turn.state = "answered"
			turn.answer = text
			var model_snapshot: Dictionary = result.get("model", turn.model_snapshot) if result.get("model", turn.model_snapshot) is Dictionary else turn.model_snapshot
			turn.model_snapshot = model_snapshot.duplicate(true)
			turn.model = (str(model_snapshot.get("provider", "local")) + ":" + str(model_snapshot.get("id", "default"))).left(256)
			record.sync_status = "本机已保存，等待同步。"
		else:
			turn.state = "unanswered"
			turn.local_error = str(result.get("error", "本机模型未返回完整回复，请检查编辑器的模型连接。"))
	if not _save(id, record):
		# Keep the returned text visible for copying when durable storage fails.
		record.sync_status = "无法保存本机回复，请先复制内容并检查存储空间。"
		records[id] = record
		_publish(id)
		return
	_publish(id)
	if not resetting:
		sync(id)


func cancel() -> void:
	if job.is_empty():
		return
	var request_id: String = job.request_id
	if is_instance_valid(host):
		host.cancel(request_id)
	_finished(request_id, {"ok": false, "error": "已停止本机回复，消息已保留。"})


func sync(id: String) -> void:
	if resetting or syncing.has(id) or not workspace.can_edit():
		return
	var record := _record(id)
	if record.is_empty():
		return
	var outstanding := false
	for turn in record.turns:
		outstanding = outstanding or (turn.state == "answered" and not turn.get("synced", false))
	if not outstanding:
		return
	syncing[id] = true
	var epoch := generation
	var route: String = workspace.CONVERSATIONS + "/" + id.uri_encode()
	var response: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route)
	if epoch != generation:
		return
	if response.status == 404:
		response = await workspace.session.api_request(HTTPClient.METHOD_POST, workspace.CONVERSATIONS, {"id": id})
		if epoch != generation:
			return
	if response.status not in [200, 201]:
		_sync_failed(id, response.status)
		return
	var remote: Dictionary = response.data
	for original in record.turns:
		if original.state != "answered" or original.get("synced", false):
			continue
		record = _record(id)
		var found: Dictionary = {}
		for existing in remote.get("turns", []):
			if existing.id == original.id:
				found = existing
		var payload: Dictionary = record.outbox.get(original.id, {})
		if payload.is_empty():
			if not found.is_empty():
				_sync_failed(id, 409)
				return
			payload = {"id": original.id, "content": original.content, "answer": original.answer, "model": original.model, "expected_version": remote.version}
			if original.has("context_snapshot"):
				payload.context_snapshot = original.context_snapshot.duplicate(true)
			record.outbox[original.id] = payload
			if not _save(id, record):
				syncing.erase(id)
				return
		# Always replay the durable payload. The service checks its normalized digest,
		# including the original version, even after a previous ACK was lost.
		response = await workspace.session.api_request(HTTPClient.METHOD_POST, route + "/local-turns", payload)
		if epoch != generation:
			return
		if response.status != 200:
			if response.status == 409 and found.is_empty():
				# A definite conflict applied nothing; a later explicit sync may rebase.
				record = _record(id)
				record.outbox.erase(original.id)
				_save(id, record)
			_sync_failed(id, response.status)
			return
		remote = response.data
		record = _record(id)
		for turn in record.turns:
			if turn.id == original.id:
				turn.synced = true
		record.outbox.erase(original.id)
		record.base = remote.duplicate(true)
		record.sync_status = "本机已保存，等待同步。" if _outstanding(record) else "已同步到工作区。"
		if not _save(id, record):
			syncing.erase(id)
			return
	syncing.erase(id)
	_publish(id)
	# A second local answer can finish while this batch is awaiting the service.
	if _outstanding(_record(id)):
		sync.call_deferred(id)


func _outstanding(record: Dictionary) -> bool:
	for turn in record.get("turns", []):
		if turn.state == "answered" and not turn.get("synced", false):
			return true
	return false


func _connection_changed() -> void:
	if workspace.session.online:
		_recover.call_deferred()


func _recover() -> void:
	if recovering or resetting or not workspace.can_edit():
		return
	recovering = true
	var epoch := generation
	for id in workspace.load_draft(INDEX).get("ids", []):
		await sync(str(id))
		if epoch != generation:
			return
	recovering = false


func _sync_failed(id: String, status: int) -> void:
	syncing.erase(id)
	var record := _record(id)
	record.sync_status = "本机已保存；当前工作区服务尚不支持本机回复同步。" if status in [404, 405] else "本机已保存，等待同步。" + workspace.error_message(status, true)
	_save(id, record)
	_publish(id)


func suggest(stage: String) -> void:
	if busy() or not workspace.design_open(stage):
		return
	var current: Dictionary = workspace.conversation()
	var key: String = workspace.design_key(stage)
	var draft: Dictionary = workspace.load_draft(key)
	var saved: Dictionary = workspace.design_revision(stage)
	var body: String = draft.get("body", saved.get("body", ""))
	var input := messages(current)
	var confirmed := {}
	for previous in workspace.DESIGN_STAGES.slice(0, workspace.DESIGN_STAGES.find(stage)):
		confirmed[previous] = workspace.design_revision(previous).get("body", "")
	input.append({"role": "user", "content": "已确认的前置阶段：\n" + JSON.stringify(confirmed)})
	input.append({"role": "user", "content": "请根据以上讨论补充设计草稿。阶段：%s；语言：%s。仅输出已有草稿缺少的补充内容，不重复或改写已有段落，不声称已经批准或执行任务。\n\n已有草稿：\n%s" % [stage, workspace.language, body]})
	var request_id: String = workspace.new_id()
	job = {"request_id": request_id, "conversation": current.id, "kind": "design", "stage": stage, "key": key, "draft": draft, "saved": saved, "body": body, "source": _design_source(current), "generation": generation}
	workspace.changed.emit("design")
	var started: Dictionary = host.start(workspace.session.scope_key(), request_id, input) if is_instance_valid(host) else {"ok": false, "error": "本机模型入口尚未准备完成。"}
	if not started.get("ok", false):
		_finished(request_id, started)


func _design_source(current: Dictionary) -> Dictionary:
	return {"current": current.get("current", {}).duplicate(true), "revisions": current.get("revisions", []).duplicate(true), "requirement_id": current.get("requirement_id")}


func _finish_design(pending: Dictionary, result: Dictionary) -> void:
	var text := str(result.get("text", ""))
	var body: String = pending.body
	if not body.strip_edges().is_empty():
		# Keep hand-written content byte for byte even when the model ignores the
		# supplement-only instruction. A repeated full prefix need not be appended.
		if text.begins_with(body):
			text = text.substr(body.length()).strip_edges()
		text = body if text.strip_edges().is_empty() else body + ("\n" if body.ends_with("\n") else "\n\n") + text
	if result.get("ok", false) and not text.strip_edges().is_empty() and text.length() <= 8000 and workspace.active_conversation == pending.conversation and workspace.load_draft(pending.key) == pending.draft and _design_source(workspace.conversation()) == pending.source:
		workspace.update_design_draft(pending.stage, text, str(pending.draft.get("title", pending.saved.get("title", ""))), str(pending.draft.get("acceptance", pending.saved.get("acceptance", ""))))
	else:
		workspace.errors.design = str(result.get("error", "无法生成草稿，或本机内容已更新。你可以继续直接编辑。"))
	workspace.changed.emit("design")
