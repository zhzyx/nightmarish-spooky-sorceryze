@tool
extends SceneTree

var control: AIChatEditorControl
var page: VBoxContainer
var line: LineEdit
var capacity_page: Control
var animation: Animation
var popup: Window
var dock: Node
var errors: Array[String] = []

func check(value: bool, label: String) -> void:
	if not value:
		errors.append(label)

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1).timeout
	control = AIChatEditorControl.get_singleton()
	dock = root.find_child("AI Chat", true, false)
	check(control != null and dock != null, "control available")
	if not errors.is_empty():
		write_json("res://ready.json", {"errors": errors})
		quit(1)
		return
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = false
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	var gradient := Gradient.new()
	check(ResourceSaver.save(gradient, "res://fixture-gradient.tres") == OK, "resource fixture saved")
	var scene_root := Node.new()
	scene_root.name = "CoverageScene"
	for i in 43:
		var child := Node.new()
		child.name = "Child%d" % i
		scene_root.add_child(child)
		child.owner = scene_root
	var packed := PackedScene.new()
	packed.pack(scene_root)
	ResourceSaver.save(packed, "res://fixture-scene.tscn")
	scene_root.free()
	page = VBoxContainer.new()
	page.name = "CommandCoveragePage"
	page.set_meta("ai_control_page", true)
	page.size = Vector2(400, 1000)
	EditorInterface.get_base_control().add_child(page)
	for i in 45:
		var added := LineEdit.new()
		added.name = "CoverageInput%02d" % i
		added.text = "original"
		page.add_child(added)
		if i == 0:
			line = added
	check(control.register_target("plugin.coverage_alias", line, "Coverage alias", "Coverage page"), "explicit alias registered")
	await process_frame
	var found := control.find_targets("CoverageInput00", 1)
	var id: String = found[0].id if not found.is_empty() else ""
	check(not id.is_empty(), "fixture target discovery")
	write_json("res://ready.json", {"errors": errors, "target": id})
	var deadline := Time.get_ticks_msec() + 120000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists("res://command.json"):
			var cmd: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://command.json"))
			DirAccess.remove_absolute("res://command.json")
			match cmd.action:
				"run_config":
					ProjectSettings.set_setting("editor/run/main_run_args", "--headless --max-fps 30 --quit-after 180")
					ProjectSettings.save()
				"models":
					var picker := dock.get_ai_settings_control().find_child("ModelPicker", true, false) as OptionButton
					picker.clear()
					for i in 150:
						picker.add_item("Fixture model %d" % i)
						picker.set_item_metadata(i, "fixture-%d" % i)
					picker.select(0)
				"model_replace":
					var picker := dock.get_ai_settings_control().find_child("ModelPicker", true, false) as OptionButton
					picker.set_item_metadata(125, "changed-model")
				"animation":
					var scene := EditorInterface.get_edited_scene_root()
					var target := Node2D.new()
					target.name = "Animated"
					scene.add_child(target)
					target.owner = scene
					var player := AnimationPlayer.new()
					player.name = "Animations"
					scene.add_child(player)
					player.owner = scene
					animation = Animation.new()
					var track := animation.add_track(Animation.TYPE_VALUE)
					animation.track_set_path(track, NodePath("Animated:position"))
					animation.track_insert_key(track, 0, Vector2(2, 3))
					var library := AnimationLibrary.new()
					library.add_animation("move", animation)
					player.add_animation_library("", library)
				"undo":
					var manager := EditorInterface.get_editor_undo_redo()
					manager.get_history_undo_redo(manager.get_object_history_id(EditorInterface.get_edited_scene_root())).undo()
				"capacity_targets", "capacity_scan":
					if is_instance_valid(capacity_page):
						capacity_page.free()
					capacity_page = Control.new()
					capacity_page.name = "CapacityFixture"
					capacity_page.set_meta("ai_control_page", true)
					EditorInterface.get_base_control().add_child(capacity_page)
					capacity_page.hide()
					for i in (8300 if cmd.action == "capacity_targets" else 50010):
						var child: Node = Button.new() if cmd.action == "capacity_targets" else Node.new()
						child.name = "CapacityButton%d" % i if cmd.action == "capacity_targets" else "CapacityNode%d" % i
						capacity_page.add_child(child)
				"capacity_clear":
					if is_instance_valid(capacity_page):
						capacity_page.free()
				"line":
					line.text = cmd.value
				"alias_secret":
					line.secret = cmd.value
				"popup":
					popup = Window.new()
					popup.name = "CoveragePopup"
					EditorInterface.get_base_control().add_child(popup)
					var field := LineEdit.new()
					field.name = "CoveragePopupInput"
					popup.add_child(field)
					popup.popup(Rect2i(0, 0, 200, 100))
				"popup_close":
					popup.hide()
				"approve":
					var dialog := root.find_child("AIFileApproval", true, false)
					dialog.hide()
					dialog.confirmed.emit()
				"auto":
					dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = cmd.value
				"draft":
					dock.find_child("ChatInput", true, false).text = cmd.value
				"disk_change":
					var project := FileAccess.open("res://project.godot", FileAccess.READ_WRITE)
					project.seek_end()
					project.store_string("\n; intervening user edit\n")
					project.close()
			await process_frame
			var scene := EditorInterface.get_edited_scene_root()
			var selected: Node = scene.get_node_or_null(String(cmd.get("path", "Renamed"))) if scene else null
			write_json("res://ack-%d.json" % int(cmd.id), {"ok": true, "text": line.text, "node_exists": selected != null, "animation_track": String(animation.track_get_path(0)) if animation and animation.get_track_count() else null, "node_position": [selected.position.x, selected.position.y] if selected is Node2D else null})
		if FileAccess.file_exists("res://finish"):
			write_json("res://final.json", {"errors": errors, "text": line.text})
			page.queue_free()
			await process_frame
			quit(0 if errors.is_empty() else 1)
			return
		await process_frame
	quit(1)
