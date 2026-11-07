@tool
extends SceneTree

var dock: Node
var approvals := 0
var stop_started := 0
var tracking_stop := false
var last_frame := 0
var max_frame_gap := 0

func _initialize():
	process_frame.connect(func():
		var now := Time.get_ticks_usec()
		if tracking_stop and last_frame > 0:
			max_frame_gap = maxi(max_frame_gap, now - last_frame)
		last_frame = now)
	_run.call_deferred()

func chat_text() -> String:
	var text := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text()
	return text

func manual_stop():
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup != null:
		setup.hide()
	EditorInterface.set_main_screen_editor("AI Chat")
	dock.find_child("ChatInput", true, false).text = "highlight_tabs"
	dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 30000
	while not FileAccess.file_exists("res://server-waiting") and Time.get_ticks_msec() < deadline:
		var dialog = root.find_child("AIFileApproval", true, false)
		if dialog and dialog.visible:
			dialog.hide()
			dialog.confirmed.emit()
		await process_frame
	if not FileAccess.file_exists("res://server-waiting"):
		push_error("Delayed highlighted response not reached")
		quit(1)
		return
	var stop = dock.find_child("Stop", true, false)
	var report := {"overlay_before": root.find_child("AIEditorHighlight", true, false) != null, "stop_was_enabled": not stop.disabled}
	stop.button_down.connect(func(): stop_started = Time.get_ticks_usec())
	tracking_stop = true
	if OS.get_environment("SEMANTIC_STOP_SIGNAL") == "1":
		await create_timer(0.25).timeout
		stop_started = Time.get_ticks_usec()
		stop.pressed.emit()
		report["stop_trigger"] = "pressed_signal_callback"
	else:
		print("SEMANTIC_READY_FOR_NATIVE_STOP")
		await stop.pressed
		report["stop_trigger"] = "native_button_down_to_pressed_return"
	report["stop_seconds"] = (Time.get_ticks_usec() - stop_started) / 1000000.0
	await process_frame
	await process_frame
	report["overlay_after"] = root.find_child("AIEditorHighlight", true, false) != null
	report["stop_disabled_after"] = stop.disabled
	report["server_released_at_stop"] = FileAccess.file_exists("res://server-released")
	dock.find_child("ChatInput", true, false).text = "recovery"
	dock.find_child("Send", true, false).pressed.emit()
	deadline = Time.get_ticks_msec() + 10000
	while not "RECOVERY_OK" in chat_text() and Time.get_ticks_msec() < deadline:
		await process_frame
	report["recovery_received"] = "RECOVERY_OK" in chat_text()
	report["server_released_at_recovery"] = FileAccess.file_exists("res://server-released")
	tracking_stop = false
	report["frame_gap_seconds"] = max_frame_gap / 1000000.0
	deadline = Time.get_ticks_msec() + 103000
	while not FileAccess.file_exists("res://server-response-finished") and Time.get_ticks_msec() < deadline:
		await process_frame
	await create_timer(0.3).timeout
	report["observed_server_release"] = FileAccess.file_exists("res://server-released")
	report["late_response_outcome"] = FileAccess.get_file_as_string("res://server-response-finished") if FileAccess.file_exists("res://server-response-finished") else "timeout"
	report["stale_response_absent"] = not "Checked highlight_tabs" in chat_text()
	FileAccess.open("res://stop-report.json", FileAccess.WRITE).store_string(JSON.stringify(report))
	print("AI_CHAT_SEMANTIC_OK")
	quit(0)

func phase(name: String, reject := false) -> bool:
	dock.find_child("ChatInput", true, false).text = name
	dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 30000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		var dialog = root.find_child("AIFileApproval", true, false)
		if dialog and dialog.visible:
			dialog.hide()
			if reject:
				dialog.canceled.emit()
			else:
				approvals += 1
				dialog.confirmed.emit()
		await process_frame
	if not dock.find_child("Stop", true, false).disabled:
		push_error("Semantic phase timed out: " + name)
		return false
	return true

func _run():
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("GONGGONG_TEST_WORKSPACE"))
	settings.set_setting("gonggong/python", OS.get_environment("GONGGONG_PYTHON"))
	settings.set_setting("gonggong/issue_number", "6")
	settings.set_setting("gonggong/request_id", "isolated-gate")
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	dock.get_ai_settings_control().find_child("APIModel", true, false).text = "mock-semantic"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "mock-key"
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	if OS.get_environment("SEMANTIC_MANUAL_STOP") == "1":
		await manual_stop()
		return
	if not OS.get_environment("SEMANTIC_CODEX_ENTRY").is_empty():
		backend.select(2)
		backend.item_selected.emit(2)
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("GONGGONG_NODE")
		dock.get_environment_settings_control().find_child("CodexEntry", true, false).text = OS.get_environment("SEMANTIC_CODEX_ENTRY")
		dock.get_ai_settings_control().find_child("CodexModel", true, false).text = "mock-semantic"
	if OS.get_environment("SEMANTIC_BOUNDS") == "1":
		if not await phase("state_empty") or not await phase("open_scene"):
			quit(1)
			return
		var scene = EditorInterface.get_edited_scene_root()
		if scene == null:
			for label in dock.find_children("*", "RichTextLabel", true, false):
				print(label.get_parsed_text())
			push_error("Fixture scene did not open")
			quit(1)
			return
		var child = scene.get_node("Child")
		var selection = EditorInterface.get_selection()
		selection.clear()
		selection.add_node(child)
		for pair in [["state_long_ascii", "a"], ["state_long_cjk", "界"], ["state_long_unicode", "😀"]]:
			child.name = pair[1].repeat(20000)
			if not await phase(pair[0]):
				quit(1)
				return
		child.name = "Child"
		selection.clear()
		var nodes: Array[Node] = []
		for i in range(105):
			var node = Node.new()
			node.name = "Node" + str(i)
			scene.add_child(node)
			node.owner = scene
			nodes.append(node)
		# Let the scene tree rebuild before establishing the intended selection.
		await create_timer(0.2).timeout
		selection.clear()
		for node in nodes:
			selection.add_node(node)
		if selection.get_selected_nodes().size() != 105:
			quit(1)
			return
		if not await phase("state_count"):
			quit(1)
			return
		for i in range(nodes.size()):
			nodes[i].name = "界".repeat(1000) + str(i)
		await create_timer(0.2).timeout
		selection.clear()
		for node in nodes:
			selection.add_node(node)
		if not await phase("state_budget"):
			quit(1)
			return
		for pair in [["test", "state_case_a"], ["null", "state_case_b"], ["true", "state_case_c"]]:
			var key: String = pair[0]
			selection.clear()
			for i in range(14):
				nodes[i].name = key.repeat(240) + str(i)
			await create_timer(0.2).timeout
			for i in range(14):
				selection.add_node(nodes[i])
			dock.get_ai_settings_control().find_child("APIKey", true, false).text = key
			if not await phase(pair[1]):
				quit(1)
				return
		print("AI_CHAT_SEMANTIC_OK")
		quit(0)
		return
	if OS.get_environment("SEMANTIC_INTERFACES") == "1":
		for name in ["open_scene", "open_script", "select_node", "interface_2d", "highlight_inspector", "highlight_filesystem", "highlight_tabs", "project_settings", "highlight_project", "editor_settings", "highlight_editor"]:
			if not await phase(name):
				quit(1)
				return
			if name == "open_script":
				var code = EditorInterface.get_script_editor().get_current_editor().get_base_editor()
				if code.get_caret_line() != 2 or code.get_caret_column() != 0:
					push_error("Incorrect script line/column")
					quit(1)
					return
			if name == "select_node" and EditorInterface.get_selection().get_selected_nodes()[0].name != "Child":
				quit(1)
				return
			if name == "highlight_tabs":
				var overlay = root.find_child("AIEditorHighlight", true, false)
				if overlay == null:
					quit(1)
					return
				root.size += Vector2i(80, 60)
				await process_frame
				await process_frame
				if not overlay.visible or overlay.size.x <= 0:
					quit(1)
					return
				dock.find_child("Stop", true, false).pressed.emit()
				if root.find_child("AIEditorHighlight", true, false) != null:
					push_error("Stop left a highlight")
					quit(1)
					return
			if name == "highlight_project" or name == "highlight_editor":
				var overlay = root.find_child("AIEditorHighlight", true, false)
				if overlay == null or overlay.mouse_filter != Control.MOUSE_FILTER_IGNORE or not overlay.visible:
					quit(1)
					return
				for window in root.find_children("*", "Window", true, false):
					window.hide()
				await process_frame
		print("AI_CHAT_SEMANTIC_OK")
		quit(0)
		return
	for name in ["state", "write", "reject", "invalid", "save_failure", "clear", "switch_2d", "highlight_scene", "clear_highlight"]:
		var old_order = ProjectSettings.get_order("display/window/size/viewport_width") if name == "save_failure" else 0
		if name == "save_failure":
			FileAccess.set_read_only_attribute("res://project.godot", true)
		if not await phase(name, name == "reject"):
			quit(1)
			return
		if name == "save_failure":
			FileAccess.set_read_only_attribute("res://project.godot", false)
			if ProjectSettings.get_setting("display/window/size/viewport_width") != 777 or ProjectSettings.get_order("display/window/size/viewport_width") != old_order:
				for label in dock.find_children("*", "RichTextLabel", true, false):
					print(label.get_parsed_text())
				push_error("Failed clear changed memory: " + str(ProjectSettings.get_setting("display/window/size/viewport_width")))
				quit(1)
				return
		if name == "highlight_scene":
			var overlay = root.find_child("AIEditorHighlight", true, false)
			if overlay == null or overlay.mouse_filter != Control.MOUSE_FILTER_IGNORE:
				push_error("Missing mouse-through highlight")
				quit(1)
				return
		if name == "clear_highlight" and root.find_child("AIEditorHighlight", true, false) != null:
			push_error("Highlight remained after clear")
			quit(1)
			return
	if approvals != 3:
		for label in dock.find_children("*", "RichTextLabel", true, false):
			print(label.get_parsed_text())
		push_error("Unexpected setting approvals: " + str(approvals))
		quit(1)
		return
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	if not await phase("consultation"):
		quit(1)
		return
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
	if not await phase("permission_off"):
		quit(1)
		return
	var denied := false
	for label in dock.find_children("*", "RichTextLabel", true, false):
		var text: String = label.get_parsed_text()
		if "permission" in text.to_lower() or "权限" in text or "禁用" in text:
			denied = true
	if not denied:
		push_error("Missing disabled-permission notice")
		quit(1)
		return
	print("PERMISSION_OFF_REJECTED")
	print("AI_CHAT_SEMANTIC_OK")
	quit(0)
