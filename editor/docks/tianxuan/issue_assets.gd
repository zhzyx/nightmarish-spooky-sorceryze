@tool
extends VBoxContainer
## Native immutable artifact inspection and revision-specific human review.

var controller: Node
var model: Node
var _choices: Array[OptionButton] = []
var _texts: Array[CodeEdit] = []
var _pictures: Array[TextureRect] = []
var _model_panels: Array[VBoxContainer] = []
var _viewports: Array[SubViewport] = []
var _cameras: Array[Camera3D] = []
var _models: Array[Node3D] = []
var _model_keys: Array[String] = []
var _orbits: Array[Vector3] = []
var _bounds: Array[AABB] = []
var _captions: Array[Label] = []
var _columns := BoxContainer.new()
var _upload := FileDialog.new()
var _destination := FileDialog.new()
var _upload_button := Button.new()
var _download_buttons: Array[Button] = []
var _original := CodeEdit.new()
var _save := Button.new()
var _discard := Button.new()
var _note := TextEdit.new()
var _recipients := OptionButton.new()
var _actions := HFlowContainer.new()
var _status := Label.new()
var _dialog := ConfirmationDialog.new()
var _intent := {}
var _download := {}
var _signature := ""
var _scope := ""
var _original_context := ""
var _syncing := false


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.issues
	_upload_button.text = "添加本机附件…"
	_upload_button.name = "NativeIssueUpload"
	_upload_button.pressed.connect(func(): _upload.popup_centered_ratio(0.6))
	add_child(_upload_button)
	_upload.access = FileDialog.ACCESS_FILESYSTEM
	_upload.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_upload.title = "选择工单附件（最大 1 MiB）"
	_upload.file_selected.connect(func(path: String): model.upload_artifact(path))
	add_child(_upload)
	_destination.access = FileDialog.ACCESS_FILESYSTEM
	_destination.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_destination.title = "保存校验过的原件"
	_destination.file_selected.connect(func(path: String):
		if _download.get("scope") == controller.session.scope_key() and _download.get("issue") == model.selected:
			model.download_artifact(_download.reference, path)
	)
	add_child(_destination)
	add_child(_columns)
	_columns.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for index in 2:
		var panel := PanelContainer.new()
		panel.theme_type_variation = "TianxuanCard"
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_columns.add_child(panel)
		var side := VBoxContainer.new()
		panel.add_child(side)
		var choice := OptionButton.new()
		choice.name = "NativeIssueArtifact" + str(index)
		choice.fit_to_longest_item = false
		choice.item_selected.connect(func(_choice: int): _selected(index))
		side.add_child(choice)
		_choices.append(choice)
		var caption := Label.new()
		caption.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
		caption.theme_type_variation = "TianxuanCaption"
		side.add_child(caption)
		_captions.append(caption)
		var picture := TextureRect.new()
		picture.custom_minimum_size.y = 180 * float(get_meta("ui_scale", 1.0))
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		side.add_child(picture)
		_pictures.append(picture)
		_build_model_view(side, index)
		var text := CodeEdit.new()
		text.editable = false
		text.custom_minimum_size.y = 180 * float(get_meta("ui_scale", 1.0))
		text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		side.add_child(text)
		_texts.append(text)
		var download := Button.new()
		download.text = "另存此版本…"
		download.pressed.connect(func():
			var reference := _reference(index)
			if reference.is_empty():
				return
			_download = {"scope": controller.session.scope_key(), "issue": model.selected, "reference": reference}
			_destination.current_file = str(reference.path).get_file().validate_filename()
			_destination.popup_centered_ratio(0.6)
		)
		side.add_child(download)
		_download_buttons.append(download)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	var heading := Label.new()
	heading.text = "判断左侧候选"
	heading.theme_type_variation = "TianxuanHeading"
	add_child(heading)
	_original.name = "NativeIssueOriginal"
	_original.custom_minimum_size.y = 180 * float(get_meta("ui_scale", 1.0))
	_original.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_original.text_changed.connect(_edit_original)
	_original.text_set.connect(_edit_original)
	add_child(_original)
	_save.text = "保存原件为新候选"
	_save.pressed.connect(_confirm.bind("edit"))
	add_child(_save)
	_discard.text = "放弃原件编辑草稿"
	_discard.pressed.connect(func(): controller.clear_draft(model.draft_key("original")))
	add_child(_discard)
	_note.placeholder_text = "判断或转交说明"
	_note.custom_minimum_size.y = 80 * float(get_meta("ui_scale", 1.0))
	add_child(_note)
	add_child(_recipients)
	add_child(_actions)
	for entry in [["approved", "采纳此版本"], ["changes_requested", "退回此版本"], ["transfer", "转交所选成员"]]:
		var action := Button.new()
		action.text = entry[1]
		action.name = "NativeIssueJudge_" + entry[0]
		action.pressed.connect(_confirm.bind(entry[0]))
		_actions.add_child(action)
	_dialog.title = "确认候选操作"
	_dialog.confirmed.connect(_execute)
	add_child(_dialog)
	model.changed.connect(_render)
	resized.connect(func(): _columns.vertical = size.x < 720 * float(get_meta("ui_scale", 1.0)))
	_render()


func _reference(index: int) -> Dictionary:
	return _choices[index].get_selected_metadata().duplicate(true) if _choices[index].selected >= 0 else {}


func _selected(index: int) -> void:
	if _syncing:
		return
	_dialog.hide()
	model.inspect_artifact(_reference(index))
	_render()


func _edit_original() -> void:
	if _syncing or not _original.editable:
		return
	var values: Dictionary = model.draft("original").get("values", {})
	if values.is_empty():
		values = {"reference": _reference(0), "expected": model.action_snapshot()}
	values.text = _original.text
	model.edit("original", values)


func _confirm(operation: String) -> void:
	var reference := _reference(0)
	if reference.is_empty():
		return
	var draft: Dictionary = model.draft("original").get("values", {})
	_intent = {"operation": operation, "reference": reference, "expected": draft.get("expected", model.action_snapshot()) if operation == "edit" else model.action_snapshot(), "text": _original.text, "note": _note.text, "recipient": str(_recipients.get_selected_metadata()) if _recipients.selected > 0 else ""}
	_dialog.dialog_text = tr("本次操作仅针对 %s 的版本 %d。\n%s") % [reference.path, int(reference.version), tr("提交后将产生新候选，原版本保留。") if operation == "edit" else tr("请核对左侧原件及判断说明。")]
	_dialog.popup_centered()


func _execute() -> void:
	if _intent.is_empty():
		return
	if _intent.operation == "edit":
		model.edit_artifact(_intent.reference, _intent.text, _intent.expected)
	else:
		model.judge_artifact(_intent.reference, _intent.operation, _intent.note, _intent.recipient, _intent.expected)
	_intent.clear()


func _render() -> void:
	_syncing = true
	var scope: String = controller.session.scope_key() + ":" + model.selected
	if scope != _scope:
		_scope = scope
		_signature = ""
		_intent.clear()
		_download.clear()
		_dialog.hide()
		_upload.hide()
		_destination.hide()
		_note.clear()
	_upload_button.disabled = not model.editable() or model.detail.is_empty()
	var artifacts: Array = model.sections.get("artifacts", {}).get("artifacts", [])
	var signature := JSON.stringify([scope, artifacts, model.catalog.get("users", {})])
	if signature != _signature:
		_signature = signature
		for index in 2:
			var previous := _reference(index)
			_choices[index].clear()
			var selected := -1
			for reference in artifacts:
				_choices[index].add_item("v%d · %s" % [int(reference.version), reference.path])
				var item := _choices[index].item_count - 1
				_choices[index].set_item_metadata(item, reference)
				if reference == previous:
					selected = item
			_choices[index].select(selected if selected >= 0 else mini(index, artifacts.size() - 1))
			_choices[index].disabled = artifacts.is_empty()
		_recipients.clear()
		_recipients.add_item("选择转交成员")
		for user in model.catalog.get("users", {}).get("users", []):
			if user.id != controller.identity().get("id") and user.get("role") != "viewer":
				_recipients.add_item(str(user.name))
				_recipients.set_item_metadata(_recipients.item_count - 1, user.id)
	for index in 2:
		var reference := _reference(index)
		var preview: Dictionary = model.previews.get(str(reference.get("version", "")), {})
		_download_buttons[index].disabled = reference.is_empty()
		_captions[index].text = tr("暂无附件或产物。") if reference.is_empty() else tr("%s · %s\n修订 %s") % [reference.kind, reference.path, reference.revision]
		if preview.get("loading", false):
			_captions[index].text += tr("\n正在读取并校验原件…")
		elif preview.has("error"):
			_captions[index].text += "\n" + str(preview.error)
		elif preview.has("size"):
			_captions[index].text += tr("\n%d 字节 · 摘要已核对") % int(preview.size)
		_pictures[index].texture = preview.get("texture")
		_pictures[index].visible = preview.has("texture")
		_texts[index].text = str(preview.get("text", ""))
		_texts[index].visible = preview.has("text")
		_show_model(index, preview)
		if preview.is_empty() and not reference.is_empty():
			model.inspect_artifact.call_deferred(reference)
	var chosen := _reference(0)
	var other := _reference(1)
	_status.text = str(model.section_errors.get("artifacts", ""))
	if not chosen.is_empty() and not other.is_empty():
		_status.text = "两个版本的原件内容相同。" if chosen.digest == other.digest else "两个版本的原件内容不同，可并排比较后判断。"
	var allowed := false
	for judgment in model.sections.get("work", {}).get("creative_judgments", []):
		if int(judgment.submission_version) == int(chosen.get("version", 0)):
			allowed = judgment.responsible == controller.identity().get("id") and judgment.decision == "pending"
	var preview: Dictionary = model.previews.get(str(chosen.get("version", "")), {})
	var draft: Dictionary = model.draft("original").get("values", {})
	_original.visible = allowed and preview.has("text")
	_original.editable = _original.visible and model.editable() and (draft.is_empty() or draft.get("reference") == chosen)
	var text := str(draft.get("text", preview.get("text", ""))) if draft.get("reference", chosen) == chosen else str(preview.get("text", ""))
	var original_context := JSON.stringify([scope, chosen])
	if _original.text != text and (original_context != _original_context or not _original.has_focus()):
		_original.text = text
	_original_context = original_context
	_save.visible = _original.visible
	_save.disabled = not _original.editable or draft.is_empty() or draft.get("expected") != model.action_snapshot()
	_discard.visible = not draft.is_empty()
	_discard.disabled = model.saving or not model.pending().is_empty()
	for action in _actions.get_children():
		action.disabled = not allowed or not model.editable()
	_syncing = false


func _build_model_view(parent: Node, index: int) -> void:
	var panel := VBoxContainer.new()
	parent.add_child(panel)
	_model_panels.append(panel)
	var container := SubViewportContainer.new()
	container.custom_minimum_size.y = 240 * float(get_meta("ui_scale", 1.0))
	container.stretch = true
	container.mouse_filter = Control.MOUSE_FILTER_STOP
	container.focus_mode = Control.FOCUS_ALL
	container.tooltip_text = "拖动旋转模型，滚轮缩放；也可使用下方按钮。"
	panel.add_child(container)
	var viewport := SubViewport.new()
	viewport.size = Vector2i(640, 480)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	container.add_child(viewport)
	_viewports.append(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	camera.current = true
	_cameras.append(camera)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("19232e")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.65
	viewport.add_child(environment)
	for rotation in [Vector3(-45, -30, 0), Vector3(-15, 125, 0)]:
		var light := DirectionalLight3D.new()
		light.rotation_degrees = rotation
		light.light_energy = 0.8
		viewport.add_child(light)
	_models.append(null)
	_model_keys.append("")
	_orbits.append(Vector3(0.6, 0.25, 1))
	_bounds.append(AABB())
	var controls := HFlowContainer.new()
	panel.add_child(controls)
	for pair in [["向左", Vector3(-0.25, 0, 0)], ["向右", Vector3(0.25, 0, 0)], ["向上", Vector3(0, 0.2, 0)], ["向下", Vector3(0, -0.2, 0)], ["放大", Vector3(0, 0, -0.15)], ["缩小", Vector3(0, 0, 0.15)], ["重置", Vector3.ZERO]]:
		var button := Button.new()
		button.text = pair[0]
		button.pressed.connect(func():
			_orbits[index] = Vector3(0.6, 0.25, 1) if pair[1] == Vector3.ZERO else _orbits[index] + pair[1]
			_position_camera(index)
		)
		controls.add_child(button)
	container.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			_orbits[index] += Vector3(-event.relative.x * 0.01, event.relative.y * 0.01, 0)
			_position_camera(index)
			container.accept_event()
		elif event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			_orbits[index].z += -0.1 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 0.1
			_position_camera(index)
			container.accept_event()
	)


func _show_model(index: int, preview: Dictionary) -> void:
	var available := preview.get("scene") is PackedScene
	_model_panels[index].visible = available
	var key := str(preview.get("reference", {}).get("digest", "")) if available else ""
	if key == _model_keys[index]:
		return
	_model_keys[index] = key
	if is_instance_valid(_models[index]):
		_viewports[index].remove_child(_models[index])
		_models[index].queue_free()
	_models[index] = null
	if not available:
		return
	var scene: Node = preview.scene.instantiate()
	if not scene is Node3D:
		scene.free()
		return
	_models[index] = scene
	_viewports[index].add_child(scene)
	scene.process_mode = Node.PROCESS_MODE_DISABLED
	_bounds[index] = preview.bounds
	_orbits[index] = Vector3(0.6, 0.25, 1)
	_position_camera(index)


func _position_camera(index: int) -> void:
	if not is_instance_valid(_models[index]):
		return
	var orbit := _orbits[index]
	orbit.y = clampf(orbit.y, -1.35, 1.35)
	orbit.z = clampf(orbit.z, 0.2, 4.0)
	_orbits[index] = orbit
	var radius := maxf(_bounds[index].size.length(), 0.01)
	var center := _bounds[index].get_center()
	var direction := Vector3(sin(orbit.x) * cos(orbit.y), sin(orbit.y), cos(orbit.x) * cos(orbit.y))
	_cameras[index].near = maxf(radius * 0.001, 0.0001)
	_cameras[index].far = maxf(radius * 20, 10)
	_cameras[index].look_at_from_position(center + direction * radius * 1.4 * orbit.z, center)
	_cameras[index].current = true


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signature = ""
		_render()
