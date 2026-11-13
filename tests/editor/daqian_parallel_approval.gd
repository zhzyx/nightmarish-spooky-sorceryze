@tool
extends SceneTree

var chat
var board
var completions := {}
var end_states := {}
var preparing_history := OS.get_environment("DAQIAN_TEST_SEED") == "1"

func _initialize():
	run.call_deferred()

func button_named(parent: Control, label: String) -> Button:
	for button in parent.find_children("*", "Button", true, false):
		if button.text == label:
			return button
	return null


func wait_for_marker(name: String) -> bool:
	var path := OS.get_environment("DAQIAN_TEST_REPO").path_join(name)
	var deadline := Time.get_ticks_msec() + 20000
	while not FileAccess.file_exists(path) and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	return FileAccess.file_exists(path)


func open_conversation() -> bool:
	var open := button_named(board.actions, "工单对话与模型")
	if not open or not open.is_visible_in_tree():
		return false
	open.pressed.emit()
	var deadline := Time.get_ticks_msec() + 10000
	while not board.conversation.is_visible_in_tree() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	return board.conversation.is_visible_in_tree()


func submit_ui(row: Dictionary, entry: String) -> bool:
	var message := "UI dispatch #%d" % int(row.number)
	if entry == "existing" and row.number == 426:
		if not await open_conversation():
			return false
		board._leave_conversation()
		if preparing_history:
			return true
	if entry == "canvas" or (entry == "existing" and row.number == 426):
		board.canvas_panel.canvas_message.text = message
		var send := button_named(board.canvas_panel.canvas_bar, "发送")
		if not send or not send.is_visible_in_tree():
			return false
		send.pressed.emit()
		if row.number == 210:
			return await wait_for_marker("canvas-route-210")
		return true
	if not await open_conversation():
		return false
	board.conversation_host.find_child("ChatInput", true, false).text = "Prepare saved root conversation" if preparing_history else message
	var send: Button = board.conversation_host.find_child("Send", true, false)
	if not send.is_visible_in_tree() or send.disabled:
		return false
	send.pressed.emit()
	board._leave_conversation()
	if entry == "existing":
		return await wait_for_marker("root-worker-busy")
	return true


func saved_worker_pair(settings: EditorSettings, rows: Array) -> bool:
	var records: Array = settings.get_project_metadata("daqian", "bindings", {}).values()
	var main_found := records.any(func(record): return record.get("source") == rows[0].url and not record.has("worker_key"))
	var worker_found := records.any(func(record): return record.get("source") == rows[1].url and not str(record.get("worker_key", "")).is_empty())
	return main_found and worker_found


func run():
	await create_timer(1.0).timeout
	chat = root.find_child("AI Chat", true, false)
	board = root.find_child("DaqianWorkspace", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("DAQIAN_TEST_REPO"))
	chat.set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var controls = chat
	controls.find_child("APIEndpoint", true, false).text = OS.get_environment("DAQIAN_TEST_ENDPOINT")
	controls.find_child("APIModel", true, false).text = "fixture"
	controls.find_child("AutoExecuteCommands", true, false).button_pressed = false
	await board.refresh()
	chat.daqian_execution_finished.connect(func(receipt, error, preflight): completions[receipt.token] = [error, preflight])
	chat.daqian_work_event.connect(func(_root, binding, _worker, kind, _phase, status):
		if kind == "request_end":
			end_states[binding.source_ref] = status)
	var rows: Array = board.board.issues
	if rows.size() != 2:
		push_error("Expected two verified fixture Issues")
		quit(1)
		return
	var entry := OS.get_environment("DAQIAN_TEST_ENTRY")
	var dock = root.find_child("Daqian", true, false)
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	if entry == "existing" and not preparing_history and not saved_worker_pair(settings, rows):
		push_error("Saved main conversation and empty Issue worker did not survive restart")
		quit(10)
		return
	for row in rows:
		await board._open_issue(row)
		if entry in ["canvas", "conversation", "existing"]:
			if not await submit_ui(row, entry):
				push_error("UI dispatch unavailable for #%d: %s %s" % [row.number, board.notice.text, board.canvas_panel.canvas_log.text])
				quit(9)
				return
			continue
		var err: String = board._bind_conversation(row)
		if not err.is_empty():
			push_error(err)
			quit(2)
			return
		board._mount_conversation(row)
		var selection = {"backend":0, "id":"fixture", "execution_receipt":{"token":row.request}}
		err = chat.open_daqian_chat(row.url, row.number, row.request, "Run the same command", false, selection, true)
		if not err.is_empty():
			push_error(err)
			quit(3)
			return
		board._leave_conversation()
	if preparing_history:
		FileAccess.open(OS.get_environment("DAQIAN_TEST_REPO").path_join("seed-worker-saved"), FileAccess.WRITE).close()
		var deadline := Time.get_ticks_msec() + 10000
		while end_states.get(rows[0].url) != "completed" and Time.get_ticks_msec() < deadline:
			await create_timer(0.05).timeout
		if end_states.get(rows[0].url) == "completed" and saved_worker_pair(settings, rows):
			print("DAQIAN_FIXTURE_HISTORY_READY")
			quit(0)
		else:
			push_error("Failed preparing historical Issue bindings " + str(end_states))
			quit(10)
		return
	var deadline := Time.get_ticks_msec() + 55000
	var a: Dictionary
	var b: Dictionary
	while Time.get_ticks_msec() < deadline:
		a = chat.get_daqian_issue_approval(rows[0].url)
		b = chat.get_daqian_issue_approval(rows[1].url)
		if not a.is_empty() and not b.is_empty():
			break
		await create_timer(0.1).timeout
	if a.is_empty() or b.is_empty():
		print("UI receipts ", board.canvas_panel.canvas_history, " current ", board.current, " notice ", board.notice.text)
		for row in rows:
			print("OPEN ", board._bind_conversation(row))
			board._mount_conversation(row)
			for label in board.conversation_host.find_children("*", "RichTextLabel", true, false):
				print(label.get_parsed_text().right(700))
			board._leave_conversation()
		push_error("Two independent command approvals did not arrive")
		quit(4)
		return
	# A card on a third Issue must not synchronously run Git for either pending candidate.
	var trace := ProjectSettings.globalize_path("res://approval-lookup-git.jsonl")
	var had_trace := OS.has_environment("GIT_TRACE2_EVENT")
	var previous_trace := OS.get_environment("GIT_TRACE2_EVENT")
	OS.set_environment("GIT_TRACE2_EVENT", trace)
	var lookup_start := Time.get_ticks_usec()
	var unrelated: Dictionary = chat.get_daqian_issue_approval("https://github.com/fixture/board/issues/212")
	var lookup_usec := Time.get_ticks_usec() - lookup_start
	var launched_git := FileAccess.file_exists(trace)
	if had_trace:
		OS.set_environment("GIT_TRACE2_EVENT", previous_trace)
	else:
		OS.unset_environment("GIT_TRACE2_EVENT")

	if launched_git or not unrelated.is_empty():
		push_error("Unrelated Issue queried another candidate checkout")
		quit(9)
		return
	if entry in ["canvas", "existing"] and board.conversation.is_visible_in_tree():
		var displayed := ""
		for label in board.conversation_host.find_children("*", "RichTextLabel", true, false):
			displayed += label.get_parsed_text()
		if not displayed.contains("UI dispatch #%d" % int(rows[1].number)) or displayed.contains("UI dispatch #%d" % int(rows[0].number)):
			push_error("A late execution replaced the currently displayed Issue conversation")
			quit(11)
			return
	if board.current != rows[1].url or a.root == b.root or a.token == b.token or a.tool != "run_command" or b.tool != a.tool or chat.confirm_daqian_issue_approval(a.url, b.token):
		push_error("Candidate or exact approval isolation failed")
		quit(5)
		return
	if not board._bind_conversation(rows[0]).is_empty():
		quit(6)
		return
	board._mount_conversation(rows[0])
	board.conversation_host.find_child("Stop", true, false).pressed.emit()
	board._leave_conversation()
	if not chat.get_daqian_issue_approval(a.url).is_empty() or not chat.confirm_daqian_issue_approval(b.url, b.token):
		push_error("Cancel A or approve B failed")
		quit(7)
		return
	deadline = Time.get_ticks_msec() + 30000
	var receipt_count := int({"native":2, "canvas":2, "existing":1, "conversation":0}[entry])
	while (completions.size() < receipt_count or end_states.size() < 2) and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	if completions.size() != receipt_count or (entry == "native" and (not completions.has(rows[0].request) or not completions.has(rows[1].request))):
		push_error("Unexpected execution receipts " + str(completions))
		quit(8)
		return
	if FileAccess.file_exists(a.root.path_join("executions")) or FileAccess.get_file_as_string(b.root.path_join("executions")).strip_edges() != "once" or end_states.get(a.url) != "cancelled" or end_states.get(b.url) != "completed":
		push_error("Unexpected command effects or receipts " + str([completions, end_states]))
		quit(8)
		return
	print("DAQIAN_PARALLEL_APPROVAL_OK ", JSON.stringify({"entry":entry,"unrelated_lookup_usec":lookup_usec,"terminal":end_states,"execution_receipts":completions,"separate_candidates":a.root != b.root}))
	quit(0)
