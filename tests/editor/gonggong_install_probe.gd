extends SceneTree

var frames := 0

func normalized_path(value: String) -> String:
	var path := value.replace("\\", "/").simplify_path()
	return path.to_lower() if OS.get_name() == "Windows" else path

func _process(_delta: float) -> bool:
	frames += 1
	var dock := root.find_child("AI Chat", true, false)
	var settings: Control = dock.get_environment_settings_control() if dock else null
	if not settings:
		if frames > 600:
			push_error("GongGong environment settings did not appear")
			quit(1)
		return false

	var workspace := settings.find_child("GongGongWorkspace", true, false) as LineEdit
	var python := settings.find_child("GongGongPython", true, false) as LineEdit
	var cli := settings.find_child("CLIBridge", true, false) as LineEdit
	var expected := OS.get_environment("GONGGONG_EXPECTED_WORKSPACE")
	var expected_python := expected.path_join("project/runtime/python/python.exe")
	if not workspace or normalized_path(workspace.text) != normalized_path(expected):
		push_error("Installed editor discovered the wrong workspace")
	elif not python or (FileAccess.file_exists(expected_python) and normalized_path(python.text) != normalized_path(expected_python)):
		push_error("Installed editor failed to find workspace Python without IDE environment")
	elif not cli or normalized_path(cli.text) != normalized_path(expected.path_join("tools/codebuddy_cli/godot_bridge.js")):
		push_error("Installed editor CLI default escaped source workspace")
	else:
		print("GONGGONG_INSTALLED_WORKSPACE_DISCOVERY_OK")
		quit(0)
		return false
	quit(1)
	return false
