@tool
extends AcceptDialog

signal catalog_changed
const PROVIDERS := ["Claude", "DeepSeek", "Gemini", "GPT", "自定义兼容端点"]
const PROTOCOLS := ["anthropic-messages","chat-completions","gemini-generate-content","responses","chat-completions"]
const ENDPOINTS := ["https://api.anthropic.com/v1/messages","https://api.deepseek.com/chat/completions",
	"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent","https://api.openai.com/v1/responses",""]

var provider: OptionButton
var account_name: LineEdit
var model: LineEdit
var url: LineEdit
var key: LineEdit
var info: Label
var pending := false


func _ready() -> void:
	title = "添加供应商模型 API"
	dialog_hide_on_ok = false
	get_ok_button().text = "保存到个人模型库"
	var fields := VBoxContainer.new()
	fields.custom_minimum_size.x = 440
	add_child(fields)
	provider = OptionButton.new()
	for label in PROVIDERS:
		provider.add_item(label)
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
	if pending:
		return
	var settings := EditorInterface.get_editor_settings()
	var root: String = str(settings.get_setting("gonggong/workspace")) if settings.has_setting("gonggong/workspace") else ""
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	var entry := root.path_join("customizations/components/godot-host/daqian/models_cli.py")
	if not root.is_absolute_path() or not FileAccess.file_exists(entry):
		info.text = "请绑定包含大千模型接入的共工仓库"
		return
	if model.text.strip_edges().is_empty() or key.text.is_empty():
		info.text = "请填写模型 ID 和密钥"
		return
	var profile := {"name":account_name.text.strip_edges(),"model":model.text.strip_edges(),"endpoint":url.text.strip_edges(),
		"protocol":PROTOCOLS[provider.selected]}
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	var process := OS.execute_with_pipe(python,[entry,"add"],false)
	if process.is_empty():
		info.text = "无法启动凭据存储接入"
		return
	pending = true
	get_ok_button().disabled = true
	var pipe: FileAccess = process.stdio
	pipe.store_line(JSON.stringify({"profile":profile,"secret":key.text}))
	pipe.flush()
	key.clear()
	info.text = "正在写入系统凭据存储…"
	var data := PackedByteArray()
	while OS.is_process_running(process.pid):
		if pipe.get_length()>0:
			data.append_array(pipe.get_buffer(pipe.get_length()))
		await get_tree().create_timer(0.1).timeout
	if pipe.get_length()>0:
		data.append_array(pipe.get_buffer(pipe.get_length()))
	var result = JSON.parse_string(data.get_string_from_utf8())
	pending = false
	get_ok_button().disabled = false
	if result is Dictionary and result.has("result"):
		info.text = "已保存，能力由宿主的评测证据决定"
		catalog_changed.emit()
		hide()
	else:
		info.text = str(result.get("error","系统凭据存储未返回成功")) if result is Dictionary else "系统凭据存储未返回有效回执"
