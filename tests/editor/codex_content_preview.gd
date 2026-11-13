@tool
extends SceneTree

var dock
var layout
var proof
var workspace
var answers_seen := 0

func _initialize():
	run.call_deferred()

func fail(reason: String):
	print("READBATCH_FAILED ", reason)
	for label in root.find_children("MessageText*", "RichTextLabel", true, false):
		var text: String = label.get_parsed_text()
		if text.contains("错误") or text.contains("失败") or text.contains("拒绝") or text.contains("Error"):
			print("READBATCH_DIAGNOSTIC ", text.left(400))
	quit(2)

func observe(expected: String, start: int, round_number: int):
	var deadline := start + 420000
	while Time.get_ticks_msec() < deadline:
		await create_timer(0.15).timeout
		var replies = layout.find_children("AIAnswer*", "RichTextLabel", true, false)
		if replies.size() <= answers_seen or not layout.find_child("Stop", true, false).disabled:
			continue
		var actual: String = replies[-1].get_parsed_text().strip_edges()
		if actual != expected:
			print("READBATCH_UNEXPECTED_LENGTH ", actual.length())
			return false
		answers_seen = replies.size()
		print("READBATCH_ROUND ", JSON.stringify({"round":round_number,"ms":Time.get_ticks_msec()-start,"transport":dock.get_meta("cli_response_transport", {})}))
		return true
	return false

func run():
	dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace", OS.get_environment("TS_WORKSPACE"))
	settings.set_setting("gonggong/issue_number", "")
	settings.set_setting("gonggong/request_id", "")
	dock.set_runtime_field("workflow_python", OS.get_environment("TS_PYTHON"))
	var ai = dock
	var env_ui = dock.get_environment_settings_control()
	var backend = ai.find_child("AIBackend", true, false)
	backend.select(2)
	backend.item_selected.emit(2)
	for pair in [["CLINode","TS_NODE"], ["CodexEntry","TS_CODEX"]]:
		var field = env_ui.find_child(pair[0], true, false)
		field.text = OS.get_environment(pair[1])
		field.text_changed.emit(field.text)
	env_ui.find_child("CLIBridge", true, false).text = OS.get_environment("TS_BRIDGE")
	for pair in [["CodexModel", OS.get_environment("TS_MODEL")], ["AllowTools",true], ["AutoApplyFileChanges",false], ["AutoExecuteCommands",false], ["EngineAutoRestart",false]]:
		var widget = ai.find_child(pair[0], true, false)
		if not widget:
			widget = env_ui.find_child(pair[0], true, false)
		if pair[0] == "CodexModel":
			widget.text = pair[1]
		else:
			widget.button_pressed = pair[1]
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	workspace = root.find_child("DaqianWorkspace", true, false)
	await workspace.refresh()
	if workspace.actor.is_empty():
		fail("live account unavailable " + workspace.notice.text)
		return
	var binding := {"url":"https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/652","number":652,"request":"tianshu-safe-preview"}
	var err: String = workspace._bind_conversation(binding)
	if not err.is_empty():
		fail(err)
		return
	workspace._mount_conversation(binding)
	layout = workspace.conversation_host.find_child("ChatLayout", true, false)
	if not layout:
		fail("mounted conversation layout missing")
		return

	var prompt := "只读验证。不要调用工具。在 content 返回100行，每行为：预览验证：这是正在生成的安全纯文本。最后一行为 PREVIEW_FINISHED。不要解释。"
	var start := Time.get_ticks_msec()
	err = dock.open_daqian_chat(binding.url,652,binding.request,prompt,false,{"backend":2,"id":OS.get_environment("TS_MODEL")},true)
	if not err.is_empty():
		fail(err)
		return
	var saw_preview := false
	while Time.get_ticks_msec() - start < 420000:
		await create_timer(0.03).timeout
		for label in layout.find_children("*", "Label", true, false):
			if label.text.contains("正在生成（预览）") and label.text.contains("预览验证") and not layout.find_child("Stop",true,false).disabled:
				if not saw_preview:
					print("PREVIEW_VISIBLE ", Time.get_ticks_msec()-start)
				saw_preview = true
		var replies = layout.find_children("AIAnswer*", "RichTextLabel", true, false)
		if replies.size() > 0 and layout.find_child("Stop",true,false).disabled:
			if not saw_preview or not replies[-1].get_parsed_text().contains("PREVIEW_FINISHED"):
				fail("preview or final answer missing")
				return
			print("PREVIEW_FINAL ", Time.get_ticks_msec()-start)
			await cancel_and_followup(binding)
			return
	fail("preview timeout")

func cancel_and_followup(binding: Dictionary):
	var composer = layout.find_child("ChatInput", true, false)
	var send = layout.find_child("Send", true, false)
	var stop = layout.find_child("Stop", true, false)
	composer.text = "不要调用工具。输出1000行，每行：取消预览验证。"
	send.pressed.emit()
	var start := Time.get_ticks_msec()
	var observed := false
	while Time.get_ticks_msec()-start < 420000:
		await create_timer(0.03).timeout
		var status = layout.find_child("AIProgressStatus",true,false)
		if status and status.text.contains("正在生成（预览）") and not stop.disabled:
			observed = true
			stop.pressed.emit()
			break
	if not observed:
		fail("cancellation preview not observed")
		return
	await create_timer(1.0).timeout
	var status = layout.find_child("AIProgressStatus",true,false)
	if not stop.disabled or status.text.contains("正在生成（预览）"):
		fail("cancel did not clear preview")
		return
	print("PREVIEW_CANCEL_CLEARED")
	var before: int = layout.find_children("AIAnswer*","RichTextLabel",true,false).size()
	composer.text = "不要调用工具，仅回复 CANCEL_FOLLOWUP_OK。"
	send.pressed.emit()
	start = Time.get_ticks_msec()
	while Time.get_ticks_msec()-start < 420000:
		await create_timer(0.1).timeout
		var replies = layout.find_children("AIAnswer*","RichTextLabel",true,false)
		if replies.size() > before and stop.disabled:
			if replies[-1].get_parsed_text().strip_edges() != "CANCEL_FOLLOWUP_OK":
				fail("followup response mismatch")
				return
			print("PREVIEW_CANCEL_FOLLOWUP_OK")
			quit(0)
			return
	fail("cancel followup timeout")
