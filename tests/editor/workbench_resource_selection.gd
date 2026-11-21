@tool
extends SceneTree

const NORTH := "res://north/SameGradient.tres"
const SOUTH := "res://south/SameGradient.tres"

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, label: String) -> bool:
	if not ok:
		push_error(label)
		quit(1)
	return ok

func run() -> void:
	root.size = Vector2i(1440, 900)
	await create_timer(0.8).timeout
	while EditorInterface.get_resource_filesystem().is_scanning():
		await process_frame
	EditorInterface.select_file(NORTH)
	var saved := load(SOUTH)
	EditorInterface.inspect_object(saved)
	await process_frame
	if not check(NORTH in EditorInterface.get_selected_paths() and EditorInterface.get_inspector().get_edited_object() == saved, "Distinct source selections"): return

	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var palette := EditorInterface.get_command_palette()
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false).front()
	var tree: Tree = palette.find_children("*", "Tree", true, false).front()
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not check(tree.get_selected().get_metadata(0) == search.text, "Open AI Workbench command"): return
	tree.item_activated.emit()
	await process_frame

	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	var input: TextEdit = sidebar.find_child("ChatInput", true, false)
	var send: Button = sidebar.find_child("Send", true, false)
	var label: Button = sidebar.find_child("WorkbenchReference", true, false)
	var menu: MenuButton = sidebar.find_child("WorkbenchResourceSelection", true, false)
	if not check(menu != null and menu.is_visible_in_tree(), "Resource source actions reachable in ordinary sidebar"): return
	var popup := menu.get_popup()
	input.text = "resource snapshot"
	popup.id_pressed.emit(1)
	popup.id_pressed.emit(0)
	popup.id_pressed.emit(1)
	if not check(label.visible and NORTH in label.text and SOUTH in label.text and label.text.count(NORTH) == 1 and input.text == "resource snapshot", "Same-name resources visible, duplicates omitted, draft preserved"): return
	var saved_label := label.text
	var temporary := Gradient.new()
	EditorInterface.inspect_object(temporary)
	await process_frame
	if not check(EditorInterface.get_inspector().get_edited_object() == temporary and temporary.resource_path.is_empty(), "Inspector observes unsaved instance"): return
	# The dock button again brings the same composer to the front after opening Inspector.
	sidebar.make_visible()
	popup.id_pressed.emit(0)
	if not check(label.visible and "临时资源" in label.text and ("Gradient/" + str(temporary.get_instance_id())) in label.text and not "失效" in label.text, "Temporary resource visibly bound by instance"): return
	var all_label := label.text
	var replacement := Gradient.new()
	EditorInterface.inspect_object(replacement)
	await process_frame
	sidebar.make_visible()
	if not check(label.text == all_label, "Changing inspector selection preserves captured draft"): return
	var dock = root.find_child("AI Chat", true, false)
	var config = dock.get_ai_settings_control()
	var backend: OptionButton = root.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("U09_ENDPOINT")
	var key: LineEdit = config.find_child("APIKey", true, false)
	key.text = "isolated-fixture"
	key.text_changed.emit(key.text)
	root.find_child("APIModel", true, false).text = "fixture"
	await create_timer(1.2).timeout
	if not check(not send.disabled and sidebar.find_child("ConsultationOnly", true, false).button_pressed, "Ready for consultation send"): return
	send.pressed.emit()
	var history_path := "res://.godot/editor/ai_chat_history.json"
	var references := []
	var deadline := Time.get_ticks_msec() + 20000
	while references.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
		if not FileAccess.file_exists(history_path): continue
		var history = JSON.parse_string(FileAccess.get_file_as_string(history_path))
		if not history is Dictionary: continue
		for agent in history.agents:
			for record in agent.transcript:
				if record.get("content", "").begins_with("resource snapshot"):
					references = record.get("editor_references", [])
	if not check(references.size() == 3 and not label.visible and input.text.is_empty(), "Frozen three-reference history"): return
	if not check(references[0] == {"kind":"editor","object_id":NORTH,"revision":FileAccess.get_sha256(NORTH)} and references[1] == {"kind":"editor","object_id":SOUTH,"revision":FileAccess.get_sha256(SOUTH)} and references[0].revision != references[1].revision, "Saved resource identities and SHA-256"): return
	if not check(references[2].object_id.ends_with("Gradient/" + str(temporary.get_instance_id())) and references[2].revision.length() == 64, "Frozen temporary identity"): return

	popup.id_pressed.emit(0)
	if not check(str(replacement.get_instance_id()) in label.text and not str(temporary.get_instance_id()) in label.text, "Second unsaved Gradient distinct"): return
	if not check(ResourceSaver.save(replacement, "res://saved-gradient.tres") == OK, "Save originally temporary Gradient"): return
	replacement.resource_path = "res://saved-gradient.tres"
	input.text = "temporary draft stays"
	send.pressed.emit()
	if not check("失效" in label.text and input.text == "temporary draft stays", "Saved instance cannot reuse its temporary identity"): return
	label.pressed.emit()
	popup.id_pressed.emit(1)
	if not check(NORTH in label.text, "Filesystem source persists independently"): return
	input.text = "stale draft stays"
	var file := FileAccess.open(NORTH, FileAccess.READ_WRITE)
	file.seek_end()
	file.store_line("; changed")
	file.close()
	send.pressed.emit()
	if not check("失效" in label.text and input.text == "stale draft stays", "Source revision change blocked at send"): return
	label.pressed.emit()
	if not check(not label.visible and input.text == "stale draft stays", "Removable stale reference"): return
	print("U09_RECEIPT ", JSON.stringify({"saved_label":saved_label, "draft_label":all_label, "history":references, "distinct_unsaved":str(replacement.get_instance_id()), "saved_temporary_blocked":true, "stale_send_blocked":true, "draft_after_removal":input.text}))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
