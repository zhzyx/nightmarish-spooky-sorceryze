@tool
extends SceneTree

var errors := []

func _initialize():
	run.call_deferred()

func check(ok: bool, message: String):
	if not ok:
		errors.append(message)
		push_error(message)

func run():
	await create_timer(1.0).timeout
	var repo := OS.get_environment("DAQIAN_TEST_REPO")
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", repo)
	settings.set_setting("gonggong/python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	var backend = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.find_child("APIEndpoint", true, false).text = "http://127.0.0.1:1/v1/chat/completions"
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	panel._compose_requirement()
	if not panel.publish_dialog.visible:
		push_error("Creation dialog unavailable")
		quit(1)
		return
	check(panel.publish_dialog.get_ok_button().disabled, "Blank draft can be sent")
	var graph = panel.editor
	var source = panel.current
	check(graph.canvas.has_node("wf-analysis") and graph.draft.nodes.size() == 1, "Analysis card missing or executable")
	panel.requirement_input.text = "Fixture requirement"
	panel.requirement_input.text_changed.emit()
	panel.model_options.select(panel.model_options.item_count - 1)
	panel.model_options.item_selected.emit(panel.model_options.selected)
	panel.manual_model.text = "fixture-model"
	panel.manual_model.text_changed.emit("fixture-model")
	panel.requirement_input.text = "需".repeat(16000)
	panel.requirement_input.text_changed.emit()
	check(not panel.publish_dialog.get_ok_button().disabled, "16000 characters rejected")
	panel.requirement_input.text += "求"
	panel.requirement_input.text_changed.emit()
	check(panel.publish_dialog.get_ok_button().disabled, "Oversized requirement accepted")
	panel.requirement_input.text = "Fixture requirement"
	panel.requirement_input.text_changed.emit()
	panel.publish_dialog.get_cancel_button().pressed.emit()
	await process_frame
	await process_frame
	var calls := repo.path_join("tools/calls")
	check(not FileAccess.file_exists(calls), "Cancel sent a request")
	panel.publish_button.pressed.emit()
	check(panel.requirement_input.text == "Fixture requirement" and panel._selected_model() == "fixture-model", "Draft lost text or selection")
	panel.publish_dialog.get_ok_button().pressed.emit()
	panel.publish_dialog.get_ok_button().pressed.emit()
	var deadline := Time.get_ticks_msec() + 10000
	while Time.get_ticks_msec() < deadline and panel.saved.get("intake", {}).get(source, {}).get("phase") != "error":
		await create_timer(0.05).timeout
	if FileAccess.file_exists(calls):
		var lines := FileAccess.get_file_as_string(calls).strip_edges().split("\n")
		check(lines.size() == 1 and JSON.parse_string(lines[0]) == ["Fixture requirement","http","fixture-model"], "Wrong or duplicate Yanshi request")
	else:
		check(false, "No native Yanshi request: " + panel.publish_status.text)
	chat.find_child("APIModel", true, false).text = "corrected-model"
	chat.find_child("ChatInput", true, false).text = "重试"
	chat.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 10000
	while Time.get_ticks_msec() < deadline and panel.saved.get("intake", {}).get(source, {}).get("phase") != "ready":
		await create_timer(0.05).timeout
	if FileAccess.file_exists(calls):
		var attempts := FileAccess.get_file_as_string(calls).strip_edges().split("\n")
		check(attempts.size() == 2 and JSON.parse_string(attempts[-1]) == ["Fixture requirement","http","corrected-model"], "Explicit retry ignored corrected model")
	check(panel.saved.get("submitted", {}).has(source), "Missing send receipt")
	check(panel.saved.get("linked", {}).get(source, {}).get("number") == 123, "Missing Issue binding")
	check(graph.canvas.has_node("wf-prepare") and graph.canvas.has_node("wf-verify"), "Ready result did not update workflow")
	var count = graph.canvas.get_connection_list().size()
	graph.draw_graph()
	check(count >= 5 and graph.canvas.get_connection_list().size() == count and graph.draft.nodes.size() == 1, "Redraw duplicated or persisted generated steps")
	var custom = graph.add_node("text", Vector2(50, 600))
	graph.draft.nodes[custom].value = "Keep personal notes"
	var fixture := {"number":123, "url":"https://github.com/fixture/board/issues/123",
		"status":"in-progress", "development":true, "dependencies":["https://github.com/fixture/board/issues/100"]}
	panel.board.issues = [fixture]
	panel._sync_workflow()
	check(graph.canvas.has_node("wf-integrate") and graph.canvas.has_node("wf-deliver"), "Development delivery steps missing")
	fixture.status = "needs-decision"
	fixture.plan = {"nodes":{"pending":{"kind":"question","title":"待确认","value":"Remote question?"}}}
	panel._sync_workflow()
	check(not graph.canvas.has_node("wf-prepare") and graph.canvas.has_node("wf-questions-" + "Remote question?".sha256_text().left(20)), "Remote decision did not supersede cached ready result")
	panel._requirement_phase(source, "questions", {"questions":["Remote question?"]})
	fixture.status = "in-progress"
	fixture.plan.nodes.clear()
	panel._sync_workflow()
	check(graph.canvas.has_node("wf-prepare") and not graph.canvas.has_node("wf-questions-" + "Remote question?".sha256_text().left(20)), "Remote decision resolution did not resume preparation")
	fixture.status = "blocked"
	panel._requirement_phase(source, "questions", {"scope":["New scope"], "questions":["Which target?"], "acceptance":["Verify"]})
	check(graph.canvas.has_node("wf-blocked") and not graph.canvas.has_node("wf-prepare"), "Blocked question still appears ready")
	check(not graph.canvas.has_node("wf-scope-" + "Implement".sha256_text().left(20)), "Superseded scope still displayed")
	check(graph.canvas.has_node("wf-questions-" + "Which target?".sha256_text().left(20)), "Missing clarification question")
	panel._save()
	panel.board = {}
	panel._show_board()
	panel._show_issue(source, {"revision":"", "plan":graph.rules.new_plan(), "context":{}})
	check(graph.draft.nodes.has(custom) and graph.canvas.has_node("wf-analysis"), "Reopening lost the personal node or framework stages")
	if errors.is_empty():
		print("DAQIAN_PUBLISH_OK")
	quit(0 if errors.is_empty() else 1)
