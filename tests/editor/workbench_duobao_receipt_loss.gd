extends "res://g13_probe.gd"


func run() -> void:
	await create_timer(1.0).timeout
	var chat = root.find_child("AI Chat", true, false)
	assert(chat.set_runtime_field("workflow_python", OS.get_environment("Q12_PYTHON")).is_empty())
	await create_timer(0.4).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	button(panel, "多宝合入").pressed.emit()
	await process_frame
	var dialog = panel.duobao_merge_dialog
	dialog.request_id.text = OS.get_environment("Q12_REQUEST")
	var phase := OS.get_environment("Q12_PHASE")
	await press(dialog, "刷新检查")
	if phase == "drop":
		await press(dialog, "交付并回写工单")
	else:
		await press(dialog, "读取目标分支")
	print("Q12_EDITOR=", JSON.stringify({
		"phase": phase, "pid": OS.get_process_id(), "request": dialog.request_id.text,
		"issue": dialog.issue.text, "status": dialog.status.text, "target": dialog.target_tip.text,
	}))
	quit()
