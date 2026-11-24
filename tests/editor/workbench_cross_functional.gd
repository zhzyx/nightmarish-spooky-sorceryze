extends "res://workbench_issue_detail.gd"

var fixture: Dictionary
var session: Node
var detail: Node
var widget: Node
var report := {"sessions": []}
var revision := ""
var module := ""


func login(role: String) -> bool:
	var dock := await open_workbench()
	if dock == null:
		return false
	session = dock.find_child("WorkbenchBusinessSession", true, false)
	detail = session.get_node("WorkbenchIssueDetail")
	widget = detail.get_node("creative_judgments")
	if not session.get_identity().is_empty():
		session.find_child("SignOut", true, false).pressed.emit()
	session.find_child("ChooseAccount", true, false).pressed.emit()
	session.find_child("AccountEmail", true, false).text = role + "@example.invalid"
	session.find_child("AccountSecret", true, false).text = OS.get_environment("Q02_PASSWORD")
	session.find_child("Authenticate", true, false).pressed.emit()
	if not require(await wait_for(func(): return session.get_identity().get("id") == fixture.actors[role]), "login " + role):
		return false
	report.sessions.append(session.get_identity())
	await detail.open_issue(int(fixture.number))
	if role == "excluded":
		var message: String = detail.find_child("IssueDetailStatus", true, false).text
		report.denied_read = message
		return require(detail.get_detail().is_empty() and detail.find_child("IssueDetailFields", true, false).text.is_empty() and message == "没有权限查看此工单", "excluded read")
	return require(detail.get_detail().get("id") == fixture.issue, "authorized detail " + role)


func submit_artwork() -> bool:
	var upload := detail.find_child("UploadIssueArtifact", true, false) as Button
	var picker := detail.find_child("IssueArtifactSource", true, false) as FileDialog
	var versions := detail.find_child("IssueArtifactVersions", true, false) as OptionButton
	if not require(await wait_for(func(): return not upload.disabled) and upload.is_visible_in_tree(), "upload entry"):
		return false
	upload.pressed.emit()
	if not require(picker.visible, "source dialog"):
		return false
	picker.hide()
	picker.file_selected.emit(fixture.source)
	if not require(await wait_for(func(): return versions.item_count == 1), "uploaded artifact"):
		return false
	var ref: Dictionary = versions.get_item_metadata(versions.selected)
	report.attachment = ref
	revision = ref.revision
	module = ref.module
	var asset := {"module": module, "path": ref.path, "kind": "concept", "revision": revision, "expected_version": int(ref.version), "call_id": "submit-icon"}
	var result: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/%s/work/submit_asset" % fixture.issue, asset)
	if not require(result.status == 200, "artist submit " + str(result.status)):
		return false
	report.submission = result.data.history.back()
	return true


func open_judgment() -> bool:
	widget.browse.pressed.emit()
	if not require(await wait_for(func(): return widget.rows.get_child_count() == 1), "personal judgment list"):
		return false
	widget.rows.get_child(0).pressed.emit()
	if not require(await wait_for(func(): return widget.selected.get("revision") == revision and not widget.transfer.disabled), "exact version and eligible recipients"):
		return false
	detail.get_node("issue_revisions").revision_view.hide()
	return true


func transfer() -> bool:
	for index in widget.recipients.item_count:
		if widget.recipients.get_item_metadata(index) == fixture.actors.artist:
			widget.recipients.select(index)
			widget.note.text = "请美术核对图标轮廓"
			widget.transfer.pressed.emit()
			return require(await wait_for(func(): return widget.status.text == "暂无待本人判断的事项"), "sender after transfer")
	return require(false, "artist missing from recipients")


func consume() -> bool:
	var output := "user://approved.png"
	var route := "/api/v1/issues/%s/work/approved-asset?module=%s&kind=concept&path=icon.png&revision=%s" % [fixture.issue, module, revision]
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route, {}, 12.0, output)
	if not require(reply.status == 200 and FileAccess.get_sha256(output) == report.submission.digest, "approved bytes"):
		return false
	var icon := Image.load_from_file(output)
	if not require(icon != null and icon.get_size() == Vector2i(8, 8) and icon.get_pixel(0, 0).is_equal_approx(Color.CORAL), "approved icon decode"):
		return false
	report.consumed = {"sha256": FileAccess.get_sha256(output), "width": icon.get_width(), "height": icon.get_height(), "pixel": icon.get_pixel(0, 0).to_html(false)}
	var draft := detail.find_child("IssueCommentDraft", true, false) as TextEdit
	draft.text = "程序已读取签认原件并核对像素"
	draft.text_changed.emit()
	var post := detail.find_child("PostIssueComment", true, false) as Button
	if not require(await wait_for(func(): return not post.disabled), "program comment entry"):
		return false
	post.pressed.emit()
	var thread := detail.find_child("IssueCommentThread", true, false) as ItemList
	if not require(await wait_for(func(): return thread.item_count == 1), "program comment receipt"):
		return false
	report.comment = thread.get_item_metadata(0)
	return true


func run() -> void:
	fixture = JSON.parse_string(OS.get_environment("Q02_FIXTURE"))
	if not await login("artist") or not await submit_artwork():
		return
	if not await login("planner") or not await open_judgment() or not await transfer():
		return
	if not await login("artist") or not await open_judgment():
		return
	report.handoff = widget.description.text
	widget.note.text = "已核对图标轮廓，采纳此版本"
	widget.approve.pressed.emit()
	if not require(await wait_for(func(): return "提交 v%d 已采纳" % int(report.submission.version) in widget.status.text), "signature receipt"):
		return
	report.signature = widget.status.text
	if not await login("programmer") or not await consume():
		return
	if not await login("excluded"):
		return
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/%s/comments" % fixture.issue, {"body": "未获授权的评论", "call_id": "excluded-comment"})
	if not require(reply.status == 403 and not reply.data.has("id"), "excluded write " + str(reply.status)):
		return
	report.denied_write = reply.status
	print("WORKBENCH_REPORT=" + JSON.stringify(report))
	quit(0)
