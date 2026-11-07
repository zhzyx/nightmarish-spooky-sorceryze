@tool
extends SceneTree

var control: AIChatEditorControl
var dock: Node
var page: VBoxContainer
var menu: PopupMenu
var graph: GraphEdit
var items: ItemList
var tree: Tree
var curve := Curve.new()
var gradient := Gradient.new()
var native_shader := VisualShader.new()
var global_resource := Resource.new()
var menu_history_version_reused := false
var global_history_id := -99
var model_links: Array = []
var model_position := Vector2.ZERO
var activations := 0
var contexts := 0
var menu_ids: Array = []
var ids := {}
var mutate_popup := false
var history_version_reused := false
var close_popup := false
var replace_popup := false

func target(label: String) -> String:
	for entry in control.find_targets(label, 20):
		if entry.get("display_name") == label:
			return entry.id
	return ""

func find_resource_editor(action: String) -> Node:
	var kind := "CurveEdit" if action == "read_curve" else "GradientEdit"
	var queue: Array[Node] = [EditorInterface.get_inspector()]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node.is_class(kind): return node
		for child in node.get_children(): queue.append(child)
	return null

func find_native_graph() -> GraphEdit:
	var queue: Array[Node] = [root]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node is GraphEdit:
			var ancestor = node.get_parent()
			while ancestor:
				if ancestor.is_class("VisualShaderEditor"): return node
				ancestor = ancestor.get_parent()
		for child in node.get_children(): queue.append(child)
	return null

func snapshot() -> Dictionary:
	var edited = EditorInterface.get_inspector().get_edited_object()
	if edited == curve or edited == gradient:
		var editor = find_resource_editor("read_curve" if edited == curve else "read_gradient")
		if editor:
			editor.name = "ComplexCurve" if edited == curve else "ComplexGradient"
			var alias := "complex_curve" if edited == curve else "complex_gradient"
			editor.set_meta("ai_control_id", alias)
			var description := control.describe_target("editor." + alias)
			ids[editor.name] = description.get("id", "") if description.get("ok", false) else ""
	if ids.is_empty():
		for label in ["ComplexMenu", "ComplexGraph", "ComplexTree", "ComplexItems", "ComplexCurve", "ComplexGradient", "ComplexLaterMenu", "ComplexSubmenu"]:
			ids[label] = target(label)
	return {"ids": ids, "menu_ids": menu_ids, "activations": activations, "contexts": contexts,
		"model_links": model_links, "model_position": [model_position.x, model_position.y],
		"curve_points": curve.point_count, "curve_first_y": curve.get_point_position(0).y,
		"gradient_count": gradient.get_point_count(), "gradient_first": gradient.get_color(0).to_html(),
		"graph_connections": graph.get_connection_list().size(), "unsafe_called": curve.get_meta("unsafe_called", false), "history_version_reused": history_version_reused, "menu_history_version_reused": menu_history_version_reused, "global_history_id": global_history_id,
		"native_shader_connections": native_shader.get_node_connections(VisualShader.TYPE_VERTEX),
		"native_shader_position": [native_shader.get_node_position(VisualShader.TYPE_VERTEX, 2).x, native_shader.get_node_position(VisualShader.TYPE_VERTEX, 2).y]}

func write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func later_menu() -> void:
	var popup := PopupMenu.new()
	popup.name = "ComplexLaterMenu"
	popup.add_item("Deferred business choice", 89)
	page.add_child(popup)
	popup.popup()

func replace_submenu() -> void:
	var old = menu.get_node("ComplexSubmenu")
	menu.remove_child(old)
	old.queue_free()
	var replacement := PopupMenu.new()
	replacement.name = "ComplexSubmenu"
	replacement.add_item("Native nested leaf", 91)
	replacement.id_pressed.connect(func(id): menu_ids.append(id))
	menu.add_child(replacement)
	menu.set_item_submenu_node(3, replacement)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	# Per-process fixture pacing; never writes EditorSettings or changes another editor.
	OS.set_low_processor_usage_mode_sleep_usec(1000)
	Engine.max_fps = 120
	await create_timer(1).timeout
	control = AIChatEditorControl.get_singleton()
	dock = root.find_child("AI Chat", true, false)
	if not control or not dock:
		quit(1)
		return
	dock.find_child("AllowTools", true, false).button_pressed = true
	dock.find_child("AutoExecuteCommands", true, false).button_pressed = false
	page = VBoxContainer.new()
	page.name = "ComplexPage"
	page.set_meta("ai_control_page", true)
	page.size = Vector2(600, 700)
	EditorInterface.get_base_control().add_child(page)
	menu = PopupMenu.new()
	menu.name = "ComplexMenu"
	menu.add_item("Create delayed menu", 73)
	menu.add_separator()
	menu.add_item("Disabled", 74)
	menu.set_item_disabled(2, true)
	menu.id_pressed.connect(func(id): menu_ids.append(id); later_menu.call_deferred())
	menu.visibility_changed.connect(func():
		if close_popup and menu.visible:
			close_popup = false
			menu.hide())
	menu.about_to_popup.connect(func():
		if replace_popup:
			replace_popup = false
			replace_submenu()
		if mutate_popup:
			menu.set_item_text(0, "Changed during native reopen")
			mutate_popup = false)
	var submenu := PopupMenu.new()
	submenu.name = "ComplexSubmenu"
	submenu.add_item("Native nested leaf", 91)
	submenu.id_pressed.connect(func(id): menu_ids.append(id))
	menu.add_child(submenu)
	menu.add_submenu_node_item("Nested native", submenu, 75)
	page.add_child(menu)
	graph = GraphEdit.new()
	graph.name = "ComplexGraph"
	graph.custom_minimum_size = Vector2(400, 200)
	page.add_child(graph)
	for label in ["Source", "Destination"]:
		var node := GraphNode.new()
		node.name = label
		graph.add_child(node)
		node.add_child(Label.new())
		node.set_slot(0, true, 0, Color.WHITE, true, 0, Color.WHITE)
	graph.connection_request.connect(func(from, from_port, to, to_port):
		model_links.append([from, from_port, to, to_port])
		graph.connect_node(from, from_port, to, to_port), CONNECT_DEFERRED)
	graph.disconnection_request.connect(func(from, from_port, to, to_port):
		model_links.clear()
		graph.disconnect_node(from, from_port, to, to_port), CONNECT_DEFERRED)
	graph.get_node("Source").dragged.connect(func(_from, to): model_position = to)
	items = ItemList.new()
	items.name = "ComplexItems"
	items.add_item("Open item")
	items.set_item_metadata(0, "res://original.gd")
	items.allow_rmb_select = true
	items.item_activated.connect(func(_index): activations += 1)
	items.item_clicked.connect(func(_index, _pos, button):
		if button == MOUSE_BUTTON_RIGHT: contexts += 1)
	page.add_child(items)
	tree = Tree.new()
	tree.name = "ComplexTree"
	tree.allow_rmb_select = true
	tree.create_item().set_text(0, "Open tree")
	tree.get_root().set_metadata(0, "res://original.tscn")
	tree.item_activated.connect(func(): activations += 1)
	tree.item_mouse_selected.connect(func(_pos, button):
		if button == MOUSE_BUTTON_RIGHT: contexts += 1)
	page.add_child(tree)
	native_shader.add_node(VisualShader.TYPE_VERTEX, VisualShaderNodeVec3Constant.new(), Vector2(10, 20), 2)
	curve.add_point(Vector2(0, 0.25))
	curve.add_point(Vector2(1, 0.75))
	await process_frame
	write_json("res://ready.json", snapshot())
	var deadline := Time.get_ticks_msec() + 600000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists("res://finish"):
			print("EDITOR_COMPLEX_CONTROLS_OK")
			EditorInterface.get_selection().clear()
			EditorInterface.inspect_object(null)
			await process_frame
			page.queue_free()
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
					if cmd.action == "approve": dialog.confirmed.emit()
					else: dialog.canceled.emit()
				"popup":
					for child in page.get_children():
						if child is PopupMenu and child != menu: child.hide()
					menu.popup()
				"item_metadata": items.set_item_metadata(0, str(items.get_item_metadata(0)) + ".changed")
				"tree_metadata": tree.get_root().set_metadata(0, str(tree.get_root().get_metadata(0)) + ".changed")
				"menu_mutate": menu.set_item_text(0, "User changed action")
				"menu_metadata": menu.set_item_metadata(0, {"owner": graph.get_node("Source")})
				"menu_context": EditorInterface.get_selection().add_node(graph.get_node("Source"))
				"mutate_menu_on_popup":
					mutate_popup = true
					menu.hide()
				"replace_submenu": replace_submenu()
				"replace_submenu_on_popup":
					replace_popup = true
					menu.hide()
				"close_parent_on_popup":
					close_popup = true
					menu.hide()
				"menu_history_seed", "menu_history_reuse":
					var plugin := EditorPlugin.new()
					var history := plugin.get_undo_redo()
					if cmd.action == "menu_history_seed":
						global_resource.take_over_path("res://complex_global_resource.tres")
						global_resource.set_meta("stamp", 0)
						global_resource.set_meta("other", 0)
						history.create_action("Same ordinary menu action", UndoRedo.MERGE_DISABLE, global_resource)
						history.add_do_method(global_resource, "set_meta", "stamp", 1)
						history.add_undo_method(global_resource, "set_meta", "stamp", 0)
						history.commit_action()
						global_history_id = history.get_object_history_id(global_resource)
					else:
						var native := history.get_history_undo_redo(global_history_id)
						var version := native.get_version()
						native.undo()
						global_resource.set_meta("stamp", 1)
						history.create_action("Same ordinary menu action", UndoRedo.MERGE_DISABLE, global_resource)
						history.add_do_method(global_resource, "set_meta", "other", 1)
						history.add_undo_method(global_resource, "set_meta", "other", 0)
						history.commit_action()
						menu_history_version_reused = native.get_version() == version
					plugin.free()
				"history_mutate":
					var plugin := EditorPlugin.new()
					var history := plugin.get_undo_redo()
					history.create_action("Unrelated resource user edit", UndoRedo.MERGE_DISABLE, curve)
					history.add_do_method(curve, "set_point_value", 0, 0.4)
					history.add_undo_method(curve, "set_point_value", 0, curve.get_point_position(0).y)
					history.commit_action()
					plugin.free()
				"replace_menu":
					menu.hide()
					page.remove_child(menu)
					menu.queue_free()
					menu = PopupMenu.new()
					menu.name = "ComplexMenu"
					menu.add_item("Create delayed menu", 73)
					page.add_child(menu)
					menu.popup()
				"native_graph":
					EditorInterface.edit_resource(native_shader)
					await create_timer(0.3).timeout
					var native_graph = find_native_graph()
					assert(native_graph)
					native_graph.name = "ComplexNativeGraph"
					native_graph.set_meta("ai_control_id", "complex_native_graph")
					var ancestor: Node = native_graph
					while ancestor:
						if ancestor is Control: ancestor.show()
						if ancestor.get_parent() is TabContainer and ancestor is Control:
							ancestor.get_parent().current_tab = ancestor.get_parent().get_tab_idx_from_control(ancestor)
						ancestor = ancestor.get_parent()
				"curve", "gradient":
					var ancestor: Node = EditorInterface.get_inspector()
					while ancestor:
						if ancestor is Control: ancestor.show()
						if ancestor.get_parent() is TabContainer and ancestor is Control:
							ancestor.get_parent().current_tab = ancestor.get_parent().get_tab_idx_from_control(ancestor)
						ancestor = ancestor.get_parent()
					EditorInterface.edit_resource(curve if cmd.action == "curve" else gradient)
					await create_timer(0.3).timeout
					await process_frame
					await process_frame
					var editor = find_resource_editor("read_curve" if cmd.action == "curve" else "read_gradient")
					if editor: editor.name = "ComplexCurve" if cmd.action == "curve" else "ComplexGradient"
					else: print("COMPLEX_RESOURCE_EDITOR_MISSING ", cmd.action, " inspector=", EditorInterface.get_inspector().get_edited_object())
				"await_submenu": await create_timer(0.2).timeout
				"resource_mutate": gradient.set_color(0, Color.GREEN if gradient.get_color(0) == Color.BLUE else Color.BLUE)
				"history_reuse":
					var plugin := EditorPlugin.new()
					var history := plugin.get_undo_redo()
					var id := history.get_object_history_id(gradient)
					var version := history.get_history_undo_redo(id).get_version()
					var colors := gradient.get_colors()
					history.get_history_undo_redo(id).undo()
					gradient.set_colors(colors)
					history.create_action("Other resource edit at reused version", UndoRedo.MERGE_DISABLE, curve)
					history.add_do_method(curve, "set_point_value", 0, 0.39)
					history.add_undo_method(curve, "set_point_value", 0, curve.get_point_position(0).y)
					history.commit_action()
					history_version_reused = history.get_history_undo_redo(id).get_version() == version
					plugin.free()
				"curve_mutate": curve.set_point_value(0, 0.41)
				"script_curve":
					var script := GDScript.new()
					script.source_code = "@tool\nextends Curve\n@warning_ignore(\"native_method_override\")\nfunc _set_data(_value):\n\tset_meta(\"unsafe_called\", true)\n"
					var source := FileAccess.open("res://scripted_curve.gd", FileAccess.WRITE)
					source.store_string(script.source_code)
					source.close()
					script = load("res://scripted_curve.gd") as GDScript
					assert(script and script.can_instantiate())
					curve.set_script(script)
				"clear_curve_script": curve.set_script(null)
				"permission": dock.find_child("AllowTools", true, false).button_pressed = cmd.value
				"consultation": dock.find_child("ConsultationOnly", true, false).button_pressed = cmd.value
			await process_frame
			await process_frame
			write_json("res://ack-%d.json" % int(cmd.id), snapshot())
		await process_frame
	quit(2)
