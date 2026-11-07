@tool
extends VBoxContainer

signal confirmation_requested(token: String)
signal status_changed(message: String)
signal operation_checked

var confirming_token := ""

var details_title := Label.new()
var details_location := Label.new()
var details_document := RichTextLabel.new()
var details_command := TextEdit.new()
var details_confirm: Button
var details_token := ""


func _button(parent: Control, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func build() -> void:
	name = "OperationDetails"
	set_meta("ai_control_exclude", true)
	custom_minimum_size.x = 320
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_stretch_ratio = 0.65
	hide()
	var header := HBoxContainer.new()
	add_child(header)
	details_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	header.add_child(details_title)
	_button(header, "关闭", dismiss)
	details_command.editable = false
	details_command.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	details_command.custom_minimum_size.y = 96
	add_child(details_command)
	details_location.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(details_location)
	details_document.size_flags_vertical = Control.SIZE_EXPAND_FILL
	details_document.selection_enabled = true
	add_child(details_document)


func dismiss() -> void:
	if is_instance_valid(details_confirm):
		remove_child(details_confirm)
		details_confirm.queue_free()
		details_confirm = null
	details_token = ""
	hide()
	details_document.clear()
	details_command.clear()


func display(item: Dictionary, op: Dictionary, render: Callable) -> void:
	dismiss()
	var token: String = op.token
	details_confirm = _button(self, "确认执行", func():
		if details_token == token:
			confirmation_requested.emit(token))
	details_token = token
	details_title.text = "#%s · 等待你确认 · %s" % [item.number, op.summary]
	details_command.text = op.detail
	show()
	var doc: Dictionary = item.get("design_document", {})
	var markdown: String = doc.get("markdown", "")
	details_document.clear()
	if markdown.is_empty():
		details_location.text = "此工单尚无可读取的设计文档"
		return
	var lines := markdown.split("\n")
	var anchor := _document_anchor(lines, op)
	details_location.text = "%s · %s" % [doc.path, doc.source]
	if anchor < 0:
		details_location.text += "\n此节点尚未关联文档位置"
		render.call(details_document, markdown)
		return
	if anchor > 0:
		render.call(details_document, "\n".join(lines.slice(0, anchor)))
	var end := anchor + 1
	while end < lines.size() and not lines[end].strip_edges().is_empty() and not lines[end].begins_with("#"):
		end += 1
	var paragraph := details_document.get_paragraph_count() - 1
	details_document.push_bgcolor(Color("#825921"))
	render.call(details_document, "\n".join(lines.slice(anchor, end)))
	details_document.pop()
	if end < lines.size():
		render.call(details_document, "\n".join(lines.slice(end)))
	await get_tree().process_frame
	if token == details_token:
		details_document.scroll_to_paragraph(paragraph)


func _document_anchor(lines: PackedStringArray, op: Dictionary) -> int:
	# Explicit node anchors identify a stable operation kind, independent of translated labels.
	var marker := "<!-- daqian-node:%s -->" % op.tool
	var fenced := false
	var explicit := false
	var candidate := -1
	for i in lines.size():
		var line := lines[i].strip_edges()
		if line.begins_with("```"):
			fenced = not fenced
			continue
		if fenced or line.is_empty():
			continue
		if line == marker:
			explicit = true
			continue
		if explicit:
			return i
		var heading := line.trim_prefix("#").lstrip("#").strip_edges()
		if line.begins_with("#") and heading == op.summary:
			candidate = i
		elif candidate < 0 and line.begins_with("#") and heading in ["原始需求", "原始需求与目标"] and op.tool == "run_command" and "issue_gate.py" in op.detail and "--intake-only" in op.detail:
			candidate = i
	return candidate


func matching_operation(item: Dictionary, op: Dictionary, root: String, user_id: String) -> Dictionary:
	if op.is_empty() or op.root != root or op.actor != user_id or op.url != item.get("url") or op.request != item.get("request") or op.source_sha256 != item.get("source_sha256", ""):
		return {}
	return op


func confirm(token: String, binding: Callable, fetch_board: Callable, pending: Callable, execute: Callable) -> void:
	var origin: Dictionary = binding.call()
	if token.is_empty() or token != origin.token or confirming_token == token:
		return
	confirming_token = token
	status_changed.emit("正在核对工单和本次操作…")
	var verified: Dictionary = await fetch_board.call(false, origin.actor.user_id)
	if confirming_token == token:
		confirming_token = ""
	if binding.call() != origin:
		return
	var latest: Dictionary = verified.get("board", {})
	if latest.get("repo_id") == origin.actor.repo_id and latest.get("user_id") == origin.actor.user_id:
		for row in latest.get("issues", []):
			if row.url == origin.url and row.updated == origin.updated and pending.call(row).get("token", "") == token:
				status_changed.emit("已核实工单，正在执行所选操作。")
				if not execute.call(token):
					status_changed.emit("这项操作已结束或发生变化，请核对当前节点。")
				operation_checked.emit()
				return
	status_changed.emit(str(verified.get("error", "工单状态或本次操作有变，请刷新后核对。")))
