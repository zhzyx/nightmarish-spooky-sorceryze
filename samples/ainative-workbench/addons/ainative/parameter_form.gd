@tool
extends VBoxContainer
# The existing JSON contract stays authoritative; widgets update individual keys.
const DEFAULTS = {"prompt":"", "seed":0, "width":512, "height":512, "steps":1, "denoise":0.65, "mesh_steps":20, "mesh_resolution":512, "octree_resolution":128, "mesh_algorithm":"surface net", "mesh_threshold":0.6}
const NUMBERS = {
	"width":["图像宽度",64,1024,8], "height":["图像高度",64,1024,8],
	"seed":["随机种子",0,9007199254740991,1], "steps":["图像采样步数",1,8,1],
	"denoise":["重绘强度",0.01,0.99,0.01], "mesh_steps":["网格采样步数",1,50,1],
	"mesh_resolution":["网格分辨率",1,4096,1], "octree_resolution":["几何细节分辨率",16,256,1],
	"mesh_threshold":["表面提取阈值",-1,1,0.01]
}
var raw_edit: TextEdit
var prompt_edit: TextEdit
var advanced_toggle: Button
var advanced_box: VBoxContainer
var developer_box: VBoxContainer
var developer_toggle: Button
var error_label: Label
var copy_hint: Label
var controls: Dictionary = {}
var rows: Dictionary = {}
var kind = "copy"
var _loading = false
var _developer = false
var _display_text: Dictionary = {}
var _shown_prompt = ""
var _dirty_numbers: Dictionary = {}

func _init():
	name = "GenerationParameterForm"
	var prompt_label = Label.new()
	prompt_label.text = "提示词"
	add_child(prompt_label)
	rows.prompt = prompt_label
	prompt_edit = TextEdit.new()
	prompt_edit.placeholder_text = "描述你希望生成的内容"
	prompt_edit.custom_minimum_size.y = 85
	prompt_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	add_child(prompt_edit)
	prompt_edit.text_changed.connect(func(): _set_parameter("prompt", prompt_edit.text))
	copy_hint = Label.new()
	copy_hint.text = "直接预览输入图像或模型，无需生成参数。"
	copy_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(copy_hint)
	for key in ["width", "height"]: _number_field(self, key)
	advanced_toggle = Button.new()
	advanced_toggle.text = "高级生成选项"
	advanced_toggle.toggle_mode = true
	add_child(advanced_toggle)
	advanced_box = VBoxContainer.new()
	add_child(advanced_box)
	advanced_box.hide()
	advanced_toggle.toggled.connect(func(opened): advanced_box.visible = opened and kind != "copy")
	for key in ["seed", "steps", "denoise", "mesh_steps", "mesh_resolution", "octree_resolution", "mesh_threshold"]: _number_field(advanced_box, key)
	var algorithm_row = HBoxContainer.new()
	var algorithm_label = Label.new()
	algorithm_label.text = "表面提取方式"
	algorithm_row.add_child(algorithm_label)
	var algorithm = OptionButton.new()
	algorithm.add_item("曲面网格")
	algorithm.set_item_metadata(0, "surface net")
	algorithm.add_item("基础网格")
	algorithm.set_item_metadata(1, "basic")
	algorithm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	algorithm_row.add_child(algorithm)
	advanced_box.add_child(algorithm_row)
	rows.mesh_algorithm = algorithm_row
	controls.mesh_algorithm = algorithm
	algorithm.item_selected.connect(func(index): _set_parameter("mesh_algorithm", algorithm.get_item_metadata(index)))
	developer_box = VBoxContainer.new()
	add_child(developer_box)
	developer_box.hide()
	developer_toggle = Button.new()
	developer_toggle.text = "原始参数 JSON（开发者）"
	developer_toggle.toggle_mode = true
	developer_box.add_child(developer_toggle)
	raw_edit = TextEdit.new()
	raw_edit.placeholder_text = "原始参数对象"
	raw_edit.custom_minimum_size.y = 85
	developer_box.add_child(raw_edit)
	raw_edit.hide()
	developer_toggle.toggled.connect(func(opened): raw_edit.visible = opened and _developer)
	raw_edit.text_changed.connect(_raw_changed)
	error_label = Label.new()
	error_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(error_label)
	error_label.hide()

func _number_field(parent: Node, key: String):
	var spec: Array = NUMBERS[key]
	var row = HBoxContainer.new()
	var label = Label.new()
	label.text = spec[0]
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	if key == "seed":
		var seed = LineEdit.new()
		seed.placeholder_text = "0"
		seed.custom_minimum_size.x = 140
		row.add_child(seed)
		parent.add_child(row)
		controls[key] = seed
		rows[key] = row
		seed.text_changed.connect(func(value):
			if value.is_valid_int(): _set_parameter("seed", value.to_int())
			else: _set_error("随机种子必须是非负整数")
		)
		return
	var input = SpinBox.new()
	input.min_value = spec[1]
	input.max_value = spec[2]
	input.step = 0
	input.custom_arrow_step = spec[3]
	input.custom_arrow_round = false
	input.format = "%s" if key in ["denoise", "mesh_threshold"] else "%.0f"
	# Imported values must not be silently clamped or rounded before validation.
	input.allow_greater = true
	input.allow_lesser = true
	input.custom_minimum_size.x = 140
	row.add_child(input)
	parent.add_child(row)
	controls[key] = input
	rows[key] = row
	input.value_changed.connect(func(value): _set_parameter(key, value))
	input.get_line_edit().text_changed.connect(func(_text):
		if not _loading: _dirty_numbers[key] = true
	)

func configure(node_kind: String, parameters: Dictionary):
	kind = node_kind
	_loading = true
	raw_edit.text = JSON.stringify(parameters, "", true, true)
	_loading = false
	advanced_toggle.set_pressed_no_signal(false)
	advanced_box.hide()
	developer_toggle.set_pressed_no_signal(false)
	raw_edit.hide()
	var generator = kind != "copy"
	var image_stage = kind in ["text_to_image", "image_to_image", "text_to_mesh"]
	rows.prompt.visible = image_stage
	prompt_edit.visible = image_stage
	copy_hint.visible = not generator
	advanced_toggle.visible = generator
	rows.width.visible = image_stage
	rows.height.visible = image_stage
	rows.seed.visible = generator
	rows.steps.visible = image_stage
	rows.denoise.visible = kind == "image_to_image"
	for key in ["mesh_steps", "mesh_resolution", "octree_resolution", "mesh_threshold", "mesh_algorithm"]:
		rows[key].visible = kind.ends_with("mesh")
	_raw_changed()

func set_developer_mode(enabled: bool):
	_developer = enabled
	developer_box.visible = enabled
	if not enabled:
		developer_toggle.set_pressed_no_signal(false)
		raw_edit.hide()

func _parse_raw():
	var json = JSON.new()
	return json.data if json.parse(raw_edit.text) == OK else null

func _set_error(message: String):
	error_label.text = message
	error_label.visible = not message.is_empty()

func _set_parameter(key: String, value):
	if _loading: return
	var parameters = _parse_raw()
	if not parameters is Dictionary:
		_set_error("请先修正开发者选项中的参数对象")
		return
	parameters[key] = value
	_dirty_numbers.erase(key)
	_loading = true
	raw_edit.text = JSON.stringify(parameters, "", true, true)
	_loading = false
	if key == "prompt": _shown_prompt = prompt_edit.text
	if key == "seed": _display_text.seed = controls.seed.text
	if controls.has(key) and controls[key] is SpinBox:
		_display_text[key] = controls[key].get_line_edit().text
	_set_error("")

func _raw_changed():
	if _loading: return
	var parameters = _parse_raw()
	if not parameters is Dictionary:
		_set_error("参数格式无效，请修正开发者选项中的参数对象")
		return
	_loading = true
	_dirty_numbers.clear()
	var prompt = str(parameters.get("prompt", ""))
	if prompt_edit.text != prompt: prompt_edit.text = prompt
	_shown_prompt = prompt
	for key in NUMBERS:
		var value = parameters.get(key, DEFAULTS[key])
		if key == "seed":
			controls[key].text = str(int(value)) if (value is int or value is float) and is_finite(value) else str(value)
			_display_text[key] = controls[key].text
		else:
			if value is float or value is int:
				controls[key].value = value
				controls[key].get_line_edit().text = JSON.stringify(value, "", true, true) if key in ["denoise", "mesh_threshold"] else str(int(value))
			else:
				controls[key].get_line_edit().text = str(value)
			_display_text[key] = controls[key].get_line_edit().text
	var algorithm = str(parameters.get("mesh_algorithm", DEFAULTS.mesh_algorithm))
	controls.mesh_algorithm.select(0 if algorithm == "surface net" else 1 if algorithm == "basic" else -1)
	_loading = false
	_set_error("")

func parameters():
	if prompt_edit.visible and prompt_edit.text != _shown_prompt:
		_set_parameter("prompt", prompt_edit.text)
	# SpinBox commits typed text on focus loss; apply must also handle keyboard use.
	if rows.seed.visible and controls.seed.text != _display_text.get("seed", controls.seed.text):
		if not controls.seed.text.is_valid_int():
			_set_error("随机种子必须是非负整数")
			return null
		_set_parameter("seed", controls.seed.text.to_int())
	for key in NUMBERS:
		if key == "seed" or not rows[key].visible: continue
		var input: SpinBox = controls[key]
		var draft = input.get_line_edit().text.strip_edges()
		if _dirty_numbers.has(key):
			if not draft.is_valid_float() or not is_finite(draft.to_float()):
				_set_error(NUMBERS[key][0] + "必须是有效数字")
				return null
			_set_parameter(key, draft.to_float())
	var result = _parse_raw()
	if not result is Dictionary:
		_set_error("参数格式无效，请修正开发者选项中的参数对象")
		return null
	if kind == "copy": return result
	if result.has("prompt") and not result.prompt is String:
		_set_error("提示词必须是文字")
		return null
	for key in NUMBERS:
		if not result.has(key): continue
		var value = result[key]
		var spec: Array = NUMBERS[key]
		var valid = (value is float or value is int) and not value is bool
		if valid:
			valid = is_finite(value)
			if key == "denoise": valid = valid and value > 0 and value < 1
			else: valid = valid and value >= spec[1] and value <= spec[2]
		if valid and key not in ["denoise", "mesh_threshold"]: valid = value == floor(value)
		if valid and key in ["width", "height"]: valid = int(value) % 8 == 0
		if not valid:
			_set_error(str(spec[0]) + "超出允许范围，或数值格式无效")
			return null
	if result.has("mesh_algorithm") and result.mesh_algorithm not in ["surface net", "basic"]:
		_set_error("请选择支持的表面提取方式")
		return null
	_set_error("")
	return result
