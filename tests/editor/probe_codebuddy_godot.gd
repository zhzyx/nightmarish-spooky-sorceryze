@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _run():
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not dock:
		push_error("CODEBUDDY_GODOT_FAILED: native dock missing")
		quit(1)
		return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(1)
	backend.item_selected.emit(1)
	dock.find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
	dock.find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
	dock.find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
	dock.find_child("CLIModel", true, false).text = "gpt-6.1-sol"
	var probe_tools = OS.get_environment("AI_CHAT_PROBE_TOOLS") == "1"
	dock.find_child("AllowTools", true, false).button_pressed = probe_tools
	var chat_input = dock.find_child("ChatInput", true, false)
	if probe_tools:
		chat_input.text = "连接验证：请仅通过 read_file 读取 res://tool_fixture.txt，然后在最终回复中原样返回该文件内容。不要读其他文件，不要写文件，不要执行命令。"
	else:
		chat_input.text = "这是一条 Godot 原生聊天面板连接验证消息。请只回复 CODEBUDDY_GODOT_OK，不要读取文件或调用任何工具。"
	var send = dock.find_child("Send", true, false)
	send.pressed.emit()
	var reply = dock.find_child("AIReply", true, false)
	var deadline = Time.get_ticks_msec() + (260000 if probe_tools else 140000)
	var confirmation = dock.get_child(1)
	while send.disabled and Time.get_ticks_msec() < deadline:
		if confirmation.visible:
			confirmation.hide()
			confirmation.canceled.emit()
			push_error("CODEBUDDY_GODOT_FAILED: read-only probe requested a write or command")
			quit(1)
			return
		await process_frame
	var answer = reply.find_child("AIAnswer", true, false)
	var ai_reply = answer.get_parsed_text() if answer else ""
	var expected = OS.get_environment("AI_CHAT_PROBE_EXPECTED") if probe_tools else "CODEBUDDY_GODOT_OK"
	var tool_read = not probe_tools or "read_file" in reply.get_node("WorkProcess").get_parsed_text()
	var transport = dock.get_meta("cli_response_transport", {})
	var increment_verified = not probe_tools or transport.get("mode", "") == "incremental"
	if not send.disabled and not expected.is_empty() and expected in ai_reply and tool_read and increment_verified:
		print("CODEBUDDY_GODOT_OK: native dock received a real model reply; tools_verified=", probe_tools, "; transport=", transport)
		quit(0)
	else:
		push_error("CODEBUDDY_GODOT_FAILED: no verification reply reached the native dock")
		quit(1)
