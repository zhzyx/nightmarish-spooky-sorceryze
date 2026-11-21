@tool
extends VBoxContainer
# The existing JSON contract stays authoritative; widgets update individual keys.
const HUMANOID_RIG = "humanoid_rig"
const HUMAN_SHAPE = "human_shape_adjust"
const DECIMALS = ["denoise", "mesh_threshold", "height_m", "head_ratio", "arm_length_scale", "leg_length_scale", "build"]
const DEFAULTS = {"prompt":"", "seed":0, "width":512, "height":512, "height_m":1.8, "head_ratio":7.5, "arm_length_scale":1.0, "leg_length_scale":1.0, "build":0.0, "steps":1, "denoise":0.65, "mesh_steps":20, "mesh_resolution":512, "octree_resolution":128, "mesh_algorithm":"surface net", "mesh_threshold":0.6}
const NUMBERS = {
	"width":["图像宽度",64,1024,8], "height":["图像高度",64,1024,8], "height_m":["目标身高（米）",0.2,4.0,0.01],
	"head_ratio":["目标头身比",3.0,12.0,0.1], "arm_length_scale":["臂长倍率",0.75,1.35,0.01],
	"leg_length_scale":["腿长倍率",0.75,1.35,0.01], "build":["胖瘦（-1 至 1）",-1.0,1.0,0.05],
	"seed":["随机种子",0,9007199254740991,1], "steps":["图像采样步数",1,8,1],
	"denoise":["重绘强度",0.01,0.99,0.01], "mesh_steps":["网格采样步数",1,50,1],
	"mesh_resolution":["网格分辨率",1,4096,1], "octree_resolution":["几何细节分辨率",16,256,1],
	"mesh_threshold":["表面提取阈值",-1,1,0.01]
}
var raw_edit: TextEdit
var prompt_edit: TextEdit
var outputs_edit: TextEdit
var landmarks_edit: TextEdit
var landmarks_label: Label
var pose_row: HBoxContainer
var pose_edit: OptionButton
var advanced_toggle: Button
var advanced_box: VBoxContainer
var developer_box: VBoxContainer
var developer_toggle: Button
var error_label: Label
var copy_hint: Label
var cli_hint: Label
var controls: Dictionary = {}
var rows: Dictionary = {}
var kind = "copy"
var _loading = false
var _developer = false
var _display_text: Dictionary = {}
var _shown_prompt = ""
var _dirty_numbers: Dictionary = {}
var _dirty_outputs = false
var _automatic_outputs = false
var _cli_mode = false
var _sculpt_mode = false
var _kimi_mode = false
var _api_mode = false

func _init():
	name = "GenerationParameterForm"
	var prompt_label = Label.new()
	prompt_label.text = "提示词"
	add_child(prompt_label)
	rows.prompt = prompt_label
	prompt_edit = TextEdit.new()
	prompt_edit.placeholder_text = "描述生成内容、风格和约束（请勿填写凭据）"
	prompt_edit.custom_minimum_size.y = 100
	prompt_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	add_child(prompt_edit)
	prompt_edit.text_changed.connect(func(): _set_parameter("prompt", prompt_edit.text))
	var outputs_label = Label.new()
	outputs_label.text = "输出数量，或每行一个视角／变体标签"
	add_child(outputs_label)
	rows.outputs = outputs_label
	outputs_edit = TextEdit.new()
	outputs_edit.name = "ImageOutputSpecifications"
	outputs_edit.placeholder_text = "例如：2\n或：\n正面\n三分之四侧面"
	outputs_edit.tooltip_text = "每张图独立生成、校验和预览；多视图拼板不算多张输出。最多 8 张。"
	outputs_edit.custom_minimum_size.y = 65
	add_child(outputs_edit)
	outputs_edit.text_changed.connect(_update_output_specs)
	copy_hint = Label.new()
	copy_hint.text = "直接预览输入图像或模型，无需生成参数。"
	copy_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(copy_hint)
	cli_hint = Label.new()
	cli_hint.text = 'CLI 图像按提示词及参考图生成；尺寸为目标要求，会采用支持的接近尺寸。图像不使用本机模型的随机种子、采样步数或重绘强度。'
	cli_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cli_hint.hide()
	add_child(cli_hint)
	for key in ["width", "height", "height_m", "head_ratio", "arm_length_scale", "leg_length_scale", "build"]: _number_field(self, key)
	pose_row = HBoxContainer.new()
	var pose_label = Label.new()
	pose_label.text = "参考姿态（AINative 自动校验）"
	pose_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pose_row.add_child(pose_label)
	pose_edit = OptionButton.new()
	pose_edit.add_item("T 姿")
	pose_edit.set_item_metadata(0, "T")
	pose_edit.add_item("A 姿")
	pose_edit.set_item_metadata(1, "A")
	pose_row.add_child(pose_edit)
	add_child(pose_row)
	pose_edit.item_selected.connect(func(index): _set_parameter("reference_pose", pose_edit.get_item_metadata(index)))
	landmarks_label = Label.new()
	landmarks_label.text = "人体关键点 JSON（AINative 自动校验源哈希、左右侧与解剖顺序）"
	landmarks_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(landmarks_label)
	landmarks_edit = TextEdit.new()
	landmarks_edit.name = "HumanShapeLandmarks"
	landmarks_edit.custom_minimum_size.y = 180
	landmarks_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	landmarks_edit.placeholder_text = '{"source_sha256":"源 GLB 的 SHA-256","head_top":[x,y,z],"chin":[x,y,z],"neck":[x,y,z],"shoulder_l":[x,y,z],"elbow_l":[x,y,z],"wrist_l":[x,y,z],"shoulder_r":[x,y,z],"elbow_r":[x,y,z],"wrist_r":[x,y,z],"hip_l":[x,y,z],"knee_l":[x,y,z],"ankle_l":[x,y,z],"hip_r":[x,y,z],"knee_r":[x,y,z],"ankle_r":[x,y,z]}'
	add_child(landmarks_edit)
	landmarks_edit.text_changed.connect(_landmarks_changed)
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
	if input.has_method("set_custom_arrow_round"):
		input.set_custom_arrow_round(false)
	if input.has_method("set_format"):
		input.set_format("%s" if key in DECIMALS else "%.0f")
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

func _output_specifications(parameters: Dictionary):
	var count = parameters.get("output_count", 1)
	var labels = parameters.get("output_labels", [])
	var valid = count is int or (count is float and count == floor(count))
	if not valid or count < 1 or count > 8 or not labels is Array:
		return null
	var normalized: Array = []
	for label in labels:
		if not label is String or label.strip_edges() != label or label.is_empty() or label.length() > 80 or normalized.has(label):
			return null
		normalized.append(label)
	if not normalized.is_empty() and normalized.size() != count: return null
	return {"count":int(count), "labels":normalized}

func _update_output_specs():
	if _loading or _automatic_outputs or not kind in ["generate_image", "text_to_image", "image_to_image"]: return
	var content = outputs_edit.text.strip_edges()
	var count = 1
	var labels: Array = []
	if content.is_valid_int():
		count = content.to_int()
	elif not content.is_empty():
		for item in content.split("\n", false):
			var label = item.strip_edges()
			if not label.is_empty(): labels.append(label)
		count = labels.size()
	_dirty_outputs = _output_specifications({"output_count":count, "output_labels":labels}) == null
	if _dirty_outputs:
		_set_error("请输入 1～8 的输出数量，或每行一个非空且不重复的视角／变体标签")
		return
	_set_parameter("output_count", count)
	_set_parameter("output_labels", labels)

func _landmarks_changed():
	if _loading or kind != HUMAN_SHAPE: return
	var json = JSON.new()
	if json.parse(landmarks_edit.text) != OK or not json.data is Dictionary:
		_set_error("人体关键点必须是有效 JSON 对象")
		return
	_set_parameter("landmarks", json.data)

func configure(node_kind: String, parameters: Dictionary, node_version: String = ""):
	kind = node_kind
	# Migrate the short-lived manual checkbox without asking users to edit JSON.
	if kind == HUMAN_SHAPE and parameters.has("confirmed"): parameters.erase("confirmed")
	_automatic_outputs = node_version == "4" or (kind == "generate_image" and node_version == "2")
	_loading = true
	raw_edit.text = JSON.stringify(parameters, "", true, true)
	_loading = false
	advanced_toggle.set_pressed_no_signal(false)
	advanced_box.hide()
	developer_toggle.set_pressed_no_signal(false)
	raw_edit.hide()
	var generator = kind != "copy" and kind != HUMANOID_RIG
	var shape = kind == HUMAN_SHAPE
	# Image-to-Mesh is deliberately image-only. Do not expose a hidden text
	# requirement which the direct 3D service cannot consume with an image.
	var image_stage = generator and not shape
	var prompt_stage = generator and kind != "image_to_mesh" and not shape
	rows.prompt.text = "提示词（无图片时必填）" if kind == "generate_image" else "提示词"
	rows.prompt.visible = prompt_stage
	prompt_edit.visible = prompt_stage
	rows.outputs.text = "图片数量、视角与局部细节由描述自动理解；多图从同一主图衍生" if _automatic_outputs else "输出数量，或每行一个视角／变体标签"
	rows.outputs.visible = kind in ["generate_image", "text_to_image", "image_to_image"]
	outputs_edit.visible = rows.outputs.visible and not _automatic_outputs
	copy_hint.visible = not generator
	copy_hint.text = "使用现有解剖模板生成 17 根骨骼＋独立 root，自动检查蒙皮和抬臂／下蹲／转身；双击角色生成物可继续调整。" if kind == HUMANOID_RIG else "直接预览输入图像或模型，无需生成参数。"
	advanced_toggle.visible = generator and not shape
	rows.width.visible = image_stage
	rows.height.visible = image_stage
	rows.height_m.visible = kind == HUMANOID_RIG or shape
	for key in ["head_ratio", "arm_length_scale", "leg_length_scale", "build"]:
		rows[key].visible = shape
	pose_row.visible = false
	landmarks_label.visible = false
	landmarks_edit.visible = false
	rows.seed.visible = generator and not shape
	rows.steps.visible = image_stage
	rows.denoise.visible = kind in ["generate_image", "image_to_image", "image_to_mesh"]
	for key in ["mesh_steps", "mesh_resolution", "octree_resolution", "mesh_threshold", "mesh_algorithm"]:
		rows[key].visible = kind.ends_with("mesh")
	_raw_changed()
	_apply_cli_controls()

func set_cli_mode(enabled: bool):
	_cli_mode = enabled
	_apply_cli_controls()

func set_sculpt_mode(enabled: bool):
	_sculpt_mode = enabled
	_apply_cli_controls()

func set_api_mode(enabled: bool):
	_api_mode = enabled
	_apply_cli_controls()

func set_kimi_mode(enabled: bool):
	_kimi_mode = enabled
	_apply_cli_controls()

func _kimi_image_mode() -> bool:
	return _kimi_mode and kind in ['generate_image', 'text_to_image', 'image_to_image']

func _is_mesh_kind(value: String) -> bool:
	return value in ['text_to_mesh', 'image_to_mesh', 'model_adjust', HUMAN_SHAPE]

func _apply_cli_controls():
	if kind == HUMANOID_RIG:
		cli_hint.hide()
		advanced_toggle.hide()
		advanced_box.hide()
		rows.height_m.show()
		return
	if kind == HUMAN_SHAPE:
		cli_hint.text = '常规流程只需五项体态参数。AINative 默认渲染源 GLB，使用 Kimi 视觉估计 T／A 姿态和 15 个人体关键点，自动写入源 SHA-256 并做网格几何校验；不调用 Tripo 生成。此步骤需要可用的 KIMI_API_KEY，输出后仍需重新审核和绑骨。开发者 JSON 可显式覆盖 landmarks。'
		cli_hint.show()
		advanced_toggle.hide()
		advanced_box.hide()
		for key in ['width', 'height', 'seed', 'steps', 'denoise', 'mesh_steps', 'mesh_resolution', 'octree_resolution', 'mesh_threshold', 'mesh_algorithm']:
			rows[key].hide()
		rows.height_m.show()
		for key in ['head_ratio', 'arm_length_scale', 'leg_length_scale', 'build']:
			rows[key].show()
		pose_row.hide()
		landmarks_label.hide()
		landmarks_edit.hide()
		return
	var generator = kind != 'copy'
	var instruction_mode = _api_mode or _kimi_mode
	var modeling_mesh = instruction_mode and _is_mesh_kind(kind)
	for key in ['width', 'height']:
		controls[key].custom_arrow_step = 16 if _kimi_image_mode() else 8
		controls[key].max_value = 3840 if _kimi_image_mode() else NUMBERS[key][2]
	if _kimi_image_mode():
		var parameters = _parse_raw()
		if parameters is Dictionary and (not parameters.has('width') or not parameters.has('height')):
			parameters['width'] = int(parameters.get('width', 1024))
			parameters['height'] = int(parameters.get('height', 1024))
			_loading = true
			raw_edit.text = JSON.stringify(parameters, '', true, true)
			_loading = false
			_raw_changed()
	cli_hint.visible = (_cli_mode or instruction_mode) and generator
	cli_hint.text = ('自选 API 返回严格规划，' + ('Blender' if _sculpt_mode else 'Godot') + ' 固定构造器生成网格；请预览检查形态与隐藏面。') if _api_mode else 'Kimi Work 独立图像服务根据提示词与可选参考图生成二维图片；下方宽高是实际请求尺寸，须为 16 的倍数。随机种子、采样步数和 denoise 不适用，不是 K3.1 Pro 直接输出图片。' if _kimi_image_mode() else 'Kimi Work 通过 Tripo API 根据描述、单图或 2–4 视图直接生成 GLB，无需 Blender 或 K3 原语规划；三视图整图按正面／右侧／背面裁切，额外图文混合约束会明确拒绝。' if _kimi_mode else 'CLI 图像按提示词及参考图生成；尺寸为目标要求，会采用支持的接近尺寸。图像不使用本机模型的随机种子、采样步数或重绘强度。'
	if kind == 'image_to_mesh': cli_hint.text = '图生网格只提交源图和参考视角，不接收额外文字要求；生成后请预览检查形态与隐藏面。'
	elif kind == 'model_adjust': cli_hint.text = '默认通过 Tripo API texture_3d_model 输出新 GLB；开发者 JSON 也可选择受限本地几何修复。原模型必须提供且不会被覆盖；四图引导需包含全部视角。'
	rows.prompt.text = '微调要求（可选）' if kind == 'model_adjust' else ('生图要求（无图片时必填）' if kind == 'generate_image' else '图生图要求' if _kimi_image_mode() and kind == 'image_to_image' else '生图要求' if _kimi_image_mode() else '建模要求' if modeling_mesh else '提示词')
	for key in ['width', 'height']:
		rows[key].visible = generator and not modeling_mesh
	for key in ['mesh_steps', 'mesh_resolution', 'octree_resolution', 'mesh_threshold', 'mesh_algorithm']:
		rows[key].visible = _is_mesh_kind(kind) and not instruction_mode
	rows.seed.visible = generator and not instruction_mode and (not _cli_mode or _is_mesh_kind(kind))
	rows.seed.get_child(0).text = '网格随机种子' if _cli_mode and _is_mesh_kind(kind) else '随机种子'
	rows.steps.visible = generator and not _cli_mode and not instruction_mode
	rows.denoise.visible = not _cli_mode and not instruction_mode and kind in ['generate_image', 'image_to_image', 'image_to_mesh']
	advanced_toggle.visible = generator and not instruction_mode and (not _cli_mode or _is_mesh_kind(kind))
	if not advanced_toggle.visible: advanced_box.hide()

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
	_dirty_outputs = false
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
				controls[key].get_line_edit().text = JSON.stringify(value, "", true, true) if key in DECIMALS else str(int(value))
			else:
				controls[key].get_line_edit().text = str(value)
			_display_text[key] = controls[key].get_line_edit().text
	var algorithm = str(parameters.get("mesh_algorithm", DEFAULTS.mesh_algorithm))
	controls.mesh_algorithm.select(0 if algorithm == "surface net" else 1 if algorithm == "basic" else -1)
	if kind == HUMAN_SHAPE:
		var landmark_text = JSON.stringify(parameters.get("landmarks", {}), "  ", true, true)
		if landmarks_edit.text != landmark_text: landmarks_edit.text = landmark_text
		pose_edit.select(1 if parameters.get("reference_pose", "T") == "A" else 0)
	var specifications = _output_specifications(parameters)
	if not _automatic_outputs and specifications != null and kind in ["generate_image", "text_to_image", "image_to_image"]:
		outputs_edit.text = "\n".join(specifications.labels) if not specifications.labels.is_empty() else str(specifications.count)
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
	if kind == "image_to_mesh": result["prompt"] = ""
	if not _automatic_outputs and kind in ["generate_image", "text_to_image", "image_to_image"]:
		if _dirty_outputs or _output_specifications(result) == null:
			_set_error("输出数量须为 1～8 的整数；每行一个非空、不重复且不超过 80 字的标签")
			return null
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
			elif _kimi_image_mode() and key in ['width', 'height']: valid = valid and value >= 64 and value <= 3840
			else: valid = valid and value >= spec[1] and value <= spec[2]
		if valid and key not in DECIMALS: valid = value == floor(value)
		if valid and key in ["width", "height"]: valid = int(value) % (16 if _kimi_image_mode() else 8) == 0
		if not valid:
			_set_error(str(spec[0]) + "超出允许范围，或数值格式无效")
			return null
	if kind == HUMAN_SHAPE and result.has("landmarks"):
		if result.get("reference_pose", "") not in ["T", "A"]:
			_set_error("手动关键点覆盖需要明确的 T 或 A 参考姿态")
			return null
		var landmarks = result.get("landmarks", {})
		var source_sha = str(landmarks.get("source_sha256", "")) if landmarks is Dictionary else ""
		if not landmarks is Dictionary or landmarks.size() != 16 or source_sha.length() != 64 or not source_sha.is_valid_hex_number(false):
			_set_error("关键点须包含源 GLB 的 64 位 SHA-256 和 15 个人体坐标")
			return null
		for name in ["head_top", "chin", "neck", "shoulder_l", "elbow_l", "wrist_l", "shoulder_r", "elbow_r", "wrist_r", "hip_l", "knee_l", "ankle_l", "hip_r", "knee_r", "ankle_r"]:
			var point = landmarks.get(name, [])
			if not point is Array or point.size() != 3:
				_set_error("缺少有效人体关键点：" + name)
				return null
			for component in point:
				if not (component is float or component is int) or component is bool or not is_finite(component):
					_set_error("人体关键点必须是有限数值：" + name)
					return null
	if _kimi_image_mode():
		var pixels = int(result.get('width', 1024)) * int(result.get('height', 1024))
		var shortest = mini(int(result.get('width', 1024)), int(result.get('height', 1024)))
		var longest = maxi(int(result.get('width', 1024)), int(result.get('height', 1024)))
		if pixels < 655360 or pixels > 8294400 or longest > shortest * 3:
			_set_error('Kimi Work 图像总像素须在 655360～8294400 之间，宽高比不得超过 3:1')
			return null
	if result.has("mesh_algorithm") and result.mesh_algorithm not in ["surface net", "basic"]:
		_set_error("请选择支持的表面提取方式")
		return null
	_set_error("")
	return result
