@tool
extends SceneTree

var dock: Node
var control: AIChatEditorControl
var failures := PackedStringArray()
var before_approval := Callable()


func check(condition: bool, message: String) -> void:
	if not condition:
		failures.push_back(message)
		push_error(message)


func act(args: Dictionary, approve := true) -> Dictionary:
	if FileAccess.file_exists("res://last-result.json"):
		DirAccess.remove_absolute("res://last-result.json")
	dock.find_child("ChatInput", true, false).text = JSON.stringify(args)
	dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 20000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		var dialog = root.find_child("AIFileApproval", true, false)
		if dialog and dialog.visible:
			if control.describe_target("project_settings").get("visible", false):
				check(dialog.get_parent() is Window, "Setting approval did not nest in the active modal")
			if before_approval.is_valid():
				before_approval.call()
				before_approval = Callable()
			dialog.hide()
			if approve:
				dialog.confirmed.emit()
			else:
				dialog.canceled.emit()
		await process_frame
	check(dock.find_child("Stop", true, false).disabled, "Guidance tool timed out: %s" % args)
	if not FileAccess.file_exists("res://last-result.json"):
		check(false, "Missing host result: %s" % args)
		return { "ok": false }
	var text := FileAccess.get_file_as_string("res://last-result.json")
	var json := JSON.new()
	if json.parse(text) != OK:
		return { "ok": false, "error": text }
	var result: Variant = json.data
	return result if result is Dictionary else { "ok": false, "error": text }


func _initialize() -> void:
	run_checks.call_deferred()


func run_checks() -> void:
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	control = AIChatEditorControl.get_singleton()
	if dock == null or control == null:
		push_error("AI Chat/semantic control unavailable")
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
	dock.find_child("APIModel", true, false).text = "mock-guidance"
	dock.find_child("APIKey", true, false).text = "mock-key"
	dock.find_child("AllowTools", true, false).button_pressed = true
	dock.find_child("AutoExecuteCommands", true, false).button_pressed = false
	if not OS.get_environment("SEMANTIC_CODEX_ENTRY").is_empty():
		backend.select(2)
		backend.item_selected.emit(2)
		dock.find_child("CLINode", true, false).text = OS.get_environment("GONGGONG_NODE")
		dock.find_child("CodexEntry", true, false).text = OS.get_environment("SEMANTIC_CODEX_ENTRY")
		dock.find_child("CodexModel", true, false).text = "mock-guidance"

	var searched := await act({ "action": "find_targets", "query": "project settings", "limit": 5 })
	check(searched.get("targets", []).any(func(item): return item.get("id") == "project_settings"), "Target search did not find Project Settings")
	var missing := await act({ "action": "describe_target", "target": "missing.target" })
	check(not missing.get("ok", true) and missing.get("candidates", []).size() <= 5, "Unknown target candidates were not bounded")
	var invalid := await act({ "action": "start_guidance", "steps": [{ "target": "project_settings", "prepare": { "action": "set_project_setting", "target": "display/window/size/viewport_width", "value": 999 } }] })
	check(not invalid.get("ok", true), "Writing preparation action bypassed confirmation")
	var button := Button.new()
	button.text = "Continue"
	root.add_child(button)
	check(control.register_target("plugin.test.continue", button, "Continue", "test"), "Plugin target registration failed")
	check(not control.register_target("scene_tree", button, "Override"), "Plugin overwrote a core target")
	check(control.describe_target("plugin.test.continue").get("available", false), "Plugin target not discoverable")
	var steps := [{ "target": "plugin.test.continue", "message": "Click Continue", "observe": { "type": "control_pressed" } }]
	var preview := await act({ "action": "start_guidance", "steps": steps })
	check(preview.get("status") == "preview", "Workflow did not start as a preview")
	await act({ "action": "guidance_start" })
	button.pressed.emit()
	check(control.guidance_status().get("status") == "completed", "Button observer did not complete")
	await act({ "action": "main_screen", "target": "2D" })
	await act({ "action": "start_guidance", "steps": [{ "target": "main_screen_tabs", "observe": { "type": "main_screen", "value": "3D" } }] })
	await act({ "action": "guidance_start" })
	await create_timer(0.2).timeout
	check(control.guidance_status().get("status") == "waiting_user", "Main-screen observer completed without a change")
	EditorInterface.set_main_screen_editor("3D")
	await create_timer(0.2).timeout
	check(control.guidance_status().get("status") == "completed", "Main-screen observer missed the change")
	await act({ "action": "open_scene", "target": "res://fixture.tscn" })
	await act({ "action": "start_guidance", "steps": [{ "target": "scene_tree", "observe": { "type": "selected_node", "path": "Child" } }] })
	await act({ "action": "guidance_start" })
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(EditorInterface.get_edited_scene_root().get_node("Child"))
	await create_timer(0.2).timeout
	check(control.guidance_status().get("status") == "completed", "Node-selection observer missed the change")

	const setting := "display/window/size/viewport_width"
	var original: int = ProjectSettings.get_setting(setting)
	var changed := original + 17
	steps = [
		{ "target": "project_settings", "message": "Open Project Settings", "prepare": { "action": "project_settings", "target": "display/window" }, "observe": { "type": "target_visible" } },
		{ "target": "project_settings", "message": "Locate Display/Window", "observe": { "type": "manual" } },
		{ "target": "project_settings", "message": "Change viewport width", "execute": { "action": "set_project_setting", "target": setting, "value": changed }, "observe": { "type": "project_setting", "setting": setting, "value": changed } },
	]
	await act({ "action": "start_guidance", "title": "Configure window", "steps": steps })
	await act({ "action": "guidance_start" })
	check(control.guidance_status().get("current_step") == 1, "Visible-target observer did not advance")
	await act({ "action": "guidance_previous" })
	check(control.guidance_status().get("current_step") == 0, "Previous failed")
	await act({ "action": "guidance_next" })
	await act({ "action": "guidance_next" })
	await create_timer(0.3).timeout
	check(control.guidance_status().get("status") == "waiting_user" and control.guidance_status().get("current_step") == 2, "Unchanged setting completed a step")
	await act({ "action": "guidance_execute" }, false)
	check(ProjectSettings.get_setting(setting) == original, "Rejected guidance write changed the setting")
	await act({ "action": "guidance_execute" })
	await create_timer(0.2).timeout
	check(control.guidance_status().get("status") == "completed" and ProjectSettings.get_setting(setting) == changed, "Confirmed write or setting observer failed")
	ProjectSettings.set_setting(setting, original)
	ProjectSettings.save()

	# An observer advancing while approval is open must invalidate that approval.
	steps = [
		{ "target": "plugin.test.continue", "execute": { "action": "set_project_setting", "target": setting, "value": changed }, "observe": { "type": "control_pressed" } },
		{ "target": "plugin.test.continue", "execute": { "action": "set_project_setting", "target": setting, "value": changed + 1 } },
	]
	await act({ "action": "start_guidance", "steps": steps })
	await act({ "action": "guidance_start" })
	before_approval = func(): button.pressed.emit()
	var stale := await act({ "action": "guidance_execute" })
	check(stale.get("error") == "guidance_changed_since_confirmation" and ProjectSettings.get_setting(setting) == original, "Stale approval executed a different guidance step")
	await act({ "action": "guidance_cancel" })

	await act({ "action": "start_guidance", "steps": [{ "target": "plugin.test.continue", "message": "Relocate", "observe": { "type": "manual" } }] })
	await act({ "action": "guidance_start" })
	button.hide()
	await create_timer(0.25).timeout
	check(control.guidance_status().get("status") == "waiting_user", "Hidden target failed before retry window")
	button.show()
	await act({ "action": "guidance_relocate" })
	check(control.guidance_status().get("highlight_visible", false), "Returned target did not relocate")
	var panel := Control.new()
	root.add_child(panel)
	panel.position = Vector2(47, 83)
	button.reparent(panel)
	button.size = Vector2(240, 80)
	await create_timer(0.2).timeout
	check(control.get_global_rect().is_equal_approx(button.get_global_rect()), "Overlay missed target reparent or resize")
	var window := Window.new()
	root.add_child(window)
	window.size = Vector2i(500, 300)
	window.show()
	button.reparent(window)
	await create_timer(0.2).timeout
	check(control.get_window() == window and control.get_global_rect().is_equal_approx(button.get_global_rect()), "Overlay did not follow target into another window")
	button.queue_free()
	await process_frame
	button = Button.new()
	button.text = "Recreated"
	root.add_child(button)
	check(control.register_target("plugin.test.continue", button, "Recreated"), "Released target could not be registered again")
	await act({ "action": "guidance_relocate" })
	check(control.guidance_status().get("highlight_visible", false) and control.get_window() == root, "Overlay did not recover a recreated target")
	window.queue_free()
	panel.queue_free()
	button.hide()
	await create_timer(5.3).timeout
	check(control.guidance_status().get("status") == "failed" and control.guidance_status().has("recovery"), "Lost target did not fail with recovery instructions")
	button.show()
	await act({ "action": "guidance_relocate" })
	check(control.guidance_status().get("status") == "waiting_user", "Failed workflow could not be relocated")
	await act({ "action": "guidance_cancel" })
	check(control.guidance_status().get("status") == "cancelled" and not control.is_processing(), "Cancel left polling or overlay")
	await act({ "action": "start_guidance", "steps": [{ "target": "plugin.test.continue", "observe": { "type": "control_pressed" } }] })
	await act({ "action": "guidance_start" })
	await act({ "action": "guidance_cancel" })
	button.pressed.emit()
	check(control.guidance_status().get("status") == "cancelled", "Cancel left button signal attached")
	check(control.unregister_target("plugin.test.continue"), "Unregister failed")
	check(not control.describe_target("plugin.test.continue").get("ok", true), "Unregistered target remained")
	control.register_target("plugin.test.released", button, "Released")
	button.queue_free()
	await process_frame
	check(not control.describe_target("plugin.test.released").get("available", true), "Freed Control remained available")
	control.unregister_target("plugin.test.released")

	# A new editor process must recover an inert preview with no replay.
	await act({ "action": "start_guidance", "title": "Restore", "steps": [{ "target": "project_settings", "prepare": { "action": "project_settings", "target": "display/window" } }] })
	await act({ "action": "guidance_start" })
	check(FileAccess.file_exists("res://.godot/editor/ai_chat_guidance.json"), "Workflow persistence was not written")
	if failures.is_empty():
		print("AI_CHAT_SEMANTIC_OK")
		quit(0)
	else:
		print("GUIDANCE_FAILURES: ", failures)
		quit(1)
