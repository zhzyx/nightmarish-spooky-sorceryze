@tool
extends AcceptDialog

signal catalog_changed
signal access_denied(root: String, user: String, reason: String)
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


func _ready() -> void:
	title = "接入模型"
	dialog_hide_on_ok = false
	get_ok_button().text = "保存到个人模型库"
	var fields := VBoxContainer.new()
	fields.custom_minimum_size.x = 440
	add_child(fields)
	provider = OptionButton.new()
	for label in PROVIDERS:
		provider.add_item(label)
	connect_local = Button.new()
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
	provider.item_selected.connect(_provider_selected)
	confirmed.connect(_save_profile)
	visibility_changed.connect(func():
		if not visible:
			key.clear())
	_provider_selected(0)


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
	var settings := EditorInterface.get_editor_settings()
	var local := {}
	for field in ["backend", "model", "endpoint", "cli_node", "cli_entry", "cli_model", "codex_entry", "codex_model"]:
		var path: String = "ai_chat/" + field
		if settings.has_setting(path):
			local[field] = str(settings.get_setting(path))
	if local.get("backend") == "0" and is_instance_valid(chat):
		var field := chat.find_child("APIKey", true, false) as LineEdit
		if field:
			var secret := field.text.strip_edges()
			# An ambient OpenAI key belongs only to its own endpoint.
			if secret != OS.get_environment("OPENAI_API_KEY") or local.get("endpoint") == "https://api.openai.com/v1/chat/completions":
				local.editor_key = secret
	_run("connect-local", local)


func _run(action: String, input: Dictionary) -> void:
	if pending:
		return
	var settings := EditorInterface.get_editor_settings()
	var root: String = str(settings.get_setting("gonggong/workspace")) if settings.has_setting("gonggong/workspace") else ""
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	var entry := root.path_join("customizations/components/godot-host/daqian/models_cli.py")
	if not root.is_absolute_path() or not FileAccess.file_exists(entry):
		info.text = "请绑定包含大千模型接入的共工仓库"
		return
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	var user := user_id
	var process := OS.execute_with_pipe(python,[entry,action,root,user,editor_session],false)
	if process.is_empty():
		info.text = "无法启动凭据存储接入"
		return
	pending = true
	connect_local.disabled = true
	get_ok_button().disabled = true
	var pipe: FileAccess = process.stdio
	pipe.store_line(JSON.stringify(input))
	pipe.flush()
	if action == "add":
		key.clear()
	info.text = "正在识别本机模型，并验证文本回复…" if action == "connect-local" else "正在写入系统凭据存储…"
	var data := PackedByteArray()
	while OS.is_process_running(process.pid):
		if pipe.get_length()>0:
			data.append_array(pipe.get_buffer(pipe.get_length()))
		await get_tree().create_timer(0.1).timeout
	if pipe.get_length()>0:
		data.append_array(pipe.get_buffer(pipe.get_length()))
	var result = JSON.parse_string(data.get_string_from_utf8())
	pending = false
	connect_local.disabled = false
	get_ok_button().disabled = false
	if result is Dictionary and result.get("denied",false):
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
			catalog_changed.emit()
			return
		info.text = "已保存，能力由宿主的评测证据决定"
		catalog_changed.emit()
		hide()
	else:
		info.text = str(result.get("error","系统凭据存储未返回成功")) if result is Dictionary else "系统凭据存储未返回有效回执"
