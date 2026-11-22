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
	if judgment.is_empty() or judgment.revision != item.revision or judgment.responsible != session.get_identity().id or judgment.decision != "pending":
		status.text = "此事项已变化，请重新读取待判断事项"
		return
	selected = item.duplicate(true)
	work_version = int(work.data.version)
	description.text = "%s\n%s\n%s @ %s" % [item.question, item.path, item.module, item.revision]
	for event: Dictionary in work.data.history:
		if int(event.get("submission_version", 0)) == int(item.submission_version) and event.action == "work.transfer":
			description.text += "\n%s → %s  %s" % [event.previous_responsible, event.responsible, event.note]
	panel.show()
	approve.disabled = false
	revise.disabled = false
	transfer.disabled = true
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
		await _browse()
	elif reply.status == 409 or reply.status == 403:
		_clear_selection()
		_clear_rows()
		status.text = "责任人、权限或修订已变化，请重新读取待判断事项"
	else:
		status.text = "未取得操作回执，请重新读取待判断事项"
