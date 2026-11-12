@tool
extends SceneTree

var dock: Node
var approvals := 0
var failure := false
var stale_regranted := false

func _catalog_ready(dock) -> bool:
	var snapshot: Dictionary = dock.get_model_catalog_snapshot()
	return snapshot.get("state", "") == "ready" and snapshot.get("catalog_current", false) and not snapshot.get("loading", true)

func _initialize():
	run.call_deferred()

func check(value: bool, reason: String) -> bool:
	if not value:
		failure = true
		push_error(reason)
		if dock != null:
			print("TASK_FAILURE_CHAT ", text())
		EditorInterface.stop_playing_scene()
	return value

func text() -> String:
	var value := ""
	for label in dock.find_children("*", "RichTextLabel", true, false):
		value += label.get_parsed_text()
	return value

func phase(name: String, marker: String, reject: bool) -> bool:
	dock.find_child("ChatInput", true, false).text = name
	dock.find_child("Send", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 90000
	var dialog := dock.find_child("AIFileApproval", true, false) as ConfirmationDialog
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		if name == "task_grant_stale" and not stale_regranted and FileAccess.file_exists("res://task_grant_stale-inflight"):
			var grant = dock.get_ai_settings_control().find_child("TaskNativeAuthorization", true, false)
			grant.button_pressed = false
			grant.button_pressed = true
			stale_regranted = true
		if name == "task_grant_stop" and FileAccess.file_exists("res://task_grant_stop-inflight"):
			dock.find_child("Stop", true, false).pressed.emit()
			await create_timer(0.3).timeout
			return check(not dock.get_ai_settings_control().find_child("TaskNativeAuthorization", true, false).button_pressed, "Stop retained grant")
		if dialog.visible:
			approvals += 1
			if not reject:
				check(false, "Task grant unexpectedly requested per-action confirmation")
			dialog.hide()
			dialog.canceled.emit()
		await create_timer(0.02).timeout
	return check(dock.find_child("Stop", true, false).disabled and marker in text(), "Missing terminal marker: " + name)

func run():
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	if not check(dock != null, "Native dock missing"):
		quit(1)
		return
	var restarting := OS.get_environment("TASK_NATIVE_RESTART") == "1"
	if restarting:
		check(not dock.get_ai_settings_control().find_child("TaskNativeAuthorization", true, false).button_pressed, "Restart restored native authority")
	if not dock.find_child("Stop", true, false).disabled:
		dock.find_child("Stop", true, false).pressed.emit()
	root.gui_embed_subwindows = true
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("network/http_proxy/host", "")
	settings.set_setting("gonggong/workspace", OS.get_environment("GONGGONG_TEST_WORKSPACE"))
	dock.set_runtime_field("workflow_python", OS.get_environment("GONGGONG_PYTHON"))
	settings.set_setting("gonggong/issue_number", "6")
	settings.set_setting("gonggong/request_id", "isolated-gate")
	var controls = dock.get_ai_settings_control()
	var backend = controls.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	controls.find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
	controls.find_child("APIModel", true, false).text = "mock-semantic"
	controls.find_child("APIKey", true, false).text = "mock-key"
	controls.find_child("AllowTools", true, false).button_pressed = true
	controls.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	controls.find_child("AutoExecuteCommands", true, false).button_pressed = true
	var key = controls.find_child("APIKey", true, false)
	key.text_changed.emit(key.text)
	var ready_deadline := Time.get_ticks_msec() + 35000
	var status = controls.find_child("ModelStatus", true, false)
	while (backend.disabled or not _catalog_ready(dock)) and Time.get_ticks_msec() < ready_deadline:
		await process_frame
	if not check(not dock.find_child("Send", true, false).disabled and _catalog_ready(dock), "Model discovery did not finish: " + status.text):
		quit(1)
		return
	var grant = controls.find_child("TaskNativeAuthorization", true, false)
	check(grant != null and not grant.button_pressed, "Grant must default off independently of other auto switches")
	EditorInterface.open_scene_from_path("res://task_game.tscn")
	await create_timer(0.5).timeout
	if restarting:
		var before_restart := approvals
		await phase("task_grant_restart", "TASK_BOUNDARY_OK", true)
		check(approvals == before_restart + 1, "Restart forged write did not require confirmation")
		check(EditorInterface.get_edited_scene_root().get_node_or_null("Unauthorized") == null, "Restart forged write mutated scene")
		check(not grant.button_pressed, "Restart request forged authorization control")
		print("TASK_NATIVE_RESTART_OK" if not failure else "TASK_NATIVE_RESTART_FAILED")
		quit(1 if failure else 0)
		return
	if not await phase("task_grant_default", "TASK_BOUNDARY_OK", true):
		quit(1)
		return
	check(EditorInterface.get_edited_scene_root().get_node_or_null("Unauthorized") == null, "Model JSON forged native authority")
	grant.button_pressed = true
	check(grant.button_pressed, "Normal task authorization control rejected bound task")
	var before := approvals
	if not await phase("task_grant_continuous", "TASK_CONTINUOUS_OK", false):
		quit(1)
		return
	check(approvals == before, "Authorized sequence displayed confirmation")
	check(EditorInterface.get_edited_scene_root().get_node_or_null("Authorized") != null, "Native scene mutation missing")
	if not await phase("task_grant_extended", "TASK_EXTENDED_OK", false):
		quit(1)
		return
	check(approvals == before, "Extended authorized sequence displayed confirmation")
	var sprite = EditorInterface.get_edited_scene_root().get_node_or_null("GrantSprite")
	check(sprite != null and sprite.texture != null and sprite.texture.get_width() == 2, "Resource assignment not observed in native scene")
	check(FileAccess.file_exists("res://grant.png.import"), "Native import metadata missing")
	before = approvals
	await phase("task_grant_special", "TASK_SPECIAL_REFUSED", true)
	check(approvals == before + 1, "Nonallowlisted resource export bypassed confirmation")
	check(not FileAccess.file_exists("res://exported.tres"), "Rejected resource export wrote destination")
	check(grant.button_pressed, "Grant lost before external boundary")
	FileAccess.open("res://external-ready", FileAccess.WRITE).store_string("ready")
	var external_deadline := Time.get_ticks_msec() + 30000
	var external_dialog = dock.find_child("AIFileApproval", true, false)
	for external_case in ["external", "resource_drift", "drift"]:
		while not FileAccess.file_exists("res://" + external_case + "-preview") and Time.get_ticks_msec() < external_deadline:
			await create_timer(0.02).timeout
		check(external_dialog.visible, "External request inherited native grant: " + external_case)
		if external_case == "external":
			external_dialog.hide()
			external_dialog.canceled.emit()
		elif external_case == "resource_drift":
			var mesh = EditorInterface.get_edited_scene_root().get_node("GrantMesh").mesh
			check(mesh.size == Vector3(1, 2, 3), "Unexpected initial mesh content")
			mesh.size = Vector3(7, 8, 9)
			external_dialog.hide()
			external_dialog.confirmed.emit()
			check(mesh.size == Vector3(7, 8, 9), "Stale assignment replaced resource content")
			print("TASK_RESOURCE_CONTENT_PRESERVED ", mesh.size)
		else:
			# A user edit after preview must invalidate the pending snapshot.
			sprite.name = "LocallyChanged"
			external_dialog.hide()
			external_dialog.confirmed.emit()
		FileAccess.open("res://" + external_case + "-resolved", FileAccess.WRITE).store_string("ready")
	while not FileAccess.file_exists("res://external-done") and Time.get_ticks_msec() < external_deadline:
		await create_timer(0.02).timeout
	check(FileAccess.get_file_as_string("res://external-done") == "passed", "External boundary driver failed")
	check(sprite.name == "LocallyChanged", "Stale external proposal overwrote local change")
	var disk_script := FileAccess.get_file_as_string("res://fixture.gd")
	EditorInterface.edit_script(load("res://fixture.gd"))
	await create_timer(0.3).timeout
	var code = EditorInterface.get_script_editor().get_current_editor().get_base_editor()
	code.insert_text_at_caret("# UNSAVED_TASK_CONFLICT\n")
	before = approvals
	await phase("task_grant_unsaved", "TASK_UNSAVED_OK", false)
	check(approvals == before, "Unsaved conflict requested approval instead of refusing")
	check("UNSAVED_TASK_CONFLICT" in code.text and not "MODEL_OVERWRITE" in code.text, "Unsaved buffer overwritten")
	check(FileAccess.get_file_as_string("res://fixture.gd") == disk_script, "Unsaved script disk overwritten")
	print("TASK_UNSAVED_BUFFER_AND_DISK_PRESERVED")
	await phase("task_grant_stale", "TASK_BOUNDARY_OK", true)
	check(stale_regranted and EditorInterface.get_edited_scene_root().get_node_or_null("Unauthorized") == null, "Queued stale proposal inherited replacement grant")
	await phase("task_grant_stop", "", true)
	check(not grant.button_pressed, "Stop did not revoke task grant")
	grant.button_pressed = false
	await phase("task_grant_revoked", "TASK_BOUNDARY_OK", true)
	check(EditorInterface.get_edited_scene_root().get_node_or_null("Unauthorized") == null, "Revoked task mutated scene")
	grant.button_pressed = true
	var tabs = dock.find_child("AgentTabs", true, false)
	var previous_tab: int = tabs.current_tab
	dock.find_child("AddAgent", true, false).pressed.emit()
	check(not grant.button_pressed, "New session inherited native authority")
	tabs.current_tab = previous_tab
	grant.button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = true
	check(not grant.button_pressed, "Consultation did not revoke task grant")
	await phase("task_grant_consultation", "TASK_BOUNDARY_OK", true)
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	grant.button_pressed = true
	check(grant.button_pressed, "Idle development mode could not authorize after consultation")
	if not failure:
		print("TASK_NATIVE_AUTHORIZATION_OK")
	EditorInterface.stop_playing_scene()
	await create_timer(0.3).timeout
	quit(1 if failure else 0)
