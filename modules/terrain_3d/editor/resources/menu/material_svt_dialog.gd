# Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.
@tool
extends ConfirmationDialog

var terrain: Terrain3D
var levels: Array[SpinBox] = []
var paths: Array[LineEdit] = []
var rows: Array[HBoxContainer] = []
var info := Label.new()
var result := Label.new()
var enable := Button.new()
var picker := EditorFileDialog.new()
var fields := VBoxContainer.new()
var picking := 0
var building := false
var refresh_in := 0.0


func _ready() -> void:
	title = "Build Terrain Material Streaming Mips"
	ok_button_text = "Build"
	dialog_hide_on_ok = false
	get_cancel_button().text = "Close"
	add_child(fields)
	_add_label("Choose the page file and coarse mip count for each material producer.")
	for caption in ["Material SVT", "Far / outer SVT"]:
		var row := HBoxContainer.new()
		rows.append(row)
		fields.add_child(row)
		var label := Label.new()
		label.text = caption
		label.custom_minimum_size.x = 150
		row.add_child(label)
		var path := LineEdit.new()
		path.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		path.text_changed.connect(func(_text: String): _refresh())
		row.add_child(path)
		paths.append(path)
		var browse := Button.new()
		browse.text = "Browse…"
		browse.pressed.connect(_browse.bind(paths.size() - 1))
		row.add_child(browse)
		var count := SpinBox.new()
		count.min_value = 1
		count.max_value = 11
		count.rounded = true
		count.suffix = "mips"
		row.add_child(count)
		levels.append(count)
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(info)
	enable.text = "Enable Mode 1 and Material RVT"
	enable.pressed.connect(_enable_material)
	fields.add_child(enable)
	_add_label("Building replaces the selected files. Save the scene if its material is embedded.")
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(result)
	picker.access = EditorFileDialog.ACCESS_RESOURCES
	picker.file_mode = EditorFileDialog.FILE_MODE_SAVE_FILE
	picker.filters = PackedStringArray(["*.svt ; Terrain material streaming texture"])
	picker.file_selected.connect(_file_selected)
	add_child(picker)
	confirmed.connect(_build)


func _add_label(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(label)


func edit(target: Terrain3D) -> void:
	if building or not is_instance_valid(target) or not target.material:
		return
	terrain = target
	var dir := terrain.data_directory
	if not dir.begins_with("res://"):
		dir = target.scene_file_path.get_base_dir() if target.scene_file_path.begins_with("res://") else "res://"
	var mat := terrain.material
	for i in 2:
		var assigned := ""
		if mat.has_method("get_material_rvt_stream_file"):
			assigned = mat.get("material_rvt_far_stream_file" if i else "material_rvt_stream_file")
		paths[i].text = assigned if assigned else dir.path_join("terrain_far.svt" if i else "terrain_near.svt")
		levels[i].max_value = 11
		levels[i].value = _stored_levels(assigned)
	result.text = ""
	_refresh()
	popup_centered(Vector2i(660, 300) * EditorInterface.get_editor_scale())


# Read the coarse count even when an edited source has detached the saved stream.
# The runtime separately validates the full header, source signature and page data.
func _stored_levels(path: String) -> int:
	if not path.is_empty() and FileAccess.file_exists(path):
		var file := FileAccess.open(path, FileAccess.READ)
		if file and file.get_length() >= 88 and file.get_32() == 0x54565347 and file.get_32() == 2:
			file.seek(12)
			if file.get_32() == 4: # TerrainPBR v2.
				file.seek(32)
				var total := file.get_32()
				var first := file.get_32()
				if total >= 1 and total <= 11 and first < total:
					return total - first
	return 4


func _file_selected(path: String) -> void:
	paths[picking].text = path
	_refresh()


func _browse(i: int) -> void:
	picking = i
	picker.current_path = paths[i].text
	picker.popup_centered_ratio(0.65)


func _process(delta: float) -> void:
	if visible and not building:
		refresh_in -= delta
		if refresh_in <= 0:
			_refresh()
			refresh_in = 0.5


func _enable_material() -> void:
	if not is_instance_valid(terrain):
		return
	Engine.get_singleton("CVars").set_value("r.Terrain3D.Mode", 1)
	terrain.material.set("material_rvt_enabled", true)
	terrain.material.emit_changed()
	EditorInterface.mark_scene_as_unsaved()
	_refresh()


func _problem(count: int) -> String:
	var outputs := {}
	for i in count:
		var path := paths[i].text.strip_edges()
		if not path.begins_with("res://") or path.get_extension().to_lower() != "svt" or ".." in path.split("/"):
			return "Choose a project .svt path for each output."
		path = path.simplify_path()
		if not DirAccess.dir_exists_absolute(path.get_base_dir()):
			return "Output directory does not exist: " + path.get_base_dir()
		if outputs.has(path.to_lower()) or path.to_lower() == terrain.height_vt_stream_file.to_lower():
			return "Choose a different file for each material endpoint and the terrain height."
		outputs[path.to_lower()] = true
	return ""


func _refresh() -> void:
	get_ok_button().disabled = true
	enable.hide()
	if not is_instance_valid(terrain) or not terrain.material:
		info.text = "Select a Terrain3D node."
		return
	var mat := terrain.material
	var count := 2 if mat.has_method("get_material_rvt_rid") and RID(mat.call("get_material_rvt_rid", true)).is_valid() else 1
	rows[1].visible = count == 2
	if not Engine.has_singleton("CVars") or not mat.has_method("bake_material_svt") or not RenderingServer.has_method("runtime_virtual_texture_get_stats") or RenderingServer.get_rendering_device() == null:
		info.text = "Open the project in the custom Forward+ editor to build material pages."
		return
	if not terrain.data or terrain.data.get_region_count() == 0 or mat.shader_override_enabled:
		info.text = "Add a terrain region and use the Terrain3D material shader to build streaming mips."
		return
	var cvars := Engine.get_singleton("CVars")
	if int(cvars.get_value("r.Terrain3D.Mode")) != 1 or not mat.get("material_rvt_enabled"):
		info.text = "Material streaming uses the Mode 1 quadtree and Material RVT."
		enable.show()
		return
	var status := PackedStringArray()
	for i in count:
		var surface: RID = mat.call("get_material_rvt_rid", bool(i))
		if not surface.is_valid():
			info.text = "Waiting for the terrain material page producer."
			return
		var stats: Dictionary = RenderingServer.call("runtime_virtual_texture_get_stats", surface)
		var layout: PackedInt32Array = stats.get("levels", PackedInt32Array())
		if layout.is_empty() or not stats.get("gpu_ready", false):
			info.text = "Waiting for the terrain material page producer."
			return
		var first := int(stats.get("stream_first_mip", -1))
		levels[i].max_value = layout.size()
		var state := "Live RVT"
		if first >= 0:
			state = "Streaming mips %d–%d" % [first, layout.size() - 1]
			var changed := int(stats.get("modified_stream_pages", 0))
			if changed:
				state += " (%d edited pages rendered live)" % changed
		elif not str(mat.get("material_rvt_far_stream_file" if i else "material_rvt_stream_file")).is_empty():
			state = "Assigned file inactive. Rendering live pages."
		status.append(("%s: " % ("Far" if i else "Material")) + state)
	var problem := _problem(count)
	if problem:
		status.append(problem)
	info.text = "\n".join(status)
	get_ok_button().disabled = building or not problem.is_empty()


func _build() -> void:
	_refresh()
	if building or get_ok_button().disabled:
		return
	building = true
	get_ok_button().disabled = true
	var mat := terrain.material
	var count := 2 if mat.has_method("get_material_rvt_rid") and RID(mat.call("get_material_rvt_rid", true)).is_valid() else 1
	var outputs := PackedStringArray()
	for i in count:
		outputs.append(paths[i].text.strip_edges().simplify_path())
	var coarse := [int(levels[0].value), int(levels[1].value)]
	var reports := PackedStringArray()
	var built := false
	for i in count:
		result.text = "Building " + outputs[i] + "…"
		await get_tree().process_frame
		if not is_instance_valid(terrain) or terrain.material != mat:
			reports.append("Terrain selection is no longer available.")
			break
		var err: Error = mat.call("bake_material_svt", outputs[i], coarse[i], bool(i))
		if err != OK:
			reports.append("Could not build %s (%s)." % [outputs[i], error_string(err)])
			if err == ERR_BUSY:
				reports.append("Wait for the source textures to finish loading and build again.")
			break
		mat.set("material_rvt_far_stream_file" if i else "material_rvt_stream_file", outputs[i])
		reports.append("Built " + outputs[i])
		built = true
	if built:
		mat.emit_changed()
		if mat.is_built_in():
			EditorInterface.mark_scene_as_unsaved()
		else:
			var saved := ResourceSaver.save(mat)
			if saved != OK:
				reports.append("Save material %s (%s)." % [mat.resource_path, error_string(saved)])
	result.text = "\n".join(reports)
	building = false
	_refresh()
