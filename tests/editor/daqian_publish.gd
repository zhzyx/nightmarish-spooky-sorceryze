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
	var backend = chat.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	chat.get_ai_settings_control().find_child("APIModel", true, false).text = "fixture"
	chat.get_ai_settings_control().find_child("APIEndpoint", true, false).text = "http://127.0.0.1:1/v1/chat/completions"
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await panel.refresh()
	panel._compose_requirement()
	var source: String = panel.current
	var graph = panel.editor
	check(not graph.canvas.has_node("wf-analysis"), "Unconfirmed requirements already show Yanshi")
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
	await panel._start_or_view_direct(binding)
	check(panel.clarification_dialog.visible and panel.clarification_prompt.text == "Which target?", "Actual question not presented")
	panel.clarification_answer.text = "The current target"
	panel.clarification_answer.text_changed.emit()
	panel.clarification_dialog.get_ok_button().pressed.emit()
	var deadline := Time.get_ticks_msec() + 10000
	while panel.publish_button.text != "用当前模型重试判断" and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(panel.publish_button.text == "用当前模型重试判断", "Failed processing of accepted answer left stale question cached")
	await panel._start_or_view_direct(binding)
	check(graph.canvas.has_node("wf-prepare") and graph.canvas.has_node("wf-verify"), "Answered requirement did not become ready")
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
	var custom = graph.add_node("text", Vector2(50, 600))
	graph.draft.nodes[custom].value = "Keep personal notes"
	panel._save()
	panel._show_board()
	panel._show_issue(source, {"revision":"", "plan":graph.rules.new_plan(), "context":{}})
	check(graph.draft.nodes.has(custom) and graph.canvas.has_node("wf-analysis") and graph.canvas.has_node("wf-routing"), "Reopening lost personal nodes or real framework decision")
	if errors.is_empty():
		print("DAQIAN_PUBLISH_OK")
	quit(0 if errors.is_empty() else 1)
