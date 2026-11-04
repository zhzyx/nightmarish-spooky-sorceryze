@tool
extends SceneTree

var dock: Node
var tabs: TabBar
var failures: Array[String] = []
var bounds: Array[Dictionary] = []

func _initialize():
	_run.call_deferred()

func _check(ok: bool, reason: String):
	if not ok:
		failures.append(reason)

func _settle():
	for i in range(12):
		await process_frame

func _title_bounds(control: TabBar, index: int, label: String):
	var local := control.get_tab_rect(index)
	var rect := Rect2(control.global_position + local.position, local.size)
	var visible := rect.intersection(Rect2(Vector2.ZERO, Vector2(root.size)))
	var parent: Node = control
	while parent is Control:
		if parent.clip_contents:
			visible = visible.intersection(parent.get_global_rect())
		parent = parent.get_parent()
	_check(control.is_visible_in_tree() and rect.size.x > 0 and rect.size.y > 0, label + " hidden/empty")
	_check(visible.size.x >= rect.size.x - 2 and visible.size.y >= rect.size.y - 2, label + " clipped")
	bounds.append({"label": label, "rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y], "visible": [visible.size.x, visible.size.y]})

func _check_title(expected: String):
	_check(tabs.get_tab_title(tabs.current_tab) == expected, "Conversation title differs: " + tabs.get_tab_title(tabs.current_tab))
	var children := dock.find_child("SubAgentTabs", true, false) as TabBar
	_check(children.get_tab_title(0) == "父 · " + expected, "Parent title did not preserve Unicode")
	_title_bounds(tabs, tabs.current_tab, expected)
	_title_bounds(children, 0, "Parent " + expected)

func _close(index: int):
	tabs.tab_close_pressed.emit(index)
	await _settle()
	var dialog := dock.find_child("AgentCloseConfirmation", true, false) as ConfirmationDialog
	if dialog.visible:
		dialog.hide()
		dialog.confirmed.emit()
		await _settle()

func _run():
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(2)
		return
	EditorInterface.set_main_screen_editor("AI Chat")
	root.min_size = Vector2i.ZERO
	root.size = Vector2i(640, 900)
	await _settle()
	_check(root.size == Vector2i(640, 900), "Physical viewport was not640x900")
	_check(is_equal_approx(EditorInterface.get_editor_scale(), 1.5), "Editor scale was not150%")
	tabs = dock.find_child("AgentTabs", true, false)
	var stage := OS.get_environment("AI_TITLE_STAGE")
	if stage == "seed":
		_check_title("会话 1")
		dock.find_child("AddAgent", true, false).pressed.emit()
		await _settle()
		_check(tabs.tab_count == 2, "New conversation not created")
		_check_title("会话 2")
		await _close(1)
		_check(tabs.tab_count == 1, "New conversation did not close")
		await _close(0)
		_check(tabs.tab_count == 1 and int(tabs.get_tab_metadata(0)) == 2, "Closing last conversation did not recreate one")
		_check_title("会话 3")
		var input := dock.find_child("ChatInput", true, false) as TextEdit
		input.text = "TITLE_PERSISTENCE_FIXTURE"
		input.text_changed.emit()
		var persisted := false
		var deadline := Time.get_ticks_msec() + 8000
		while Time.get_ticks_msec() < deadline:
			await create_timer(0.1).timeout
			if FileAccess.file_exists("res://.godot/editor/ai_chat_history.json"):
				var history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
				if history is Dictionary and history.get("agents", []).size() == 1:
					var agent = history.agents[0]
					persisted = agent.get("title") == "会话 3" and agent.get("draft") == "TITLE_PERSISTENCE_FIXTURE"
					if persisted:
						break
		_check(persisted, "Title/draft not persisted before restart")
	else:
		_check(tabs.tab_count == 1, "Restart restored wrong number of conversations")
		_check_title("会话 3")
		_check(dock.find_child("ChatInput", true, false).text == "TITLE_PERSISTENCE_FIXTURE", "Restart lost persisted draft")
	if OS.get_environment("AI_TITLE_SCREENSHOT") == "1":
		var rendered := root.get_texture().get_image()
		_check(rendered != null and not rendered.is_empty(), "Title screenshot unavailable")
		if rendered != null and not rendered.is_empty():
			_check(rendered.save_png(OS.get_environment("AI_TITLE_RESULT").get_basename() + ".png") == OK, "Cannot save title screenshot")
	var report := {"stage": stage, "failures": failures, "title": tabs.get_tab_title(tabs.current_tab), "window": [root.size.x, root.size.y], "scale": EditorInterface.get_editor_scale(), "bounds": bounds}
	FileAccess.open(OS.get_environment("AI_TITLE_RESULT"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("TITLE_PROBE ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
