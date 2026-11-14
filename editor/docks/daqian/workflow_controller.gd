@tool
extends RefCounted

signal event_received(event: Dictionary)
signal routing_changed

var direct_in_flight: Dictionary = {}
var starting_direct: Dictionary = {}
var saved: Dictionary = {}
var routing_in_flight: Dictionary = {}
var routing_stages: Dictionary = {}
var execution_turns: Dictionary = {}
var chat_work: Dictionary = {}
var legacy_route_path := ""
var legacy_route_result: Dictionary = {}
var legacy_route_turns: Array = []

var runtime: Object
var context_reader: Callable
var session_opener: Callable
var routing_launcher: Callable
var access_refresher: Callable
var binding_reader: Callable
var catalog_reader: Callable
var route_runs: Dictionary = {}
var execution_runs: Dictionary = {}
var worker_runs: Dictionary = {}
var preview_runs: Dictionary = {}
var scope_generation := 0


func context() -> Dictionary:
	return context_reader.call() if context_reader.is_valid() else {}


func routing_key(binding: Dictionary) -> String:
	var current := context()
	return JSON.stringify([current.get("root", ""), current.get("actor", {}).get("user_id"), binding.get("url"), binding.get("request"),
		binding.get("updated", binding.get("revision", ""))])


func start_key(binding: Dictionary) -> String:
	var current := context()
	return JSON.stringify([current.get("root", ""), current.get("actor", {}).get("user_id"), binding.url, binding.request])


func execution_key(binding: Dictionary) -> String:
	var current := context()
	return JSON.stringify([current.get("root", ""), current.get("actor", {}).get("user_id"), binding.get("url"), int(binding.get("number", 0)),
		binding.get("request"), binding.get("source_sha256", binding.get("updated", binding.get("revision", "")))])


func _begin_run(workflow: String, request_id: String, model: Dictionary, binding: Dictionary) -> Dictionary:
	if not is_instance_valid(runtime) and ClassDB.class_exists("AIWorkflowRuntime"):
		runtime = ClassDB.instantiate("AIWorkflowRuntime")
	if not is_instance_valid(runtime):
		return {}
	var current := context()
	var actor: Dictionary = current.get("actor", {}).duplicate(true)
	var root: String = current.get("root", "")
	var scope := JSON.stringify([current.get("root", ""), current.get("actor", {}).get("user_id"), binding.get("url", "")])
	var generation := scope_generation
	var event: Dictionary = runtime.begin_run(workflow, scope, request_id, model, binding)
	if event.is_empty() or event.get("state") != "running":
		return {}
	event_received.emit(event.duplicate(true))
	var after := context()
	if generation != scope_generation or after.get("root", "") != root or after.get("actor", {}) != actor:
		runtime.cancel(event.run_id)
		return {}
	var latest: Dictionary = runtime.snapshot(event.run_id)
	return latest if latest.get("state") == "running" else {}


func _publish(run: Dictionary, kind: String, payload: Dictionary = {}, state := "") -> Dictionary:
	if run.is_empty() or not is_instance_valid(runtime):
		return {}
	var event: Dictionary = runtime.publish(run.run_id, run.generation, kind, payload, state)
	if not event.is_empty():
		event_received.emit(event.duplicate(true))
	return event


func bind_conversation(binding: Dictionary, current_source := "") -> String:
	if not session_opener.is_valid():
		return "推进对话尚未就绪。"
	return session_opener.call(str(binding.get("url", current_source)), int(binding.get("number", 0)),
		str(binding.get("request", "")), "", false, {}, true, "", has_started_worker(binding, current_source), false)


func has_started_worker(binding: Dictionary, current_source := "") -> bool:
	var url: String = binding.get("url", current_source)
	var request: String = binding.get("request", "")
	if request.is_empty():
		return false
	var started = saved.get("direct_started", {}).get(url)
	if started is bool and started:
		for original in saved.get("linked", {}).values():
			if original.get("url") == url and original.get("request") == request and original.get("number") == binding.get("number"):
				return true
	return started is String and started == request


func open_conversation(source: String, number: int, request: String, message: String, preview: bool, selection: Dictionary,
		embedded: bool, receipt := "", existing := false, background := false) -> String:
	if not session_opener.is_valid():
		return "推进对话尚未就绪。"
	selection = selection.duplicate(true)
	if message.is_empty():
		return session_opener.call(source, number, request, message, preview, selection, embedded, receipt, existing, background)
	var binding := {"url":source, "number":number, "request":request}
	if not preview:
		return submit_execution(binding, message, selection, existing, background, false, false, embedded)
	if not receipt.is_empty() and preview_runs.has(receipt):
		return "该预览请求仍在进行，请等待原请求的回执。"
	var key := receipt if not receipt.is_empty() else "tianshu_preview_" + Crypto.new().generate_random_bytes(16).hex_encode()
	var input := binding.duplicate(true)
	input.message = message
	var run := _begin_run("tianshu.preview", Crypto.new().generate_random_bytes(16).hex_encode(), selection, input)
	if run.is_empty():
		return "AI 工作流运行时尚未就绪。"
	var current := context()
	preview_runs[key] = {"run":run, "root":current.get("root", ""), "actor":current.get("actor", {}).duplicate(),
		"source":source if receipt.is_empty() else receipt}
	var error: String = session_opener.call(source, number, request, message, preview, selection, embedded, key, existing, background)
	if not error.is_empty():
		finish_preview(key, "", error)
	return error


func finish_preview(source: String, text: String, error := "") -> Dictionary:
	var pending: Dictionary = preview_runs.get(source, {})
	if pending.is_empty():
		return {}
	preview_runs.erase(source)
	var current := context()
	if pending.root != current.get("root", "") or pending.actor != current.get("actor", {}):
		_publish(pending.run, "cancelled", {"reason":"scope_changed"}, "cancelled")
		return {}
	var event := _publish(pending.run, "completed" if error.is_empty() else "failed", {"text":text, "error":error}, "succeeded" if error.is_empty() else "failed")
	return {} if event.is_empty() else {"source":pending.source}


func submit_execution(binding: Dictionary, message: String, selection: Dictionary, existing: bool, background: bool, retry: bool, record_started := true, embedded := true) -> String:
	if not session_opener.is_valid():
		return "无法取得共工 AI 对话入口"
	binding = binding.duplicate(true)
	var token := ""
	var run := {}
	var current := context()
	selection = selection.duplicate(true)
	if not message.is_empty() and not selection.is_empty():
		token = Crypto.new().generate_random_bytes(16).hex_encode()
		var input := binding.duplicate(true)
		input.message = message
		run = _begin_run("tianshu.execution", token, selection, input)
		if run.is_empty():
			return "AI 工作流运行时尚未就绪。"
		execution_runs[token] = run
		execution_turns[token] = {"root":current.get("root", ""), "actor":current.get("actor", {}).duplicate(), "key":execution_key(binding)}
		selection.execution_receipt = {"token":token}
		if retry:
			selection.retry_existing = true
	var error: String = session_opener.call(str(binding.url), int(binding.number), str(binding.request), message, false, selection, embedded, "", existing, background)
	if not error.is_empty():
		finish_execution({"token":token}, error, false)
		return error
	if record_started:
		saved.get_or_add("direct_started", {})[binding.url] = binding.request
	return ""


func finish_execution(receipt: Dictionary, error: String, past_preflight: bool) -> bool:
	var token: String = receipt.get("token", "")
	var turn: Dictionary = execution_turns.get(token, {})
	if turn.is_empty():
		return false
	execution_turns.erase(token)
	var run: Dictionary = execution_runs.get(token, {})
	execution_runs.erase(token)
	var current := context()
	if turn.root != current.get("root", "") or turn.actor != current.get("actor", {}):
		_publish(run, "cancelled", {"reason":"scope_changed"}, "cancelled")
		return false
	if not error.is_empty():
		saved.get_or_add("execution_errors", {})[turn.key] = error if past_preflight else ("预检失败 · " + error)
	elif past_preflight:
		saved.get("execution_errors", {}).erase(turn.key)
	_publish(run, "failed" if not error.is_empty() else "completed", {"error":error, "past_preflight":past_preflight}, "failed" if not error.is_empty() else "succeeded")
	return true


func routing_receipt(binding: Dictionary) -> Dictionary:
	var verified: Dictionary = binding.get("routing_receipt", {})
	if binding.has("routing_receipt"):
		return verified
	var result: Dictionary = saved.get("routing", {}).get(binding.get("url", ""), {})
	var revision: String = binding.get("updated", binding.get("revision", ""))
	if result.get("revision", "") != revision or result.get("request_id", "") != binding.get("request", ""):
		return {}
	return result


func discard_routing(binding: Dictionary) -> void:
	var key := routing_key(binding)
	var cached: Dictionary = saved.get("routing", {}).get(binding.url, {})
	if cached.get("revision") == binding.get("updated", binding.get("revision")) and cached.get("request_id") == binding.request:
		saved.routing.erase(binding.url)
	for row in context().get("board", {}).get("issues", []):
		if routing_key(row) == key:
			row.routing_receipt = {}


func judge_requirement(binding: Dictionary, answer := "", retry := false, expected_questions: Array = []) -> Dictionary:
	binding = binding.duplicate(true)
	var key := routing_key(binding)
	if routing_in_flight.has(key) or binding.get("closed", false) or binding.status != "planned":
		return {}
	var initial := context()
	var generation := scope_generation
	var user: Dictionary = initial.get("actor", {}).duplicate()
	var root: String = initial.get("root", "")
	var request := {"issue_number":int(binding.number), "request_id":binding.request, "expected_user":user.get("user_id", ""),
		"expected_revision":binding.get("updated", binding.get("revision", "")), "retry_authorized":retry}
	if not answer.is_empty():
		request.answer = answer
		request.expected_questions = expected_questions.duplicate()
	routing_in_flight[key] = true
	saved.get("routing_errors", {}).erase(key)
	routing_changed.emit()
	var result := {"error":"请在工单内打开「推进模型」并配置连接，然后重试判断。"}
	var launched := false
	var run := {}
	if access_refresher.is_valid() and await access_refresher.call():
		var latest := context()
		var live: Dictionary = binding_reader.call() if binding_reader.is_valid() else {}
		if generation == scope_generation and root == latest.get("root", "") and user == latest.get("actor", {}):
			if live.get("number") != binding.number or routing_key(live) != key:
				result.error = "回到此工单后，可继续需求判断。"
			elif not answer.is_empty() and routing_receipt(live).get("questions", []) != expected_questions:
				result.error = "待答复问题已改变，请核对当前工单。"
			else:
				var error := bind_conversation(binding)
				if not error.is_empty():
					result.error = error
				elif catalog_reader.is_valid() and routing_launcher.is_valid():
					var catalog: Dictionary = catalog_reader.call()
					var selection: Dictionary = saved.get("execution_models", {}).get(binding.url, {"backend":catalog.backend, "id":catalog.current}).duplicate(true)
					if needs_model(catalog, selection):
						result = {"error":"请选择此工单的推进模型。", "needs_model":true}
					else:
						var input := binding.duplicate(true)
						input.routing_request = request
						run = _begin_run("tianshu.routing", Crypto.new().generate_random_bytes(16).hex_encode(), selection, input)
						if run.is_empty():
							result.error = "AI 工作流运行时尚未就绪。"
						else:
							route_runs[key] = run
							var process: Dictionary = routing_launcher.call(request, selection)
							if process.has("pid"):
								launched = true
								routing_in_flight[key] = process.pid
							result = await host_result(process.pid, process.input, process.output) if process.has("pid") else process
	if generation != scope_generation:
		return {}
	routing_in_flight.erase(key)
	routing_stages.erase(key)
	route_runs.erase(key)
	routing_changed.emit()
	legacy_route_path = ""
	var final_context := context()
	if user != final_context.get("actor", {}) or root != final_context.get("root", ""):
		_publish(run, "cancelled", {"reason":"scope_changed"}, "cancelled")
		return {}
	if launched and not answer.is_empty() and result.get("ok") != true:
		discard_routing(binding)
	if not answer.is_empty() and result.get("refresh_routing") == true:
		_publish(run, "failed", result, "failed")
		return await judge_requirement(binding)
	var verified := accept_routing_result(binding, request, result)
	_publish(run, "completed" if verified else "failed", result, "succeeded" if verified else "failed")
	return {"binding":binding, "result":result, "verified":verified, "needs_model":result.get("needs_model", false)}


func needs_model(catalog: Dictionary, selection: Dictionary) -> bool:
	return selection.get("backend") != catalog.backend or (catalog.backend in [0, 3] and str(selection.get("id", "")).strip_edges().is_empty())


func accept_routing_result(binding: Dictionary, request: Dictionary, result: Dictionary) -> bool:
	var verified: bool = (result.get("ok") == true and result.get("url") == binding.url and result.get("number") == binding.number
		and result.get("request_id") == binding.request and result.get("revision") == request.expected_revision
		and result.get("route") in ["sinan", "yanshi"] and result.get("reason") is String and result.get("ready") is bool
		and result.get("scope") is Array and result.get("acceptance") is Array and result.get("questions") is Array)
	if not verified:
		saved.get_or_add("routing_errors", {})[routing_key(binding)] = str(result.get("error", "判断回执待核对"))
		return false
	var key := routing_key(binding)
	var history := confirmed_clarifications(binding, result).duplicate(true)
	if not result.has("clarification_history") and result.route == "yanshi" and request.has("answer"):
		var turn := {"questions":request.expected_questions, "answer":request.answer}
		if turn not in history:
			history.append(turn)
	if not history.is_empty():
		saved.get_or_add("clarification_history", {})[key] = history
	elif result.has("clarification_history"):
		saved.get("clarification_history", {}).erase(key)
	result.clarification_history = history
	saved.get_or_add("routing", {})[binding.url] = result
	for item in context().get("board", {}).get("issues", []):
		if item.url == binding.url and item.request == binding.request and item.updated == request.expected_revision:
			item.routing_receipt = result
	return true


func host_result(pid: int, req_path: String, result_path: String) -> Dictionary:
	if pid >= 0:
		while not FileAccess.file_exists(result_path) and OS.is_process_running(pid):
			await Engine.get_main_loop().create_timer(1.0).timeout
	if FileAccess.file_exists(req_path):
		DirAccess.remove_absolute(req_path)
	if FileAccess.file_exists(result_path):
		var result = JSON.parse_string(FileAccess.get_file_as_string(result_path))
		DirAccess.remove_absolute(result_path)
		if result is Dictionary:
			return result
	return {"error":"没有收到宿主回执，请回读原工单后再操作"}


func reset_runtime() -> void:
	scope_generation += 1
	for pending in preview_runs.values():
		_publish(pending.run, "cancelled", {"reason":"scope_changed"}, "cancelled")
	preview_runs.clear()
	for group in [route_runs, execution_runs, worker_runs]:
		for run in group.values():
			_publish(run, "cancelled", {"reason":"scope_changed"}, "cancelled")
		group.clear()
	routing_in_flight.clear()
	routing_stages.clear()
	execution_turns.clear()
	chat_work.clear()


func consume_work_event(root: String, binding: Dictionary, worker: String, kind: String, stage: String, state: String) -> Dictionary:
	var current := context()
	var actor: Dictionary = current.get("actor", {})
	if root != current.get("root", "") or actor.is_empty() or binding.get("actor") != actor.user_id:
		return {}
	var url: String = binding.get("source_ref", "")
	var active: Dictionary = chat_work.get(url, {})
	var version: String = binding.get("source_sha256", "")
	if version.is_empty():
		return {}
	var candidates: Array = current.get("board", {}).get("issues", [])
	if kind == "request_end" and active.get(worker, {}).get("version") == version:
		candidates = candidates + current.get("other_board", {}).get("issues", [])
	for row in candidates:
		if row.url != url or row.request != binding.get("request_ref"):
			continue
		var changed := false
		if kind == "request_end":
			if row.get("source_sha256") == version:
				var key := execution_key(row)
				if state == "failed":
					saved.get_or_add("execution_errors", {}).get_or_add(key, "关联推进对话报告本轮失败")
					changed = true
				elif state == "completed":
					saved.get("execution_errors", {}).erase(key)
			if active.get(worker, {}).get("version") == version:
				active.erase(worker)
		elif row.get("source_sha256", "") == version and (kind == "request" or active.get(worker, {}).get("version") == version):
			active[worker] = {"version":version, "step":stage if state in ["running", "waiting"] else "chat"}
		else:
			return {}
		chat_work[url] = active
		publish_work_event(binding, worker, kind, stage, state)
		return {"row":row, "save":changed, "terminal":kind == "request_end"}
	return {}


func publish_work_event(binding: Dictionary, worker: String, kind: String, stage: String, state: String) -> void:
	var key := JSON.stringify([binding.get("source_ref"), binding.get("request_ref"), binding.get("source_sha256"), worker])
	var run: Dictionary = worker_runs.get(key, {})
	if kind == "request":
		run = _begin_run("tianshu.worker", Crypto.new().generate_random_bytes(16).hex_encode(), {}, binding)
		if run.is_empty():
			return
		worker_runs[key] = run
	if run.is_empty():
		return
	var payload := {"worker":worker, "phase":stage, "status":state}
	if kind == "request_end":
		var terminal := "cancelled" if state == "cancelled" else ("completed" if state == "completed" else "failed")
		_publish(run, terminal, payload, "succeeded" if terminal == "completed" else terminal)
		worker_runs.erase(key)
	else:
		_publish(run, "progress", payload, "waiting_confirmation" if state == "waiting" else "running")


func read_routing_stage(binding: Dictionary) -> void:
	var current := context()
	var actor: Dictionary = current.get("actor", {})
	var fresh_progress: bool = current.get("fresh_progress", false)
	var progress_directory: String = current.get("progress_directory", "")
	var key := routing_key(binding)
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
				_publish(route_runs.get(key, {}), "progress", {"stage":stage})
			return


func routing_stage(item: Dictionary) -> String:
	var current := context()
	var fresh_progress: bool = current.get("fresh_progress", false)
	var key := routing_key(item)
	var pid = routing_in_flight.get(key)
	if typeof(pid) != TYPE_INT or not fresh_progress or not OS.is_process_running(pid):
		return ""
	if routing_stages.has(key):
		return routing_stages[key]
	var attempt: Dictionary = item.get("judgment_attempt", {})
	if attempt.get("pid") == pid and attempt.get("agent") in ["sinan", "yanshi"]:
		return attempt.agent
	return ""


func legacy_clarifications(binding: Dictionary, decision: Dictionary) -> Array:
	var current := context()
	var actor: Dictionary = current.get("actor", {})
	var fresh_progress: bool = current.get("fresh_progress", false)
	var progress_directory: String = current.get("progress_directory", "")
	var stored: Array = saved.get("clarification_history", {}).get(routing_key(binding), [])
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


func confirmed_clarifications(binding: Dictionary, decision: Dictionary) -> Array:
	var turns = decision.get("clarification_history")
	if turns == null:
		turns = legacy_clarifications(binding, decision)
	if not turns is Array or turns.size() > 32:
		return []
	for turn in turns:
		if not turn is Dictionary or not turn.get("questions") is Array or turn.questions.is_empty() or not turn.get("answer") is String:
			return []
		if not turn.questions.all(func(question): return question is String):
			return []
	return turns


func issue_action(binding: Dictionary, pending_operation: Dictionary) -> Dictionary:
	var current: String = context().get("current", "")
	if binding.is_empty():
		if current.begins_with("draft_") and (saved.get("submitted", {}).has(current) or saved.get("linked", {}).has(current)):
			return {"kind":"discuss", "text":"查看分析进度"}
		if not current.begins_with("draft_"):
			return {}
		if direct_in_flight.has(current):
			return {"kind":"wait", "text":"正在核对建单回执…"}
		return {"kind":"publish", "text":"核对建单回执" if saved.get("direct_pending", {}).has(current) else "发布需求…"}
	if binding.has("error"):
		return {"kind":"wait", "text":"需求标识已改变"}
	if binding.get("closed", false):
		return {"kind":"wait", "text":"工单已关闭"}
	if str(binding.get("url", "")).is_empty() or not binding.has("status"):
		return {"kind":"wait", "text":"正在核对关联工单"}
	var key := routing_key(binding)
	if starting_direct.has(start_key(binding)):
		return {"kind":"wait", "text":"正在核对开工回执…"}
	var started := has_started_worker(binding, current)
	if not pending_operation.is_empty():
		return {"kind":"approval", "text":"查看待确认操作"}
	for turn in execution_turns.values():
		if turn.key == execution_key(binding):
			return {"kind":"view", "text":"查看推进对话"} if started else {"kind":"wait", "text":"推进对话处理中…"}
	if saved.get("execution_errors", {}).has(execution_key(binding)) and binding.get("status") in ["in-progress", "in-review"]:
		return {"kind":"resume", "text":"重试推进", "detail":saved.execution_errors[execution_key(binding)]}
	if started:
		return {"kind":"view", "text":"继续原工单对话"}
	if binding.get("status") not in ["planned", "in-progress", "in-review"]:
		return {"kind":"wait", "text":"等待工单就绪"}
	if saved.get("direct_start_receipts", {}).get(binding.url) == binding.request:
		return {"kind":"resume", "text":"继续推进对话"}
	if routing_in_flight.has(key):
		return {"kind":"wait", "text":"框架判断中…"}
	if binding.status == "planned":
		var decision := routing_receipt(binding)
		if decision.is_empty():
			if saved.get("routing_errors", {}).has(key):
				return {"kind":"retry", "text":"用当前模型重试判断"}
			return {"kind":"judge", "text":"判断需求"}
		if not decision.ready:
			return {"kind":"clarify", "text":"补充需求"}
	if saved.get("start_errors", {}).has(key):
		return {"kind":"start", "text":"重试开工", "detail":saved.start_errors[key]}
	return {"kind":"start", "text":"开始推进"}


func work_summary(item: Dictionary, judged: Dictionary) -> Dictionary:
	var current := context()
	var fresh_progress: bool = current.get("fresh_progress", false)
	var offline: bool = current.get("offline", false)
	var board: Dictionary = current.get("board", {})
	var url: String = item.get("url", "")
	if item.get("closed", false):
		return {"state":"completed", "text":"工单已关闭"}
	var names := PackedStringArray(item.get("workers", [])) if fresh_progress and not offline else PackedStringArray()
	var waiting := PackedStringArray()
	var key := routing_key(item)
	var stage := routing_stage(item)
	if not stage.is_empty():
		names.append("司南 · 需求判断" if stage == "sinan" else "偃师 · 需求分析")
	for worker in (chat_work.get(url, {}) if fresh_progress and not offline else {}):
		var activity: Dictionary = chat_work[url][worker]
		if item.get("source_sha256") != activity.version:
			continue
		var step: String = activity.step
		var role := str(worker).replace("sinan ·", "司南 ·").replace("yanshi ·", "偃师 ·")
		if step == "confirmation":
			waiting.append(role + " · 等待操作确认")
		else:
			names.append(role + (" · " + step if step != "chat" else ""))
	if not names.is_empty():
		return {"state":"running", "text":"正在工作 · " + "、".join(names + waiting), "chat_waiting":not waiting.is_empty()}
	if not waiting.is_empty():
		return {"state":"waiting", "text":"、".join(waiting), "chat_waiting":true}
	for turn in execution_turns.values():
		if turn.key == execution_key(item):
			return {"state":"running", "text":"推进对话处理中"}
	var failure: String = saved.get("execution_errors", {}).get(execution_key(item), "")
	if not failure.is_empty():
		return {"state":"failed", "text":"推进失败 · " + failure + " · 可在推进卡重试"}
	if routing_in_flight.has(key):
		return {"state":"running", "text":"天枢宿主 · 正在核对需求判断"}
	if not judged.is_empty() and saved.get("start_errors", {}).has(key):
		return {"state":"failed", "text":"开工受阻 · " + str(saved.start_errors[key])}
	if item.get("status") == "planned" and saved.get("direct_start_receipts", {}).get(url, "") == item.get("request", "missing"):
		return {"state":"waiting", "text":"已取得开工回执 · 查看推进对话"}
	if saved.get("routing_errors", {}).has(key) and judged.is_empty():
		return {"state":"failed", "text":"判断受阻 · " + str(saved.routing_errors[key])}
	if not fresh_progress and not board.is_empty():
		return {"state":"waiting", "text":"正在核实当前进度" if not offline else "离线 · 当前工作者待核实"}
	match item.get("status"):
		"blocked": return {"state":"blocked", "text":"工单受阻 · 等待处理"}
		"needs-decision":
			if item.get("answers_unverified", false):
				return {"state":"unknown", "text":"共享计划的答复待核实"}
			if item.get("pending_count", 0) > 0:
				return {"state":"waiting", "text":"请在待确认节点答复（剩余 %d 项）" % item.pending_count}
			if item.get("answered_count", 0) > 0:
				return {"state":"pending", "text":"已收到答复，等待工单负责人推进"}
			return {"state":"pending", "text":"待工单负责人核对后续工作"}
		"in-review": return {"state":"waiting", "text":"等待审查结果"}
	if item.get("status") == "planned":
		if judged.is_empty():
			return {"state":"waiting", "text":"等待司南判断回执"}
		return {"state":"waiting", "text":"判断完成 · 等待开始推进" if judged.ready else "偃师已提出问题 · 等待答复"}
	return {"state":"waiting", "text":"等待工作者回执"}
