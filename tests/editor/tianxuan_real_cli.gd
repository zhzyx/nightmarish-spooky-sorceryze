@tool
extends SceneTree
## Optional real-provider probe. Run only through run_tianxuan_real_cli.py with explicit opt-in.

var report := {"ok": false, "provider": "codex", "model_selection": "CLI default", "checks": {}}
var finished_result := {}
var request_id := "tianxuan-real-cli-" + str(Time.get_ticks_usec())


class OfflineSession extends Node:
	signal identity_resetting
	signal identity_changed
	signal authenticated
	signal connection_changed
	func get_identity() -> Dictionary:
		return {"id": "private-probe", "project": "private-probe", "role": "admin"}
	func scope_key() -> String:
		return "private-real-cli-recovery"
	func api_request(_method: int, _route: String, _payload := {}) -> Dictionary:
		return {"status": 0, "data": {}}


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
	report.checks.unknown_progress_is_private = host.progress("unknown-request") == {"active": false, "phase": "idle"}
	var recovery: Node
	var original := {"id": "original-unanswered-pig-request", "content": "给我生成一头猪的写实模型", "state": "unanswered", "answer": null, "error": "provider_unavailable"}
	var accepted := {}
	if OS.get_environment("TX_REAL_CLI_RESUME") == "yes":
		var session := OfflineSession.new()
		root.add_child(session)
		# Use the compiled controller scripts, with private storage and no real
		# business identity. Only the existing local provider transport is real.
		recovery = controller.get_script().new()
		recovery.storage_root = OS.get_environment("TX_REAL_CLI_ROOT").path_join("recovery-drafts")
		recovery.set_meta("session_controller", session)
		recovery.set_meta("model_host", host)
		recovery.set_meta("local_conversation_script", controller.get_meta("local_conversation_script"))
		root.add_child(recovery)
		recovery.active_conversation = "private-pig-conversation"
		recovery.cache["conversation:private-pig-conversation"] = {"id": recovery.active_conversation, "title": original.content, "version": 1, "turns": [original.duplicate(true)], "current": {}, "revisions": [], "requirement_id": null}
		recovery.save_draft(recovery.chat_draft_key(recovery.active_conversation), {"text": "未发送的补充规格"})
		recovery.resume_message(original.id, recovery.active_conversation, session.scope_key())
		if recovery.local_chat.busy():
			request_id = recovery.local_chat.job.request_id
			accepted = {"ok": true}
			report.checks.recovery_progress_visible = recovery.local_chat.progress().active
			recovery.resume_message(original.id)
			report.checks.recovery_not_duplicated = recovery.conversation().turns.size() == 2
	else:
		accepted = host.start("isolated-real-provider-smoke", request_id, [{"role": "user", "content": "仅回答：本机天璇连接正常"}])
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
	report.checks.running_progress_is_truthful = host.progress(request_id) == {"active": true, "phase": "waiting"}
	var deadline := Time.get_ticks_msec() + 180000
	while finished_result.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	if finished_result.is_empty():
		host.cancel(request_id)
		finish("The real provider did not finish within 180 seconds.")
		return
	report.result = finished_result
	report.checks.completed_progress_is_private = host.progress(request_id) == {"active": false, "phase": "idle"}
	report.checks.ordinary_session_unchanged = before == dock.get_ai_session_snapshot()
	report.checks.ordinary_transcript_unchanged = before_transcript == transcript(dock)
	if recovery:
		var current: Dictionary = recovery.conversation()
		report.checks.real_answer_received = finished_result.get("ok", false) and not str(finished_result.get("text", "")).strip_edges().is_empty()
		report.checks.original_request_preserved = current.turns.size() == 2 and current.turns[0] == original and current.turns[1].content == original.content and current.turns[1].continued_from == original.id
		report.checks.real_answer_in_history = current.turns.back().state == "answered" and current.turns.back().answer == finished_result.get("text")
		report.checks.draft_preserved = recovery.load_draft(recovery.chat_draft_key(recovery.active_conversation)).text == "未发送的补充规格"
		report.checks.progress_finished = not recovery.local_chat.progress().active
	else:
		report.checks.real_answer_received = finished_result.get("ok", false) and str(finished_result.get("text", "")).strip_edges().contains("本机天璇连接正常")
	report.ok = report.checks.values().all(func(value): return value == true)
	finish("" if report.ok else str(finished_result.get("error", "The real provider probe failed an isolation or response check.")))
