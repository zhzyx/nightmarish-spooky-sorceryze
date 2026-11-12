@tool
extends Node

signal checks_finished

var metadata_saver: Callable
var memory_script: Script
var memory_helper_source := ""
var connection_memory: Node
var prior_summary: Label
var git_script: Script
var git_helper_source := ""
var status_host: Control
var automatic_enabled := true
var chat: Node
var planner: Node
var synchronizer: RefCounted
var summary: Label
var retry: Button
var cancel_button: Button
var running := false
var automatic_started := false
var generation := 0
var probe_generation := -1
var ai_finished := true
var statuses := {
	"git":{"status":"idle", "message":"尚未检查"},
	"ai":{"status":"idle", "message":"尚未检查"},
	"catalog":{"status":"idle", "message":"尚未刷新"},
}


func _ready() -> void:
	if is_instance_valid(status_host):
		summary = Label.new()
		summary.name = "StartupCheckSummary"
		summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		status_host.add_child(summary)
		var actions := HFlowContainer.new()
		status_host.add_child(actions)
		retry = Button.new()
		retry.name = "RetryStartupChecks"
		retry.text = "重新检查并获取更新"
		retry.pressed.connect(run_checks)
		actions.add_child(retry)
		cancel_button = Button.new()
		cancel_button.name = "CancelStartupChecks"
		cancel_button.text = "取消"
		cancel_button.pressed.connect(cancel_checks)
		actions.add_child(cancel_button)
		prior_summary = Label.new()
		prior_summary.name = "LastStartupChecks"
		prior_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		status_host.add_child(prior_summary)
		var prior: Dictionary = EditorInterface.get_editor_settings().get_project_metadata("startup_checks", "last_run", {})
		if not prior.is_empty():
			prior_summary.text = "上次检查（历史记录，当前状态以本次验证为准） · %s\nGit：%s · AI：%s · 模型库：%s" % [str(prior.get("time", "")), str(prior.get("git", "")), str(prior.get("ai", "")), str(prior.get("catalog", ""))]
	if memory_script:
		connection_memory = Node.new()
		connection_memory.name = "AIConnectionMemory"
		connection_memory.set_script(memory_script)
		connection_memory.helper_source = memory_helper_source
		connection_memory.metadata_saver = metadata_saver
		add_child(connection_memory)
	_render()
	_start_automatic.call_deferred()


func _start_automatic() -> void:
	if automatic_started or not automatic_enabled or DisplayServer.get_name() == "headless":
		return
	var args := OS.get_cmdline_args()
	if "--script" in args or "-s" in args or "--recovery-mode" in args:
		return
	automatic_started = true
	# All native docks are constructed before the deferred startup event.
	await get_tree().process_frame
	await run_checks()


func get_status() -> Dictionary:
	return {"running":running, "automatic_started":automatic_started, "checks":statuses.duplicate(true)}


func _render() -> void:
	if is_instance_valid(summary):
		summary.text = "Git：%s\nAI 连接：%s\n天枢模型库：%s" % [statuses.git.message, statuses.ai.message, statuses.catalog.message]
	if is_instance_valid(retry):
		retry.disabled = running
	if is_instance_valid(cancel_button):
		cancel_button.visible = running


func _set_result(key: String, value: Dictionary) -> void:
	statuses[key] = value
	_render()


func run_checks() -> void:
	if running or not is_inside_tree():
		return
	if not is_instance_valid(chat):
		chat = get_tree().root.find_child("AI Chat", true, false)
	if not is_instance_valid(planner):
		planner = get_tree().root.find_child("DaqianWorkspace", true, false)
	running = true
	generation += 1
	var current := generation
	ai_finished = false
	_render()
	if is_instance_valid(connection_memory):
		await connection_memory.restore()
		if generation != current: return
	_set_result("git", {"status":"checking", "message":"正在检查当前项目并获取远端更新…"})
	_check_ai(current)
	var runtime: Dictionary = chat.get_runtime_configuration().get("executables", {}) if is_instance_valid(chat) else {}
	if git_script:
		synchronizer = git_script.new()
		synchronizer.helper_source = git_helper_source
		var result: Dictionary = await synchronizer.run(self, ProjectSettings.globalize_path("res://"), str(runtime.get("workflow_python", "")))
		if generation != current:
			return
		_set_result("git", result)
	else:
		_set_result("git", {"status":"unavailable", "message":"Git 检查组件未就绪。"})
	while generation == current and not ai_finished:
		await get_tree().create_timer(0.1).timeout
	if generation != current:
		return
	var record := {"time":Time.get_datetime_string_from_system(false, true)}
	for key in statuses:
		record[key] = str(statuses[key].status)
	var settings := EditorInterface.get_editor_settings()
	settings.set_project_metadata("startup_checks", "last_run", record)

	running = false
	synchronizer = null
	_render()
	checks_finished.emit()


func _check_ai(current: int) -> void:
	if not is_instance_valid(chat):
		_set_result("ai", {"status":"needs_configuration", "message":"项目 AI 配置尚未就绪。"})
		_set_result("catalog", {"status":"needs_configuration", "message":"请先配置工作区与运行环境。"})
		ai_finished = true
		return
	if not chat.is_connected("ai_connection_status_changed", _update_ai_status):
		chat.connect("ai_connection_status_changed", _update_ai_status)
	# The existing probe binds its response to the current config and credential.
	probe_generation = -1
	if chat.get_ai_connection_status().get("state", "") != "checking":
		chat.verify_ai_connection()
		probe_generation = int(chat.get_ai_connection_status().get("generation", -1))
	var token := probe_generation
	_update_ai_status()
	_refresh_catalog(current)
	var deadline := Time.get_ticks_msec() + 50_000
	while generation == current and str(chat.get_ai_connection_status().get("state", "")) == "checking":
		if token >= 0 and int(chat.get_ai_connection_status().get("generation", -1)) != token:
			break
		if Time.get_ticks_msec() >= deadline:
			if token >= 0:
				chat.cancel_ai_connection_check(token)
			_set_result("ai", {"status":"timeout", "message":"连接验证超时，请稍后重试。"})
			break
		await get_tree().create_timer(0.1).timeout
	if current != generation:
		return
	while current == generation and statuses.catalog.status == "checking":
		await get_tree().create_timer(0.1).timeout
	if current == generation:
		ai_finished = true


func _update_ai_status() -> void:
	if not is_instance_valid(chat):
		return
	var value: Dictionary = chat.get_ai_connection_status()
	_set_result("ai", {"status":value.get("state", "unconfigured"), "message":value.get("message", "请检查 AI 配置。")})


func _refresh_catalog(current: int) -> void:
	_set_result("catalog", {"status":"checking", "message":"正在核对身份并刷新已配置模型…"})
	var result := {"status":"needs_configuration", "message":"天枢尚未就绪，请检查工作区与 Python 配置。"}
	if is_instance_valid(planner) and planner.has_method("refresh_startup_models"):
		result = await planner.refresh_startup_models()
	if generation == current:
		_set_result("catalog", result)


func cancel_checks() -> void:
	generation += 1
	if is_instance_valid(connection_memory):
		connection_memory.epoch += 1
	if synchronizer:
		synchronizer.cancel()
	if running:
		if is_instance_valid(planner) and planner.has_method("cancel_startup_model_refresh"):
			planner.cancel_startup_model_refresh()
		if is_instance_valid(chat) and probe_generation >= 0:
			chat.cancel_ai_connection_check(probe_generation)
	probe_generation = -1
	for key in statuses:
		if statuses[key].status == "checking":
			statuses[key] = {"status":"cancelled", "message":"已取消，可重新检查。"}
	running = false
	ai_finished = true
	_render()
	checks_finished.emit()


func _exit_tree() -> void:
	cancel_checks()
