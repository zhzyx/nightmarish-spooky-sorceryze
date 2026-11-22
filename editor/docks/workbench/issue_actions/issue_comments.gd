@tool
extends VBoxContainer

var _session: Node
var _generation := 0
var _busy := false
var _route := ""
var _pending := {}
var _call_id := ""
var _bookmark_key := ""
var _thread := ItemList.new()
var _selected_body := RichTextLabel.new()
var _original := Button.new()
var _draft := TextEdit.new()
var _post := Button.new()
var _reply := Button.new()
var _status := Label.new()


func _ready() -> void:
	_session = get_parent().get_parent()
	var heading := Label.new()
	heading.text = "工单评论"
	add_child(heading)
	_thread.name = "IssueCommentThread"
	_thread.custom_minimum_size.y = 96
	_thread.item_selected.connect(_select)
	add_child(_thread)
	_selected_body.name = "SelectedCommentBody"
	_selected_body.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_selected_body.selection_enabled = true
	_selected_body.custom_minimum_size.y = 60
	add_child(_selected_body)
	_original.name = "LocateOriginalComment"
	_original.text = "查看被回复的评论"
	_original.pressed.connect(_locate_original)
	add_child(_original)
	_draft.name = "IssueCommentDraft"
	_draft.placeholder_text = "评论内容"
	_draft.custom_minimum_size.y = 54
	_draft.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_draft.text_changed.connect(_update_buttons)
	add_child(_draft)
	var actions := HFlowContainer.new()
	add_child(actions)
	_post.name = "PostIssueComment"
	_post.text = "发表评论"
	_post.pressed.connect(_send.bind(false))
	actions.add_child(_post)
	_reply.name = "ReplyToIssueComment"
	_reply.text = "回复选中评论"
	_reply.pressed.connect(_send.bind(true))
	actions.add_child(_reply)
	_status.name = "IssueCommentStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	get_parent().detail_changed.connect(_detail_changed)
	_detail_changed()


func _detail_changed() -> void:
	_generation += 1
	_route = ""
	_pending.clear()
	_call_id = ""
	_bookmark_key = ""
	_thread.clear()
	_selected_body.text = ""
	_status.text = ""
	_draft.text = ""
	_busy = false
	_update_buttons()
	var detail: Dictionary = get_parent().get_detail()
	visible = not detail.is_empty()
	if not visible:
		return
	_route = "/api/v1/issues/%s/comments" % str(detail.id).uri_encode()
	var identity: Dictionary = _session.get_identity()
	_bookmark_key = JSON.stringify([identity.id, identity.project, detail.id]).sha256_text()
	var settings := EditorInterface.get_editor_settings()
	var saved := str(settings.get_project_metadata("workbench_issue_comments", _bookmark_key, ""))
	await _load_thread(saved)


func _load_thread(restore_id: String) -> void:
	var attempt := _generation
	_busy = true
	_update_buttons()
	_status.text = "正在读取评论…"
	var result: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route)
	if attempt != _generation:
		return
	_busy = false
	if result.status != 200 or not result.data.get("comments") is Array:
		_status.text = "读取评论失败，请重新读取工单"
		_update_buttons()
		return
	_thread.clear()
	_selected_body.text = ""
	for comment in result.data.comments:
		var author := str(comment.get("author_name", ""))
		if author.is_empty():
			author = str(comment.author)
		var index := _thread.add_item("%s　%s" % [author, str(comment.body).get_slice("\n", 0)])
		_thread.set_item_metadata(index, comment)
		_thread.set_item_tooltip(index, "%s · %s" % [comment.author, comment.created_at])
	_status.text = "暂无评论" if _thread.item_count == 0 else ""
	_focus_id(restore_id)
	_update_buttons()


# Preserve the user's unsent draft when the current consultation posts a comment.
func reveal_comment(receipt: Dictionary) -> bool:
	if _busy or get_parent().get_detail().get("id") != receipt.get("issue_id"):
		return false
	await _load_thread(str(receipt.id))
	return _selected() == receipt


func _focus_id(comment_id: String) -> void:
	for index in _thread.item_count:
		if _thread.get_item_metadata(index).id == comment_id:
			_thread.select(index)
			_thread.ensure_current_is_visible()
			_select(index)
			return


func _selected() -> Dictionary:
	var indices := _thread.get_selected_items()
	return {} if indices.is_empty() else _thread.get_item_metadata(indices[0])


func get_selected_comment_id() -> String:
	return str(_selected().get("id", ""))


func _select(index: int) -> void:
	var comment: Dictionary = _thread.get_item_metadata(index)
	_selected_body.text = str(comment.body)
	EditorInterface.get_editor_settings().set_project_metadata("workbench_issue_comments", _bookmark_key, comment.id)
	_update_buttons()


func _locate_original() -> void:
	var comment := _selected()
	if comment.get("parent_id") != null:
		_focus_id(str(comment.parent_id))


func _update_buttons() -> void:
	var selected := _selected()
	_selected_body.visible = not selected.is_empty()
	_original.visible = selected.get("parent_id") != null
	_draft.editable = not _busy
	_post.disabled = _busy or _route.is_empty() or _draft.text.strip_edges().is_empty()
	_reply.disabled = _post.disabled or selected.is_empty()


func _send(as_reply: bool) -> void:
	if _post.disabled or (as_reply and _reply.disabled):
		return
	var payload := {"body": _draft.text}
	if as_reply:
		payload.parent_id = _selected().id
	if _pending != payload:
		_pending = payload.duplicate()
		_call_id = Crypto.new().generate_random_bytes(16).hex_encode()
	payload.call_id = _call_id
	var attempt := _generation
	_busy = true
	_update_buttons()
	var result: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, _route, payload)
	if attempt != _generation:
		return
	if result.status != 200 or not result.data.has("id"):
		_busy = false
		_status.text = "没有权限发表评论" if result.status == 403 else "未确认发布结果，可重试同一条评论"
		_update_buttons()
		return
	_draft.text = ""
	_pending.clear()
	_call_id = ""
	await _load_thread(str(result.data.id))
