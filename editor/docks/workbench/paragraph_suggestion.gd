@tool
extends ConfirmationDialog

var view: AcceptDialog
var open_button := Button.new()
var instruction := LineEdit.new()
var generate := Button.new()
var preview := TextEdit.new()
var status := Label.new()
var paragraph := 0
var ticket := 0
var candidate := ""
var prepared := {}
var conflict := {}
var resolving := false
var decision_base := ""
var choices := VBoxContainer.new()
var baseline := Label.new()
var human := Label.new()
var decision := OptionButton.new()
var custom_text := TextEdit.new()


func _ready() -> void:
	name = "WorkbenchParagraphSuggestion"
	title = "修改所选段落"
	dialog_hide_on_ok = false
	get_ok_button().text = "接受并保存"
	get_cancel_button().text = "取消"
	confirmed.connect(_accept)
	canceled.connect(_reset)
	open_button.text = "修改所选段落"
	open_button.name = "SuggestDocumentParagraph"
	open_button.pressed.connect(_open)
	view.actions.add_child(open_button)
	view.target_changed.connect(_reset)
	view.visibility_changed.connect(_view_visibility_changed)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(480, 260) * EditorInterface.get_editor_scale()
	add_child(box)
	instruction.placeholder_text = "描述希望怎样修改这一段"
	instruction.max_length = 4000
	instruction.text_changed.connect(_instruction_changed)
	box.add_child(instruction)
	generate.text = "生成段落建议"
	generate.pressed.connect(_generate)
	box.add_child(generate)
	preview.editable = false
	preview.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	preview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(preview)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)
	box.add_child(choices)
	for label: Label in [baseline, human]:
		label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
		choices.add_child(label)
	choices.add_child(decision)
	decision.add_item("保留人的版本")
	decision.add_item("选用上方 AI 片段")
	decision.add_item("直接写第三版")
	decision.item_selected.connect(_choose)
	custom_text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	custom_text.custom_minimum_size.y = 70
	choices.add_child(custom_text)
	_reset()


func _view_visibility_changed() -> void:
	if not view.visible:
		_reset()


func _reset() -> void:
	ticket += 1
	paragraph = 0
	candidate = ""
	prepared.clear()
	conflict.clear()
	resolving = false
	decision_base = ""
	choices.hide()
	baseline.text = ""
	human.text = ""
	custom_text.clear()
	get_ok_button().text = "接受并保存"
	hide()
	instruction.clear()
	preview.clear()
	status.text = ""


func _open() -> void:
	_reset()
	paragraph = view.sync_selected_paragraph()
	if paragraph == 0:
		view.status.text = "请从段落列表选择一段，或在正文中完整选中一段。"
		return
	title = "修改第 %d 段 · v%d" % [paragraph, view.reference.version]
	get_ok_button().disabled = true
	instruction.editable = true
	generate.disabled = true
	popup_centered()
	instruction.grab_focus()


func _instruction_changed(value: String) -> void:
	ticket += 1
	candidate = ""
	prepared.clear()
	preview.clear()
	status.text = ""
	get_ok_button().disabled = true
	generate.disabled = value.strip_edges().is_empty()


func _current(attempt: int) -> bool:
	if attempt != ticket or not visible:
		return false
	if paragraph != view.selected_paragraph() or view.reference.is_empty():
		_reset()
		view.status.text = "选区已改变，请重新选择要修改的段落。"
		return false
	return true


func _route() -> String:
	return "/api/v1/docs/" + str(view.reference.document_id).uri_encode()


func _generate() -> void:
	if generate.disabled or not _current(ticket):
		return
	ticket += 1
	var attempt := ticket
	get_ok_button().disabled = true
	generate.disabled = true
	candidate = ""
	preview.clear()
	status.text = "正在生成建议…"
	var payload := {"expected_version": view.reference.version, "paragraph": paragraph, "instruction": instruction.text}
	var reply: Dictionary = await view.session.api_request(HTTPClient.METHOD_POST, _route() + "/paragraph-suggestion", payload, 40.0)
	if not _current(attempt):
		return
	if reply.status == 409:
		status.text = "修订已改变。请重开最新修订，再生成建议。"
		instruction.editable = false
		return
	generate.disabled = false
	if reply.status != 200:
		status.text = "生成失败（%d）。可再次生成建议。" % reply.status
		return
	var data: Dictionary = reply.data
	var span: Vector2i = view.raw_spans[paragraph - 1]
	var original: String = view.raw_body.substr(span.x, span.y - span.x)
	if data.get("document_id") != view.reference.document_id or data.get("expected_version") != view.reference.version or data.get("paragraph") != paragraph or data.get("original") != original or not data.get("replacement") is String:
		status.text = "建议与所选段落不符，请重新生成。"
		return
	var replacement: String = data.replacement
	for line in replacement.replace("\r\n", "\n").split("\n"):
		if line.strip_edges().is_empty():
			status.text = "建议包含空段落，请重新生成。"
			return
	if data.get("candidate_body") != view.raw_body.left(span.x) + replacement + view.raw_body.substr(span.y):
		status.text = "建议包含所选段落以外的更改，请重新生成。"
		return
	candidate = data.candidate_body
	preview.text = replacement
	status.text = "请审阅以上建议。接受后将保存为新修订。"
	get_ok_button().disabled = false


func _choose(index: int) -> void:
	custom_text.visible = index == 2
	get_ok_button().disabled = false


func _show_conflict(data: Dictionary, base_version: int) -> bool:
	var sections: Variant = data.get("sections")
	if data.get("status") != "conflict" or not sections is Array or sections.size() != 1 or not sections[0] is Dictionary:
		return false
	var part: Dictionary = sections[0]
	for key in ["before", "base", "local", "remote", "after"]:
		if not part.get(key) is String:
			return false
	if part.before + part.remote + part.after != data.get("remote_md") or int(data.get("remote_version", 0)) <= base_version:
		return false
	resolving = true
	decision_base = data.remote_md
	conflict = part.duplicate(true)
	conflict.version = int(data.remote_version)
	prepared.clear()
	baseline.text = "基线 v%d\n%s" % [base_version, part.base]
	human.text = "人的当前版 v%d\n%s" % [int(conflict.version), part.remote]
	preview.text = part.local
	custom_text.text = part.remote
	choices.show()
	decision.disabled = false
	decision.select(-1)
	custom_text.hide()
	custom_text.editable = true
	get_ok_button().text = "确认解决并保存"
	get_ok_button().disabled = true
	status.text = "同一段发生冲突。请核对基线、人的当前版和上方 AI 片段。"
	return true


func _accept() -> void:
	if get_ok_button().disabled or candidate.is_empty() or not _current(ticket):
		return
	var attempt := ticket
	if prepared.is_empty():
		var version: int = view.reference.version
		var body := candidate
		if not conflict.is_empty():
			if decision.selected < 0:
				return
			var replacement: String = conflict.remote
			if decision.selected == 1:
				replacement = conflict.local
			elif decision.selected == 2:
				replacement = custom_text.text
				if "\r\n" in str(conflict.remote):
					replacement = replacement.replace("\n", "\r\n")
			body = conflict.before + replacement + conflict.after
			version = conflict.version
			decision.disabled = true
			custom_text.editable = false
		prepared = {"expected_version": version, "body_md": body, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
	get_ok_button().disabled = true
	generate.disabled = true
	instruction.editable = false
	status.text = "正在保存…"
	var reply: Dictionary = await view.session.api_request(HTTPClient.METHOD_PATCH, _route(), prepared)
	if not _current(attempt):
		return
	if reply.status == 409 and resolving:
		# Reconcile the human's confirmed decision against the revision they saw.
		var reviewed_version := int(prepared.expected_version)
		var check: Dictionary = await view.session.api_request(HTTPClient.METHOD_POST, _route() + "/merge/preview", {
			"expected_version": reviewed_version, "base_md": decision_base, "local_md": prepared.body_md,
		})
		if not _current(attempt):
			return
		if check.status == 409 and _show_conflict(check.data, reviewed_version):
			return
		if check.status == 200 and check.data.get("status") == "ready" and check.data.get("remote_md") is String and check.data.get("body_md") is String and int(check.data.get("remote_version", 0)) > reviewed_version:
			decision_base = check.data.remote_md
			prepared = {"expected_version": int(check.data.remote_version), "body_md": check.data.body_md, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
			choices.hide()
			preview.text = prepared.body_md
			status.text = "确认期间有新修订。请审阅基于 v%d 的完整结果，再确认保存。" % int(prepared.expected_version)
		else:
			status.text = "无法核对最新修订。可再次点击确认重试。"
		get_ok_button().disabled = false
		return
	if reply.status == 409 and candidate != view.raw_body:
		var merge: Dictionary = await view.session.api_request(HTTPClient.METHOD_POST, _route() + "/merge/preview", {
			"expected_version": view.reference.version, "base_md": view.raw_body, "local_md": candidate,
		})
		if not _current(attempt):
			return
		if merge.status == 200 and merge.data.get("status") == "ready" and merge.data.get("body_md") is String and int(merge.data.get("remote_version", 0)) > int(view.reference.version):
			# Replay this exact compare-and-swap if the separate commit acknowledgement is lost.
			prepared = {"expected_version": int(merge.data.remote_version), "body_md": merge.data.body_md, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
			reply = await view.session.api_request(HTTPClient.METHOD_PATCH, _route(), prepared)
			if not _current(attempt):
				return
			if reply.status == 409:
				prepared.clear()
				status.text = "合并期间有新修订。再次点击接受可保留建议并重新核对。"
				get_ok_button().disabled = false
				return
		elif merge.status == 409 and _show_conflict(merge.data, int(view.reference.version)):
			return
		elif merge.status != 200:
			reply = merge
	var version: int = prepared.expected_version
	var saved: Dictionary = reply.data
	if reply.status == 0 or reply.status >= 500 or (reply.status == 200 and (saved.get("id") != view.reference.document_id or saved.get("version") != version + 1 or not saved.get("title") is String)):
		status.text = "尚未收到保存回执。再次点击接受可核对此次提交。"
		get_ok_button().disabled = false
		return
	if reply.status != 200:
		status.text = "修订已冲突。请重开最新修订，再生成建议。" if reply.status == 409 else "保存失败（%d）。请重开文档。" % reply.status
		return
	var selected := paragraph
	if view.collaboration and view.collaboration.document_id == saved.id:
		view.collaboration.notified_version = maxi(view.collaboration.notified_version, int(saved.version))
	_reset()
	await view.open_saved(saved, selected)
