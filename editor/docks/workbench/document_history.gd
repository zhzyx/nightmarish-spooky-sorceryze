@tool
extends VBoxContainer

var session: Node
var view: AcceptDialog
var dialog := AcceptDialog.new()
var source := OptionButton.new()
var comparison := OptionButton.new()
var diff := TextEdit.new()
var changes := VBoxContainer.new()
var status := Label.new()
var read := Button.new()
var restore := Button.new()
var generation := 0
var document_id := ""
var head := 0
var call_id := ""


func _ready() -> void:
	hide()
	session = get_parent()
	if not session.is_node_ready():
		await session.ready
	view = session.get_node("WorkbenchDocuments")
	view.history.pressed.connect(_open)
	view.revision_cleared.connect(dialog.hide)
	view.visibility_changed.connect(_view_visibility_changed)
	dialog.title = "版本历史"
	dialog.get_ok_button().text = "关闭"
	dialog.visibility_changed.connect(_visibility_changed)
	view.add_child(dialog)
	var fields := VBoxContainer.new()
	fields.custom_minimum_size = Vector2(510, 320) * EditorInterface.get_editor_scale()
	dialog.add_child(fields)
	var row := HBoxContainer.new()
	fields.add_child(row)
	for entry: Array in [["原修订", source], ["对比修订", comparison]]:
		var label := Label.new()
		label.text = entry[0]
		row.add_child(label)
		row.add_child(entry[1])
		entry[1].item_selected.connect(_compare)
	diff.name = "RevisionDiff"
	diff.editable = false
	diff.size_flags_vertical = Control.SIZE_EXPAND_FILL
	fields.add_child(diff)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.y = 68 * EditorInterface.get_editor_scale()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	changes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	changes.name = "ChangedParagraphs"
	scroll.add_child(changes)
	fields.add_child(scroll)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(status)
	var actions := HBoxContainer.new()
	fields.add_child(actions)
	read.text = "阅读原修订"
	read.pressed.connect(_read_revision)
	actions.add_child(read)
	restore.text = "恢复原修订为新版本"
	restore.pressed.connect(_restore)
	actions.add_child(restore)


func _view_visibility_changed() -> void:
	if not view.visible:
		dialog.hide()


func _visibility_changed() -> void:
	if dialog.visible:
		return
	generation += 1
	document_id = ""
	call_id = ""
	source.clear()
	comparison.clear()
	diff.clear()
	_clear_changes()
	status.text = ""


func _route() -> String:
	return "/api/v1/docs/" + document_id.uri_encode()


func _open() -> void:
	if view.reference.is_empty() or dialog.visible:
		return
	generation += 1
	var attempt := generation
	document_id = view.reference.document_id
	dialog.title = "版本历史 · " + document_id
	dialog.popup_centered()
	head = 0
	read.disabled = true
	restore.disabled = true
	source.disabled = true
	comparison.disabled = true
	restore.text = "恢复原修订为新版本"
	status.text = "正在读取版本历史…"
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, _route() + "/versions")
	if attempt != generation:
		return
	if reply.status != 200 or not reply.data.get("versions") is Array:
		status.text = "无法读取版本历史。请重开后重试。"
		return
	for revision: Dictionary in reply.data.versions:
		var version := int(revision.version)
		head = maxi(head, version)
		source.add_item("v%d" % version, version)
		comparison.add_item("v%d" % version, version)
	if head == 0:
		status.text = "此文档没有修订。"
		return
	var selected := int(view.reference.version)
	if selected == head and source.item_count > 1:
		selected = source.get_item_id(source.get_item_index(head) - 1)
	source.select(source.get_item_index(selected))
	comparison.select(comparison.get_item_index(head))
	source.disabled = false
	comparison.disabled = false
	read.disabled = false
	_compare(0)


func _compare(_index: int) -> void:
	if source.disabled or not dialog.visible:
		return
	generation += 1
	var attempt := generation
	diff.clear()
	_clear_changes()
	restore.disabled = true
	var before := source.get_selected_id()
	var after := comparison.get_selected_id()
	status.text = "正在比较 v%d 与 v%d…" % [before, after]
	var route := _route() + "/diff?from_version=%d&to_version=%d&paragraphs=true" % [before, after]
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
	if attempt != generation:
		return
	if reply.status != 200 or not reply.data.get("diff") is String or not reply.data.get("changes") is Array or int(reply.data.get("from_version", 0)) != before or int(reply.data.get("to_version", 0)) != after:
		status.text = "无法读取所选修订的差异。"
		return
	diff.text = reply.data.diff
	# Skip the two file headers; content lines in unified hunks carry one prefix.
	for line in range(2, diff.get_line_count()):
		var prefix := diff.get_line(line).left(1)
		if prefix == "+" or prefix == "-":
			var tint := get_theme_color("success_color" if prefix == "+" else "error_color", "Editor")
			diff.set_line_background_color(line, Color(tint, 0.22))
	for change: Dictionary in reply.data.changes:
		var removed: bool = change.after == null
		var paragraph := int(change.before if removed else change.after)
		var version := before if removed else after
		var editable: bool = not removed and reply.data.editable
		var label := "已删除" if removed else ("新增" if change.before == null else "修改")
		var row := Button.new()
		row.text = "%s · v%d 第 %d 段　%s" % [label, version, paragraph, change.preview]
		row.tooltip_text = "编辑此段" if editable else "阅读此段"
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		row.add_theme_color_override("font_color", get_theme_color("accent_color", "Editor"))
		row.pressed.connect(_open_change.bind(document_id, version, paragraph, editable))
		changes.add_child(row)
	status.text = "v%d → v%d · 当前最新 v%d" % [before, after, head]
	if diff.text.is_empty():
		status.text += " · 正文相同"
	# The restore uses exactly the head that the reviewer compared against.
	restore.disabled = before == after or after != head
	if not restore.disabled:
		restore.text = "将 v%d 恢复为新修订 v%d" % [before, head + 1]
	else:
		restore.text = "恢复原修订为新版本"


func _clear_changes() -> void:
	for row in changes.get_children():
		changes.remove_child(row)
		row.queue_free()


func _open_change(id: String, version: int, paragraph: int, editable: bool) -> void:
	if not dialog.visible or document_id != id:
		return
	dialog.hide()
	await view.open_document(id, version, paragraph)
	if editable and view.reference == {"document_id": id, "version": version, "paragraph": paragraph}:
		view.edit_selected_paragraph()


func _read_revision() -> void:
	if read.disabled or not dialog.visible:
		return
	var id := document_id
	var version := source.get_selected_id()
	dialog.hide()
	view.open_document(id, version, 1)


func _restore() -> void:
	if restore.disabled or not dialog.visible:
		return
	var attempt := generation
	var before := source.get_selected_id()
	var expected := comparison.get_selected_id()
	if call_id.is_empty():
		call_id = Crypto.new().generate_random_bytes(16).hex_encode()
	var payload := {"expected_version": expected, "call_id": call_id}
	source.disabled = true
	comparison.disabled = true
	restore.disabled = true
	read.disabled = true
	_clear_changes()
	status.text = "正在恢复 v%d…" % before
	var route := _route() + "/versions/%d/restore" % before
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route, payload)
	if attempt != generation:
		return
	var saved: Dictionary = reply.data
	if reply.status == 200 and saved.get("id") == document_id and int(saved.get("version", 0)) == expected + 1:
		dialog.hide()
		await view.open_saved(saved)
		return
	if reply.status in [0, 200] or reply.status >= 500:
		status.text = "恢复回执待确认，请重试同一请求。"
		restore.text = "重试此次恢复"
		restore.disabled = false
		return
	call_id = ""
	read.disabled = false
	if reply.status == 409:
		status.text = "文档已更新。请重开版本历史，审阅最新修订后再恢复。"
	else:
		status.text = "恢复失败（%d）。请核对权限后重开版本历史。" % reply.status
