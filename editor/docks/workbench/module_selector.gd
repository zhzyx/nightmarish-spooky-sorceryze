@tool
extends VBoxContainer

signal operation_finished

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
var document_links := MenuButton.new()
var comment_action := Button.new()
var comment_dialog := ConfirmationDialog.new()
var comment_preview := TextEdit.new()
var reviewed_comment := {}
var issue_view: Node
var design_action := Button.new()
var progress_action := Button.new()
var design := DirectionDraft.new()
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
var consultation_detail := {}
var pending_consultation_location := {}
var comments: Array = []
var drafts := {}
var pending_turn := {}
var asset_picker
var staged_assets := {}
var restoring_draft := false
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
	document_links.name = "SentDocumentReferences"
	document_links.text = "消息中的文档段落"
	document_links.hide()
	document_links.get_popup().id_pressed.connect(_open_sent_reference)
	content.add_child(document_links)
	composer.name = "ModuleChatInput"
	composer.custom_minimum_size.y = 70 * EditorInterface.get_editor_scale()
	composer.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	composer.placeholder_text = "输入此模块的问题…"
	composer.text_changed.connect(_save_draft)
	composer.text_set.connect(_save_draft)
	content.add_child(composer)
	send.text = "发送"
	send.name = "ModuleSend"
	send.pressed.connect(_send)
	content.add_child(send)
	comment_action.name = "ReviewIssueChatComment"
	comment_action.text = "将本轮回复拟为工单评论…"
	comment_action.pressed.connect(_review_issue_comment)
	comment_action.hide()
	content.add_child(comment_action)
	comment_dialog.name = "AuthorizeIssueChatComment"
	comment_dialog.get_ok_button().text = "授权发表"
	comment_dialog.confirmed.connect(_publish_issue_comment)
	comment_dialog.canceled.connect(func(): reviewed_comment.clear())
	comment_preview.editable = false
	comment_preview.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	comment_preview.custom_minimum_size = Vector2(380, 170)
	comment_dialog.add_child(comment_preview)
	add_child(comment_dialog)
	design_action.name = "ModuleDesignAction"
	design_action.pressed.connect(_open_design)
	content.add_child(design_action)
	progress_action.name = "OpenConversationDesignProgress"
	progress_action.text = "偃师设计阶段"
	progress_action.pressed.connect(_open_progress)
	content.add_child(progress_action)
	design.panel = self
	add_child(design)
	# Reparenting the conversation view must not cancel an in-flight request.
	http.timeout = 15
	http.max_redirects = 0
	http.body_size_limit = 8 * 1024 * 1024
	EditorInterface.get_base_control().add_child.call_deferred(http)
	if has_meta("asset_picker_script"):
		asset_picker = get_meta("asset_picker_script").new()
		asset_picker.name = "WorkbenchAssetPicker"
		add_child(asset_picker)
		move_child(asset_picker, 1)
	_bind_session.call_deferred()


func _bind_session() -> void:
	var sidebar := get_meta("workbench_sidebar") as Node
	if sidebar:
		session = sidebar.find_child("WorkbenchBusinessSession", true, false)
	if is_instance_valid(session):
		managed_identity = true
		var detail := session.find_child("WorkbenchIssueDetail", true, false)
		if detail:
			issue_view = detail
			detail.detail_changed.connect(_comment_context_changed)
			detail.consultation_requested.connect(_open_issue_consultation.bind(detail))
		session.connect("identity_changed", _identity_changed)
		if session.has_signal("identity_resetting"):
			session.connect("identity_resetting", _save_draft)
		_identity_changed()


func _identity_changed() -> void:
	_comment_context_changed()
	identity_generation += 1
	design.reset()
	module_id = ""
	location = {}
	conversation = {}
	issue_details.clear()
	consultation_detail.clear()
	comments.clear()
	drafts.clear()
	pending_turn.clear()
	_reset_reference_scope()
	staged_assets.clear()
	if asset_picker:
		asset_picker.reset()
	location_dirty = false
	composer.clear()
	composer.clear_undo_history()
	history.clear()
	document_links.hide()
	document_links.get_popup().clear()
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
	if not identity.is_empty() and not pending_consultation_location.is_empty():
		restore_consultation_location(pending_consultation_location)


func _consultation_scope() -> String:
	return JSON.stringify([api, session.get_identity().id, project, ProjectSettings.globalize_path("res://")]).sha256_text()


func get_consultation_location() -> Dictionary:
	if consultation_detail.is_empty() or not managed_identity or not _authenticated():
		return pending_consultation_location
	return {"scope": _consultation_scope(), "number": consultation_detail.number, "id": consultation_detail.id}


func restore_consultation_location(record: Dictionary) -> void:
	if not managed_identity or not _authenticated():
		pending_consultation_location = record
		return
	pending_consultation_location = {}
	if record.get("scope") == _consultation_scope() and record.get("id") is String and not record.id.is_empty():
		session.get_node("WorkbenchIssueDetail").open_issue(int(record.get("number", 0)), record.id)


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
	comment_action.disabled = value
	design_action.disabled = value
	progress_action.disabled = value
	if not busy:
		operation_finished.emit()


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
	elif target != module_id or not consultation_detail.is_empty():
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


func _draft_key(issue_id: Variant) -> String:
	var identity: Dictionary = session.get_identity() if managed_identity else {}
	var scope := [api, identity.get("id"), project, ProjectSettings.globalize_path("res://"), module_id, issue_id]
	if not consultation_detail.is_empty() and consultation_detail.id == issue_id:
		scope.append("issue_consultation")
	return JSON.stringify(scope)


func _read_draft(key: String) -> Dictionary:
	if managed_identity:
		return get_meta("read_draft").call(key)
	return drafts.get(key, {})


func _save_draft() -> bool:
	if restoring_draft or module_id.is_empty():
		return true
	var key := _draft_key(location.get("issue_id"))
	var record := {"text": redact_reference(composer.text), "conversation_id": location.get("conversation_id"),
		"pending": pending_turn.get(key, {})}
	var assets: Dictionary = {}
	for locator in staged_assets.get(key, {}):
		if str(record.text).contains(locator) and redact_reference(locator) == locator:
			assets[locator] = staged_assets[key][locator]
	record["assets"] = assets
	if not managed_identity:
		drafts[key] = record
		return true
	if not get_meta("write_draft").call(key, record):
		_notice("无法保存当前草稿，请检查编辑器数据目录。")
		return false
	return true


func _saved_draft_hash(record: Dictionary) -> String:
	return JSON.stringify([record.get("text", ""), record.get("references", []), record.get("excerpts", {}), record.get("assets", {})]).sha256_text()


func _restore_draft() -> void:
	restoring_draft = true
	_reset_reference_scope()
	var key := _draft_key(location.get("issue_id"))
	var record := {} if module_id.is_empty() else _read_draft(key)
	staged_assets[key] = record.get("assets", {})
	var pending: Dictionary = record.get("pending", {})
	composer.text = record.get("text", "")
	composer.clear_undo_history()
	if not module_id.is_empty():
		get_meta("restore_references").call(key, record)
	if pending.has("id") and conversation.get("turns", []).any(func(turn): return turn.id == pending.id):
		# A committed reply may arrive after the editor closed. Preserve any later
		# edits to either the text or the reference list.
		if pending.get("draft_hash") == _saved_draft_hash(record):
			composer.clear()
			composer.clear_undo_history()
			staged_assets.erase(key)
			_reset_reference_scope()
		pending = {}
	pending_turn[key] = pending
	restoring_draft = false


func _switch_to(target: String) -> void:
	if not module_id.is_empty():
		if not _save_draft() or not await _save_location():
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
	_show_location(target, next_location, next_chat, next_issues, next_comments, {})


func _open_issue_consultation(after_open: Callable, view: Node) -> void:
	var detail: Dictionary = view.get_detail()
	if not _authenticated() or detail.is_empty() or detail.project != project:
		return
	var generation := identity_generation
	if busy:
		await operation_finished
		if busy or identity_generation != generation or view.get_detail() != detail:
			return
	_lock(true)
	_notice("")
	await _read_issue_consultation(view, detail, after_open)
	if generation == identity_generation:
		_lock(false)


func _read_issue_consultation(view: Node, detail: Dictionary, after_open: Callable) -> void:
	var generation := identity_generation
	var target: String = detail.module_id
	if not module_id.is_empty():
		if not _save_draft() or not await _save_location():
			return
	if generation != identity_generation or view.get_detail() != detail:
		return
	var list := await _request("/api/v1/issues?module_id=" + target.uri_encode())
	if generation != identity_generation or not list.get("issues") is Array or view.get_detail() != detail:
		return
	if not list.issues.any(func(item): return item.id == detail.id):
		_notice("工单归属或读权已变化，请重新读取详情。")
		return
	var chat := await _request(CONVERSATIONS + "/for-issue/" + str(detail.id).uri_encode(), HTTPClient.METHOD_POST)
	if generation != identity_generation or not chat.has("id") or view.get_detail() != detail:
		return
	var known_module := false
	for i in picker.item_count:
		if picker.get_item_metadata(i) == target:
			known_module = true
			break
	if not known_module:
		picker.add_item(target)
		picker.set_item_metadata(picker.item_count - 1, target)
	var selected := {"issue_id": detail.id, "conversation_id": chat.id, "position": "issue/details"}
	_show_location(target, selected, chat, list.issues, [], detail)
	if after_open.is_valid():
		after_open.call(self)


func _show_location(target: String, next_location: Dictionary, next_chat: Dictionary, next_issues: Array, next_comments: Array, detail: Dictionary) -> void:
	consultation_detail = detail
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
	_restore_draft()
	_render()
	if content.visible:
		composer.grab_focus()


func _choose_issue(index: int) -> void:
	if not busy:
		await _change_issue(index)


func _change_issue(index: int) -> void:
	var previous := issues.selected
	for i in issues.item_count:
		if issues.get_item_metadata(i) == location.get("issue_id"):
			previous = i
			break
	var target = issues.get_item_metadata(index)
	issues.select(previous)
	if location.get("issue_id") == target or not _save_draft():
		return
	var generation := identity_generation
	_lock(true)
	var record := _read_draft(_draft_key(target))
	var chat := {}
	var id = record.get("conversation_id")
	if id != null:
		chat = await _request(CONVERSATIONS + "/" + str(id).uri_encode())
		if generation != identity_generation:
			return
		if chat.get("id") != id:
			_lock(false)
			return
	var next := {"issue_id": target, "conversation_id": id,
		"position": "module/overview" if target == null else "issue/details"}
	var can_save: bool = not managed_identity or session.get_identity().get("role") != "viewer"
	var saved := await _request(_location_path(module_id), HTTPClient.METHOD_PUT, next) if can_save else {"location": next}
	if generation != identity_generation:
		return
	if saved.get("location") == next:
		issues.select(index)
		consultation_detail = {}
		location = next
		location_dirty = false
		comments.clear()
		conversation = chat
		_restore_draft()
		_render()
	_lock(false)


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
	_comment_context_changed()
	if asset_picker:
		asset_picker.update_issue_button()
	page.text = location.get("position", "")
	if not consultation_detail.is_empty():
		page.text = "仅咨询 · #%d · %s" % [int(consultation_detail.number), consultation_detail.revision]
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
	var menu := document_links.get_popup()
	menu.clear()
	for turn in conversation.get("turns", []):
		var snapshot = turn.get("context_snapshot")
		if snapshot is Dictionary:
			for ref in snapshot.get("references", []):
				if ref.get("kind") == "document" and int(ref.get("paragraph", 0)) > 0:
					menu.add_item("%s · v%d · 第 %d 段" % [ref.object_id,ref.revision,ref.paragraph])
					menu.set_item_metadata(menu.item_count - 1, ref)
	document_links.visible = menu.item_count > 0
	progress_action.visible = managed_identity and consultation_detail.is_empty() and not conversation.is_empty()
	var published := conversation.get("requirement_id") != null
	var revision := _direction()
	design_action.text = "打开本次咨询的需求文档" if published else "从咨询形成方向草稿"
	design_action.visible = consultation_detail.is_empty() and ((published and is_instance_valid(session)) or (
		not published and not conversation.get("turns", []).is_empty() and revision.get("confirmed_at") == null))


func _comment_payload() -> Dictionary:
	if consultation_detail.is_empty() or not is_instance_valid(issue_view) or issue_view.get_detail() != consultation_detail:
		return {}
	if not consultation_detail.get("can_classify", false) or conversation.get("turns", []).is_empty() or location.get("issue_id") != consultation_detail.id:
		return {}
	var turn: Dictionary = conversation.turns.back()
	var ref := {"kind": "issue", "object_id": consultation_detail.id, "revision": consultation_detail.revision}
	if turn.state != "answered" or turn.has("issue_comment") or not turn.get("context_snapshot", {}).get("references", []).has(ref):
		return {}
	var payload := {"expected_version": int(conversation.version), "issue": ref, "turn_id": turn.id, "body": turn.answer}
	if consultation_detail.get("design_source") != null:
		var grant: Variant = consultation_detail.task_confirmation
		if not grant is Dictionary or grant.status != "confirmed" or grant.stage != "工单评论" or grant.confirmed_by != session.get_identity().get("id"):
			return {}
		payload.target_revision = int(grant.target_revision)
		payload.confirmation_revision = int(grant.revision)
	return payload


func _comment_context_changed() -> void:
	reviewed_comment.clear()
	comment_dialog.hide()
	comment_action.visible = not _comment_payload().is_empty()


func _review_issue_comment() -> void:
	if busy:
		return
	reviewed_comment = _comment_payload()
	if reviewed_comment.is_empty():
		return
	comment_dialog.title = "发表到 #%d %s" % [int(consultation_detail.number), consultation_detail.title]
	comment_preview.text = reviewed_comment.body
	comment_dialog.popup_centered()


func _publish_issue_comment() -> void:
	if busy or reviewed_comment.is_empty() or reviewed_comment != _comment_payload():
		return
	var payload := reviewed_comment.duplicate(true)
	reviewed_comment.clear()
	var generation := identity_generation
	var key: String = conversation.id
	_lock(true)
	var result := await _request(CONVERSATIONS + "/" + key + "/issue-comment", HTTPClient.METHOD_POST, payload)
	if generation != identity_generation:
		return
	if not result.is_empty() and _comment_payload() == payload and key == conversation.get("id"):
		var receipt: Dictionary = result.comment
		conversation = result.conversation
		_render()
		var widget := issue_view.get_node("issue_comments")
		var shown: bool = await widget.reveal_comment(receipt)
		if generation != identity_generation:
			return
		if issue_view.get_detail().get("id") == payload.issue.object_id:
			_notice("工单评论已发表并回读。" if shown else "已发表，请在工单详情重读评论。")
	_lock(false)


func stage_document_reference(ref: Dictionary) -> bool:
	var input: TextEdit = composer if not module_id.is_empty() else get_parent().find_child("ChatInput", true, false)
	if busy or not is_instance_valid(input):
		return false
	var locator := "<tianxuan-doc://%s/%d/%d>" % [str(ref.document_id).uri_encode(),ref.version,ref.paragraph]
	if not input.text.contains(locator):
		input.deselect()
		input.set_caret_line(input.get_line_count()-1)
		input.set_caret_column(input.get_line(input.get_caret_line()).length())
		input.insert_text_at_caret(("" if input.text.is_empty() else "\n") + locator)
	input.grab_focus()
	return true


func _document_references(text: String) -> Array:
	var pattern := RegEx.new()
	pattern.compile("<tianxuan-doc://([^/<>\\s]+)/([1-9][0-9]{0,17})/([1-9][0-9]{0,8})>")
	var references := []
	for match_ in pattern.search_all(text):
		var ref := {"kind":"document","object_id":match_.get_string(1).uri_decode(),"revision":int(match_.get_string(2)),"paragraph":int(match_.get_string(3))}
		if not references.has(ref):
			references.append(ref)
	return references


func _open_sent_reference(id: int) -> void:
	if not is_instance_valid(session):
		return
	var menu := document_links.get_popup()
	var index := menu.get_item_index(id)
	if index < 0:
		return
	var ref: Dictionary = menu.get_item_metadata(index)
	var view = session.find_child("WorkbenchDocuments",true,false)
	if is_instance_valid(view):
		view.open_document(ref.object_id, int(ref.revision), int(ref.paragraph))


func _open_progress() -> void:
	if not busy and progress_action.is_visible_in_tree() and is_instance_valid(session):
		var progress = session.get_node("WorkbenchDesignProgress")
		progress.open_chat(conversation.id, self)


func _direction() -> Dictionary:
	var active = conversation.get("current", {}).get("direction")
	for revision in conversation.get("revisions", []):
		if revision.stage == "direction" and revision.revision == active:
			return revision
	return {}


func _open_design() -> void:
	if busy or not design_action.visible:
		return
	if conversation.get("requirement_id") != null:
		var documents := session.find_child("WorkbenchDocuments", true, false)
		if documents:
			documents.open_document(conversation.requirement_id, int(conversation.requirement_version), 1)
		return
	design.open_draft()


func _uuid() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var hex := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]


func _issue_excerpt(text: String, limit: int) -> String:
	return text if text.length() <= limit else text.left(limit) + "…"


func _send() -> void:
	if busy or module_id.is_empty() or composer.text.strip_edges().is_empty():
		return
	var question := composer.text.strip_edges()
	if not consultation_detail.is_empty():
		var data := consultation_detail
		var owner := "未分配"
		if data.assignee is Dictionary:
			owner = str(data.assignee.name) if data.assignee.name else str(data.assignee.id)
		question += "\n\n[工单详情 · 仅作为引用]\n#%d %s\n%s\n验收：%s\n负责人：%s\n状态：%s" % [
			int(data.number), data.title, _issue_excerpt(data.body_md, 2000), _issue_excerpt(data.acceptance, 1000), owner, data.status]
	var frozen: Dictionary = get_meta("freeze_references").call(redact_reference(question))
	if frozen.is_empty():
		_notice("引用已失效，请移除或重新选择后发送。")
		return
	var body: String = frozen.content
	if body.length() > 8000:
		_notice("正文与引用合计超过 8000 字符，请缩短后发送。")
		return
	var references: Array = frozen.references.duplicate()
	if not consultation_detail.is_empty():
		references.append({"kind": "issue", "object_id": consultation_detail.id, "revision": consultation_detail.revision})
	var citation_text := body if consultation_detail.is_empty() else composer.text
	for reference in _asset_references(_draft_key(location.get("issue_id")), citation_text) + _document_references(citation_text):
		if not references.has(reference):
			references.append(reference)
	if references.size() > 16:
		_notice("每条消息最多可引用 16 个对象。")
		return
	var snapshot := {"project": project, "module_id": module_id, "issue_id": location.issue_id, "references": references}
	var generation := identity_generation
	_lock(true)
	_notice("")
	if location.conversation_id == null:
		var draft_key := _draft_key(location.issue_id)
		var create_id: String = pending_turn.get(draft_key, {}).get("create_id", "")
		if create_id.is_empty():
			create_id = _uuid()
			pending_turn[draft_key] = {"create_id": create_id}
		if not _save_draft():
			_lock(false)
			return
		var created := await _request(CONVERSATIONS, HTTPClient.METHOD_POST, {"id": create_id})
		if generation != identity_generation:
			return
		if not created.has("id"):
			_lock(false)
			return
		location.conversation_id = created.id
		conversation = created
		location_dirty = true
	if await _save_location():
		var key := _draft_key(location.issue_id)
		var pending: Dictionary = pending_turn.get(key, {})
		var fingerprint := JSON.stringify([body, snapshot]).sha256_text()
		if pending.get("fingerprint") != fingerprint:
			if not _save_draft():
				_lock(false)
				return
			pending = {"id": _uuid(), "fingerprint": fingerprint, "expected_version": conversation.version,
				"draft_hash": _saved_draft_hash(_read_draft(key))}
		pending_turn[key] = pending
		if not _save_draft():
			_lock(false)
			return
		var turn := {"id": pending.id, "content": body, "expected_version": pending.expected_version,
			"context_snapshot": snapshot}
		var result := await _request(CONVERSATIONS + "/" + str(location.conversation_id).uri_encode() + "/turns", HTTPClient.METHOD_POST, turn)
		if generation != identity_generation:
			return
		if result.get("id") == location.conversation_id:
			conversation = result
			staged_assets.erase(key)
			pending_turn.erase(key)
			_reset_reference_scope()
			composer.clear()
			_save_draft()
			_render()
		elif last_status == 409:
			pending_turn.erase(key)
			var latest := await _request(CONVERSATIONS + "/" + str(location.conversation_id).uri_encode())
			if generation != identity_generation:
				return
			if latest.get("id") == location.conversation_id:
				conversation = latest
				_render()
				if consultation_detail.is_empty():
					_notice("会话已更新，请查看后重新发送草稿。")
				else:
					_notice("会话或工单修订已更新，请重新读取工单详情，核对草稿后发送。")
	if generation == identity_generation:
		_lock(false)


# Asset-origin navigation chooses a module; only an explicit issue-origin action inherits an issue.
func select_asset_module(target: String, owners: Array) -> bool:
	if module_id != target:
		await _switch_to(target)
	if module_id != target:
		return false
	var listed := false
	for index in picker.item_count:
		if picker.get_item_metadata(index) == target:
			listed = true
			break
	if not listed:
		for owner in owners:
			if owner.id == target:
				picker.add_item("%s · %s" % [owner.name, target])
				picker.set_item_metadata(picker.item_count - 1, target)
				break
	_select_current()
	if location.get("issue_id") != null:
		await _change_issue(0)
	return module_id == target and location.get("issue_id") == null


func stage_asset_reference(asset: Dictionary) -> void:
	var input: TextEdit = composer if not module_id.is_empty() else get_parent().find_child("ChatInput", true, false)
	if not is_instance_valid(input):
		return
	var locator := "<duobao://%s/%s/%s>" % [asset.source_module, asset.revision, str(asset.path).uri_encode()]
	if not module_id.is_empty():
		var key := _draft_key(location.get("issue_id"))
		var refs: Dictionary = staged_assets.get(key, {})
		# Preserve the service's per-message reference limit. Editing a citation out releases its slot.
		for existing in refs.keys():
			if not input.text.contains(existing):
				refs.erase(existing)
		if refs.size() >= 16 and not refs.has(locator):
			_notice("每条消息最多可引用 16 个对象。")
			return
		refs[locator] = {"kind": "editor", "object_id": "duobao:" + str(asset.asset_id), "revision": asset.revision}
		staged_assets[key] = refs
	if not input.text.contains(locator):
		input.set_caret_line(input.get_line_count() - 1)
		input.set_caret_column(input.get_line(input.get_caret_line()).length())
		input.deselect()
		input.insert_text_at_caret(("" if input.text.is_empty() else "\n") + locator)
	if not module_id.is_empty():
		_save_draft()
	input.grab_focus()


func _asset_references(key: String, body: String) -> Array:
	var result := []
	var refs: Dictionary = staged_assets.get(key, {})
	for locator in refs:
		if body.contains(locator):
			result.append(refs[locator])
	return result


class DirectionDraft extends AcceptDialog:
	var panel: Control
	var source := Label.new()
	var body := TextEdit.new()
	var feedback := Label.new()
	var latest_body := TextEdit.new()
	var suggest := Button.new()
	var save := Button.new()
	var version := -1
	var read_required := false

	func _ready() -> void:
		title = "咨询方向草稿"
		exclusive = true
		get_ok_button().text = "关闭"
		var fields := VBoxContainer.new()
		fields.custom_minimum_size = Vector2(470, 320) * EditorInterface.get_editor_scale()
		add_child(fields)
		source.name = "DesignSource"
		source.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		fields.add_child(source)
		body.name = "DesignDraftBody"
		body.text_changed.connect(_update_save)
		body.placeholder_text = "编写设计方向，或根据本次咨询生成草稿"
		body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		body.size_flags_vertical = Control.SIZE_EXPAND_FILL
		fields.add_child(body)
		var actions := HBoxContainer.new()
		fields.add_child(actions)
		suggest.text = "从问答补充草稿"
		suggest.name = "SuggestDesignDraft"
		suggest.pressed.connect(_request_design.bind(false))
		actions.add_child(suggest)
		save.text = "保存新修订"
		save.name = "SaveDesignDraft"
		save.pressed.connect(_request_design.bind(true))
		actions.add_child(save)
		feedback.name = "DesignDraftStatus"
		feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		fields.add_child(feedback)
		latest_body.name = "LatestDirectionBody"
		latest_body.editable = false
		latest_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		latest_body.custom_minimum_size.y = 65 * EditorInterface.get_editor_scale()
		fields.add_child(latest_body)
		latest_body.hide()

	func reset() -> void:
		hide()
		source.text = ""
		body.clear()
		feedback.text = ""
		latest_body.clear()
		latest_body.hide()
		version = -1
		read_required = false

	func _show_source() -> void:
		source.text = "来源会话 %s · 会话版本 %d" % [panel.conversation.id, version]

	func open_draft() -> void:
		version = int(panel.conversation.version)
		_show_source()
		latest_body.hide()
		body.text = panel._direction().get("body", "")
		feedback.text = ""
		read_required = false
		_lock(false)
		popup_centered()
		body.grab_focus()

	func _lock(value: bool) -> void:
		panel._lock(value)
		body.editable = not value
		suggest.disabled = value or read_required
		_update_save()
		save.text = "读取最新修订" if read_required else "保存新修订"

	func _request_design(write: bool) -> void:
		if panel.busy or version < 0:
			return
		var generation: int = panel.identity_generation
		var chat: String = panel.conversation.id
		var route: String = panel.CONVERSATIONS + "/" + chat.uri_encode()
		var entered := body.text
		if not read_required and (entered.length() > 8000 or (write and entered.strip_edges().is_empty())):
			feedback.text = "请输入不超过 8000 个字符的草稿。"
			return
		_lock(true)
		panel._notice("")
		if not read_required:
			var payload := {"expected_version": version}
			var endpoint := "/drafts" if write else "/suggest"
			if write:
				payload.body = entered
			else:
				payload.draft_body = entered
				payload.lang = "zh"
			var reply: Dictionary = await panel._request(route + "/design/direction" + endpoint, HTTPClient.METHOD_POST, payload)
			if generation != panel.identity_generation:
				return
			if write and reply.get("id") == chat:
				panel.conversation = reply
				version = int(reply.version)
				panel._render()
				_show_source()
				feedback.text = "已保存方向修订 %d。" % int(panel._direction().revision)
				_lock(false)
				latest_body.hide()
				return
			if not write and reply.get("content") is String and not reply.content.strip_edges().is_empty():
				body.text = reply.content
				feedback.text = "草稿已生成，可继续编辑后保存。"
				_lock(false)
				return
			read_required = panel.last_status == 409 or (write and (panel.last_status == 0 or panel.last_status >= 500 or panel.last_status == 200))
			if not read_required:
				feedback.text = "请求失败（%d），草稿已保留，可重试。" % panel.last_status
				_lock(false)
				return
		var latest: Dictionary = await panel._request(route)
		if generation != panel.identity_generation:
			return
		if latest.get("id") != chat:
			feedback.text = "请先读回会话核对保存结果，草稿已保留。"
			_lock(false)
			return
		panel.conversation = latest
		panel._notice("")
		latest_body.hide()
		panel._render()
		version = int(latest.version)
		_show_source()
		var current: Dictionary = panel._direction()
		read_required = false
		_lock(false)
		if latest.get("requirement_id") != null or current.get("confirmed_at") != null:
			feedback.text = "方向已确认，可复制此处草稿。"
			suggest.disabled = true
			save.disabled = true
		elif current.get("body") == entered:
			feedback.text = "已读回相同正文的方向修订 %d。" % int(current.revision)
		else:
			feedback.text = "已读回最新会话。请核对下方已保存正文，再决定是否保存本地草稿。"
			latest_body.text = current.get("body", "（空）")
			latest_body.show()

	func _update_save() -> void:
		var current: Dictionary = panel._direction()
		save.disabled = panel.busy or (not read_required and (
			body.text.strip_edges().is_empty() or current.get("body") == body.text
			or panel.conversation.get("requirement_id") != null or current.get("confirmed_at") != null))
