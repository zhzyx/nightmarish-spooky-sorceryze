@tool
extends VBoxContainer

var view: Node
var session: Node
var generation := 0
var detail := {}
var flow_version := -1
var open := Button.new()
var form := VBoxContainer.new()
var assignees := OptionButton.new()
var apply_owner := Button.new()
var stage := OptionButton.new()
var apply_stage := Button.new()
var feedback := Label.new()


func _ready() -> void:
	view = get_parent()
	session = view.get_parent()
	open.name = "EditIssueProperties"
	open.text = "维护负责人和状态"
	open.pressed.connect(_toggle)
	add_child(open)
	add_child(form)
	assignees.name = "IssueOwnerChoice"
	form.add_child(assignees)
	apply_owner.name = "ApplyIssueOwner"
	apply_owner.text = "更新负责人"
	apply_owner.pressed.connect(_save.bind(true))
	form.add_child(apply_owner)
	stage.name = "IssueStageChoice"
	form.add_child(stage)
	apply_stage.name = "ApplyIssueStage"
	apply_stage.text = "迁移状态"
	apply_stage.pressed.connect(_save.bind(false))
	form.add_child(apply_stage)
	feedback.name = "IssuePropertyFeedback"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	form.add_child(feedback)
	view.detail_changed.connect(_reset)
	_reset()


func _reset() -> void:
	generation += 1
	detail = view.get_detail()
	visible = not detail.is_empty()
	form.hide()
	assignees.clear()
	assignees.disabled = true
	stage.clear()
	stage.disabled = true
	flow_version = -1
	feedback.text = ""
	open.disabled = false
	apply_owner.disabled = true
	apply_stage.disabled = true


func _toggle() -> void:
	if form.visible:
		_reset()
		return
	form.show()
	if session.get_identity().get("role") == "viewer":
		feedback.text = "当前账号仅可查看工单"
		return
	var attempt := generation
	feedback.text = "正在读取成员和流程…"
	var users: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/users")
	if attempt != generation:
		return
	if users.status == 200 and users.data.get("users") is Array:
		assignees.add_item("未分配")
		for entry in users.data.users:
			assignees.add_item("%s (%s)" % [entry.name, entry.email])
			var index := assignees.item_count - 1
			assignees.set_item_metadata(index, entry.id)
			if detail.assignee is Dictionary and entry.id == detail.assignee.id:
				assignees.select(index)
	var flow: Dictionary = await session.api_request(HTTPClient.METHOD_GET, _route() + "/work/flow")
	if attempt != generation:
		return
	var state: Dictionary = flow.data
	if flow.status == 200 and state.get("id") == detail.id and state.get("status") == detail.status:
		flow_version = int(state.version)
		var human := false
		for step in state.stages:
			if step.id == detail.status:
				human = step.human
		if not human:
			for edge in state.edges:
				if edge.from == detail.status and edge.to != "done":
					stage.add_item(edge.to)
		feedback.text = "当前阶段需要人工判断" if human else ""
		if not human and stage.item_count == 0:
			feedback.text = "当前状态没有可用迁移"
	else:
		feedback.text = "无法读取当前流程，请重新读取工单"
	apply_stage.disabled = stage.item_count == 0
	apply_owner.disabled = assignees.item_count == 0
	stage.disabled = apply_stage.disabled
	assignees.disabled = apply_owner.disabled
	if apply_owner.disabled:
		feedback.text += " 无法读取成员，请重新打开属性"


func _route() -> String:
	return "/api/v1/issues/" + str(detail.id).uri_encode()


func _save(assign: bool) -> void:
	if (apply_owner.disabled if assign else apply_stage.disabled):
		return
	var attempt := generation
	var route := _route()
	var payload: Dictionary
	var method: int
	if assign:
		payload = {"assignee_id": assignees.get_selected_metadata(), "expected_assignee_id": detail.assignee.id if detail.assignee is Dictionary else null}
		route += "/assignee"
		method = HTTPClient.METHOD_PUT
	else:
		payload = {"to_status": stage.get_item_text(stage.selected), "expected_version": flow_version, "call_id": Crypto.new().generate_random_bytes(16).hex_encode()}
		route += "/work/flow/advance"
		method = HTTPClient.METHOD_POST
	apply_owner.disabled = true
	apply_stage.disabled = true
	assignees.disabled = true
	stage.disabled = true
	open.disabled = true
	feedback.text = "正在保存…"
	var result: Dictionary = await session.api_request(method, route, payload)
	if attempt != generation:
		return
	open.disabled = false
	if result.status == 200:
		await view.open_issue(int(detail.number))
		return
	match int(result.status):
		403:
			feedback.text = "没有权限修改此工单"
		409:
			feedback.text = "负责人或流程已变化，或当前流程不允许此操作。请重新读取工单"
		_:
			feedback.text = "未取得保存回执，请重新读取工单"
