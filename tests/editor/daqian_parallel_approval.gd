@tool
extends SceneTree

var chat
var board
var completions := {}
var end_states := {}

func _initialize():
	run.call_deferred()

func run():
	await create_timer(1.0).timeout
	chat = root.find_child("AI Chat", true, false)
	board = root.find_child("DaqianWorkspace", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("DAQIAN_TEST_REPO"))
	chat.set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var controls = chat.get_ai_settings_control()
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
	for row in rows:
		await board._open_issue(row)
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
	if a.root == b.root or a.token == b.token or a.tool != "run_command" or b.tool != a.tool or chat.confirm_daqian_issue_approval(a.url, b.token):
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
	while (completions.size() < 2 or end_states.size() < 2) and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	if not completions.has(rows[0].request) or not completions.has(rows[1].request) or FileAccess.file_exists(a.root.path_join("executions")) or FileAccess.get_file_as_string(b.root.path_join("executions")).strip_edges() != "once" or end_states.get(a.url) != "cancelled" or end_states.get(b.url) != "completed":
		push_error("Unexpected command effects or receipts " + str([completions, end_states]))
		quit(8)
		return
	print("DAQIAN_PARALLEL_APPROVAL_OK ", JSON.stringify({"unrelated_lookup_usec":lookup_usec,"terminal":end_states,"execution_receipts":completions,"separate_candidates":a.root != b.root}))
	quit(0)
