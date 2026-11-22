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
	page.set_meta("workbench_field_checks", {"Brief/Summary": _check_summary})
	var validate := Button.new()
	validate.name = "ValidateSummary"
	validate.text = "验证当前修改"
	fields.add_child(validate)
	var status := Label.new()
	status.name = "SummaryValidation"
	fields.add_child(status)
	summary.text_changed.connect(func(_value): status.text = "")
	validate.pressed.connect(func():
		var receipt := EditorDock.validate_workbench_field(summary)
		status.text = "验证不可用" if not receipt.has("passed") else (
			("%s · %s" % ["通过" if receipt.passed else "未通过", receipt.revision])
		)
	)
	add_dock(page)

func _check_summary(value: String) -> bool:
	return not value.strip_edges().is_empty() and value.length() <= 240

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
