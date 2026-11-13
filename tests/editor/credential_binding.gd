@tool
extends Node

var chat
var settings
var checks: Array = []
var failures: Array = []

func _ready() -> void:
	run.call_deferred()

func check(ok: bool, label: String) -> void:
	checks.append(label)
	if not ok: failures.append(label)

func edit(field: String, value: String, signal_change := true) -> void:
	var control = settings.find_child(field, true, false)
	if control == null:
		control = chat.find_child(field, true, false)
	control.text = value
	if signal_change: control.text_changed.emit(value)

func verify() -> void:
	chat.verify_ai_connection()
	var deadline := Time.get_ticks_msec() + 5000
	while chat.get_ai_connection_status().state == "checking" and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.03).timeout
	check(chat.get_ai_connection_status().state == "available", "loopback connection probe completes")

func wait_send_ready() -> void:
	var send = chat.find_child("Send", true, false)
	var deadline := Time.get_ticks_msec() + 15000
	while send.disabled and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.03).timeout
	check(not send.disabled, "startup and catalog refreshes release the send action")

func run() -> void:
	await get_tree().create_timer(0.5).timeout
	chat = get_tree().root.find_child("AI Chat", true, false)
	settings = chat.get_ai_settings_control()
	var key = settings.find_child("APIKey", true, false)
	if OS.get_environment("BINDING_CASE") == "openai-official":
		# A real backend switch must wait for the same lock that the UI exposes.
		# Select the API controls before reading their credential accessor, but do
		# not emit a change until the official endpoint has been replaced by loopback.
		var backend = chat.find_child("AIBackend", true, false)
		var startup_deadline := Time.get_ticks_msec() + 35000
		while backend.disabled and Time.get_ticks_msec() < startup_deadline:
			await get_tree().create_timer(0.03).timeout
		check(not backend.disabled, "startup model discovery releases the backend selector")
		backend.select(0)
		if chat.has_method("get_ai_credential"):
			check(str(chat.get_ai_credential()) == OS.get_environment("BINDING_SECRET"), "OpenAI environment credential authorizes its official service")
			check(chat.get_ai_configuration().credential_source == "openai_environment", "official environment provenance retained")
		edit("APIEndpoint", OS.get_environment("BINDING_ENDPOINT") + "/v1/chat/completions")
		backend.item_selected.emit(0)
		edit("APIModel", "synthetic-model")
	var bound := OS.get_environment("BINDING_CASE") == "godot-bound"
	check((not key.text.is_empty()) == bound, "ambient key only enters explicitly bound custom endpoint")
	if OS.get_environment("BINDING_CASE") in ["godot-unbound", "godot-other"]:
		check(str(chat.get_ai_connection_status().message).contains("GODOT_AI_API_ENDPOINT"), "unbound environment credential explains the repair in connection status")
		check(key.tooltip_text.contains("GODOT_AI_API_ENDPOINT"), "credential settings explain explicit endpoint binding")
	await verify()
	await get_tree().create_timer(1).timeout
	if chat.has_method("get_ai_credential"):
		check((not str(chat.get_ai_credential()).is_empty()) == bound, "native accessor enforces startup provenance")
	# Explicit manual input authorizes this service even if the bytes equal an
	# environment secret. Authorization is provenance, never string inequality.
	edit("APIKey", OS.get_environment("BINDING_SECRET"))
	await verify()
	chat.find_child("ConsultationOnly", true, false).button_pressed = true
	chat.find_child("ChatInput", true, false).text = "SYNTHETIC_CREDENTIAL_REQUEST"
	await wait_send_ready()
	chat.find_child("Send", true, false).pressed.emit()
	await get_tree().create_timer(0.8).timeout
	var endpoint := OS.get_environment("BINDING_ENDPOINT")
	edit("APIEndpoint", endpoint + "/other/chat/completions")
	check(key.text.is_empty(), "endpoint mutation clears manually bound key")
	await verify()
	await get_tree().create_timer(1).timeout
	edit("APIKey", OS.get_environment("BINDING_SECRET"))
	await verify()
	edit("APIEndpoint", endpoint + "/silent/chat/completions", false)
	if chat.has_method("get_ai_credential"):
		check(str(chat.get_ai_credential()).is_empty(), "silent endpoint mutation cannot bypass request accessor")
	await verify()
	edit("APIEndpoint", endpoint + "/v1/chat/completions")
	if chat.has_method("restore_ai_credential"):
		check(not chat.restore_ai_credential(OS.get_environment("BINDING_SECRET"), endpoint + "/other/chat/completions"), "restore rejects stale expected endpoint")
		check(chat.restore_ai_credential(OS.get_environment("BINDING_SECRET"), endpoint + "/v1/chat/completions"), "restore accepts current endpoint")
		check(chat.get_ai_configuration().credential_source == "saved", "restore retains explicit saved provenance")
		check(not chat.restore_ai_credential("replacement", endpoint + "/v1/chat/completions"), "restore does not overwrite current bound credential")
	await verify()
	# Mutate the endpoint while a synthetic response is delayed. Its tool round
	# must not carry the frozen request key to the replacement service.
	settings.find_child("AllowTools", true, false).button_pressed = true
	chat.find_child("ChatInput", true, false).text = "SYNTHETIC_CONTINUATION_REQUEST"
	await wait_send_ready()
	chat.find_child("Send", true, false).pressed.emit()
	await get_tree().create_timer(0.15).timeout
	edit("APIEndpoint", endpoint + "/continuation-other/chat/completions", false)
	await get_tree().create_timer(1).timeout
	edit("APIEndpoint", endpoint + "/v1/chat/completions")
	if chat.has_method("restore_ai_credential"):
		chat.restore_ai_credential(OS.get_environment("BINDING_SECRET"), endpoint + "/v1/chat/completions")
	# Exercise the real issue-worker constructor with fixture-only local identity.
	# Opening an empty canvas preview creates a worker without issue/API operations.
	var editor_settings := EditorInterface.get_editor_settings()
	var workspace := ProjectSettings.globalize_path("res://").trim_suffix("/")
	editor_settings.set_setting("gonggong/workspace", workspace)
	editor_settings.set_project_metadata("daqian_access", workspace.sha256_text(), {"actor":{"repo_id":"fixture", "user_id":"fixture", "repo":"fixture/local"}})
	chat.open_daqian_chat("canvas_route_credential_fixture", 0, "", "", true, {}, true, "", false, true)
	var worker = chat.find_child("ParallelIssueChat", true, false)
	check(worker != null, "real child worker instantiated without external authorization or API calls")
	if worker != null and worker.has_method("get_ai_credential"):
		check(worker.get_ai_credential() == chat.get_ai_credential(), "child copies current credential and audience")
		check(worker.get_ai_configuration().credential_source == "saved", "child preserves credential provenance")
		var worker_endpoint = worker.get_ai_settings_control().find_child("APIEndpoint", true, false)
		worker_endpoint.text = endpoint + "/worker-other/chat/completions"
		check(str(worker.get_ai_credential()).is_empty(), "child silent endpoint mutation invalidates copied key")
		worker.verify_ai_connection()
		await get_tree().create_timer(0.3).timeout
		# At dispatch the child refreshes both endpoint and credential from its owner.
		edit("APIEndpoint", endpoint + "/parent-other/chat/completions")
		worker.find_child("ConsultationOnly", true, false).button_pressed = true
		worker.find_child("ChatInput", true, false).text = "SYNTHETIC_CHILD_CREDENTIAL_REQUEST"
		worker.find_child("Send", true, false).pressed.emit()
		await get_tree().create_timer(0.6).timeout
		check(str(worker.get_ai_credential()).is_empty(), "child start cannot resurrect invalidated owner credential")
	var report := {"passed":failures.is_empty(), "checks":checks, "failures":failures}
	FileAccess.open(OS.get_environment("BINDING_REPORT"), FileAccess.WRITE).store_string(JSON.stringify(report))
	get_tree().root.propagate_notification(NOTIFICATION_WM_CLOSE_REQUEST)
