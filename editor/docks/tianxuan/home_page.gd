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


func _ready() -> void:
	controller = get_meta("controller")
	ui_scale = float(get_meta("ui_scale", 1.0))
	compact = bool(get_meta("compact", false))
	set_h_size_flags(Control.SIZE_EXPAND_FILL)
	set_v_size_flags(Control.SIZE_EXPAND_FILL)
	var title := Label.new()
	title.text = "一起推进下一步"
	title.theme_type_variation = "TianxuanHeading" if compact else "TianxuanTitle"
	add_child(title)
	var subtitle := Label.new()
	subtitle.text = "从一个问题开始，将讨论整理为设计与可追踪的工作。"
	subtitle.theme_type_variation = "TianxuanMuted"
	subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(subtitle)
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	picker.name = "TianxuanConversations"
	picker.fit_to_longest_item = false
	picker.custom_minimum_size.x = 180 * ui_scale
	picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	picker.item_selected.connect(func(index: int): controller.select_conversation(str(picker.get_item_metadata(index))))
	toolbar.add_child(picker)
	var refresh := Button.new()
	refresh.text = "刷新"
	refresh.pressed.connect(_refresh)
	toolbar.add_child(refresh)
	design.text = "整理为需求"
	design.pressed.connect(func(): controller.navigate("design"))
	toolbar.add_child(design)
	more.text = "更多会话"
	more.pressed.connect(func(): controller.refresh_conversations(true))
	add_child(more)
	feedback.name = "TianxuanConversationStatus"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	feedback.theme_type_variation = "TianxuanCaption"
	add_child(feedback)
	scroll.name = "TianxuanConversationHistory"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	add_child(scroll)
	history.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	history.add_theme_constant_override("separation", roundi(18 * ui_scale))
	scroll.add_child(history)
	stop.text = "停止等待此回复"
	stop.pressed.connect(func(): controller.stop_waiting())
	add_child(stop)
	retry.text = "核对并重试原消息"
	retry.pressed.connect(func(): controller.retry_pending_message())
	add_child(retry)
	_model_status.name = "TianxuanLocalModelStatus"
	_model_status.theme_type_variation = "TianxuanCaption"
	_model_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_model_status)
	var sync_row := HBoxContainer.new()
	add_child(sync_row)
	_sync_status.name = "TianxuanConversationSyncStatus"
	_sync_status.theme_type_variation = "TianxuanCaption"
	_sync_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_sync_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sync_row.add_child(_sync_status)
	_sync.name = "SyncTianxuanLocalConversation"
	_sync.text = "同步回复"
	_sync.pressed.connect(func():
		if controller.local_chat:
			controller.local_chat.sync(controller.active_conversation)
	)
	sync_row.add_child(_sync)
	_build_editor_tools()
	composer.name = "TianxuanComposer"
	composer.placeholder_text = "描述需求，或提出开发问题…"
	composer.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	composer.custom_minimum_size.y = (100 if compact else 130) * ui_scale
	composer.text_changed.connect(_save_draft)
	composer.text_set.connect(_save_draft)
	composer.gui_input.connect(_composer_input)
	add_child(composer)
	var footer := HBoxContainer.new()
	add_child(footer)
	var hint := Label.new()
	hint.text = tr("⌘ / Ctrl + Enter 发送")
	hint.theme_type_variation = "TianxuanCaption"
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(hint)
	send.name = "SendTianxuanMessage"
	send.text = "发送"
	send.theme_type_variation = "TianxuanPrimaryButton"
	send.pressed.connect(_send)
	footer.add_child(send)
	_poll.wait_time = 3.0
	_poll.timeout.connect(_poll_pending)
	add_child(_poll)
	controller.changed.connect(_changed)
	visibility_changed.connect(_visibility_changed)
	_changed("identity")
	_refresh()


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
	send.text = "处理中…" if busy else "发送"
	stop.visible = pending
	stop.disabled = not controller.can_edit() or (busy and not (controller.local_chat and controller.local_chat.busy()))
	var configuration: Dictionary = controller.local_chat.configuration() if controller.local_chat else {}
	_model_status.text = tr("本机模型 · %s · %s") % [str(configuration.get("provider", "")), str(configuration.get("id", "默认模型")) if not str(configuration.get("id", "")).is_empty() else tr("默认模型")]
	_sync_status.text = tr(str(current.get("local_sync", "")))
	_sync.visible = not _sync_status.text.is_empty()
	_sync.disabled = not controller.can_edit() or (controller.local_chat and controller.local_chat.syncing.has(controller.active_conversation))
	feedback.text = str(controller.errors.get("conversation:" + controller.active_conversation, controller.errors.get("conversations", controller.errors.get("chat", ""))))
	if unknown and feedback.text.is_empty():
		feedback.text = "正在核对已提交消息的回执，草稿仍保留。"
	elif busy and feedback.text.is_empty():
		feedback.text = "正在等待本机模型回复…" if controller.local_chat and controller.local_chat.busy() else "正在与工作区同步…"
	elif not controller.can_edit() and feedback.text.is_empty():
		feedback.text = "当前账号可阅读会话，发送消息需要编辑权限。"
	var signature := JSON.stringify([controller.active_conversation, current.get("version"), current.get("turns", [])])
	if signature != _rendered:
		_rendered = signature
		_render_messages(current)
	if (pending or unknown) and is_visible_in_tree():
		if _poll.is_stopped():
			_poll.start()
	else:
		_poll.stop()
	_updating = false
	_render_editor_context()
	if topic == "identity":
		_open_file.hide()
		_import_source.hide()
		_import_destination.hide()
		_source = ""


func _build_editor_tools() -> void:
	var row := HBoxContainer.new()
	add_child(row)
	_editor_tools.name = "TianxuanEditorActions"
	_editor_tools.text = "编辑器联动"
	for caption in ["加入选中节点", "加入选中资源", "打开项目文件或脚本", "导入资源到项目"]:
		_editor_tools.get_popup().add_item(caption)
	_editor_tools.get_popup().id_pressed.connect(func(id: int):
		match id:
			0:
				controller.editor_context.attach_nodes()
			1:
				controller.editor_context.attach_resources()
			2:
				_open_file.popup_centered_ratio(0.7)
			3:
				_import_source.popup_centered_ratio(0.7)
	)
	row.add_child(_editor_tools)
	_modules.fit_to_longest_item = false
	_modules.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_modules.item_selected.connect(func(index: int):
		controller.editor_module = str(_modules.get_item_metadata(index))
		controller.changed.emit("editor_context")
	)
	row.add_child(_modules)
	add_child(_attachments)
	_editor_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_editor_status.theme_type_variation = "TianxuanCaption"
	add_child(_editor_status)
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
	var items: Array = controller.editor_context.attachments()
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
	for child in history.get_children():
		child.queue_free()
	if current.get("turns", []).is_empty():
		_message("天璇", tr("把正在思考的问题放在这里。\n\n你可以讨论方案、整理需求，或查看已有工作的进展。"), false)
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
			_message(str(turn.get("model", "AI")), str(turn.answer), false)
		elif turn.state == "pending":
			_message("等待回复", tr("正在等待本机模型回复…") if turn.get("reply_source") == "editor-local" else tr("消息已保存，正在等待模型的处理结果。"), false)
		else:
			var reason := str(turn.get("local_error", ""))
			if reason.is_empty():
				reason = "此前调用的线上模型未返回回复。新消息将使用编辑器本机 CLI 或 API。" if turn.get("error") != null else "已停止等待此回复，消息已保留。"
			_message("消息已保存", tr(reason), false)
	_scroll_to_end.call_deferred()


func _message(author: String, body: String, user: bool, attachment_text := "") -> void:
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


func _scroll_to_end() -> void:
	await get_tree().process_frame
	if is_instance_valid(scroll):
		scroll.scroll_vertical = int(scroll.get_v_scroll_bar().max_value)


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_attachment_signature = ""
		_rendered = ""
		_changed("")
