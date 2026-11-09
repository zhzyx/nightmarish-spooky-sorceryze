@tool
extends SceneTree

var errors := []

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, reason: String) -> void:
	if not ok:
		push_error(reason)
		errors.append(reason)

func wait_for_details(panel) -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while panel.issue_inspector.busy and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	check(not panel.issue_inspector.busy, "No document receipt")

func read_graph(_url: String) -> Dictionary:
	return {}

func apply_graph(_url: String, _revision: String, _execution: String, _plan: Dictionary) -> Dictionary:
	return {}

func run() -> void:
	await create_timer(1).timeout
	var repo := OS.get_environment("DAQIAN_TEST_REPO")
	EditorInterface.get_editor_settings().set_setting("gonggong/workspace", repo)
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	await panel.refresh()
	panel.host = self
	var rows := []
	for number in [1, 2]:
		rows.append({"number":number, "request":"request-%d" % number, "title":"Fixture", "status":"in-progress",
			"owners":[], "creator":"tester", "dependencies":[], "development":true, "decision":false, "updated":"stamp", "url":"https://github.com/fixture/board/issues/%d" % number, "closed":number == 2,
			"plan":{"nodes":{"requirement":{"kind":"text","title":"需求","value":"Selected content"}},"edges":[]}})
	panel.board.issues = rows
	await panel._open_issue(rows[0])
	await wait_for_details(panel)
	var details = panel.issue_inspector
	check(details.visible and details.field.text == "original" and details.issue_link.uri == rows[0].url, "Missing default Issue document or link")
	check("Related" in details.relations.get_parsed_text() and "父工单" in details.relations.get_parsed_text(), "Missing linked issue")
	details.field.insert_text_at_caret("draft ")
	details.field.text_changed.emit()
	check(not details.save.disabled and not details.revert.disabled, "Document controls stayed disabled")
	var draft: String = details.field.text
	var card: GraphNode = panel.editor.canvas.get_node("requirement")
	panel.editor.canvas.node_selected.emit(card)
	check(details.node_id == "requirement" and "Selected content" in details.card_text.text and "关联板块" in details.card_text.text, "Selected card lost content or connections")
	panel.editor.context.states["requirement"] = "running"
	panel.editor.refresh_states()
	check(panel.graph_script.FlowCanvas.state_text("running") in details.card_text.text, "Selected card state stayed stale")
	for frame in 3:
		await process_frame
	if not panel.issue_split.vertical:
		check(details.get_global_rect().end.x <= panel.editor.get_global_rect().position.x + 1, "Inspector not left of graph")
	else:
		check(details.get_global_rect().end.y <= panel.editor.get_global_rect().position.y + 1, "Inspector overlaps graph")
	details.back.pressed.emit()
	check(details.field.text == draft, "Card selection lost document edits")
	await panel._open_issue(rows[1])
	await wait_for_details(panel)
	check(details.field.text == "original", "Draft leaked across issues")
	check(panel.graph_script.FlowCanvas.state_text("closed") in details.summary.text, "Closed issue showed stale workflow status")
	await panel._open_issue(rows[0])
	await wait_for_details(panel)
	check(details.field.text == draft, "Navigation discarded unsaved text")
	details.revert.pressed.emit()
	check(details.field.text == "original" and details.save.disabled, "Revert failed")
	details.field.text = "已修改\nsecond line"
	details.field.text_changed.emit()
	details.save.pressed.emit()
	await wait_for_details(panel)
	check(details.save.disabled and "已保存" in details.feedback.text, "Save receipt missing")
	panel._show_board()
	await panel._open_issue(rows[0])
	await wait_for_details(panel)
	check(details.field.text == "已修改\nsecond line", "Reopened document did not contain saved text")
	if errors.is_empty():
		print("DAQIAN_DETAILS_OK")
	quit(0 if errors.is_empty() else 1)
