@tool
extends EditorPlugin

var page: EditorDock

func _enter_tree() -> void:
	page = EditorDock.new()
	page.title = "Project Brief"
	page.default_slot = EditorDock.DOCK_SLOT_MAIN_SCREEN
	page.available_layouts = EditorDock.DOCK_LAYOUT_MAIN_SCREEN
	var fields := VBoxContainer.new()
	fields.name = "Brief"
	page.add_child(fields)
	var settings := EditorInterface.get_editor_settings()
	var summary := _field(fields, "Summary", settings.get_project_metadata("project_brief", "summary", "First playable"))
	summary.text_changed.connect(func(value): settings.set_project_metadata("project_brief", "summary", value))
	var milestone := _field(fields, "Milestone", "Prototype")
	milestone.editable = false
	_field(fields, "PrivateNote", "")
	page.set_meta("workbench_fields", {"Brief/Summary": "replace_text", "Brief/Milestone": "read"})
	add_dock(page)

func _field(fields: VBoxContainer, key: String, value: String) -> LineEdit:
	var label := Label.new()
	label.text = key.capitalize()
	fields.add_child(label)
	var edit := LineEdit.new()
	edit.name = key
	edit.text = value
	fields.add_child(edit)
	return edit

func _exit_tree() -> void:
	remove_dock(page)
	page.queue_free()
