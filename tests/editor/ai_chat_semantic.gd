@tool
extends SceneTree

var dock: Node
var approvals := 0

func _initialize():
	_run.call_deferred()

func phase(name: String, reject := false) -> bool:
	dock.find_child("ChatInput", true, false).text = name
	dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 30000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		var dialog = dock.find_child("AIFileApproval", true, false)
		if dialog.visible:
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
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	dock.find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	dock.find_child("APIModel", true, false).text = "mock-semantic"
	dock.find_child("APIKey", true, false).text = "mock-key"
	dock.find_child("AllowTools", true, false).button_pressed = true
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
			dock.find_child("APIKey", true, false).text = key
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
	dock.find_child("AllowTools", true, false).button_pressed = false
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
