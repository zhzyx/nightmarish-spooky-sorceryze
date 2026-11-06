@tool
extends EditorPlugin
var panel
func _enter_tree():
	panel = preload("workbench.gd").new()
	add_control_to_bottom_panel(panel, "AINative")
func _exit_tree():
	remove_control_from_bottom_panel(panel)
	panel.queue_free()
