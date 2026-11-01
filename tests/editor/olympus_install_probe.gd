extends SceneTree

var frames := 0

func _process(_delta: float) -> bool:
	frames += 1
	var page := root.find_child("OlympusPage", true, false)
	if page:
		var fields: Array[LineEdit] = []
		for field in page.get_children():
			if field is LineEdit:
				fields.append(field)
		var expected_python := OS.get_environment("OLYMPUS_EXPECTED_WORKSPACE").path_join("project/runtime/python/python.exe").replace("\\", "/").simplify_path().to_lower()
		if FileAccess.file_exists(expected_python) and (fields.size() < 2 or fields[1].text.replace("\\", "/").simplify_path().to_lower() != expected_python):
			push_error("Installed editor failed to find workspace Python without IDE environment")
			quit(1)
			return false
		var cli := root.find_child("CLIBridge", true, false)
		var expected_cli := OS.get_environment("OLYMPUS_EXPECTED_WORKSPACE").path_join("tools/codebuddy_cli/godot_bridge.js").replace("\\", "/").simplify_path().to_lower()
		if not cli or cli.text.replace("\\", "/").simplify_path().to_lower() != expected_cli:
			push_error("Installed editor CLI default escaped source workspace")
			quit(1)
			return false
		for child in page.get_children():
			if child is LineEdit:
				var expected := OS.get_environment("OLYMPUS_EXPECTED_WORKSPACE").replace("\\", "/").simplify_path()
				if child.text.replace("\\", "/").simplify_path().to_lower() != expected.to_lower():
					push_error("Installed editor discovered the wrong workspace")
					quit(1)
				else:
					print("OLYMPUS_INSTALLED_WORKSPACE_DISCOVERY_OK")
					quit(0)
				return false
	if frames > 600:
		push_error("Olympus page did not appear")
		quit(1)
	return false
