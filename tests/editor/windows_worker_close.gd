@tool
extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	await create_timer(1).timeout
	var dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/issue_number", "1775")
	settings.set_setting("gonggong/request_id", "gonggong-ai-workbench-plan1-r03")
	settings.set_setting("ai_chat/parallel_work_orders_config", OS.get_environment("R03_CONFIG"))
	dock.set_runtime_field("node", OS.get_environment("R03_NODE"))
	dock.set_runtime_field("workflow_python", OS.get_environment("R03_PYTHON"))
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for name in ["AllowTools", "AutoApplyFileChanges", "AutoExecuteCommands"]:
		dock.get_ai_settings_control().find_child(name, true, false).button_pressed = true
	dock.find_child("SpawnWorkOrderAgents", true, false).pressed.emit()
	var dialog = dock.find_child("WorkOrderConfirmation", true, false)
	if not dialog.visible:
		for label in dock.find_children("*", "RichTextLabel", true, false):
			print(label.get_parsed_text().right(512))
		push_error("Native work-order confirmation missing")
		quit(1)
		return
	dialog.get_ok_button().pressed.emit()
	var folder = OS.get_environment("R03_DIR")
	var deadline = Time.get_ticks_msec() + 80000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists(folder.path_join("close-editor")):
			print("R03_NORMAL_EDITOR_QUIT")
			quit()
			return
		await create_timer(0.05).timeout
	push_error("Timed out waiting for both process trees")
	quit(1)
