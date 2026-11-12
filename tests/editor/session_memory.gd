@tool
extends Node

var checks: Array = []
var failures: Array = []
var chat
var ai
var memory

func _ready() -> void:
	run.call_deferred()

func check(value: bool, text: String) -> void:
	checks.append(text)
	if not value: failures.append(text)
	print(("PASS " if value else "FAIL ") + text)

func edit(name: String, value: String) -> void:
	var field = ai.find_child(name, true, false)
	field.text = value
	field.text_changed.emit(value)

func verify() -> void:
	chat.verify_ai_connection()
	var deadline := Time.get_ticks_msec() + 8000
	while chat.get_ai_connection_status().state == "checking" and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.025).timeout
	check(chat.get_ai_connection_status().state == "available", "actual loopback verifies the current restored credential")

func run() -> void:
	await get_tree().create_timer(0.8).timeout
	chat = get_tree().root.find_child("AI Chat", true, false)
	memory = get_tree().root.find_child("AIConnectionMemory", true, false)
	check(chat != null and memory != null, "native editor installs connection memory")
	if chat == null or memory == null:
		finish(); return
	ai = chat.get_ai_settings_control()
	memory.test_helper_source = FileAccess.get_file_as_string("res://credential_fixture.py")
	var settings := EditorInterface.get_editor_settings()
	var key = ai.find_child("APIKey", true, false)
	var endpoint := OS.get_environment("MEMORY_ENDPOINT") + "/chat/completions"
	var secret := OS.get_environment("MEMORY_SECRET")
	var stage := OS.get_environment("MEMORY_STAGE")
	check(ai.find_child("RememberAIConnection", true, false) != null and ai.find_child("ForgetAIConnections", true, false) != null, "AI configuration exposes remember and clear controls")
	if stage == "save":
		check(settings.get_project_metadata("ai_connection_memory", "accounts", {}).is_empty(), "fresh project has no credential handles")
		edit("APIEndpoint", endpoint)
		edit("APIModel", "remembered-model")
		edit("APIKey", secret)
		await verify()
		await memory._remember_verified() # Explicit isolated entry; headless never touches native credentials.
		check(memory.message.contains("已安全记住"), "verified API key saved through bounded helper protocol")
		check(settings.get_project_metadata("ai_connection_memory", "accounts", {}).size() == 1, "only a project and endpoint bound handle is persisted")
		check(memory.history.text.contains("remembered-model"), "last verified model and time are visible")
		edit("APIEndpoint", OS.get_environment("MEMORY_ENDPOINT") + "/responses")
		check(chat.get_ai_credential() == secret, "remembered credential survives same-service endpoint protocol switch")
		var backend = ai.find_child("AIBackend", true, false)
		backend.select(3)
		backend.item_selected.emit(3)
		check(chat.get_ai_credential() == secret, "remembered credential survives chat to responses backend switch")
		backend.select(0)
		backend.item_selected.emit(0)
		edit("APIEndpoint", endpoint)
		check(chat.get_ai_credential() == secret, "remembered credential survives responses to chat switch")
		await verify() # Restore available state before exercising a second in-flight save.
		# Forget only in-memory binding to exercise a first save while switching endpoints.
		memory.saved_signature = ""
		memory.restored_binding = ""
		memory.managed_secret_hash = ""
		memory._remember_verified()
		await get_tree().create_timer(0.03).timeout
		edit("APIEndpoint", endpoint + "-other")
		await get_tree().create_timer(0.35).timeout
		check(key.text.is_empty(), "endpoint switch during pending save clears the verified old credential")
		edit("APIEndpoint", endpoint)

		settings.set_project_metadata("startup_checks", "last_run", {"time":"previous-launch", "git":"current", "ai":"available", "catalog":"refreshed"})
	elif stage == "restore":
		check(key.text.is_empty(), "new editor process starts without plaintext key in settings")
		check(ai.find_child("APIModel", true, false).text == "remembered-model", "last selected model survives editor restart")
		check(get_tree().root.find_child("LastStartupChecks", true, false).text.contains("previous-launch"), "previous Git AI check is shown as historical record")
		var test_source: String = memory.test_helper_source
		memory.test_helper_source = ""
		await memory.restore()
		check(key.text.is_empty(), "headless credential transport is disabled without explicit test substitute")
		memory.test_helper_source = test_source
		var controller = get_tree().root.find_child("StartupConfigurationChecks", true, false)
		controller.run_checks()
		await get_tree().create_timer(0.03).timeout
		check(controller.cancel_button.visible and controller.retry.disabled, "credential restore immediately exposes cancel and disables retry")
		controller.cancel_checks()
		await get_tree().create_timer(0.4).timeout
		check(key.text.is_empty(), "cancelled startup discards delayed credential restore")
		await memory.restore()
		check(key.text == secret, "editor restart restores credential from same project and endpoint")
		check(chat.get_ai_connection_status().state != "available", "historical success does not grant current green status")
		await verify()
		edit("APIEndpoint", endpoint + "-other")
		await get_tree().process_frame
		check(key.text.is_empty(), "switching endpoint clears managed credential")
		await memory.restore()
		check(key.text.is_empty(), "different endpoint cannot restore previous credential")
		edit("APIEndpoint", endpoint)
		memory.restore()
		await get_tree().create_timer(0.03).timeout
		edit("APIKey", "manual-replacement")
		await get_tree().create_timer(0.4).timeout
		check(key.text == "manual-replacement", "late credential load preserves newer manual input")
		edit("APIKey", "")
		memory.restore()
		await get_tree().create_timer(0.03).timeout
		edit("APIEndpoint", endpoint + "-other")
		await get_tree().create_timer(0.4).timeout
		check(key.text.is_empty(), "late credential load cannot follow endpoint change")
		edit("APIEndpoint", endpoint)
		var good_helper: String = memory.test_helper_source
		memory.test_helper_source = "import json,sys;sys.stdin.readline();print(json.dumps({'status':'unavailable'}))"
		await memory.restore()
		check(key.text.is_empty() and memory.message.contains("不可用"), "unavailable credential store preserves manual recovery path")
		memory.test_helper_source = good_helper
		await memory.restore()
		await verify()
		memory._remember_verified()
		await get_tree().create_timer(0.03).timeout
		await memory.clear_saved()
		check(not memory.remember.button_pressed, "clear disables automatic restoration")
		check(settings.get_project_metadata("ai_connection_memory", "accounts", {}).is_empty(), "clear serialized after save removes all saved handles")
		check(settings.get_project_metadata("ai_connection_memory", "last_used", {}).is_empty(), "clear removes last use record")
		check(key.text == secret, "clearing saved record keeps current session usable")
	elif stage == "forgotten":
		check(not memory.remember.button_pressed, "remember preference stays disabled after restart")
		await memory.restore()
		check(key.text.is_empty(), "forgotten credential never restores on next launch")
		check(memory.history.text.contains("尚无"), "forgotten history is absent after restart")
	elif stage == "other-project":
		await memory.restore()
		check(key.text.is_empty(), "another project cannot discover saved credentials")
		check(settings.get_project_metadata("ai_connection_memory", "accounts", {}).is_empty(), "credential handles stay isolated per project")
	finish()

func finish() -> void:
	var report := {"checks":checks,"failures":failures,"passed":failures.is_empty()}
	var file := FileAccess.open(OS.get_environment("MEMORY_REPORT"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report)); file.close()
	get_tree().root.propagate_notification(NOTIFICATION_WM_CLOSE_REQUEST)
