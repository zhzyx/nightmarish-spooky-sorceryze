@tool
extends VBoxContainer

signal send_requested
signal models_requested

const QUESTION_LIMIT := 12000
var canvas_bar := HBoxContainer.new()
var canvas_message := TextEdit.new()
var canvas_models := OptionButton.new()
var canvas_backend := -1
var pending_turns := {}
var session_epoch := 0
var selections := {}
var canvas_history := {}
var canvas_drafts := {}
var canvas_location := ""
var canvas_generation := 0
var canvas_log := RichTextLabel.new()
var waiting := Label.new()


func _button(parent: Control, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func build() -> void:
	add_child(canvas_log)
	canvas_log.custom_minimum_size.y = 68 * get_theme_default_base_scale()
	canvas_log.selection_enabled = true
	canvas_log.scroll_following = true
	canvas_log.hide()
	add_child(waiting)
	waiting.hide()
	add_child(canvas_bar)
	canvas_bar.set_meta("ai_control_exclude", true)
	canvas_message.placeholder_text = "询问当前画布，或描述要执行的操作"
	canvas_message.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	canvas_message.custom_minimum_size.y = 32 * get_theme_default_base_scale()
	canvas_message.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas_bar.add_child(canvas_message)
	canvas_message.gui_input.connect(_message_input)
	canvas_models.item_selected.connect(func(_index): remember_model())
	canvas_models.tooltip_text = "对话模型"
	canvas_models.add_item("选择模型")
	canvas_bar.add_child(canvas_models)
	canvas_models.get_popup().about_to_popup.connect(models_requested.emit)
	_button(canvas_bar, "发送", send_requested.emit)


func _message_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or canvas_message.has_ime_text():
		return
	if event.keycode not in [KEY_ENTER, KEY_KP_ENTER] or event.ctrl_pressed or event.alt_pressed or event.meta_pressed:
		return
	canvas_message.accept_event()
	if event.shift_pressed:
		canvas_message.insert_text_at_caret("\n")
	elif not event.echo:
		send_requested.emit()


func load_models(catalog: Dictionary) -> void:
	var chosen = selections.get(canvas_location, {}).get(str(catalog.backend), catalog.current)
	canvas_backend = catalog.backend
	canvas_models.clear()
	var ids := [str(catalog.current)]
	for option in catalog.options:
		if not ids.has(option.id):
			ids.append(option.id)
	for id in ids:
		canvas_models.add_item("后端默认模型" if str(id).is_empty() else str(id))
		canvas_models.set_item_metadata(canvas_models.item_count - 1, id)
	canvas_models.select(maxi(0, ids.find(chosen)))


func remember_model() -> void:
	if canvas_backend >= 0:
		if not selections.has(canvas_location):
			selections[canvas_location] = {}
		selections[canvas_location][str(canvas_backend)] = canvas_models.get_selected_metadata()


func bind_scope(location: String) -> void:
	if location == canvas_location:
		return
	canvas_generation += 1
	if not canvas_location.is_empty():
		remember_model()
		canvas_drafts[canvas_location] = canvas_message.text
	canvas_location = location
	_update_waiting()
	canvas_message.text = canvas_drafts.get(location, "")
	canvas_message.clear_undo_history()
	canvas_log.text = canvas_history.get(location, "")
	canvas_log.visible = not canvas_log.text.is_empty()
	canvas_backend = -1
	models_requested.emit()


func append_line(scope: String, value: String) -> void:
	var entry := (str(canvas_history.get(scope, "")) + "\n" + value).strip_edges().right(16000)
	canvas_history[scope] = entry
	if scope == canvas_location:
		canvas_log.text = entry
		canvas_log.show()


func clear_session() -> void:
	canvas_message.clear()
	canvas_message.clear_undo_history()
	session_epoch += 1
	pending_turns.clear()
	waiting.hide()
	selections.clear()
	canvas_backend = -1
	canvas_location = ""
	canvas_log.text = ""
	canvas_log.hide()
	canvas_history.clear()
	canvas_drafts.clear()
	canvas_generation += 1


func model_selection() -> Dictionary:
	return {"backend":canvas_backend, "id":canvas_models.get_selected_metadata()}


func sent(turn: Dictionary) -> void:
	if not turn.project:
		canvas_generation += 1
		turn.generation = canvas_generation
		append_line(turn.scope, "你 · " + str(turn.question))
		if canvas_message.text.strip_edges() == turn.question:
			canvas_message.clear()
			canvas_message.clear_undo_history()
	pending_turns[turn.source] = turn
	_update_waiting()


func take_reply(source: String) -> Dictionary:
	var turn: Dictionary = pending_turns.get(source, {})
	pending_turns.erase(source)
	_update_waiting()
	return turn


func _update_waiting() -> void:
	for turn in pending_turns.values():
		if turn.scope == canvas_location:
			waiting.text = "正在等待模型分析全项目…" if turn.project else "正在等待模型分析当前画布…"
			waiting.show()
			return
	waiting.hide()
