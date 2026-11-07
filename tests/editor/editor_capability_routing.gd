@tool
extends SceneTree

var dock: Node
var control: AIChatEditorControl
var tabs: TabContainer
var page: VBoxContainer
var line: LineEdit
var text: TextEdit
var number: SpinBox
var choice: OptionButton
var presses := 0
var ids := {}


func target(label: String) -> String:
	for item in control.find_targets(label, 20):
		if item.get("display_name") == label:
			return item.id
	return ""


func snapshot() -> Dictionary:
	var daqian = root.find_child("Daqian", true, false)
	return { "ids": ids, "text": line.text, "multiline": text.text, "number": number.value,
		"daqian_title": daqian.get_title() if daqian else "missing",
		"selected": choice.selected, "presses": presses, "stop_disabled": dock.find_child("Stop", true, false).disabled,
		"approval": root.find_child("AIFileApproval", true, false).visible,
		"current_input": target("FixtureInput"),
		"password_targets": control.find_targets("FixturePassword", 20),
		"protected_targets": control.find_targets("FixtureProtected", 20) }


func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	control = AIChatEditorControl.get_singleton()
	if not dock or not control:
		quit(1)
		return
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = false
	tabs = TabContainer.new()
	tabs.name = "CapabilityFixtureTabs"
	tabs.size = Vector2(500, 500)
	EditorInterface.get_base_control().add_child(tabs)
	var empty := Control.new()
	empty.name = "FixtureEmpty"
	tabs.add_child(empty)
	page = VBoxContainer.new()
	page.name = "FixturePage"
	tabs.add_child(page)
	line = LineEdit.new()
	line.name = "FixtureInput"
	line.text = "original"
	page.add_child(line)
	text = TextEdit.new()
	text.name = "FixtureMultiline"
	text.custom_minimum_size.y = 60
	page.add_child(text)
	number = SpinBox.new()
	number.name = "FixtureNumber"
	number.value = 3
	page.add_child(number)
	choice = OptionButton.new()
	choice.name = "FixtureChoice"
	choice.add_item("First")
	choice.add_item("Second")
	page.add_child(choice)
	var button := Button.new()
	button.name = "FixtureButton"
	button.text = "FixturePress"
	button.pressed.connect(func(): presses += 1)
	page.add_child(button)
	var disabled := Button.new()
	disabled.text = "FixtureDisabled"
	disabled.disabled = true
	page.add_child(disabled)
	var password := LineEdit.new()
	password.name = "FixturePassword"
	password.secret = true
	page.add_child(password)
	var protected := LineEdit.new()
	protected.name = "FixtureProtected"
	protected.set_meta("ai_control_exclude", true)
	page.add_child(protected)
	await process_frame
	for label in ["FixturePage", "FixtureInput", "FixtureMultiline", "FixtureNumber", "First", "FixturePress", "FixtureDisabled"]:
		ids[label] = target(label)
	tabs.current_tab = 0
	write_json("res://ready.json", snapshot())
	var deadline := Time.get_ticks_msec() + 120000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists("res://finish"):
			write_json("res://final.json", snapshot())
			print("EDITOR_CAPABILITY_ROUTING_OK")
			tabs.queue_free()
			await process_frame
			quit(0)
			return
		if FileAccess.file_exists("res://command.json"):
			var cmd: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://command.json"))
			DirAccess.remove_absolute("res://command.json")
			match cmd.get("action", "snapshot"):
				"approve", "reject":
					var dialog = root.find_child("AIFileApproval", true, false)
					dialog.hide()
					if cmd.action == "approve":
						dialog.confirmed.emit()
					else:
						dialog.canceled.emit()
				"stop":
					dock.find_child("Stop", true, false).pressed.emit()
				"permission":
					dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = cmd.value
				"consultation":
					dock.find_child("ConsultationOnly", true, false).button_pressed = cmd.value
				"auto":
					dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = cmd.value
				"edit":
					line.text = "user-changed"
				"replace":
					var old := line
					page.remove_child(old)
					old.queue_free()
					line = LineEdit.new()
					line.name = "FixtureInput"
					line.text = "original"
					page.add_child(line)
				"reparent":
					button.reparent(text)
				"secret":
					line.secret = cmd.value
				"later":
					var later := VBoxContainer.new()
					later.name = "FixtureLaterPage"
					tabs.add_child(later)
					var added := LineEdit.new()
					added.name = "FixtureLaterInput"
					later.add_child(added)
				"duplicate_alias":
					for index in 2:
						var duplicate := LineEdit.new()
						duplicate.name = "DuplicateAlias%d" % index
						duplicate.set_meta("ai_control_id", "fixture_duplicate")
						page.add_child(duplicate)
			await process_frame
			write_json("res://ack-%d.json" % int(cmd.id), snapshot())
		await process_frame
	push_error("Capability fixture timed out")
	quit(1)
