extends SceneTree

const LEAVES := ["Right/SharedLeaf", "Left/SharedLeaf", "Other/SharedLeaf"]

func _initialize():
	_run.call_deferred()

func _check(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition

func _invoke_workbench() -> bool:
	var palette := EditorInterface.get_command_palette()
	var shortcut := EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	for menu: PopupMenu in root.find_children("*", "PopupMenu", true, false):
		for index in menu.item_count:
			if menu.get_item_shortcut(index) == shortcut:
				menu.id_pressed.emit(menu.get_item_id(index))
				break
		if palette.visible: break
	if not _check(palette.visible, "Editor menu did not open the command palette"): return false
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false).front()
	var results: Tree = palette.find_children("*", "Tree", true, false).front()
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not _check(results.get_selected() != null and results.get_selected().get_metadata(0) == search.text, "Missing workbench command"): return false
	results.item_activated.emit()
	await process_frame
	return true

func _run():
	root.size = Vector2i(1440, 900)
	await create_timer(1.0).timeout
	var chat = root.find_child("AI Chat", true, false)
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	if OS.get_environment("SCENE_SELECTION_RESTORE") == "1":
		var host: Node = sidebar if sidebar.is_visible_in_tree() else chat
		var restored: Button = host.find_child("WorkbenchReference", true, false)
		var input: TextEdit = host.find_child("ChatInput", true, false)
		if not _check(is_instance_valid(restored) and is_instance_valid(input) and restored.visible and "失效" in restored.text and input.text == "retain stale draft", "Lost restored multiselection draft"): return
		for path in LEAVES:
			if not _check(path in restored.text, "Missing restored selection member"): return
		print("SCENE_SELECTION_RESTORED")
		quit(0)
		return
	var backend: OptionButton = chat.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	var config: Control = chat.get_ai_settings_control()
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("TIANSHU_REFERENCE_ENDPOINT")
	var key: LineEdit = config.find_child("APIKey", true, false)
	key.text = "loopback-only"
	key.text_changed.emit(key.text)
	chat.find_child("APIModel", true, false).text = "fixture"

	for screen in ["2D", "3D"]:
		var scene := "res://selection-%s.tscn" % screen
		EditorInterface.open_scene_from_path(scene)
		EditorInterface.set_main_screen_editor(screen)
		await create_timer(0.3).timeout
		var scene_root := EditorInterface.get_edited_scene_root()
		var selection := EditorInterface.get_selection()
		for count in [1, 3]:
			selection.clear()
			var expected := []
			for path in LEAVES.slice(0, count):
				selection.add_node(scene_root.get_node(path))
				expected.append({"kind":"editor", "object_id":scene + "#" + path, "revision":FileAccess.get_sha256(scene)})
			if not await _invoke_workbench(): return
			var label: Button = sidebar.find_child("WorkbenchReference", true, false)
			var input: TextEdit = sidebar.find_child("ChatInput", true, false)
			var send: Button = sidebar.find_child("Send", true, false)
			var draft := "%s selection %d" % [screen, count]
			input.text = draft
			if not _check(label.is_visible_in_tree(), "Missing draft reference " + draft): return
			for ref in expected:
				if not _check(ref.object_id in label.text and ref.revision in label.tooltip_text, "Missing path or revision in " + label.text): return
			print("SELECTION_DRAFT ", JSON.stringify({"draft": draft, "label": label.text, "references": expected}))
			selection.clear()
			selection.add_node(scene_root)
			send.pressed.emit()
			var persisted := false
			var deadline := Time.get_ticks_msec() + 15000
			while not persisted and Time.get_ticks_msec() < deadline:
				await create_timer(0.1).timeout
				var history_file := "res://.godot/editor/ai_chat_history.json"
				if not FileAccess.file_exists(history_file): continue
				var history = JSON.parse_string(FileAccess.get_file_as_string(history_file))
				if not history is Dictionary: continue
				for agent in history.agents:
					for message in agent.transcript:
						if message.get("editor_references") == expected:
							persisted = true
			if not _check(persisted and not label.visible and input.text.is_empty(), "Selection did not reach history " + draft): return
			sidebar.find_child("CloseWorkbench", true, false).pressed.emit()
			await create_timer(0.15).timeout
	# Invalidating a non-primary member must block the entire selection.
	var selection := EditorInterface.get_selection()
	var scene_root := EditorInterface.get_edited_scene_root()
	selection.clear()
	for path in LEAVES: selection.add_node(scene_root.get_node(path))
	if not await _invoke_workbench(): return
	var label: Button = sidebar.find_child("WorkbenchReference", true, false)
	var composer: TextEdit = sidebar.find_child("ChatInput", true, false)
	scene_root.get_node(LEAVES.back()).name = "Moved"
	composer.text = "retain stale draft"
	sidebar.find_child("Send", true, false).pressed.emit()
	if not _check(label.visible and "失效" in label.text and composer.text == "retain stale draft", "Stale group sent"): return
	label.pressed.emit()
	if not _check(not label.visible and composer.text == "retain stale draft", "Removing selection lost draft"): return
	scene_root.get_node("Other/Moved").name = "SharedLeaf"
	if not await _invoke_workbench(): return
	if not _check(label.visible and not "失效" in label.text, "Could not capture replacement selection"): return
	await create_timer(1.2).timeout
	print("SCENE_SELECTION_OK")
	quit(0)
