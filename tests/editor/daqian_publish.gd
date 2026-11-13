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
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	var panel = dock.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	var backend = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.find_child("APIModel", true, false).text = "fixture"
	chat.get_ai_settings_control().find_child("APIEndpoint", true, false).text = "http://127.0.0.1:1/v1/chat/completions"
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	panel._compose_requirement()
	var source: String = panel.current
	var graph = panel.editor
	check(not graph.canvas.has_node("wf-analysis"), "Unconfirmed requirements already show Yanshi")
	panel.requirement_input.text = "需".repeat(16000)
	panel.requirement_input.text_changed.emit()
	check(not panel.publish_confirm.disabled, "16000 characters rejected")
	panel.requirement_input.text += "求"
	panel.requirement_input.text_changed.emit()
	check(panel.publish_confirm.disabled, "Oversized requirement accepted")
	panel.requirement_input.text = "Fixture requirement"
	panel.requirement_input.text_changed.emit()
	panel.publish_cancel.pressed.emit()
	await process_frame
	var calls := repo.path_join("tools/calls")
	check(not FileAccess.file_exists(calls), "Saving a draft sent a request")
	panel.publish_button.pressed.emit()
	check(panel.requirement_input.text == "Fixture requirement", "Draft lost text")
	await panel._confirm_publish()
	var binding: Dictionary = panel.saved.get("linked", {}).get(source, {})
	if binding.get("number") != 124:
		push_error("No verified Issue after model failure")
		quit(1)
		return
	check(panel.publish_button.text == "用当前模型重试判断" and not graph.canvas.has_node("wf-analysis"), "Failed routing incorrectly invoked Yanshi or erased the issue")
	await panel._start_or_view_direct(binding)
	check(graph.canvas.has_node("wf-analysis") and graph.canvas.has_node("wf-routing") and not graph.canvas.has_node("wf-prepare"), "Delegation missing or awaiting answer already runnable")
	check(panel.publish_button.text == "补充需求", "Missing bound clarification action")
	await panel._respond_to_wait()
	var card := graph.canvas.get_node("wf-clarification") as GraphNode
	var inline := card.get_node("AnswerInput") as TextEdit
	check(inline.visible and not panel.clarification_dialog.visible, "Clarification action did not open the graph editor")
	inline.insert_text_at_caret("  The current")
	await process_frame
	card.get_node("AnswerActions/CancelAnswer").pressed.emit()
	check(not inline.visible and not panel.clarification_dialog.visible, "Cancel left the inline editor open")
	card.get_node("FillAnswer").pressed.emit()
	check(inline.visible and inline.text == "  The current", "Reopening the same question lost its draft")
	graph.draw_graph()
	await panel._respond_to_wait()
	card = graph.canvas.get_node("wf-clarification")
	inline = card.get_node("AnswerInput")
	check(inline.text == "  The current", "A graph redraw lost the current answer")
	# Exercise the fallback separately from the normal graph interaction.
	var many := []
	for i in 20:
		many.append("问题 %d：" % i + "请说明需要实现的目标与验收方式。".repeat(12))
	panel._open_clarification(binding, many)
	for i in 4:
		await process_frame
	var dialog: ConfirmationDialog = panel.clarification_dialog
	check(panel.get_mouse_filter_with_override() == Control.MOUSE_FILTER_IGNORE and panel.clarification_answer.get_mouse_filter_with_override() != Control.MOUSE_FILTER_IGNORE, "Modal hover reached the workspace or disabled its answer field")
	var previous_zoom: float = graph.canvas.zoom
	graph.canvas.zoom = panel.ZOOM_TO_PARENT
	panel._check_canvas_zoom()
	check(panel.current == source, "Background zoom left the draft while its modal was open")
	graph.canvas.zoom = previous_zoom
	var viewport_rect := Rect2(Vector2.ZERO, Vector2(dialog.size))
	var scrollbar: VScrollBar = panel.clarification_scroll.get_v_scroll_bar()
	check(scrollbar.max_value > scrollbar.page and viewport_rect.encloses(dialog.get_ok_button().get_global_rect()) and viewport_rect.encloses(dialog.get_cancel_button().get_global_rect()), "Long clarification questions pushed dialog actions offscreen")
	panel.clarification_answer.text = "待补充的草稿"
	dialog.get_cancel_button().pressed.emit()
	await process_frame
	panel._open_clarification(binding, many)
	check(not dialog.get_ok_button().disabled and panel.clarification_answer.text == "待补充的草稿", "Cancel lost the unsent answer")
	dialog.notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	await process_frame
	check(not dialog.visible, "Title-bar close did not dismiss clarification")
	check(panel.mouse_behavior_recursive == Control.MOUSE_BEHAVIOR_INHERITED, "Closing the modal left workspace controls disabled")
	await panel._start_or_view_direct(binding)
	check(not dialog.visible and inline.visible and inline.text == "  The current", "Toolbar did not return to the same inline draft")
	inline.text = "  The current target  "
	inline.text_changed.emit()
	card.get_node("AnswerActions/SubmitAnswer").pressed.emit()
	panel._submit_inline_answer("The current target") # Race a second click against the same in-flight judgment.
	var deadline := Time.get_ticks_msec() + 10000
	while panel.publish_button.text != "用当前模型重试判断" and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(panel.publish_button.text == "用当前模型重试判断" and graph.workflow.clarification_history.is_empty(), "Failed answer was represented as completed")
	await panel._start_or_view_direct(binding)
	check(graph.canvas.has_node("wf-prepare") and graph.canvas.has_node("wf-verify"), "Answered requirement did not become ready")
	var expected_history := [{"questions":["Which target?"], "answer":"The current target"}]
	check(graph.workflow.clarification_history == expected_history, "Verified retry did not recover the answered question")
	var other_revision := binding.duplicate()
	other_revision.revision = "another-revision"
	check(panel._confirmed_clarifications(other_revision, {}).is_empty(), "A different requirement revision inherited the answer")
	var records := FileAccess.get_file_as_string(calls).strip_edges().split("\n")
	var actions := []
	for line in records:
		var call: Array = JSON.parse_string(line)
		actions.append(call[0])
		if call[0] == "issue-route":
			check(call[1].issue_number == binding.number and call[1].request_id == binding.request, "Clarification lost Issue binding")
	check(actions == ["issue-direct","issue-route","issue-route","issue-route","issue-route"], "Unexpected publication, analysis or execution order")
	await panel._start_or_view_direct(binding)
	check(panel.publish_button.text == "用当前模型重试判断" and not graph.canvas.has_node("wf-prepare"), "Start rejection left stale readiness cached")
	await panel._start_or_view_direct(binding)
	var custom := "legacy_note"
	graph.draft.nodes[custom] = {"kind":"text", "title":"Notes", "value":"Keep personal notes"}
	panel._save()
	panel._show_board()
	panel._show_issue(source, {"revision":"", "plan":graph.rules.new_plan(), "context":{}})
	check(graph.draft.nodes.has(custom) and graph.canvas.has_node("wf-analysis") and graph.canvas.has_node("wf-routing"), "Reopening lost personal nodes or real framework decision")
	check(graph.workflow.clarification_history == expected_history, "Reopening the draft lost its confirmed answer")
	if errors.is_empty():
		print("DAQIAN_PUBLISH_OK")
	quit(0 if errors.is_empty() else 1)
