@tool
extends SceneTree

var dock: Node
var animation: Animation
class SideEffectLoader extends ResourceFormatLoader:
	var mode := ""
	var calls := 0
	func _get_recognized_extensions() -> PackedStringArray:
		return PackedStringArray(["tres"])
	func _handles_type(_type: StringName) -> bool:
		return true
	func _recognize_path(path: String, _type: StringName) -> bool:
		return path.get_file().begins_with("loader-")
	func _get_resource_type(_path: String) -> String:
		return "Gradient"
	func _load(_path: String, _original: String, _threads: bool, _cache: int) -> Variant:
		calls += 1
		var scene := EditorInterface.get_edited_scene_root()
		var node := scene.get_node("Line")
		if mode == "delete" or mode == "replace":
			node.free()
			if mode == "replace":
				var replacement := Line2D.new()
				replacement.name = "Line"
				scene.add_child(replacement)
				replacement.owner = scene
		else:
			node.gradient = Gradient.new()
		return Gradient.new()

var loader: SideEffectLoader
var folder := OS.get_environment("SCENE_COMMAND_DIR")

func write_json(name: String, value: Dictionary) -> void:
	var path := folder.path_join(name)
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		quit(1)
		return
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	var fs := EditorInterface.get_resource_filesystem()
	while fs.is_scanning() or fs.is_importing():
		await process_frame
	write_json("ready.json", {"ok": true})
	var deadline := Time.get_ticks_msec() + 180000
	while Time.get_ticks_msec() < deadline:
		var path := folder.path_join("command.json")
		if FileAccess.file_exists(path):
			var command: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
			DirAccess.remove_absolute(path)
			var answer := {"ok": true}
			var scene := EditorInterface.get_edited_scene_root()
			match command.action:
				"approve":
					var dialog := root.find_child("AIFileApproval", true, false)
					answer["visible"] = dialog != null and dialog.visible
					if answer.visible:
						dialog.hide()
						dialog.confirmed.emit()
				"loader":
					if loader:
						ResourceLoader.remove_resource_format_loader(loader)
					loader = SideEffectLoader.new()
					loader.mode = command.value
					ResourceLoader.add_resource_format_loader(loader, true)
				"loader_clear":
					ResourceLoader.remove_resource_format_loader(loader)
					loader = null
					if scene.get_node_or_null("Line") == null:
						var line := Line2D.new()
						line.name = "Line"
						scene.add_child(line)
						line.owner = scene
				"metadata_reference":
					var reference := Node2D.new()
					reference.name = "Reference"
					var value: Variant = NodePath("../Branch/Leaf")
					match command.value:
						"array": value = [NodePath("../Branch/Leaf")]
						"dictionary": value = {"target": NodePath("../Branch/Leaf")}
						"key": value = {NodePath("../Branch/Leaf"): true}
						"scalar": value = 7
					reference.set_meta("path", value)
					scene.add_child(reference)
					reference.owner = scene
				"script_reference":
					var reference := Node2D.new()
					reference.name = "Reference"
					reference.set_script(load("res://reference-%s.gd" % command.value))
					scene.add_child(reference)
					reference.owner = scene
				"script_reference_clear":
					scene.get_node("Reference").free()
				"animation":
					var player := AnimationPlayer.new()
					player.name = "Animations"
					scene.add_child(player)
					player.owner = scene
					animation = Animation.new()
					var track := animation.add_track(Animation.TYPE_VALUE)
					animation.track_set_path(track, NodePath("Branch/Leaf:position"))
					animation.track_insert_key(track, 0.0, Vector2(2, 3))
					var library := AnimationLibrary.new()
					library.add_animation("move", animation)
					player.add_animation_library("", library)
				"undo", "redo":
					var manager := EditorInterface.get_editor_undo_redo()
					var history := manager.get_history_undo_redo(manager.get_object_history_id(scene))
					answer["changed"] = history.undo() if command.action == "undo" else history.redo()
				"history_noop", "history_branch":
					var manager := EditorInterface.get_editor_undo_redo()
					var history := manager.get_history_undo_redo(manager.get_object_history_id(scene))
					if command.action == "history_branch":
						history.undo()
					manager.create_action("fixture no-op", UndoRedo.MERGE_DISABLE, scene)
					manager.add_do_property(scene, "position", scene.position)
					manager.add_undo_property(scene, "position", scene.position)
					manager.commit_action()
					answer["version"] = history.get_version()
				"editable":
					scene.set_editable_instance(scene.get_node("Instance"), command.value)
				"mutate":
					scene.get_node(command.path).position = Vector2(999, 999)
				"gradient_mutate":
					var gradient: Gradient = scene.get_node("Line").gradient
					gradient.colors = PackedColorArray([Color(randf(), 0.2, 0.4), Color.BLUE])
				"gradient_metadata":
					var gradient: Gradient = scene.get_node("Line").gradient
					if gradient.has_meta("nested"):
						gradient.remove_meta("nested")
					if command.value == "script":
						var child := Gradient.new()
						child.set_script(load("res://resource_behavior.gd"))
						gradient.set_meta("nested", {"array": [child]})
					elif command.value == "cycle":
						gradient.set_meta("nested", [gradient])
				"tools":
					dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = command.value
				"consultation":
					dock.find_child("ConsultationOnly", true, false).button_pressed = command.value
				"snapshot":
					var node := scene.get_node_or_null(String(command.get("path", ".")))
					answer["exists"] = node != null
					answer["loader_calls"] = loader.calls if loader else 0
					if node:
						answer["instance"] = node.get_instance_id()
						answer["owner"] = String(scene.get_path_to(node.owner)) if node.owner else ""
						answer["position"] = [node.position.x, node.position.y] if node is Node2D else null
						answer["script"] = node.get_script() != null
						answer["hijacks"] = int(node.get("hijacks")) if node.get_script() and node.get("hijacks") != null else 0
						if node.name == "Reference":
							if node.has_meta("path"):
								answer["metadata_path"] = str(node.get_meta("path"))
							elif node.get("has_custom_getter"):
								answer["reference_getter_calls"] = int(node.get("getter_calls"))
							else:
								answer["reference_path"] = str(node.get("path"))
						answer["self_connected"] = node.is_connected("visibility_changed", Callable(node, "_on_pressed")) if node.get_script() else false
						if node is Line2D:
							answer["gradient"] = node.gradient != null
						if node is Button:
							answer["connected"] = node.is_connected("pressed", Callable(scene.get_node("Receiver"), "_on_pressed"))
						if node.has_node("Leaf"):
							answer["leaf_owner"] = String(scene.get_path_to(node.get_node("Leaf").owner))
					answer["reference"] = String(scene.get_node("Tracker").remote_path) if scene.has_node("Tracker") else ""
					answer["fired"] = int(scene.get_node("Receiver").fired) if scene.has_node("Receiver") else 0
					answer["track"] = String(animation.track_get_path(0)) if animation and animation.get_track_count() else ""
					answer["tracks"] = animation.get_track_count() if animation else 0
					answer["scanning"] = fs.is_scanning() or fs.is_importing()
					answer["playing"] = EditorInterface.is_playing_scene()
				"finish":
					write_json("ack-%d.json" % int(command.id), answer)
					EditorInterface.get_editor_undo_redo().clear_history()
					quit(0)
					return
			await process_frame
			write_json("ack-%d.json" % int(command.id), answer)
		await process_frame
	quit(1)
