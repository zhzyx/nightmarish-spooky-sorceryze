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
	detail.detail_changed.connect(_clear_selection)
	_reset()


func _clear_selection() -> void:
	generation += 1
	selected.clear()
	panel.hide()
	description.text = ""
	recipients.clear()
	note.clear()
	status.text = ""


func _clear_rows() -> void:
	for child in rows.get_children():
		rows.remove_child(child)
		child.queue_free()


func _reset() -> void:
	_clear_selection()
	_clear_rows()
	browse.disabled = session.get_identity().is_empty()


func _browse() -> void:
	_reset()
	var attempt := generation
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/work/my-judgments")
	if generation != attempt:
		return
	if reply.status != 200 or reply.data.get("project") != session.get_identity().project or not reply.data.get("items") is Array:
		status.text = "无法读取本人的待判断事项"
		return
	for item: Dictionary in reply.data.items:
		var row := Button.new()
		row.text = "#%d %s · %s\n%s" % [int(item.number), item.title, item.path, item.question]
		row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.tooltip_text = "%s @ %s" % [item.module, item.revision]
		row.pressed.connect(_open.bind(item))
		rows.add_child(row)
	if rows.get_child_count() == 0:
		status.text = "暂无待本人判断的事项"


func _open(item: Dictionary) -> void:
	# Resolving the numbered issue also opens its original design and comment controls.
	await detail.open_issue(int(item.number))
	if detail.get_detail().get("id") != item.issue_id:
		return
	await _inspect(item, true)


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


func _inspect(item: Dictionary, open_original: bool) -> void:
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
	work_version = int(work.data.version)
	description.text = "%s\n%s\n判断人　%s" % [item.question, binding, judgment.responsible]
	for event: Dictionary in work.data.history:
		if int(event.get("submission_version", 0)) == int(item.submission_version) and event.action == "work.transfer":
			description.text += "\n%s → %s  %s" % [event.previous_responsible, event.responsible, event.note]
	panel.show()
	approve.disabled = false
	revise.disabled = false
	transfer.disabled = true
	if open_original:
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
