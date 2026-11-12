@tool
extends SceneTree

var dock: Node
var failed := false

func _catalog_ready(dock) -> bool:
	var snapshot: Dictionary = dock.get_model_catalog_snapshot()
	return snapshot.get("state", "") == "ready" and snapshot.get("catalog_current", false) and not snapshot.get("loading", true)

func require(value: bool, reason: String):
	if not value:
		failed = true
		push_error(reason)

func _initialize():
	_run.call_deferred()

func phase(label: String):
	dock.find_child("ChatInput", true, false).text = label
	dock.find_child("Send", true, false).pressed.emit()
	await process_frame
	var deadline := Time.get_ticks_msec() + 15000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		await process_frame
	require(dock.find_child("Stop", true, false).disabled, "Chat phase timed out: " + label)

func tree_has(item: TreeItem, text: String) -> bool:
	if item == null:
		return false
	if text in item.get_text(0) or text in item.get_text(1):
		return true
	for child in item.get_children():
		if tree_has(child, text):
			return true
	return false

func _run():
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	require(dock != null, "AI dock missing")
	if failed:
		quit(1)
		return
	var controls = dock.get_ai_settings_control()
	var backend = controls.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	controls.find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	controls.find_child("APIModel", true, false).text = "runtime-diagnostics-fixture"
	controls.find_child("APIKey", true, false).text = OS.get_environment("GODOT_AI_API_KEY")
	controls.find_child("AllowTools", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	var key = controls.find_child("APIKey", true, false)
	key.text_changed.emit(key.text)
	var deadline := Time.get_ticks_msec() + 15000
	var model_status = controls.find_child("ModelStatus", true, false)
	while (backend.disabled or not _catalog_ready(dock)) and Time.get_ticks_msec() < deadline:
		await process_frame
	require(not backend.disabled and _catalog_ready(dock), "Local model discovery did not complete")
	await phase("empty")
	EditorInterface.play_main_scene()
	await create_timer(2).timeout
	var observed := false
	for tree in root.find_children("*", "Tree", true, false):
		if tree.columns >= 2 and tree_has(tree.get_root(), "RUNTIME_DIAGNOSTIC_ERROR"):
			observed = true
	require(observed, "Real debugger error tree did not receive game error")
	print("RUNTIME_DEBUGGER_ERROR_OBSERVED=", observed)
	await phase("bad")
	EditorInterface.stop_playing_scene()
	await create_timer(0.5).timeout
	await phase("stopped")
	if OS.get_environment("RUNTIME_DIAGNOSTICS_EXTENDED") == "1":
		var cleared := 0
		for tree in root.find_children("*", "Tree", true, false):
			if tree.columns >= 2 and tree_has(tree.get_root(), "RUNTIME_DIAGNOSTIC_ERROR"):
				for button in tree.get_parent().find_children("*", "Button", true, false):
					if button.text == "Clear":
						button.pressed.emit()
						cleared += 1
		require(cleared == int(OS.get_environment("RUNTIME_DIAGNOSTICS_INSTANCES")), "Did not clear each actual debugger error tree")
		await phase("cleared")
	# Change the controlled input, then prove the next real debugger session is fresh.
	var file := FileAccess.open("res://game.gd", FileAccess.WRITE)
	file.store_string('extends Node\nfunc _ready():\n\tprint("RUNTIME_REPAIRED_OUTPUT")\n')
	file.close()
	EditorInterface.get_resource_filesystem().scan()
	await create_timer(0.5).timeout
	EditorInterface.play_main_scene()
	await create_timer(2).timeout
	await phase("fixed")
	if OS.get_environment("RUNTIME_DIAGNOSTICS_EXTENDED") == "1":
		EditorInterface.stop_playing_scene()
		await create_timer(0.5).timeout
		EditorInterface.play_custom_scene("res://flood.tscn")
		await create_timer(3).timeout
		await phase("bounded")
	controls.find_child("AllowTools", true, false).button_pressed = false
	await phase("permission_off")
	var chat := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		chat += label.get_parsed_text()
	FileAccess.open("res://chat.txt", FileAccess.WRITE).store_string(chat)
	EditorInterface.stop_playing_scene()
	await create_timer(0.5).timeout
	print("RUNTIME_DIAGNOSTICS_DRIVER_OK=", not failed)
	quit(1 if failed else 0)
