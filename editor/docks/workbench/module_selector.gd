@tool
extends VBoxContainer

# Shared by the workbench sidebar and the expanded conversation view.
const MODULES := "/api/v1/business-modules"
const CONVERSATIONS := "/api/v1/workspace/conversations"

var picker: OptionButton
var feedback: Label
var content: VBoxContainer
var issues: OptionButton
var page: Label
var history: TextEdit
var composer: TextEdit
var send: Button
var http: HTTPRequest
var session: Node
var managed_identity := false
var identity_generation := 0
var api := OS.get_environment("TIANXUAN_API").trim_suffix("/")
var project := OS.get_environment("TIANXUAN_PROJECT")
var module_id := ""
var location := {}
var conversation := {}
var issue_details := {}
var comments: Array = []
var drafts := {}
var pending_turn := {}
var busy := false
var location_dirty := false
var last_status := 0


func _ready() -> void:
	if api.is_empty():
		api = "http://127.0.0.1:8000"
	if project.is_empty():
		project = "workspace"
	picker = OptionButton.new()
	feedback = Label.new()
	content = VBoxContainer.new()
	issues = OptionButton.new()
	page = Label.new()
	history = TextEdit.new()
	composer = TextEdit.new()
	send = Button.new()
	http = HTTPRequest.new()
	picker.name = "BusinessModuleSelector"
	picker.fit_to_longest_item = false
	_add_local_picker()
	picker.item_selected.connect(_select)
	add_child(picker)
	feedback.name = "ModuleStatus"
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	feedback.hide()
	add_child(feedback)
	add_child(content)
	content.hide()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	issues.name = "ModuleIssue"
	issues.fit_to_longest_item = false
	issues.item_selected.connect(_choose_issue)
	content.add_child(issues)
	page.name = "ModulePagePosition"
	page.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	content.add_child(page)
	history.name = "ModuleConversation"
	history.editable = false
	history.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	history.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(history)
	var reference_host := VBoxContainer.new()
	reference_host.name = "ModuleReferenceHost"
	content.add_child(reference_host)
	composer.name = "ModuleChatInput"
	composer.custom_minimum_size.y = 70 * EditorInterface.get_editor_scale()
	composer.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	composer.placeholder_text = "输入此模块的问题…"
	content.add_child(composer)
	send.text = "发送"
	send.name = "ModuleSend"
	send.pressed.connect(_send)
	content.add_child(send)
	# Reparenting the conversation view must not cancel an in-flight request.
	http.timeout = 15
	http.max_redirects = 0
	http.body_size_limit = 8 * 1024 * 1024
	EditorInterface.get_base_control().add_child.call_deferred(http)
	_bind_session.call_deferred()


func _bind_session() -> void:
	var sidebar := get_meta("workbench_sidebar") as Node
	if sidebar:
		session = sidebar.find_child("WorkbenchBusinessSession", true, false)
	if is_instance_valid(session):
		managed_identity = true
		session.connect("identity_changed", _identity_changed)
		_identity_changed()


func _identity_changed() -> void:
	identity_generation += 1
	module_id = ""
	location = {}
	conversation = {}
	issue_details.clear()
	comments.clear()
	drafts.clear()
	pending_turn.clear()
	_reset_reference_scope()
	location_dirty = false
	composer.clear()
	history.clear()
	issues.clear()
	page.text = ""
	content.hide()
	size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	get_parent().get_node("ChatScroll").show()
	get_parent().get_node("ChatComposerPanel").show()
	picker.clear()
	_add_local_picker()
	_lock(false)
	_notice("")
	var identity: Dictionary = session.call("get_identity")
	project = identity.get("project", "")


func _authenticated() -> bool:
	if managed_identity:
		return is_instance_valid(session) and not Dictionary(session.call("get_identity")).is_empty()
	return not OS.get_environment("TIANXUAN_TOKEN").is_empty()


func _add_local_picker() -> void:
	picker.add_item("本机会话")
	picker.set_item_metadata(0, "")
	picker.add_item("选择业务模块…")
	picker.set_item_metadata(1, null)


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and is_instance_valid(http):
		http.queue_free()


func _notice(message: String) -> void:
	feedback.text = message
	feedback.visible = not message.is_empty()


func _lock(value: bool) -> void:
	busy = value
	picker.disabled = value
	issues.disabled = value
	composer.editable = not value
	send.disabled = value


func _request(path: String, method := HTTPClient.METHOD_GET, data := {}) -> Dictionary:
	var generation := identity_generation
	last_status = 0
	if managed_identity:
		if not _authenticated():
			_notice("请先登录天璇。")
			return {}
		var response: Dictionary = await session.call("api_request", method, path, data)
		if identity_generation != generation:
			return {}
		last_status = response.get("status", 0)
		if last_status < 200 or last_status >= 300:
			_notice("天璇请求失败（%s），请检查连接或登录身份后重试。" % last_status)
			return {}
		return response.get("data", {})
	var origin := api.split("/", false)
	if origin.size() < 2:
		_notice("请检查天璇服务地址。")
		return {}
	var host := origin[1].get_slice(":", 0)
	if not api.begins_with("https://") and not (api.begins_with("http://") and host in ["localhost", "127.0.0.1"]):
		_notice("请为天璇使用 HTTPS 或本机回环服务。")
		return {}
	var headers := PackedStringArray(["Authorization: Bearer " + OS.get_environment("TIANXUAN_TOKEN"), "Content-Type: application/json"])
	var scoped_path := path + ("&" if "?" in path else "?") + "project=" + project.uri_encode()
	var err := http.request(api + scoped_path, headers, method, "" if data.is_empty() else JSON.stringify(data))
	if err != OK:
		_notice("无法连接天璇，请检查服务地址后重试。")
		return {}
	var reply: Array = await http.request_completed
	if generation != identity_generation:
		return {}
	last_status = reply[1]
	if reply[0] != HTTPRequest.RESULT_SUCCESS or last_status < 200 or last_status >= 300:
		_notice("天璇请求失败（%s）。请检查连接或登录身份后重试。" % last_status)
		return {}
	var body = JSON.parse_string(reply[3].get_string_from_utf8())
	if body is Dictionary:
		return body
	_notice("天璇返回的工作位置格式无效。")
	return {}


func _location_path(id: String) -> String:
	return MODULES + "/" + id.uri_encode() + "/location"


func _select_current() -> void:
	for i in picker.item_count:
		if picker.get_item_metadata(i) == module_id:
			picker.select(i)
			return


func _select(index: int) -> void:
	if busy:
		_select_current()
		return
	var generation := identity_generation
	var target = picker.get_item_metadata(index)
	_select_current()
	_lock(true)
	_notice("")
	if target == null and not _authenticated():
		_notice("请先登录天璇。" if managed_identity else "请使用天璇登录会话启动编辑器（TIANXUAN_TOKEN）。")
	elif target == null:
		var response := await _request(MODULES)
		if response.get("modules") is Array:
			picker.clear()
			picker.add_item("本机会话")
			picker.set_item_metadata(0, "")
			var counts := {}
			for item in response.modules:
				counts[item.name] = counts.get(item.name, 0) + 1
			for item in response.modules:
				var label := str(item.name)
				if counts[label] > 1:
					label += " · " + str(item.id)
				picker.add_item(label)
				picker.set_item_metadata(picker.item_count - 1, item.id)
			picker.show_popup()
	elif target != module_id:
		await _switch_to(target)
	if identity_generation == generation:
		_lock(false)


func _save_location() -> bool:
	if not location_dirty:
		return true
	var saved := await _request(_location_path(module_id), HTTPClient.METHOD_PUT, location)
	if saved.get("location") != location:
		return false
	location_dirty = false
	return true


func _draft_key() -> String:
	return JSON.stringify([module_id, location.get("issue_id"), location.get("conversation_id")])


func _switch_to(target: String) -> void:
	if not module_id.is_empty():
		drafts[_draft_key()] = composer.text
		if not await _save_location():
			return
	var next_location := {}
	var next_chat := {}
	var next_issues: Array = []
	var next_comments: Array = []
	if not target.is_empty():
		var result := await _request(_location_path(target))
		if not result.has("location"):
			return
		next_location = result.location if result.location != null else {"issue_id": null, "conversation_id": null, "position": "module/overview"}
		var issue_result := await _request("/api/v1/issues?module_id=" + target.uri_encode())
		if not issue_result.get("issues") is Array:
			return
		next_issues = issue_result.issues
		if next_location.issue_id != null and not next_issues.any(func(item): return item.id == next_location.issue_id):
			_notice("工单归属或读权已变化，请重新选择模块。")
			return
		if next_location.issue_id != null and str(next_location.position).begins_with("issue/comments"):
			var thread := await _request("/api/v1/issues/" + str(next_location.issue_id).uri_encode() + "/comments")
			if not thread.get("comments") is Array:
				return
			next_comments = thread.comments
		if next_location.conversation_id != null:
			next_chat = await _request(CONVERSATIONS + "/" + str(next_location.conversation_id).uri_encode())
			if next_chat.get("id") != next_location.conversation_id:
				return
	# Publish all controls together after the target's authenticated reads succeed.
	module_id = target
	location = next_location
	conversation = next_chat
	comments = next_comments
	issue_details.clear()
	location_dirty = false
	_select_current()
	content.visible = not module_id.is_empty()
	size_flags_vertical = Control.SIZE_EXPAND_FILL if content.visible else Control.SIZE_SHRINK_BEGIN
	get_parent().get_node("ChatScroll").visible = not content.visible
	get_parent().get_node("ChatComposerPanel").visible = not content.visible
	issues.clear()
	issues.add_item("模块概览")
	issues.set_item_metadata(0, null)
	for issue in next_issues:
		issue_details[issue.id] = issue
		issues.add_item("#%d  %s" % [int(issue.number), issue.title])
		issues.set_item_metadata(issues.item_count - 1, issue.id)
		if issue.id == location.get("issue_id"):
			issues.select(issues.item_count - 1)
	_reset_reference_scope()
	_render()
	composer.text = drafts.get(_draft_key(), "")
	if content.visible:
		composer.grab_focus()


func _choose_issue(index: int) -> void:
	if busy or location.get("issue_id") == issues.get_item_metadata(index):
		return
	drafts[_draft_key()] = composer.text
	comments.clear()
	location.issue_id = issues.get_item_metadata(index)
	location.position = "module/overview" if location.issue_id == null else "issue/details"
	location_dirty = true
	_reset_reference_scope()
	composer.text = drafts.get(_draft_key(), "")
	_render()


func _reset_reference_scope() -> void:
	var module_label := "" if module_id.is_empty() else picker.get_item_text(picker.selected)
	var issue_label := "无关联工单" if location.get("issue_id") == null else issues.get_item_text(issues.selected)
	get_meta("change_reference_scope").call(module_label, issue_label)


func redact_reference(text: String) -> String:
	if managed_identity and is_instance_valid(session) and session.has_method("redact_credentials"):
		return session.redact_credentials(text)
	var token := OS.get_environment("TIANXUAN_TOKEN")
	return text if token.is_empty() else text.replace(token, "[REDACTED]")


func _render() -> void:
	page.text = location.get("position", "")
	page.tooltip_text = page.text
	var messages := PackedStringArray()
	var issue: Dictionary = issue_details.get(location.get("issue_id"), {})
	if not str(issue.get("body_md", "")).is_empty():
		messages.append(issue.body_md)
	for comment in comments:
		messages.append(comment.body)
	for turn in conversation.get("turns", []):
		messages.append(turn.content)
		if turn.get("answer") != null:
			messages.append(turn.answer)
		elif turn.get("state") == "unanswered":
			messages.append("消息已保存，模型尚未回复。")
	for revision in conversation.get("revisions", []):
		if conversation.current.get(revision.stage) == revision.revision and revision.confirmed_at == null:
			messages.append("设计草稿 · " + revision.body)
	history.text = "\n\n".join(messages)


func _uuid() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var hex := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]


func _send() -> void:
	if busy or module_id.is_empty() or composer.text.strip_edges().is_empty():
		return
	var frozen: Dictionary = get_meta("freeze_references").call(composer.text.strip_edges())
	if frozen.is_empty():
		_notice("引用已失效，请移除或重新选择后发送。")
		return
	var body: String = frozen.content
	if body.length() > 8000:
		_notice("正文与引用合计超过 8000 字符，请缩短后发送。")
		return
	var snapshot := {"project": project, "module_id": module_id, "issue_id": location.issue_id, "references": frozen.references}
	var generation := identity_generation
	_lock(true)
	_notice("")
	if location.conversation_id == null:
		var draft_key := _draft_key()
		var create_id: String = pending_turn.get(draft_key, {}).get("create_id", "")
		if create_id.is_empty():
			create_id = _uuid()
			pending_turn[draft_key] = {"create_id": create_id}
		var created := await _request(CONVERSATIONS, HTTPClient.METHOD_POST, {"id": create_id})
		if generation != identity_generation:
			return
		if not created.has("id"):
			_lock(false)
			return
		pending_turn.erase(draft_key)
		drafts.erase(draft_key)
		location.conversation_id = created.id
		conversation = created
		location_dirty = true
	if await _save_location():
		var key := _draft_key()
		var turn: Dictionary = pending_turn.get(key, {})
		if turn.get("content") != body or turn.get("context_snapshot") != snapshot:
			turn = {"id": _uuid(), "content": body, "expected_version": conversation.version,
				"context_snapshot": snapshot}
		pending_turn[key] = turn
		var result := await _request(CONVERSATIONS + "/" + str(location.conversation_id).uri_encode() + "/turns", HTTPClient.METHOD_POST, turn)
		if generation != identity_generation:
			return
		if result.get("id") == location.conversation_id:
			conversation = result
			composer.clear()
			_reset_reference_scope()
			drafts.erase(key)
			pending_turn.erase(key)
			_render()
		elif last_status == 409:
			pending_turn.erase(key)
			var latest := await _request(CONVERSATIONS + "/" + str(location.conversation_id).uri_encode())
			if generation != identity_generation:
				return
			if latest.get("id") == location.conversation_id:
				conversation = latest
				_render()
				_notice("会话已更新，请查看后重新发送草稿。")
	if generation == identity_generation:
		_lock(false)
