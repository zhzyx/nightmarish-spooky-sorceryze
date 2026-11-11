@tool
extends Node

class CatalogFixture extends Node:
	var calls := 0
	var cancelled := false
	func refresh_startup_models() -> Dictionary:
		calls += 1
		await get_tree().create_timer(0.25).timeout
		return {"status":"cancelled" if cancelled else "refreshed", "message":"fixture catalog"}
	func cancel_startup_model_refresh() -> void:
		cancelled = true

@onready var root: Window = get_tree().root
var checks: Array = []
var failures: Array = []
var controller
var chat
var ai

func _ready() -> void:
	run.call_deferred()

func check(value: bool, message: String) -> void:
	checks.append(message)
	if not value: failures.append(message)
	print(("PASS " if value else "FAIL ") + message)

func edit(name: String, value: String) -> void:
	var field = ai.find_child(name, true, false)
	field.text = value
	field.text_changed.emit(value)

func wait_checks() -> void:
	var until := Time.get_ticks_msec() + 15000
	while controller.running and Time.get_ticks_msec() < until:
		await get_tree().create_timer(0.025).timeout
	check(not controller.running, "startup check completes within deadline")

func run() -> void:
	await get_tree().create_timer(1.0).timeout
	controller = root.find_child("StartupConfigurationChecks", true, false)
	chat = root.find_child("AI Chat", true, false)
	check(controller != null and chat != null, "native startup coordinator is installed")
	if controller == null or chat == null:
		finish(); return
	check(not controller.running and not controller.automatic_started, "headless startup does not perform remote checks")
	check(root.find_child("RetryStartupChecks", true, false) != null, "settings exposes retry action")
	check(root.find_child("StartupCheckSummary", true, false) != null, "settings exposes separate status rows")
	var settings_dock = root.find_child("UnifiedSettings", true, false)
	var selected: int = settings_dock.find_child("UnifiedSettingsCategories", true, false).current_tab
	var visible_before: bool = settings_dock.is_visible_in_tree()
	var real_planner = root.find_child("DaqianWorkspace", true, false)
	var missing: Dictionary = await real_planner.refresh_startup_models()
	check(missing.status == "needs_configuration", "missing model workspace yields actionable configuration status")
	check(not real_planner.project_model_connecting, "missing configuration releases model refresh guard")
	var planner := CatalogFixture.new()
	root.add_child(planner)
	controller.planner = planner
	ai = chat.get_ai_settings_control()
	edit("APIEndpoint", OS.get_environment("STARTUP_ENDPOINT") + "/v1/chat/completions")
	edit("APIModel", "startup-model")
	edit("APIKey", OS.get_environment("STARTUP_SECRET"))
	controller.run_checks()
	controller.run_checks()
	check(controller.running and root.find_child("RetryStartupChecks", true, false).disabled, "in-flight check rejects duplicate invocation and disables retry")
	await wait_checks()
	check(planner.calls == 1, "one run refreshes catalog once")
	check(controller.get_status().checks.git.status == "no_repository", "native Git bridge reports non-repository without mutation")
	check(controller.get_status().checks.ai.status == "available", "real loopback API success marks connection available")
	check(controller.get_status().checks.catalog.status == "refreshed", "catalog result is reported independently")
	check(settings_dock.is_visible_in_tree() == visible_before and settings_dock.find_child("UnifiedSettingsCategories", true, false).current_tab == selected, "background check does not navigate settings")
	check(not root.find_child("RetryStartupChecks", true, false).disabled, "completed check re-enables retry")
	edit("APIEndpoint", OS.get_environment("STARTUP_ENDPOINT") + "/fail/chat/completions")
	controller.run_checks()
	await wait_checks()
	check(controller.get_status().checks.ai.status == "unavailable", "API failure is distinct from successful catalog refresh")
	check(controller.get_status().checks.catalog.status == "refreshed", "API failure does not suppress catalog result")
	edit("APIEndpoint", OS.get_environment("STARTUP_ENDPOINT") + "/slow/chat/completions")
	controller.run_checks()
	await get_tree().create_timer(0.05).timeout
	controller.cancel_checks()
	check(not controller.running and planner.cancelled, "cancel stops coordinator and model refresh")
	check(chat.get_ai_connection_status().state != "checking", "cancel stops native AI probe")
	await get_tree().create_timer(1.0).timeout
	check(controller.get_status().checks.ai.status != "available", "late cancelled response cannot restore green")
	planner.cancelled = false
	controller.run_checks()
	await get_tree().create_timer(0.05).timeout
	chat.verify_ai_connection()
	var manual_generation: int = chat.get_ai_connection_status().generation
	controller.cancel_checks()
	check(chat.get_ai_connection_status().state == "checking" and chat.get_ai_connection_status().generation == manual_generation, "cancelling startup preserves newer manual connection probe")
	await get_tree().create_timer(1.0).timeout
	planner.cancelled = false
	edit("APIEndpoint", OS.get_environment("STARTUP_ENDPOINT") + "/v1/chat/completions")
	await controller.run_checks()
	check(controller.get_status().checks.ai.status == "available", "cancelled startup check can be retried")
	edit("APIModel", "changed-model")
	check(controller.get_status().checks.ai.status != "available", "editing configuration revokes startup success summary")
	# Exercise the real native model dialog's await/cancel contract, with a private helper.
	var settings := EditorInterface.get_editor_settings()
	var old_workspace: String = str(settings.get_setting("gonggong/workspace"))
	var model_workspace := OS.get_environment("STARTUP_MODEL_WORKSPACE")
	settings.set_setting("gonggong/workspace", model_workspace)
	real_planner._observe_environment(real_planner._environment_state())
	var catalog = real_planner.models_dialog
	catalog.chat = chat
	catalog.user_id = "fixture-user"
	catalog.authorize_embedded(model_workspace)
	var start := Time.get_ticks_msec()
	await catalog._connect_local()
	check(Time.get_ticks_msec() - start >= 200 and not catalog.pending, "one-click model refresh awaits actual helper completion")
	check(catalog.last_result.status == "refreshed", "real model dialog publishes successful model refresh receipt: " + str(catalog.last_result))
	catalog._connect_local()
	await get_tree().create_timer(0.05).timeout
	real_planner.startup_models_running = true
	real_planner.project_model_connecting = true
	real_planner.startup_model_operation = -1
	real_planner.cancel_startup_model_refresh()
	check(catalog.pending, "cancelling identity stage preserves manual model operation")
	while catalog.pending:
		await get_tree().create_timer(0.05).timeout
	check(catalog.last_result.status == "refreshed", "manual model operation completes after startup cancellation")
	FileAccess.open(model_workspace.path_join("cancel-mode"), FileAccess.WRITE).close()
	catalog._connect_local()
	await get_tree().create_timer(0.15).timeout
	check(catalog.pending, "real model refresh is asynchronous")
	catalog.cancel_operation()
	await get_tree().create_timer(1.0).timeout
	check(not catalog.pending and catalog.last_result.status == "cancelled", "cancelled model refresh cannot apply late helper result")
	check(not FileAccess.file_exists(model_workspace.path_join("descendant-ran")), "model refresh cancellation stops provider descendants")
	catalog.clear_embedded_access()
	settings.set_setting("gonggong/workspace", old_workspace)
	planner.queue_free()
	finish()

func finish() -> void:
	var f := FileAccess.open(OS.get_environment("STARTUP_REPORT"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"passed":failures.is_empty(), "checks":checks, "failures":failures}))
	f.close()
	if failures.is_empty():
		root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	else:
		get_tree().quit(1)
