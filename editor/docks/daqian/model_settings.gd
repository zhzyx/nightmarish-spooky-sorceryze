@tool
extends AcceptDialog

signal catalog_changed
signal access_denied(root: String, user: String, reason: String)
signal access_requested
const PROVIDERS := ["Claude", "DeepSeek", "Gemini", "GPT", "自定义兼容端点"]
const PROTOCOLS := ["anthropic-messages","chat-completions","gemini-generate-content","responses","chat-completions"]
const ENDPOINTS := ["https://api.anthropic.com/v1/messages","https://api.deepseek.com/chat/completions",
	"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent","https://api.openai.com/v1/responses",""]

var connect_local: Button
var provider: OptionButton
var account_name: LineEdit
var model: LineEdit
var url: LineEdit
var key: LineEdit
var info: Label
var pending := false
var editor_session := ""
var user_id := ""
var chat: Control
var settings_control: VBoxContainer
var embedded_save: Button
var access_button: Button
var embedded := false
var authorized_root := ""
var authorized_workflow_python := ""
var context_generation := 0
var last_result: Dictionary = {}
var operation_pid := -1
var operation_serial := 0
var process_stopper: Callable


func _ready() -> void:
	title = "接入模型"
	dialog_hide_on_ok = false
	get_ok_button().text = "保存到个人模型库"
	embedded = bool(get_meta("unified_settings", false))
	var fields := VBoxContainer.new()
	settings_control = fields
	fields.name = "PersonalModelSettings"
	fields.custom_minimum_size.x = 440
	add_child(fields)
	if embedded:
		access_button = Button.new()
		access_button.text = "核对身份并接入模型库"
		access_button.name = "AuthorizePersonalModels"
		access_button.pressed.connect(func(): access_requested.emit())
		fields.add_child(access_button)
	provider = OptionButton.new()
	for label in PROVIDERS:
		provider.add_item(label)
	connect_local = Button.new()
	connect_local.name = "ConnectLocalModels"
	connect_local.text = "一键识别并接入本地模型"
	connect_local.tooltip_text = "读取本机 Codex、CodeBuddy 型号和已配置的供应商环境变量"
	connect_local.pressed.connect(_connect_local)
	fields.add_child(connect_local)
	fields.add_child(provider)
	account_name = _field(fields,"配置名称")
	model = _field(fields,"准确的模型 ID")
	url = _field(fields,"API 接口地址")
	key = _field(fields,"API 密钥 · 由本机系统凭据存储保管")
	key.secret = true
	info = Label.new()
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(info)
	if embedded:
		embedded_save = Button.new()
		embedded_save.name = "SavePersonalModel"
		embedded_save.text = "保存到个人模型库"
		embedded_save.pressed.connect(_save_profile)
		fields.add_child(embedded_save)
		fields.visibility_changed.connect(func():
			if not fields.is_visible_in_tree(): key.clear())
	provider.item_selected.connect(_provider_selected)
	confirmed.connect(_save_profile)
	visibility_changed.connect(func():
		if not visible:
			key.clear())
	_provider_selected(0)
	_update_controls()
	if embedded: info.text = "先核对当前工作区身份。模型识别会验证文本回复，只有点击后执行。"


func get_settings_control() -> Control:
	return settings_control


func authorize_embedded(root: String) -> void:
	authorized_root = root
	var runtime: Dictionary = chat.get_runtime_configuration().get("executables", {}) if is_instance_valid(chat) and chat.has_method("get_runtime_configuration") else {}
	authorized_workflow_python = str(runtime.get("workflow_python", ""))
	context_generation += 1
	_update_controls()
	info.text = "身份已核对，可添加模型或识别本机模型。"


func clear_embedded_access() -> void:
	authorized_root = ""
	authorized_workflow_python = ""
	user_id = ""
	context_generation += 1
	if is_instance_valid(key): key.clear()
	_update_controls()


func _update_controls() -> void:
	var disabled := pending or (embedded and (authorized_root.is_empty() or user_id.is_empty()))
	if is_instance_valid(connect_local): connect_local.disabled = disabled
	if is_instance_valid(provider): provider.disabled = disabled
	for field in [account_name, model, url, key]:
		if is_instance_valid(field): field.editable = not disabled
	if is_instance_valid(embedded_save): embedded_save.disabled = disabled
	if is_instance_valid(access_button): access_button.disabled = pending
	get_ok_button().disabled = disabled


func _field(box: VBoxContainer, placeholder: String) -> LineEdit:
	var control := LineEdit.new()
	control.placeholder_text = placeholder
	box.add_child(control)
	return control


func _provider_selected(index: int) -> void:
	account_name.text = PROVIDERS[index]
	url.text = ENDPOINTS[index]
	key.clear()


func _save_profile() -> void:
	if model.text.strip_edges().is_empty() or key.text.is_empty():
		info.text = "请填写模型 ID 和密钥"
		return
	var profile := {"name":account_name.text.strip_edges(),"model":model.text.strip_edges(),"endpoint":url.text.strip_edges(),
		"protocol":PROTOCOLS[provider.selected]}
	_run("add", {"profile":profile, "secret":key.text})


func _connect_local() -> void:
	if pending:
		return
	last_result = {"status":"needs_configuration", "message":"模型设置尚未准备完成，请检查配置。"}
	var local := {}
	# Model choices belong to this project; executable paths remain host-owned.
	if is_instance_valid(chat) and chat.has_method("get_ai_configuration"):
		var configuration: Dictionary = chat.get_ai_configuration()
		for field in ["backend", "model", "endpoint", "cli_model", "codex_model", "cli_entry"]:
			local[field] = str(configuration.get(field, ""))
	# Executable paths are filled from the effective runtime by _run.
	if local.get("backend") in ["0", "3"] and is_instance_valid(chat):
		local.editor_key = str(chat.get_ai_credential())
	await _run("connect-local", local)


func _run(action: String, input: Dictionary) -> void:
	if pending:
		return
	last_result = {"status":"needs_configuration", "message":"请核对工作区身份与模型运行环境。"}
	var root: String = str(chat.get_production_workspace()) if is_instance_valid(chat) else ""
	var host_root: String = str(chat.get_installed_host_root()) if is_instance_valid(chat) else ""
	if embedded and (authorized_root != root or user_id.is_empty()):
		clear_embedded_access()
		info.text = "工作区或身份已改变，请重新核对模型库访问身份。"
		return
	var configuration: Dictionary = chat.prepare_runtime_configuration() if is_instance_valid(chat) else {}
	var runtime: Dictionary = configuration.get("executables", {})
	var python: String = str(runtime.get("workflow_python", ""))
	if embedded and python != authorized_workflow_python:
		clear_embedded_access()
		info.text = "工作流运行环境已改变，请重新核对模型库访问身份。"
		return
	if action == "connect-local":
		input.cli_node = str(runtime.get("node", ""))
		input.codex_entry = str(runtime.get("codex", ""))
	var entry := host_root.path_join("customizations/components/godot-host/daqian/models_cli.py")
	if not root.is_absolute_path() or not host_root.is_absolute_path() or not FileAccess.file_exists(entry):
		info.text = "请核对当前项目和编辑器安装中的天枢模型接入"
		return
	if python.is_empty():
		info.text = "请配置有效的工作流 Python 路径"
		return
	var user := user_id
	var generation := context_generation
	var process := OS.execute_with_pipe(python,[entry,action,root,user,editor_session],false)
	if process.is_empty():
		info.text = "无法启动凭据存储接入"
		return
	pending = true
	operation_serial += 1
	var operation := operation_serial
	operation_pid = int(process.pid)
	_update_controls()
	var pipe: FileAccess = process.stdio
	pipe.store_line(JSON.stringify(input))
	pipe.flush()
	if action == "add":
		key.clear()
	info.text = "正在识别本机模型，并验证文本回复…" if action == "connect-local" else "正在写入系统凭据存储…"
	var data := PackedByteArray()
	var deadline := Time.get_ticks_msec() + 180_000
	var timed_out := false
	while operation == operation_serial and OS.is_process_running(process.pid):
		if pipe.get_length() > 0:
			data.append_array(pipe.get_buffer(mini(pipe.get_length(), 1_048_576)))
		var errors: FileAccess = process.get("stderr")
		if errors and errors.get_length() > 0:
			errors.get_buffer(mini(errors.get_length(), 1_048_576))
		if Time.get_ticks_msec() >= deadline or data.size() > 1_048_576:
			timed_out = true
			_stop_process(process.pid)
			break
		await get_tree().create_timer(0.1).timeout
	if operation != operation_serial:
		return
	operation_pid = -1
	if pipe.get_length() > 0:
		data.append_array(pipe.get_buffer(mini(pipe.get_length(), 1_048_576)))
	var result = JSON.parse_string(data.get_string_from_utf8())
	pending = false
	_update_controls()
	if timed_out:
		last_result = {"status":"timeout", "message":"模型库刷新超时，请检查网络后重试。"}
		info.text = last_result.message
		return
	var current_root: String = str(chat.get_production_workspace()) if is_instance_valid(chat) else ""
	var current_host: String = str(chat.get_installed_host_root()) if is_instance_valid(chat) else ""
	var current_runtime: Dictionary = chat.get_runtime_configuration().get("executables", {}) if is_instance_valid(chat) else {}
	if embedded and (generation != context_generation or authorized_root != root or current_root != root or current_host != host_root or runtime != current_runtime):
		last_result = {"status":"changed", "message":"配置已变化，请重新检查。"}
		clear_embedded_access()
		info.text = "设置上下文已改变，旧接入回执已保留，不应用到当前工作区。"
		return
	if result is Dictionary and result.get("denied",false):
		last_result = {"status":"denied", "message":"模型库身份核验未通过。"}
		access_denied.emit(root,user,str(result.error))
		return
	if result is Dictionary and result.has("result"):
		if action == "connect-local":
			var lines := PackedStringArray()
			for source in result.result:
				var line := "%s · 新接入 %d，已有 %d" % [source.name, source.added, source.existing]
				var names := PackedStringArray(source.get("models", []).slice(0, 3))
				if not names.is_empty():
					line += "（" + "、".join(names) + ("…" if source.models.size() > names.size() else "") + "）"
				if not str(source.note).is_empty():
					line += " · " + str(source.note)
				lines.append(line)
			info.text = "\n".join(lines)
			last_result = {"status":"refreshed", "message":"已刷新天枢模型发现结果，请在个人模型库查看各来源详情。"}
			catalog_changed.emit()
			return
		info.text = "已保存，能力由宿主的评测证据决定"
		catalog_changed.emit()
		hide()
	else:
		last_result = {"status":"unavailable", "message":"模型库刷新未成功，请检查配置与网络。"}
		info.text = str(result.get("error","系统凭据存储未返回成功")) if result is Dictionary else "系统凭据存储未返回有效回执"


func _stop_process(pid: int) -> void:
	if process_stopper.is_valid():
		process_stopper.call(pid)
	elif OS.is_process_running(pid):
		OS.kill(pid)


func cancel_operation(expected_serial := -1) -> void:
	if expected_serial >= 0 and expected_serial != operation_serial:
		return
	operation_serial += 1
	if operation_pid > 0 and OS.is_process_running(operation_pid):
		_stop_process(operation_pid)
	operation_pid = -1
	pending = false
	last_result = {"status":"cancelled", "message":"模型库刷新已取消。"}
	_update_controls()


func _exit_tree() -> void:
	cancel_operation()
