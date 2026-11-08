@tool
extends SceneTree
var serial := 0
var dock: Node
func write_json(path: String, value: Dictionary) -> void:
	var f := FileAccess.open(path + ".pending", FileAccess.WRITE)
	f.store_string(JSON.stringify(value))
	f.close()
	DirAccess.rename_absolute(path + ".pending", path)
func _initialize() -> void:
	run.call_deferred()
func run() -> void:
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	assert(dock)
	var settings = dock.get_ai_settings_control()
	settings.find_child("AllowTools", true, false).button_pressed = true
	settings.find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	write_json("res://ready.json", {"ok": true})
	while true:
		if FileAccess.file_exists("res://command.json"):
			var c = JSON.parse_string(FileAccess.get_file_as_string("res://command.json"))
			if c is Dictionary and c.serial > serial:
				serial = c.serial
				var result := {"ok": true}
				if c.action == "approve":
					var dialog = dock.find_child("AIFileApproval", true, false)
					result["visible"] = dialog.visible
					if dialog.visible: dialog.confirmed.emit()
				elif c.action == "tools":
					settings.find_child("AllowTools", true, false).button_pressed = c.value
				elif c.action == "exit":
					EditorInterface.stop_playing_scene()
					write_json("res://ack-%d.json" % serial, result)
					quit()
					return
				write_json("res://ack-%d.json" % serial, result)
		await create_timer(0.01).timeout
