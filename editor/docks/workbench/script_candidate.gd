@tool
extends Button

var panel
var dialog := ConfirmationDialog.new()
var diff := TextEdit.new()
var status := Label.new()
var reviewed := {}


func _ready() -> void:
	name = "ReviewScriptCandidate"
	text = "查看脚本候选差异"
	pressed.connect(_review)
	dialog.title = "将候选应用到最后保存的脚本"
	dialog.get_ok_button().text = "接受并保存"
	dialog.dialog_hide_on_ok = false
	dialog.confirmed.connect(_apply)
	add_child(dialog)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(510, 240) * EditorInterface.get_editor_scale()
	dialog.add_child(box)
	diff.editable = false
	diff.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(diff)
	box.add_child(status)
	hide()


func _candidate() -> Dictionary:
	var turns: Array = panel.conversation.get("turns", [])
	if not panel.consultation_detail.is_empty() or turns.is_empty() or not panel.saved_changes or panel.location.get("conversation_id") != panel.conversation.get("id"):
		return {}
	var turn: Dictionary = turns.back()
	var snapshot: Dictionary = turn.get("context_snapshot", {})
	if turn.get("state") != "answered" or not snapshot.has("continuation") or not turn.get("answer") is String:
		return {}
	var parser := JSON.new()
	if parser.parse(turn.answer) != OK or not parser.data is Dictionary:
		return {}
	var edit: Dictionary = parser.data
	for field in ["object_id", "revision", "original", "replacement"]:
		if not edit.get(field) is String:
			return {}
	if edit.original == "" or edit.original == edit.replacement or edit.replacement.length() > 16000:
		return {}
	var ref := {"kind":"editor", "object_id":edit.object_id, "revision":edit.revision}
	if not snapshot.get("references", []).has(ref) or not panel.saved_changes.targets.has(edit.object_id):
		return {}
	var path: String = panel.saved_changes.local_path(edit.object_id)
	if path.get_extension() != "gd":
		return {}
	return {"path":path, "edit":edit, "turn":turn.id, "chat":panel.conversation.id, "generation":panel.identity_generation}


func refresh() -> void:
	visible = not _candidate().is_empty()
	if dialog.visible:
		dialog.hide()
	reviewed.clear()


func _prepare() -> Dictionary:
	var candidate := _candidate()
	var editor := EditorInterface.get_script_editor()
	var script := editor.get_current_script()
	if candidate.is_empty() or not script or script.resource_path != candidate.path:
		return {}
	var code := editor.get_current_editor().get_base_editor() as CodeEdit
	if not code:
		return {}
	var file := FileAccess.open(candidate.path, FileAccess.READ)
	if file == null or file.get_length() > 1024 * 1024:
		return {}
	var length := file.get_length()
	var bytes := file.get_buffer(length)
	file.close()
	var source := bytes.get_string_from_utf8().replace("\r\n", "\n")
	if bytes.size() != length or source != code.text:
		return {}
	var checksum := HashingContext.new()
	checksum.start(HashingContext.HASH_SHA256)
	checksum.update(bytes)
	var edit: Dictionary = candidate.edit
	var pattern := RegEx.new()
	pattern.compile("#L([0-9]+):([0-9]+)-L([0-9]+):([0-9]+)$")
	var match_range := pattern.search(edit.object_id)
	if not match_range:
		return {}
	var start := Vector2i(int(match_range.get_string(2))-1, int(match_range.get_string(1))-1)
	var end := Vector2i(int(match_range.get_string(4))-1, int(match_range.get_string(3))-1)
	if start.y < 0 or end.y < start.y or end.y >= code.get_line_count() or start.x < 0 or start.x > code.get_line(start.y).length() or end.x < 0 or end.x > code.get_line(end.y).length():
		return {}
	var from := 0
	for line in start.y:
		from += code.get_line(line).length() + 1
	from += start.x
	var to := from - start.x + end.x
	for line in range(start.y, end.y):
		to += code.get_line(line).length() + 1
	if to < from or source.substr(from, to - from) != edit.original:
		return {}
	candidate.merge({"start":start, "end":end, "disk":checksum.finish().hex_encode(),
		"expected":(source.left(from) + edit.replacement + source.substr(to)).sha256_text()})
	return candidate


func _review() -> void:
	reviewed = _prepare()
	diff.text = ""
	status.text = "请打开引用的脚本并保存修改。选区发生冲突时，请重新生成候选。"
	if not reviewed.is_empty():
		diff.text = "- " + reviewed.edit.original.replace("\n", "\n- ") + "\n+ " + reviewed.edit.replacement.replace("\n", "\n+ ")
		status.text = "%s · %s" % [reviewed.edit.object_id, reviewed.disk.left(12)]
	dialog.get_ok_button().disabled = reviewed.is_empty()
	dialog.popup_centered()


func _apply() -> void:
	if reviewed.is_empty() or reviewed != _prepare():
		status.text = "脚本或会话已改变，请重新查看差异。"
		dialog.get_ok_button().disabled = true
		return
	var editor := EditorInterface.get_script_editor()
	var code := editor.get_current_editor().get_base_editor() as CodeEdit
	code.remove_secondary_carets()
	code.select(reviewed.start.y, reviewed.start.x, reviewed.end.y, reviewed.end.x)
	code.insert_text_at_caret(reviewed.edit.replacement)
	editor.save_current_script()
	dialog.get_ok_button().disabled = true
	if FileAccess.get_file_as_string(reviewed.path).replace("\r\n", "\n").sha256_text() == reviewed.expected:
		dialog.hide()
		panel._notice("已保存脚本候选 " + FileAccess.get_sha256(reviewed.path).left(12))
	else:
		status.text = "磁盘内容与已确认的差异不一致，请检查脚本编辑器。"
