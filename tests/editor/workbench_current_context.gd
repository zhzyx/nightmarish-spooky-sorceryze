extends SceneTree

const LocalModelFixture = preload("res://local_model_fixture.gd")
var checks: Array[String] = []

func _initialize() -> void:
	run.call_deferred()

func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Current editor context: " + description)
		quit(1)
		return false
	checks.append(description)
	print("CONTEXT_CHECK ", checks.size(), ": ", description)
	return true

func wait_until(predicate: Callable) -> bool:
	for attempt in 600:
		if predicate.call(): return true
		await create_timer(0.025).timeout
	return false

func select_node(node: Node) -> void:
	EditorInterface.get_selection().clear()
	if node:
		EditorInterface.get_selection().add_node(node)

func open_chat() -> void:
	var button: Button = root.find_child("OpenAIWorkbench", true, false)
	button.button_down.emit()
	button.pressed.emit()

func saved_users() -> Array:
	var path := "res://.godot/editor/ai_chat_history.json"
	if not FileAccess.file_exists(path): return []
	var result := []
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	for agent in data.get("agents", []):
		for message in agent.get("transcript", []):
			if message.get("role") == "user": result.append(message)
	return result

func run() -> void:
	root.size = Vector2i(1500, 950)
	await create_timer(0.5).timeout
	var configured := await LocalModelFixture.configure(self)
	if not check(not configured.is_empty(), "configure only the isolated editor's local API controls"): return
	var dock: Node = configured.dock
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	var input: TextEdit = dock.find_child("ChatInput", true, false)
	var sidebar: EditorDock = root.find_child("AIWorkbenchSidebar", true, false)
	var tabs: TabContainer = dock.get_parent()
	EditorInterface.open_scene_from_path("res://fixture.tscn")
	await process_frame
	var scene := EditorInterface.get_edited_scene_root()
	var first := Node2D.new()
	first.name = "ContextFirst"
	scene.add_child(first)
	var second := Node2D.new()
	second.name = "ContextSecond"
	scene.add_child(second)
	tabs.current_tab = tabs.get_tab_idx_from_control(root.find_child("2D", true, false))
	await process_frame
	select_node(first)
	open_chat()
	var current: Label = sidebar.find_child("WorkbenchCurrentContext", true, false)
	if not check(current != null and current.text.contains("ContextFirst"), "opening the sidebar displays the selected node immediately before the first timer tick"): return
	EditorInterface.select_file("res://linked.gd")
	sidebar.find_child("WorkbenchResourceSelection", true, false).get_popup().id_pressed.emit(1)
	var retained: Button = sidebar.find_child("WorkbenchReference", true, false)
	if not check(retained.visible and retained.text.contains("linked.gd"), "explicit resource attachment remains a separate retained reference"): return
	var manual := retained.text
	var pixels := Image.create_empty(2, 2, false, Image.FORMAT_RGBA8)
	pixels.fill(Color.BLUE)
	pixels.save_png("res://context-image.png")
	dock.find_child("AIImagePicker", true, false).files_selected.emit(PackedStringArray([ProjectSettings.globalize_path("res://context-image.png")]))
	var draft := input.text
	var images: Array = dock.get_ai_session_snapshot().draft_images.duplicate(true)
	select_node(second)
	if not check(await wait_until(func(): return current.text.contains("ContextSecond")), "real editor selection changes replace only the current context slot"): return
	if not check(retained.text == manual and input.text == draft and dock.get_ai_session_snapshot().draft_images == images and images.size() == 1, "refreshing current context preserves manual references, draft text and image attachments"): return
	select_node(null)
	var cleared := await wait_until(func(): return current.text.contains("未选中内容"))
	if not cleared: print("CURRENT_CLEAR_DIAGNOSTIC ", current.text)
	if not check(cleared, "clearing the selection clears the automatic slot instead of retaining an old node"): return
	select_node(second)
	if not check(await wait_until(func(): return current.text.contains("ContextSecond")), "the automatic context follows a new selection after clearing"): return
	var host: Node = root.find_child("TianxuanModelHost", true, false)
	EditorInterface.inspect_object(second)
	var inspector_focus := LineEdit.new()
	EditorInterface.get_inspector().add_child(inspector_focus)
	inspector_focus.grab_focus()
	var inspected: Dictionary = host.editor_context(true)
	if not check(inspected.get("references", []).size() == 1 and str(inspected.text).contains("ContextSecond"), "focusing the native inspector for a scene node retains that node's bounded context"): return
	inspector_focus.free()
	open_chat()
	# Each slot may fit independently while their union exceeds the shared limit.
	var extra_nodes: Array[Node] = []
	for index in 15:
		var extra := Node2D.new()
		extra.name = "Extra%d" % index
		scene.add_child(extra)
		extra_nodes.append(extra)
		EditorInterface.get_selection().add_node(extra)
	await create_timer(0.6).timeout
	input.text = "OVER_LIMIT_MUST_NOT_SEND"
	sidebar.find_child("Send", true, false).pressed.emit()
	if not check(input.text == "OVER_LIMIT_MUST_NOT_SEND" and current.text.contains("合计超过 16"), "manual plus current references exceeding the limit reject the whole send without dropping either slot"): return
	select_node(second)
	for extra in extra_nodes: extra.free()
	if not check(await wait_until(func(): return current.text.contains("ContextSecond")), "shrinking the selection restores an explicitly displayed valid context"): return
	# Same locator and transform must not hide a replaced live node between preview and send.
	input.text = "REPLACED_NODE_MUST_NOT_SEND"
	select_node(null)
	second.free()
	second = Node2D.new()
	second.name = "ContextSecond"
	scene.add_child(second)
	select_node(second)
	sidebar.find_child("Send", true, false).pressed.emit()
	if not check(input.text == "REPLACED_NODE_MUST_NOT_SEND" and current.text.contains("已变化"), "send revalidates the displayed live identity and rejects a same-name replacement without consuming the draft"): return
	if not check(await wait_until(func(): return current.text.contains("ContextSecond")), "the replacement becomes visible as a new current snapshot"): return
	for remove in sidebar.find_child("ImageAttachments", true, false).find_children("RemoveImage", "Button", true, false):
		remove.pressed.emit()
	input.text = "CURRENT_FIRST LAYOUT_DELAYED_REPLY"
	sidebar.find_child("Send", true, false).pressed.emit()
	if not check(await wait_until(func(): return input.text.is_empty() and not sidebar.find_child("Stop", true, false).disabled), "the explicit ordinary chat send reaches the real local HTTP fixture"): return
	input.text = "CURRENT_QUEUED"
	sidebar.find_child("Send", true, false).pressed.emit()
	if not check(input.text.is_empty(), "queuing another message freezes the displayed context independently"): return
	select_node(first)
	await create_timer(0.7).timeout
	if not check(current.text.contains("ContextSecond"), "busy request context stays fixed while the original editor selection changes"): return
	if not check(await wait_until(func(): return sidebar.find_child("Stop", true, false).disabled and saved_users().size() >= 2), "both actual local replies finish and their frozen messages persist"): return
	var users := saved_users()
	for index in 2:
		if not check(str(users[index].content).contains("ContextSecond") and not str(users[index].content).contains("ContextFirst"), "sent and queued messages retain their original selected node after later selection changes"): return
	if not check(users[0].editor_references.size() == 2 and users[0].editor_references[0].object_id == "res://linked.gd" and users[1].editor_references.size() == 1, "combined references preserve manual order and consume manual attachments only on explicit send"): return
	sidebar.close()
	# Tianxuan uses the same bounded provider but owns its conversation slot and module scope.
	var base := EditorInterface.get_base_control()
	var view: Control = base.find_child("TianxuanSidebarView", true, false)
	var controller: Node = view.get_meta("controller")
	var session: Node = controller.session
	if not check(await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace"), "authenticate only the private Tianxuan fixture identity"): return
	base.find_child("TianxuanWorkspaceView", true, false).find_child("OpenTianxuanSidebar", true, false).pressed.emit()
	view._navigate("home", "")
	if not check(await wait_until(func(): return not controller.chat_busy()), "the native conversation finishes its isolated initial reads"): return
	var home: Control = view._page_instances.home
	# This is the private fixture's own token, never an installed editor credential.
	var fixture_token: String = session._token
	var token_script := GDScript.new()
	token_script.source_code = "extends Node\n# fixture identity " + fixture_token + "\n"
	if not check(ResourceSaver.save(token_script, "res://identity-fixture.gd", ResourceSaver.FLAG_CHANGE_PATH) == OK, "create only a private source fixture containing its own identity token"): return
	token_script = load("res://identity-fixture.gd")
	if not check(token_script.resource_path == "res://identity-fixture.gd", "select the saved script resource rather than its unsaved in-memory source"): return
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(token_script)
	await process_frame
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	code.grab_focus()
	code.select(1, 0, 1, code.get_line(1).length())
	controller.editor_context.capture_current_context()
	var redacted: Dictionary = controller.editor_context.current_context()
	var safe_context: Dictionary = controller.editor_context.message_context("")
	if not check(not JSON.stringify(redacted).contains(fixture_token) and str(redacted.get("text", "")).contains("[REDACTED]") and safe_context.valid and not str(safe_context.text).contains(fixture_token), "Tianxuan redacts its own identity before displaying, freezing or revalidating selected source text"): return
	tabs.current_tab = tabs.get_tab_idx_from_control(root.find_child("2D", true, false))
	await process_frame
	select_node(first)
	base.find_child("TianxuanWorkspaceView", true, false).find_child("OpenTianxuanSidebar", true, false).pressed.emit()
	await process_frame
	if not check(home.is_visible_in_tree(), "reopen the actual Tianxuan sidebar after changing the original editor surface"): return
	controller.editor_context.capture_current_context()
	if not check(home.find_child("TianxuanCurrentContext", true, false).text.contains("ContextFirst") and controller.editor_module.is_empty(), "Tianxuan shows the current editor selection without assigning a business module"): return
	controller.editor_context.attach_nodes()
	var manual_items: Array = controller.editor_context.attachments()
	select_node(second)
	var followed := await wait_until(func(): return controller.editor_context.current_context_status().contains("ContextSecond"))
	if not followed: print("TIANXUAN_FOLLOW_DIAGNOSTIC ", JSON.stringify({"status": controller.editor_context.current_context_status(), "busy": controller.chat_busy(), "visible": home.is_visible_in_tree(), "selection": EditorInterface.get_selection().get_selected_nodes().map(func(item): return str(item.name))}))
	if not check(followed, "Tianxuan independently follows the new selected node"): return
	if not check(controller.editor_context.attachments() == manual_items and not controller.editor_context.message_context("").valid and controller.editor_module.is_empty(), "automatic context never replaces manual attachments or bypasses their explicit module requirement"): return
	controller.editor_module = OS.get_environment("TX_MODULE")
	var prepared: Dictionary = controller.editor_context.message_context(controller.editor_module)
	if not check(prepared.valid and str(prepared.text).contains("ContextFirst") and str(prepared.text).contains("ContextSecond") and prepared.references.references.size() == 1, "manual module-scoped references and the current consultation snapshot remain distinguishable"): return
	home.composer.text = "UNINITIALIZED_MUST_NOT_SEND"
	controller.editor_context._current_contexts.clear()
	home.send.pressed.emit()
	if not check(home.composer.text == "UNINITIALIZED_MUST_NOT_SEND" and controller.editor_context.current_context_status().contains("再次发送"), "an uninitialized conversation slot first displays context and preserves the unsent draft"): return
	prepared = controller.editor_context.message_context(controller.editor_module)
	if not check(prepared.valid and not controller.editor_context.current_context_status().contains("再次发送"), "successful revalidation clears the transient initialization prompt"): return
	home.composer.text = "TIANXUAN_CURRENT_FROZEN"
	home.send.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("turns", []).size() == 1 and controller.local_chat.syncing.is_empty()), "Tianxuan sends its current snapshot through the actual local model and synchronizes the completed turn"): return
	var turn: Dictionary = controller.conversation().turns[0]
	if not check(str(turn.content).contains("ContextSecond") and turn.context_snapshot.references[0].object_id.ends_with("#ContextFirst") and turn.reply_source == "editor-local", "the synchronized turn freezes shown current content while retaining explicit module provenance"): return
	if not check(controller.editor_context.attachments() == manual_items, "starting the first conversation preserves its manual attachment draft under the new conversation key"): return
	var before: Dictionary = controller.editor_context.current_context().duplicate(true)
	select_node(first)
	controller.select_conversation("")
	controller.editor_context.capture_current_context()
	if not check(controller.editor_context.attachments().is_empty() and controller.editor_context.current_context_status().contains("ContextFirst") and controller.editor_context.current_context() != before, "another conversation captures its own current selection without inheriting the previous attachment slot"): return
	# Equal length and coarse filesystem timestamp cannot establish a revision.
	var original := FileAccess.get_file_as_string("res://fixture.tscn")
	var rewritten := original.replace("Vector2(4, 7)", "Vector2(8, 7)")
	var same_stamp := false
	for attempt in 3:
		var file := FileAccess.open("res://fixture.tscn", FileAccess.WRITE)
		file.store_string(original)
		file.close()
		host.editor_context(true)
		controller.editor_context.capture_current_context()
		var stamp := FileAccess.get_modified_time("res://fixture.tscn")
		file = FileAccess.open("res://fixture.tscn", FileAccess.WRITE)
		file.store_string(rewritten)
		file.close()
		same_stamp = FileAccess.get_modified_time("res://fixture.tscn") == stamp
		if same_stamp: break
	if not check(same_stamp and rewritten.length() == original.length() and rewritten != original, "the isolated source rewrite has equal size and the same filesystem timestamp"): return
	home.composer.text = "SAME_SECOND_MUST_NOT_SEND"
	home.send.pressed.emit()
	if not check(home.composer.text == "SAME_SECOND_MUST_NOT_SEND" and controller.editor_context.current_context_status().contains("已变化"), "send hashes the shown file revision again and refuses a same-second equal-size rewrite without consuming text"): return
	session.reset()
	if not check(controller.editor_context.current_context().is_empty() and controller.editor_context.attachments().is_empty(), "identity reset clears live context without restoring another account's references"): return
	print(JSON.stringify({"passed": true, "checks": checks, "frozen_current": before.source}))
	quit(0)
