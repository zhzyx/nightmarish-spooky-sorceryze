@tool
extends Node
# Owns transport and orchestration, never controls. Executor SQLite remains the
# authority for domain tasks. The shared runtime is an in-process event projection.
signal completed(command: String, data: Dictionary, spec: Dictionary)
signal failed(command: String, message: String, details: Dictionary, section: String)
signal state_changed(data: Dictionary)
signal run_event(snapshot: Dictionary)

var run_id = ""
var current: Dictionary = {}
var jobs: Dictionary = {}
var serial = 0
var heartbeat = 0
var auto_step = false
var creating = false
var cancel_create = false
var preview_target = ""
var configuration: Dictionary = {}
var run_configuration: Dictionary = {}
var model_snapshot: Dictionary = {}
var public_snapshot: Dictionary = {}
var runtime: Object
var _views = 0
var _event_serial = 0
var _cancel_requested = false
var _service_snapshot_path = ""
var _execution_epoch = 0

func _ready():
	if runtime == null and Engine.is_editor_hint() and Engine.has_singleton("AIWorkflowRuntime"):
		runtime = Engine.get_singleton("AIWorkflowRuntime")

func configure(value: Dictionary):
	configuration = value.duplicate(true)

func attach_view():
	_views += 1

func detach_view():
	_views = maxi(0, _views - 1)
	# A replacement view can attach in the same frame. A second live view retains
	# the controller. Closing the last view stops its processes as before.
	_close_if_unused.call_deferred()

func _close_if_unused():
	if _views == 0: shutdown()

func restore():
	if not jobs.is_empty() or auto_step: return
	if not run_id.is_empty():
		launch("status", {"run": run_id})
		return
	var path = str(configuration.get("state_dir", "")).path_join("last_run.txt")
	if not FileAccess.file_exists(path): return
	run_id = FileAccess.get_file_as_string(path).strip_edges()
	if run_id.is_empty(): return
	run_configuration = configuration.duplicate(true)
	var identity_path = str(configuration.get("state_dir", "")).path_join("last_run.identity.json")
	if FileAccess.file_exists(identity_path):
		var identity = JSON.parse_string(FileAccess.get_file_as_string(identity_path))
		if identity is Dictionary and identity.get("domain_run_id") == run_id and identity.get("nodes") is Array:
			model_snapshot = {"nodes": identity.nodes.duplicate(true)}
	if not _begin_public("restore", "reconciling"): return
	# Status is a read, never a submission or an automatic resume.
	launch("status", {"run": run_id})

func start(model: Dictionary, target: String = ""):
	if creating or auto_step or not jobs.is_empty(): return
	_execution_epoch += 1
	run_configuration = configuration.duplicate(true)
	model_snapshot = model.duplicate(true)
	run_id = ""
	current = {}
	preview_target = target
	cancel_create = false
	_cancel_requested = false
	auto_step = true
	creating = true
	if not _begin_public("create"): return
	var spec = {"model": model_snapshot.duplicate(true)}
	if not target.is_empty(): spec.target = target
	launch("create", spec)

func resume():
	if creating or run_id.is_empty() or not jobs.is_empty(): return
	_execution_epoch += 1
	_cancel_requested = false
	if public_snapshot.is_empty() or public_snapshot.get("state") in ["succeeded", "failed", "cancelled"]:
		if not _begin_public("resume", "reconciling"): return
	auto_step = true
	launch("step", {"run": run_id})

func cancel():
	_execution_epoch += 1
	auto_step = false
	preview_target = ""
	_cancel_requested = true
	if runtime != null and not public_snapshot.is_empty():
		var result: Dictionary = runtime.cancel(public_snapshot.run_id, public_snapshot.generation, "cancel")
		_accept_public(result)
	if creating:
		cancel_create = true
	elif not run_id.is_empty():
		launch("cancel", {"run": run_id})

func retry(node_id: String):
	if creating or auto_step or not jobs.is_empty() or run_id.is_empty(): return
	_execution_epoch += 1
	_cancel_requested = false
	if not _begin_public("retry"): return
	launch("retry", {"run": run_id, "node": node_id})

func _begin_public(operation: String, initial_state: String = "running") -> bool:
	public_snapshot = {}
	if runtime == null: return true # Standalone sample/old editor, domain still works.
	var selected: Array = []
	for node in model_snapshot.get("nodes", []):
		var selection = {"node_id": node.get("id", ""), "provider": node.get("provider", ""), "model": node.get("model", ""), "variant": node.get("type", "copy")}
		# Auxiliary image model is independent from the mesh node's own choice.
		if node.has("image_model"): selection["image_model"] = node.image_model
		selected.append(selection)
	var request = {"workflow": "maliang", "scope": str(configuration.get("db", "")).sha256_text(),
		"request_id": str(OS.get_process_id()) + "-" + str(Time.get_ticks_usec()),
		"model": {"nodes": selected}, "binding": {"controller": "maliang", "operation": operation, "domain_run_id": run_id},
		"input": {"target": preview_target, "domain_run_id": run_id}, "initial_state": initial_state}
	var result: Dictionary = runtime.begin_run(request)
	if not result.get("ok", false):
		_failure(operation, "无法建立公共运行身份。", {"code": result.get("code", "runtime_rejected")})
		return false
	_accept_public(result)
	return true

func _accept_public(result: Dictionary):
	if result.get("ok", false):
		public_snapshot = result.snapshot.duplicate(true)
		if result.get("changed", false): run_event.emit(public_snapshot.duplicate(true))

func _publish_public(state: String, kind: String, data: Dictionary):
	if runtime == null or public_snapshot.is_empty(): return
	_event_serial += 1
	var event_kind = {"succeeded":"completed", "failed":"failed", "cancelled":"cancelled"}.get(state, "progress")
	# Do not copy task prompts, local paths or credential-bearing service config
	# into public metadata. Domain detail remains queryable from Executor.
	var result: Dictionary = runtime.publish({"run_id": public_snapshot.run_id,
		"generation": public_snapshot.generation, "event_id": "event-" + str(_event_serial),
		"expected_sequence": public_snapshot.sequence, "kind": event_kind, "state": state,
		"payload": {"domain_run_id": run_id, "domain_state": data.get("state", state), "phase":kind}})
	_accept_public(result)
	if not result.get("ok", false) and result.get("code", "") not in ["terminal", "duplicate"]:
		auto_step = false
		failed.emit("runtime", "公共运行状态更新失败，请核对当前任务回执。", {"code":result.get("code", "runtime_rejected")}, "ai")

func _failure(command: String, message: String, details: Dictionary = {}, section: String = "ai", unknown_outcome := false):
	auto_step = false
	if command == "create":
		creating = false
		preview_target = ""
	if command in ["create", "step", "retry", "status", "cancel"]:
		_publish_public("reconciling" if unknown_outcome else "failed", "transport_unknown" if unknown_outcome else "error", {})
	failed.emit(command, message, details, section)

func launch(command: String, spec: Dictionary):
	var config = run_configuration if command in ["create", "step", "cancel", "retry", "status", "preview", "publish"] and not run_configuration.is_empty() else configuration
	var interpreter = str(config.get("python", ""))
	var script = str(config.get("script", ""))
	var bundle: Dictionary = config.get("bundled_runtime", {})
	if command == "managed-comfy" and bundle.has("root") and spec.get("runtime_root") == bundle.root:
		interpreter = bundle.python
	if interpreter.is_empty() or script.is_empty():
		_failure(command, "运行环境为空。请在环境设置中选择马良使用的 Python 3.11 或更高版本。" if interpreter.is_empty() else "运行工具路径为空。请在环境设置中恢复马良内置工具路径。", {}, "environment")
		return
	serial += 1
	var prefix = str(config.get("state_dir", "")).path_join(str(OS.get_process_id()) + "-" + str(get_instance_id()) + "-" + str(serial))
	var file = FileAccess.open(prefix + ".json", FileAccess.WRITE)
	if file == null:
		_failure(command, "无法写入本机运行请求，请检查用户目录是否可写。")
		return
	file.store_string(JSON.stringify(spec, "", true, true))
	file.close()
	var arguments = PackedStringArray([script, command, "--db", str(config.get("db", "")), "--factory", str(config.get("factory", "")), "--spec", prefix + ".json", "--result", prefix + ".result"])
	if bundle.has("python") and interpreter == bundle.python:
		arguments = PackedStringArray(["-E", "-s", "-B"]) + arguments
	if command in ["create", "step"] and config.get("uses_service", false):
		# The host persists the resolved service with its run. Freeze the create
		# file too, so editing settings before child startup cannot change it.
		var service_path = str(config.get("service_config", ""))
		if command == "create":
			_service_snapshot_path = prefix + ".service.json"
			if DirAccess.copy_absolute(service_path, _service_snapshot_path) != OK:
				DirAccess.remove_absolute(prefix + ".json")
				_failure(command, "无法冻结本次运行的生成服务配置。")
				return
			service_path = _service_snapshot_path
		arguments.append_array(PackedStringArray(["--service-config", service_path]))
	var pid = OS.create_process(interpreter, arguments)
	if pid < 0:
		DirAccess.remove_absolute(prefix + ".json")
		_cleanup_service_snapshot()
		_failure(command, "无法启动本机运行环境，请检查马良 Python 的位置与执行权限。", {"python": interpreter}, "environment")
		return
	jobs[pid] = {"command": command, "prefix": prefix, "spec": spec.duplicate(true), "python": interpreter, "script": script, "epoch":_execution_epoch}

func _accept_reply(job: Dictionary) -> bool:
	if job.command not in ["create", "step", "retry", "status", "cancel"]: return true
	# Cancelling during creation must still recover the new domain identity so
	# the original run can be cancelled, without starting a second create.
	return int(job.get("epoch", _execution_epoch)) == _execution_epoch or (job.command == "create" and cancel_create)

func _process(_delta):
	heartbeat += 1
	for pid in jobs.keys():
		if OS.is_process_running(pid): continue
		var job = jobs[pid]
		jobs.erase(pid)
		var path = job.prefix + ".result"
		var result = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		DirAccess.remove_absolute(job.prefix + ".json")
		DirAccess.remove_absolute(path)
		if job.command == "create": _cleanup_service_snapshot()
		if not _accept_reply(job): continue
		if not result is Dictionary or not result.get("ok", false) or not result.get("result") is Dictionary:
			var message = str(result.get("message", "")) if result is Dictionary else ""
			if message.is_empty(): message = "本机运行环境未返回有效结果。请确认 Python 3.11 或更高版本可用，并检查本机设置。"
			var details: Dictionary = result.get("diagnostic", {}) if result is Dictionary else {"code": "host_result_missing", "command": job.command, "python": job.python, "script": job.script, "exit_code": OS.get_process_exit_code(pid)}
			_failure(job.command, "操作回执待核对：" + message, details, "ai", true)
			continue
		_complete(job, result.result)
	if auto_step and jobs.is_empty() and not run_id.is_empty(): launch("step", {"run": run_id})

func _complete(job: Dictionary, data: Dictionary):
	if not _accept_reply(job): return
	if job.command == "create" and (not data.get("run_id") is String or str(data.run_id).is_empty()):
		_failure(job.command, "运行环境未返回有效运行编号。", {}, "ai", true)
		return
	if job.command in ["step", "status", "cancel", "retry"] and (not data.get("state") is String or not data.get("nodes") is Dictionary):
		_failure(job.command, "运行环境未返回有效任务状态。", {}, "ai", true)
		return
	if job.command == "create":
		creating = false
		run_id = str(data.get("run_id", ""))
		var file = FileAccess.open(str(run_configuration.get("state_dir", "")).path_join("last_run.txt"), FileAccess.WRITE)
		if file != null:
			file.store_string(run_id)
			file.close()
		var selections: Array = []
		for node in model_snapshot.get("nodes", []):
			var selection: Dictionary = {}
			for key in ["id", "type", "provider", "model", "image_model"]:
				if node.has(key): selection[key] = node[key]
			selections.append(selection)
		var identity = FileAccess.open(str(run_configuration.get("state_dir", "")).path_join("last_run.identity.json"), FileAccess.WRITE)
		if identity != null:
			identity.store_string(JSON.stringify({"domain_run_id": run_id, "nodes": selections}))
			identity.close()
		_publish_public("running", "created", {})
		if cancel_create: launch("cancel", {"run": run_id})
	elif job.command in ["step", "status", "cancel", "retry"]:
		# A step may finish after cancel. Never restart orchestration or replace
		# the cancellation receipt with that stale response; read Executor again.
		if _cancel_requested and job.command in ["step", "retry"]:
			if jobs.is_empty() and not run_id.is_empty() and current.get("state") != "cancelled": launch("cancel", {"run": run_id})
			return
		current = data.duplicate(true)
		if job.command == "retry": auto_step = true
		if data.state != "running": auto_step = false
		var state = "reconciling" if data.state == "reconcile" else str(data.state)
		_publish_public(state, "domain_state", data)
		state_changed.emit(current.duplicate(true))
		if not preview_target.is_empty() and data.get("nodes", {}).has(preview_target) and data.nodes[preview_target].state == "succeeded":
			var target = preview_target
			preview_target = ""
			auto_step = false
			launch("preview", {"run": run_id, "node": target})
	completed.emit(job.command, data.duplicate(true), job.spec.duplicate(true))

func _cleanup_service_snapshot():
	if not _service_snapshot_path.is_empty():
		DirAccess.remove_absolute(_service_snapshot_path)
		_service_snapshot_path = ""

func shutdown():
	_execution_epoch += 1
	auto_step = false
	creating = false
	for pid in jobs:
		if OS.is_process_running(pid): OS.kill(pid)
		DirAccess.remove_absolute(jobs[pid].prefix + ".json")
		DirAccess.remove_absolute(jobs[pid].prefix + ".result")
	jobs.clear()
	_cleanup_service_snapshot()
	# Do not synthesize a domain cancellation: killing transport leaves the
	# Executor journal authoritative and recoverable via status/reconcile.
	if not public_snapshot.is_empty() and public_snapshot.get("state") not in ["succeeded", "failed", "cancelled"]:
		_publish_public("reconciling", "transport_stopped", {})

func _exit_tree():
	shutdown()
