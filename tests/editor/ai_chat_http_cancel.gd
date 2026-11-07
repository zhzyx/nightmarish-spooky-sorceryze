@tool
extends SceneTree

func _refresh_models(chat: Node):
	# A real connection edit now replaces the removed manual refresh action.
	# Normalization retains the fixture credential/executable used on the wire.
	var backend = chat.get_ai_settings_control().find_child("AIBackend", true, false)
	var field = chat.get_environment_settings_control().find_child("CLINode", true, false) if backend.selected in [1, 2] else chat.get_ai_settings_control().find_child("APIKey", true, false)
	field.text = field.text.get_base_dir() + "/./" + field.text.get_file() if backend.selected in [1, 2] else field.text + " "
	var status = chat.get_ai_settings_control().find_child("ModelStatus", true, false)
	var previous_status = status.text
	field.text_changed.emit(field.text)
	var deadline = Time.get_ticks_msec() + 5000
	while not backend.disabled and status.text == previous_status and Time.get_ticks_msec() < deadline:
		await process_frame

var dock: Node
var tracking := false
var last_frame := 0
var max_gap_usec := 0
var manual_started := 0

func _initialize():
	process_frame.connect(_heartbeat)
	_run.call_deferred()

func _heartbeat():
	var now := Time.get_ticks_usec()
	if tracking and last_frame > 0:
		max_gap_usec = maxi(max_gap_usec, now - last_frame)
	last_frame = now

func _text() -> String:
	var result := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		result += label.get_parsed_text()
	return result

func _run():
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(2)
		return
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup != null:
		setup.hide()
	EditorInterface.set_main_screen_editor("AI Chat")
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("CANCEL_ENDPOINT")
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "isolated-fixture-key"
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "fixture"
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
	var mode := OS.get_environment("CANCEL_CASE")
	if mode == "models":
		await _refresh_models(dock)
	else:
		dock.find_child("ChatInput", true, false).text = "DELAYED_RESPONSE_MUST_NOT_APPEAR"
		dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 15000
	while not FileAccess.file_exists("res://server-waiting") and Time.get_ticks_msec() < deadline:
		await process_frame
	if not FileAccess.file_exists("res://server-waiting"):
		push_error("Delayed HTTP handler was not reached")
		quit(2)
		return
	# Give the old worker time to enter its blocking response/header read.
	await create_timer(0.25).timeout
	max_gap_usec = 0
	last_frame = Time.get_ticks_usec()
	tracking = true
	var start := Time.get_ticks_usec()
	var stop = dock.find_child("Stop", true, false)
	var stop_enabled: bool = not stop.disabled
	var manual := OS.get_environment("CANCEL_MANUAL") == "1"
	if manual:
		stop.button_down.connect(func(): manual_started = Time.get_ticks_usec())
		print("HTTP_CANCEL_READY_FOR_NATIVE_CLICK")
		await stop.pressed
		start = manual_started
	else:
		stop.pressed.emit()
	var elapsed := Time.get_ticks_usec() - start
	await process_frame
	await process_frame
	tracking = false
	var report := {"case": mode, "stop_was_enabled": stop_enabled,
		"stop_trigger": "native_button_down_to_pressed_return" if manual else "pressed_signal_callback",
		"stop_call_seconds": elapsed / 1000000.0,
		"max_frame_gap_seconds": max_gap_usec / 1000000.0,
		"stop_disabled_after": stop.disabled,
		"server_released_at_stop_return": FileAccess.file_exists("res://server-released")}
	# A new request must work while the cancelled server request is still delayed.
	max_gap_usec = 0
	last_frame = Time.get_ticks_usec()
	tracking = true
	dock.find_child("ChatInput", true, false).text = "RECOVERY_REQUEST"
	dock.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 10000
	while not "RECOVERY_OK" in _text() and Time.get_ticks_msec() < deadline:
		await process_frame
	report["recovery_received"] = "RECOVERY_OK" in _text()
	report["server_released_at_recovery"] = FileAccess.file_exists("res://server-released")
	if mode == "models":
		while not stop.disabled and Time.get_ticks_msec() < deadline:
			await process_frame
		await _refresh_models(dock)
		deadline = Time.get_ticks_msec() + 10000
		var status = dock.get_ai_settings_control().find_child("ModelStatus", true, false)
		while not "模型列表已获取" in status.text and Time.get_ticks_msec() < deadline:
			await process_frame
		var picker = dock.get_ai_settings_control().find_child("ModelPicker", true, false)
		var found := false
		for index in picker.item_count:
			found = found or "recovered-model" in picker.get_item_text(index)
		report["models_recovered"] = found
	await process_frame
	tracking = false
	report["recovery_max_frame_gap_seconds"] = max_gap_usec / 1000000.0
	deadline = Time.get_ticks_msec() + int(float(OS.get_environment("CANCEL_DELAY")) * 1000) + 3000
	while not FileAccess.file_exists("res://server-released") and Time.get_ticks_msec() < deadline:
		await process_frame
	await create_timer(0.3).timeout
	report["observed_server_release"] = FileAccess.file_exists("res://server-released")
	report["stale_response_absent"] = not "STALE_CANCELLED_REPLY" in _text()
	if mode == "models":
		var picker = dock.get_ai_settings_control().find_child("ModelPicker", true, false)
		var final_models: Array[String] = []
		for index in picker.item_count:
			final_models.append(picker.get_item_text(index))
		report["final_model_list"] = final_models
		report["final_model_selection"] = dock.get_ai_settings_control().find_child("APIModel", true, false).text
		report["late_models_rejected"] = "recovered-model" in final_models and not "stale-model" in final_models and report["final_model_selection"] != "stale-model"
	FileAccess.open("res://cancel-report.json", FileAccess.WRITE).store_string(JSON.stringify(report))
	print("HTTP_CANCEL_REPORT=", JSON.stringify(report))
	quit(0)
