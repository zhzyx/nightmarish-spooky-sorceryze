@tool
extends SceneTree

var dock: Node
var last_command := 0

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func chat_text() -> String:
	var text := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text() + "\n"
	return text

func send_text(text: String) -> void:
	dock.find_child("ChatInput", true, false).text = text
	dock.find_child("Send", true, false).pressed.emit()

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("DESIGN_BATCH_ROOT"))
	settings.set_setting("gonggong/python", OS.get_environment("DESIGN_BATCH_PYTHON"))
	settings.set_setting("gonggong/issue_number", "999")
	settings.set_setting("gonggong/request_id", "external-global-sentinel")
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	for field in ["workflow_python", "build_python"]:
		assert(dock.set_runtime_field(field, OS.get_environment("DESIGN_BATCH_PYTHON")).is_empty())
	for field in ["node", "codex"]:
		assert(dock.set_runtime_field(field, OS.get_environment("DESIGN_BATCH_NODE")).is_empty())
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup:
		setup.hide()
	var ai = dock.get_ai_settings_control()
	ai.find_child("APIEndpoint", true, false).text = OS.get_environment("DESIGN_BATCH_ENDPOINT")
	ai.find_child("APIModel", true, false).text = "external-chat-fixture"
	ai.find_child("APIKey", true, false).text = "isolated-external-fixture"
	ai.find_child("AllowTools", true, false).button_pressed = true
	ai.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	ai.find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for unused in 300:
		if dock.find_child("Stop", true, false).disabled and not dock.find_child("Send", true, false).disabled:
			break
		await create_timer(0.03).timeout
	if OS.get_environment("EXTERNAL_CHAT_PHASE") != "restore":
		send_text("DESIGN_BATCH_WARMUP")
		for unused in 1500:
			if "EXTERNAL_WARMUP_OK" in chat_text() and dock.find_child("Stop", true, false).disabled:
				break
			await create_timer(0.03).timeout
		assert("EXTERNAL_WARMUP_OK" in chat_text())
	write_json("res://external-ready.json", {"pid": OS.get_process_id()})
	while true:
		if FileAccess.file_exists("res://external-command.json"):
			var command = JSON.parse_string(FileAccess.get_file_as_string("res://external-command.json"))
			if command is Dictionary and command.get("id", 0) > last_command:
				last_command = command.id
				var name: String = command.name
				if name == "draft":
					dock.find_child("ChatInput", true, false).text = command.get("value", "")
				elif name == "tools":
					ai.find_child("AllowTools", true, false).button_pressed = command.value
				elif name == "automatic":
					ai.find_child("AutoExecuteCommands", true, false).button_pressed = command.value
				elif name == "consultation":
					dock.find_child("ConsultationOnly", true, false).button_pressed = command.value
				elif name == "queue":
					send_text("FIXTURE_QUEUED_MESSAGE")
				elif name == "new_parent":
					dock.find_child("AddAgent", true, false).pressed.emit()
				elif name == "first_parent":
					dock.find_child("AgentTabs", true, false).current_tab = 0
				elif name == "child":
					dock.find_child("AddSubAgent", true, false).pressed.emit()
				elif name == "parent":
					dock.find_child("SubAgentTabs", true, false).tab_selected.emit(0)
				elif name == "peer_child":
					var arguments := PackedStringArray([OS.get_environment("EXTERNAL_CHAT_PEER_PROBE"), ProjectSettings.globalize_path("res://"), str(OS.get_process_id()), ProjectSettings.globalize_path("res://peer-child.json")])
					OS.create_process("/usr/bin/python3", arguments)
				elif name == "close_prompt":
					var tabs = dock.find_child("AgentTabs", true, false)
					tabs.tab_close_pressed.emit(tabs.current_tab)
				elif name == "close_cancel":
					dock.find_child("AgentCloseConfirmation", true, false).get_cancel_button().pressed.emit()
				elif name == "exit":
					write_json("res://external-ack-%d.json" % last_command, {"ok": true})
					quit()
					return
				write_json("res://external-ack-%d.json" % last_command, {"ok": true, "draft": dock.find_child("ChatInput", true, false).text, "text": chat_text(), "busy": not dock.find_child("Stop", true, false).disabled, "send_enabled": not dock.find_child("Send", true, false).disabled})
		await create_timer(0.03).timeout
