@tool
extends SceneTree

func _chat_setting(chat: Node, name: String) -> Control:
	for section in [chat.get_ai_settings_control(), chat.get_environment_settings_control()]:
		var control = section.find_child(name, true, false)
		if control != null: return control
	return null

var dock
var chat_input: TextEdit
var send_button: Button
var dialog: ConfirmationDialog
var approvals = 0
var reject_write = false
var undoing = false
var messages: VBoxContainer

func _initialize():
	_run.call_deferred()

func _text() -> String:
	var text = ""
	for label in messages.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text() + "\n"
	return text

func _check(condition: bool, reason: String) -> bool:
	if not condition:
		push_error(reason)
	return condition

func _approve() -> void:
	approvals += 1
	if not undoing and FileAccess.file_exists("res://fixture.gd"):
		if not _check(FileAccess.get_file_as_string("res://fixture.gd") == OS.get_environment("AI_CHAT_EXPECTED_BEFORE"), "Native write ran before Godot confirmation"):
			quit(1)
			return
	# Exercise the buttons so AcceptDialog also dismisses its modal window.
	# Emitting confirmed/canceled directly leaves it blocking later mouse input.
	if reject_write:
		dialog.get_cancel_button().pressed.emit()
	else:
		dialog.get_ok_button().pressed.emit()

func _wait() -> bool:
	var deadline = Time.get_ticks_msec() + 15000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	return _check(dock.find_child("Stop", true, false).disabled, "Native file flow timed out")

func _snapshot_buttons(parent: Node, changes: bool) -> Array[Button]:
	var buttons: Array[Button] = []
	for button in parent.find_children("*", "Button", true, false):
		if button.has_meta("snapshot_id") and button.has_meta("snapshot_restored") != changes:
			buttons.append(button)
	return buttons

func _last_snapshot_button() -> Button:
	var buttons = _snapshot_buttons(messages, false)
	return buttons[-1] if not buttons.is_empty() else null

func _previous_version_button() -> Button:
	var buttons = _snapshot_buttons(messages, false)
	return buttons[-2] if buttons.size() >= 2 else null

func _phase(name: String, expected: String) -> bool:
	chat_input.text = "case:" + name
	send_button.pressed.emit()
	if not await _wait():
		return false
	if expected not in _text():
		print(_text())
	return _check(expected in _text(), "Native file result missing: " + expected)

func _check_agent_rename() -> bool:
	var tabs = dock.find_child("AgentTabs", true, false) as TabBar
	var menu = dock.get_node("AgentContextMenu") as PopupMenu
	var rename = dock.get_node("AgentRenameDialog") as ConfirmationDialog
	var name_input = rename.find_child("AgentName", true, false) as LineEdit
	var first_id = tabs.get_tab_metadata(0)
	var second_id = tabs.get_tab_metadata(1)
	var original = tabs.get_tab_title(0)
	var before = _text()
	chat_input.text = "RENAME_KEEP_DRAFT"
	# Mouse input needs the AI main screen visible, unlike signal-based checks.
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	if not _check(tabs.is_visible_in_tree(), "Agent tabs must be visible before testing mouse input"):
		return false
	# Exercise a real right click on the inactive tab without switching Agents.
	var click = InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_RIGHT
	click.pressed = true
	click.position = tabs.global_position + tabs.get_tab_rect(0).get_center()
	click.global_position = click.position
	if not _check(not dialog.visible, "Approval modal must be dismissed before testing mouse input"):
		return false
	root.push_input(click, true)
	if not _check(menu.visible and tabs.current_tab == 1 and menu.get_item_text(0).begins_with("重命名"), "Right click must open Rename without switching Agents"):
		return false
	menu.hide()
	click.pressed = false
	root.push_input(click, true)
	menu.id_pressed.emit(0)
	if not _check(rename.visible and name_input.text == original and name_input.has_focus(), "Rename dialog must show and focus the existing name"):
		return false
	# Programmatic LineEdit.text assignments do not emit text_changed.
	# Reproduce the typing signal before testing submission validation.
	name_input.text = "   "
	name_input.text_changed.emit(name_input.text)
	name_input.text_submitted.emit(name_input.text)
	if not _check(rename.get_ok_button().disabled and rename.visible and tabs.get_tab_title(0) == original, "Blank names must not submit"):
		return false
	name_input.text = "Cancelled name"
	rename.canceled.emit()
	if not _check(not rename.visible and tabs.get_tab_title(0) == original, "Canceling rename changed the title"):
		return false
	tabs.tab_rmb_clicked.emit(0)
	menu.hide()
	menu.id_pressed.emit(0)
	name_input.text = "  研发助手  "
	name_input.text_changed.emit(name_input.text)
	name_input.text_submitted.emit(name_input.text)
	if not _check(not rename.visible and tabs.get_tab_title(0) == "研发助手" and tabs.get_tab_metadata(0) == first_id and tabs.current_tab == 1 and chat_input.text == "RENAME_KEEP_DRAFT" and _text() == before, "Renaming an inactive Agent changed its identity or active conversation"):
		return false
	tabs.tab_rmb_clicked.emit(1)
	menu.hide()
	menu.id_pressed.emit(0)
	name_input.text = "x".repeat(100)
	if not _check(name_input.text.length() == 64, "Agent names must have a bounded length"):
		return false
	name_input.text = "关卡助手"
	name_input.text_changed.emit(name_input.text)
	rename.get_ok_button().pressed.emit()
	if not _check(tabs.get_tab_title(1) == "关卡助手" and tabs.get_tab_metadata(1) == second_id, "Save button renamed the wrong Agent"):
		return false
	# Closing the target while its dialog is open must not rename a neighbor.
	dock.find_child("AddAgent", true, false).pressed.emit()
	tabs.tab_rmb_clicked.emit(2)
	menu.hide()
	menu.id_pressed.emit(0)
	name_input.text = "Stale rename"
	tabs.tab_close_pressed.emit(2)
	rename.confirmed.emit()
	if not _check(tabs.tab_count == 2 and tabs.get_tab_title(0) == "研发助手" and tabs.get_tab_title(1) == "关卡助手", "Closed rename target changed another Agent"):
		return false
	tabs.current_tab = 0
	tabs.current_tab = 1
	messages = dock.find_child("Messages", true, false)
	if not _check(chat_input.text == "RENAME_KEEP_DRAFT" and _text() == before, "Agent switch after rename lost the conversation or draft"):
		return false
	print("AI_CHAT_AGENT_RENAME_OK")
	return true

func _put_file(file_path: String, contents: PackedByteArray) -> void:
	var file = FileAccess.open(file_path, FileAccess.WRITE)
	file.store_buffer(contents)
	file.close()

func _check_snapshot_history(expected: int) -> bool:
	var entry = dock.find_child("LocalSnapshotHistory", true, false) as Button
	var history = dock.get_node("LocalSnapshotHistoryDialog") as AcceptDialog
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	if not _check(entry != null and entry.is_visible_in_tree() and not entry.disabled and "本地快照" in entry.text, "Fixed local restore entry must be visible outside advanced settings even without snapshots"):
		return false
	entry.pressed.emit()
	if not _check(history.visible and history.get_meta("snapshot_count", -1) == expected, "History did not list only the active Agent's snapshots"):
		return false
	if expected == 0:
		var info = history.find_child("SnapshotHistoryInfo", true, false) as Label
		if not _check("无法事后还原" in info.text and history.find_children("RestoreSessionSnapshot", "Button", true, false).is_empty(), "Missing snapshots must explain limitations instead of hiding the entry or inventing a restore"):
			return false
	if not _check(history.find_children("ViewSessionChanges", "Button", true, false).size() == expected and history.find_children("JumpToChatMessage", "Button", true, false).size() == expected, "Every recorded turn needs a jump-to-chat entry and a read-only changes entry"):
		return false
	history.hide()
	return true

func _check_recorded_changes(expected: int = 2) -> bool:
	var disk_before = FileAccess.get_file_as_bytes("res://history_fixture.txt")
	var fixture_before = FileAccess.get_file_as_bytes("res://fixture.gd")
	var created_exists = FileAccess.file_exists("res://snapshot_created.txt")
	dock.find_child("LocalSnapshotHistory", true, false).pressed.emit()
	var history = dock.get_node("LocalSnapshotHistoryDialog") as AcceptDialog
	var entries = history.find_children("ViewSessionChanges", "Button", true, false)
	if not _check(entries.size() == expected, "All changing turns must be retained, including version restores"):
		return false
	var latest_id = entries[-2].get_meta("snapshot_id")
	var earlier_id = entries[-1].get_meta("snapshot_id")
	entries[-1].pressed.emit()
	var changes = dock.get_node("LocalSnapshotChangesDialog") as AcceptDialog
	var files = changes.find_child("SnapshotChangesFiles", true, false) as ItemList
	var before = changes.find_child("SnapshotChangesBefore", true, false) as TextEdit
	var after = changes.find_child("SnapshotChangesAfter", true, false) as TextEdit
	var diff = changes.find_child("SnapshotChangesDiff", true, false) as TextEdit
	if not _check(changes.visible and not history.visible and changes.get_meta("snapshot_id") == earlier_id and files.get_item_count() == 1 and before.text == "original history\n" and after.text == "earlier turn\n" and "-original history" in diff.text and "+earlier turn" in diff.text and not before.editable and not after.editable and not diff.editable, "Old turn must show its stored before/after/diff even after the same file changes again"):
		return false
	changes.hide()
	# Viewing records does not need local tool permission or a restorable disk.
	dock.get_ai_settings_control().find_child("AllowTools", true, false).set_pressed_no_signal(false)
	var inline_entries = _snapshot_buttons(messages, true)
	print("AI_CHAT_INLINE_CHANGES_COUNT ", inline_entries.size())
	for button in _snapshot_buttons(messages, false):
		print("AI_CHAT_INLINE_RESTORE_STATE ", button.name, " disabled=", button.disabled, " snapshot=", button.get_meta("snapshot_id"))
	if not _check(inline_entries.size() == expected, "Each changing chat turn needs its own changes entry after cleanup/restart"):
		return false
	if not _check(messages.find_children("ViewSessionChanges", "Button", true, false).size() == inline_entries.size() and messages.find_children("RestoreSessionSnapshot", "Button", true, false).size() == _snapshot_buttons(messages, false).size(), "Later turn buttons were auto-renamed and cannot receive busy/restore state updates"):
		return false
	inline_entries[1].pressed.emit()
	if not _check(changes.visible and changes.get_meta("snapshot_id") == latest_id and files.get_item_count() == 4, "Latest chat turn did not open its entire recorded file list"):
		return false
	for index in files.get_item_count():
		files.select(index)
		files.item_selected.emit(index)
		if files.get_item_text(index).ends_with("history_fixture.txt"):
			if not _check(before.text == "earlier turn\n" and after.text == "later turn\n" and "-earlier turn" in diff.text and "+later turn" in diff.text, "Latest turn history uses current disk instead of that turn's first-before and last-after"):
				return false
		elif files.get_item_text(index).ends_with("snapshot_created.txt"):
			if not _check(before.text.is_empty() and after.text == "created in one turn\n" and "+created in one turn" in diff.text, "Created file record disappeared after restore"):
				return false
		elif files.get_item_text(index).ends_with("fixture.gd"):
			if not _check("AI_CHAT_RUN_OK" in after.text and "intermediate" not in after.text, "Repeated writes should show the final recorded content"):
				return false
	changes.hide()
	dock.get_ai_settings_control().find_child("AllowTools", true, false).set_pressed_no_signal(true)
	return _check(FileAccess.get_file_as_bytes("res://history_fixture.txt") == disk_before and FileAccess.get_file_as_bytes("res://fixture.gd") == fixture_before and FileAccess.file_exists("res://snapshot_created.txt") == created_exists and not dialog.visible, "Viewing changes wrote files or opened restore confirmation")

func _run_snapshots() -> bool:
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	chat_input = dock.find_child("ChatInput", true, false)
	send_button = dock.find_child("Send", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	messages = dock.find_child("Messages", true, false)
	if not _check(dock.find_child("Undo", true, false) == null and dock.find_child("GitConversationCheckpoints", true, false) == null and dock.find_child("CheckpointHistory", true, false) == null, "Only local turn restore should remain; single-file/Git UI was not removed"):
		return false
	dock.get_ai_settings_control().find_child("AllowTools", true, false).set_pressed_no_signal(true)
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).set_pressed_no_signal(true)
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	var cli = OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli"
	backend.select(1 if cli else 0)
	backend.item_selected.emit(backend.selected)
	if cli:
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.get_ai_settings_control().find_child("CLIModel", true, false).text = "mock-model"
	else:
		dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
		dock.get_ai_settings_control().find_child("APIModel", true, false).text = "mock-model"
		dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	var before = "extends SceneTree\n\nfunc _initialize():\n\tquit(0)\n"
	var after = OS.get_environment("AI_CHAT_EXPECTED_AFTER")
	var eol_before = "\uFEFFheader\r\n\tvalue = 1\r\nfooter\r\n".to_utf8_buffer()
	var eol_after = "\uFEFFheader\r\n\tvalue = 2\r\nfooter\r\n".to_utf8_buffer()
	if OS.get_environment("AI_CHAT_SNAPSHOT_STAGE") == "seed":
		if not await _check_snapshot_history(0):
			return false
		if not await _phase("snapshot_seed", "SNAPSHOT_SEED_OK"):
			return false
		if not await _check_snapshot_history(0) or not await _phase("snapshot_earlier", "SNAPSHOT_EARLIER_OK"):
			return false
		if not await _check_snapshot_history(1) or not await _phase("snapshot_multi", "SNAPSHOT_MULTI_OK"):
			return false
		if not await _check_snapshot_history(2) or not await _check_recorded_changes():
			return false
		var restore = _snapshot_buttons(messages, false)[0]
		if not _check(restore != null and not restore.disabled and restore.text == "还原到此版本" and FileAccess.get_file_as_string("res://fixture.gd") == after and FileAccess.file_exists("res://snapshot_created.txt"), "Multi-file version or restore button missing"):
			return false
		# The fixed entry must route to the same whole-turn confirmation.
		dock.find_child("LocalSnapshotHistory", true, false).pressed.emit()
		var history = dock.get_node("LocalSnapshotHistoryDialog") as AcceptDialog
		var listed = history.find_children("RestoreSessionSnapshot", "Button", true, false)
		if not _check(listed.size() == 2, "Fixed history lost a recorded turn"):
			return false
		listed[-1].pressed.emit()
		if not _check(not history.visible, "Restore preview left its history modal open"):
			return false
		var preview = dialog.get_child(0).text
		if not _check(dialog.visible and dialog.title.contains("本地快照") and "fixture.gd" in preview and "eol_fixture.txt" in preview and "snapshot_created.txt" in preview and FileAccess.get_file_as_string("res://fixture.gd") == after, "Preview must include the entire turn without changing files even with automation enabled"):
			return false
		dialog.get_cancel_button().pressed.emit()
		if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == after, "Cancel performed a restore"):
			return false
		# Any conflict refuses all files, not a partial restore.
		_put_file("res://eol_fixture.txt", "external edit\n".to_utf8_buffer())
		restore.pressed.emit()
		if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == after and FileAccess.file_exists("res://snapshot_created.txt"), "A later edit was overwritten or earlier files partially restored"):
			return false
		_put_file("res://eol_fixture.txt", eol_after)
		# Check the files again at confirmation, not just at preview.
		restore.pressed.emit()
		_put_file("res://fixture.gd", (after + "# after preview\n").to_utf8_buffer())
		dialog.get_ok_button().pressed.emit()
		if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd").ends_with("# after preview\n") and FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_after and FileAccess.file_exists("res://snapshot_created.txt"), "Confirmation ignored a fresh conflict"):
			return false
		_put_file("res://fixture.gd", after.to_utf8_buffer())
		# Each Agent has independent restore entries; switching must not lose them.
		dock.find_child("AddAgent", true, false).pressed.emit()
		messages = dock.find_child("Messages", true, false)
		if not _check(_last_snapshot_button() == null, "New Agent inherited another Agent's restore button") or not await _check_snapshot_history(0):
			return false
		dock.find_child("AgentTabs", true, false).current_tab = 0
		messages = dock.find_child("Messages", true, false)
		if not _check(_last_snapshot_button() != null, "Switching Agents lost the snapshot"):
			return false
		print("AI_CHAT_SNAPSHOT_SEED_OK")
		return true
	if OS.get_environment("AI_CHAT_SNAPSHOT_STAGE").begins_with("verify"):
		if not await _check_snapshot_history(6) or not await _check_recorded_changes(6):
			return false
		if not _check(FileAccess.get_file_as_string("res://fixture.gd") == before and FileAccess.get_file_as_string("res://history_fixture.txt") == "continued after restore\n" and FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before and not FileAccess.file_exists("res://snapshot_created.txt") and not FileAccess.file_exists("res://.godot/editor/ai_chat_version_transaction.json"), "Startup transaction recovery lost files/context or left a journal"):
			return false
		if not await _phase("snapshot_verify", "SNAPSHOT_VERIFY_OK"):
			return false
		print("AI_CHAT_VERSION_RECOVERY_OK")
		return true
	# Restart reconstructs all versions, not merely the last turn's undo.
	if not await _check_snapshot_history(2) or not await _check_recorded_changes():
		return false
	var buttons = _snapshot_buttons(messages, false)
	var target_id = buttons[0].get_meta("snapshot_id")
	var newer_id = buttons[1].get_meta("snapshot_id")
	buttons[1].pressed.emit()
	if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == after, "Restoring current version must be a no-op, not undo that turn"):
		return false
	var restore = buttons[0]
	# A journal storage failure cannot change either files or Agent history.
	restore.pressed.emit()
	var journal_tmp = "res://.godot/editor/ai_chat_version_transaction.json.tmp"
	if not _check(DirAccess.make_dir_absolute(journal_tmp) == OK, "Cannot create transaction storage failure fixture"):
		return false
	dialog.get_ok_button().pressed.emit()
	DirAccess.remove_absolute(journal_tmp)
	if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == after and FileAccess.get_file_as_string("res://history_fixture.txt") == "later turn\n" and FileAccess.file_exists("res://snapshot_created.txt"), "Storage failure partially restored files") or not await _check_snapshot_history(2):
		return false
	EditorInterface.edit_script(load("res://fixture.gd"))
	await process_frame
	var code: CodeEdit = null
	for candidate in root.find_children("*", "CodeEdit", true, false):
		if candidate.text == after:
			code = candidate
	if not _check(code != null, "Cannot find the saved fixture editor"):
		return false
	code.set_caret_line(code.get_line_count() - 1)
	code.insert_text_at_caret("# unsaved")
	restore.pressed.emit()
	if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == after and "# unsaved" in code.text, "Unsaved buffer was overwritten"):
		return false
	code.undo()
	chat_input.text = "KEEP_VERSION_DRAFT"
	restore.pressed.emit()
	if not _check(dialog.visible, "Version restore needs separate confirmation even with automatic writes enabled"):
		return false
	dialog.get_ok_button().pressed.emit()
	if not _check(not dialog.visible and FileAccess.get_file_as_string("res://fixture.gd") == before and code.text == before and FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before and not FileAccess.file_exists("res://snapshot_created.txt") and FileAccess.get_file_as_string("res://history_fixture.txt") == "earlier turn\n" and chat_input.text == "KEEP_VERSION_DRAFT", "Restore must reach the END of the earlier version, undo later-only files, and preserve drafts"):
		return false
	if not await _check_snapshot_history(3) or not await _check_recorded_changes(3):
		return false
	var latest_changes = _snapshot_buttons(messages, true)[-1]
	latest_changes.pressed.emit()
	var changes = dock.get_node("LocalSnapshotChangesDialog") as AcceptDialog
	var files = changes.find_child("SnapshotChangesFiles", true, false) as ItemList
	if not _check(files.get_item_count() == 4 and "版本还原操作" in changes.find_child("SnapshotChangesInfo", true, false).text, "Restore did not create its own multi-file modification record"):
		return false
	changes.hide()
	# Previously selected versions stay usable, including forward restoration.
	for button in _snapshot_buttons(messages, false):
		if button.get_meta("snapshot_id") == newer_id:
			button.pressed.emit()
	if not _check(dialog.visible, "Newer original version is no longer restorable"):
		return false
	dialog.get_ok_button().pressed.emit()
	if not _check(FileAccess.get_file_as_string("res://fixture.gd") == after and code.text == after and FileAccess.get_file_as_string("res://history_fixture.txt") == "later turn\n" and FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_after and FileAccess.file_exists("res://snapshot_created.txt"), "Forward restore did not recreate the newer version exactly"):
		return false
	for button in _snapshot_buttons(messages, false):
		if button.get_meta("snapshot_id") == target_id:
			button.pressed.emit()
	dialog.get_ok_button().pressed.emit()
	if not await _check_snapshot_history(5) or not await _check_recorded_changes(5):
		return false
	if not await _phase("snapshot_follow", "SNAPSHOT_FOLLOW_OK"):
		return false
	if not _check(FileAccess.get_file_as_string("res://history_fixture.txt") == "continued after restore\n", "Following turn used stale source assumptions") or not await _check_snapshot_history(6):
		return false
	print("AI_CHAT_SNAPSHOT_RESTORE_OK")
	return true

func _windows_user_handles() -> int:
	var output = []
	var script = "import ctypes as c, sys; from ctypes import wintypes as w; k=c.WinDLL('kernel32'); u=c.WinDLL('user32'); k.OpenProcess.restype=w.HANDLE; k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.CloseHandle.argtypes=[w.HANDLE]; u.GetGuiResources.argtypes=[w.HANDLE,w.DWORD]; h=k.OpenProcess(0x1000,False,int(sys.argv[1])); print(u.GetGuiResources(h,1)); k.CloseHandle(h)"
	var code = OS.execute(OS.get_environment("AI_CHAT_TEST_PYTHON"), ["-c", script, str(OS.get_process_id())], output)
	if not _check(code == 0 and not output.is_empty() and str(output[0]).strip_edges().is_valid_int(), "Cannot measure Windows USER resources"):
		return -1
	return int(str(output[0]).strip_edges())

func _run_rename_stress():
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	chat_input = dock.find_child("ChatInput", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	dock.find_child("AddAgent", true, false).pressed.emit()
	messages = dock.find_child("Messages", true, false)
	var tabs = dock.find_child("AgentTabs", true, false) as TabBar
	var menu = dock.get_node("AgentContextMenu") as PopupMenu
	var rename = dock.get_node("AgentRenameDialog") as ConfirmationDialog
	var name_input = rename.find_child("AgentName", true, false) as LineEdit
	await process_frame
	var before = _windows_user_handles()
	print("AI_CHAT_USER_HANDLES_BEFORE ", before)
	if before < 0:
		quit(1)
		return
	for index in 256:
		if OS.get_environment("AI_CHAT_TEST_RAW_INPUT_STRESS") == "1":
			var injected_output = []
			var injected = OS.execute(OS.get_environment("AI_CHAT_TEST_PYTHON"), [OS.get_environment("AI_CHAT_TEST_RUNNER"), "--inject-mouse", str(OS.get_process_id())], injected_output)
			if not _check(injected == 0, "Windows mouse injection failed: " + str(injected_output)):
				quit(1)
				return
			# OS.execute deliberately stalled the editor while input queued.
			await process_frame
			await process_frame
			var resources = _windows_user_handles()
			if not _check(resources >= 0 and resources <= before + 32, "Raw mouse input leaked USER handles at iteration " + str(index) + ": " + str(resources)):
				quit(1)
				return
		var click = InputEventMouseButton.new()
		click.button_index = MOUSE_BUTTON_RIGHT
		click.pressed = true
		click.position = tabs.global_position + tabs.get_tab_rect(0).get_center()
		click.global_position = click.position
		root.push_input(click, true)
		if not _check(menu.visible, "Repeated right click failed at iteration " + str(index)):
			quit(1)
			return
		menu.hide()
		click.pressed = false
		root.push_input(click, true)
		if index % 3 != 0:
			menu.id_pressed.emit(0)
			if not _check(rename.visible, "Repeated rename dialog failed at iteration " + str(index)):
				quit(1)
				return
			if index % 3 == 1:
				name_input.text = "压力测试 " + str(index)
				name_input.text_changed.emit(name_input.text)
				rename.get_ok_button().pressed.emit()
			else:
				rename.get_cancel_button().pressed.emit()
		await process_frame
		if index % 64 == 63:
			print("AI_CHAT_USER_HANDLES_ITERATION ", index + 1, " ", _windows_user_handles())
	var after = _windows_user_handles()
	print("AI_CHAT_USER_HANDLES_AFTER ", after)
	if not _check(after >= 0 and after <= before + 16, "Repeated Agent popups leaked Windows USER resources"):
		quit(1)
		return
	print("AI_CHAT_AGENT_RENAME_STRESS_OK")
	quit(0)

func _run():
	if not OS.get_environment("AI_CHAT_SNAPSHOT_STAGE").is_empty():
		quit(0 if await _run_snapshots() else 1)
		return
	if OS.get_environment("AI_CHAT_TEST_RENAME_STRESS") == "1":
		await _run_rename_stress()
		return
	if OS.get_environment("AI_CHAT_TEST_RENAME_RESTORE") == "1":
		await create_timer(0.5).timeout
		dock = root.find_child("AI Chat", true, false)
		var tabs = dock.find_child("AgentTabs", true, false) as TabBar
		chat_input = dock.find_child("ChatInput", true, false)
		messages = dock.find_child("Messages", true, false)
		if not _check(tabs.tab_count == 2 and tabs.get_tab_title(0) == "研发助手" and tabs.get_tab_title(1) == "关卡助手" and tabs.current_tab == 1 and chat_input.text == "RENAME_KEEP_DRAFT" and "AGENT_B_SECRET" in _text() and "AGENT_A_SECRET" not in _text(), "Restart lost Agent names or conversation isolation"):
			quit(1)
			return
		print("AI_CHAT_AGENT_RENAME_RESTORE_OK")
		quit(0)
		return
	var controls = ""
	for code in range(1, 32):
		controls += String.chr(code)
	var control_data = {controls: controls}
	var encoded = JSON.stringify(control_data)
	for character in encoded:
		if not _check(character.unicode_at(0) >= 32, "JSON emitted a raw control character"):
			quit(1)
			return
	if not _check("\\v" not in encoded and JSON.parse_string(encoded) == control_data, "JSON control text did not round-trip with standard escapes"):
		quit(1)
		return
	print("AI_CHAT_JSON_CONTROLS_OK")
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "AI chat dock missing"):
		quit(1)
		return
	# Visibility assertions require the AI main screen to be selected.
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	if not _check(dock.is_visible_in_tree(), "AI chat dock should be visible for option checks"):
		quit(1)
		return
	var advanced = dock.get_ai_settings_control() as VBoxContainer
	var environment = dock.get_environment_settings_control() as VBoxContainer
	var settings_page = root.find_child("UnifiedSettings", true, false) as Control
	var categories = settings_page.find_child("UnifiedSettingsCategories", true, false) as TabContainer if settings_page != null else null
	var advanced_toggle = dock.find_child("AdvancedToggle", true, false) as Button
	if not _check(advanced != null and environment != null and settings_page != null and categories != null and advanced_toggle != null and not advanced.is_visible_in_tree() and not environment.is_visible_in_tree(), "Settings forms should stay off the business page"):
		quit(1)
		return
	var option_names = ["AllowTools", "AutoApplyFileChanges", "AutoExecuteCommands", "EngineAutoRestart"]
	var saved_options = {}
	for option_name in option_names:
		var option = _chat_setting(dock, option_name) as CheckBox
		var expected_parent = environment if option_name == "EngineAutoRestart" else advanced
		if not _check(option != null and option.get_parent() == expected_parent and not option.is_visible_in_tree(), "Option must belong to its central settings category: " + option_name):
			quit(1)
			return
		saved_options[option_name] = option.button_pressed
	for option_name in option_names:
		var category = 1 if option_name == "EngineAutoRestart" else 0
		var navigation = dock.find_child("EnvironmentSettings", true, false) if category == 1 else advanced_toggle
		navigation.pressed.emit()
		await process_frame
		if not _check(settings_page.is_visible_in_tree() and categories.current_tab == category and _chat_setting(dock, option_name).is_visible_in_tree(), "Central category did not reveal its option: " + option_name):
			quit(1)
			return
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	for option_name in option_names:
		var option = _chat_setting(dock, option_name) as CheckBox
		if not _check(not option.is_visible_in_tree() and option.button_pressed == saved_options[option_name], "Returning from settings changed an option: " + option_name):
			quit(1)
			return
	if not _check(dock.find_child("AttachLogs", true, false) == null, "Automatic log attachment checkbox should be removed"):
		quit(1)
		return
	if not _check(dock.find_child("CancelEngineBuild", true, false).is_visible_in_tree(), "Build cancellation must remain reachable outside settings"):
		quit(1)
		return
	if not _check(dock.find_child("ChatSettingsDialog", true, false) == null, "Global configuration must no longer use the old editable dialog"):
		quit(1)
		return
	dock.find_child("EnvironmentSettings", true, false).pressed.emit()
	await process_frame
	for control_name in ["BuildEngine", "RestartUpdatedEngine", "EngineBuildLog"]:
		var control = _chat_setting(dock, control_name)
		if not _check(environment.is_ancestor_of(control) and control.is_visible_in_tree() and categories.current_tab == 1, "Build controls must remain reachable in central environment settings: " + control_name):
			quit(1)
			return
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	print("AI_CHAT_ADVANCED_OPTIONS_OK")
	# Approval cases must not depend on the editor's automation defaults.
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).set_pressed_no_signal(false)
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).set_pressed_no_signal(false)
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(1)
	backend.item_selected.emit(1)
	dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
	dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
	dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
	dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
	dock.get_ai_settings_control().find_child("CLIModel", true, false).text = "mock-model"
	var tools = dock.get_ai_settings_control().find_child("AllowTools", true, false)
	tools.button_pressed = true
	# A legacy saved opt-in must no longer enable automatic attachment.
	EditorInterface.get_editor_settings().set_setting("ai_chat/attach_editor_logs", true)
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "LOG_TEST_PRIVATE_KEY"
	print("AI_CHAT_ON_DEMAND_LOG_SENTINEL LOG_TEST_PRIVATE_KEY")
	await process_frame
	chat_input = dock.find_child("ChatInput", true, false)
	send_button = dock.find_child("Send", true, false)
	messages = dock.find_child("Messages", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	dialog.about_to_popup.connect(_approve)
	var before = FileAccess.get_file_as_string("res://fixture.gd")
	OS.set_environment("AI_CHAT_EXPECTED_BEFORE", before)
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).set_pressed_no_signal(true)
	if not await _phase("native_baseline", "NATIVE_BASELINE_OK"):
		quit(1)
		return
	dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false).set_pressed_no_signal(false)
	if not await _phase("native_read", "NATIVE_READ_OK") or not await _phase("editor_logs", "NATIVE_LOGS_ON_DEMAND_OK"):
		quit(1)
		return
	if not _check(approvals == 0, "Read-only editor logs must not request execution approval"):
		quit(1)
		return
	tools.button_pressed = false
	if not await _phase("editor_logs_disabled", "NATIVE_LOGS_DISABLED_OK"):
		quit(1)
		return
	tools.button_pressed = true
	if not await _phase("native_write", "NATIVE_WRITE_OK"):
		quit(1)
		return
	print("AI_CHAT_ON_DEMAND_LOGS_OK")
	if not _check(FileAccess.get_file_as_string("res://fixture.gd") == OS.get_environment("AI_CHAT_EXPECTED_AFTER"), "Approved native write did not change the actual file"):
		quit(1)
		return
	var transport = dock.get_meta("cli_response_transport")
	if not _check(transport.protocol == "acp-native-files", "Native file channel was not used"):
		quit(1)
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(FileAccess.get_file_as_string("res://fixture.gd") == before, "Native write undo did not restore original file"):
		quit(1)
		return
	undoing = false
	reject_write = true
	if not await _phase("native_reject", "NATIVE_REJECT_OK") or not _check(FileAccess.get_file_as_string("res://fixture.gd") == before, "Denied native write changed the file"):
		quit(1)
		return
	reject_write = false
	if not await _phase("native_create", "NATIVE_CREATE_OK") or not _check(FileAccess.get_file_as_string("res://native_created.txt") == "Created through Godot approval\n", "Native new file write did not happen"):
		quit(1)
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(not FileAccess.file_exists("res://native_created.txt"), "Undo native creation did not remove the new file"):
		quit(1)
		return
	undoing = false
	if not await _phase("native_range", "NATIVE_RANGE_OK") or not await _phase("native_large", "NATIVE_LARGE_OK"):
		quit(1)
		return
	chat_input.text = "case:native_progress"
	send_button.pressed.emit()
	var stream_deadline = Time.get_ticks_msec() + 10000
	var streamed = false
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < stream_deadline:
		if "NATIVE_STREAM_" in _text():
			streamed = true
			break
		await create_timer(0.02).timeout
	if not _check(streamed and not dock.find_child("Stop", true, false).disabled, "Body was not shown before completion") or not await _wait():
		return
	if not _check(_text().count("NATIVE_STREAM_VISIBLE_OK") == 1 and not "PRIVATE_" in _text(), "Streaming duplicated the final body or leaked private notifications"):
		return
	if not await _phase("native_stream_next", "NATIVE_STREAM_NEXT_OK"):
		return
	if not await _phase("native_progress_error", "回复未完成"):
		return
	var failure_info = dock.get_meta("cli_failure_diagnostics", {})
	if not _check(_text().count("NATIVE_STREAM_VISIBLE_OK") == 2 and failure_info.get("stderr_bytes", 0) > 0 and not "PRIVATE_" in _text(), "Partial body or safe failure diagnostics were lost"):
		return
	var eol_before = FileAccess.get_file_as_bytes("res://eol_fixture.txt")
	if not await _phase("native_eol_edit", "NATIVE_EOL_EDIT_OK"):
		return
	var eol_after = FileAccess.get_file_as_bytes("res://eol_fixture.txt")
	if not _check(eol_after == ("\uFEFFheader\r\n\tvalue = 2\r\nfooter\r\n").to_utf8_buffer(), "Edit did not preserve exact BOM/CRLF bytes"):
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before, "CRLF edit undo did not restore exact bytes"):
		return
	undoing = false
	reject_write = true
	if not await _phase("native_eol_reject", "NATIVE_EOL_REJECT_OK") or not _check(FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before, "Rejected CRLF edit changed bytes"):
		return
	reject_write = false
	if not await _phase("native_search_edit", "NATIVE_SEARCH_EDIT_OK"):
		return
	if not _check(FileAccess.get_file_as_bytes("res://eol_fixture.txt") == ("\uFEFFheader\r\n\tvalue = 3\r\nfooter\r\n").to_utf8_buffer(), "Search to edit failed after seven read rounds"):
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before, "Search-to-edit undo did not restore exact bytes"):
		return
	undoing = false
	var auto_apply = dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false) as CheckBox
	if not _check(auto_apply != null and not auto_apply.button_pressed, "Automatic file changes must require initial opt-in"):
		quit(1)
		return
	auto_apply.button_pressed = true
	var previous_approvals = approvals
	if not await _phase("auto_write", "AUTO_WRITE_OK") or not _check(approvals == previous_approvals and FileAccess.get_file_as_string("res://fixture.gd") == OS.get_environment("AI_CHAT_EXPECTED_AFTER"), "Automatic native write showed approval or failed to write"):
		quit(1)
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(approvals == previous_approvals + 1 and FileAccess.get_file_as_string("res://fixture.gd") == before, "Automatic write undo must still confirm and restore the file"):
		quit(1)
		return
	undoing = false
	previous_approvals = approvals
	if not await _phase("auto_create", "AUTO_CREATE_OK") or not _check(approvals == previous_approvals and FileAccess.get_file_as_string("res://auto_created.txt") == "Automatically applied\n", "Automatic file creation showed approval or failed"):
		quit(1)
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(not FileAccess.file_exists("res://auto_created.txt"), "Automatic file creation undo failed"):
		quit(1)
		return
	undoing = false
	previous_approvals = approvals
	if not await _phase("auto_eol_edit", "AUTO_EOL_EDIT_OK") or not _check(approvals == previous_approvals and FileAccess.get_file_as_bytes("res://eol_fixture.txt") == ("\uFEFFheader\r\n\tvalue = 2\r\nfooter\r\n").to_utf8_buffer(), "Automatic Edit failed to preserve BOM/CRLF or showed approval"):
		quit(1)
		return
	undoing = true
	_previous_version_button().pressed.emit()
	if not await _wait() or not _check(FileAccess.get_file_as_bytes("res://eol_fixture.txt") == eol_before, "Automatic Edit undo failed to restore bytes"):
		quit(1)
		return
	undoing = false
	previous_approvals = approvals
	if not await _phase("native_command", "NATIVE_COMMAND_EXIT_OK") or not _check(approvals == previous_approvals + 1, "Automatic file changes bypassed command confirmation"):
		quit(1)
		return
	var auto_execute = dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false) as CheckBox
	if not _check(auto_execute != null and not auto_execute.button_pressed, "Automatic execution must require initial opt-in"):
		quit(1)
		return
	auto_execute.button_pressed = true
	previous_approvals = approvals
	if not await _phase("native_command_auto", "NATIVE_COMMAND_EXIT_OK") or not _check(approvals == previous_approvals, "Automatic command still showed approval"):
		quit(1)
		return
	auto_execute.button_pressed = false
	if not await _phase("native_command_restored", "NATIVE_COMMAND_EXIT_OK") or not _check(approvals == previous_approvals + 1, "Disabling automatic execution did not restore confirmation"):
		quit(1)
		return
	reject_write = true
	if not await _phase("native_command_reject", "NATIVE_COMMAND_REJECT_OK") or not _check(not FileAccess.file_exists("res://command_rejected.txt"), "Rejected command executed"):
		return
	reject_write = false
	tools.button_pressed = false
	if not await _phase("native_command_disabled", "NATIVE_COMMAND_REJECT_OK"):
		return
	print("AI_CHAT_NATIVE_COMMANDS_OK")
	if not await _phase("native_permission_off", "NATIVE_PERMISSION_OFF_OK"):
		quit(1)
		return
	tools.button_pressed = true
	if not await _phase("agent_a_seed", "AGENT_A_SECRET"):
		quit(1)
		return
	var agent = dock.find_child("AgentTabs", true, false) as TabBar
	dock.find_child("AddAgent", true, false).pressed.emit()
	messages = dock.find_child("Messages", true, false)
	if not _check(not "AGENT_A_SECRET" in _text(), "New native agent reused the old UI") or not await _phase("agent_b_seed", "AGENT_B_SECRET"):
		quit(1)
		return
	agent.current_tab = 0
	messages = dock.find_child("Messages", true, false)
	if not await _phase("agent_a_resume", "AGENT_A_RESUME_OK"):
		quit(1)
		return
	if not _check(dock.find_child("Clear", true, false) == null, "Removed new-conversation button is still present"):
		quit(1)
		return
	agent.current_tab = 1
	messages = dock.find_child("Messages", true, false)
	if not await _phase("agent_b_resume", "AGENT_B_RESUME_OK") or not _check(approvals == 16, "Unexpected native file/command/undo approval count"):
		quit(1)
		return
	if not await _check_agent_rename():
		quit(1)
		return
	print("AI_CHAT_INTEGRATION_OK native_files=true approvals=", approvals)
	quit(0)
