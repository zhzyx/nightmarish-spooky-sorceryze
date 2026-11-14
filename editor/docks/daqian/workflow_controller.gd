@tool
extends Node

# Runtime and receipt ownership outlives any particular workspace View. No GUI
# object or View callback is retained here; the chat service is a domain port.
signal state_changed
signal receipt_changed
signal issue_invalidated(request_id: String)
signal routing_finished(binding: Dictionary, result: Dictionary, verified: bool)
signal work_changed(row: Dictionary)

var runtime: Object
var chat: Object
var root := ""
var actor := {}
var saved := {}
var board := {}
var other_board := {}
var fresh_progress := false
var progress_directory := ""
var offline := false
var routing_in_flight := {}
var routing_stages := {}
var execution_turns := {}
var starting_direct := {}
var checked_execution := {}
var chat_work := {}
var legacy_route_path := ""
var legacy_route_result := {}
var legacy_route_turns := []
var runs := {}
var worker_runs := {}
var stores := {}
var cache_path := ""
const HOST_RECEIPT_POLL_SECONDS := 1.0


func attach_to_root(tree_root: Node) -> void:
	if not is_inside_tree() and is_instance_valid(tree_root):
		tree_root.add_child(self)


func configure(context: Dictionary) -> void:
	root = str(context.get("root", ""))
	actor = context.get("actor", {})
	saved = context.get("saved", {})
	var identity := JSON.stringify([root, actor.get("repo_id"), actor.get("user_id")])
	# Reattaching a View can load an older disk snapshot. Receipt fields remain
	# owned by this Controller; unrelated presentation/draft fields stay intact.
	if stores.has(identity) and not is_same(stores[identity], saved):
		for key in ["routing", "routing_errors", "clarification_history", "execution_errors"]:
			if stores[identity].has(key):
				saved[key] = stores[identity][key]
	stores[identity] = saved
	cache_path = str(context.get("cache_path", ""))
	board = context.get("board", {})
	other_board = context.get("other_board", {})
	fresh_progress = context.get("fresh_progress", false)
	progress_directory = context.get("progress_directory", "")
	offline = context.get("offline", false)
	if not is_instance_valid(runtime) and Engine.is_editor_hint() and Engine.has_singleton("AIWorkflowRuntime"):
		runtime = Engine.get_singleton("AIWorkflowRuntime")


func attach_chat(service: Object) -> void:
	if chat == service:
		return
	for pair in [["daqian_execution_finished", _execution_finished], ["daqian_work_event", _chat_work_event]]:
		if is_instance_valid(chat) and chat.has_signal(pair[0]) and chat.is_connected(pair[0], pair[1]):
			chat.disconnect(pair[0], pair[1])
	chat = service
	for pair in [["daqian_execution_finished", _execution_finished], ["daqian_work_event", _chat_work_event]]:
		if is_instance_valid(chat) and chat.has_signal(pair[0]):
			chat.connect(pair[0], pair[1])


func _repo() -> String:
	return root


func _sync_workflow() -> void:
	state_changed.emit()


func _save() -> void:
	if not cache_path.is_empty() and not actor.is_empty():
		var temporary := cache_path + ".controller.tmp"
		var file := FileAccess.open(temporary, FileAccess.WRITE)
		if file:
			file.store_var(saved)
			file.close()
			if DirAccess.rename_absolute(temporary, cache_path) != OK:
				DirAccess.remove_absolute(temporary)
	receipt_changed.emit()


func _queue_save() -> void:
	_save()


func bind_conversation(binding: Dictionary, existing_only: bool) -> String:
	if not is_instance_valid(chat):
		return "推进对话尚未就绪。"
	return chat.open_daqian_chat(str(binding.get("url", "")), int(binding.get("number", 0)),
		str(binding.get("request", "")), "", false, {}, true, "", existing_only)


func _public_model(selection: Dictionary) -> Dictionary:
	var model := {}
	for key in ["backend", "id", "model", "provider", "connection_id", "revision", "source_revision", "reasoning_effort", "effort", "strength"]:
		if selection.has(key):
			model[key] = selection[key]
	return model


func begin_operation(binding: Dictionary, selection: Dictionary, operation: String, identity: String, input: Dictionary, recovering := false) -> Dictionary:
	if not is_instance_valid(runtime):
		return {"ok":false, "error":"公共 AI 运行服务尚未就绪，请重新加载已验证的编辑器。"}
	var result: Dictionary = runtime.begin_run({"workflow":"tianshu", "scope":JSON.stringify([root, actor.get("user_id"), binding.get("url")]),
		"request_id":identity, "initial_state":"reconciling" if recovering else "running", "model":_public_model(selection),
		"binding":{"issue_number":int(binding.get("number", 0)), "request_id":str(binding.get("request", "")),
			"source_revision":str(binding.get("source_sha256", binding.get("updated", binding.get("revision", "")))),
			"actor_id":str(actor.get("user_id", "")), "operation":operation}, "input":input})
	if not result.get("ok", false):
		return {"ok":false, "error":str(result.get("reason", "运行绑定失败"))}
	runs[identity] = result.snapshot
	return result


func query_run(identity: String) -> Dictionary:
	if not runs.has(identity) or not is_instance_valid(runtime):
		return {}
	return runtime.snapshot(runs[identity].run_id).get("snapshot", {})


func publish_operation(identity: String, kind: String, state: String, payload: Dictionary) -> Dictionary:
	var run := query_run(identity)
	if run.is_empty():
		return {}
	return runtime.publish({"run_id":run.run_id, "generation":run.generation, "expected_sequence":run.sequence,
		"event_id":identity + ":" + str(run.sequence), "kind":kind, "state":state, "payload":payload})


func prepare_execution(binding: Dictionary, selection: Dictionary, message: String) -> Dictionary:
	var token := Crypto.new().generate_random_bytes(16).hex_encode()
	var result := begin_operation(binding, selection, "execution", token, {"message_digest":message.sha256_text()})
	if not result.get("ok", false):
		return result
	execution_turns[token] = {"root":root, "actor":actor.duplicate(true), "key":_execution_key(binding), "binding":binding.duplicate(true)}
	return {"ok":true, "token":token}


func execute(binding: Dictionary, selection: Dictionary, message: String, started: bool, background: bool, retry_existing: bool) -> Dictionary:
	if not is_instance_valid(chat):
		return {"error":"推进对话尚未就绪。"}
	selection = selection.duplicate(true)
	var token := ""
	if not message.is_empty() and not selection.is_empty():
		var prepared := prepare_execution(binding, selection, message)
		if not prepared.get("ok", false):
			return prepared
		token = prepared.token
		selection.execution_receipt = {"token":token}
		if retry_existing:
			selection.retry_existing = true
	var error: String = chat.open_daqian_chat(binding.url, int(binding.number), binding.request, message, false, selection, true, "", started, background)
	if not error.is_empty():
		if not token.is_empty():
			_execution_finished({"token":token, "terminal_state":"failed"}, error, false)
		return {"error":error}
	saved.get_or_add("direct_started", {})[binding.url] = binding.request
	_save()
	state_changed.emit()
	return {"ok":true, "token":token}


func start_issue(binding: Dictionary, selection: Dictionary, args: PackedStringArray, configuration: Dictionary, cache_dir: String) -> Dictionary:
	var user := actor.duplicate(true)
	var source_root := root
	var key := _routing_key(binding)
	var start_key := _start_key(binding)
	if starting_direct.has(start_key):
		return {"error":"正在核对本工单开工回执，请等待原操作。"}
	var request := {"issue_number":int(binding.number), "request_id":binding.request, "expected_user":user.user_id,
		"expected_revision":binding.get("updated", binding.get("revision", ""))}
	var identity := Crypto.new().generate_random_bytes(16).hex_encode()
	var began := begin_operation(binding, selection, "issue-start", identity, {"request_digest":JSON.stringify(request).sha256_text()})
	if not began.get("ok", false):
		return began
	starting_direct[start_key] = true
	state_changed.emit()
	var result: Dictionary = await host_command(args, "--out", request, configuration, cache_dir)
	starting_direct.erase(start_key)
	var verified: bool = result.get("ok") == true and result.get("status") in ["status:in-progress", "status:in-review"]
	publish_operation(identity, "completed" if verified else "progress", "succeeded" if verified else "reconciling", {"verified":verified})
	if user != actor or source_root != root:
		return {"error":"工作区身份已改变，请回读原工单。", "environment_changed":true}
	if not verified:
		saved.get_or_add("start_errors", {})[key] = str(result.get("error", "未取得开始推进回执"))
		if result.get("refresh_routing") == true:
			saved.get_or_add("routing_errors", {})[key] = str(result.get("error", "判断回执待核对"))
			_discard_routing(binding)
	else:
		saved.get("start_errors", {}).erase(key)
		saved.get_or_add("direct_start_receipts", {})[binding.url] = binding.request
	_save()
	state_changed.emit()
	return result


func host_command(args: PackedStringArray, output_flag: String, request: Dictionary, configuration: Dictionary, cache_dir: String) -> Dictionary:
	if configuration.get("_environment_changed", false):
		return {"environment_changed":true,"error":"运行环境已改变，请重新核对工作区身份。"}
	var python: String = str(configuration.get("workflow_python", ""))
	if python.is_empty():
		return {"error":"工作流 Python 路径未配置或无效"}
	args = args.duplicate()
	if args.size() > 1 and args[1] == "issue-direct":
		request = request.duplicate(true)
		request.node_runtime = str(configuration.get("node", ""))
	var stem := cache_dir.path_join("daqian-" + Crypto.new().generate_random_bytes(12).hex_encode())
	var result_path := stem + ".result"
	var req_path := stem + ".request"
	args.append_array([output_flag, result_path])
	if not request.is_empty():
		var file := FileAccess.open(req_path, FileAccess.WRITE)
		if not file:
			return {"error":"无法保存本次提交请求"}
		file.store_string(JSON.stringify(request))
		file.close()
		args.append_array(["--request", req_path])
	var pid := OS.create_process(python, args)
	return await _host_result(pid, req_path, result_path)


func judge(binding: Dictionary, selection: Dictionary, answer := "", retry := false, expected_questions := []) -> Dictionary:
	var key := _routing_key(binding)
	if routing_in_flight.has(key) or binding.get("closed", false) or binding.get("status") != "planned":
		return {"ok":false, "error":"判断已在运行或工单状态已改变。"}
	var url: String = binding.url
	var user := actor.duplicate(true)
	var source_root := root
	var request := {"issue_number":int(binding.number), "request_id":binding.request, "expected_user":user.user_id,
		"expected_revision":binding.get("updated", binding.get("revision", "")), "retry_authorized":retry}
	if not answer.is_empty():
		request.answer = answer
		request.expected_questions = expected_questions.duplicate()
	var identity := Crypto.new().generate_random_bytes(16).hex_encode()
	var started := begin_operation(binding, selection, "routing", identity, {"request_digest":JSON.stringify(request).sha256_text()})
	if not started.get("ok", false):
		return started
	routing_in_flight[key] = true
	saved.get("routing_errors", {}).erase(key)
	state_changed.emit()
	var process: Dictionary = chat.launch_daqian_routing(request, selection) if is_instance_valid(chat) else {"error":"推进对话尚未就绪。"}
	var launched := process.has("pid")
	var result := process
	if launched:
		routing_in_flight[key] = process.pid
		result = await _host_result(process.pid, process.input, process.output)
	routing_in_flight.erase(key)
	routing_stages.erase(key)
	legacy_route_path = ""
	var verified: bool = (result.get("ok") == true and result.get("url") == url and result.get("number") == binding.number
		and result.get("request_id") == binding.request and result.get("revision") == request.expected_revision
		and result.get("route") in ["sinan", "yanshi"] and result.get("reason") is String and result.get("ready") is bool
		and result.get("scope") is Array and result.get("acceptance") is Array and result.get("questions") is Array)
	# An unreadable/missing receipt cannot prove failure of a remote side effect.
	publish_operation(identity, "completed" if verified else "progress", "succeeded" if verified else "reconciling", {"verified":verified})
	if user != actor or source_root != root:
		return {"ok":false, "environment_changed":true, "error":"工作区身份已改变，请回读原工单回执。"}
	if launched and not answer.is_empty() and result.get("ok") != true:
		_discard_routing(binding)
	if verified:
		if not saved.has("routing"):
			saved.routing = {}
		var history := _confirmed_clarifications(binding, result).duplicate(true)
		# Older helpers acknowledge a submitted answer without returning the whole transcript.
		if not result.has("clarification_history") and result.route == "yanshi" and request.has("answer"):
			var turn := {"questions":request.expected_questions, "answer":request.answer}
			if turn not in history:
				history.append(turn)
		if not history.is_empty():
			saved.get_or_add("clarification_history", {})[key] = history
		elif result.has("clarification_history"):
			saved.get("clarification_history", {}).erase(key)
		result.clarification_history = history
		saved.routing[url] = result
		for item in board.get("issues", []):
			if item.url == url and item.request == binding.request and item.updated == request.expected_revision:
				item.routing_receipt = result
		_save()
	else:
		saved.get_or_add("routing_errors", {})[key] = str(result.get("error", "判断回执待核对"))
		_save()

	state_changed.emit()
	routing_finished.emit(binding, result, verified)
	return result


func _routing_key(binding: Dictionary) -> String:
	return JSON.stringify([_repo(), actor.get("user_id"), binding.get("url"), binding.get("request"),
		binding.get("updated", binding.get("revision", ""))])


func _start_key(binding: Dictionary) -> String:
	return JSON.stringify([_repo(), actor.get("user_id"), binding.url, binding.request])



func _execution_key(binding: Dictionary) -> String:
	return JSON.stringify([_repo(), actor.get("user_id"), binding.get("url"), int(binding.get("number", 0)),
		binding.get("request"), binding.get("source_sha256", binding.get("updated", binding.get("revision", "")))])



func _read_routing_stage(binding: Dictionary) -> void:
	var key := _routing_key(binding)
	var pid = routing_in_flight.get(key)
	if typeof(pid) != TYPE_INT or not OS.is_process_running(pid) or not fresh_progress or progress_directory.is_empty():
		return
	var request := str(binding.get("request", ""))
	var suffix := request.trim_prefix("daqian-direct-")
	if request == suffix or suffix.length() != 20 or not suffix.is_valid_hex_number(false):
		return
	var expected := {"actor":actor.user_id, "number":int(binding.number), "request_id":request, "url":binding.url,
		"revision":binding.get("updated", binding.get("revision", ""))}
	var folder := progress_directory.path_join("daqian-direct").path_join(request)
	var files := PackedStringArray()
	if binding.has("source_sha256"):
		expected.source_sha256 = binding.source_sha256
		files.append("route-" + JSON.stringify(expected).sha256_text() + ".json")
	else:
		# Before the first board row, probe a small request folder only. A verified
		# source hash on the next board snapshot gives us the exact path.
		var directory := DirAccess.open(folder)
		if not directory or directory.list_dir_begin() != OK:
			return
		for i in 12:
			var next := directory.get_next()
			if next.is_empty():
				break
			files.append(next)
		if not directory.get_next().is_empty():
			return
	for name in files:
		if not name.begins_with("route-") or not name.ends_with(".json") or name.length() != 75:
			continue
		var path := folder.path_join(name)
		var file := FileAccess.open(path, FileAccess.READ)
		if not file:
			continue
		# Real journals are small; large histories can wait for normal verification.
		var length := file.get_length()
		if length <= 0 or length > 128 * 1024:
			continue
		var state = JSON.parse_string(file.get_buffer(length).get_string_from_utf8())
		if not state is Dictionary or not state.get("binding") is Dictionary or not state.get("calls") is Dictionary:
			continue
		var source: Dictionary = state.binding.duplicate()
		if source.get("number") != expected.number:
			continue
		source.number = expected.number # JSON parses numbers as floats; the journal hash uses integers.
		if name != "route-" + JSON.stringify(source).sha256_text() + ".json":
			continue
		if not expected.has("source_sha256"):
			source.erase("source_sha256")
		if source != expected:
			continue
		var stage := ""
		var matched_pid := false
		for call in state.calls.values():
			if not call is Dictionary or not call.get("attempts") is Array or call.attempts.is_empty():
				continue
			var attempt = call.attempts.back()
			if attempt is Dictionary and attempt.get("pid") == pid and attempt.get("agent") in ["sinan", "yanshi"]:
				matched_pid = true
				if not attempt.has("outcome"):
					stage = attempt.agent
					break
		if matched_pid:
			if routing_stages.get(key) != stage:
				routing_stages[key] = stage
				_sync_workflow()
			return


func _routing_stage(item: Dictionary) -> String:
	var key := _routing_key(item)
	var pid = routing_in_flight.get(key)
	if typeof(pid) != TYPE_INT or not fresh_progress or not OS.is_process_running(pid):
		return ""
	if routing_stages.has(key):
		return routing_stages[key]
	var attempt: Dictionary = item.get("judgment_attempt", {})
	if attempt.get("pid") == pid and attempt.get("agent") in ["sinan", "yanshi"]:
		return attempt.agent
	return ""


func _routing_receipt(binding: Dictionary) -> Dictionary:
	var verified: Dictionary = binding.get("routing_receipt", {})
	if binding.has("routing_receipt"):
		return verified
	var result: Dictionary = saved.get("routing", {}).get(binding.get("url", ""), {})
	var revision: String = binding.get("updated", binding.get("revision", ""))
	if result.get("revision", "") != revision or result.get("request_id", "") != binding.get("request", ""):
		return {}
	return result



func _legacy_clarifications(binding: Dictionary, decision: Dictionary) -> Array:
	var stored: Array = saved.get("clarification_history", {}).get(_routing_key(binding), [])
	if decision.get("route") != "yanshi" or not fresh_progress or progress_directory.is_empty() or not binding.has("source_sha256"):
		return stored
	var request := str(binding.get("request", ""))
	var suffix := request.trim_prefix("daqian-direct-")
	if request == suffix or suffix.length() != 20 or not suffix.is_valid_hex_number(false):
		return stored
	var expected := {"actor":actor.user_id, "number":int(binding.number), "request_id":request, "url":binding.url,
		"revision":decision.revision, "source_sha256":binding.source_sha256}
	var final_result := {}
	for field in ["route", "reason", "scope", "acceptance", "questions", "ready"]:
		final_result[field] = decision.get(field)
	var planned: bool = binding.get("status") == "planned"
	var name := ("route-" + JSON.stringify(expected).sha256_text() + ".json") if planned else "start.json"
	var path := progress_directory.path_join("daqian-direct").path_join(request).path_join(name)
	if legacy_route_path == path and legacy_route_result == final_result:
		return legacy_route_turns
	var file := FileAccess.open(path, FileAccess.READ)
	if not file or file.get_length() > 8 * 1024 * 1024:
		return stored
	var state = JSON.parse_string(file.get_buffer(file.get_length()).get_string_from_utf8())
	if not state is Dictionary or not state.get("binding") is Dictionary or state.get("result") != final_result:
		return stored
	var source: Dictionary = state.binding.duplicate()
	if source.get("number") != expected.number:
		return stored
	source.number = expected.number
	if source != expected:
		return stored
	var turns = state.get("answers" if planned else "clarifications")
	if not turns is Array:
		return stored
	legacy_route_path = path
	legacy_route_result = final_result
	legacy_route_turns = turns
	return turns


func _confirmed_clarifications(binding: Dictionary, decision: Dictionary) -> Array:
	var turns = decision.get("clarification_history")
	if turns == null:
		turns = _legacy_clarifications(binding, decision)
	if not turns is Array or turns.size() > 32:
		return []
	for turn in turns:
		if not turn is Dictionary or not turn.get("questions") is Array or turn.questions.is_empty() or not turn.get("answer") is String:
			return []
		if not turn.questions.all(func(question): return question is String):
			return []
	return turns


func _discard_routing(binding: Dictionary) -> void:
	var key := _routing_key(binding)
	var cached: Dictionary = saved.get("routing", {}).get(binding.url, {})
	if cached.get("revision") == binding.get("updated", binding.get("revision")) and cached.get("request_id") == binding.request:
		saved.routing.erase(binding.url)
	for row in board.get("issues", []):
		if _routing_key(row) == key:
			row.routing_receipt = {}


func _host_result(pid: int, req_path: String, result_path: String) -> Dictionary:
	if pid >= 0:
		while not FileAccess.file_exists(result_path) and OS.is_process_running(pid):
			await get_tree().create_timer(HOST_RECEIPT_POLL_SECONDS).timeout
	if FileAccess.file_exists(req_path):
		DirAccess.remove_absolute(req_path)
	if FileAccess.file_exists(result_path):
		var result = JSON.parse_string(FileAccess.get_file_as_string(result_path))
		DirAccess.remove_absolute(result_path)
		if result is Dictionary:
			return result
	return {"error":"没有收到宿主回执，请回读原工单后再操作"}


func restore_execution_failure(item: Dictionary, tenant: String) -> void:
	if not fresh_progress or offline or not is_instance_valid(chat) or not chat.has_method("get_legacy_candidate_failure"):
		return
	var key := _execution_key(item)
	var request := str(item.get("request", ""))
	var suffix := request.trim_prefix("daqian-direct-")
	if checked_execution.has(key) or item.get("status") not in ["in-progress", "in-review"] or request == suffix or suffix.length() != 20 or not suffix.is_valid_hex_number(false) or not item.get("source_sha256"):
		return
	checked_execution[key] = true
	if not tenant.is_valid_filename() or tenant in [".",".."]:
		return
	var folder := _repo().path_join("gonggong-diting-data/events").path_join(tenant).path_join(request)
	var owner := await _legacy_failed_owner(folder, item, request)
	if owner.is_empty() or not fresh_progress or offline or _execution_key(item) != key:
		return
	var error: String = chat.get_legacy_candidate_failure(owner, _repo(), int(item.number))
	if not error.is_empty():
		saved.get_or_add("execution_errors", {}).get_or_add(key, error)
		_sync_workflow()
		_queue_save()



func _legacy_failed_owner(folder: String, item: Dictionary, request: String) -> String:
	var directory := DirAccess.open(folder)
	if not directory or directory.list_dir_begin() != OK:
		return ""
	# Enumerate first. An omitted new receipt could supersede an old failure.
	var names := PackedStringArray()
	for i in 64:
		var name := directory.get_next()
		if name.is_empty():
			break
		if name.begins_with("godot-event-") and name.ends_with(".json"):
			names.append(name)
	if not directory.get_next().is_empty():
		return ""
	var latest := ""
	var owner := ""
	var total := 0
	var slice := Time.get_ticks_usec()
	var principal := actor.duplicate()
	var root := _repo()
	for name in names:
		if Time.get_ticks_usec() - slice > 1500:
			await get_tree().process_frame
			if principal != actor or root != _repo() or not fresh_progress or offline:
				return ""
			slice = Time.get_ticks_usec()
		var file := FileAccess.open(folder.path_join(name), FileAccess.READ)
		if not file:
			return ""
		var length := file.get_length()
		total += length
		if length <= 0 or length > 32 * 1024 or total > 128 * 1024:
			return ""
		var event = JSON.parse_string(file.get_buffer(length).get_string_from_utf8())
		if not event is Dictionary:
			return ""
		if event.get("kind") not in ["request", "request_end"] or event.get("request_id") != request or event.get("source_ref") != item.url:
			continue
		var payload = event.get("payload")
		if not payload is Dictionary or not payload.get("binding") is Dictionary:
			return ""
		var binding: Dictionary = payload.binding
		if binding.get("actor") != actor.user_id or binding.get("source_ref") != item.url or binding.get("request_ref") != request:
			continue
		var stamp := str(event.get("occurred_at", ""))
		if stamp.is_empty():
			return ""
		if stamp == latest:
			owner = "" # Receipts without a strict order cannot establish a terminal failure.
		elif stamp > latest:
			latest = stamp
			var authority := str(binding.get("authority_ref", ""))
			owner = authority.trim_prefix("godot-editor:user-chat:") if authority.begins_with("godot-editor:user-chat:") and event.kind == "request_end" and payload.get("status") == "failed" and binding.get("source_sha256") == item.source_sha256 else ""
	if owner.length() != 32 or not owner.is_valid_hex_number(false):
		return ""
	return owner


func _execution_finished(receipt: Dictionary, error: String, past_preflight: bool) -> void:
	var token: String = receipt.get("token", "")
	var turn: Dictionary = execution_turns.get(token, {})
	if turn.is_empty():
		return
	execution_turns.erase(token)
	var terminal := str(receipt.get("terminal_state", ""))
	var kind := "completed" if terminal == "succeeded" else (terminal if terminal in ["failed", "cancelled"] else "progress")
	publish_operation(token, kind, terminal if kind != "progress" else "reconciling", {"past_preflight":past_preflight})
	if turn.root != _repo() or turn.actor != actor:
		return
	if not error.is_empty():
		saved.get_or_add("execution_errors", {})[turn.key] = error if past_preflight else ("预检失败 · " + error)
	elif past_preflight:
		saved.get("execution_errors", {}).erase(turn.key)
	_sync_workflow()
	_queue_save()


func _chat_work_event(root: String, binding: Dictionary, worker: String, kind: String, stage: String, state: String) -> void:
	var url: String = binding.get("source_ref", "")
	if root != _repo() or actor.is_empty() or binding.get("actor") != actor.user_id:
		return
	var active: Dictionary = chat_work.get(url, {})
	var version: String = binding.get("source_sha256", "")
	if version.is_empty():
		return
	# A terminal callback may arrive after switching between personal and project boards.
	var candidates: Array = board.get("issues", [])
	if kind == "request_end" and active.get(worker, {}).get("version") == version:
		candidates = candidates + other_board.get("issues", [])
	for row in candidates:
		if row.url != url or row.request != binding.get("request_ref"):
			continue
		if kind == "request_end":
			if row.get("source_sha256") == version:
				var key := _execution_key(row)
				if state == "failed":
					saved.get_or_add("execution_errors", {}).get_or_add(key, "关联推进对话报告本轮失败")
					_queue_save()
				elif state == "completed":
					saved.get("execution_errors", {}).erase(key)
			if active.get(worker, {}).get("version") == version:
				active.erase(worker)
		elif row.get("source_sha256", "") == version and (kind == "request" or active.get(worker, {}).get("version") == version):
			active[worker] = {"version":version, "step":stage if state in ["running", "waiting"] else "chat"}
		chat_work[url] = active
		var identity := JSON.stringify([root, actor.user_id, url, worker, version])
		if not worker_runs.has(identity):
			var begun := begin_operation(row, {}, "worker", identity, {"worker":worker}, kind != "request")
			if begun.get("ok", false):
				worker_runs[identity] = true
		if worker_runs.has(identity):
			var terminal := kind == "request_end" and state in ["failed", "completed", "cancelled"]
			var run_kind := ("completed" if state == "completed" else state) if terminal else "progress"
			var run_state := ("succeeded" if state == "completed" else state) if terminal else ("waiting_confirmation" if state == "waiting" else "running")
			publish_operation(identity, run_kind, run_state, {"stage":stage})
		work_changed.emit(row)
		if kind == "request_end":
			issue_invalidated.emit(str(row.request))
		return
