@tool
extends SceneTree

var dock: Node
var control: AIChatEditorControl
var victim: Node
var scene_widget: Tree
var scene_parent: Node
var scene_index := -1
var scene_row := -1
var ordinary_tree: Tree
var ordinary_edits := 0
var wrapper: VBoxContainer
var sequence := 0

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func target_for(node: Node, query: String) -> String:
	for entry in control.find_targets(query, 100):
		if int(entry.get("target_instance", 0)) == node.get_instance_id():
			return entry.id
	return ""

func scene_callback_attached() -> bool:
	for connection in scene_widget.get_signal_connection_list("item_edited"):
		var receiver = connection.callable.get_object()
		if receiver and receiver.is_class("SceneTreeEditor"):
			return true
	return false

func snapshot() -> Dictionary:
	return {
		"scene_target": target_for(scene_widget, "Tree"),
		"scene_row": scene_row,
		"scene_widget_visible": scene_widget.is_visible_in_tree(),
		"scene_callback_attached": scene_callback_attached(),
		"victim_name": str(victim.name),
		"ordinary_target": target_for(ordinary_tree, "OrdinaryGuardTree"),
		"ordinary_text": ordinary_tree.get_root().get_text(0),
		"ordinary_edits": ordinary_edits,
		"confirmation_visible": dock.find_child("AIFileApproval", true, false).visible,
	}

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1.0).timeout
	control = AIChatEditorControl.get_singleton()
	dock = root.find_child("AI Chat", true, false)
	assert(control and dock)
	var settings = dock.get_ai_settings_control()
	settings.find_child("AllowTools", true, false).button_pressed = true
	settings.find_child("AutoExecuteCommands", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	EditorInterface.open_scene_from_path("res://fixture.tscn")
	await create_timer(1.0).timeout
	victim = EditorInterface.get_edited_scene_root().get_node("Victim")
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(victim)
	await create_timer(0.5).timeout
	for node in root.find_children("*", "Tree", true, false):
		var ancestor = node.get_parent()
		while ancestor:
			if ancestor.is_class("SceneTreeEditor"):
				var item = node.get_root()
				var index := 0
				while item:
					if item.get_text(0) == "Victim" and item.is_editable(0) and item.is_selected(0):
						scene_widget = node
						scene_row = index
					item = item.get_next_in_tree()
					index += 1
				break
			ancestor = ancestor.get_parent()
	assert(scene_widget and scene_row >= 0)
	scene_parent = scene_widget.get_parent()
	scene_index = scene_widget.get_index()
	ordinary_tree = Tree.new()
	ordinary_tree.name = "OrdinaryGuardTree"
	ordinary_tree.size = Vector2(200, 120)
	EditorInterface.get_base_control().add_child(ordinary_tree)
	var ordinary_item = ordinary_tree.create_item()
	ordinary_item.set_text(0, "Ordinary")
	ordinary_item.set_editable(0, true)
	ordinary_tree.item_edited.connect(func(): ordinary_edits += 1)
	await process_frame
	write_json("res://ready.json", snapshot())
	while true:
		if FileAccess.file_exists("res://command.json"):
			var command = JSON.parse_string(FileAccess.get_file_as_string("res://command.json"))
			if command is Dictionary and int(command.sequence) > sequence:
				sequence = int(command.sequence)
				var result := {"ok": true}
				match str(command.action):
					"approve":
						var dialog = dock.find_child("AIFileApproval", true, false)
						result["was_visible"] = dialog.visible
						if dialog.visible:
							dialog.confirmed.emit()
					"reparent_native_widget":
						wrapper = VBoxContainer.new()
						wrapper.name = "ReparentedSceneGuardCompound"
						wrapper.size = Vector2(200, 120)
						wrapper.set_meta("ai_control_page", true)
						EditorInterface.get_base_control().add_child(wrapper)
						scene_widget.reparent(wrapper)
						wrapper.set_meta("ai_control_semantic_actions", [{
							"name": "scene_rename_alias",
							"target": str(wrapper.get_path_to(scene_widget)),
							"action": "edit_tree_cell",
						}])
						await process_frame
						result["compound_target"] = target_for(wrapper, "ReparentedSceneGuardCompound")
						result["has_scene_editor_ancestor"] = false
						var ancestor = scene_widget.get_parent()
						while ancestor:
							if ancestor.is_class("SceneTreeEditor"):
								result["has_scene_editor_ancestor"] = true
							ancestor = ancestor.get_parent()
					"exit":
						if scene_widget.get_parent() != scene_parent:
							scene_widget.reparent(scene_parent)
							scene_parent.move_child(scene_widget, scene_index)
						write_json("res://ack-%d.json" % sequence, result)
						quit()
						return
				result.merge(snapshot())
				write_json("res://ack-%d.json" % sequence, result)
		await create_timer(0.01).timeout
