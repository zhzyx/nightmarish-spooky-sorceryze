@tool
extends VBoxContainer

var detail: Node
var session: Node
var generation := 0
var browse := Button.new()
var rows := VBoxContainer.new()
var panel := VBoxContainer.new()
var description := Label.new()
var recipients := OptionButton.new()
var note := LineEdit.new()
var transfer := Button.new()
var approve := Button.new()
var revise := Button.new()
var status := Label.new()
var selected := {}
var work_version := 0
var edit_original := Button.new()
var save_original := Button.new()
var local_original := ""
var original_editor: ScriptEditorBase
var original_digest := ""
var pending_rows: Array = []


func _ready() -> void:
	detail = get_parent()
	session = detail.get_parent()
	browse.name = "MyCreativeJudgments"
	browse.text = "我的待判断事项"
	browse.pressed.connect(_browse)
	add_child(browse)
	rows.name = "PendingJudgmentRows"
	add_child(rows)
	add_child(panel)
	description.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	panel.add_child(description)
	var compare := Button.new()
	compare.text = "比较此工单的候选…"
	compare.pressed.connect(func(): detail.get_node("WorkbenchIssueArtifacts").open_comparison())
	panel.add_child(compare)
	edit_original.text = "在原生文本编辑器打开原件"
	edit_original.pressed.connect(_edit_original)
	panel.add_child(edit_original)
	save_original.text = "保存原件并返回判断项"
	save_original.pressed.connect(_save_original)
	panel.add_child(save_original)
	recipients.name = "JudgmentRecipient"
	panel.add_child(recipients)
	note.name = "JudgmentNote"
	note.placeholder_text = "转交说明或判断意见"
	panel.add_child(note)
	for button: Button in [transfer, approve, revise]:
		panel.add_child(button)
	transfer.name = "TransferJudgment"
	transfer.text = "转交所选成员"
	transfer.pressed.connect(_send.bind("transfer"))
	approve.name = "ApproveJudgment"
	approve.text = "采纳此修订"
	approve.pressed.connect(_send.bind("approved"))
	revise.text = "退回此修订"
	revise.pressed.connect(_send.bind("changes_requested"))
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(status)
	session.identity_changed.connect(_reset)
	session.authenticated.connect(_browse.bind(true))
	detail.detail_changed.connect(_clear_selection)
	_reset()


func _clear_selection() -> void:
	generation += 1
	_close_original()
	selected.clear()
	panel.hide()
	description.text = ""
	recipients.clear()
	note.clear()
	status.text = ""


func _clear_rows() -> void:
	pending_rows.clear()
	for child in rows.get_children():
		rows.remove_child(child)
		child.queue_free()


func _reset() -> void:
	_clear_selection()
	_clear_rows()
	browse.disabled = session.get_identity().is_empty()


func _browse(on_startup := false) -> void:
	_reset()
	var attempt := generation
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/work/my-judgments")
	if generation != attempt:
		return
	if reply.status != 200 or reply.data.get("project") != session.get_identity().project or not reply.data.get("items") is Array:
		if not on_startup:
			status.text = "无法读取本人的待判断事项"
		return
	pending_rows = reply.data.items
	for item: Dictionary in pending_rows:
		var row := Button.new()
		row.text = "#%d %s · %s\n%s" % [int(item.number), item.title, item.path, item.question]
		row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.tooltip_text = "%s @ %s" % [item.module, item.revision]
		row.pressed.connect(_open.bind(item))
		rows.add_child(row)
	if rows.get_child_count() == 0:
		if not on_startup:
			status.text = "暂无待本人判断的事项"
	elif on_startup:
		detail.get_meta("open_linked_sidebar").call()
		# Wait for the dock and newly added rows to receive their actual geometry.
		await get_tree().process_frame
		if generation == attempt:
			rows.get_child(0).grab_focus()


func _open(item: Dictionary, show_revision := true) -> void:
	# Resolving the numbered issue also opens its original design and comment controls.
	await detail.open_issue(int(item.number))
	if detail.get_detail().get("id") != item.issue_id:
		return
	await _inspect(item, show_revision)


func open_compared(ref: Dictionary) -> void:
	var issue: Dictionary = detail.get_detail()
	if issue.is_empty():
		return
	var item := {
		"issue_id": issue.id, "number": issue.number, "question": issue.title, "submission_version": ref.version,
		"kind": ref.kind, "module": ref.module, "revision": ref.revision, "path": ref.path, "digest": ref.digest,
	}
	if issue.get("design_source") is Dictionary:
		item.question = issue.design_source.acceptance
	await _inspect(item, false)


func _matches_reference(event: Dictionary, item: Dictionary) -> bool:
	for key in ["kind", "module", "revision", "path"]:
		if event.get(key) != item[key]:
			return false
	return int(event.get("submission_version", 0)) == int(item.submission_version)


func _inspect(item: Dictionary, show_revision: bool) -> void:
	_clear_selection()
	var attempt := generation
	var route := "/api/v1/issues/%s/work" % str(item.issue_id).uri_encode()
	var work: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
	if generation != attempt:
		return
	if work.status != 200 or work.data.get("id") != item.issue_id:
		status.text = "无法读取此判断项"
		return
	var judgment := {}
	for candidate: Dictionary in work.data.creative_judgments:
		if int(candidate.submission_version) == int(item.submission_version):
			judgment = candidate
			break
	if judgment.is_empty() or not _matches_reference(judgment, item) or judgment.digest != item.get("digest", judgment.digest):
		status.text = "此事项已变化，请重新读取待判断事项"
		return
	var binding := "#%d · 提交 v%d · %s\n%s @ %s" % [int(item.number), int(item.submission_version), item.path, item.module, item.revision]
	if judgment.decision != "pending":
		status.text = "%s\n%s · 签认人 %s\n%s" % [binding, "已采纳" if judgment.decision == "approved" else "已退回", judgment.actor, judgment.get("note", "")]
		return
	if judgment.responsible != session.get_identity().id:
		status.text = "%s\n待 %s 判断" % [binding, judgment.responsible]
		return
	selected = item.duplicate(true)
	original_digest = judgment.digest
	edit_original.visible = str(item.path).get_extension().to_lower() in ["svg", "obj", "gltf"]
	edit_original.disabled = false
	save_original.hide()
	work_version = int(work.data.version)
	description.text = "%s\n%s\n判断人　%s" % [item.question, binding, judgment.responsible]
	for event: Dictionary in work.data.history:
		if int(event.get("submission_version", 0)) == int(item.submission_version) and event.action == "work.transfer":
			description.text += "\n%s → %s  %s" % [event.previous_responsible, event.responsible, event.note]
	panel.show()
	approve.disabled = false
	revise.disabled = false
	transfer.disabled = true
	if show_revision:
		detail.get_node("issue_revisions").open_revision(str(item.module), str(item.revision))
	var users: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/users")
	if attempt != generation:
		return
	if users.status == 200:
		for member: Dictionary in users.data.users:
			if member.id != session.get_identity().id and member.role != "viewer":
				recipients.add_item("%s (%s)" % [member.name, member.email])
				recipients.set_item_metadata(recipients.item_count - 1, member.id)
	transfer.disabled = recipients.item_count == 0


func _close_original() -> void:
	if not local_original.is_empty():
		detail.get_meta("close_original_text").call(local_original)
		DirAccess.remove_absolute(local_original)
	local_original = ""
	original_editor = null
	save_original.hide()


func _exit_tree() -> void:
	if not local_original.is_empty():
		DirAccess.remove_absolute(local_original)


func _edit_original() -> void:
	if selected.is_empty() or edit_original.disabled or not edit_original.visible:
		return
	var attempt := generation
	edit_original.disabled = true
	var temporary := EditorInterface.get_editor_paths().get_cache_dir().path_join("judgment-%s-%s.txt" % [
		Crypto.new().generate_random_bytes(16).hex_encode(), str(selected.path).get_file().validate_filename().left(80)])
	var route := "/api/v1/issues/by-number/%d/artifacts/%d" % [int(selected.number), int(selected.submission_version)]
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route, {}, 15.0, temporary)
	if attempt != generation:
		DirAccess.remove_absolute(temporary)
		return
	if reply.status != 200 or FileAccess.get_sha256(temporary) != original_digest:
		DirAccess.remove_absolute(temporary)
		edit_original.disabled = false
		status.text = "原件读取失败或摘要已变化，请重新读取判断项"
		return
	var file := FileAccess.open(temporary, FileAccess.READ)
	if not file or file.get_length() > 1024 * 1024:
		DirAccess.remove_absolute(temporary)
		edit_original.disabled = false
		status.text = "可编辑的原件最大为 1 MiB"
		return
	file.close()
	if not detail.get_meta("open_original_text").call(temporary):
		DirAccess.remove_absolute(temporary)
		edit_original.disabled = false
		status.text = "原生文本编辑器无法打开此原件"
		return
	local_original = temporary
	original_editor = EditorInterface.get_script_editor().get_current_editor()
	EditorInterface.set_main_screen_editor("Script")
	save_original.disabled = false
	save_original.show()
	status.text = "在文本编辑器中修改 %s，然后保存并返回。" % selected.path


func _save_original() -> void:
	if local_original.is_empty() or save_original.disabled:
		return
	var editor := EditorInterface.get_script_editor()
	if not is_instance_valid(original_editor) or editor.get_current_editor() != original_editor:
		status.text = "请先选择此判断项的原件编辑标签"
		return
	editor.save_current_script()
	var file := FileAccess.open(local_original, FileAccess.READ)
	if not file or file.get_length() > 1024 * 1024:
		status.text = "无法读取已保存的原件，或原件超过 1 MiB"
		return
	var size := file.get_length()
	var bytes := file.get_buffer(size)
	if bytes.size() != size or file.get_length() != size:
		status.text = "原件读取不完整，请重新保存"
		return
	file.close()
	var code := original_editor.get_base_editor() as CodeEdit
	if not code or bytes != code.text.to_utf8_buffer():
		status.text = "编辑器内容和已保存文件不同，请先完成原生保存"
		return
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	if not bytes.is_empty():
		hash.update(bytes)
	var digest := hash.finish().hex_encode()
	if digest == original_digest:
		status.text = "原件尚未修改"
		return
	var attempt := generation
	var item := selected.duplicate(true)
	var route := "/api/v1/issues/by-number/%d/artifacts/%d/edit" % [int(item.number), int(item.submission_version)]
	var payload := {"expected_version": work_version, "revision": item.revision, "content": Marshalls.raw_to_base64(bytes),
		"call_id": ("%s/%s/%s/%s" % [item.issue_id, int(item.submission_version), work_version, digest]).sha256_text()}
	save_original.disabled = true
	code.editable = false
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route, payload)
	if attempt != generation:
		return
	if is_instance_valid(code):
		code.editable = true
	save_original.disabled = false
	if reply.status != 200 or reply.data.get("digest") != digest:
		status.text = "原件未绑定，判断项或来源修订可能已变化（%d）" % reply.status
		return
	await _browse()
	for updated: Dictionary in pending_rows:
		if updated.issue_id == item.issue_id and int(updated.submission_version) == int(reply.data.submission_version) and updated.revision == reply.data.revision:
			await _open(updated, false)
			if selected == updated:
				edit_original.grab_focus()
				status.text = "已保存并返回判断项 · %s" % updated.revision
			return


func _send(operation: String) -> void:
	if selected.is_empty() or approve.disabled:
		return
	var attempt := generation
	var payload := {
		"kind": selected.kind, "module": selected.module, "revision": selected.revision, "path": selected.path,
		"submission_version": int(selected.submission_version), "expected_version": work_version,
		"note": note.text, "call_id": Crypto.new().generate_random_bytes(16).hex_encode(),
	}
	var action := "decide"
	if operation == "transfer":
		if recipients.selected < 0:
			return
		action = operation
		payload.target = recipients.get_selected_metadata()
	else:
		payload.decision = operation
	var route := "/api/v1/issues/%s/work/%s" % [str(selected.issue_id).uri_encode(), action]
	transfer.disabled = true
	approve.disabled = true
	revise.disabled = true
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route, payload)
	if generation != attempt:
		return
	if reply.status == 200:
		var receipt := ""
		if action == "decide":
			var history: Array = reply.data.get("history", [])
			var event: Dictionary = {} if history.is_empty() else history.back()
			if reply.data.get("id") != selected.issue_id or event.get("action") != "work.decide" or event.get("actor") != session.get_identity().id or not _matches_reference(event, selected) or event.get("decision") != operation or event.get("note") != payload.note:
				status.text = "无法核对签认回执，请重新读取此版本"
				return
			receipt = "提交 v%d 已%s · %s @ %s\n签认人　%s\n%s" % [int(selected.submission_version), "采纳" if operation == "approved" else "退回", selected.module, event.revision, event.actor, event.note]
		await _browse()
		if generation == attempt + 1 and not receipt.is_empty():
			status.text = receipt + ("\n" + status.text if not status.text.is_empty() else "")
	elif reply.status == 409 or reply.status == 403:
		var version := int(selected.submission_version)
		_clear_selection()
		_clear_rows()
		status.text = "提交 v%d 的状态或责任人已变化，请重新读取" % version if reply.status == 409 else "当前账号无权签认或转交提交 v%d" % version
	else:
		status.text = "未取得操作回执，请重新读取待判断事项"
