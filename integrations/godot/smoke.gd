extends SceneTree

func _initialize():
	call_deferred("verify")

func verify():
	var panel = root.find_child("OlympusPage", true, false)
	if panel == null:
		push_error("Olympus page missing")
		quit(1)
		return
	var fields = []
	for child in panel.get_children():
		if child is LineEdit:
			fields.append(child)
	fields[0].text = OS.get_environment("OLYMPUS_WORKSPACE")
	fields[1].text = OS.get_environment("OLYMPUS_PYTHON")
	for action in ["读取框架状态", "校验赫尔墨斯数据"]:
		for child in panel.get_children():
			if child is Button and child.text == action:
				child.pressed.emit()
		var result = null
		for attempt in range(200):
			await create_timer(0.1).timeout
			var content = panel.get_node("OlympusOutput").text
			if content.begins_with("{"):
				result = JSON.parse_string(content)
				break
		if result == null or not result.get("ok", false) or result.get("agent_execution_enabled", true):
			push_error("Olympus action failed: " + action)
			quit(1)
			return
	print("OLYMPUS_EDITOR_INTEGRATION_OK")
	quit(0)
