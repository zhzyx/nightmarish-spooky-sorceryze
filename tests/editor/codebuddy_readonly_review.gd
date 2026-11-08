@tool
extends SceneTree

var dock: Node
var host: Control
var serial := 0
var stop_button: Button
var send_button: Button
var input_box: TextEdit

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func chat_text() -> String:
	var text := ""
	for message_list in root.find_children("Messages", "", true, false):
		for label in message_list.find_children("*", "RichTextLabel", true, false):
			text += label.get_parsed_text() + "\n"
	return text

func send(text: String) -> void:
	input_box.text = text
	send_button.pressed.emit()

func wait_idle_marker(marker: String) -> bool:
	for unused in 3000:
		if marker in chat_text() and stop_button.disabled:
			return true
		await create_timer(0.03).timeout
	push_error("Missing private native marker: " + marker + "\n" + chat_text().right(6000))
	quit(1)
	return false

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	assert(dock != null)
	stop_button = dock.find_child("Stop", true, false)
	send_button = dock.find_child("Send", true, false)
	input_box = dock.find_child("ChatInput", true, false)
	assert(stop_button and send_button and input_box)
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("DESIGN_BATCH_ROOT"))
	settings.set_setting("gonggong/python", OS.get_environment("DESIGN_BATCH_PYTHON"))
	settings.set_setting("gonggong/issue_number", "999")
	settings.set_setting("gonggong/request_id", "private-global-sentinel")
	settings.set_setting("ai_chat/parallel_work_orders_config", "")
	for field in ["workflow_python", "build_python"]:
		assert(dock.set_runtime_field(field, OS.get_environment("DESIGN_BATCH_PYTHON")).is_empty())
	for field in ["node", "codex"]:
		assert(dock.set_runtime_field(field, OS.get_environment("DESIGN_BATCH_NODE")).is_empty())
	var setup = dock.find_child("GongGongRuntimeSetup", true, false)
	if setup:
		setup.hide()
	var ai = dock.get_ai_settings_control()
	ai.find_child("APIKey", true, false).text = "private-offline-fixture"
	ai.find_child("AllowTools", true, false).button_pressed = true
	ai.find_child("AutoApplyFileChanges", true, false).button_pressed = true
	ai.find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for unused in 600:
		if not send_button.disabled:
			break
		await create_timer(0.03).timeout
	assert(dock.open_daqian_chat("https://github.com/example/design-batch/issues/441", 441, "design-batch-fixture", "DESIGN_BATCH_WARMUP", false).is_empty())
	if not await wait_idle_marker("PRIVATE_NATIVE_WARMUP_OK"):
		return
	# Only this private fixture's account scope is simulated; the normal host
	# mount path still validates the native binding and actual candidate owner.
	var workspace := OS.get_environment("DESIGN_BATCH_ROOT")
	var actor := {"repo_id": "fixture-repository", "user_id": "fixture-operator", "repo": "example/design-batch"}
	settings.set_project_metadata("daqian_access", workspace.sha256_text(), {"actor": actor})
	var scope := (workspace + "|fixture-repository|fixture-operator").sha256_text()
	var bindings: Dictionary = settings.get_project_metadata("daqian", "bindings", {})
	for owner in bindings:
		if bindings[owner].get("request_id", "") == "design-batch-fixture":
			bindings[owner]["scope"] = scope
	settings.set_project_metadata("daqian", "bindings", bindings)
	assert(dock.open_daqian_chat("https://github.com/example/design-batch/issues/441", 441, "design-batch-fixture", "", false, {}, true).is_empty())
	host = VBoxContainer.new()
	host.name = "PrivateMountedChat"
	root.add_child(host)
	assert(dock.mount_daqian_chat(host))
	write_json("res://ready.json", {"pid": OS.get_process_id(), "text": chat_text()})
	while true:
		if FileAccess.file_exists("res://fixture-command.json"):
			var command = JSON.parse_string(FileAccess.get_file_as_string("res://fixture-command.json"))
			if command is Dictionary and command.get("serial", 0) > serial:
				serial = command.serial
				var result := {"ok": true}
				if command.action == "approve":
					var dialog = dock.find_child("AIFileApproval", true, false)
					result["visible"] = dialog.visible
					if dialog.visible:
						dialog.confirmed.emit()
				elif command.action == "read":
					result["text"] = chat_text()
					result["busy"] = not stop_button.disabled
				elif command.action == "unmount":
					dock.unmount_daqian_chat()
					if is_instance_valid(host):
						host.queue_free()
				elif command.action == "history_view":
					var dialog = dock.find_child("LocalSnapshotChangesDialog", true, false)
					result["visible"] = dialog.visible
					result["file_count"] = dock.find_child("SnapshotChangesFiles", true, false).item_count
					result["after"] = dock.find_child("SnapshotChangesAfter", true, false).text
					dialog.hide()
				elif command.action == "review":
					dock.unmount_daqian_chat()
					if is_instance_valid(host):
						host.queue_free()
					var environment = dock.get_environment_settings_control()
					environment.find_child("CLIBridge", true, false).text = OS.get_environment("CODEBUDDY_REVIEW_BRIDGE")
					environment.find_child("CLIEntry", true, false).text = OS.get_environment("CODEBUDDY_REVIEW_ENTRY")
					ai.find_child("CLIModel", true, false).text = "mock-model"
					var backend = ai.find_child("AIBackend", true, false)
					backend.select(1)
					backend.item_selected.emit(1)
					for unused in 1000:
						if not send_button.disabled:
							break
						await create_timer(0.03).timeout
					send("case:readonly_parent")
					if not await wait_idle_marker("READONLY_PARENT_RETURN_OK"):
						return
					await create_timer(0.3).timeout
					write_json("res://complete.json", {"ok": true, "text": chat_text(), "backend": backend.selected})
					print("CODEBUDDY_READONLY_NATIVE_OK")
					quit()
					return
				write_json("res://ack-%d.json" % serial, result)
		await create_timer(0.02).timeout
