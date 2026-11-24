extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func button(parent: Node, caption: String) -> Button:
	for child in parent.find_children("*", "Button", true, false):
		if child.text == caption and child.is_visible_in_tree():
			return child
	return null


func press(dialog, caption: String) -> void:
	var action := button(dialog, caption)
	assert(action != null and not action.disabled)
	action.pressed.emit()
	var deadline := Time.get_ticks_msec() + 20000
	while dialog.busy and Time.get_ticks_msec() < deadline:
		await create_timer(0.03).timeout
	assert(not dialog.busy)


func run() -> void:
	await create_timer(1.0).timeout
	var chat = root.find_child("AI Chat", true, false)
	assert(chat.set_runtime_field("workflow_python", OS.get_environment("G13_PYTHON")).is_empty())
	await create_timer(0.4).timeout
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	var entry := button(panel, "多宝合入")
	assert(entry != null)
	entry.pressed.emit()
	await process_frame
	var dialog = panel.duobao_merge_dialog
	var checks := {}
	checks.entry = dialog.visible and dialog.repository.text == "sample.git"
	var first := OS.get_environment("G13_OLD_ID").is_empty()
	var oid := OS.get_environment("G13_SOURCE")
	var target_sha := OS.get_environment("G13_TARGET")
	if not first:
		dialog.request_id.text = OS.get_environment("G13_OLD_ID")
		await press(dialog, "刷新检查")
		checks.stale = "检查已失效" in dialog.status.text and OS.get_environment("G13_OLD_SHA") in dialog.status.text
		await press(dialog, "发起合入请求")
		checks.old_rejected = "409" in dialog.status.text
	dialog.source.text = "feature/g13"
	dialog.target.text = "main"
	await press(dialog, "读取来源候选")
	checks.source = dialog.candidate.text == oid
	await press(dialog, "发起合入请求")
	checks.accepted = dialog.request_id.text.begins_with("mr_") and oid in dialog.status.text
	var received: String = dialog.request_id.text
	var expected := "检查通过" if first else "检查未通过"
	var until := Time.get_ticks_msec() + 25000
	while not expected in dialog.status.text and Time.get_ticks_msec() < until:
		await create_timer(0.15).timeout
		await press(dialog, "刷新检查")
	checks.checks_from_service = expected in dialog.status.text and ("退出码 0" if first else "退出码 1") in dialog.status.text
	var summary: String = dialog.status.text
	await press(dialog, "发起合入请求")
	checks.replayed = dialog.request_id.text == received and expected in dialog.status.text
	await press(dialog, "读取目标分支")
	checks.target = target_sha in dialog.target_tip.text and dialog.target.text == "main"
	print("G13_RESULT=", JSON.stringify({"checks": checks, "id": received, "summary": summary, "target_readback": dialog.target_tip.text}))
	if checks.values().has(false):
		push_error(str(checks) + " " + dialog.status.text)
		quit(1)
	else:
		quit()
