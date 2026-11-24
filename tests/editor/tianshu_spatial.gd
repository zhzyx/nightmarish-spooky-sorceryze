@tool
extends SceneTree

class ApprovalChat extends Control:
	var confirmed := []
	func confirm_daqian_issue_approval(url: String, token: String) -> bool:
		confirmed.append([url, token])
		return true
	func render_daqian_markdown(view: RichTextLabel, markdown: String) -> void: view.add_text(markdown)

class AccessFixture extends VBoxContainer:
	var actor := {"repo":"fixture/project", "user_id":"42", "repo_id":"1"}
	var board := {"issues":[]}
	var offline := false
	var fresh_progress := true
	var chat_work := {}
	var graph_script: Script
	var chat: Control
	var notice := Label.new()
	var allowed := true
	var delay := false
	var reads := 0
	var saved := {}
	var saves := 0
	var refreshes := 0
	var snapshot := {}
	var detail_delay := false
	var answer_delay := false
	var answer_result := {}
	var answers_sent := []
	var operation := {}
	var matcher
	var board_delay := false
	signal release_board
	func _board_command(_refresh: bool, _user: String) -> Dictionary:
		if board_delay: await release_board
		return {"board":{"repo_id":actor.repo_id,"user_id":actor.user_id,"issues":board.issues}}
	signal release_detail
	signal release_answer
	func read_issue_details(_item: Dictionary) -> Dictionary:
		if detail_delay: await release_detail
		return {"document":{"markdown":"# Model design", "editable":true}, "related":[]}
	func read_graph(_id: String) -> Dictionary: return snapshot.duplicate(true)
	func _pending_operation(item: Dictionary) -> Dictionary:
		return {} if operation.is_empty() else matcher.matching_operation(item, operation, _repo(), actor.user_id)
	func _graph_command(id: String, action: String, request: Dictionary) -> Dictionary:
		answers_sent.append({"url":id,"action":action,"request":request})
		if answer_delay: await release_answer
		return answer_result.duplicate(true)
	signal release_access
	func _repo() -> String: return ProjectSettings.globalize_path("res://").trim_suffix("/")
	func _fresh_access() -> bool:
		reads += 1
		if delay: await release_access
		return allowed
	func _has_started_worker(_item: Dictionary) -> bool: return false
	func _leave_conversation() -> void: pass
	func _save() -> void: saves += 1
	func refresh() -> void: refreshes += 1
	func _work_summary(_item: Dictionary, _judged: Dictionary) -> Dictionary: return {"text":"fixture"}
	func _display_state(item: Dictionary) -> String: return item.get("status", "planned")

var failures: Array = []
func check(value: bool, reason: String) -> void:
	if not value:
		failures.append(reason)
		push_error(reason)

func _initialize() -> void:
	run.call_deferred()

func settle() -> void:
	for frame in 8: await process_frame

func run() -> void:
	root.size = Vector2i(1440, 900)
	await settle()
	var script := GDScript.new()
	script.source_code = FileAccess.get_file_as_string(OS.get_environment("TIANSHU_SPATIAL_SOURCE"))
	check(script.reload() == OK, "spatial script parses")
	if not failures.is_empty(): quit(1); return
	if OS.get_environment("TIANSHU_SOURCE_ONLY") == "1":
		print("TIANSHU_SPATIAL_OK source-only")
		quit(0)
		return
	var workspace = root.find_child("DaqianWorkspace", true, false)
	check(is_instance_valid(workspace), "native workspace exists")
	if not is_instance_valid(workspace): quit(1); return
	var spatial = workspace.spatial_workbench
	check(is_instance_valid(spatial), "native spatial entry installed")
	if not is_instance_valid(spatial): quit(1); return
	if not OS.get_environment("TIANSHU_REFERENCE_RESTORE").is_empty():
		EditorInterface.set_main_screen_editor("AI Chat")
		await settle()
		var restored_label: Button = workspace.chat.find_child("WorkbenchReference", true, false)
		var restored_input: TextEdit = workspace.chat.find_child("ChatInput", true, false)
		var restored_send: Button = workspace.chat.find_child("Send", true, false)
		var ready_by := Time.get_ticks_msec() + 5000
		while Time.get_ticks_msec() < ready_by and (not restored_label.is_visible_in_tree() or not restored_label.text.contains("引用已失效")):
			await process_frame
		var expected := "legacy question" if OS.get_environment("TIANSHU_REFERENCE_RESTORE") == "legacy" else "must stay in draft: same-named node in newly opened scene"
		check(restored_input.text == expected, "reopened the original user draft")
		check(restored_label.is_visible_in_tree() and restored_label.text.contains("引用已失效"), "disk history never reuses another process's node identity")
		restored_send.pressed.emit()
		check(restored_input.text == expected and workspace.chat.get_meta("queued_message_count", 0) == 0, "restored reference blocks send")
		print(JSON.stringify({"restore":OS.get_environment("TIANSHU_REFERENCE_RESTORE"),"reference":restored_label.text,"failures":failures}))
		if failures.is_empty(): print("TIANSHU_SPATIAL_OK restored references")
		quit(0 if failures.is_empty() else 1)
		return
	if OS.get_environment("TIANSHU_REFERENCE_ENDPOINT") != "":
		await check_editor_references(workspace, spatial)
		print(JSON.stringify({"reference_failures":failures}))
		if failures.is_empty(): print("TIANSHU_SPATIAL_OK references")
		quit(0 if failures.is_empty() else 1)
		return
	if OS.get_environment("TIANSHU_RESTART") == "1":
		var stored: Dictionary = spatial.links.get("fixture/project", {})
		check(stored.get("res://production.tscn::Hero", {}).get("https://github.com/fixture/project/issues/1", {}).get("contents", []) == ["res://textures/hero.png"], "model content persists across editor restart")
		check(stored.get("res://production.tscn::Prop", {}).has("https://github.com/fixture/project/issues/2"), "bound task persists across editor restart")
		print(JSON.stringify({"restart_failures":failures}))
		if failures.is_empty(): print("TIANSHU_SPATIAL_OK restart")
		quit(0 if failures.is_empty() else 1)
		return
	EditorInterface.set_main_screen_editor("3D")
	spatial.toggle.button_pressed = true
	await settle()
	check(spatial.panel.is_visible_in_tree(), "3D panel visible")
	var new_task_button: Button
	for child in spatial.actions.get_children():
		if child is Button and child.text == "新任务": new_task_button = child
	check(is_instance_valid(new_task_button), "new task button exists")
	var saved_actor: Dictionary = workspace.actor.duplicate(true)
	workspace.actor = {}
	var prior_feedback: String = spatial.feedback.text
	new_task_button.pressed.emit()
	await settle()
	check(spatial.feedback.text != prior_feedback and spatial.feedback.text.contains("工作区连接"), "unconnected button explains connection requirement")
	check(not spatial.owns_chat and not spatial.opening, "unconnected click releases action without opening chat")
	var connection_feedback: String = spatial.feedback.text
	spatial.update_view(true)
	check(spatial.feedback.text == connection_feedback, "connection guidance survives board redraw")
	var connection_button: Button
	for child in spatial.panel.get_child(0).get_children():
		if child is Button and child.text == "工作区连接": connection_button = child
	check(is_instance_valid(connection_button), "3D has direct workspace connection action")
	workspace.actor = saved_actor
	check(spatial.panel.size.x > 0 and spatial.panel.size.x < EditorInterface.get_base_control().size.x, "panel keeps viewport space: %s / %s" % [spatial.panel.size, EditorInterface.get_base_control().size])
	var scene := Node3D.new()
	scene.name = "ProductionScene"
	var model := MeshInstance3D.new()
	model.name = "Hero"
	model.mesh = BoxMesh.new()
	scene.add_child(model)
	model.owner = scene
	var other := MeshInstance3D.new()
	other.name = "Prop"
	other.mesh = SphereMesh.new()
	scene.add_child(other)
	other.owner = scene
	var packed := PackedScene.new()
	check(packed.pack(scene) == OK and ResourceSaver.save(packed, "res://production.tscn") == OK, "save fixture scene")
	scene.free()
	EditorInterface.open_scene_from_path("res://production.tscn")
	await settle()
	scene = EditorInterface.get_edited_scene_root()
	model = scene.get_node("Hero")
	other = scene.get_node("Prop")
	var selected := EditorInterface.get_selection()
	selected.clear()
	selected.add_node(model)
	await settle()
	spatial.selection_changed()
	check(spatial.selection.get("key") == "res://production.tscn::Hero", "built-in model identity")
	var fake_issue := {"url":"https://github.com/fixture/project/issues/1", "number":1,"request":"fixture-request", "title":"Make Hero", "status":"in-progress","closed":false,"workers":[]}
	workspace.actor = {"repo":"fixture/project", "user_id":"42", "repo_id":"1"}
	workspace.board = {"issues":[fake_issue]}
	workspace.offline = false
	workspace.fresh_progress = true
	spatial.update_view(true)
	check(spatial.rows.item_count == 0, "no inferred association")
	spatial.picker.select(0)
	spatial.bind_issue()
	check(spatial.rows.item_count == 1, "explicit issue association")
	spatial.output_path.text = "res://textures/hero.png"
	spatial.register_content()
	check(spatial.details.get_parsed_text().contains("待制作 / 文件未找到"), "missing output shown honestly")
	spatial.load_links()
	spatial.update_view(true)
	check(spatial.model_links().get(fake_issue.url, {}).get("contents", []) == ["res://textures/hero.png"], "association survives reload")
	selected.clear()
	selected.add_node(other)
	spatial.selection_changed()
	check(spatial.rows.item_count == 0, "other model does not inherit issues")
	selected.add_node(model)
	spatial.selection_changed()
	check(spatial.selection.is_empty(), "multiple selection invalidates context")
	selected.clear()
	selected.add_node(model)
	spatial.selection_changed()
	workspace.offline = true
	spatial.update_view(true)
	check(spatial.feedback.text.contains("待核实"), "offline status not live")
	workspace.board = {"issues":[]}
	spatial.update_view(true)
	check(spatial.rows.item_count == 1 and spatial.selected_issue().get("unverified", false), "out of scope linked issue stays unknown")
	var before: String = FileAccess.get_file_as_string(spatial.LINKS_PATH)
	var file := FileAccess.open(spatial.LINKS_PATH, FileAccess.WRITE)
	file.store_string(before + "\n")
	file.close()
	check(not spatial.save_links({}), "external file update rejects overwrite")
	check(spatial.feedback.text.contains("已被其他操作更新"), "concurrent save explains retry")
	check(FileAccess.get_file_as_string(spatial.LINKS_PATH) == before + "\n", "external content retained")
	check(spatial.save_links(spatial.links.duplicate(true)), "retry after concurrent update can save")
	check(not spatial.feedback.text.contains("已被其他操作更新"), "successful save clears old conflict feedback")
	spatial.toggle.button_pressed = false
	check(not spatial.panel.visible, "collapse panel")
	EditorInterface.set_main_screen_editor("Script")
	await settle()
	EditorInterface.set_main_screen_editor("3D")
	spatial.toggle.button_pressed = true
	await settle()
	check(spatial.panel.is_visible_in_tree(), "return to 3D preserves panel")
	# Native chat mount/staging boundary: no network or model request is sent.
	var chat: Control = workspace.chat
	var settings := EditorInterface.get_editor_settings()
	var fixture_root := ProjectSettings.globalize_path("res://").trim_suffix("/")
	settings.set_setting("gonggong/workspace", fixture_root)
	settings.set_project_metadata("daqian_access", fixture_root.sha256_text(), {"actor":workspace.actor})
	await create_timer(0.3).timeout
	var error: String = chat.open_daqian_chat("spatial_fixture", 0, "", "", false, {}, true)
	check(error.is_empty(), "open native draft: " + error)
	check(chat.mount_daqian_chat(spatial.chat_host), "mount native chat in 3D")
	spatial.owns_chat = true
	spatial.chat_scroll.show()
	spatial.rows.hide()
	spatial.details.hide()
	spatial.actions.hide()
	spatial.mapping.hide()
	check(chat.stage_daqian_message(spatial.chat_host, "Hero context\nTask: ").is_empty(), "stage model context without send")
	var input: TextEdit = spatial.chat_host.find_child("ChatInput", true, false)
	check(is_instance_valid(input) and input.text == "Hero context\nTask: ", "real mounted input contains context")
	check(not chat.stage_daqian_message(spatial.chat_host, "Other model").is_empty(), "existing draft not overwritten")
	var wrong_host := VBoxContainer.new()
	root.add_child(wrong_host)
	check(not chat.stage_daqian_message(wrong_host, "Wrong host").is_empty(), "wrong host cannot stage draft")
	wrong_host.queue_free()
	await settle()
	for width in [1440, 1100]:
		root.size = Vector2i(width, 900)
		await settle()
		check(spatial.panel.size.x < EditorInterface.get_base_control().size.x - 160, "mounted chat retains viewport at %d" % width)
		var field := input.get_global_rect()
		var viewport_rect: Rect2 = spatial.chat_scroll.get_global_rect()
		check(input.is_visible_in_tree() and field.position.y >= viewport_rect.position.y and field.end.y <= minf(viewport_rect.end.y, root.size.y), "mounted input is visible within the preview at %d: %s / %s" % [width, field, viewport_rect])
		print("TIANSHU_COMPOSER_GEOMETRY=", JSON.stringify({"window_width":width, "window_height":root.size.y, "input_top":field.position.y, "input_bottom":field.end.y, "visible":input.is_visible_in_tree(), "scroll_top":viewport_rect.position.y, "scroll_bottom":viewport_rect.end.y}))
	spatial.close_chat()
	check(chat.open_daqian_chat("spatial_fixture", 0, "", "", false, {}, true).is_empty(), "restore same draft session")
	check(chat.mount_daqian_chat(spatial.chat_host), "remount same draft")
	spatial.owns_chat = true
	check(spatial.chat_host.find_child("ChatInput", true, false).text == "Hero context\nTask: ", "draft persists across unmount")
	spatial.close_chat()
	# Apply the same persisted metadata transition as the native issue guide,
	# then require existing-only reopen to find the original spatial draft.
	var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
	for key in bindings:
		if bindings[key].get("source") == "spatial_fixture":
			bindings[key].issue_number = "1"
			bindings[key].request_id = "fixture-request"
	settings.set_project_metadata("daqian", "bindings", bindings)
	check(chat.open_daqian_chat(fake_issue.url, 1, "fixture-request", "", false, {}, true, "", true).is_empty(), "bound spatial draft reopens by canonical Issue URL")
	check(chat.mount_daqian_chat(spatial.chat_host), "mount original bound spatial draft")
	spatial.owns_chat = true
	check(spatial.chat_host.find_child("ChatInput", true, false).text == "Hero context\nTask: ", "canonical Issue reopen preserves original draft")
	spatial.close_chat()
	# Exercise the real side-panel action with an isolated access port. Only the
	# remote permission lookup is controlled; native open/mount/stage remain real.
	var access := AccessFixture.new()
	access.chat = chat
	access.graph_script = workspace.graph_script
	root.add_child(access)
	spatial.workspace = access
	spatial.scope = JSON.stringify([access._repo(), access.actor])
	selected.clear()
	selected.add_node(model)
	spatial.selection_changed()
	access.delay = true
	spatial.open_chat(true)
	check(access.reads == 1 and spatial.opening, "panel action awaits access")
	check(spatial.feedback.text.contains("正在核对"), "pending access gives immediate feedback")
	spatial.update_view(true)
	check(spatial.feedback.text.contains("正在核对"), "pending feedback survives redraw")
	new_task_button.pressed.emit()
	check(access.reads == 1, "repeated click does not start another access request")
	selected.clear()
	selected.add_node(other)
	spatial.selection_changed()
	access.release_access.emit()
	await settle()
	check(not spatial.owns_chat, "late access cannot mount previous model")
	check(spatial.feedback.text.contains("已改变"), "stale model action explains cancellation")
	spatial.open_chat(true)
	access.actor.user_id = "different"
	access.release_access.emit()
	await settle()
	check(not spatial.owns_chat, "late access cannot cross account")
	access.actor.user_id = "42"
	access.delay = false
	access.allowed = false
	access.notice.text = "当前离线，须重新核实协作者身份后提交"
	new_task_button.pressed.emit()
	await settle()
	check(not spatial.owns_chat and not spatial.opening, "failed access releases action without mounting")
	check(spatial.feedback.text.contains("当前离线") and spatial.feedback.text.contains("工作区连接"), "failed access gives real cause and next step")
	spatial.update_view(true)
	check(spatial.feedback.text.contains("当前离线"), "access error survives board refresh")
	access.allowed = true
	spatial.open_chat(true)
	await settle()
	check(spatial.owns_chat, "panel opens real native chat")
	input = spatial.chat_host.find_child("ChatInput", true, false)
	check(is_instance_valid(input) and spatial.chat_host.find_child("WorkbenchReference", true, false).text.contains("res://production.tscn#Prop"), "panel stages selected model context")
	var task_source := "spatial_" + ("fixture/project" + "res://production.tscn::Prop").sha256_text()
	chat.daqian_issue_bound.emit(task_source, 2, "new-task-request")
	check(spatial.model_links().has("https://github.com/fixture/project/issues/2"), "bound task automatically links original model")
	check(access.saved.get("following", []).has(2) and access.saves == 1 and access.refreshes == 1, "bound task follows and refreshes workbench")
	check(not spatial.pending_sources.has(task_source), "consumed source receipt is retired")
	spatial.close_chat()
	await settle()
	check(not spatial.feedback.text.contains("在下方聊天"), "closing chat clears obsolete send hint")
	# Inline details and graph answer ports stay in the 3D panel. The native
	# conversation is real; remote reads/writes use bounded, delayed fixtures.
	selected.clear()
	selected.add_node(model)
	spatial.selection_changed()
	access.board = {"issues":[fake_issue]}
	spatial.update_view(true)
	access.snapshot = {"revision":"rev1", "context":{"can_answer":true,"questions":{"color":{"prompt":"Choose model color", "options":["rainbow","gradient"]}},"answers":{}}}
	await spatial.open_detail()
	check(spatial.drawer.is_visible_in_tree() and not spatial.details.visible, "details rendered in visible 3D drawer")
	check(spatial.inspector.field.text == "# Model design" and not spatial.inspector.field.editable, "existing inspector renders read-only design")
	check(spatial.reply_controls == 1, "explicit graph question has inline reply control")
	var choice: OptionButton = spatial.question_box.find_child("InlineAnswer", true, false)
	choice.select(2)
	choice.item_selected.emit(2)
	spatial.close_chat()
	await spatial.open_detail()
	choice = spatial.question_box.find_child("InlineAnswer", true, false)
	check(choice.selected == 2, "answer draft survives closing and reopening same revision")
	access.delay = true
	spatial.submit_answer("color")
	check(spatial.submitting and spatial.question_box.find_child("InlineAnswer", true, false).disabled, "answer controls freeze while permission check runs")
	selected.clear()
	selected.add_node(other)
	spatial.selection_changed()
	access.release_access.emit()
	await settle()
	check(access.answers_sent.is_empty(), "switching model before access completes sends no answer")
	selected.clear()
	selected.add_node(model)
	spatial.selection_changed()
	access.delay = false
	access.answer_result = {"ok":false,"error":"revision changed"}
	await spatial.open_detail()
	await spatial.submit_answer("color")
	check(access.answers_sent.size() == 1 and access.answers_sent[0].request == {"revision":"rev1","node":"color","value":"gradient"}, "reply uses original revision and selected value")
	check(spatial.feedback.text == "revision changed" and spatial.question_box.find_child("InlineAnswer", true, false).selected == 2, "failed reply retains draft and actual failure")
	access.answer_result = {"ok":true,"context":{"can_answer":true,"questions":access.snapshot.context.questions,"answers":{"color":{"value":"gradient"}}}}
	await spatial.submit_answer("color")
	check(spatial.reply_controls == 0 and spatial.feedback.text.contains("已记录答复"), "successful reply displays receipt without duplicate request")
	# A refreshed source invalidates an older drawer rather than leaving a stale prompt.
	fake_issue.updated = "new-revision"
	spatial.update_view(true)
	check(not spatial.drawer.visible and spatial.details.visible, "board update invalidates drawer and restores summary")
	# An older response invocation may not mount chat after another details selection.
	access.detail_delay = true
	spatial.open_response()
	spatial.close_chat()
	access.release_detail.emit()
	await settle()
	check(not spatial.owns_chat, "cancelled response read cannot reopen chat")
	access.detail_delay = false
	access.snapshot = {"revision":"rev2", "context":{"can_answer":false,"questions":{"human":{"prompt":"Material clarification"}},"answers":{}}}
	await spatial.open_response()
	await settle()
	check(spatial.owns_chat and spatial.chat_host.is_visible_in_tree(), "ordinary clarification opens original native chat inside 3D")
	check(spatial.chat_host.find_child("ChatInput", true, false).text == "Hero context\nTask: ", "inline continuation preserves existing original conversation draft")
	spatial.close_chat()
	check(spatial.details.visible and not spatial.drawer.visible, "return restores model summary")
	var approval_chat := ApprovalChat.new()
	root.add_child(approval_chat)
	access.chat = approval_chat
	access.matcher = spatial.operation_panel
	access.operation = {"token":"one-click", "url":fake_issue.url, "request":fake_issue.request, "source_sha256":"", "actor":"42", "board_workspace":access._repo(), "summary":"fixture operation", "detail":"fixture command", "tool":"fixture"}
	await spatial.open_detail()
	await settle()
	check(spatial.operation_panel.visible and spatial.operation_panel.details_confirm.text == "确认此操作", "pending operation renders existing confirmation module in 3D")
	check(approval_chat.confirmed.is_empty(), "viewing pending operation never executes it")
	for width in [1440, 1100]:
		root.size = Vector2i(width, 900)
		await settle()
		check(spatial.panel.size.x < EditorInterface.get_base_control().size.x - 160, "inline details preserve viewport at %d" % width)
		check(spatial.drawer.get_global_rect().end.y <= root.size.y, "scrollable detail drawer within window at %d" % width)
	access.board_delay = true
	spatial.operation_panel.details_confirm.pressed.emit()
	check(approval_chat.confirmed.is_empty(), "confirmation waits for live board readback")
	spatial.close_chat()
	access.release_board.emit()
	await settle()
	check(approval_chat.confirmed.is_empty(), "closing drawer cancels stale confirmation")
	await spatial.open_detail()
	spatial.operation_panel.details_confirm.pressed.emit()
	access.operation.token = "replacement"
	access.release_board.emit()
	await settle()
	check(approval_chat.confirmed.is_empty(), "changed operation token cannot be confirmed")
	await spatial.open_detail()
	access.board_delay = false
	spatial.operation_panel.details_confirm.pressed.emit()
	await settle()
	check(approval_chat.confirmed == [[fake_issue.url,"replacement"]], "explicit click confirms exactly selected issue and live token")
	access.chat = chat
	approval_chat.queue_free()
	spatial.workspace = workspace
	# Run the actual embedded access method with a delayed transport port, so
	# stale denials cannot destroy a newer actor/root/epoch after awaiting I/O.
	var native_source: String = workspace.get_script().source_code
	var access_method := native_source.substr(native_source.find("func _fresh_access()"))
	access_method = access_method.substr(0, access_method.find("func _open_models()"))
	var guard_script := GDScript.new()
	guard_script.source_code = "extends Node\nsignal release\nvar actor := {\"user_id\":\"42\"}\nvar scope_epoch := 0\nvar root := \"initial\"\nvar notice := Label.new()\nvar response := {}\nvar result = null\nvar forgotten := 0\nfunc _repo() -> String: return root\nfunc _access_key() -> String: return root.sha256_text()\nfunc _board_command(_a, _b) -> Dictionary:\n\tawait release\n\treturn response\nfunc _forget(_reason): forgotten += 1\nfunc begin(): result = await _fresh_access()\n" + access_method
	var guard_error := guard_script.reload()
	check(guard_error == OK, "embedded access guard compiles with controlled transport")
	if guard_error != OK: quit(1); return
	var guard = guard_script.new()
	guard.add_child(guard.notice)
	for mutation in ["actor", "root", "epoch", "success_epoch", "unchanged"]:
		guard.actor = {"user_id":"42"}
		guard.root = "initial"
		guard.result = null
		guard.response = {"access":{"user_id":"42"}} if mutation in ["success_epoch", "unchanged"] else {"denied":true,"error":"old denial"}
		guard.begin()
		if mutation == "actor": guard.actor = {"user_id":"other"}
		if mutation == "root": guard.root = "other"
		if mutation in ["epoch", "success_epoch"]: guard.scope_epoch += 1
		guard.release.emit()
		check(guard.forgotten == 0, "stale denial preserves new connection: " + mutation)
		check(guard.result == (mutation == "unchanged"), "access guard result: " + mutation)
	guard.free()
	# Run the embedded details adapter with distinct installed-host and project
	# roots. Project data must never choose the executable host implementation.
	var details_method := native_source.substr(native_source.find("func read_issue_details("))
	details_method = details_method.substr(0, details_method.find("func read_graph("))
	var details_script := GDScript.new()
	details_script.source_code = "extends RefCounted\nvar offline := false\nvar actor := {\"user_id\":\"42\"}\nvar editor_session := \"fixture-session\"\nvar calls := []\nfunc _repo() -> String: return \"project-data\"\nfunc _host_root() -> String: return \"installed-host\"\nfunc _board_entry_args(script: String) -> PackedStringArray: return PackedStringArray([script])\nfunc _host_command(args: PackedStringArray, output_flag: String, request: Dictionary) -> Dictionary:\n\tcalls.append({\"args\":args,\"flag\":output_flag,\"request\":request})\n\treturn {\"document\":{}}\n" + details_method
	var details_error := details_script.reload()
	check(details_error == OK, "embedded details adapter compiles with isolated transport")
	if details_error != OK: quit(1); return
	var detail_guard = details_script.new()
	await detail_guard.read_issue_details({"number":42,"request":"fixture-request"})
	check(detail_guard.calls.size() == 1, "details adapter issues one host request")
	if detail_guard.calls.size() == 1:
		var call: Dictionary = detail_guard.calls[0]
		check(call.args[0] == "installed-host/customizations/components/godot-host/daqian/board.py", "details uses installed helper rather than project implementation")
		check(call.args[call.args.find("--repo") + 1] == "project-data", "details uses selected project only as data")
		check(call.args[call.args.find("--expected-user") + 1] == "42" and call.args[call.args.find("--editor-session") + 1] == "fixture-session", "details preserves verified actor and editor session")
		check(call.flag == "--result" and call.request == {"action":"details","number":42,"request":"fixture-request"}, "details preserves the selected Issue binding")
	detail_guard.offline = true
	check((await detail_guard.read_issue_details({"number":42})).has("error") and detail_guard.calls.size() == 1, "offline details cannot launch a helper")
	detail_guard.offline = false
	detail_guard.actor = {}
	check((await detail_guard.read_issue_details({"number":42})).has("error") and detail_guard.calls.size() == 1, "unverified details cannot launch a helper")
	access.notice.free()
	access.queue_free()
	selected.clear()
	spatial.selection_changed()
	check(spatial.selection.is_empty(), "selection cleared")
	print(JSON.stringify({"failures":failures,"passed":failures.is_empty()}))
	if failures.is_empty(): print("TIANSHU_SPATIAL_OK")
	quit(0 if failures.is_empty() else 1)

func stage_again(chat, host: Control, node: Node, label: Button, input: TextEdit) -> void:
	if label.visible: label.pressed.emit()
	input.text = ""
	check(chat.stage_workbench_reference(host, node).is_empty(), "explicitly attach the chosen instance")
	check(label.visible and not label.text.contains("失效"), "fresh reference is visible")

func refused(label: Button, input: TextEdit, send: Button, reason: String) -> void:
	input.text = "must stay in draft: " + reason
	var before := label.text
	send.pressed.emit()
	print("REFERENCE_REFUSAL ", JSON.stringify({"reason":reason, "before":before, "after":label.text, "visible":label.is_visible_in_tree(), "draft":input.text}))
	check(label.is_visible_in_tree() and label.text.contains("失效") and input.text.ends_with(reason), reason)

func check_editor_references(workspace, spatial) -> void:
	var chat: Control = workspace.chat
	var access := AccessFixture.new()
	access.chat = chat
	access.graph_script = workspace.graph_script
	root.add_child(access)
	spatial.workspace = access
	spatial.scope = JSON.stringify([access._repo(), access.actor])
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", access._repo())
	settings.set_project_metadata("daqian_access", access._repo().sha256_text(), {"actor":access.actor})
	var mesh_file := "res://hero-mesh.tres"
	var scene_file := "res://reference-a.tscn"
	check(ResourceSaver.save(BoxMesh.new(), mesh_file) == OK, "save external mesh")
	var origin := Node3D.new()
	origin.name = "Root"
	for node_name in ["Hero", "Other"]:
		var model := MeshInstance3D.new()
		model.name = node_name
		model.mesh = load(mesh_file)
		origin.add_child(model)
		model.owner = origin
	var packed := PackedScene.new()
	check(packed.pack(origin) == OK and ResourceSaver.save(packed, scene_file) == OK, "save first scene")
	check(ResourceSaver.save(packed, "res://reference-b.tscn") == OK, "save same-name second scene")
	origin.free()
	EditorInterface.open_scene_from_path(scene_file)
	EditorInterface.set_main_screen_editor("3D")
	await settle()
	origin = EditorInterface.get_edited_scene_root()
	var original: MeshInstance3D = origin.get_node("Hero")
	var selection := EditorInterface.get_selection()
	selection.clear()
	selection.add_node(original)
	spatial.selection_changed()
	spatial.toggle.button_pressed = true
	var issue := {"url":"https://github.com/fixture/project/issues/8", "number":8, "request":"reference-fixture", "title":"Check model", "status":"planned", "closed":false, "workers":[]}
	access.board.issues = [issue]
	spatial.update_view(true)
	spatial.picker.select(0)
	spatial.bind_issue()
	check(spatial.selected_issue().get("url") == issue.url, "explicit model association selects the exact issue")
	# Inline workflow replies still use the original mounted composer and its send boundary.
	# The migrated consultation buttons are exercised in workbench_compact_model_route.gd.
	await spatial.open_chat(false)
	await settle()
	check(spatial.owns_chat, "inline spatial reply mounted the existing composer")
	if not spatial.owns_chat: return
	var host: Control = spatial.chat_host
	var input: TextEdit = host.find_child("ChatInput", true, false)
	var label: Button = host.find_child("WorkbenchReference", true, false)
	var send: Button = host.find_child("Send", true, false)
	check(label.is_visible_in_tree() and label.text.contains(scene_file + "#Hero"), "selected model is bound in composer")
	var config: Control = chat.get_ai_settings_control()
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("TIANSHU_REFERENCE_ENDPOINT")
	var backend: OptionButton = root.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("TIANSHU_REFERENCE_ENDPOINT")
	var key: LineEdit = config.find_child("APIKey", true, false)
	key.text = "spatial-fixture-key"
	key.text_changed.emit(key.text)
	root.find_child("APIModel", true, false).text = "fixture"
	host.find_child("ConsultationOnly", true, false).button_pressed = true
	await create_timer(1.2).timeout
	var deadline := Time.get_ticks_msec() + 12000
	while send.disabled and Time.get_ticks_msec() < deadline: await process_frame
	check(not send.disabled, "fixture model accepts native Send")
	selection.clear()
	selection.add_node(origin.get_node("Other"))
	spatial.selection_changed()
	input.text = "inspect original"
	var expected := [
		{"kind":"editor", "object_id":scene_file + "#Hero", "revision":FileAccess.get_sha256(scene_file)},
		{"kind":"editor", "object_id":mesh_file, "revision":FileAccess.get_sha256(mesh_file)}
	]
	send.pressed.emit()
	var history_path := "res://.godot/editor/ai_chat_history.json"
	var frozen := {}
	deadline = Time.get_ticks_msec() + 15000
	while frozen.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
		if not FileAccess.file_exists(history_path): continue
		var history = JSON.parse_string(FileAccess.get_file_as_string(history_path))
		if not history is Dictionary: continue
		for agent in history.get("agents", []):
			for record in agent.transcript:
				if record.get("editor_references") == expected: frozen = record
	check(not frozen.is_empty() and not label.visible and input.text.is_empty(), "persisted user message contains both exact revisions")
	if frozen.is_empty():
		print("REFERENCE_SEND_DIAGNOSTIC ", chat.get_ai_workflow_snapshot(), " ", host.find_child("ProgressStatus", true, false), " ", input.text)
		return
	stage_again(chat, host, original, label, input)
	var replacement := MeshInstance3D.new()
	replacement.mesh = original.mesh
	# Replace before the next frame. A path-only resolver would accept this target.
	origin.remove_child(original)
	original.free()
	replacement.name = "Hero"
	origin.add_child(replacement)
	replacement.owner = origin
	refused(label, input, send, "same name and path with a new instance")
	stage_again(chat, host, replacement, label, input)
	replacement.name = "Renamed"
	await create_timer(0.4).timeout
	check(label.text.contains("失效"), "renamed node becomes visibly invalid before send")
	refused(label, input, send, "stale node path")
	stage_again(chat, host, replacement, label, input)
	var bytes := FileAccess.get_file_as_bytes(mesh_file)
	var changed := FileAccess.open(mesh_file, FileAccess.READ_WRITE)
	changed.seek_end()
	changed.store_string("\n")
	changed.close()
	refused(label, input, send, "same file path with different bytes")
	var restored := FileAccess.open(mesh_file, FileAccess.WRITE)
	restored.store_buffer(bytes)
	restored.close()
	stage_again(chat, host, replacement, label, input)
	check(DirAccess.remove_absolute(mesh_file) == OK, "delete captured resource")
	await create_timer(0.4).timeout
	check(label.text.contains("失效"), "deleted file becomes visibly invalid before send")
	refused(label, input, send, "deleted external resource")
	restored = FileAccess.open(mesh_file, FileAccess.WRITE)
	restored.store_buffer(bytes)
	restored.close()
	replacement.name = "Hero"
	stage_again(chat, host, replacement, label, input)
	EditorInterface.open_scene_from_path("res://reference-b.tscn")
	await settle()
	check(EditorInterface.get_edited_scene_root().get_node("Hero") != replacement and label.text.contains("失效"), "scene switch invalidates identical path")
	refused(label, input, send, "same-named node in newly opened scene")
	await create_timer(1.5).timeout
	var stored = JSON.parse_string(FileAccess.get_file_as_string(history_path))
	var retained := false
	for agent in stored.agents:
		for record in agent.transcript:
			if record == frozen: retained = true
	check(retained, "historical message still points to original object and revisions")
	print("FROZEN_EDITOR_REFERENCES ", JSON.stringify(expected))
	spatial.close_chat()
	spatial.workspace = workspace
	access.notice.free()
	access.queue_free()
