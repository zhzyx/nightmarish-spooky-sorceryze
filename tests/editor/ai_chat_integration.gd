@tool
extends SceneTree

func _refresh_models(chat: Node, wait_for_completion := true):
	chat.refresh_model_catalog()
	var deadline := Time.get_ticks_msec() + 40000
	while wait_for_completion and chat.get_model_catalog_snapshot().loading and Time.get_ticks_msec() < deadline:
		await process_frame

func _chat_setting(chat: Node, name: String) -> Control:
	for section in [chat.get_ai_settings_control(), chat.get_environment_settings_control()]:
		var control = section.find_child(name, true, false)
		if control != null: return control
	return null

const BEFORE = "extends SceneTree\n\nfunc _initialize():\n\tquit(0)\n"
const AFTER = "extends SceneTree\n\nfunc _initialize():\n\tprint(\"AI_CHAT_RUN_OK\")\n\tprinterr(\"AI_CHAT_STDERR_OK\")\n\tquit(0)\n"

var chat_input: TextEdit
var message_list: VBoxContainer

func _chat_text() -> String:
	var text = ""
	for label in message_list.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text() + "\n"
	return text
var send_button: Button
var stop_button: Button
var dialog: ConfirmationDialog
var tools: CheckBox
var progress_status: Label
var agent_tabs: TabBar
var approvals = 0
var failure = ""

func _initialize():
	_run.call_deferred()

func _check(condition: bool, message: String) -> bool:
	if not condition:
		failure = message
		push_error(message)
	return condition

func _chat_busy() -> bool:
	return not root.find_child("AI Chat", true, false).find_child("Stop", true, false).disabled

func _wait_idle(reject := false) -> bool:
	var deadline = Time.get_ticks_msec() + (90000 if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") == "1" else 25000)
	while _chat_busy() and Time.get_ticks_msec() < deadline:
		var active_tab = agent_tabs.current_tab
		for index in agent_tabs.tab_count:
			if not _check(not agent_tabs.is_tab_disabled(index), "Busy agent close buttons must remain usable"):
				return false
			if index != active_tab:
				agent_tabs.current_tab = index
				if not _check(agent_tabs.current_tab == active_tab, "Busy agent allowed a conversation switch"):
					return false
		if dialog.visible:
			if not _check(dialog.is_embedded() or dialog.get_window_id() != DisplayServer.INVALID_WINDOW_ID, "Approval dialog is visible without a native or embedded window"):
				return false
			if not _check("等待你确认" in progress_status.text, "Approval state was not displayed"):
				return false
			dialog.hide()
			# Window::get_exclusive_child() is not exposed to scripts; the engine clears it
			# exactly when the exclusive child stops being visible.
			var blocking = root.find_children("*", "Window", true, false).filter(func(w): return w.visible and w.exclusive)
			if not _check(not dialog.visible and blocking.is_empty(), "Hidden approval dialog still blocks the editor"):
				return false
			if reject:
				dialog.canceled.emit()
			else:
				approvals += 1
				dialog.confirmed.emit()
		await process_frame
	return _check(not _chat_busy() and progress_status.text.begins_with("就绪"), "AI operation timed out or progress did not reset")

func _chat_key(code: Key, shift := false, echo := false, pressed := true):
	var event = InputEventKey.new()
	event.keycode = code
	event.pressed = pressed
	event.shift_pressed = shift
	event.echo = echo
	chat_input.gui_input.emit(event)

func _check_chat_keys() -> bool:
	for code in [KEY_ENTER, KEY_KP_ENTER]:
		chat_input.text = "firstsecond"
		chat_input.set_caret_column(5)
		_chat_key(code, true)
		if not _check(chat_input.text == "first\nsecond" and not _chat_busy(), "Shift+Enter must insert a newline at the caret without sending"):
			return false
		chat_input.undo()
		if not _check(chat_input.text == "firstsecond", "Shift+Enter newline must be undoable"):
			return false
		chat_input.select(0, 0, 0, 5)
		_chat_key(code, true)
		if not _check(chat_input.text == "\nsecond", "Shift+Enter must replace the selected text"):
			return false
		_chat_key(code, false, true)
		_chat_key(code, false, false, false)
		if not _check(chat_input.text == "\nsecond" and not _chat_busy(), "Repeated Enter and key release must not send or insert newlines"):
			return false
		chat_input.text = ""
		_chat_key(code)
		if not _check(chat_input.text.is_empty() and not _chat_busy(), "Empty Enter must not send or insert a newline"):
			return false
	print("AI_CHAT_KEYBOARD_OK")
	return true

func _last_snapshot_button() -> Button:
	var buttons = message_list.find_children("RestoreSessionSnapshot", "Button", true, false)
	return buttons[-1] if not buttons.is_empty() else null

func _check_workflow_session(dock: Node) -> bool:
	var buttons = message_list.find_children("RestoreSessionSnapshot", "Button", true, false)
	return _check(buttons.size() == 1 and "本地快照" in buttons[0].text and dock.find_child("Undo", true, false) == null, "A changed turn must offer only the local snapshot restore")

func _check_agent_sessions(dock: Node) -> bool:
	return _check(_last_snapshot_button() == null and not dock.find_children("RestoreSessionSnapshot", "Button", true, false).is_empty(), "A second Agent must not inherit another Agent's local snapshots")

func _command_pid_alive(pid: int) -> bool:
	# OS.is_process_running only knows direct Godot children on Windows. The
	# PowerShell child belongs to the real provenance guard, so query its handle.
	var probe = "import ctypes,sys; k=ctypes.WinDLL('kernel32',use_last_error=True); k.OpenProcess.restype=ctypes.c_void_p; k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]; k.CloseHandle.argtypes=[ctypes.c_void_p]; h=k.OpenProcess(0x1000,False,int(sys.argv[1])); c=ctypes.c_ulong(); alive=bool(h and k.GetExitCodeProcess(h,ctypes.byref(c)) and c.value==259); k.CloseHandle(h) if h else None; sys.exit(0 if alive else 1)"
	return OS.execute(OS.get_environment("AI_CHAT_TEST_PYTHON"), ["-c", probe, str(pid)]) == 0

func _wait_send_ready() -> bool:
	var dock = root.find_child("AI Chat", true, false)
	var backend = dock.find_child("AIBackend", true, false)
	var send = dock.find_child("Send", true, false)
	var deadline = Time.get_ticks_msec() + 40000
	while (backend.disabled or send.disabled) and Time.get_ticks_msec() < deadline:
		await process_frame
	var status = dock.find_child("ModelStatus", true, false)
	return _check(not backend.disabled and not send.disabled, "Model loading did not re-enable chat sending: " + status.text)

func _phase(name: String, marker: String, reject := false) -> bool:
	if not await _wait_send_ready():
		return false
	chat_input.text = "case:" + name
	if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") == "1":
		send_button.pressed.emit()
		var idle = await _wait_idle(reject)
		print("WINDOWS_COMMAND_PHASE ", name, " passed=", idle and marker in _chat_text())
		return idle and _check(marker in _chat_text(), "Missing response marker: " + marker)
	var code = KEY_ENTER if name == "workflow" else KEY_KP_ENTER
	_chat_key(code)
	if not _check(chat_input.text.is_empty() and "正在等待 AI" in progress_status.text, "Enter did not send and clear the input immediately"):
		return false
	chat_input.text = "queued draft"
	_chat_key(code, false, true)
	if not _check(chat_input.text == "queued draft", "Repeated Enter while busy must preserve the draft without submitting duplicates"):
		return false
	chat_input.text = ""
	if not await _wait_idle(reject):
		return false
	return _check(marker in _chat_text(), "Missing response marker: " + marker)

func _check_window_fill(root: Window, main_screen: Control) -> bool:
	# Compare dock widths above the editor's minimum size on every host.
	root.size = Vector2i(1600, 1000)
	EditorInterface.set_distraction_free_mode(false)
	EditorInterface.set_main_screen_editor("3D")
	await create_timer(0.3).timeout
	var bottom_panel = _find_by_name(root, "BottomPanel")
	if not _check(bottom_panel != null and bottom_panel is Control, "Bottom panel not found"):
		return false
	var scene_tabs = _find_by_name(root, "SceneTabs")
	if not _check(scene_tabs != null and scene_tabs is Control, "Scene tabs not found"):
		return false

	# The editor starts on a normal main screen (3D) with the docks visible.
	var normal_x = main_screen.get_size().x
	if not _check(bottom_panel.is_visible() and scene_tabs.is_visible(), "Docks must be visible before selecting AI Chat"):
		return false

	EditorInterface.set_main_screen_editor("AI Chat")
	await create_timer(0.3).timeout
	var fill_x = main_screen.get_size().x
	if not _check(not bottom_panel.is_visible() and not scene_tabs.is_visible(), "Bottom panel and scene tabs must be hidden with AI Chat"):
		return false
	if not _check(fill_x > normal_x * 1.1, "AI Chat does not fill the window width"):
		return false

	EditorInterface.set_main_screen_editor("Script")
	await create_timer(0.3).timeout
	if not _check(bottom_panel.is_visible() and scene_tabs.is_visible(), "Bottom panel and scene tabs must return after switching away"):
		return false
	if not _check(main_screen.get_size().x < fill_x * 0.9, "Other main screens must not fill the window width"):
		return false
	EditorInterface.set_main_screen_editor("AI Chat")
	await create_timer(0.3).timeout
	if not _check(not bottom_panel.is_visible() and not scene_tabs.is_visible(), "AI Chat must hide the bottom panel and scene tabs again"):
		return false
	if not _check(main_screen.get_size().x >= fill_x * 0.9, "AI Chat must fill the window width again"):
		return false
	EditorInterface.set_main_screen_editor("3D")
	await create_timer(0.3).timeout
	return true

func _find_by_name(node: Node, fragment: String) -> Node:
	for child in node.get_children():
		if String(child.name).contains(fragment):
			return child
		var found = _find_by_name(child, fragment)
		if found != null:
			return found
	return null

func _check_workspace_pages(dock: Node) -> bool:
	var pages = dock.find_child("AIWorkspacePages", true, false) as TabContainer
	if pages != null:
		var titles: Array[String] = []
		for index in pages.get_tab_count():
			titles.append(pages.get_tab_title(index))
		print("AI_WORKSPACE_PAGES=", JSON.stringify({"titles": titles, "current": pages.current_tab}))
	if not _check(pages != null and pages.get_tab_count() == 3 and pages.current_tab == 0 and pages.get_tab_title(0) == "会话" and pages.get_tab_title(1) == "定时器" and pages.get_tab_title(2) == "共工", "AI workspace needs conversation, timer and GongGong fixed pages, initially conversation"):
		return false
	var tabs = pages.get_tab_bar()
	var agents_page = pages.get_tab_control(0)
	var timers_page = pages.get_tab_control(1)
	if not _check(tabs.tab_close_display_policy == TabBar.CLOSE_BUTTON_SHOW_NEVER and not pages.drag_to_rearrange_enabled and tabs.find_children("*", "Button", true, false).is_empty() and agents_page.is_ancestor_of(dock.find_child("AgentTabs", true, false)) and timers_page.find_child("ScheduledTasks", true, false) != null, "Workspace tabs must not have add/close/reorder controls; timer page needs task controls"):
		return false
	var chat = dock.find_child("ChatInput", true, false) as TextEdit
	var draft = chat.text
	chat.text = "WORKSPACE_PAGE_DRAFT"
	pages.current_tab = 1
	await process_frame
	if not _check(timers_page.visible and not agents_page.visible and chat.text == "WORKSPACE_PAGE_DRAFT" and timers_page.size.x > 0 and timers_page.size.y > 0, "Switching to the blank timer page lost the draft or layout"):
		return false
	tabs.tab_close_pressed.emit(1)
	if not _check(pages.get_tab_count() == 3 and pages.current_tab == 1, "Fixed timer page was closed"):
		return false
	pages.current_tab = 0
	await process_frame
	if not _check(agents_page.visible and not timers_page.visible and chat.text == "WORKSPACE_PAGE_DRAFT", "Returning to Agents lost its existing UI"):
		return false
	chat.text = draft
	print("AI_CHAT_WORKSPACE_PAGES_OK")
	return true

func _schedule_add(dock: Node, title: String, unit: int, prompt := "case:scheduler_run"):
	dock.find_child("AddScheduledTask", true, false).pressed.emit()
	dock.find_child("ScheduledTaskTitle", true, false).text = title
	dock.find_child("ScheduledTaskPrompt", true, false).text = prompt
	dock.find_child("ScheduledTaskUnit", true, false).select(unit)
	dock.find_child("ScheduledTaskDialog", true, false).confirmed.emit()
	dock.find_child("ScheduledTaskDialog", true, false).hide()

func _schedule_history() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))

func _schedule_wait(dock: Node, count: int, seconds := 25.0) -> bool:
	var deadline = Time.get_ticks_msec() + int(seconds * 1000)
	var tabs: TabBar = dock.find_child("ScheduledAgentTabs", true, false)
	while Time.get_ticks_msec() < deadline:
		if tabs.tab_count == count and not _chat_busy() and ("已完成" in tabs.get_tab_tooltip(count - 1) or "失败" in tabs.get_tab_tooltip(count - 1)):
			await process_frame
			return true
		await process_frame
	return _check(false, "Scheduled Agent count/completion timed out")

func _run_schedules(dock: Node) -> bool:
	var pages: TabContainer = dock.find_child("AIWorkspacePages", true, false)
	var picker: OptionButton = dock.find_child("ScheduledTasks", true, false)
	var runs: TabBar = dock.find_child("ScheduledAgentTabs", true, false)
	var run: Button = dock.find_child("RunScheduledTaskNow", true, false)
	var enabled: CheckBox = dock.find_child("ScheduledTaskEnabled", true, false)
	pages.current_tab = 1
	if OS.get_environment("AI_CHAT_SCHEDULE_STAGE") == "restore":
		if not _check(picker.item_count == 4 and runs.tab_count == 3 and not _chat_busy(), "Tasks/runs were not restored independently"):
			return false
		await create_timer(2.0).timeout
		if not _check(not _chat_busy() and runs.tab_count == 3, "Startup replayed missed ticks or an interrupted Agent"):
			return false
		# Sequence continues even after deleting one run, without reusing its name.
		run.pressed.emit()
		if not await _schedule_wait(dock, 4) or not _check(runs.get_tab_title(3) == "MINUTE_5", "Restart reused the schedule sequence"):
			return false
		print("AI_CHAT_SCHEDULE_RESTORE_OK")
		return true
	# All periods are configured through the real editor form.
	for unit in 4:
		_schedule_add(dock, ["MINUTE", "HOUR", "DAY", "WEEK"][unit], unit)
		if unit != 0:
			enabled.button_pressed = false
	picker.select(0)
	picker.item_selected.emit(0)
	if not _check(picker.item_count == 4 and enabled.button_pressed and "每 1" in dock.find_child("ScheduledTaskDescription", true, false).text, "Task form did not configure the periods"):
		return false
	chat_input.text = "MANUAL_UNSENT_DRAFT"
	run.pressed.emit()
	# Attempting another trigger while this task is outstanding must not overlap.
	run.pressed.emit()
	if not await _schedule_wait(dock, 1):
		return false
	message_list = dock.find_child("Messages", true, false)
	if not _check(runs.get_tab_title(0) == "MINUTE_1" and "SCHEDULER_RUN_OK" in _chat_text() and dock.find_child("ScheduledAgentChat", true, false).is_ancestor_of(chat_input), "Run was not routed below the task introduction"):
		return false
	pages.current_tab = 0
	await process_frame
	message_list = dock.find_child("Messages", true, false)
	if not _check(chat_input.text == "MANUAL_UNSENT_DRAFT" and "SCHEDULER_RUN_OK" not in _chat_text() and pages.get_tab_control(0).is_ancestor_of(chat_input), "Scheduler consumed the manual draft or mixed histories"):
		return false
	# A due task waits for a normal conversation to finish, then creates fresh context.
	chat_input.text = "case:scheduler_manual"
	send_button.pressed.emit()
	pages.current_tab = 1
	run.pressed.emit()
	if not _check(_chat_busy() and runs.tab_count == 2 and dock.find_child("ScheduledAgentChat", true, false).get_child_count() == 0, "Busy manual task was interrupted"):
		return false
	if not await _schedule_wait(dock, 2):
		return false
	# Verify a real minimum-period tick (60 seconds), not a synthetic immediate call.
	if not await _schedule_wait(dock, 3, 80.0):
		return false
	if not _check(runs.get_tab_title(2) == "MINUTE_3", "Periodic tick did not create a new named Agent"):
		return false
	print("AI_CHAT_SCHEDULE_REAL_MINUTE_OK")
	enabled.button_pressed = false
	await create_timer(1.5).timeout
	var data = _schedule_history()
	# JSON parses numbers as floats; Array equality also compares element types.
	if not _check(data.scheduled_tasks.size() == 4 and data.scheduled_tasks.map(func(t): return int(t.unit)) == [0, 1, 2, 3] and data.scheduled_tasks.all(func(t): return not t.enabled), "Task persistence/disable state is wrong"):
		return false
	print("AI_CHAT_SCHEDULE_PERSISTENCE_OK")
	# Edit only future instructions; preserve the existing run's independent history.
	dock.find_child("EditScheduledTask", true, false).pressed.emit()
	dock.find_child("ScheduledTaskTitle", true, false).text = "MINUTE"
	dock.find_child("ScheduledTaskPrompt", true, false).text = "case:scheduler_fail"
	dock.find_child("ScheduledTaskDialog", true, false).confirmed.emit()
	dock.find_child("ScheduledTaskDialog", true, false).hide()
	run.pressed.emit()
	if not await _schedule_wait(dock, 4):
		return false
	if not _check("失败" in dock.find_child("ScheduledTaskStatus", true, false).text, "Failed task did not stop with diagnostics"):
		return false
	# Restore future prompt, delete only the failed run, preserve numbering.
	dock.find_child("EditScheduledTask", true, false).pressed.emit()
	dock.find_child("ScheduledTaskPrompt", true, false).text = "case:scheduler_run"
	dock.find_child("ScheduledTaskDialog", true, false).confirmed.emit()
	dock.find_child("ScheduledTaskDialog", true, false).hide()
	runs.tab_close_pressed.emit(3)
	var close: ConfirmationDialog = dock.find_child("AgentCloseConfirmation", true, false)
	if close.visible:
		close.hide()
		close.confirmed.emit()
	await create_timer(1.5).timeout
	if not _check(runs.tab_count == 3, "Closing one execution removed its task or other runs"):
		return false
	print("AI_CHAT_SCHEDULE_OK")
	return true

func _queue_wait(dock: Node) -> bool:
	var deadline = Time.get_ticks_msec() + (90000 if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") == "1" else 25000)
	while (_chat_busy() or (dock.get_meta("queued_message_count", 0) > 0 and not dock.get_meta("queue_paused", false))) and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(not _chat_busy(), "Queued operation did not finish")

func _queue_send(text: String):
	chat_input.text = "case:" + text
	_chat_key(KEY_ENTER)

func _run_message_queue(dock: Node) -> bool:
	var resume: Button = dock.find_child("ResumeMessageQueue", true, false)
	var attachments: HFlowContainer = dock.find_child("ImageAttachments", true, false)
	var picker: FileDialog = dock.get_node("AIImagePicker")
	if OS.get_environment("AI_CHAT_QUEUE_STAGE") == "restore":
		if not _check(agent_tabs.tab_count == 2 and agent_tabs.current_tab == 1 and chat_input.text == "UNSENT_B" and dock.get_meta("queue_paused") and dock.get_meta("queued_message_count") == 1 and not _chat_busy(), "Restart did not safely restore Agent B queue and draft"):
			return false
		await create_timer(0.3).timeout
		if not _check(not _chat_busy() and "QUEUE_RESTART_B_OK" not in _chat_text(), "Startup automatically executed a pending task"):
			return false
		resume.pressed.emit()
		if not await _queue_wait(dock) or not _check("QUEUE_RESTART_B_OK" in _chat_text() and chat_input.text == "UNSENT_B", "Agent B queue did not resume or draft was consumed"):
			return false
		agent_tabs.current_tab = 0
		message_list = dock.find_child("Messages", true, false)
		if not _check(dock.get_meta("queued_message_count") == 1 and dock.get_meta("queue_paused"), "Agent A queue was lost or mixed with B"):
			return false
		resume.pressed.emit()
		if not await _queue_wait(dock) or not _check("QUEUE_RESTART_A_OK" in _chat_text() and "QUEUE_RESTART_B_OK" not in _chat_text(), "Agent A resumed the wrong message"):
			return false
		print("AI_CHAT_QUEUE_RESTORE_OK")
		return true
	var image = Image.create(8, 8, false, Image.FORMAT_RGB8)
	image.fill(Color(0.2, 0.4, 0.6))
	var image_path = ProjectSettings.globalize_path("res://queue_image.png")
	if not _check(image.save_png(image_path) == OK, "Could not prepare queue image"):
		return false
	_queue_send("queue_first")
	if not _check(_chat_busy() and not send_button.disabled and not dock.find_child("AddImage", true, false).disabled and chat_input.editable, "Composer was locked during execution"):
		return false
	picker.files_selected.emit(PackedStringArray([image_path]))
	_queue_send("queue_second")
	_queue_send("queue_deleted")
	dock.find_child("QueuedMessages", true, false).find_children("RemoveQueuedMessage", "Button", true, false)[1].pressed.emit()
	_queue_send("queue_third")
	_chat_key(KEY_ENTER, false, true)
	if not _check(dock.get_meta("queued_message_count") == 2 and chat_input.text.is_empty() and attachments.get_child_count() == 0 and "case:queue_second" not in _chat_text(), "Queue order, deletion or input clearing failed"):
		return false
	chat_input.text = "UNSENT_DRAFT"
	picker.files_selected.emit(PackedStringArray([image_path]))
	var pages = dock.find_child("AIWorkspacePages", true, false) as TabContainer
	pages.current_tab = 1
	await process_frame
	if not _check(_chat_busy() and not pages.get_tab_control(0).visible and pages.get_tab_control(1).visible, "Timer page switch interrupted the running Agent"):
		return false
	if not await _queue_wait(dock):
		return false
	if not _check(pages.current_tab == 1 and "QUEUE_THIRD_OK" in _chat_text(), "Hidden Agents stopped dispatching queued turns or stole the active page"):
		return false
	pages.current_tab = 0
	await process_frame
	var text = _chat_text()
	if not _check(text.find("QUEUE_FIRST_OK") < text.find("case:queue_second") and text.find("QUEUE_SECOND_OK") < text.find("case:queue_third") and "QUEUE_THIRD_OK" in text and "queue_deleted" not in text and chat_input.text == "UNSENT_DRAFT" and attachments.get_child_count() == 1 and dock.get_meta("queued_message_count") == 0, "FIFO execution or draft/image isolation failed"):
		return false
	attachments.find_child("RemoveImage", true, false).pressed.emit()
	_queue_send("queue_fail")
	_queue_send("queue_after_failure")
	if not await _queue_wait(dock) or not _check(dock.get_meta("queue_paused") and dock.get_meta("queued_message_count") == 1 and "QUEUE_AFTER_FAILURE_OK" not in _chat_text(), "Failure did not pause the pending queue"):
		return false
	resume.pressed.emit()
	if not await _queue_wait(dock) or not _check("QUEUE_AFTER_FAILURE_OK" in _chat_text(), "Explicit queue resume failed"):
		return false
	_queue_send("queue_slow")
	picker.files_selected.emit(PackedStringArray([image_path]))
	_queue_send("queue_restart_a")
	stop_button.pressed.emit()
	if not _check(dock.get_meta("queue_paused") and dock.get_meta("queued_message_count") == 1 and not _chat_busy(), "Stop lost the queue or started another task"):
		return false
	dock.find_child("AddAgent", true, false).pressed.emit()
	message_list = dock.find_child("Messages", true, false)
	if not _check(dock.get_meta("queued_message_count") == 0, "New Agent inherited a pending task"):
		return false
	_queue_send("queue_slow")
	_queue_send("queue_restart_b")
	stop_button.pressed.emit()
	chat_input.text = "UNSENT_B"
	await create_timer(1.7).timeout
	if not _check(not _chat_busy() and "QUEUE_STALE_RESPONSE" not in _chat_text() and "QUEUE_RESTART_B_OK" not in _chat_text(), "Cancelled task or queued task executed after stop"):
		return false
	if not await _wait_saved_history(dock):
		return false
	print("AI_CHAT_QUEUE_OK")
	return true

func _find_code(node: Node) -> CodeEdit:
	if node is CodeEdit and "extends SceneTree" in node.text:
		return node
	for child in node.get_children():
		var found = _find_code(child)
		if found:
			return found
	return null

func _wait_saved_history(dock: Node) -> bool:
	# Persistence is asynchronous; an idle model is not a disk-write barrier.
	await process_frame
	await process_frame
	var save_timer: Timer = dock.find_child("AIHistorySaveTimer", true, false)
	var deadline = Time.get_ticks_msec() + 30000
	while (not save_timer.is_stopped() or dock.get_meta("history_saving", false)) and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(save_timer.is_stopped() and not dock.get_meta("history_saving", false), "History autosave did not finish")

func _run_history_performance():
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "History performance dock missing"):
		quit(1)
		return
	chat_input = dock.find_child("ChatInput", true, false)
	agent_tabs = dock.find_child("AgentTabs", true, false)
	if OS.get_environment("AI_CHAT_HISTORY_PERFORMANCE") == "restore":
		if not _check(agent_tabs.tab_count == 3 and agent_tabs.current_tab == 2 and chat_input.text == "SHUTDOWN_LATEST_DRAFT", "Shutdown did not flush the latest draft"):
			quit(1)
			return
		print("AI_CHAT_HISTORY_PERFORMANCE_RESTORE_OK")
		quit(0)
		return
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text_changed.emit("test-secret")
	# Drain startup persistence before measuring saves caused by user input.
	if not await _wait_saved_history(dock):
		quit(1)
		return
	var initial_save_count: int = dock.get_meta("history_save_stats", {}).get("count", 0)
	var max_gap = 0
	for i in 25:
		var before = Time.get_ticks_usec()
		# set_text emits text_set, not the text_changed signal used by typing.
		chat_input.select_all()
		chat_input.insert_text_at_caret("连续输入_%d" % i)
		await create_timer(0.08).timeout
		max_gap = maxi(max_gap, Time.get_ticks_usec() - before)
	print("AI_CHAT_HISTORY_TYPING_MAX_GAP_USEC: ", max_gap)
	if not _check(max_gap < 500000 and not dock.get_meta("history_saving", false) and dock.get_meta("history_save_stats", {}).get("count", 0) == initial_save_count, "Continuous typing triggered a full-history save or blocked the main loop"):
		quit(1)
		return
	var deadline = Time.get_ticks_msec() + 10000
	while not dock.get_meta("history_saving", false) and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _check(dock.get_meta("history_saving", false), "Background history writer did not start"):
		quit(1)
		return
	chat_input.text = "EDIT_DURING_BACKGROUND_WRITE test-secret"
	var before = Time.get_ticks_usec()
	agent_tabs.current_tab = 0
	await process_frame
	agent_tabs.current_tab = 2
	await process_frame
	max_gap = maxi(max_gap, Time.get_ticks_usec() - before)
	# Watch frame latency throughout the expensive serialization/backup as well.
	deadline = Time.get_ticks_msec() + 30000
	var save_timer: Timer = dock.find_child("AIHistorySaveTimer", true, false)
	while (not save_timer.is_stopped() or dock.get_meta("history_saving", false)) and Time.get_ticks_msec() < deadline:
		before = Time.get_ticks_usec()
		await process_frame
		max_gap = maxi(max_gap, Time.get_ticks_usec() - before)
	if not await _wait_saved_history(dock):
		quit(1)
		return
	var stats: Dictionary = dock.get_meta("history_save_stats", {})
	print("AI_CHAT_HISTORY_PERFORMANCE_STATS: ", stats, " max_gap_usec=", max_gap)
	if not _check(stats.get("error", -1) == OK and stats.get("bytes", 0) > 58000000 and stats.get("count", 0) >= initial_save_count + 2 and stats.get("snapshot_usec", 1000000) < 100000 and max_gap < 500000, "Large-history save still blocks input or loses in-flight edits"):
		quit(1)
		return
	var disk = FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json")
	if not _check("EDIT_DURING_BACKGROUND_WRITE [REDACTED]" in disk and "test-secret" not in disk, "Background snapshot lost a draft or leaked a key"):
		quit(1)
		return
	# Exit before the debounce expires: the shutdown barrier must save this too.
	chat_input.text = "SHUTDOWN_LATEST_DRAFT"
	print("AI_CHAT_HISTORY_PERFORMANCE_OK")
	quit(0)

func _run_cleanup():
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "Cleanup dock missing"):
		quit(1)
		return
	chat_input = dock.find_child("ChatInput", true, false)
	agent_tabs = dock.find_child("AgentTabs", true, false)
	message_list = dock.find_child("Messages", true, false)
	send_button = dock.find_child("Send", true, false)
	stop_button = dock.find_child("Stop", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	progress_status = dock.find_child("AIProgressStatus", true, false)
	if not _check("KEEP_UNFINISHED_WORK" in _chat_text() and "KEEP_INCOMPLETE" in _chat_text() and "KEEP_FAILURE" in _chat_text(), "Unfinished evidence was removed at startup"):
		quit(1)
		return
	if OS.get_environment("AI_CHAT_CLEANUP_STAGE") == "restore":
		if not _check("CLEANUP_FINAL" in _chat_text() and "CLEANUP_FOLLOW_OK" in _chat_text() and message_list.find_children("WorkProcess", "RichTextLabel", true, false).size() == 1, "Completed work reappeared after restart"):
			quit(1)
			return
		print("AI_CHAT_CLEANUP_RESTORE_OK")
		quit(0)
		return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(1 if OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli" else 0)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	dock.find_child("APIModel", true, false).text = "mock-model"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text_changed.emit("test-secret")
	if backend.selected == 1:
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.find_child("CLIModel", true, false).text = "mock-model"
	chat_input.text = "case:cleanup_round"
	send_button.pressed.emit()
	var deadline = Time.get_ticks_msec() + (90000 if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") == "1" else 25000)
	var saw_details = false
	while _chat_busy() and Time.get_ticks_msec() < deadline:
		if message_list.find_children("WorkProcess", "RichTextLabel", true, false).size() >= 2 and "已读取文件" in _chat_text():
			saw_details = true
		await process_frame
	if not _check(saw_details and "CLEANUP_FINAL" in _chat_text() and "TEMPORARY_ANALYSIS" not in _chat_text() and message_list.find_children("WorkProcess", "RichTextLabel", true, false).size() == 1, "Working details must exist until the final answer, then disappear"):
		quit(1)
		return
	var pid = dock.get_meta("cli_transport", {}).get("pid", -1)
	if not await _phase("cleanup_follow", "CLEANUP_FOLLOW_OK"):
		quit(1)
		return
	if backend.selected == 1 and not _check(dock.get_meta("cli_transport").pid == pid and dock.get_meta("cli_transport").mode == "incremental", "Cleanup restarted the CLI or replayed the user task"):
		quit(1)
		return
	if not await _wait_saved_history(dock):
		quit(1)
		return
	for suffix in ["", ".bak"]:
		var history_text = FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json" + suffix)
		if not _check(history_text.length() < 100000 and "DISCARDED_TOOL_PAYLOAD" not in history_text and "TEMPORARY_ANALYSIS" not in history_text, "Removed details remain in primary/backup"):
			quit(1)
			return
	print("AI_CHAT_CLEANUP_OK")
	quit(0)

func _run_history():
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "History test dock missing"):
		quit(1)
		return
	var stage = OS.get_environment("AI_CHAT_HISTORY_STAGE")
	agent_tabs = dock.find_child("AgentTabs", true, false)
	chat_input = dock.find_child("ChatInput", true, false)
	message_list = dock.find_child("Messages", true, false)
	send_button = dock.find_child("Send", true, false)
	stop_button = dock.find_child("Stop", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	progress_status = dock.find_child("AIProgressStatus", true, false)
	var key = dock.get_ai_settings_control().find_child("APIKey", true, false)
	var history_path = "res://.godot/editor/ai_chat_history.json"
	var thumbnails = dock.find_child("ImageAttachments", true, false)
	# History persistence uses a read-only loopback fixture; requirement intake
	# and write authorization are covered by their own native work-order tests.
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	if stage == "corrupt":
		if not _check("暂停本次运行的自动保存" in _chat_text() and agent_tabs.tab_count == 1, "Invalid history was not protected"):
			quit(1)
			return
		chat_input.text = "Must not overwrite corrupt history"
		await create_timer(1.2).timeout
		print("AI_CHAT_HISTORY_CORRUPT_OK")
		quit(0)
		return
	if stage != "seed":
		var restored_model = dock.find_child("CLIModel" if OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli" else "APIModel", true, false)
		if not _check(restored_model.text == "history-model-b", "Restart did not restore Agent B's independent model"):
			quit(1)
			return
		if not _check(key.text.is_empty() and agent_tabs.tab_count == 2 and agent_tabs.current_tab == 1 and chat_input.text == "历史草稿 B" and "HISTORY_B_SEED_OK" in _chat_text() and "HISTORY_A_SEED_OK" not in _chat_text() and not _chat_busy() and not dialog.visible and dock.find_child("Undo", true, false) == null, "Startup did not restore the active Agent safely"):
			quit(1)
			return
		if stage == "backup" and not _check("上一份备份恢复" in _chat_text(), "Corrupt primary did not load its backup"):
			quit(1)
			return
		agent_tabs.current_tab = 0
		message_list = dock.find_child("Messages", true, false)
		if not _check(restored_model.text == "history-model-a", "Restart did not restore Agent A's independent model"):
			quit(1)
			return
		if not _check(chat_input.text == "历史草稿 A [REDACTED]" and thumbnails.find_children("ImageThumbnail", "Button", true, false).size() == 1 and message_list.find_children("ImageThumbnail", "Button", true, false).size() == 1 and "HISTORY_A_SEED_OK" in _chat_text() and "HISTORY_B_SEED_OK" not in _chat_text(), "Agent A text, images or draft was not restored"):
			quit(1)
			return
		if not _check(message_list.find_child("WorkProcess", true, false) == null and not dock.get_node("AIToolDetails").visible, "Completed historical tool details must not be restored"):
			quit(1)
			return
	key.text = "test-secret"
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	key.text_changed.emit(key.text)
	if stage == "seed":
		dock.find_child("APIModel", true, false).text = "mock-model"
	var backend = dock.find_child("AIBackend", true, false)
	var expected_backend = 1 if OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli" else 0
	if stage == "seed":
		backend.select(expected_backend)
		backend.item_selected.emit(expected_backend)
	else:
		if not _check(backend.selected == expected_backend, "Agent backend was not restored"):
			quit(1)
			return
	if expected_backend == 1:
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.find_child("CLIModel", true, false).text = "mock-model"
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	if not await _wait_send_ready():
		quit(1)
		return
	if stage == "seed":
		var image = Image.create(16, 8, false, Image.FORMAT_RGB8)
		image.fill(Color(0.2, 0.4, 0.6))
		image.save_png("res://history_image.png")
		var picker = dock.get_node("AIImagePicker")
		picker.files_selected.emit(PackedStringArray([ProjectSettings.globalize_path("res://history_image.png")]))
		chat_input.text = "case:history_a_seed\n中文对话 test-secret"
		send_button.pressed.emit()
		if not await _wait_idle() or not _check("HISTORY_A_SEED_OK" in _chat_text(), "History seed response missing; status=" + progress_status.text + "; draft=" + chat_input.text + "; chat=" + _chat_text()):
			quit(1)
			return
		chat_input.text = "历史草稿 A test-secret"
		picker.files_selected.emit(PackedStringArray([ProjectSettings.globalize_path("res://history_image.png")]))
		dock.find_child("AddAgent", true, false).pressed.emit()
		message_list = dock.find_child("Messages", true, false)
		if not await _phase("history_b_seed", "HISTORY_B_SEED_OK"):
			quit(1)
			return
		chat_input.text = "历史草稿 B"
		var session_model = dock.find_child("CLIModel" if expected_backend == 1 else "APIModel", true, false)
		session_model.text = "history-model-b"
		session_model.text_changed.emit(session_model.text)
		agent_tabs.current_tab = 0
		session_model.text = "history-model-a"
		session_model.text_changed.emit(session_model.text)
		agent_tabs.current_tab = 1
		if not _check(session_model.text == "history-model-b", "Agent B model was overwritten by Agent A"):
			quit(1)
			return
		agent_tabs.current_tab = 0
		if not _check(session_model.text == "history-model-a", "Agent A model was overwritten by Agent B"):
			quit(1)
			return
		agent_tabs.current_tab = 1
		if not await _wait_saved_history(dock):
			quit(1)
			return
		if not _check(FileAccess.file_exists(history_path), "Autosave did not write history before shutdown"):
			quit(1)
			return
		var disk = FileAccess.get_file_as_string(history_path)
		if not _check("test-secret" not in disk and "api_key" not in disk and "cli_process_id" not in disk and "HISTORY_A_SEED_OK" in disk and "HISTORY_B_SEED_OK" in disk, "Persisted history leaked credentials or lost agents"):
			quit(1)
			return
	else:
		# Restore drafts/images before asking the model to resume the confirmed history.
		chat_input.text = "case:history_a_resume"
		send_button.pressed.emit()
		if not await _wait_idle() or not _check("HISTORY_A_RESUME_OK" in _chat_text(), "Restart lost Agent A model context"):
			quit(1)
			return
		agent_tabs.current_tab = 1
		message_list = dock.find_child("Messages", true, false)
		if not await _phase("history_b_resume", "HISTORY_B_RESUME_OK"):
			quit(1)
			return
		if stage == "restore":
			if not _check(dock.find_child("Clear", true, false) == null, "Removed new-conversation button was restored"):
				quit(1)
				return
			agent_tabs.current_tab = 0
			message_list = dock.find_child("Messages", true, false)
			if not _check("HISTORY_A_SEED_OK" in _chat_text(), "Switching back lost Agent A history"):
				quit(1)
				return
			agent_tabs.current_tab = 1
			message_list = dock.find_child("Messages", true, false)
			if not _check("HISTORY_B_SEED_OK" in _chat_text(), "Switching back lost Agent B history"):
				quit(1)
				return
	print("AI_CHAT_HISTORY_" + stage.to_upper() + "_OK")
	quit(0)

func _check_agent_add_layout(add: Button) -> bool:
	await process_frame
	await process_frame
	if not _check(add.text.is_empty() and add.flat and add.icon == agent_tabs.get_theme_icon("Add", "EditorIcons") and not add.tooltip_text.is_empty(), "New Agent must use the scene-tab plus icon, flat style and tooltip"):
		return false
	if agent_tabs.get_offset_buttons_visible():
		return _check(add.get_parent().name == "AddAgentPlaceholder" and add.position.is_equal_approx(Vector2.ZERO), "Overflow must keep the plus outside the scrolling arrows")
	var last = agent_tabs.get_tab_rect(agent_tabs.tab_count - 1)
	var separation = agent_tabs.get_theme_constant("h_separation")
	var expected_x = last.position.x - add.size.x - separation if agent_tabs.is_layout_rtl() else last.end.x + separation
	return _check(add.get_parent() == agent_tabs and is_equal_approx(add.position.x, expected_x) and is_equal_approx(add.size.y, agent_tabs.size.y), "New Agent plus must follow the last tab and match its height")

func _run_agent_close():
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "Agent close test dock missing"):
		quit(1)
		return
	agent_tabs = dock.find_child("AgentTabs", true, false)
	chat_input = dock.find_child("ChatInput", true, false)
	message_list = dock.find_child("Messages", true, false)
	send_button = dock.find_child("Send", true, false)
	progress_status = dock.find_child("AIProgressStatus", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	var close_dialog = dock.get_node("AgentCloseConfirmation") as ConfirmationDialog
	var add = dock.find_child("AddAgent", true, false) as Button
	if not await _check_agent_add_layout(add):
		quit(1)
		return
	if not _check(agent_tabs.tab_close_display_policy == TabBar.CLOSE_BUTTON_SHOW_ALWAYS, "Every Agent tab must show a native close button"):
		quit(1)
		return
	if OS.get_environment("AI_CHAT_TEST_AGENTS") == "restore":
		if not _check(agent_tabs.tab_count == 1 and chat_input.text.is_empty() and "AGENT_A_SECRET" not in _chat_text() and "AGENT_B_SECRET" not in _chat_text() and not _chat_busy(), "Closed agents or drafts reappeared after restart"):
			quit(1)
			return
		print("AI_CHAT_AGENT_CLOSE_RESTORE_OK")
		quit(0)
		return
	var cli = OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli"
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(1 if cli else 0)
	backend.item_selected.emit(backend.selected)
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	dock.find_child("APIModel", true, false).text = "mock-model"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text_changed.emit("test-secret")
	if cli:
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.find_child("CLIModel", true, false).text = "mock-model"
	if not await _phase("agent_a_seed", "AGENT_A_SECRET"):
		quit(1)
		return
	chat_input.text = "KEEP_A_DRAFT"
	add.pressed.emit()
	message_list = dock.find_child("Messages", true, false)
	if not await _phase("agent_b_seed", "AGENT_B_SECRET"):
		quit(1)
		return
	var b_pid = dock.get_meta("cli_transport").pid if cli else -1
	chat_input.text = "DELETE_B_DRAFT"
	agent_tabs.tab_close_pressed.emit(1)
	if not _check(close_dialog.visible and agent_tabs.tab_count == 2, "Populated Agent closed without confirmation"):
		quit(1)
		return
	close_dialog.hide()
	close_dialog.canceled.emit()
	if not _check(agent_tabs.tab_count == 2 and chat_input.text == "DELETE_B_DRAFT" and "AGENT_B_SECRET" in _chat_text(), "Cancelled close changed the Agent"):
		quit(1)
		return
	add.pressed.emit()
	chat_input.text = "KEEP_C_DRAFT"
	var image = Image.create(8, 8, false, Image.FORMAT_RGB8)
	image.fill(Color(0.2, 0.4, 0.6))
	image.save_png("res://close_image.png")
	dock.get_node("AIImagePicker").files_selected.emit(PackedStringArray([ProjectSettings.globalize_path("res://close_image.png")]))
	agent_tabs.current_tab = 0
	message_list = dock.find_child("Messages", true, false)
	if not _check(chat_input.text == "KEEP_A_DRAFT", "Agent A draft was lost before closing"):
		quit(1)
		return
	chat_input.text = "case:slow"
	send_button.pressed.emit()
	await create_timer(0.2).timeout
	var a_pid = dock.get_meta("cli_transport").pid if cli else -1
	agent_tabs.current_tab = 2
	if not _check(agent_tabs.current_tab == 0 and _chat_busy(), "Busy Agent allowed a switch"):
		quit(1)
		return
	agent_tabs.tab_close_pressed.emit(1)
	close_dialog.confirmed.emit()
	if not _check(agent_tabs.tab_count == 2 and agent_tabs.current_tab == 0 and _chat_busy() and "AGENT_A_SECRET" in _chat_text(), "Closing inactive Agent stopped or replaced the active request"):
		quit(1)
		return
	if cli and not _check(not OS.is_process_running(b_pid) and OS.is_process_running(a_pid), "Closing inactive Agent killed the wrong CLI process"):
		quit(1)
		return
	agent_tabs.tab_close_pressed.emit(0)
	close_dialog.confirmed.emit()
	message_list = dock.find_child("Messages", true, false)
	if not _check(agent_tabs.tab_count == 1 and agent_tabs.current_tab == 0 and not _chat_busy() and chat_input.text == "KEEP_C_DRAFT" and dock.find_child("ImageAttachments", true, false).find_children("ImageThumbnail", "Button", true, false).size() == 1, "Active close did not stop and restore the neighboring Agent and image draft"):
		quit(1)
		return
	if cli and not _check(not OS.is_process_running(a_pid), "Closing active Agent left its CLI running"):
		quit(1)
		return
	await create_timer(1.8).timeout
	if not _check("STALE_RESPONSE" not in _chat_text(), "Closed Agent's delayed answer contaminated its neighbor"):
		quit(1)
		return
	var last_id = agent_tabs.get_tab_metadata(0)
	agent_tabs.tab_close_pressed.emit(0)
	close_dialog.confirmed.emit()
	message_list = dock.find_child("Messages", true, false)
	if not _check(agent_tabs.tab_count == 1 and agent_tabs.get_tab_metadata(0) != last_id and chat_input.text.is_empty() and dock.find_child("ImageAttachments", true, false).get_child_count() == 0 and "AGENT_A_SECRET" not in _chat_text(), "Closing last Agent did not create a clean replacement"):
		quit(1)
		return
	for index in range(15):
		add.pressed.emit()
	if not _check(agent_tabs.tab_count == 16 and add.disabled, "Agent capacity limit was not enforced") or not await _check_agent_add_layout(add):
		quit(1)
		return
	agent_tabs.tab_close_pressed.emit(0)
	if not _check(agent_tabs.tab_count == 15 and not add.disabled and not close_dialog.visible, "Closing an empty Agent did not free capacity immediately"):
		quit(1)
		return
	while agent_tabs.tab_count > 1:
		agent_tabs.tab_close_pressed.emit(0)
	if not await _check_agent_add_layout(add):
		quit(1)
		return
	print("AI_CHAT_AGENT_ADD_LAYOUT_OK")
	if not await _wait_saved_history(dock):
		quit(1)
		return
	var history = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
	var saved_text = JSON.stringify(history)
	if not _check(history.agents.size() == 1 and history.active_agent == agent_tabs.get_tab_metadata(0) and "AGENT_A_SECRET" not in saved_text and "AGENT_B_SECRET" not in saved_text and "KEEP_C_DRAFT" not in saved_text and dock.find_child("AgentArchive", true, false).get_child_count() == 0, "Closed Agent history or archived UI was retained"):
		quit(1)
		return
	print("AI_CHAT_AGENT_CLOSE_OK")
	quit(0)

func _run():
	if not OS.get_environment("AI_CHAT_CLEANUP_STAGE").is_empty():
		await _run_cleanup()
		return
	if not OS.get_environment("AI_CHAT_HISTORY_PERFORMANCE").is_empty():
		await _run_history_performance()
		return
	if not OS.get_environment("AI_CHAT_TEST_AGENTS").is_empty():
		await _run_agent_close()
		return
	if not OS.get_environment("AI_CHAT_HISTORY_STAGE").is_empty():
		await _run_history()
		return
	print("AI_CHAT_TEST_START")
	await create_timer(0.5).timeout
	var dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "Native AI dock was not created"):
		quit(1)
		return
	var main_screen: Control = null
	var ancestor = dock.get_parent()
	while ancestor:
		if ancestor is Control and ancestor.get_theme_type_variation() == "MainScreenContainer":
			main_screen = ancestor
			break
		ancestor = ancestor.get_parent()
	if not _check(dock.get_default_slot() == 11 and main_screen != null, "AI Chat must be a top main-screen tab"):
		quit(1)
		return
	if not await _check_window_fill(root, main_screen):
		quit(1)
		return
	if not await _check_workspace_pages(dock):
		quit(1)
		return
	agent_tabs = dock.find_child("AgentTabs", true, false) as TabBar
	var agent_panel = dock.find_child("AgentTabsPanel", true, false) as PanelContainer
	if not _check(agent_tabs != null and agent_panel != null and agent_panel.is_ancestor_of(agent_tabs), "Agent tabs need a contrasting scene-tab background strip"):
		quit(1)
		return
	if not _check(agent_panel.get_theme_stylebox("panel") == dock.get_theme_stylebox("tabbar_background", "TabContainer") and agent_tabs.get_theme_stylebox("tab_selected") == dock.get_theme_stylebox("tab_selected", "TabBar") and agent_tabs.get_theme_color("font_selected_color") == dock.get_theme_color("accent_color", "Editor"), "Agent tabs must reuse scene-tab styles and the editor accent color"):
		quit(1)
		return
	dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	dock.find_child("APIModel", true, false).text = "mock-model"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	dock.get_ai_settings_control().find_child("APIKey", true, false).text_changed.emit("test-secret")
	var backend = dock.find_child("AIBackend", true, false)
	if OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli":
		backend.select(1)
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.find_child("CLIModel", true, false).text = "mock-model"
	else:
		backend.select(0)
	backend.item_selected.emit(backend.selected)
	tools = dock.get_ai_settings_control().find_child("AllowTools", true, false)
	if not _check(tools.button_pressed, "Local tools must be enabled for the unrestricted development mode"):
		quit(1)
		return
	tools.button_pressed = true
	message_list = dock.find_child("Messages", true, false)
	chat_input = dock.find_child("ChatInput", true, false)
	send_button = dock.find_child("Send", true, false)
	stop_button = dock.find_child("Stop", true, false)
	if not _check(dock.find_child("Clear", true, false) == null and send_button != null and stop_button != null, "Action row must retain Send and Stop without the removed new-conversation button"):
		quit(1)
		return
	if not _check(dock.find_child("Undo", true, false) == null, "Single-file undo must not be present"):
		quit(1)
		return
	progress_status = dock.find_child("AIProgressStatus", true, false)
	dialog = dock.find_child("AIFileApproval", true, false)
	if not OS.get_environment("AI_CHAT_SCHEDULE_STAGE").is_empty():
		quit(0 if await _run_schedules(dock) else 1)
		return
	if not OS.get_environment("AI_CHAT_QUEUE_STAGE").is_empty():
		quit(0 if await _run_message_queue(dock) else 1)
		return
	if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") != "1" and not _check_chat_keys():
		quit(1)
		return
	var settings_page = root.find_child("UnifiedSettings", true, false) as Control
	var categories = settings_page.find_child("UnifiedSettingsCategories", true, false) as TabContainer if settings_page != null else null
	var settings_toggle = dock.find_child("AdvancedToggle", true, false) as Button
	var ai_settings = dock.get_ai_settings_control()
	var environment_settings = dock.get_environment_settings_control()
	if not _check(settings_page != null and categories != null and settings_page.is_ancestor_of(ai_settings) and settings_page.is_ancestor_of(environment_settings) and not settings_page.is_ancestor_of(chat_input) and dock.find_child("ChatSettingsDialog", true, false) == null, "Settings must own the unique forms on its native page without moving the composer"):
		quit(1)
		return
	for section in ["ai", "environment", "ai"]:
		var navigation = settings_toggle if section == "ai" else dock.find_child("EnvironmentSettings", true, false)
		navigation.pressed.emit()
		await process_frame
		if not _check(settings_page.is_visible_in_tree() and categories.current_tab == (0 if section == "ai" else 1) and (ai_settings if section == "ai" else environment_settings).is_visible_in_tree(), "Settings navigation did not reveal the requested category: " + section):
			quit(1)
			return
		dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
		await process_frame
		if not _check(not settings_page.is_visible_in_tree() and not settings_toggle.toggle_mode and chat_input.is_visible_in_tree() and dock.get_ai_settings_control() == ai_settings, "Returning from settings must restore the composer and retain the same form"):
			quit(1)
			return
	var picker = dock.find_child("ModelPicker", true, false)
	await _refresh_models(dock)
	if not await _wait_idle() or not _check("已获取" in dock.find_child("ModelStatus", true, false).text, "Model enumeration failed"):
		quit(1)
		return
	if not _check(picker.get_item_count() >= 2 and picker.get_item_metadata(picker.selected) == "mock-model", "Model list or retained selection is incorrect"):
		quit(1)
		return
	var model_field = dock.find_child("CLIModel", true, false) if backend.selected == 1 else dock.find_child("APIModel", true, false)
	var catalog_size = picker.item_count
	for manual_id in ["a", "ab", "abc"]:
		model_field.text = manual_id
		model_field.text_changed.emit(manual_id)
		if not _check(picker.item_count == catalog_size + 1, "Partial manual IDs accumulated in model list"):
			quit(1)
			return
	model_field.text = "mock-model"
	model_field.text_changed.emit("mock-model")
	if not _check(picker.item_count == catalog_size and picker.get_item_text(picker.selected) == "Mock Model" and "Friendly description" in picker.get_item_tooltip(picker.selected), "Manual editing lost model names or descriptions"):
		quit(1)
		return
	for i in picker.item_count:
		if picker.get_item_metadata(i) == "mock-alternative":
			picker.select(i)
			picker.item_selected.emit(i)
			if not _check((dock.find_child("CLIModel", true, false) if backend.selected == 1 else dock.find_child("APIModel", true, false)).text == "mock-alternative", "Model selection did not update the request configuration"):
				quit(1)
				return
	for i in picker.item_count:
		if picker.get_item_metadata(i) == "mock-model":
			picker.select(i)
			picker.item_selected.emit(i)
	if backend.selected == 0:
		var endpoint = dock.get_ai_settings_control().find_child("APIEndpoint", true, false)
		var configured_url = endpoint.text
		endpoint.text = configured_url.replace("/v1/chat/", "/v1/no-list/chat/")
		await _refresh_models(dock)
		if not await _wait_idle() or not _check("失败" in dock.find_child("ModelStatus", true, false).text and picker.get_item_metadata(picker.selected) == "mock-model" and not "private-model-error" in _chat_text(), "Model enumeration fallback did not preserve selection or leaked diagnostics"):
			quit(1)
			return
		endpoint.text = configured_url
	if OS.get_environment("AI_CHAT_WINDOWS_COMMANDS") == "1":
		dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = true
		for kind in ([] if OS.get_environment("AI_CHAT_WINDOWS_CANCEL_ONLY") == "1" else ["short", "near", "long", "throw", "timeout", "limit", "source"]):
			if not await _phase("win_command_" + kind, kind.to_upper() + "_COMMAND_OK"):
				quit(1)
				return
		chat_input.text = "case:win_command_cancel"
		send_button.pressed.emit()
		var marker = OS.get_environment("AI_CHAT_TEST_EXTERNAL").path_join("工作 ' quoted/started")
		var deadline = Time.get_ticks_msec() + 90000
		while not FileAccess.file_exists(marker) and Time.get_ticks_msec() < deadline:
			await process_frame
		if not _check(FileAccess.file_exists(marker), "Long cancellation command did not start"):
			quit(1)
			return
		var command_pid = FileAccess.get_file_as_string(marker).to_int()
		if not _check(command_pid > 0 and _command_pid_alive(command_pid), "Cancellation marker must identify the running PowerShell process"):
			quit(1)
			return
		stop_button.pressed.emit()
		deadline = Time.get_ticks_msec() + 20000
		while _command_pid_alive(command_pid) and Time.get_ticks_msec() < deadline:
			await create_timer(0.1).timeout
		if not _check(not _command_pid_alive(command_pid), "Stopped command process is still alive"):
			quit(1)
			return
		print("WINDOWS_COMMAND_CANCEL_PROCESS_EXITED")
		if not await _phase("win_command_short", "SHORT_COMMAND_OK") or not _check(not FileAccess.file_exists(marker.get_base_dir().path_join("unexpected")), "Cancelled command continued"):
			quit(1)
			return
		var system_root = OS.get_environment("SystemRoot")
		OS.set_environment("SystemRoot", OS.get_environment("AI_CHAT_TEST_EXTERNAL").path_join("missing-system-root"))
		var failed_safely = await _phase("win_command_failstart", "FAILSTART_COMMAND_OK")
		OS.set_environment("SystemRoot", system_root)
		if not failed_safely:
			quit(1)
			return
		print("WINDOWS_COMMANDS_OK")
		quit(0)
		return
	var filesystem = EditorInterface.get_resource_filesystem()
	while filesystem.is_scanning():
		await process_frame
	EditorInterface.edit_script(load("res://fixture.gd"))
	await process_frame
	var code = _find_code(root)
	if not _check(code != null, "Fixture script editor was not opened"):
		quit(1)
		return
	push_warning("AI_CHAT_LOG_SENTINEL test-secret")
	# File changes apply automatically by default (documented in the dock); this
	# workflow verifies the per-change approval path, so opt out explicitly.
	var auto_apply = dock.get_ai_settings_control().find_child("AutoApplyFileChanges", true, false) as CheckBox
	if not _check(auto_apply != null and auto_apply.button_pressed, "File changes must apply automatically by default"):
		quit(1)
		return
	auto_apply.button_pressed = false
	if not await _phase("workflow", "WORKFLOW_OK"):
		quit(1)
		return
	if not _check(approvals == 3 and FileAccess.get_file_as_string("res://fixture.gd") == AFTER and code.text == AFTER, "Approved write, execution or editor refresh failed: approvals=%d file=%s editor=%s" % [approvals, FileAccess.get_file_as_string("res://fixture.gd") == AFTER, code.text == AFTER]):
		quit(1)
		return
	if not await _check_workflow_session(dock):
		quit(1)
		return
	if not _check(not BEFORE in _chat_text() and not AFTER in _chat_text() and not "AI_CHAT_LOG_SENTINEL" in _chat_text() and not '"exit_code"' in _chat_text(), "Raw source, logs or tool JSON leaked into the chat"):
		quit(1)
		return
	var work = message_list.find_child("WorkProcess", true, false)
	var toggle = message_list.find_child("WorkToggle", true, false)
	var answer = message_list.find_child("AIAnswer", true, false)
	if not _check(work == null and toggle == null and answer.visible and "WORKFLOW_OK" in answer.get_parsed_text(), "Completed work process must be deleted while retaining the final answer"):
		quit(1)
		return
	var screenshot = OS.get_environment("AI_CHAT_SCREENSHOT")
	if not screenshot.is_empty():
		EditorInterface.set_main_screen_editor("AI Chat")
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		if not _check(root.get_texture().get_image().save_png(screenshot) == OK, "Could not save rendered chat screenshot"):
			quit(1)
			return
	if not _check(message_list.find_child("UserMessage", true, false) != null and message_list.find_child("AIReply", true, false) != null, "User and AI message cards are missing"):
		quit(1)
		return
	var details = dock.get_node("AIToolDetails")
	if not _check(not details.visible and details.get_child(0).text.is_empty(), "Completed tool preview retained raw source"):
		quit(1)
		return
	if backend.selected == 1:
		var sent = dock.get_meta("cli_transport")
		var received = dock.get_meta("cli_response_transport")
		if not _check(sent.mode == "incremental" and sent.skipped_messages > 0 and received.mode == "incremental", "Actual CLI continuation did not use incremental transport"):
			quit(1)
			return
	await create_timer(0.8).timeout
	if not await _phase("incremental_next", "INCREMENTAL_NEXT_OK"):
		quit(1)
		return
	if backend.selected == 1:
		var old_pid = dock.get_meta("cli_transport").pid
		model_field.text = "mock-alternative"
		model_field.text_changed.emit("mock-alternative")
		var old_session = dock.get_meta("cli_response_transport").session_id
		if not await _phase("model_switch", "MODEL_SWITCH_OK") or not _check(dock.get_meta("cli_transport").mode == "incremental" and dock.get_meta("cli_transport").pid == old_pid and dock.get_meta("cli_response_transport").session_id == old_session, "Model switch restarted the native conversation"):
			quit(1)
			return
		model_field.text = "mock-model"
		model_field.text_changed.emit("mock-model")
		if not await _phase("model_restore", "MODEL_RESTORE_OK"):
			quit(1)
			return
	var old_chat = _chat_text()
	var query_endpoint = dock.get_ai_settings_control().find_child("APIEndpoint", true, false)
	var previous_endpoint = query_endpoint.text
	if backend.selected == 0:
		query_endpoint.text = previous_endpoint.replace("/v1/chat/", "/v1/slow-models/chat/")
	await _refresh_models(dock, false)
	for field in ["APIEndpoint", "APIKey", "APIModel", "CLINode", "CLIBridge", "CLIEntry", "CLIModel"]:
		if not _check(_chat_setting(dock, field).editable, "Catalog blocked independent connection field: " + field):
			quit(1)
			return
	if not _check(message_list.find_child("WorkProcess", true, false) == null, "Model refresh altered a finished work process"):
		quit(1)
		return
	await create_timer(0.1).timeout
	dock.cancel_model_catalog()
	if not _check(_chat_text() == old_chat and message_list.find_child("WorkProcess", true, false) == null and query_endpoint.editable and model_field.editable, "Canceling model refresh altered chat or did not unlock configuration"):
		quit(1)
		return
	query_endpoint.text = previous_endpoint
	await _refresh_models(dock)
	if not await _wait_idle() or not _check(message_list.find_child("WorkProcess", true, false) == null, "Completed model refresh changed historical work state"):
		quit(1)
		return
	await create_timer(1.6).timeout
	for i in picker.item_count:
		if not _check(picker.get_item_metadata(i) != "stale-model", "Cancelled model response overwrote the new model list"):
			quit(1)
			return
	if not await _phase("context_kept", "CONTEXT_KEPT_OK"):
		quit(1)
		return
	_last_snapshot_button().pressed.emit()
	if not await _wait_idle() or not _check(FileAccess.get_file_as_string("res://fixture.gd") == BEFORE and code.text == BEFORE, "Undo did not restore disk and editor content"):
		quit(1)
		return
	if not _check(not auto_apply.button_pressed, "Approval mode for file changes was not kept"):
		quit(1)
		return
	auto_apply.button_pressed = true
	code.set_caret_line(code.get_line_count() - 1)
	code.insert_text_at_caret("\n# UNSAVED_TEST\n")
	await process_frame
	var previous_approvals = approvals
	if not await _phase("unsaved", "UNSAVED_OK") or not _check(approvals == previous_approvals and "UNSAVED_TEST" in code.text and FileAccess.get_file_as_string("res://fixture.gd") == BEFORE, "Unsaved editor content was overwritten"):
		quit(1)
		return
	code.undo()
	if not await _phase("auto_write", "AUTO_WRITE_OK") or not _check(approvals == previous_approvals and FileAccess.get_file_as_string("res://fixture.gd") == AFTER and code.text == AFTER, "Automatic HTTP write showed approval or did not refresh disk/editor"):
		quit(1)
		return
	_last_snapshot_button().pressed.emit()
	if not await _wait_idle() or not _check(approvals == previous_approvals + 1 and FileAccess.get_file_as_string("res://fixture.gd") == BEFORE and code.text == BEFORE, "Automatic HTTP write undo did not confirm or restore the file"):
		quit(1)
		return
	auto_apply.button_pressed = false
	var auto_execute = dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false) as CheckBox
	if not _check(auto_execute != null and not auto_execute.button_pressed, "Automatic execution must require initial opt-in"):
		quit(1)
		return
	auto_execute.button_pressed = true
	previous_approvals = approvals
	if not await _phase("auto_execution", "AUTO_EXECUTION_OK") or not _check(approvals == previous_approvals, "Automatic scripts or command still showed approval"):
		quit(1)
		return
	auto_execute.button_pressed = false
	if not await _phase("reject", "REJECT_OK", true) or not _check(FileAccess.get_file_as_string("res://fixture.gd") == BEFORE, "Rejected change modified the file"):
		quit(1)
		return
	if not await _phase("traversal", "TRAVERSAL_OK"):
		quit(1)
		return
	chat_input.text = "case:slow"
	send_button.pressed.emit()
	await create_timer(0.6).timeout
	stop_button.pressed.emit()
	if not await _phase("after_cancel", "AFTER_CANCEL_OK"):
		quit(1)
		return
	await create_timer(1.6).timeout
	if not _check(not "STALE_RESPONSE" in _chat_text() and not "test-secret" in _chat_text(), "Cancelled response or API key leaked into chat"):
		quit(1)
		return
	if not await _phase("expanded", "EXPANDED_OK"):
		quit(1)
		return
	var external_file = OS.get_environment("AI_CHAT_TEST_EXTERNAL").path_join("sample.cpp")
	_last_snapshot_button().pressed.emit()
	if not await _wait_idle() or not _check(FileAccess.get_file_as_string(external_file) == "int sample() { return 0; }\n", "External C++ undo failed"):
		quit(1)
		return
	if not screenshot.is_empty():
		EditorInterface.set_main_screen_editor("AI Chat")
		chat_input.text = "case:scroll"
		send_button.pressed.emit()
		await create_timer(0.25).timeout
		var chat_scroll = message_list.get_parent() as ScrollContainer
		if not _check(chat_scroll.get_v_scroll_bar().max_value > chat_scroll.get_v_scroll_bar().page + 12, "Scrollable chat fixture was not rendered"):
			quit(1)
			return
		chat_scroll.set_v_scroll(0)
		if not await _wait_idle():
			quit(1)
			return
		await create_timer(0.2).timeout
		if not _check(chat_scroll.get_v_scroll() == 0 and "SCROLL_OK" in _chat_text(), "Background answer pulled the user away from older messages"):
			quit(1)
			return
	chat_input.text = "case:malformed"
	send_button.pressed.emit()
	if not await _wait_idle():
		quit(1)
		return
	if not _check(not _chat_busy(), "Malformed response left the UI busy"):
		quit(1)
		return
	var approval_count = approvals
	var chat_before_refresh = _chat_text()
	var details_before_refresh = dock.get_node("AIToolDetails").visible
	await _refresh_models(dock, false)
	dock.cancel_model_catalog()
	if not _check(dock.get_node("AIToolDetails").visible == details_before_refresh and progress_status.text.begins_with("就绪") and approvals == approval_count and _chat_text() == chat_before_refresh, "Model refresh cancellation lost details, conversation or approval state"):
		quit(1)
		return
	dock.get_node("AIToolDetails").hide()
	if not await _phase("after_refresh", "AFTER_REFRESH_OK"):
		quit(1)
		return
	if not await _phase("budget", "BUDGET_OK"):
		quit(1)
		return
	var replies = message_list.find_children("AIReply*", "VBoxContainer", true, false)
	if not _check(tools.button_pressed and replies[-1].find_child("WorkProcess", true, false) == null, "Completed budget turn retained intermediate tool records"):
		quit(1)
		return
	chat_input.text = "case:budget_violation"
	send_button.pressed.emit()
	if not await _wait_idle() or not _check("UNLIMITED_VIOLATION_OK" in _chat_text(), "Tools were unavailable after the fifth round"):
		quit(1)
		return
	replies = message_list.find_children("AIReply*", "VBoxContainer", true, false)
	if not _check(replies[-1].find_child("WorkToggle", true, false) == null, "Completed unlimited turn retained work UI"):
		quit(1)
		return
	tools.button_pressed = false
	if not await _phase("permission_off", "PERMISSION_OFF_OK"):
		quit(1)
		return
	replies = message_list.find_children("AIReply*", "VBoxContainer", true, false)
	if not _check(not tools.button_pressed and "PERMISSION_OFF_OK" in _chat_text(), "Unchecked permission was not explained separately"):
		quit(1)
		return
	tools.button_pressed = true
	if not await _phase("budget_resume", "BUDGET_RESUME_OK") or not _check(approvals == approval_count, "Read-only budget test unexpectedly required write approval"):
		quit(1)
		return
	if not await _phase("large_context", "LARGE_CONTEXT_OK"):
		quit(1)
		return
	var stats = dock.get_meta("context_stats")
	if not _check(stats.duplicates >= 1 and stats.shortened >= 2 and stats.context_bytes <= 384 * 1024, "Large reads were not compacted within the byte budget"):
		quit(1)
		return
	if not await _phase("range_context", "RANGE_CONTEXT_OK") or not await _phase("long_structured_context", "LONG_STRUCTURED_CONTEXT_OK") or not await _phase("range_invalid", "RANGE_INVALID_OK") or not await _phase("large_next", "LARGE_NEXT_OK"):
		quit(1)
		return
	for i in range(14):
		print("CONTEXT_STRESS_SEND ", i)
		chat_input.text = "case:history_fill\nHISTORY_MARKER_%d\n" % i + "对话记录".repeat(5500)
		send_button.pressed.emit()
		if not await _wait_idle():
			quit(1)
			return
		print("CONTEXT_STRESS_DONE ", i)
	stats = dock.get_meta("context_stats")
	# The compaction notice lives in the turn's work panel, which completed turns
	# drop by design (question + final answer only), so verify via the stats.
	if not _check(stats.dropped_turns > 0 and stats.context_bytes <= 384 * 1024 and "HISTORY_MARKER_0" in _chat_text() and "HISTORY_MARKER_13" in _chat_text(), "Old turns were not compacted transparently while preserving full UI history: stats=%s" % [stats]):
		quit(1)
		return
	var agents = dock.find_child("AgentTabs", true, false) as TabBar
	if not _check(agents != null and agents.tab_count == 1 and agents.get_tab_title(0) == "Agent 1" and agents.clip_tabs and agents.scrolling_enabled, "Scrollable agent tabs were not created") or not await _phase("agent_a_seed", "AGENT_A_SECRET"):
		quit(1)
		return
	chat_input.text = "AGENT_A_DRAFT"
	dock.find_child("AddAgent", true, false).pressed.emit()
	message_list = dock.find_child("Messages", true, false)
	if not _check(agents.tab_count == 2 and agents.get_tab_title(1) == "Agent 2" and agents.current_tab == 1 and chat_input.text.is_empty() and not "AGENT_A_SECRET" in _chat_text(), "New agent reused the previous UI or draft") or not await _phase("agent_b_seed", "AGENT_B_SECRET"):
		quit(1)
		return
	agents.current_tab = 0
	message_list = dock.find_child("Messages", true, false)
	if not _check(chat_input.text == "AGENT_A_DRAFT" and not "AGENT_B_SECRET" in _chat_text(), "Agent A UI or draft was not restored") or not await _phase("agent_a_resume", "AGENT_A_RESUME_OK"):
		quit(1)
		return
	agents.current_tab = 1
	message_list = dock.find_child("Messages", true, false)
	if not _check("AGENT_B_SECRET" in _chat_text(), "Switching agents lost agent B UI") or not await _phase("agent_b_resume", "AGENT_B_RESUME_OK"):
		quit(1)
		return
	if not await _check_agent_sessions(dock):
		quit(1)
		return
	print("AI_CHAT_INTEGRATION_OK approvals=", approvals, " context_stats=", stats)
	quit(0)
