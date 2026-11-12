@tool
extends Node

var helper_source := ""
var test_helper_source := "" # Explicit isolated transport; native credentials stay disabled headless.
var metadata_saver: Callable
var chat: Node
var remember: CheckBox
var forget: Button
var history: Label
var key_field: LineEdit
var message := "Git、天枢和 CLI 沿用本机已有登录，无需重复输入。"
var busy := false
var clearing := false
var epoch := 0
var process: Dictionary = {}
var restored_binding := ""
var managed_secret_hash := ""
var saved_signature := ""


func _ready() -> void:
	chat = get_tree().root.find_child("AI Chat", true, false)
	if not is_instance_valid(chat): return
	var settings: Control = chat.get_ai_settings_control()
	key_field = settings.find_child("APIKey", true, false) as LineEdit
	if not is_instance_valid(key_field): return
	var box := key_field.get_parent()
	remember = CheckBox.new()
	remember.name = "RememberAIConnection"
	remember.text = "记住已验证的连接（密钥保存在本机系统凭据库）"
	remember.clip_text = true
	remember.tooltip_text = remember.text
	remember.button_pressed = bool(_get_record("enabled", true))
	remember.toggled.connect(_toggle_remember)
	box.add_child(remember)
	history = Label.new()
	history.name = "LastAIConnection"
	history.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(history)
	forget = Button.new()
	forget.name = "ForgetAIConnections"
	forget.text = "清除本项目保存的连接记录"
	forget.pressed.connect(clear_saved)
	box.add_child(forget)
	chat.connect("ai_connection_status_changed", _connection_changed)
	chat.connect("ai_configuration_changed", _configuration_changed)
	_render()


func _get_record(key: String, fallback: Variant) -> Variant:
	return EditorInterface.get_editor_settings().get_project_metadata("ai_connection_memory", key, fallback)


func _set_record(key: String, value: Variant) -> void:
	var settings := EditorInterface.get_editor_settings()
	settings.set_project_metadata("ai_connection_memory", key, value)
	if metadata_saver.is_valid(): metadata_saver.call()


func _binding() -> String:
	var config: Dictionary = chat.get_ai_configuration()
	return JSON.stringify([ProjectSettings.globalize_path("res://").simplify_path(), int(config.get("backend", 0)), str(config.get("endpoint", "")).strip_edges()]).sha256_text()


func _signature() -> String:
	return JSON.stringify(chat.get_ai_configuration()) + ":" + key_field.text.sha256_text()


func _render() -> void:
	if not is_instance_valid(history): return
	var last: Dictionary = _get_record("last_used", {})
	var prefix := "尚无已验证的使用记录。"
	if not last.is_empty():
		prefix = "上次使用：%s · %s\n%s" % [str(last.get("backend", "")), str(last.get("model", "")), str(last.get("time", ""))]
	history.text = prefix + "\n" + message
	forget.disabled = clearing
	remember.disabled = clearing


func _configuration_changed() -> void:
	# Never carry a restored credential to another endpoint. Fresh manual input wins.
	if not restored_binding.is_empty() and restored_binding != _binding():
		var previous_hash := managed_secret_hash
		restored_binding = ""
		managed_secret_hash = ""
		if not previous_hash.is_empty() and key_field.text.sha256_text() == previous_hash:
			key_field.text = ""
			key_field.text_changed.emit("")
		message = "接口已切换，请验证当前连接；不会沿用其他接口的密钥。"
		_render()


func _toggle_remember(enabled: bool) -> void:
	epoch += 1
	_set_record("enabled", enabled)
	if not enabled:
		await clear_saved()
	else:
		message = "连接验证成功后会自动记住；下次启动恢复并重新核验。"
		_render()
		_connection_changed()


func restore() -> void:
	if not is_instance_valid(key_field) or not remember.button_pressed or clearing: return
	var config: Dictionary = chat.get_ai_configuration()
	if int(config.get("backend", 0)) in [1, 2] or not key_field.text.is_empty(): return
	var account := _binding()
	var records: Dictionary = _get_record("accounts", {})
	if not records.has(account): return
	var token := epoch
	var signature := _signature()
	while busy:
		await get_tree().process_frame
		if token != epoch or signature != _signature(): return
	message = "正在恢复上次保存的连接…"
	_render()
	var result := await _request({"action":"load", "account":account})
	if token != epoch or clearing or not remember.button_pressed or signature != _signature(): return
	if result.get("status") == "loaded" and result.get("secret") is String and not str(result.secret).is_empty():
		restored_binding = account
		managed_secret_hash = str(result.secret).sha256_text()
		key_field.text = result.secret
		key_field.text_changed.emit(key_field.text)
		message = "已恢复上次保存的密钥，正在等待当前连接验证。"
	else:
		message = "保存的密钥缺失或系统凭据库不可用，请重新输入；原登录记录仍保留。"
	result.clear()
	_render()


func _connection_changed() -> void:
	if DisplayServer.get_name() == "headless": return
	if not is_instance_valid(key_field) or clearing: return
	if str(chat.get_ai_connection_status().get("state", "")) != "available": return
	_remember_verified()


func _remember_verified() -> void:
	var token := epoch
	var signature := _signature()
	while busy:
		await get_tree().process_frame
		if token != epoch or signature != _signature() or clearing: return
	if signature == saved_signature or str(chat.get_ai_connection_status().get("state", "")) != "available": return
	var config: Dictionary = chat.get_ai_configuration()
	var backend := int(config.get("backend", 0))
	if not remember.button_pressed: return
	var model_key := "cli_model" if backend == 1 else ("codex_model" if backend == 2 else "model")
	_set_record("last_used", {"time":Time.get_datetime_string_from_system(false, true), "backend":["API", "CodeBuddy", "Codex", "API"][clampi(backend, 0, 3)], "model":str(config.get(model_key, ""))})
	if backend in [1, 2] or key_field.text.is_empty():
		saved_signature = signature
		message = "已记住使用记录；登录由原 CLI 或本机凭据管理器保管。"
		_render()
		return
	var account := _binding()
	# Record the handle before writing so interrupted saves can still be deleted.
	var records: Dictionary = _get_record("accounts", {})
	records[account] = true
	_set_record("accounts", records)
	restored_binding = account
	managed_secret_hash = key_field.text.sha256_text()
	var result := await _request({"action":"save", "account":account, "secret":key_field.text})
	if token != epoch or signature != _signature() or clearing: return
	if result.get("status") == "saved":
		saved_signature = signature
		restored_binding = account
		managed_secret_hash = key_field.text.sha256_text()
		message = "已安全记住此连接，下次启动无需重复填写密钥。"
	else:
		message = "系统凭据库不可用，密钥仅用于本次会话；修复后重新验证即可保存。"
	_render()


func clear_saved() -> void:
	if clearing: return
	clearing = true
	epoch += 1
	saved_signature = ""
	remember.set_pressed_no_signal(false)
	_set_record("enabled", false)
	_set_record("last_used", {})
	message = "正在清除保存记录…"
	_render()
	# Serialize behind a save: deleting first could let that save recreate a key.
	while busy:
		await get_tree().process_frame
	var records: Dictionary = _get_record("accounts", {})
	for account in records.keys():
		var result := await _request({"action":"delete", "account":account})
		if result.get("status") in ["deleted", "missing"]:
			records.erase(account)
			_set_record("accounts", records)
	clearing = false
	message = "已清除保存记录，下次启动不会恢复。当前会话可继续使用。" if records.is_empty() else "已关闭自动恢复；系统凭据库暂不可用，部分密钥未删除，请再次清除。"
	_render()


func _request(request: Dictionary) -> Dictionary:
	var source := test_helper_source if DisplayServer.get_name() == "headless" else helper_source
	if source.is_empty(): return {"status":"unavailable"}
	busy = true
	var runtime: Dictionary = chat.get_runtime_configuration().get("executables", {})
	var python := str(runtime.get("workflow_python", ""))
	if python.is_empty():
		busy = false
		return {"status":"unavailable"}
	process = OS.execute_with_pipe(python, ["-c", source], false)
	if process.is_empty():
		busy = false
		return {"status":"unavailable"}
	var current := process
	current.stdio.store_line(JSON.stringify(request))
	current.stdio.flush()
	request.clear()
	var output := PackedByteArray()
	var deadline := Time.get_ticks_msec() + 10_000
	var failed := false
	while OS.is_process_running(current.pid):
		var count := mini(current.stdio.get_length(), 16384)
		if count > 0: output.append_array(current.stdio.get_buffer(count))
		var errors := mini(current.stderr.get_length(), 16384)
		if errors > 0: current.stderr.get_buffer(errors)
		if output.size() > 16384 or Time.get_ticks_msec() >= deadline:
			OS.kill(current.pid)
			failed = true
			break
		await get_tree().create_timer(0.03).timeout
	var remaining: int = current.stdio.get_length()
	if remaining + output.size() <= 16384:
		output.append_array(current.stdio.get_buffer(remaining))
	else:
		failed = true
	current.stdio.close()
	current.stderr.close()
	process = {}
	busy = false
	var parser := JSON.new()
	if not failed and parser.parse(output.get_string_from_utf8()) == OK and parser.data is Dictionary:
		return parser.data
	return {"status":"unavailable"}


func _exit_tree() -> void:
	epoch += 1
	if not process.is_empty():
		OS.kill(process.pid)
		process.stdio.close()
		process.stderr.close()
	process = {}
