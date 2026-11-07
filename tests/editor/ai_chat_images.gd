@tool
extends SceneTree

var dock
var chat_input: TextEdit
var send_button: Button
var messages: VBoxContainer
var attachments: HFlowContainer
var picker: FileDialog
var preview: AcceptDialog
var image_path: String
var second_path: String

func _initialize():
	_run.call_deferred()

func _check(condition: bool, reason: String) -> bool:
	if not condition:
		push_error(reason)
		quit(1)
	return condition

func _text() -> String:
	var text = ""
	for label in messages.find_children("*", "RichTextLabel", true, false):
		text += label.get_parsed_text() + "\n"
	return text

func _count(parent: Node) -> int:
	return parent.find_children("ImageThumbnail", "Button", true, false).size()

func _select(paths: PackedStringArray) -> void:
	picker.files_selected.emit(paths)
	picker.hide()

func _send(text: String, expected: String) -> bool:
	chat_input.text = text
	send_button.pressed.emit()
	var deadline = Time.get_ticks_msec() + 15000
	while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	if expected not in _text():
		print(_text())
	return _check(dock.find_child("Stop", true, false).disabled and expected in _text(), "Image response missing: " + expected)

func _switch(index: int) -> void:
	var agent = dock.find_child("AgentTabs", true, false) as TabBar
	agent.current_tab = index
	messages = dock.find_child("Messages", true, false)

func _run():
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	if not _check(dock != null, "AI chat dock missing"):
		return
	var cli = OS.get_environment("AI_CHAT_TEST_BACKEND") == "cli"
	var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
	backend.select(1 if cli else 0)
	backend.item_selected.emit(1 if cli else 0)
	if cli:
		dock.get_environment_settings_control().find_child("CLINode", true, false).text = OS.get_environment("AI_CHAT_TEST_NODE")
		dock.get_environment_settings_control().find_child("CLINode", true, false).text_changed.emit(dock.get_environment_settings_control().find_child("CLINode", true, false).text)
		dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("AI_CHAT_TEST_BRIDGE")
		dock.get_environment_settings_control().find_child("CLIEntry", true, false).text = OS.get_environment("AI_CHAT_TEST_ENTRY")
		dock.get_ai_settings_control().find_child("CLIModel", true, false).text = "mock-model"
	else:
		dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("AI_CHAT_TEST_URL")
		dock.get_ai_settings_control().find_child("APIModel", true, false).text = "mock-model"
		dock.get_ai_settings_control().find_child("APIKey", true, false).text = "test-secret"
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	chat_input = dock.find_child("ChatInput", true, false)
	send_button = dock.find_child("Send", true, false)
	messages = dock.find_child("Messages", true, false)
	attachments = dock.find_child("ImageAttachments", true, false)
	picker = dock.find_child("AIImagePicker", true, false)
	preview = dock.find_child("AIImagePreview", true, false)
	var image = Image.create(2048, 1024, false, Image.FORMAT_RGB8)
	image.fill(Color(0.1, 0.6, 0.8))
	image_path = ProjectSettings.globalize_path("res://test_picture.png")
	second_path = ProjectSettings.globalize_path("res://second_picture.png")
	if not _check(image.save_png(image_path) == OK, "Cannot save test image"):
		return
	image.fill(Color(0.8, 0.3, 0.2))
	image.save_png(second_path)
	dock.find_child("AddImage", true, false).pressed.emit()
	if not _check(picker.visible, "Image selection dialog did not open"):
		return
	_select([image_path, second_path])
	if not _check(_count(attachments) == 2, "Draft images missing"):
		return
	attachments.find_children("ImageThumbnail", "Button", true, false)[0].pressed.emit()
	var view = dock.find_child("PreviewImage", true, false)
	if not _check(preview.visible and view.texture != null and view.texture.get_width() == 1600, "Draft image preview or automatic resize failed"):
		return
	preview.hide()
	attachments.find_children("RemoveImage", "Button", true, false)[1].pressed.emit()
	if not _check(_count(attachments) == 1, "Image removal failed"):
		return
	_select([second_path])
	if not await _send("case:image_send", "IMAGE_SEND_OK"):
		return
	if not _check(_count(attachments) == 0 and _count(messages) == 2, "Sent images were not moved from draft to conversation"):
		return
	messages.find_children("ImageThumbnail", "Button", true, false)[0].pressed.emit()
	if not _check(preview.visible and view.texture != null, "Conversation image preview failed"):
		return
	preview.hide()
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
	_select([image_path])
	if not await _send("", "IMAGE_ONLY_OK"):
		return
	if not await _send("case:image_follow", "IMAGE_FOLLOW_OK"):
		return
	if cli:
		var entry = dock.get_environment_settings_control().find_child("CLIEntry", true, false)
		entry.text = entry.text.get_base_dir() + "/./" + entry.text.get_file()
		if not await _send("case:image_recovery", "IMAGE_RECOVERY_OK"):
			return
	_select([second_path])
	dock.find_child("AddAgent", true, false).pressed.emit()
	messages = dock.find_child("Messages", true, false)
	if not _check(_count(attachments) == 0 and _count(messages) == 0, "Agent B inherited Agent A images"):
		return
	if not await _send("case:image_agent_b", "IMAGE_AGENT_B_OK"):
		return
	_switch(0)
	if not _check(_count(attachments) == 1 and _count(messages) == 3, "Agent A image draft or history was lost"):
		return
	attachments.find_children("RemoveImage", "Button", true, false)[0].pressed.emit()
	if not await _send("case:image_agent_a", "IMAGE_AGENT_A_OK"):
		return
	_select([image_path])
	if not _check(dock.find_child("Clear", true, false) == null and _count(attachments) == 1 and _count(messages) == 3, "Removed new-conversation button is present or Agent A images were lost"):
		return
	_switch(1)
	if not _check(_count(attachments) == 0 and _count(messages) == 0, "Agent B inherited Agent A images after switching"):
		return
	if not await _send("case:image_agent_b_resume", "IMAGE_AGENT_B_RESUME_OK"):
		return
	var jpeg_path = ProjectSettings.globalize_path("res://test_picture.jpg")
	var webp_path = ProjectSettings.globalize_path("res://test_picture.webp")
	image.save_jpg(jpeg_path)
	image.save_webp(webp_path)
	_select([jpeg_path, webp_path, image_path, second_path, image_path])
	if not _check(_count(attachments) == 4, "JPEG/WebP loading or four-image limit failed"):
		return
	for index in range(4):
		attachments.find_children("RemoveImage", "Button", true, false)[0].pressed.emit()
	var pixels = PackedByteArray()
	pixels.resize(1024 * 1024 * 3)
	var rng = RandomNumberGenerator.new()
	rng.seed = 12345
	for index in range(pixels.size()):
		pixels[index] = rng.randi() & 255
	var noisy = Image.create_from_data(1024, 1024, false, Image.FORMAT_RGB8, pixels)
	noisy.save_png(image_path)
	_select([image_path])
	attachments.find_children("ImageThumbnail", "Button", true, false)[0].pressed.emit()
	if not _check(view.texture.get_width() < 1024 and view.texture.get_height() > 0, "Large image did not pass JPEG compression budget"):
		return
	preview.hide()
	attachments.find_children("RemoveImage", "Button", true, false)[0].pressed.emit()
	print("AI_CHAT_INTEGRATION_OK images=true backend=", OS.get_environment("AI_CHAT_TEST_BACKEND"))
	quit(0)
