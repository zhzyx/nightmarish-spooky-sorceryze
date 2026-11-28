@tool
extends EditorDock

const Landform = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_landform.gd")
const Preview = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_preview.gd")
const Apply = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_apply.gd")
const Planner = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_ai.gd")

const Layout = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout.gd")
const Builder = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_terrain_builder.gd")
const LayoutMap = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout_map.gd")
const Expedition = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_expedition.gd")

const Fieldcraft = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_fieldcraft.gd")

var current_layout_button:Button
var offline_button:Button
var shaping:=VBoxContainer.new()
var river_scale:=SpinBox.new()
var road_scale:=SpinBox.new()
var rise_scale:=SpinBox.new()
var sightline:=CheckBox.new()
var shape_button:Button
var layout_map := LayoutMap.new()
var layout_toggle: Button
var layout_ai: Button
var play_button: Button
var layout_picker := EditorFileDialog.new()
var worker: Thread
var building := {}
var plugin: EditorPlugin
var prompt := TextEdit.new()
var image_mode := OptionButton.new()
var image_label := Label.new()
var image_guide: Image
var span_input := SpinBox.new()
var relief_input := SpinBox.new()
var seed_input := SpinBox.new()
var center_x := SpinBox.new()
var center_z := SpinBox.new()
var preview := Preview.new()
var planner := Planner.new()
var gallery := OptionButton.new()
var status := Label.new()
var metrics := Label.new()
var placeholder := Label.new()
var file_picker := EditorFileDialog.new()
var confirm := ConfirmationDialog.new()
var apply_button: Button
var new_scene_button: Button
var ai_button: Button
var cancel_button: Button
var candidates: Array[Dictionary] = []
var sequence := 0
var pending_ai := {}
var pending_apply := {}
var opening := false

func _init() -> void:
	name = "Yugong"
	title = "愚公"
	layout_key = "YugongMainScreen"
	default_slot = EditorDock.DOCK_SLOT_MAIN_SCREEN
	available_layouts = EditorDock.DOCK_LAYOUT_MAIN_SCREEN
	icon_name = &"Terrain3D"

func _ready() -> void:
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	add_child(margin)
	var split := HSplitContainer.new()
	margin.add_child(split)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.x = 320
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	split.add_child(scroll)
	var inputs := VBoxContainer.new()
	inputs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inputs.add_theme_constant_override("separation", 9)
	scroll.add_child(inputs)
	var heading := _label(inputs, "愚公 · 地形草案")
	heading.add_theme_font_size_override("font_size", 22)
	_label(inputs, "地形描述")
	prompt.placeholder_text = Layout.EXAMPLE
	prompt.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	prompt.custom_minimum_size.y = 84
	inputs.add_child(prompt)
	offline_button=_button(inputs,"本地生成可玩地形",generate_offline)
	offline_button.tooltip_text="离线解读方位、河流、道路与地标；拖动布局或调整整形参数后可直接试玩。"
	var layout_row := HBoxContainer.new()
	inputs.add_child(layout_row)
	layout_ai = _button(layout_row, "Astra 自由布局", func(): generate_ai(true))
	_button(layout_row, "金岬示例", generate_example)
	_button(inputs,"复制轻量模型指令",copy_intent_brief)
	var saved_row:=HBoxContainer.new()
	inputs.add_child(saved_row)
	current_layout_button=_button(saved_row,"载入当前场景布局",load_current_layout)
	_button(saved_row, "打开布局文件…", func(): layout_picker.popup_centered_ratio(.65))
	_label(inputs, "图像输入")
	for caption in ["布局草图 · 红山脊 / 蓝河谷 / 绿平地", "灰度高度图 · 白高黑低", "地貌参考图 · AI 解读"]:
		image_mode.add_item(caption)
	inputs.add_child(image_mode)
	var image_row := HBoxContainer.new()
	inputs.add_child(image_row)
	_button(image_row, "选择图片…", func(): file_picker.popup_centered_ratio(0.68))
	_button(image_row, "清除", func(): image_guide = null; image_label.text = "未选择图片")
	image_label.text = "未选择图片"
	image_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	inputs.add_child(image_label)
	_spin(inputs, "地形宽度（米）", span_input, 64, 4096, 512)
	_spin(inputs, "最大起伏（米）", relief_input, 1, 1200, 120)
	_spin(inputs, "生成种子", seed_input, 0, 2147483646, 42)
	var buttons := HBoxContainer.new()
	inputs.add_child(buttons)
	_button(buttons, "本地高度草案", generate_local)
	ai_button = _button(buttons, "AI 解读并生成", generate_ai)
	ai_button.tooltip_text = "使用本机已登录的 Codex CLI；描述与选作地貌参考的图片将发送给模型。"
	cancel_button = _button(inputs, "取消 AI 任务", _cancel_ai)
	cancel_button.hide()
	inputs.add_child(shaping)
	_label(shaping,"当前布局整形")
	_spin(shaping,"河床宽度（%）",river_scale,60,160,100)
	_spin(shaping,"古道宽度（%）",road_scale,60,160,100)
	_spin(shaping,"台地抬升（%）",rise_scale,60,160,100)
	sightline.text="保持出生点至地标的视线"
	shaping.add_child(sightline)
	shape_button=_button(shaping,"按当前布局重新整形",reshape)
	shaping.hide()
	var results := VBoxContainer.new()
	results.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	results.add_theme_constant_override("separation", 8)
	split.add_child(results)
	var bar := HBoxContainer.new()
	results.add_child(bar)
	_label(bar, "地形预览")
	gallery.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gallery.disabled = true
	bar.add_child(gallery)
	layout_toggle = _button(bar, "查看三维地形", toggle_layout)
	layout_toggle.hide()
	_button(bar, "换种子生成", _variation)
	var canvas := PanelContainer.new()
	canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas.custom_minimum_size = Vector2(240, 170)
	results.add_child(canvas)
	canvas.add_child(preview)
	layout_map.custom_minimum_size=Vector2(220,160)
	canvas.add_child(layout_map)
	layout_map.hide()
	layout_map.edited.connect(rebuild_layout)
	layout_map.edit_rejected.connect(func(reason:String): status.text=reason)
	placeholder.text = "输入描述或选择布局图，生成第一版可旋转的地形。"
	placeholder.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	placeholder.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	placeholder.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	placeholder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(placeholder)
	results.add_child(metrics)
	var center_row := HBoxContainer.new()
	results.add_child(center_row)
	_label(center_row, "已有地形覆盖中心（米）")
	_spin(center_row, "X", center_x, -999999, 999999, 0)
	_spin(center_row, "Z", center_z, -999999, 999999, 0)
	var publish := HBoxContainer.new()
	results.add_child(publish)
	apply_button = _button(publish, "应用到当前场景", _apply_current)
	new_scene_button = _button(publish, "另建地形场景", _create_scene)
	apply_button.disabled = true
	new_scene_button.disabled = true
	play_button = _button(publish, "生成场景并试玩", func(): _create_scene(true))
	play_button.hide()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	results.add_child(status)
	file_picker.file_mode = EditorFileDialog.FILE_MODE_OPEN_FILE
	file_picker.access = EditorFileDialog.ACCESS_FILESYSTEM
	file_picker.filters = PackedStringArray(["*.png,*.jpg,*.jpeg,*.webp,*.exr ; 地形输入图像"])
	add_child(file_picker)
	file_picker.file_selected.connect(load_guide)
	layout_picker.file_mode=EditorFileDialog.FILE_MODE_OPEN_FILE
	layout_picker.access=EditorFileDialog.ACCESS_FILESYSTEM
	layout_picker.filters=PackedStringArray(["*.json ; 愚公布局"])
	add_child(layout_picker)
	layout_picker.file_selected.connect(load_layout)
	set_process(false)
	add_child(confirm)
	confirm.title = "应用地形高度"
	confirm.confirmed.connect(_confirm_apply)
	confirm.canceled.connect(func(): pending_apply.clear())
	add_child(planner)
	planner.finished.connect(_ai_finished)
	gallery.item_selected.connect(show_candidate)
	var settings := EditorInterface.get_editor_settings()
	if not settings.has_setting("yugong/codex_executable"):
		settings.set_setting("yugong/codex_executable", "")
	settings.add_property_info({"name": "yugong/codex_executable", "type": TYPE_STRING, "hint": PROPERTY_HINT_GLOBAL_FILE})

func _label(parent: Control, caption: String) -> Label:
	var label := Label.new()
	label.text = caption
	parent.add_child(label)
	return label

func _button(parent: Control, caption: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = caption
	parent.add_child(button)
	button.pressed.connect(callback)
	return button

func _spin(parent: Control, caption: String, input: SpinBox, minimum: int, maximum: int, initial: int) -> void:
	var row := HBoxContainer.new()
	parent.add_child(row)
	var label := _label(row, caption)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.min_value = minimum
	input.max_value = maximum
	input.value = initial
	row.add_child(input)

func load_guide(path: String) -> void:
	var picture := Image.load_from_file(path)
	if picture == null or picture.is_empty():
		status.text = "无法读取图片，请检查文件格式。"
		return
	image_guide = picture
	image_label.text = path.get_file() + " · %d × %d" % [picture.get_width(), picture.get_height()]

func _inputs() -> Dictionary:
	return {"description": prompt.text.strip_edges(), "image": image_guide, "image_name": image_label.text, "mode": image_mode.selected,
		"span": span_input.value, "relief": relief_input.value, "seed": int(seed_input.value)}

func copy_intent_brief() -> void:
	var instruction:=Fieldcraft.MODEL_BRIEF
	if not prompt.text.strip_edges().is_empty():
		instruction+="\n地形描述："+prompt.text.strip_edges()
	DisplayServer.clipboard_set(instruction)
	status.text="已复制。把模型返回的 JSON 粘入地形描述，点「本地生成可玩地形」。"

func generate_offline() -> void:
	if worker or not pending_ai.is_empty():return
	var inputs:=_inputs()
	if inputs.image!=null:
		status.text="离线布局使用文字。使用图片请选高度草案或 Astra 参考图布局。"
		return
	if inputs.span<256:
		status.text="可玩地形宽度至少 256 米。"
		return
	if inputs.description.is_empty():
		status.text="输入出生点、地标或河谷的描述，也可以直接打开金岬示例。"
		return
	var plan:=Fieldcraft.compile_layout(inputs.description,inputs.seed)
	if plan.has("error"):
		status.text=plan.error
		return
	build_layout(inputs,plan,"本地规则")

func reshape() -> void:
	if worker or not pending_ai.is_empty() or candidates.is_empty():return
	var current:=candidates[gallery.selected]
	if not current.has("layout"):return
	var plan:Dictionary=current.layout.duplicate(true)
	plan.operations={"river_width":river_scale.value,"road_width":road_scale.value,
		"plateau_rise":rise_scale.value,"sightline":sightline.button_pressed}
	if plan==current.layout:
		status.text="这些整形参数已应用到当前候选。"
		return
	build_layout(current,plan,"局部整形")

func generate_local() -> void:
	if worker or not pending_ai.is_empty():return
	var inputs := _inputs()
	if inputs.description.is_empty() and inputs.image == null:
		status.text = "请输入描述或选择一张图片。"
		return
	if inputs.image != null and inputs.mode == Landform.Guide.REFERENCE:
		status.text = "地貌参考图请点「AI 解读并生成」。布局图和高度图支持本地生成。"
		return
	_generate(inputs, Landform.local_recipe(inputs.description), "本地")

func generate_ai(playable := false) -> void:
	var inputs := _inputs()
	if inputs.description.is_empty() and inputs.image == null:
		status.text = "请输入描述或选择一张图片。"
		return
	if not pending_ai.is_empty() or worker != null: return
	if playable and inputs.span < 256:
		status.text = "可玩场景宽度至少 256 米，请调整地形宽度。"
		return
	if playable and inputs.image != null and inputs.mode != Landform.Guide.REFERENCE:
		status.text = "可玩布局支持地貌参考图。要使用布局草图或灰度图，请生成高度草案。"
		return
	pending_ai = inputs
	pending_ai.playable = playable
	offline_button.disabled=true
	layout_ai.disabled = true
	ai_button.disabled = true
	cancel_button.show()
	status.text = "正在解读地形意图…"
	planner.start(inputs.description, inputs.image if inputs.mode == Landform.Guide.REFERENCE else null, inputs.span, inputs.relief, playable)

func _cancel_ai() -> void:
	offline_button.disabled=false
	layout_ai.disabled = false
	planner.cancel()
	pending_ai.clear()
	ai_button.disabled = false
	cancel_button.hide()
	status.text = "已取消，现有候选可继续使用。"

func _ai_finished(recipe: Dictionary, error: String) -> void:
	offline_button.disabled=false
	layout_ai.disabled = false
	ai_button.disabled = false
	cancel_button.hide()
	var inputs := pending_ai
	pending_ai = {}
	if not error.is_empty():
		status.text = error
	elif inputs.get("playable",false):
		build_layout(inputs,recipe,"Astra High")
	elif not inputs.is_empty():
		_generate(inputs, recipe, "AI")

func _variation() -> void:
	if worker or not pending_ai.is_empty():return
	if candidates.is_empty():
		seed_input.value += 1
		generate_local()
		return
	var previous := candidates[gallery.selected]
	if previous.image != null and previous.mode == Landform.Guide.HEIGHT:
		status.text = "灰度高度图固定了每个采样的高度。调整起伏后可生成新版本。"
		return
	var next := previous.duplicate()
	next.seed = (int(previous.seed) + 1) % 2147483647
	seed_input.value = next.seed
	if previous.has("layout"): build_layout(next,previous.layout,previous.source)
	else: _generate(next, previous.recipe, previous.source)

func _generate(inputs: Dictionary, recipe: Dictionary, source: String) -> void:
	var height := Landform.build(recipe, inputs.seed, inputs.relief, inputs.image, inputs.mode)
	var candidate := inputs.duplicate()
	candidate.merge({"height": height, "recipe": recipe, "source": source}, true)
	var kind: String = "高度图" if inputs.image != null and inputs.mode == Landform.Guide.HEIGHT else Landform.TITLES[Landform.SHAPES.find(recipe.shape)]
	add_candidate(candidate,kind)

func add_candidate(candidate: Dictionary, kind: String) -> void:
	sequence += 1
	if candidates.size() >= 8:
		candidates.pop_front()
		gallery.remove_item(0)
	candidates.append(candidate)
	gallery.add_item("%02d   %s · %s · 种子 %d" % [sequence, kind, candidate.source, candidate.seed])
	gallery.disabled = false
	gallery.select(gallery.item_count - 1)
	show_candidate(gallery.selected)
	status.text = "候选已生成。选定版本后可应用，场景中的手工修改暂时保留。"

func show_candidate(index: int) -> void:
	var candidate := candidates[index]
	prompt.text = candidate.description
	image_guide = candidate.image
	image_mode.select(candidate.mode)
	image_label.text = candidate.image_name
	span_input.value = candidate.span
	relief_input.value = candidate.relief
	seed_input.value = candidate.seed
	placeholder.hide()
	preview.display_height(candidate.height, candidate.span, candidate.relief, candidate.get("geography",{}).get("control"))
	metrics.text = "%d × %d 米    高度差 %.1f 米    ·    拖动旋转，滚轮缩放" % [candidate.span, candidate.span, preview.extent]
	apply_button.disabled = false
	new_scene_button.disabled = false
	var playable:=candidate.has("layout")
	shaping.visible=playable
	layout_toggle.visible=playable
	layout_map.visible=playable
	preview.visible=not playable
	play_button.visible=playable
	if playable:
		var ops:Dictionary=candidate.layout.get("operations",Fieldcraft.DEFAULTS)
		river_scale.value=ops.river_width
		road_scale.value=ops.road_width
		rise_scale.value=ops.plateau_rise
		sightline.button_pressed=candidate.layout.has("operations") and ops.sightline
		layout_map.set_plan(candidate.layout,candidate.height)
		layout_toggle.text="查看三维地形"
		layout_metrics()

func _apply_current() -> void:
	if worker or candidates.is_empty():return
	var root := EditorInterface.get_edited_scene_root()
	if root == null:
		_create_scene()
		return
	var terrain: Terrain3D
	for selected in EditorInterface.get_selection().get_selected_nodes():
		if selected is Terrain3D:
			if terrain != null:
				status.text = "请选择一块 Terrain3D 作为应用目标。"
				return
			terrain = selected
	if terrain == null:
		var terrains := root.find_children("*", "Terrain3D", true, false)
		if root is Terrain3D:
			terrains.push_front(root)
		if terrains.size() > 1:
			status.text = "场景内有多块地形，请先在 3D 视图选中目标。"
			return
		if terrains.size() == 1:
			terrain = terrains.front()
	var candidate := candidates[gallery.selected]
	if terrain == null:
		_attach(root, candidate, Apply.new_directory())
		return
	var center := Vector2(center_x.value, center_z.value)
	pending_apply = {"target": terrain, "root": root, "center": center, "candidate": candidate}
	confirm.dialog_text = "将替换 %s 上以 (%.0f, %.0f) 为中心、宽 %.0f 米范围内的高度。材质和洞口保留，可撤销本次应用。" % [terrain.name, center.x, center.y, candidate.span]
	confirm.popup_centered()

func _confirm_apply() -> void:
	var pending := pending_apply
	pending_apply = {}
	if pending.is_empty() or not is_instance_valid(pending.target) or EditorInterface.get_edited_scene_root() != pending.root or not pending.target.is_inside_tree():
		status.text = "场景已切换，请重新选择目标。"
		return
	var candidate: Dictionary = pending.candidate
	var error := Apply.apply_patch(plugin.get_undo_redo(), pending.target, candidate.height, candidate.span, pending.center)
	if error.is_empty():
		_edit_terrain(pending.target)
	else:
		status.text = error

func _create_scene(play_now := false) -> void:
	if opening or worker or candidates.is_empty():
		return
	var folder := Apply.new_directory()
	if folder.is_empty():
		status.text = "无法在项目中创建输出目录。"
		return
	var candidate := candidates[gallery.selected]
	var root := Node3D.new()
	root.name = "YugongLandscape"
	var camera := Camera3D.new()
	camera.name = "Overview"
	var target := Vector3(0, candidate.relief * 0.32, 0)
	var eye := target + Vector3(0.75, 0.88, 1.0) * maxf(candidate.span, candidate.relief)
	camera.transform = Transform3D(Basis.looking_at(target - eye), eye)
	camera.far = maxf(1000.0, eye.length() * 3)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("#566c7c")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.55
	camera.environment = environment
	root.add_child(camera)
	camera.owner = root
	var light := DirectionalLight3D.new()
	light.name = "Sun"
	light.rotation_degrees = Vector3(-48, -35, 0)
	root.add_child(light)
	light.owner = root
	if candidate.has("layout"):
		environment.background_mode=Environment.BG_SKY
		var sky:=Sky.new()
		var atmosphere:=ProceduralSkyMaterial.new()
		atmosphere.ground_bottom_color=Color("#676f70")
		atmosphere.ground_horizon_color=Color("#b8c7c5")
		atmosphere.sky_horizon_color=atmosphere.ground_horizon_color
		sky.sky_material=atmosphere
		camera.projection=Camera3D.PROJECTION_ORTHOGONAL
		camera.size=candidate.span*1.02
		environment.sky=sky
		light.shadow_enabled=true
		if not Expedition.populate(root,candidate,folder):
			root.free()
			status.text="无法保存可玩场景的运行资源。"
			return
	var packed := PackedScene.new()
	var error := packed.pack(root)
	root.free()
	var path := folder.path_join("Landscape.tscn")
	if error != OK or ResourceSaver.save(packed, path) != OK:
		status.text = "无法写入新地形场景。"
		return
	opening = true
	EditorInterface.open_scene_from_path(path)
	for frame in 180:
		root = EditorInterface.get_edited_scene_root() as Node3D
		if root != null and root.scene_file_path == path:
			if not _attach(root, candidate, folder):
				opening = false
				return
			EditorInterface.save_scene_as(path, false)
			var saved := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
			if saved == null or not _contains_terrain(saved):
				status.text = "地形已生成，保存场景失败。"
			elif play_now:
				EditorInterface.play_custom_scene(path)
			opening = false
			return
		await get_tree().process_frame
	opening = false
	status.text = "新场景未能打开，请检查编辑器中的弹窗。"

func _attach(root: Node, candidate: Dictionary, folder: String) -> bool:
	if folder.is_empty():
		status.text = "无法创建地形目录。"
		return false
	var terrain := Apply.add_terrain(plugin.get_undo_redo(), root, candidate.height, candidate.span, folder,candidate.get("geography",{}))
	if terrain == null:
		status.text = "无法写入地形材质资源，请检查输出目录。"
		return false
	_edit_terrain(terrain)
	var bounds: Vector2 = terrain.data.get_height_range()
	plugin.get_meta(&"frame_yugong_terrain").call((bounds.x + bounds.y) * 0.5, maxf(candidate.span, bounds.y - bounds.x))
	return true

func _edit_terrain(terrain: Terrain3D) -> void:
	EditorInterface.set_main_screen_editor("3D")
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(terrain)
	EditorInterface.edit_node(terrain)
	status.text = "已应用。可在 3D 视口雕刻，或使用撤销恢复。"


func _contains_terrain(packed: PackedScene) -> bool:
	var state:=packed.get_state()
	for i in state.get_node_count():
		if state.get_node_type(i)==&"Terrain3D":return true
	return false

func generate_example() -> void:
	if worker != null or not pending_ai.is_empty():return
	var inputs:=_inputs()
	inputs.merge({"description":Layout.EXAMPLE,"span":1536.0,"relief":195.0,"image":null,"image_name":"未选择图片"},true)
	var plan:=Layout.example()
	plan.operations=Fieldcraft.DEFAULTS.duplicate()
	plan.ridge_road="west_road"
	build_layout(inputs,plan,"金岬示例")

func load_current_layout() -> void:
	var scene:=EditorInterface.get_edited_scene_root()
	if scene==null or scene.scene_file_path.is_empty():
		status.text="请先打开愚公生成的地形场景。"
		return
	var path:=scene.scene_file_path.get_base_dir().path_join("layout.json")
	if not FileAccess.file_exists(path):
		status.text="当前场景目录中没有愚公布局，可选择「打开布局文件…」。"
		return
	load_layout(path)

func load_layout(path:String) -> void:
	var obj:Variant=JSON.parse_string(FileAccess.get_file_as_string(path))
	if not obj is Dictionary or obj.get("version")!=Layout.VERSION or not obj.get("layout") is Dictionary or not obj.get("description") is String or not Layout.finite_number(obj.get("span")) or not Layout.finite_number(obj.get("relief")) or not Layout.finite_number(obj.get("seed")):
		status.text="无法读取此版本的愚公布局。"
		return
	if obj.span<256 or obj.span>4096 or obj.relief<1 or obj.relief>1200 or obj.seed<0 or obj.seed>2147483646:
		status.text="布局尺寸、起伏或种子超出范围。"
		return
	var inputs:=_inputs()
	inputs.merge({"origin":str(obj.get("origin","已保存布局")),"description":obj.description,"span":obj.span,"relief":obj.relief,"seed":int(obj.seed),"image":null,"image_name":"未选择图片"},true)
	build_layout(inputs,obj.get("layout",{}),"已保存布局")

func toggle_layout() -> void:
	layout_map.visible=not layout_map.visible
	preview.visible=not layout_map.visible
	layout_toggle.text="查看三维地形" if layout_map.visible else "编辑平面布局"

	layout_metrics()

func layout_metrics() -> void:
	var current:=candidates[gallery.selected]
	var geo:Dictionary=current.geography
	metrics.text=("北朝上 · 蓝线河流 / 金线西路 / 白线东路 / 橙色台地 · 拖点调整" if layout_map.visible else "三维地形 · 拖动旋转 / 滚轮缩放") + "  ·  %d 座桥" % geo.bridges.size()
	metrics.text+="  ·  河宽 %.1f m  /  路宽 %.1f m  /  台地高差 %.1f m" % [2*geo.water_width,2*geo.road_width,geo.goal_y-geo.spawn_y]

func rebuild_layout(plan:Dictionary) -> void:
	if worker!=null:return
	var current:=candidates[gallery.selected]
	build_layout(current,plan,"布局编辑")

func build_layout(inputs:Dictionary, plan:Dictionary, source:String) -> void:
	if worker!=null or not pending_ai.is_empty():return
	var issue:=Layout.error(plan)
	if not issue.is_empty():
		status.text=issue
		return
	building=inputs.duplicate()
	building.layout=plan.duplicate(true)
	building.source=source
	building.origin=inputs.get("origin",source)
	worker=Thread.new()
	if worker.start(Builder.build.bind(building.layout,building.seed,building.span,building.relief))!=OK:
		worker=null
		building={}
		status.text="无法启动地形生成任务。"
		return
	play_button.disabled=true
	apply_button.disabled=true
	new_scene_button.disabled=true
	gallery.disabled=true
	layout_map.mouse_filter=Control.MOUSE_FILTER_IGNORE
	shape_button.disabled=true
	offline_button.disabled=true
	layout_ai.disabled=true
	status.text="正在整形河床、连接道路并烘焙地形…"
	set_process(true)

func _process(_delta:float) -> void:
	if not worker or worker.is_alive():return
	var result:Variant=worker.wait_to_finish()
	worker=null
	set_process(false)
	play_button.disabled=false
	apply_button.disabled=candidates.is_empty()
	new_scene_button.disabled=candidates.is_empty()
	gallery.disabled=candidates.is_empty()
	layout_map.mouse_filter=Control.MOUSE_FILTER_STOP
	shape_button.disabled=false
	offline_button.disabled=false
	layout_ai.disabled=false
	var candidate:=building
	building={}
	if not result is Dictionary or not result.has("height"):
		status.text="地形生成失败。"
		return
	candidate.geography=result
	candidate.height=result.height
	add_candidate(candidate,"可玩地形")

func _exit_tree() -> void:
	if worker:worker.wait_to_finish()
