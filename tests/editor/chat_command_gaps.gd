@tool
extends SceneTree

var dock: Node
var serial := 0

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(0.5).timeout
	dock = root.find_child("AI Chat", true, false)
	assert(dock != null)
	var image := Image.create(2, 2, false, Image.FORMAT_RGBA8)
	image.fill(Color.RED)
	assert(image.save_png("res://tiny.png") == OK)
	assert(image.save_jpg("res://tiny.jpg") == OK)
	assert(image.save_webp("res://tiny.webp", false) == OK)
	var settings = dock.get_ai_settings_control()
	settings.find_child("APIKey", true, false).text = "private-fixture-secret"
	settings.find_child("AllowTools", true, false).button_pressed = true
	settings.find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	for unused in 600:
		if not dock.find_child("Send", true, false).disabled:
			break
		await create_timer(0.02).timeout
	assert(not dock.find_child("Send", true, false).disabled)
	write_json("res://ready.json", {"pid": OS.get_process_id()})
	while true:
		if FileAccess.file_exists("res://fixture-command.json"):
			var command = JSON.parse_string(FileAccess.get_file_as_string("res://fixture-command.json"))
			if command is Dictionary and command.get("serial", 0) > serial:
				serial = command.serial
				var action: String = command.action
				var result := {"ok": true}
				if action == "approve":
					var dialog = dock.find_child("AIFileApproval", true, false)
					result["visible"] = dialog.visible
					if dialog.visible:
						dialog.confirmed.emit()
				elif action == "reject":
					var dialog = dock.find_child("AIFileApproval", true, false)
					result["visible"] = dialog.visible
					if dialog.visible:
						dialog.canceled.emit()
				elif action == "draft":
					dock.find_child("ChatInput", true, false).text = command.value
				elif action == "change_image":
					var changed := Image.create(2, 2, false, Image.FORMAT_RGBA8)
					changed.fill(Color.BLUE)
					assert(changed.save_png("res://tiny.png") == OK)
				elif action == "tools":
					settings.find_child("AllowTools", true, false).button_pressed = command.value
				elif action == "state":
					var tabs = dock.find_child("AgentTabs", true, false)
					result["title"] = tabs.get_tab_title(tabs.current_tab)
					result["tab_count"] = tabs.tab_count
					result["draft"] = dock.find_child("ChatInput", true, false).text
					result["send_disabled"] = dock.find_child("Send", true, false).disabled
				elif action == "exit":
					write_json("res://ack-%d.json" % serial, result)
					quit()
					return
				write_json("res://ack-%d.json" % serial, result)
		await create_timer(0.01).timeout
