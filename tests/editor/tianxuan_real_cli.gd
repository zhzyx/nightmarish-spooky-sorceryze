@tool
extends SceneTree
## Optional real-provider probe. Run only through run_tianxuan_real_cli.py with explicit opt-in.

var report := {"ok": false, "provider": "codex", "model_selection": "CLI default", "checks": {}}
var finished_result := {}
var request_id := "tianxuan-real-cli-" + str(Time.get_ticks_usec())


func _initialize() -> void:
	run.call_deferred()


func finish(error: String = "") -> void:
	if not error.is_empty():
		report.error = error
	var output := FileAccess.open(OS.get_environment("TX_REAL_CLI_RESULT"), FileAccess.WRITE)
	if output != null:
		output.store_string(JSON.stringify(report, "  ") + "\n")
	quit(0 if report.ok else 1)


func transcript(dock: Node) -> Array:
	var messages := []
	for container in dock.find_children("Messages", "", true, false):
		for label in container.find_children("*", "RichTextLabel", true, false):
			messages.append(label.get_parsed_text())
	return messages


func receive(id: String, result: Dictionary) -> void:
	if id == request_id:
		finished_result = result.duplicate(true)


func run() -> void:
	if OS.get_environment("TX_REAL_CLI_OPT_IN") != "explicit":
		finish("Explicit real-provider opt-in is required.")
		return
	await process_frame
	await process_frame
	var paths := EditorInterface.get_editor_paths()
	report.checks.private_editor_paths = paths.is_self_contained() and paths.get_data_dir().begins_with(OS.get_environment("TX_REAL_CLI_ROOT"))
	if not report.checks.private_editor_paths:
		finish("EditorPaths is not isolated.")
		return
	var dock := root.find_child("AI Chat", true, false)
	var controller := EditorInterface.get_base_control().get_node_or_null("TianxuanWorkspaceController")
	if dock == null or controller == null:
		finish("Compiled native model host is unavailable.")
		return
	var host: Node = controller.get_meta("model_host", null)
	if host == null:
		finish("Compiled native model host metadata is unavailable.")
		return
	for field in ["node", "codex", "workflow_python"]:
		var error: String = dock.set_runtime_field(field, OS.get_environment("TX_REAL_CLI_" + field.to_upper()))
		if not error.is_empty():
			finish("Unable to configure private runtime field " + field + ": " + error)
			return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(2)
	backend.item_selected.emit(2)
	var model = dock.find_child("CodexModel", true, false)
	model.text = ""
	model.text_changed.emit("")
	# No ordinary chat request is sent; a distinctive local draft detects accidental takeover.
	var input = dock.find_child("ChatInput", true, false)
	input.text = "普通 AIChat 的私有验收草稿：天璇调用不得消费。"
	input.text_changed.emit()
	await process_frame
	var before: Dictionary = dock.get_ai_session_snapshot().duplicate(true)
	var before_transcript := transcript(dock)
	report.model = host.configuration()
	report.runtime_paths = {"node": OS.get_environment("TX_REAL_CLI_NODE"), "codex": OS.get_environment("TX_REAL_CLI_CODEX")}
	if report.model.get("backend") != 2 or report.model.get("id") != "" or not report.model.get("configured", false):
		finish("The private editor did not select the existing Codex CLI default model.")
		return
	host.finished.connect(receive)
	var accepted: Dictionary = host.start("isolated-real-provider-smoke", request_id, [{"role": "user", "content": "仅回答：本机天璇连接正常"}])
	report.accepted = accepted.get("ok", false)
	if not report.accepted:
		finish(str(accepted.get("error", "The local request was not accepted.")))
		return
	var worker := host.find_child("TianxuanConsultationWorker", true, false)
	if worker == null:
		host.cancel(request_id)
		finish("An isolated model worker was not created.")
		return
	var settings: Control = worker.get_ai_settings_control()
	report.checks.tools_disabled = not settings.find_child("AllowTools", true, false).button_pressed
	report.checks.consultation_only = worker.find_child("ConsultationOnly", true, false).button_pressed
	report.checks.auto_write_disabled = not settings.find_child("AutoApplyFileChanges", true, false).button_pressed
	report.checks.auto_execute_disabled = not settings.find_child("AutoExecuteCommands", true, false).button_pressed
	report.checks.independent_worker = worker != dock
	var deadline := Time.get_ticks_msec() + 180000
	while finished_result.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	if finished_result.is_empty():
		host.cancel(request_id)
		finish("The real provider did not finish within 180 seconds.")
		return
	report.result = finished_result
	report.checks.ordinary_session_unchanged = before == dock.get_ai_session_snapshot()
	report.checks.ordinary_transcript_unchanged = before_transcript == transcript(dock)
	report.checks.real_answer_received = finished_result.get("ok", false) and str(finished_result.get("text", "")).strip_edges().contains("本机天璇连接正常")
	report.ok = report.checks.values().all(func(value): return value == true)
	finish("" if report.ok else str(finished_result.get("error", "The real provider probe failed an isolation or response check.")))
