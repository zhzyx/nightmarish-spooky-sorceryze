extends SceneTree
## Source-level failure/restart/race checks; provider transport is tested in native-shell.

class Session extends Node:
	signal identity_resetting
	signal identity_changed
	signal authenticated
	signal connection_changed
	var online := true
	var role := "admin"
	var scope := "actor-a-project"
	var remote := {}
	var requests := []
	var legacy := false
	var delay := 0.02
	var lose_ack := false
	var accepted := {}
	var generation := 0

	func get_identity() -> Dictionary:
		return {"id": "actor-a", "project": "project", "role": role}

	func scope_key() -> String:
		return scope

	func redact_credentials(value: String) -> String:
		return value

	func api_request(method: int, route: String, payload := {}) -> Dictionary:
		requests.append({"method": method, "route": route, "payload": payload.duplicate(true)})
		await get_tree().create_timer(delay).timeout
		if not online:
			return {"status": 0, "data": {}}
		var id: String = route.get_slice("/", 5)
		if method == HTTPClient.METHOD_GET:
			return {"status": 200, "data": remote[id].duplicate(true)} if remote.has(id) else {"status": 404, "data": {}}
		if route.ends_with("/local-turns"):
			if legacy:
				return {"status": 404, "data": {}}
			var record: Dictionary = remote[id]
			if accepted.has(payload.id):
				return {"status": 200, "data": record.duplicate(true)} if accepted[payload.id] == payload else {"status": 409, "data": {}}
			if payload.expected_version != record.version:
				return {"status": 409, "data": {}}
			var turn: Dictionary = payload.duplicate(true)
			turn.erase("expected_version")
			turn.content = str(turn.content).strip_edges()
			turn.state = "answered"
			turn.error = null
			turn.reply_source = "editor-local"
			record.turns.append(turn)
			record.version += 1
			accepted[payload.id] = payload.duplicate(true)
			if lose_ack:
				lose_ack = false
				return {"status": 0, "data": {}}
			return {"status": 200, "data": record.duplicate(true)}
		if route == "/api/v1/workspace/conversations":
			remote[payload.id] = {"id": payload.id, "title": "", "version": 0, "turns": [], "revisions": [], "current": {}}
			return {"status": 201, "data": remote[payload.id].duplicate(true)}
		return {"status": 500, "data": {}}

class Model extends Node:
	signal finished(id: String, result: Dictionary)
	var inputs := []
	var cancelled := []
	func configuration() -> Dictionary:
		return {"provider": "openai", "id": "fixture", "configured": true}
	func start(scope: String, id: String, messages: Array) -> Dictionary:
		inputs.append({"scope": scope, "id": id, "messages": messages.duplicate(true)})
		return {"ok": true, "model": configuration()}
	func cancel(id: String) -> bool:
		cancelled.append(id)
		return true
	func complete(text: String) -> void:
		finished.emit(inputs.back().id, {"ok": true, "text": text, "model": configuration()})

var checks: Array[String] = []
var workspace: Node
var session: Session
var model: Model

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, description: String) -> bool:
	if not ok:
		push_error(description)
		quit(1)
		return false
	checks.append(description)
	return true

func load_source(path: String) -> GDScript:
	var script := GDScript.new()
	script.source_code = FileAccess.get_file_as_string(OS.get_environment("TX_SOURCE").path_join(path))
	assert(script.reload() == OK)
	return script

func settle() -> void:
	var deadline := Time.get_ticks_msec() + 5000
	while not workspace.local_chat.syncing.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout

func run() -> void:
	session = Session.new()
	model = Model.new()
	root.add_child(session)
	root.add_child(model)
	workspace = load_source("editor/docks/tianxuan/workspace_controller.gd").new()
	workspace.storage_root = OS.get_environment("TX_DRAFTS")
	workspace.set_meta("session_controller", session)
	workspace.set_meta("model_host", model)
	workspace.set_meta("local_conversation_script", load_source("editor/docks/tianxuan/local_conversation_controller.gd"))
	root.add_child(workspace)
	var local: Node = workspace.local_chat
	workspace.send_message("第一条问题")
	var id: String = workspace.active_conversation
	if not check(local.busy() and model.inputs.size() == 1 and workspace.conversation().turns[0].state == "pending", "persist user turn before starting one local request"):
		return
	workspace.send_message("duplicate while busy")
	if not check(model.inputs.size() == 1, "double send cannot duplicate local inference"):
		return
	model.complete("**本机回答**\n\n保留 Markdown。")
	await settle()
	if not check(workspace.conversation().turns[0].answer == "**本机回答**\n\n保留 Markdown。" and session.remote[id].turns.size() == 1 and not local._outstanding(local._record(id)), "local reply is preserved and storage-only sync acknowledges it"):
		return
	if not check(session.remote[id].turns[0].model == "openai:fixture", "provider metadata is normalized without serializing credentials"):
		return
	workspace.send_message("第二条问题")
	var second_id: String = model.inputs.back().id
	local.cancel()
	model.finished.emit(second_id, {"ok": true, "text": "late cancelled answer", "model": model.configuration()})
	if not check(model.cancelled.has(second_id) and workspace.conversation().turns.back().state == "unanswered" and workspace.conversation().turns.back().answer == null, "cancel closes only its request and rejects a late result"):
		return
	session.online = false
	workspace.send_message("离线问题")
	model.complete("离线完整回复")
	await settle()
	var disk: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(workspace._draft_path(local._key(id))))
	if not check(disk.turns.back().answer == "离线完整回复" and local._outstanding(disk), "offline complete answer is durable before synchronization"):
		return
	local.records.clear()
	workspace._drafts.clear()
	workspace.cache.clear()
	if not check(workspace.conversation().turns.back().answer == "离线完整回复", "recreated controller cache restores offline answer from disk"):
		return
	session.online = true
	session.connection_changed.emit()
	await create_timer(0.02).timeout
	await settle()
	if not check(session.remote[id].turns.size() == 2, "reconnect automatically synchronizes persisted answers without inference"):
		return
	session.legacy = true
	workspace.send_message("旧服务问题")
	model.complete("旧服务仍显示本机回复")
	await settle()
	if not check("尚不支持" in workspace.conversation().local_sync and workspace.conversation().turns.back().answer == "旧服务仍显示本机回复", "legacy service leaves real local answer visible with explicit pending sync"):
		return
	for request in session.requests:
		if not check(not request.route.ends_with("/turns") and not request.route.ends_with("/suggest"), "no fallback to cloud inference"):
			return
	session.legacy = false
	await local.sync(id)
	# Complete another answer during an earlier storage-only batch.
	session.delay = 0.1
	workspace.send_message("并发同步一")
	model.complete("并发回复一")
	workspace.send_message("并发同步二")
	model.complete("并发回复二")
	await settle()
	await create_timer(0.05).timeout
	await settle()
	if not check(session.remote[id].turns.size() == 5 and not local._outstanding(local._record(id)), "answers completed during sync are drained in the next batch"):
		return
	if not check(workspace.conversation().turns[1].id == second_id, "cancelled local turn keeps chronological order after later replies synchronize"):
		return
	session.lose_ack = true
	workspace.send_message("  首尾空白与回执丢失  ")
	model.complete("原样回答\n")
	await settle()
	var replay: Dictionary = local._record(id).outbox.duplicate(true)
	if not check(not replay.is_empty() and session.remote[id].turns.size() == 6, "lost synchronization ACK retains exact submitted payload"):
		return
	await local.sync(id)
	if not check(session.remote[id].turns.size() == 6 and local._record(id).outbox.is_empty(), "replay uses normalized server idempotency despite trimmed content without duplicating a turn"):
		return
	var design: Dictionary = session.remote[id].duplicate(true)
	design.current = {"direction": 1}
	design.revisions = [{"stage": "direction", "revision": 1, "body": "已确认方向正文", "confirmed_at": "fixture"}]
	local.observe(id, design)
	local._publish(id)
	workspace.suggest_design("plan")
	if not check("已确认方向正文" in JSON.stringify(model.inputs.back().messages), "next-stage local suggestion includes confirmed predecessor content"):
		return
	design.revisions.append({"stage": "direction", "revision": 2, "body": "修订后的方向", "confirmed_at": "fixture"})
	design.current.direction = 2
	local.observe(id, design)
	local._publish(id)
	model.complete("基于旧方向的草稿")
	if not check(workspace.load_draft(workspace.design_key("plan")).is_empty() and not workspace.errors.get("design", "").is_empty(), "late design result cannot rebase itself onto a changed confirmed stage"):
		return
	workspace.suggest_design("plan")
	model.complete("当前方向对应的策划")
	if not check(workspace.load_draft(workspace.design_key("plan")).body == "当前方向对应的策划", "unchanged design inputs accept completed local suggestion"):
		return
	workspace.suggest_design("plan")
	model.complete("新增验收条件")
	if not check(workspace.load_draft(workspace.design_key("plan")).body == "当前方向对应的策划\n\n新增验收条件", "suggestions append to existing authored draft without replacing its text"):
		return
	workspace.send_message("身份切换期间")
	var old_request: String = model.inputs.back().id
	session.identity_resetting.emit()
	session.scope = "actor-b-project"
	session.generation += 1
	session.identity_changed.emit()
	model.finished.emit(old_request, {"ok": true, "text": "wrong account", "model": model.configuration()})
	if not check(workspace.active_conversation.is_empty() and local.summaries([]).is_empty() and local.records.is_empty(), "identity transition cancels old request and isolates persisted conversations"):
		return
	session.role = "viewer"
	var count := model.inputs.size()
	workspace.send_message("viewer forbidden")
	if not check(model.inputs.size() == count, "viewer cannot start local inference through workspace controller"):
		return
	session.role = "admin"
	var blocker: String = OS.get_environment("TX_DRAFTS").path_join("storage-blocker")
	FileAccess.open(blocker, FileAccess.WRITE).store_string("ordinary file")
	workspace.storage_root = blocker.path_join("not-a-directory")
	workspace.send_message("failed durable storage")
	if not check(model.inputs.size() == count and workspace.active_conversation.is_empty() and not workspace.errors.get("chat", "").is_empty(), "failed durable storage does not start a model request or consume input"):
		return
	var report := {"ok": true, "checks": checks}
	FileAccess.open(OS.get_environment("TX_REPORT"), FileAccess.WRITE).store_string(JSON.stringify(report, "  "))
	print(JSON.stringify({"ok": true, "checks": checks.size()}))
	quit(0)
