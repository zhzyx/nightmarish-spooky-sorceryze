@tool
extends Node3D

const STROKE := Vector3(12, 0, 12)
var failures := PackedStringArray()


func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)


func _ready() -> void:
	if Engine.is_editor_hint() and OS.has_environment("TERRAIN3D_EDITOR_GUI_STAGE"):
		run.call_deferred()


func run() -> void:
	for i in 150:
		await get_tree().process_frame
		if EditorInterface.get_edited_scene_root() == self:
			break
	if EditorInterface.get_edited_scene_root() != self:
		return
	var plugin = get_tree().root.find_child("Terrain3DEditorPlugin", true, false)
	check(plugin != null and plugin.get_script() != null, "Missing built-in editor plugin")
	if not plugin:
		finish()
		return
	var reopen := OS.get_environment("TERRAIN3D_EDITOR_GUI_STAGE") == "reopen"
	var terrain: Terrain3D = get_node_or_null("EditableTerrain")
	var other: Terrain3D = get_node_or_null("OtherTerrain")
	if not reopen:
		terrain = Terrain3D.new()
		terrain.name = "EditableTerrain"
		terrain.region_size = 64
		add_child(terrain)
		terrain.owner = self
		other = Terrain3D.new()
		other.name = "OtherTerrain"
		other.region_size = 64
		add_child(other)
		other.owner = self
		other.data_directory = "res://editable_terrain_data"
		other.data.add_region_blank(Vector2i.ONE)
		other.data.set_height(Vector3(80, 0, 80), 7.0)
		other.data.update_maps()
	check(terrain != null, "Terrain missing from reopened scene")
	if not terrain:
		finish()
		return
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(terrain)
	EditorInterface.edit_node(terrain)
	for i in 60:
		await get_tree().process_frame
		if plugin.terrain == terrain and plugin.asset_dock != null:
			break
	check(plugin.terrain == terrain and plugin.ui != null, "Selection did not bind Terrain3D editor tools")
	if not plugin.ui:
		finish()
		return
	var menu = plugin.ui.terrain_menu
	check(plugin.asset_dock.texture_list != null and plugin.asset_dock.mesh_list != null, "Texture and mesh dock lists")
	check(menu.baker != null and menu.material_svt != null and menu.packer != null, "Baking and channel packing tools")
	var brushes: ButtonGroup = plugin.ui.tool_settings.settings["brush"]
	check(brushes.get_buttons().size() >= 35 and brushes.get_pressed_button() != null, "Missing default brush palette")
	check(other != null and other.data_directory == "res://editable_terrain_data" and is_equal_approx(other.data.get_height(Vector3(80,0,80)), 7.0), "Neighboring terrain lost an authored height")
	if reopen:
		check(terrain.data.has_region(Vector2i.ZERO) and terrain.data.get_height(STROKE) > 0.01, "Persisted brush stroke or region missing")
		check(not menu.initialize_button.visible, "Initialization offered for existing data")
		print("Reopened terrain ", terrain.data_directory, " height ", terrain.data.get_height(STROKE))
		finish()
		return
	if OS.has_environment("TERRAIN3D_EDITOR_CAPTURE"):
		EditorInterface.set_main_screen_editor("3D")
		for frame in 8:
			await RenderingServer.frame_post_draw
		var capture := EditorInterface.get_base_control().get_viewport().get_texture().get_image()
		check(capture != null and capture.save_png(OS.get_environment("TERRAIN3D_EDITOR_CAPTURE")) == OK, "Could not capture native editor tools")
	var old_material := terrain.material
	var data_id := terrain.data.get_instance_id()
	check(menu.initialize_button.visible, "New node has no Initialize Terrain button")
	menu.initialize_button.pressed.emit()
	var path := terrain.data_directory
	check(path.begins_with("res://") and path != "res://editable_terrain_data" and terrain.data.has_region(Vector2i.ZERO), "Initialization overwrote a folder or did not create its first region: " + path)
	check(terrain.material == old_material and not menu.initialize_button.visible, "Initialization changed material or remained enabled")
	var manager: EditorUndoRedoManager = plugin.get_undo_redo()
	var undo := manager.get_history_undo_redo(manager.get_object_history_id(terrain))
	check(undo.undo() and terrain.data_directory.is_empty() and terrain.data.get_region_locations().is_empty(), "Undo initialization")
	check(undo.redo() and terrain.data_directory == path and terrain.data.has_region(Vector2i.ZERO), "Redo initialization")
	var cvars := Engine.get_singleton("CVars")
	if cvars:
		var previous_mode = cvars.get_value("r.Terrain3D.Mode")
		var previous_height = cvars.get_value("r.Terrain3D.VTHeight")
		plugin.preview_height_vt()
		check(cvars.get_value("r.Terrain3D.Mode") == 1 and cvars.get_value("r.Terrain3D.VTHeight") == 1, "Preview preset did not select quadtree height VT")
		if RenderingServer.get_rendering_device() != null:
			for frame in 45:
				await get_tree().process_frame
				if terrain.get_quadtree_multimesh_rid().is_valid() and terrain.get_height_vt_rid().is_valid():
					break
			check(terrain.get_quadtree_multimesh_rid().is_valid() and terrain.get_height_vt_rid().is_valid(), "Preview did not produce GPU geometry and a height VT")
		if previous_mode != 1 or previous_height != 1:
			check(undo.undo() and cvars.get_value("r.Terrain3D.Mode") == previous_mode and cvars.get_value("r.Terrain3D.VTHeight") == previous_height, "Undo preview preset")
	var raise_button: Button = plugin.ui.toolbar.get_button("Raise")
	check(raise_button != null, "Missing raise terrain tool")
	if raise_button:
		raise_button.button_pressed = true
		raise_button.get_button_group().pressed.emit(raise_button)
		check(plugin.editor.get_tool() == Terrain3DEditor.SCULPT, "Raise toolbar button did not select the native sculpt tool")
	var brush_settings: Dictionary = plugin.ui.tool_settings.get_settings()
	brush_settings["size"] = 8.0
	brush_settings["strength"] = 100.0
	brush_settings["mouse_pressure"] = 1.0
	brush_settings["modifier_alt"] = false
	brush_settings["modifier_ctrl"] = false
	brush_settings["mesh_asset_ids"] = []
	brush_settings["texture_asset_ids"] = []
	var editor: Terrain3DEditor = plugin.editor
	editor.set_brush_data(brush_settings)
	editor.start_operation(STROKE)
	editor.operate(STROKE, 0.0)
	editor.stop_operation()
	check(terrain.data.get_height(STROKE) > 0.01, "Height brush did not raise terrain")
	check(undo.undo() and absf(terrain.data.get_height(STROKE)) < 0.001, "Undo sculpt stroke")
	check(undo.redo() and terrain.data.get_height(STROKE) > 0.01, "Redo sculpt stroke")
	menu.baker.bake_mesh_popup()
	menu.baker.bake_lod_dialog.lod = 2
	menu.baker.bake_lod_dialog.confirmed.emit()
	menu.baker.bake_lod_dialog.hide()
	var baked := terrain.get_node_or_null("MeshInstance3D") as MeshInstance3D
	check(is_instance_valid(baked) and baked.mesh != null and baked.mesh.get_surface_count() > 0, "ArrayMesh bake dialog produced no mesh")
	check(undo.undo() and not terrain.has_node("MeshInstance3D"), "Undo ArrayMesh bake")
	EditorInterface.save_scene_as(scene_file_path, false)
	for cycle in 2:
		check(undo.undo() and is_zero_approx(terrain.data.get_height(STROKE)), "Sculpt undo after save")
		check(undo.undo() and terrain.data_directory.is_empty(), "Initialization undo after save")
		check(undo.redo() and is_zero_approx(terrain.data.get_height(STROKE)), "Initialization redo restored a later stroke")
		check(undo.redo() and terrain.data.get_height(STROKE) > 0.01, "Sculpt redo after save")
		EditorInterface.save_scene_as(scene_file_path, false)
		check(terrain.data.get_instance_id() == data_id and terrain.material == old_material, "Initialization invalidated live terrain resources")
		check(is_equal_approx(other.data.get_height(Vector3(80,0,80)), 7.0), "Undo changed the other terrain")
	# Allow the native editor's deferred updates to settle before closing the scene.
	for frame in 4:
		await get_tree().process_frame
	print("Initialized terrain ", path, " brushes ", brushes.get_buttons().size(), " height ", terrain.data.get_height(STROKE))
	finish()


func finish() -> void:
	print("Terrain3D editor ", OS.get_environment("TERRAIN3D_EDITOR_GUI_STAGE"), ": ", failures.size(), " failures")
	get_tree().quit(int(not failures.is_empty()))
