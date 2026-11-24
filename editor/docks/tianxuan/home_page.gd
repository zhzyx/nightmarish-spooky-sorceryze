@tool
extends VBoxContainer

var controller: Node
var ui_scale := 1.0
var compact := false
var picker := OptionButton.new()
var more := Button.new()
var feedback := Label.new()
var history := VBoxContainer.new()
var scroll := ScrollContainer.new()
var composer := TextEdit.new()
var send := Button.new()
var stop := Button.new()
var design := Button.new()
var retry := Button.new()
var _rendered := ""
var _updating := false
var _poll := Timer.new()
var _model_status := Label.new()
var _sync_status := Label.new()
var _sync := Button.new()
var _editor_tools := MenuButton.new()
var _modules := OptionButton.new()
var _attachments := VBoxContainer.new()
var _editor_status := Label.new()
var _attachment_signature := ""
var _open_file := FileDialog.new()
var _import_source := FileDialog.new()
var _import_destination := FileDialog.new()
var _source := ""
var _progress_timer := Timer.new()
var _progress_row := HBoxContainer.new()
var _progress_status := Label.new()
var _status_row := HBoxContainer.new()
var _context_panel := ScrollContainer.new()
var _rendered_conversation := ""
var _render_generation := 0
var _scroll_interaction := 0
var _following_tail := true
var _restoring_history := false


func _ready() -> void:
	controller = get_meta("controller")
	ui_scale = float(get_meta("ui_scale", 1.0))
	compact = bool(get_meta("compact", false))
	set_h_size_flags(Control.SIZE_EXPAND_FILL)
	set_v_size_flags(Control.SIZE_EXPAND_FILL)
	add_theme_constant_override("separation", roundi(6 * ui_scale))
	var toolbar := HBoxContainer.new()
	toolbar.add_theme_constant_override("separation", roundi(4 * ui_scale))
	add_child(toolbar)
	picker.name = "TianxuanConversations"
	picker.fit_to_longest_item = false
	picker.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	picker.item_selected.connect(func(index: int): controller.select_conversation(str(picker.get_item_metadata(index))))
	toolbar.add_child(picker)
	var refresh := Button.new()
	refresh.icon = EditorInterface.get_editor_theme().get_icon("Reload", "EditorIcons")
	refresh.tooltip_text = "刷新"
	refresh.pressed.connect(_refresh)
	toolbar.add_child(refresh)
	design.text = "需求"
	design.tooltip_text = "整理为需求"
	design.pressed.connect(func(): controller.navigate("design"))
	toolbar.add_child(design)
	more.text = "···"
	more.tooltip_text = "更多会话"
	more.pressed.connect(func(): controller.refresh_conversations(true))
	toolbar.add_child(more)
	feedback.name = "TianxuanConversationStatus"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	feedback.theme_type_variation = "TianxuanCaption"
	feedback.max_lines_visible = 2
	feedback.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	add_child(feedback)
	scroll.name = "TianxuanConversationHistory"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = false
	scroll.gui_input.connect(_history_input)
	scroll.get_v_scroll_bar().gui_input.connect(_history_input)
	scroll.get_v_scroll_bar().value_changed.connect(_history_position_changed)
	scroll.get_v_scroll_bar().changed.connect(_history_range_changed)
	add_child(scroll)
	history.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	history.add_theme_constant_override("separation", roundi(12 * ui_scale))
	scroll.add_child(history)
	_progress_row.name = "TianxuanLocalProgress"
	add_child(_progress_row)
	_progress_status.name = "TianxuanLocalProgressStatus"
	_progress_status.theme_type_variation = "TianxuanCaption"
	_progress_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_progress_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_progress_row.add_child(_progress_status)
	stop.name = "StopTianxuanMessage"
	stop.text = "停止"
	stop.tooltip_text = "停止等待此回复"
	stop.pressed.connect(func(): controller.stop_waiting())
	_progress_row.add_child(stop)
	retry.text = "核对并重试原消息"
	retry.pressed.connect(func(): controller.retry_pending_message())
	add_child(retry)
	_model_status.name = "TianxuanLocalModelStatus"
	_model_status.theme_type_variation = "TianxuanCaption"
	_model_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_model_status.clip_text = true
	_model_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(_status_row)
	_status_row.add_child(_model_status)
	_sync_status.name = "TianxuanConversationSyncStatus"
	_sync_status.theme_type_variation = "TianxuanCaption"
	_sync_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_sync_status.clip_text = true
	_sync_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status_row.add_child(_sync_status)
	_sync.name = "SyncTianxuanLocalConversation"
	_sync.text = "同步回复"
	_sync.pressed.connect(func():
		if controller.local_chat:
			controller.local_chat.sync(controller.active_conversation)
	)
	_status_row.add_child(_sync)
	_build_editor_tools(toolbar)
	var composer_row := HBoxContainer.new()
	composer_row.name = "TianxuanComposerRow"
	add_child(composer_row)
	composer.name = "TianxuanComposer"
	composer.placeholder_text = "描述需求，或提出开发问题…"
	composer.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	composer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	composer.tooltip_text = "⌘ / Ctrl + Enter 发送"
	for state in ["normal", "read_only"]:
		var style: StyleBox = get_theme_stylebox(state, "TextEdit").duplicate()
		style.content_margin_top = 6 * ui_scale
		style.content_margin_bottom = 6 * ui_scale
		composer.add_theme_stylebox_override(state, style)
	composer.text_changed.connect(_save_draft)
	composer.text_set.connect(_save_draft)
	composer.gui_input.connect(_composer_input)
	composer_row.add_child(composer)
	send.name = "SendTianxuanMessage"
	send.text = "发送"
	send.theme_type_variation = "TianxuanPrimaryButton"
	send.pressed.connect(_send)
	send.size_flags_vertical = Control.SIZE_SHRINK_END
	composer_row.add_child(send)
	for button in [picker, refresh, design, more, _editor_tools, stop, retry, _sync, send]:
		_compact_button(button)
	resized.connect(_fit_composer)
	_fit_composer()
	_progress_timer.wait_time = 1.0
	_progress_timer.timeout.connect(_update_progress)
	add_child(_progress_timer)
	_poll.wait_time = 3.0
	_poll.timeout.connect(_poll_pending)
	add_child(_poll)
	controller.changed.connect(_changed)
	visibility_changed.connect(_visibility_changed)
	_changed("identity")
	_refresh()


func _compact_button(button: BaseButton) -> void:
	button.add_theme_font_size_override("font_size", roundi(12 * ui_scale))
	for state in ["normal", "hover", "pressed", "disabled"]:
		var style: StyleBox = button.get_theme_stylebox(state).duplicate()
		style.content_margin_top = 4 * ui_scale
		style.content_margin_bottom = 4 * ui_scale
		style.content_margin_left = 7 * ui_scale
		style.content_margin_right = 7 * ui_scale
		button.add_theme_stylebox_override(state, style)


func _fit_composer() -> void:
	composer.custom_minimum_size.y = clampf(size.y * 0.12, 36 * ui_scale, 68 * ui_scale)
	_context_panel.custom_minimum_size.y = minf(96 * ui_scale, maxf(48 * ui_scale, size.y * 0.2))


func _history_input(event: InputEvent) -> void:
	if event is InputEventMouseButton or event is InputEventPanGesture or event is InputEventScreenDrag or event is InputEventKey:
		_scroll_interaction += 1
		_restoring_history = false


func _history_position_changed(value: float) -> void:
	if not _restoring_history:
		var bar := scroll.get_v_scroll_bar()
		_following_tail = bar.max_value - bar.page - value <= 12 * ui_scale


func _history_range_changed() -> void:
	# RichTextLabel can finish measuring after the first container layout.
	# Continue following only for a reader who was already at the bottom.
	if _following_tail and is_inside_tree():
		scroll.scroll_vertical = int(scroll.get_v_scroll_bar().max_value)


func _update_progress() -> void:
	var progress: Dictionary = controller.local_chat.progress() if controller.local_chat else {}
	var active: bool = bool(progress.get("active", false)) and progress.get("conversation", "") == controller.active_conversation
	var pending := false
	for turn in controller.conversation().get("turns", []):
		pending = pending or turn.get("state") == "pending"
	_progress_row.visible = active or pending
	_status_row.visible = not active
	stop.visible = active or pending
	stop.disabled = not controller.can_edit() or (controller.chat_busy() and not active)
	if active:
		var phase := tr("正在启动本机模型") if progress.get("phase") == "starting" else tr("正在等待本机模型回复")
		var seconds := maxi(0, int(progress.get("elapsed_seconds", 0)))
		_progress_status.text = tr("%s · 已用时 %d:%02d") % [phase, seconds / 60, seconds % 60]
		_progress_status.tooltip_text = _progress_status.text
	elif pending:
		_progress_status.text = "正在核对已提交消息的回执，草稿仍保留。"
	if active and is_visible_in_tree():
		if _progress_timer.is_stopped():
			_progress_timer.start()
	else:
		_progress_timer.stop()


func _composer_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ENTER and (event.ctrl_pressed or event.meta_pressed):
		_send()
		get_viewport().set_input_as_handled()


func _save_draft() -> void:
	if _updating:
		return
	var key: String = controller.chat_draft_key(controller.active_conversation)
	var draft: Dictionary = controller.load_draft(key)
	draft.text = composer.text
	if not controller.save_draft(key, draft):
		feedback.text = "无法保存本机草稿，请先复制内容再离开。"


func _send() -> void:
	if not send.disabled:
		var context: Dictionary = controller.editor_context.message_context(controller.editor_module)
		if context.valid:
			controller.send_message(composer.text + str(context.text), context.references, composer.text)
		else:
			_context_panel.show()
			_render_editor_context()


func _refresh() -> void:
	controller.refresh_conversations()
	if not controller.cache.has("editor-modules"):
		controller.read("editor-modules", "/api/v1/business-modules")
	if not controller.active_conversation.is_empty():
		controller.refresh_conversation(controller.active_conversation)


func _poll_pending() -> void:
	if is_visible_in_tree() and not controller.chat_busy() and not controller.active_conversation.is_empty():
		controller.refresh_conversation(controller.active_conversation)


func _visibility_changed() -> void:
	if is_visible_in_tree():
		_changed("visibility")
		_refresh()
	else:
		_poll.stop()
		_progress_timer.stop()


func _changed(topic: String) -> void:
	if topic == "identity_resetting":
		return
	if topic.begins_with("draft:") and topic != "draft:" + controller.chat_draft_key(controller.active_conversation):
		return
	_updating = true
	var current: Dictionary = controller.conversation()
	var busy: bool = controller.chat_busy()
	_editor_tools.disabled = busy or not controller.can_edit()
	design.disabled = controller.active_conversation.is_empty()
	picker.clear()
	picker.add_item("新对话")
	picker.set_item_metadata(0, "")
	var summaries: Dictionary = controller.cache.get("conversations", {})
	for item in summaries.get("conversations", []):
		picker.add_item(str(item.get("title", "未命名对话")))
		picker.set_item_auto_translate_mode(picker.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		picker.set_item_metadata(picker.item_count - 1, item.id)
		if item.id == controller.active_conversation:
			picker.select(picker.item_count - 1)
	more.visible = summaries.get("next") is String and not str(summaries.next).is_empty()
	more.disabled = controller.busy("conversations")
	picker.disabled = busy
	var draft: Dictionary = controller.load_draft(controller.chat_draft_key(controller.active_conversation))
	var text := str(draft.get("text", ""))
	if composer.text != text:
		composer.text = text
	var pending := false
	for turn in current.get("turns", []):
		pending = pending or turn.get("state") == "pending"
	var unknown := not str(draft.get("pending_id", "")).is_empty()
	retry.visible = unknown
	retry.disabled = busy or not controller.can_edit()
	composer.editable = controller.can_edit() and not busy and not pending and not unknown
	send.disabled = not composer.editable or composer.text.strip_edges().is_empty()
	send.text = "发送"
	var configuration: Dictionary = controller.local_chat.configuration() if controller.local_chat else {}
	_model_status.text = tr("本机模型 · %s · %s") % [str(configuration.get("provider", "")), str(configuration.get("id", "默认模型")) if not str(configuration.get("id", "")).is_empty() else tr("默认模型")]
	_sync_status.text = tr(str(current.get("local_sync", "")))
	_sync_status.tooltip_text = _sync_status.text
	_sync_status.visible = not _sync_status.text.is_empty() and str(current.get("local_sync", "")) != "已同步到工作区。"
	_model_status.visible = not _sync_status.visible
	_model_status.tooltip_text = _model_status.text
	_sync.visible = _sync_status.visible
	_sync.disabled = not controller.can_edit() or (controller.local_chat and controller.local_chat.syncing.has(controller.active_conversation))
	feedback.text = str(controller.errors.get("conversation:" + controller.active_conversation, controller.errors.get("conversations", controller.errors.get("chat", ""))))
	if unknown and feedback.text.is_empty():
		feedback.text = "正在核对已提交消息的回执，草稿仍保留。"
	elif busy and feedback.text.is_empty() and not (controller.local_chat and controller.local_chat.busy()):
		feedback.text = "正在与工作区同步…"
	elif not controller.can_edit() and feedback.text.is_empty():
		feedback.text = "当前账号可阅读会话，发送消息需要编辑权限。"
	feedback.visible = not feedback.text.is_empty()
	feedback.tooltip_text = feedback.text
	var resume_states := []
	for turn in current.get("turns", []):
		if turn.get("state") == "unanswered" and controller.local_chat:
			resume_states.append(controller.local_chat.resume_state(str(turn.id)))
	var signature := JSON.stringify([controller.active_conversation, current.get("version"), current.get("turns", []), resume_states])
	if signature != _rendered:
		_rendered = signature
		_render_messages(current)
	if (pending or unknown) and is_visible_in_tree():
		if _poll.is_stopped():
			_poll.start()
	else:
		_poll.stop()
	_updating = false
	_update_progress()
	_render_editor_context()
	if topic == "identity":
		_open_file.hide()
		_import_source.hide()
		_import_destination.hide()
		_source = ""
		_context_panel.hide()


func _build_editor_tools(toolbar: HBoxContainer) -> void:
	_editor_tools.name = "TianxuanEditorActions"
	_editor_tools.text = "上下文"
	_editor_tools.tooltip_text = "编辑器联动"
	for caption in ["加入选中节点", "加入选中资源", "打开项目文件或脚本", "导入资源到项目"]:
		_editor_tools.get_popup().add_item(caption)
	_editor_tools.get_popup().add_separator()
	_editor_tools.get_popup().add_item("引用模块与附件", 4)
	_editor_tools.get_popup().id_pressed.connect(func(id: int):
		match id:
			0:
				controller.editor_context.attach_nodes()
				_context_panel.show()
			1:
				controller.editor_context.attach_resources()
				_context_panel.show()
			2:
				_open_file.popup_centered_ratio(0.7)
			3:
				_import_source.popup_centered_ratio(0.7)
			4:
				_context_panel.visible = not _context_panel.visible
	)
	toolbar.add_child(_editor_tools)
	_context_panel.name = "TianxuanEditorContextDetails"
	_context_panel.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(_context_panel)
	var details := VBoxContainer.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_context_panel.add_child(details)
	_modules.fit_to_longest_item = false
	_modules.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_modules.item_selected.connect(func(index: int):
		controller.editor_module = str(_modules.get_item_metadata(index))
		controller.changed.emit("editor_context")
	)
	details.add_child(_modules)
	details.add_child(_attachments)
	_editor_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_editor_status.theme_type_variation = "TianxuanCaption"
	details.add_child(_editor_status)
	_context_panel.hide()
	_open_file.access = FileDialog.ACCESS_RESOURCES
	_open_file.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_open_file.file_selected.connect(func(path: String): controller.editor_context.open_file(path))
	add_child(_open_file)
	_import_source.title = "选择要导入的资源"
	_import_source.access = FileDialog.ACCESS_FILESYSTEM
	_import_source.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_import_source.file_selected.connect(func(path: String):
		_source = path
		_import_destination.current_file = path.get_file()
		_import_destination.popup_centered_ratio(0.7)
	)
	add_child(_import_source)
	_import_destination.title = "保存到项目目录"
	_import_destination.access = FileDialog.ACCESS_RESOURCES
	_import_destination.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_import_destination.file_selected.connect(func(path: String):
		controller.editor_context.import_asset(_source, path)
		_source = ""
	)
	add_child(_import_destination)
	controller.editor_context.changed.connect(_render_editor_context)
	controller.read("editor-modules", "/api/v1/business-modules")


func _render_editor_context() -> void:
	if not controller or not controller.editor_context:
		return
	_modules.clear()
	_modules.add_item("选择引用所属模块")
	_modules.set_item_metadata(0, "")
	for module in controller.cache.get("editor-modules", {}).get("modules", []):
		_modules.add_item(str(module.name))
		_modules.set_item_auto_translate_mode(_modules.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		_modules.set_item_metadata(_modules.item_count - 1, module.id)
		if module.id == controller.editor_module:
			_modules.select(_modules.item_count - 1)
	_editor_status.text = controller.editor_context.status
	_editor_status.visible = not _editor_status.text.is_empty()
	var items: Array = controller.editor_context.attachments()
	_editor_tools.text = tr("上下文") if items.is_empty() else tr("引用 · %d") % items.size()
	var signature := JSON.stringify(items)
	if signature == _attachment_signature:
		return
	_attachment_signature = signature
	for child in _attachments.get_children():
		_attachments.remove_child(child)
		child.queue_free()
	for index in items.size():
		var item: Dictionary = items[index]
		var row := HBoxContainer.new()
		_attachments.add_child(row)
		var title := Label.new()
		title.text = str(item.title)
		title.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
		title.tooltip_text = str(item.snapshot)
		title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(title)
		var remove := Button.new()
		remove.text = "移除"
		remove.pressed.connect(func(): controller.editor_context.remove(index))
		row.add_child(remove)


func _render_messages(current: Dictionary) -> void:
	var previous := scroll.scroll_vertical
	var bar := scroll.get_v_scroll_bar()
	var follow: bool = controller.active_conversation != _rendered_conversation or bar.max_value - bar.page - bar.value <= 12 * ui_scale
	_following_tail = follow
	_restoring_history = true
	_rendered_conversation = controller.active_conversation
	_render_generation += 1
	for child in history.get_children():
		history.remove_child(child)
		child.queue_free()
	if current.get("turns", []).is_empty():
		_message("天璇", tr("把正在思考的问题放在这里。\n\n你可以讨论方案、整理需求，或查看已有工作的进展。"), false)
	var latest: String = str(current.turns.back().id) if not current.get("turns", []).is_empty() else ""
	for turn in current.get("turns", []):
		var text := str(turn.content)
		var attachment_text := ""
		var marker := "\n\n---\nGodot 编辑器引用（本次消息的对象快照）：\n\n"
		var boundary := text.rfind(marker)
		if turn.get("context_snapshot") is Dictionary and boundary >= 0:
			attachment_text = text.substr(boundary + marker.length())
			text = text.left(boundary)
		_message("你", text, true, attachment_text)
		if turn.state == "answered":
			var answer := _message(str(turn.get("model", "AI")), str(turn.answer), false)
			if str(turn.id) == latest:
				_design_action(answer, str(current.get("id", "")))
		elif turn.state == "pending":
			_message("等待回复", tr("正在等待本机模型回复…") if turn.get("reply_source") == "editor-local" else tr("消息已保存，正在等待模型的处理结果。"), false)
		else:
			var reason := str(turn.get("local_error", ""))
			if reason.is_empty():
				reason = "此前未收到回复。点击“继续此请求”使用本机模型接着处理。" if turn.get("error") != null else "已停止等待此回复，消息已保留。"
			var card := _message("消息已保存", tr(reason), false)
			if controller.local_chat:
				var state: Dictionary = controller.local_chat.resume_state(str(turn.id))
				var resume := Button.new()
				resume.name = "ResumeTianxuanMessage_" + str(turn.id)
				resume.text = "已继续处理" if state.get("resumed", false) else "继续此请求"
				resume.disabled = not state.get("available", false)
				resume.tooltip_text = str(state.get("reason", ""))
				var turn_id := str(turn.id)
				var conversation_id := str(current.get("id", ""))
				var scope: String = controller.session.scope_key()
				resume.pressed.connect(func(): controller.resume_message(turn_id, conversation_id, scope))
				card.add_child(resume)
				_compact_button(resume)
				if resume.disabled and not resume.tooltip_text.is_empty():
					var explanation := Label.new()
					explanation.text = resume.tooltip_text
					explanation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
					explanation.theme_type_variation = "TianxuanCaption"
					card.add_child(explanation)
			if str(turn.id) == latest:
				_design_action(card, str(current.get("id", "")))
	_restore_scroll.call_deferred(_render_generation, previous, follow, _scroll_interaction)


func _design_action(card: VBoxContainer, conversation_id: String) -> void:
	var explanation := Label.new()
	explanation.text = "确认规格后，整理为需求并执行。"
	explanation.theme_type_variation = "TianxuanCaption"
	explanation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	card.add_child(explanation)
	var action := Button.new()
	action.name = "TianxuanNextRequirement"
	action.text = "整理为需求"
	action.pressed.connect(func():
		if controller.active_conversation == conversation_id:
			controller.navigate("design")
	)
	card.add_child(action)
	_compact_button(action)


func _message(author: String, body: String, user: bool, attachment_text := "") -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "TianxuanInset" if user else "TianxuanCard"
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	history.add_child(panel)
	var layout := VBoxContainer.new()
	panel.add_child(layout)
	var label := Label.new()
	label.text = author
	label.theme_type_variation = "TianxuanCaption"
	layout.add_child(label)
	var content: RichTextLabel = get_meta("markdown_script").new()
	content.set_meta("controller", controller)
	content.ui_scale = ui_scale
	layout.add_child(content)
	content.set_markdown(body)
	if not attachment_text.is_empty():
		var expand := Button.new()
		expand.text = "查看随消息发送的编辑器引用"
		expand.toggle_mode = true
		layout.add_child(expand)
		var attachments_view: RichTextLabel = get_meta("markdown_script").new()
		attachments_view.ui_scale = ui_scale
		layout.add_child(attachments_view)
		attachments_view.set_markdown(attachment_text)
		attachments_view.hide()
		expand.toggled.connect(func(expanded: bool): attachments_view.visible = expanded)
	return layout


func _restore_scroll(generation: int, previous: int, follow: bool, interaction: int) -> void:
	if not is_inside_tree():
		return
	await get_tree().process_frame
	if not is_inside_tree():
		return
	await get_tree().process_frame
	if is_instance_valid(scroll) and generation == _render_generation and interaction == _scroll_interaction:
		scroll.scroll_vertical = int(scroll.get_v_scroll_bar().max_value) if follow else previous
		_restoring_history = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_attachment_signature = ""
		_rendered = ""
		_changed("")
