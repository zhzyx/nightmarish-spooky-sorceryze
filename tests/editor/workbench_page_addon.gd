@tool
extends SceneTree

func _initialize() -> void:
	_observe.call_deferred()

func _observe() -> void:
	await create_timer(1).timeout
	var modes := []
	for dock in root.find_children("*", "EditorDock", true, false):
		if dock.title == "Project Brief":
			modes.append(dock.get_meta("workbench_fields")["Brief/Summary"])
	var script: Script = load("res://addons/project_brief/plugin.gd")
	var observation := {
		"configured": "res://addons/project_brief/plugin.cfg" in ProjectSettings.get_setting("editor_plugins/enabled", []),
		"enabled": EditorInterface.is_plugin_enabled("project_brief"),
		"script_base": str(script.get_instance_base_type()),
		"summary_modes": modes,
	}
	print("ADDON_OBSERVATION ", JSON.stringify(observation))
	quit()
