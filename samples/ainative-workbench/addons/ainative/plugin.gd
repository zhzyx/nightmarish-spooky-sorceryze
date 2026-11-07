@tool
extends EditorPlugin
var panel
func _enter_tree():
	# The engine-native page owns the workbench in current editor builds.
	if ClassDB.class_exists("AINativeEditorPlugin"):
		return
	panel = preload("workbench.gd").new()
	add_control_to_bottom_panel(panel, "AINative")
func _exit_tree():
	if panel == null:
		return
	remove_control_from_bottom_panel(panel)
	panel.queue_free()
