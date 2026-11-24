extends SceneTree

var dock: Node
var composer: TextEdit
var messages: Node
var results := []

func _initialize():
	_run.call_deferred()

func _check(ok: bool, detail: String) -> bool:
	if not ok:
		push_error(detail)
		quit(1)
	return ok

func _open(source: Window) -> AcceptDialog:
	var event := InputEventKey.new()
	event.keycode = KEY_P if source.exclusive else KEY_I
	event.shift_pressed = source.exclusive
	event.alt_pressed = not source.exclusive
	if OS.get_name() == "macOS":
		event.meta_pressed = true
	else:
		event.ctrl_pressed = true
	event.pressed = true
	source.push_input(event)
	await process_frame
	var dialog := source.get_node_or_null("AIWorkbenchWindow") as AcceptDialog
	if not _check(dialog != null and dialog.visible and source.visible and dialog.is_ancestor_of(composer) and dialog.is_ancestor_of(messages) and composer.has_focus(), "Original conversation did not open from " + source.title):
		return null
	return dialog

func _close(dialog: AcceptDialog):
	dialog.get_ok_button().pressed.emit()
	await process_frame
	await process_frame
	_check(not is_instance_valid(dialog), "Closed window was retained")

func _line_roundtrip(source: Window, line: LineEdit, sample: String, send: bool) -> bool:
	line.grab_focus()
	line.text = sample
	line.caret_column = 9
	line.select(2, 9)
	var expected := line.get_selected_text()
	var id := line.get_instance_id()
	var draft := composer.text
	var dialog := await _open(source)
	if dialog == null:
		return false
	var quote := dialog.find_child("InsertWindowReference", true, false) as Button
	if not _check(composer.text == draft and quote != null, "Lost composer draft or window reference"):
		return false
	quote.pressed.emit()
	if not _check(composer.text.begins_with(draft) and composer.text.ends_with(expected) and not sample in composer.text, "Selection reference differs from current selection"):
		return false
	if send:
		dialog.find_child("Send", true, false).pressed.emit()
		var reply := false
		var deadline := Time.get_ticks_msec() + 12000
		while not reply and Time.get_ticks_msec() < deadline:
			await process_frame
			for label in messages.find_children("*", "RichTextLabel", true, false):
				reply = reply or "WINDOW_REPLY_OK" in label.get_parsed_text()
		if not _check(reply, "Loopback answer did not reach shared conversation"):
			return false
	await _close(dialog)
	if not _check(dock.is_ancestor_of(composer) and source.visible and source.gui_get_focus_owner() == line and line.text == sample and line.caret_column == 9 and line.get_selected_text() == expected, "Lost window, focus, contents or selection while returning to " + source.title):
		return false
	results.append({"source": source.title, "source_id": id, "returned_focus_id": source.gui_get_focus_owner().get_instance_id(), "source_text": line.text, "quoted": expected, "caret": line.caret_column, "loopback_reply": send})
	return true

func _run():
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	var setup := dock.find_child("GongGongRuntimeSetup", true, false)
	if setup:
		setup.hide()
	EditorInterface.set_main_screen_editor("AI Chat")
	composer = dock.find_child("ChatInput", true, false)
	messages = dock.find_child("Messages", true, false)
	var settings: Control = dock.get_ai_settings_control()
	var backend := dock.find_child("AIBackend", true, false) as OptionButton
	backend.select(0)
	backend.item_selected.emit(0)
	settings.find_child("APIEndpoint", true, false).text = OS.get_environment("WINDOW_ENDPOINT")
	dock.find_child("APIModel", true, false).text = "fixture"
	dock.refresh_model_catalog()
	await create_timer(0.5).timeout
	composer.text = "Explain the selection."
	var tabs := dock.find_child("AgentTabs", true, false) as TabBar
	var menu := dock.find_child("AgentContextMenu", true, false) as PopupMenu
	tabs.tab_rmb_clicked.emit(tabs.current_tab)
	menu.hide()
	menu.id_pressed.emit(0)
	var rename := dock.find_child("AgentRenameDialog", true, false) as ConfirmationDialog
	if not await _line_roundtrip(rename, rename.find_child("AgentName", true, false), "unsaved-session-name", true):
		return
	rename.hide()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/editor_settings")
	root.push_input(shortcut)
	await process_frame
	var options: Window = root.find_children("*", "EditorSettingsDialog", true, false).front()
	var filter: LineEdit
	for candidate in options.find_children("*", "LineEdit", true, false):
		if candidate.is_visible_in_tree() and candidate.placeholder_text == "Filter Settings":
			filter = candidate
			break
	if not _check(options.visible and filter != null, "General settings filter was not opened"):
		return
	if not await _line_roundtrip(options, filter, "round4-editor-filter", false):
		return
	options.hide()
	var aux := Window.new()
	aux.title = "Auxiliary editor"
	var field := TextEdit.new()
	aux.add_child(field)
	EditorInterface.get_base_control().add_child(aux)
	aux.popup(Rect2i(0, 0, 360, 240))
	await process_frame
	field.text = "unsaved auxiliary text"
	field.grab_focus()
	field.select(0, 0, 0, 7)
	var dialog := await _open(aux)
	if dialog == null:
		return
	dialog.find_child("InsertWindowReference", true, false).pressed.emit()
	if not _check(composer.text.ends_with("unsaved"), "Auxiliary TextEdit selection was not staged"):
		return
	await _close(dialog)
	if not _check(aux.gui_get_focus_owner() == field and field.get_selected_text() == "unsaved" and field.text == "unsaved auxiliary text", "Auxiliary window did not restore its focused text"):
		return
	field.deselect()
	field.set_caret_column(field.get_line(0).length())
	var typing := InputEventKey.new()
	typing.keycode = KEY_X
	typing.unicode = 120
	typing.pressed = true
	aux.push_input(typing)
	if not _check(field.text == "unsaved auxiliary textx", "Source did not receive the next keystroke"):
		return
	dialog = await _open(aux)
	if dialog == null:
		return
	dialog.find_child("InsertWindowReference", true, false).pressed.emit()
	if not _check(composer.text.ends_with(field.text), "Whole unsaved field was not quoted"):
		return
	await _close(dialog)
	var private_line := LineEdit.new()
	private_line.secret = true
	aux.add_child(private_line)
	private_line.grab_focus()
	private_line.text = "private-fixture"
	dialog = await _open(aux)
	if not _check(dialog != null and dialog.find_child("InsertWindowReference", true, false) == null, "Private field was exposed"):
		return
	aux.queue_free()
	await process_frame
	await process_frame
	if not _check(not is_instance_valid(aux) and not is_instance_valid(dialog) and is_instance_valid(composer) and dock.is_ancestor_of(composer), "Releasing source destroyed shared conversation"):
		return
	print("WINDOW_ROUTE_RESULT=" + JSON.stringify({"line_edits": results, "auxiliary_text_preserved": true, "whole_field_quoted": true, "continued_typing": true, "secret_excluded": true, "destroyed_source_detached": true, "composer_id": composer.get_instance_id(), "messages_id": messages.get_instance_id()}))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
