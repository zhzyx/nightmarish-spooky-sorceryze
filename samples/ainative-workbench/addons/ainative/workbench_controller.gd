@tool
extends RefCounted
## Owns workflow execution and its process transport without any UI nodes.

signal command_completed(command: String, result: Dictionary, request: Dictionary)
signal command_failed(command: String, failure: Dictionary)
signal runtime_event(event: Dictionary)

var run_id := ""
var current: Dictionary = {}
var jobs: Dictionary = {}
var serial := 0
var heartbeat := 0
var auto_step := false
var creating := false
var cancel_create := false
var preview_target := ""

var _settings: Dictionary = {}
var _run_settings: Dictionary = {}
var _runtime: RefCounted
var _runtime_run_id := ""
var _generation := 0
var _model: Dictionary = {}
var _model_source := "workflow"
var _result_epoch := 0
var _cancel_requested := false
var _processing_result := false
var _transport_id := Crypto.new().generate_random_bytes(16).hex_encode()
var _resume_after_restore := false

func _init(runtime: RefCounted = null):
	_runtime = runtime
	if _runtime == null and ClassDB.class_exists("AIWorkflowRuntime"):
		_runtime = ClassDB.instantiate("AIWorkflowRuntime")

func configure(settings: Dictionary):
	_settings = settings.duplicate(true)

func is_busy() -> bool:
	return _processing_result or creating or auto_step or not jobs.is_empty()

func has_command(command: String) -> bool:
	return jobs.values().any(func(job):
		return job.command == command)

func runtime_snapshot() -> Dictionary:
	if _runtime == null or _runtime_run_id.is_empty():
		return {}
	return _runtime.snapshot(_runtime_run_id)

func _begin_runtime(model: Dictionary, target: String, settings: Dictionary, model_source := "workflow") -> bool:
	if _runtime == null:
		_fail("create", "runtime_unavailable", {"class": "AIWorkflowRuntime"})
		return false
	_model = model.duplicate(true)
	_model_source = model_source
	var selection: Dictionary = {}
	for node in model.get("nodes", []):
		if node.get("provider_manifest") is Dictionary:
			selection[str(node.id)] = node.provider_manifest.duplicate(true)
		else:
			selection[str(node.id)] = {
				"provider": node.get("provider", ""),
				"model": node.get("model", ""),
				"image_model": node.get("image_model", "")
			}
	var request_id = str(OS.get_process_id()) + "-" + str(Time.get_ticks_usec()) + "-" + str(serial)
	var binding = {
		"executor": "ainative",
		"database": str(settings.get("database", "")),
		"target": target,
		"executor_run_id": run_id,
		"model_source": model_source
	}
	var event: Dictionary = _runtime.begin_run("maliang", str(settings.get("database", "maliang")), request_id, selection, binding)
	if event.is_empty():
		_fail("create", "runtime_rejected", {})
		return false
	_runtime_run_id = str(event.run_id)
	_generation = int(event.generation)
	var expected_run = _runtime_run_id
	var expected_generation = _generation
	runtime_event.emit(event)
	var snapshot = runtime_snapshot()
	return (
		_runtime_run_id == expected_run
		and _generation == expected_generation
		and snapshot.get("state") == "running"
		and snapshot.get("generation") == expected_generation
	)

func _publish(kind: String, payload: Dictionary = {}, state: String = ""):
	if _runtime == null or _runtime_run_id.is_empty():
		return
	var event: Dictionary = _runtime.publish(_runtime_run_id, _generation, kind, payload, state)
	if not event.is_empty():
		runtime_event.emit(event)

func start(model: Dictionary, target: String = "") -> bool:
	if is_busy():
		return false
	var submitted_model = model.duplicate(true)
	var submitted_settings = _settings.duplicate(true)
	run_id = ""
	_cancel_requested = false
	if not _begin_runtime(submitted_model, target, submitted_settings):
		return false
	current = {}
	preview_target = target
	auto_step = true
	creating = true
	cancel_create = false
	_run_settings = submitted_settings
	var request = {"model": submitted_model}
	if not target.is_empty():
		request.target = target
	return _launch("create", request, _run_settings)

func resume():
	if _processing_result or creating or run_id.is_empty() or not jobs.is_empty():
		return
	var submitted_settings = _settings.duplicate(true)
	var snapshot = runtime_snapshot()
	if snapshot.is_empty():
		_resume_after_restore = true
		_run_settings = submitted_settings
		_launch("status", {"run": run_id}, _run_settings)
		return
	if snapshot.is_empty() or snapshot.state in ["succeeded", "failed", "cancelled"]:
		if not _begin_runtime(_model, preview_target, submitted_settings, _model_source):
			return
	_run_settings = submitted_settings
	auto_step = true
	_launch("step", {"run": run_id}, _run_settings)

func cancel():
	_result_epoch += 1
	_cancel_requested = true
	_resume_after_restore = false
	auto_step = false
	preview_target = ""
	if _runtime != null and not _runtime_run_id.is_empty():
		var event: Dictionary = _runtime.cancel(_runtime_run_id)
		if not event.is_empty():
			runtime_event.emit(event)
	if creating:
		cancel_create = true
	elif not run_id.is_empty():
		_launch("cancel", {"run": run_id}, _run_settings if not _run_settings.is_empty() else _settings)

func retry(node_id: String):
	if is_busy() or run_id.is_empty():
		return
	var submitted_settings = _settings.duplicate(true)
	if not _begin_runtime(_model, preview_target, submitted_settings, _model_source):
		return
	_run_settings = submitted_settings
	_launch("retry", {"run": run_id, "node": node_id}, _run_settings)

func reset():
	if is_busy():
		return
	run_id = ""
	current = {}
	preview_target = ""
	_runtime_run_id = ""
	_generation = 0
	_model = {}
	_model_source = "workflow"
	_run_settings = {}
	_cancel_requested = false
	_resume_after_restore = false
	_result_epoch += 1

func restore_run(executor_run_id: String) -> bool:
	if is_busy() or executor_run_id.is_empty():
		return false
	reset()
	run_id = executor_run_id
	_run_settings = _settings.duplicate(true)
	return _launch("status", {"run": run_id}, _run_settings)

func submit(command: String, request: Dictionary) -> bool:
	if command == "status" and _runtime_run_id.is_empty():
		_run_settings = _settings.duplicate(true)
	return _launch(command, request, _settings)

func _fail(command: String, code: String, diagnostic: Dictionary, message: String = ""):
	var was_processing = _processing_result
	_processing_result = true
	auto_step = false
	_resume_after_restore = false
	if command == "create":
		creating = false
		preview_target = ""
	if command in ["create", "step", "retry"]:
		_publish("failed", {"code": code, "diagnostic": diagnostic}, "failed")
	command_failed.emit(command, {"code": code, "message": message, "diagnostic": diagnostic})
	_processing_result = was_processing

func _launch(command: String, request: Dictionary, settings: Dictionary) -> bool:
	var interpreter = str(settings.get("python", "")).strip_edges()
	var script = str(settings.get("script", "")).strip_edges()
	if command == "managed-comfy" and settings.has("bundled_root") and request.get("runtime_root") == settings.bundled_root:
		interpreter = str(settings.get("bundled_python", interpreter))
	if interpreter.is_empty() or script.is_empty():
		_fail(command, "runtime_path_empty", {"python": interpreter, "script": script})
		return false
	serial += 1
	var prefix = str(settings.get("state_dir", "")).path_join(str(OS.get_process_id()) + "-" + _transport_id + "-" + str(serial))
	var request_file = FileAccess.open(prefix + ".json", FileAccess.WRITE)
	if request_file == null:
		_fail(command, "request_write_failed", {"path": prefix + ".json"})
		return false
	request_file.store_string(JSON.stringify(request, "", true, true))
	request_file.close()
	var arguments = PackedStringArray([
		script, command,
		"--db", str(settings.get("database", "")),
		"--factory", str(settings.get("factory", "editor_demo:factory")),
		"--spec", prefix + ".json",
		"--result", prefix + ".result"
	])
	if interpreter == settings.get("bundled_python", ""):
		arguments = PackedStringArray(["-E", "-s", "-B"]) + arguments
	if command in ["create", "step"] and settings.get("use_service", false):
		arguments.append_array(PackedStringArray(["--service-config", str(settings.get("service_config", ""))]))
	var pid = OS.create_process(interpreter, arguments)
	if pid < 0:
		DirAccess.remove_absolute(prefix + ".json")
		_fail(command, "process_start_failed", {"python": interpreter, "script": script})
		return false
	jobs[pid] = {
		"command": command,
		"prefix": prefix,
		"spec": request.duplicate(true),
		"python": interpreter,
		"script": script,
		"state_dir": settings.get("state_dir", ""),
		"runtime_run_id": _runtime_run_id,
		"generation": _generation,
		"result_epoch": _result_epoch
	}
	return true

func _job_is_current(job: Dictionary, allow_cancelled_create := false) -> bool:
	if job.runtime_run_id != _runtime_run_id or job.generation != _generation:
		return false
	if job.command not in ["create", "step", "status", "cancel", "retry", "preview"]:
		return true
	return job.result_epoch == _result_epoch or (allow_cancelled_create and job.command == "create" and _cancel_requested)

func _attach_runtime(data: Dictionary, job: Dictionary) -> bool:
	var model_nodes: Array = []
	for node_id in data.get("nodes", {}):
		var node: Dictionary = data.nodes[node_id]
		var definition = {
			"id": node_id,
			"provider": node.get("provider", ""),
			"provider_manifest": node.get("provider_manifest", {}).duplicate(true)
		}
		model_nodes.append(definition)
	if not _begin_runtime({"nodes": model_nodes}, "", _run_settings, "persisted_executor"):
		return false
	job.runtime_run_id = _runtime_run_id
	job.generation = _generation
	return _job_is_current(job)

func _apply_result(command: String, data: Dictionary, job: Dictionary):
	if command == "create":
		creating = false
		run_id = str(data.run_id)
		var saved_run = FileAccess.open(str(job.state_dir).path_join("last_run.txt"), FileAccess.WRITE)
		if saved_run != null:
			saved_run.store_string(run_id)
			saved_run.close()
		if _cancel_requested:
			_launch("cancel", {"run": run_id}, _run_settings)
			return
		_publish("progress", {"executor_run_id": run_id})
		if not _job_is_current(job):
			return
	elif command in ["step", "status", "cancel", "retry"]:
		if str(job.spec.get("run", "")) != run_id:
			return
		if _runtime_run_id.is_empty() and not _attach_runtime(data, job):
			return
		current = data.duplicate(true)
		if command == "retry":
			auto_step = true
		if data.state != "running":
			auto_step = false
		var state = "reconciling" if data.state == "reconcile" else str(data.state)
		var kind = "progress"
		if state == "succeeded":
			for node_id in data.get("nodes", {}):
				var node: Dictionary = data.nodes[node_id]
				if node.get("state") == "succeeded":
					_publish("artifact_ready", {"node": node_id, "outputs": node.get("job", {}).get("outputs", {})})
					if not _job_is_current(job):
						return
			kind = "completed"
		elif state == "failed":
			kind = "failed"
		elif state == "cancelled":
			kind = "cancelled"
		var states: Dictionary = {}
		for node_id in data.get("nodes", {}):
			var node: Dictionary = data.nodes[node_id]
			states[node_id] = {
				"state": node.get("state", ""),
				"attempt": node.get("attempt", 0),
				"error": node.get("error")
			}
		_publish(kind, {"executor_run_id": run_id, "nodes": states}, state)
		if not _job_is_current(job):
			return
		if command == "status" and _resume_after_restore:
			_resume_after_restore = false
			if state in ["running", "reconciling"]:
				auto_step = true
		if not preview_target.is_empty() and data.get("nodes", {}).get(preview_target, {}).get("state") == "succeeded":
			var finished_target = preview_target
			preview_target = ""
			auto_step = false
			_launch("preview", {"run": run_id, "node": finished_target}, _run_settings)
	command_completed.emit(command, data, job.spec)

func tick():
	if _processing_result:
		return
	heartbeat += 1
	for pid in jobs.keys():
		if OS.is_process_running(pid):
			continue
		var job: Dictionary = jobs[pid]
		jobs.erase(pid)
		var result = null
		if FileAccess.file_exists(job.prefix + ".result"):
			result = JSON.parse_string(FileAccess.get_file_as_string(job.prefix + ".result"))
		DirAccess.remove_absolute(job.prefix + ".json")
		DirAccess.remove_absolute(job.prefix + ".result")
		if not _job_is_current(job, true):
			continue
		if not result is Dictionary or not result.get("ok", false) or not result.get("result") is Dictionary:
			var message = str(result.get("message", "")) if result is Dictionary else ""
			var diagnostic: Dictionary = {
				"code": "host_result_missing",
				"command": job.command,
				"python": job.python,
				"script": job.script,
				"exit_code": OS.get_process_exit_code(pid)
			}
			if result is Dictionary:
				diagnostic = result.get("diagnostic", {})
			_fail(job.command, str(diagnostic.get("code", "host_result_failed")), diagnostic, message)
			continue
		_processing_result = true
		_apply_result(job.command, result.result, job)
		_processing_result = false
	if auto_step and jobs.is_empty() and not run_id.is_empty():
		_launch("step", {"run": run_id}, _run_settings)

func shutdown():
	auto_step = false
	for pid in jobs:
		if OS.is_process_running(pid):
			OS.kill(pid)
	jobs.clear()
