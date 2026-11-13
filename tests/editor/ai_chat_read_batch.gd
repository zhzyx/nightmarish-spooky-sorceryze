@tool
extends SceneTree

var chat
var layout
var mode: String
var observed := []
var native_calls := {}
var armed := false
var changed := false

func _initialize():
	run.call_deferred()

func on_event(_root, _binding, _worker, kind, phase, status):
	if kind != "step":
		return
	observed.append([phase, status])
	if phase.begins_with("read-batch-") and status == "running":
		armed = true
		if mode == "acp":
			var journal = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_resume.json"))
			if journal is Dictionary:
				for call in journal.get("tool_calls", []):
					var args = JSON.parse_string(call.function.arguments)
					native_calls[str(args.path).get_file()] = call.id
	if armed and phase.begins_with("tool-") and status == "result_returned" and not changed and mode in ["steer", "stop"]:
		changed = true
		interrupt_batch.call_deferred()

func interrupt_batch():
	if mode == "stop":
		layout.find_child("Stop", true, false).pressed.emit()
	else:
		layout.find_child("ChatInput", true, false).text = "USE_CORRECTED_SCOPE"
		layout.find_child("Send", true, false).pressed.emit()

func run():
	mode = OS.get_environment("BATCH_CASE")
	chat = root.find_child("AI Chat", true, false)
	EditorInterface.get_editor_settings().set_setting("gonggong/workspace", OS.get_environment("DAQIAN_TEST_REPO"))
	chat.set_runtime_field("workflow_python",OS.get_environment("DAQIAN_TEST_PYTHON"))
	var ai = chat
	var backend = ai.find_child("AIBackend", true, false)
	var backend_id := 1 if mode == "acp" else 2
	backend.select(backend_id)
	backend.item_selected.emit(backend_id)
	var env_ui = chat.get_environment_settings_control()
	for name in (["CLINode"] if mode == "acp" else ["CLINode","CodexEntry"]):
		var field = env_ui.find_child(name,true,false)
		field.text = OS.get_environment("BATCH_NODE")
		field.text_changed.emit(field.text)
	if mode == "acp":
		for field_name in ["CLIBridge", "CLIEntry"]:
			var widget = env_ui.find_child(field_name, true, false)
			widget.text = OS.get_environment(field_name)
			widget.text_changed.emit(widget.text)
		ai.find_child("CLIModel", true, false).text = "mock-model"
	else:
		ai.find_child("CodexModel", true,false).text = "fixture"
	ai.find_child("AllowTools",true,false).button_pressed = true
	var wb = root.find_child("DaqianWorkspace",true,false)
	await wb.refresh()
	var row: Dictionary = wb.board.issues[0]
	var err: String = wb._bind_conversation(row)
	if not err.is_empty():
		push_error(err)
		quit(1)
		return
	wb._mount_conversation(row)
	layout = wb.conversation_host.find_child("ChatLayout",true,false)
	chat.daqian_work_event.connect(on_event)
	err = chat.open_daqian_chat(row.url, int(row.number),row.request,("case:host_read_batch" if mode == "acp" else "READ_BATCH_ORIGINAL"),false,{"backend":backend_id,"id":"mock-model" if mode == "acp" else "fixture"},true)
	if not err.is_empty():
		push_error(err)
		quit(2)
		return
	var deadline := Time.get_ticks_msec()+45000
	while Time.get_ticks_msec()<deadline:
		await create_timer(0.05).timeout
		if armed and layout.find_child("Stop",true,false).disabled:
			break
	await create_timer(1).timeout
	var detail := ""
	for label in layout.find_children("*","RichTextLabel",true,false):
		detail += label.get_parsed_text()
	print("BATCH_REPORT ", JSON.stringify({"native_calls":native_calls,"acp_complete":detail.contains("ACP_BATCH_COMPLETE"),"armed":armed,"changed":changed,"idle":layout.find_child("Stop",true,false).disabled,"events":observed,"receipt_error":detail.contains("batch_receipt_test_failure"),"corrected":detail.contains("CORRECTION_ACCEPTED")}))
	if not armed or (mode == "steer" and not detail.contains("CORRECTION_ACCEPTED")):
		print("BATCH_DIAGNOSTIC ", detail.right(2400))
	quit(0)
