@tool
extends VBoxContainer

var view: Node
var session: Node
var issue := {}
var state := {}
var generation := 0
var busy := false
var pending := {}
var pending_key := ""
var summary := Label.new()
var history := Label.new()
var accept := Button.new()
var close := Button.new()
var reopen := Button.new()
var feedback := Label.new()


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	summary.name = "IssueAcceptanceCriteria"
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)
	history.name = "IssueLifecycleHistory"
	history.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	add_child(history)
	var actions := HFlowContainer.new()
	add_child(actions)
	accept.name = "AcceptIssueEvidence"
	accept.text = "确认选中评论所附的验收证据"
	close.name = "CloseAcceptedIssue"
	close.text = "关闭工单"
	reopen.name = "ReopenIssue"
	reopen.text = "重开工单"
	for pair in [[accept, "accept"], [close, "close"], [reopen, "reopen"]]:
		pair[0].pressed.connect(_submit.bind(pair[1]))
		actions.add_child(pair[0])
	feedback.name = "IssueLifecycleFeedback"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(feedback)
	view.detail_changed.connect(_on_detail)
	_on_detail()


func _on_detail() -> void:
	generation += 1
	issue = view.get_detail()
	state = {}
	pending = {}
	pending_key = ""
	history.text = ""
	feedback.text = ""
	visible = not issue.is_empty()
	busy = visible
	_controls()
	if visible:
		summary.text = "验收条件　" + str(issue.get("acceptance", ""))
		_load(generation)


func _route() -> String:
	return "/api/v1/issues/%s/lifecycle" % str(issue.id).uri_encode()


func _controls() -> void:
	var editable: bool = not busy and not state.is_empty() and session.get_identity().get("role") != "viewer"
	accept.disabled = not editable or not state.get("can_close", false) or state.get("accepted") != null
	close.disabled = not editable or not state.get("can_close", false)
	reopen.disabled = not editable or str(state.get("reopen_to", "")).is_empty()


func _load(attempt: int) -> void:
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, _route())
	if attempt != generation:
		return
	busy = false
	if reply.status != 200 or reply.data.get("id") != issue.id or not reply.data.has_all(["history", "version", "status", "revision", "reopen_to", "accepted", "asset_version"]):
		state = {}
		feedback.text = "无法回读工单的验收记录，请重新读取详情"
		_controls()
		return
	state = reply.data
	var lines := PackedStringArray()
	for entry in state.history:
		var labels := {"accepted": "确认验收", "closed": "关闭", "reopened": "重开", "historical": "历史状态"}
		var text := "%s　%s　%s → %s　%s" % [entry.created_at, labels.get(entry.kind, entry.kind), entry.previous, entry.target, entry.actor]
		if entry.get("evidence"):
			text += "　" + str(entry.evidence)
		lines.append(text)
	history.text = "\n".join(lines)
	if state.managed:
		feedback.text = "此工单由原生工作流验收"
	elif session.get_identity().get("role") == "viewer":
		feedback.text = "当前账号仅可查看验收记录"
	elif state.accepted:
		feedback.text = "已登记本版验收证据，可以关闭"
	elif state.can_close:
		feedback.text = "请在工单评论中选中实测记录，核对验收条件并确认"
	elif not str(state.reopen_to).is_empty():
		feedback.text = "重开将返回 " + str(state.reopen_to)
	else:
		feedback.text = "当前流程阶段不能关闭工单"
	_controls()


func _submit(operation: String) -> void:
	if (accept.disabled if operation == "accept" else (close.disabled if operation == "close" else reopen.disabled)):
		return
	var payload := {"expected_version": int(state.version), "revision": issue.revision, "asset_version": int(state.asset_version)}
	if operation == "accept":
		var comments := view.get_node_or_null("issue_comments")
		var selected := "" if comments == null else str(comments.get_selected_comment_id())
		if selected.is_empty():
			feedback.text = "请先选中本单的验收证据评论"
			return
		payload.comment = selected
	var intent := {"operation": operation, "payload": payload.duplicate()}
	if pending != intent:
		pending = intent
		pending_key = Crypto.new().generate_random_bytes(16).hex_encode()
	payload.call_id = pending_key
	busy = true
	_controls()
	var attempt := generation
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, _route() + "/" + operation, payload)
	if attempt != generation:
		return
	# Always reconcile the current service state before another write, including on a lost receipt.
	await _load(attempt)
	if attempt != generation or state.is_empty():
		return
	if state.status != issue.status or state.revision != issue.revision:
		await view.open_issue(int(issue.number))
		return
	if reply.status == 403:
		feedback.text = "没有权限修改此工单"
	elif reply.status == 409:
		if reply.data.get("detail") == "current acceptance evidence required":
			feedback.text = "缺少本版验收证据，工单仍然开放"
		else:
			feedback.text = "当前流程、版本或证据未满足操作条件，请核对工单"
	elif reply.status != 200 and not (operation == "accept" and state.accepted == payload.get("comment")):
		feedback.text = "未收到写入回执，已回读现状，可重试同一操作"
