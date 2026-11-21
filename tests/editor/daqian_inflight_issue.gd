@tool
extends SceneTree

const URL := "https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1755"
const REQUEST := "original-i13"
var failures := PackedStringArray()

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> void:
	if not ok:
		push_error(message)
		failures.append(message)

func button(parent: Node, title: String) -> Button:
	for node in parent.find_children("*", "Button", true, false):
		if node.text == title and node.is_visible_in_tree():
			return node
	return null

func open_sidebar() -> bool:
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	if not palette.visible:
		return false
	var search: LineEdit = palette.find_children("*", "LineEdit", true, false)[0]
	var results: Tree = palette.find_children("*", "Tree", true, false)[0]
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not results.get_selected() or results.get_selected().get_metadata(0) != search.text:
		return false
	results.item_activated.emit()
	await process_frame
	return true

func verify_conversation_detail(panel) -> void:
	var deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < deadline:
		if is_instance_valid(panel.inflight_dialog) and not panel.inflight_dialog.is_queued_for_deletion() and panel.inflight_dialog.visible:
			var dialog: AcceptDialog = panel.inflight_dialog
			var details: TextEdit = dialog.find_children("*", "TextEdit", true, false)[0]
			if "Original body." in details.text and URL in details.text and "原单状态：open · in-review" in details.text and "原会话" in details.text:
				dialog.confirmed.emit()
				await process_frame
				return
		await create_timer(0.05).timeout
	check(false, "Conversation control did not resolve its own original")

func run() -> void:
	await create_timer(1).timeout
	var settings := EditorInterface.get_editor_settings()
	var workspace := OS.get_environment("DAQIAN_TEST_REPO")
	settings.set_setting("gonggong/workspace", workspace)
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	EditorInterface.set_main_screen_editor("天枢")
	var panel = root.find_child("DaqianWorkspace", true, false)
	var chat = root.find_child("AI Chat", true, false)
	await panel.refresh()
	if panel.actor.get("user_id") != "42":
		push_error("No verified board account: " + panel.notice.text)
		quit(1)
		return
	if OS.get_environment("DAQIAN_TEST_RESTART") == "0":
		var link := {"url":URL, "number":1755, "request":REQUEST, "status":"in-progress"}
		panel.saved.linked = {"draft_prior":link, "draft_stale":link.merged({"request":"replaced-request"}, true)}
		panel.saved.direct_started = {URL:REQUEST}
		var entry := {"source":"draft_prior", "issue_number":"1755", "request_id":REQUEST}
		var scope := (workspace + "|123|42").sha256_text()
		settings.set_project_metadata("daqian", "bindings", {"legacy":entry,
				"scoped":entry.merged({"scope":scope}, true), "foreign":entry.merged({"scope":"other-user"}, true),
				"unverified":entry.merged({"source":"draft_no_link"}, true)})
		panel._save()
		var error: String = chat.open_daqian_chat(URL, 1755, REQUEST, "", false, {}, false)
		if not error.is_empty():
			push_error(error)
			quit(1)
			return
		chat.find_child("ChatInput", true, false).text = "original private draft"
		await create_timer(2.0).timeout
		print("DAQIAN_INFLIGHT_SAVED")
		quit()
		return
	var before: Dictionary = settings.get_project_metadata("daqian", "bindings", {}).duplicate(true)
	var links: Dictionary = panel.saved.get("linked", {}).duplicate(true)
	var starts: Dictionary = panel.saved.get("direct_started", {}).duplicate(true)
	var advanced := button(panel, "筛选与跟进 ▾")
	if not advanced:
		push_error("Missing board filter controls")
		quit(1)
		return
	advanced.pressed.emit()
	var entry_button := button(panel, "在途工单")
	if not entry_button:
		push_error("Missing inflight entry")
		quit(1)
		return
	entry_button.pressed.emit()
	var deadline := Time.get_ticks_msec() + 30000
	while not is_instance_valid(panel.inflight_dialog) and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	var dialog: AcceptDialog = panel.inflight_dialog
	if not dialog or not dialog.visible:
		push_error("No inflight picker: " + panel.notice.text)
		quit(1)
		return
	var picker: OptionButton = dialog.find_children("*", "OptionButton", true, false)[0]
	var details: TextEdit = dialog.find_children("*", "TextEdit", true, false)[0]
	var read := button(dialog, "读取原单详情")
	var labels := PackedStringArray()
	for index in picker.item_count:
		labels.append(picker.get_item_text(index))
	check("#1755 · 原会话 scoped" in labels, "Missing current-scope conversation")
	check("#1755 · 原会话 foreign" not in labels and "#1755 · 原会话 unverified" not in labels, "Cross-account or unverified legacy conversation")
	for origin in ["原会话 legacy", "开工记录", "原记录 draft_stale"]:
		var index := labels.find("#1755 · " + str(origin))
		if index < 0:
			failures.append("Missing record " + str(origin))
			continue
		picker.select(index)
		picker.item_selected.emit(index)
		check(URL in details.text and origin in details.text and not details.editable, "Missing original identity")
		if origin == "原会话 legacy":
			check("记录状态：in-progress" in details.text, "Lost recorded status")
		read.pressed.emit()
		deadline = Time.get_ticks_msec() + 30000
		while read.disabled and Time.get_ticks_msec() < deadline:
			await create_timer(0.05).timeout
		if origin == "原记录 draft_stale":
			check("无法读取" in details.text and "Original body." not in details.text, "Rebound stale request")
		else:
			check("原单状态：open · in-review" in details.text and "Original body." in details.text and URL in details.text, "Missing live original: " + details.text)
	dialog.confirmed.emit()
	await process_frame
	var error: String = chat.open_daqian_chat(URL, 1755, REQUEST, "", false, {}, false, "", true)
	if not error.is_empty():
		push_error("No original conversation after editor restart: " + error)
		quit(1)
		return
	var draft: TextEdit = chat.find_child("ChatInput", true, false)
	var tabs: TabBar = chat.find_child("AgentTabs", true, false)
	var tab_count := tabs.tab_count
	var tab_index := tabs.current_tab
	check(draft.text == "original private draft", "Failed to restore original draft")
	EditorInterface.set_main_screen_editor("2D")
	if not await open_sidebar():
		push_error("Could not open sidebar")
		quit(1)
		return
	var sidebar := root.find_child("AIWorkbenchSidebar", true, false)
	var sidebar_link := button(sidebar, "查看关联工单")
	if not sidebar_link:
		push_error("Sidebar missing original action")
		quit(1)
		return
	sidebar_link.pressed.emit()
	await verify_conversation_detail(panel)
	sidebar.find_child("ExpandWorkbench", true, false).pressed.emit()
	await process_frame
	var expanded_link := button(chat, "查看关联工单")
	if not expanded_link or expanded_link != sidebar_link:
		push_error("Expanded original conversation lost shared action")
		quit(1)
		return
	expanded_link.pressed.emit()
	await verify_conversation_detail(panel)
	check(tab_count > 1, "Missing separate session for inactive tab lookup")
	var other_tab := 1 if tab_index == 0 else 0
	tabs.current_tab = other_tab
	await process_frame
	var other_draft := draft.text
	tabs.tab_rmb_clicked.emit(tab_index)
	var menu: PopupMenu = chat.find_child("AgentContextMenu", true, false)
	check(menu.visible and menu.get_item_text(menu.get_item_index(1)) == "查看关联工单", "Original action missing from tab menu")
	menu.hide()
	menu.id_pressed.emit(1)
	await verify_conversation_detail(panel)
	check(tabs.tab_count == tab_count and tabs.current_tab == other_tab and draft.text == other_draft, "Reading an inactive tab changed the selected session")
	tabs.current_tab = tab_index
	check(draft.text == "original private draft", "Lost original private draft")
	check(before == settings.get_project_metadata("daqian", "bindings", {}) and links == panel.saved.linked and starts == panel.saved.direct_started, "Opening original mutated bindings or starts")
	check(panel.current.is_empty() and panel.workflow_controller.execution_turns.is_empty(), "Reading an issue started a turn")
	if failures.is_empty():
		print("DAQIAN_INFLIGHT_OK")
	else:
		push_error(str(failures))
	quit(0 if failures.is_empty() else 1)
