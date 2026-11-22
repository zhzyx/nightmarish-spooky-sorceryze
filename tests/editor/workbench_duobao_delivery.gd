extends "res://g13_probe.gd"


func current_state(dialog, text: String) -> bool:
	var deadline := Time.get_ticks_msec() + 20000
	while not text in dialog.status.text and Time.get_ticks_msec() < deadline:
		await create_timer(0.15).timeout
		await press(dialog, "刷新检查")
	return text in dialog.status.text


func run() -> void:
	await create_timer(1.0).timeout
	var chat = root.find_child("AI Chat", true, false)
	assert(chat.set_runtime_field("workflow_python", OS.get_environment("G13_PYTHON")).is_empty())
	await create_timer(0.4).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	button(panel, "多宝合入").pressed.emit()
	await process_frame
	var dialog = panel.duobao_merge_dialog
	var phase := OS.get_environment("DUOBAO_PHASE")
	var out := {"phase": phase}
	if phase == "resolve":
		dialog.source.text = "feature"
		dialog.target.text = "main"
		dialog.issue.text = OS.get_environment("DUOBAO_ISSUE")
		await press(dialog, "读取来源候选")
		await press(dialog, "发起合入请求")
		out.original = dialog.request_id.text
		assert(await current_state(dialog, "存在合入冲突"), dialog.status.text)
		await press(dialog, "查看冲突差异")
		assert(dialog.conflict_box.visible and dialog.conflict_path.get_item_text(0) == "asset.txt", dialog.status.text)
		assert("source line" in dialog.versions.text and "target line" in dialog.versions.text)
		dialog.resolved_text.text = "resolved line\n"
		await press(dialog, "采用编辑内容")
		await press(dialog, "重建并检查候选")
		assert(await current_state(dialog, "检查通过"), dialog.status.text)
		assert(out.original != dialog.request_id.text and "退出码 0" in dialog.status.text)
		out.branch = dialog.source.text
	else:
		dialog.request_id.text = OS.get_environment("DUOBAO_REQUEST")
		await press(dialog, "刷新检查")
		if phase == "reject":
			await press(dialog, "要求修改")
			assert("要求修改" in dialog.status.text, dialog.status.text)
		elif phase == "denied":
			await press(dialog, "批准候选")
			assert("403" in dialog.status.text, dialog.status.text)
			await press(dialog, "交付并回写工单")
			assert("403" in dialog.status.text, dialog.status.text)
		elif phase == "approve":
			await press(dialog, "批准候选")
			assert("已批准" in dialog.status.text, dialog.status.text)
		elif phase == "deliver":
			await press(dialog, "交付并回写工单")
			assert("已合入目标分支" in dialog.status.text and OS.get_environment("DUOBAO_ISSUE") in dialog.target_tip.text, dialog.status.text)
			out.receipt = dialog.target_tip.text
			await press(dialog, "交付并回写工单")
			assert(out.receipt == dialog.target_tip.text, dialog.status.text)
	out.id = dialog.request_id.text
	out.candidate = dialog.candidate.text
	out.status = dialog.status.text
	print("DUOBAO_DELIVERY=", JSON.stringify(out))
	quit()
