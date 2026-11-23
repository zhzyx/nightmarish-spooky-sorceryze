@tool
extends VBoxContainer

var model: Node
var workspace: Node
var ui_scale := 1.0
var _updating := false
var _detail_signature := ""
var _list_signature := ""
var _filter := LineEdit.new()
var _picker := OptionButton.new()
var _tree := Tree.new()
var _columns := HBoxContainer.new()
var _tabs := TabContainer.new()
var _title := LineEdit.new()
var _body := TextEdit.new()
var _preview: RichTextLabel
var _edit_preview: RichTextLabel
var _edit_columns := BoxContainer.new()
var _edit_preview_scroll := ScrollContainer.new()
var _editor_mode := OptionButton.new()
var _format_buttons: Array[Button] = []
var _status := Label.new()
var _save := Button.new()
var _discard := Button.new()
var _remote := TextEdit.new()
var _resolve := Button.new()
var _from := OptionButton.new()
var _to := OptionButton.new()
var _diff := TextEdit.new()
var _versions := VBoxContainer.new()
var _comments := VBoxContainer.new()
var _comment := TextEdit.new()
var _post := Button.new()
var _shares := VBoxContainer.new()
var _share_user := LineEdit.new()
var _share_permission := OptionButton.new()
var _expires := LineEdit.new()
var _visibility := OptionButton.new()
var _links := VBoxContainer.new()
var _confirm := ConfirmationDialog.new()
var _confirmed := Callable()
var _export := FileDialog.new()
var _format := OptionButton.new()
var _export_id := ""
var _context := ""


func _ready() -> void:
	workspace = get_meta("controller")
	model = workspace.documents
	ui_scale = float(get_meta("ui_scale", 1.0))
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	var title := Label.new()
	title.text = "文曲 · 团队知识"
	title.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	add_child(title)
	var caption := Label.new()
	caption.text = "把想法写清楚，让修改、讨论和版本留有依据。"
	caption.theme_type_variation = "TianxuanMuted"
	caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(caption)
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	_filter.placeholder_text = "搜索标题、类型或状态"
	_filter.custom_minimum_size.x = 180 * ui_scale
	_filter.text_changed.connect(func(_text: String): _render_list(true))
	toolbar.add_child(_filter)
	_button(toolbar, "刷新", func(): model.refresh_list(); model.refresh())
	_button(toolbar, "新建文档", func(): model.open(""); _tabs.current_tab = 1)
	_picker.name = "TianxuanDocumentPicker"
	_picker.fit_to_longest_item = false
	_picker.item_selected.connect(func(index: int): model.open(str(_picker.get_item_metadata(index))))
	add_child(_picker)
	_status.name = "TianxuanDocumentStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	_columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_columns)
	_tree.custom_minimum_size.x = 210 * ui_scale
	_tree.hide_root = true
	_tree.item_selected.connect(func():
		if not _updating and _tree.get_selected() and _tree.get_selected().get_metadata(0) is String:
			model.open.call_deferred(_tree.get_selected().get_metadata(0))
	)
	_columns.add_child(_tree)
	_tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tabs.clip_tabs = true
	_columns.add_child(_tabs)
	_build_document()
	_build_history()
	_build_comments()
	_build_sharing()
	_links = _tab("关联")
	_tabs.tab_changed.connect(_tab_changed)
	_confirm.confirmed.connect(func():
		if _confirmed.is_valid():
			_confirmed.call()
		_confirmed = Callable()
	)
	add_child(_confirm)
	_export.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_export.access = FileDialog.ACCESS_FILESYSTEM
	_export.file_selected.connect(func(path: String):
		if _export_id == model.active_id:
			model.export_file(_format.get_item_text(_format.selected), path)
	)
	add_child(_export)
	model.changed.connect(_changed)
	resized.connect(_responsive)
	_changed()
	_responsive()
	model.refresh_list()


func _button(parent: Node, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _tab(caption: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = caption
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	_tabs.add_child(scroll)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(column)
	return column


func _build_document() -> void:
	var read := _tab("阅读")
	_preview = get_meta("markdown_script").new()
	_preview.set_meta("controller", workspace)
	_preview.ui_scale = ui_scale
	read.add_child(_preview)
	var export_row := HFlowContainer.new()
	read.add_child(export_row)
	for format in ["md", "html", "docx", "pdf"]:
		_format.add_item(format)
	export_row.add_child(_format)
	_button(export_row, "导出文档", func():
		if model.active_id.is_empty():
			return
		_export_id = model.active_id
		var format := _format.get_item_text(_format.selected)
		_export.filters = PackedStringArray(["*." + format + " ; " + format.to_upper()])
		_export.current_file = "document." + format
		_export.popup_centered_ratio(0.7)
	)
	var edit := _tab("编辑")
	_title.name = "TianxuanDocumentTitle"
	_title.placeholder_text = "文档标题"
	_title.text_changed.connect(func(_text: String): _save_draft())
	edit.add_child(_title)
	var formatting := HFlowContainer.new()
	edit.add_child(formatting)
	for item in [["加粗", "**", "**", "强调文字"], ["斜体", "*", "*", "斜体文字"], ["二级标题", "## ", "", "标题"], ["列表", "- ", "", "列表项"], ["引用", "> ", "", "引用文字"], ["代码", "`", "`", "代码"]]:
		var format_button := _button(formatting, item[0], _format_selection.bind(item[1], item[2], item[3]))
		format_button.name = "NativeDocumentFormat" + str(_format_buttons.size())
		_format_buttons.append(format_button)
	for caption in ["编辑与预览", "仅编辑", "仅预览"]:
		_editor_mode.add_item(caption)
	_editor_mode.item_selected.connect(func(_index: int): _responsive())
	formatting.add_child(_editor_mode)
	edit.add_child(_edit_columns)
	_body.name = "TianxuanDocumentBody"
	_body.custom_minimum_size.y = 280 * ui_scale
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_body.placeholder_text = "使用 Markdown 编写正文…"
	_body.text_changed.connect(_save_draft)
	_body.text_set.connect(_save_draft)
	_edit_columns.add_child(_body)
	_edit_preview_scroll.custom_minimum_size.y = 280 * ui_scale
	_edit_preview_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_edit_preview_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_edit_columns.add_child(_edit_preview_scroll)
	_edit_preview = get_meta("markdown_script").new()
	_edit_preview.set_meta("controller", workspace)
	_edit_preview.ui_scale = ui_scale
	_edit_preview_scroll.add_child(_edit_preview)
	_body.gui_input.connect(func(event: InputEvent):
		if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_S and event.is_command_or_control_pressed():
			_body.accept_event()
			_save_draft()
			if not _save.disabled:
				model.save()
	)
	var actions := HFlowContainer.new()
	edit.add_child(actions)
	_save = _button(actions, "保存到工作区", func(): model.save())
	_save.name = "SaveTianxuanDocument"
	_save.theme_type_variation = "TianxuanPrimaryButton"
	_discard = _button(actions, "放弃本机草稿", func(): _ask("放弃此设备上尚未提交的修改？", model.discard_draft))
	_remote.editable = false
	_remote.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_remote.custom_minimum_size.y = 200 * ui_scale
	edit.add_child(_remote)
	_resolve = _button(edit, "已比较服务器版本，使用上方草稿", func(): _ask("将上方草稿作为已解决冲突的内容？随后仍需点击保存。", model.resolve_conflict))


func _build_history() -> void:
	var page := _tab("版本")
	var compare := HFlowContainer.new()
	page.add_child(compare)
	compare.add_child(_from)
	compare.add_child(_to)
	_button(compare, "比较版本", func():
		if _from.item_count and _to.item_count:
			model.compare_versions(int(_from.get_item_metadata(_from.selected)), int(_to.get_item_metadata(_to.selected)))
	)
	page.add_child(_versions)
	_diff.editable = false
	_diff.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_diff.custom_minimum_size.y = 240 * ui_scale
	page.add_child(_diff)


func _build_comments() -> void:
	var page := _tab("评论")
	page.add_child(_comments)
	_comment.placeholder_text = "补充建议或提出问题…"
	_comment.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_comment.custom_minimum_size.y = 90 * ui_scale
	var edited := func():
		if not _updating:
			workspace.save_draft("comment:" + model.active_id, {"text": _comment.text})
	_comment.text_changed.connect(edited)
	_comment.text_set.connect(edited)
	page.add_child(_comment)
	_post = _button(page, "发表评论", _post_comment)


func _build_sharing() -> void:
	var page := _tab("共享")
	_visibility.add_item("工作空间可见")
	_visibility.add_item("仅自己与指定成员")
	page.add_child(_visibility)
	_button(page, "更新可见性", func(): model.action(HTTPClient.METHOD_PATCH, "/visibility", {"visibility": "private" if _visibility.selected == 1 else "tenant"}))
	page.add_child(_shares)
	_share_user.placeholder_text = "成员用户 ID"
	page.add_child(_share_user)
	_share_permission.add_item("可阅读")
	_share_permission.add_item("可编辑")
	page.add_child(_share_permission)
	_expires.placeholder_text = "到期时间（可选，ISO 8601）"
	page.add_child(_expires)
	_button(page, "添加或更新共享", func():
		if not _share_user.text.strip_edges().is_empty():
			model.action(HTTPClient.METHOD_POST, "/shares", {"user_id": _share_user.text.strip_edges(), "permission": "write" if _share_permission.selected == 1 else "read", "expires_at": null if _expires.text.strip_edges().is_empty() else _expires.text.strip_edges()}, "shares")
	)


func _ask(text: String, action: Callable) -> void:
	_confirmed = action
	_confirm.dialog_text = text
	_confirm.popup_centered()


func _save_draft() -> void:
	if not _updating:
		model.update_draft(_title.text, _body.text)


func _position_after(position: Vector2i, text: String) -> Vector2i:
	var lines := text.split("\n")
	return Vector2i(position.x + lines.size() - 1, lines[-1].length() + (position.y if lines.size() == 1 else 0))


func _format_selection(before: String, after: String, placeholder: String) -> void:
	if not model.editable():
		return
	var selected := _body.get_selected_text() if _body.has_selection() else placeholder
	var start := Vector2i(_body.get_selection_from_line(), _body.get_selection_from_column()) if _body.has_selection() else Vector2i(_body.get_caret_line(), _body.get_caret_column())
	_body.begin_complex_operation()
	_body.insert_text_at_caret(before + selected + after)
	_body.end_complex_operation()
	var first := _position_after(start, before)
	var last := _position_after(first, selected)
	_body.select(first.x, first.y, last.x, last.y)
	_body.grab_focus()
	_save_draft()


func _post_comment() -> void:
	if _post.disabled or _comment.text.strip_edges().is_empty():
		return
	_post.disabled = true
	var id: String = model.active_id
	var submitted := _comment.text
	var result: Dictionary = await model.action(HTTPClient.METHOD_POST, "/comments", {"body": submitted.strip_edges()}, "comments")
	if result.status == 200 and id == model.active_id and workspace.load_draft("comment:" + id).get("text", "") == submitted:
		workspace.clear_draft("comment:" + id)
	_post.disabled = false


func _tab_changed(index: int) -> void:
	if index == 2:
		model.load_details("versions")
	elif index == 3:
		model.load_details("comments")
	elif index == 4:
		model.load_details("shares")
	elif index == 5:
		model.load_details("external-links")
		model.load_details("links")


func _mapped_offset(previous: String, current: String, offset: int) -> int:
	var prefix := 0
	while prefix < mini(previous.length(), current.length()) and previous[prefix] == current[prefix]:
		prefix += 1
	var suffix := 0
	while suffix < mini(previous.length(), current.length()) - prefix and previous[previous.length() - suffix - 1] == current[current.length() - suffix - 1]:
		suffix += 1
	if offset <= prefix:
		return offset
	if offset >= previous.length() - suffix:
		return offset + current.length() - previous.length()
	return mini(offset, current.length() - suffix)


func _offset(editor: TextEdit, line: int, column: int) -> int:
	var result := column
	for index in line:
		result += editor.get_line(index).length() + 1
	return result


func _sync_text(editor: TextEdit, value: String, switched: bool) -> void:
	if editor.text == value:
		return
	var previous := editor.text
	var carets := []
	for index in editor.get_caret_count():
		carets.append({"caret": _offset(editor, editor.get_caret_line(index), editor.get_caret_column(index)), "selected": editor.has_selection(index), "from": _offset(editor, editor.get_selection_from_line(index), editor.get_selection_from_column(index)), "to": _offset(editor, editor.get_selection_to_line(index), editor.get_selection_to_column(index))})
	var vertical := editor.scroll_vertical
	var horizontal := editor.scroll_horizontal
	editor.text = value
	# A remote/merged snapshot is the new editing baseline, not an undoable local edit.
	editor.clear_undo_history()
	if switched:
		return
	for index in carets.size():
		var state: Dictionary = carets[index]
		var caret := _position_after(Vector2i.ZERO, value.substr(0, _mapped_offset(previous, value, state.caret)))
		var restored := 0
		if index == 0:
			editor.set_caret_line(caret.x, false)
			editor.set_caret_column(caret.y, false)
		else:
			restored = editor.add_caret(caret.x, caret.y)
			if restored < 0:
				continue
		if state.selected:
			var start := _position_after(Vector2i.ZERO, value.substr(0, _mapped_offset(previous, value, state.from)))
			var end := _position_after(Vector2i.ZERO, value.substr(0, _mapped_offset(previous, value, state.to)))
			editor.select(start.x, start.y, end.x, end.y, restored)
	editor.scroll_vertical = vertical
	editor.scroll_horizontal = horizontal


func _sync_title(value: String, switched: bool) -> void:
	if _title.text == value:
		return
	var previous := _title.text
	var caret := _title.caret_column
	var selected := _title.has_selection()
	var start := _title.get_selection_from_column() if selected else caret
	var end := _title.get_selection_to_column() if selected else caret
	_title.text = value
	if not switched:
		_title.caret_column = _mapped_offset(previous, value, caret)
		if selected:
			_title.select(_mapped_offset(previous, value, start), _mapped_offset(previous, value, end))


func _changed() -> void:
	_updating = true
	var context: String = workspace.session.scope_key() + ":" + model.active_id
	var switched := context != _context
	if switched:
		_context = context
		_confirm.hide()
		_export.hide()
		_confirmed = Callable()
		_share_user.clear()
		_expires.clear()
	_status.text = tr(model.status)
	if model.collaborators.size() > 1:
		_status.text += tr(" · %d 人在线协作") % model.collaborators.size()
	var local: Dictionary = model.draft()
	var shown: Dictionary = model.document if local.is_empty() else local
	var title := str(shown.get("title", ""))
	var body := str(shown.get("body_md", ""))
	_sync_title(title, switched)
	_sync_text(_body, body, switched)
	_preview.set_markdown("# " + title + "\n\n" + body if not title.is_empty() else tr("选择一份文档，或创建新的设计。"))
	_edit_preview.set_markdown(body)
	_title.editable = model.editable()
	_body.editable = model.editable()
	for button in _format_buttons:
		button.disabled = not model.editable()
	_save.disabled = not model.editable() or local.is_empty() or not model.conflict.is_empty()
	_discard.disabled = not model.editable() or local.is_empty()
	_remote.visible = not model.conflict.is_empty()
	_resolve.visible = _remote.visible
	_remote.text = tr("服务器版本 · %s · v%d\n\n%s") % [model.conflict.get("title", ""), int(model.conflict.get("version", 0)), model.conflict.get("body_md", "")]
	_visibility.select(1 if model.document.get("visibility") == "private" else 0)
	var comment_draft: Dictionary = workspace.load_draft("comment:" + model.active_id)
	_sync_text(_comment, str(comment_draft.get("text", "")), switched)
	_render_list()
	_render_details()
	_updating = false


func _render_list(force := false) -> void:
	var signature := JSON.stringify([model.documents, model.active_id, _filter.text])
	if not force and signature == _list_signature:
		return
	_list_signature = signature
	var previous := _updating
	_updating = true
	_tree.clear()
	_picker.clear()
	_picker.add_item("新文档")
	_picker.set_item_metadata(0, "")
	var root := _tree.create_item()
	var groups := {}
	for doc in model.documents:
		if not _filter.text.is_empty() and not (str(doc.title) + str(doc.get("kind", "")) + str(doc.get("status", ""))).to_lower().contains(_filter.text.to_lower()):
			continue
		var kind := str(doc.get("kind", "文档"))
		if not groups.has(kind):
			groups[kind] = _tree.create_item(root)
			groups[kind].set_text(0, kind)
			groups[kind].set_selectable(0, false)
		var item := _tree.create_item(groups[kind])
		item.set_text(0, str(doc.title))
		item.set_auto_translate_mode(0, Node.AUTO_TRANSLATE_MODE_DISABLED)
		item.set_tooltip_text(0, "%s · v%d · %s" % [doc.title, int(doc.version), doc.status])
		item.set_metadata(0, doc.id)
		_picker.add_item(str(doc.title))
		_picker.set_item_auto_translate_mode(_picker.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		_picker.set_item_metadata(_picker.item_count - 1, doc.id)
		if doc.id == model.active_id:
			item.select(0)
			_picker.select(_picker.item_count - 1)
	_updating = previous


func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()


func _note(parent: Node, text: String) -> void:
	var label := Label.new()
	label.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(label)


func _render_details() -> void:
	var signature := JSON.stringify([model.active_id, model.detail])
	if signature == _detail_signature:
		return
	_detail_signature = signature
	for container in [_versions, _comments, _shares, _links]:
		_clear(container)
	_from.clear()
	_to.clear()
	for version in model.detail.get("versions", {}).get("versions", []):
		for picker in [_from, _to]:
			picker.add_item("v%d" % int(version.version))
			picker.set_item_metadata(picker.item_count - 1, version.version)
		var row := HFlowContainer.new()
		_versions.add_child(row)
		_note(row, "v%d · %s · %s" % [int(version.version), version.author, version.created_at])
		if int(version.version) < int(model.document.get("version", 0)):
			var id: String = model.active_id
			var expected: int = model.document.version
			_button(row, "恢复此版本", func():
				_ask(tr("恢复 v%d 为新的文档版本？现有历史会保留。") % int(version.version), func():
					if model.active_id == id:
						model.action(HTTPClient.METHOD_POST, "/versions/%d/restore" % int(version.version), {"expected_version": expected}, "versions")
				)
			)
	if _to.item_count:
		_to.select(_to.item_count - 1)
		_from.select(maxi(0, _from.item_count - 2))
	_diff.text = str(model.detail.get("diff", ""))
	for comment in model.detail.get("comments", {}).get("comments", []):
		_note(_comments, "%s · %s%s\n%s" % [comment.author, comment.created_at, tr(" · 已解决") if comment.resolved else "", comment.body])
		_button(_comments, "重新打开" if comment.resolved else "标记解决", func(): model.resolve_comment(str(comment.id), not comment.resolved))
	for share in model.detail.get("shares", {}).get("shares", []):
		_note(_shares, "%s · %s · %s" % [share.user_id, tr("可编辑") if share.permission == "write" else tr("可阅读"), str(share.get("expires_at", tr("长期")))])
		_button(_shares, tr("撤销此共享"), func(): _ask(tr("撤销此成员对文档的共享权限？"), func(): model.action(HTTPClient.METHOD_DELETE, "/shares/" + str(share.user_id).uri_encode(), {}, "shares")))
	for link in model.detail.get("external-links", {}).get("links", []):
		_note(_links, "%s · %s" % [link.get("system", link.get("provider", tr("来源"))), link.get("external_id", "")])
		var url := str(link.get("url", ""))
		if url.begins_with("https://") or url.begins_with("http://"):
			_button(_links, "打开来源", func(): OS.shell_open(url))
	for group in ["outgoing", "backlinks"]:
		for link in model.detail.get("links", {}).get(group, []):
			var id := str(link.get("doc_id", link.get("id", "")))
			if not id.is_empty():
				_button(_links, str(link.get("title", link.get("target", id))), func(): model.open(id))


func _responsive() -> void:
	var narrow := bool(get_meta("compact", false)) or size.x < 820 * ui_scale
	_tree.visible = not narrow
	_picker.visible = narrow
	_edit_columns.vertical = narrow
	_body.visible = _editor_mode.selected != 2
	_edit_preview_scroll.visible = _editor_mode.selected != 1


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_detail_signature = ""
		_list_signature = ""
		_changed()
