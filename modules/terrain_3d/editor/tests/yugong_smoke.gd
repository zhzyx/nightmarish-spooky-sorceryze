@tool
extends Node3D

var failures := PackedStringArray()

func check(value: bool, message: String) -> void:
	if not value:
		failures.append(message)
		push_error(message)

func _ready() -> void:
	if Engine.is_editor_hint() and OS.has_environment("TERRAIN3D_YUGONG_STAGE"):
		run.call_deferred()
	elif not Engine.is_editor_hint() and OS.get_environment("TERRAIN3D_YUGONG_STAGE") == "runtime":
		var camera := Camera3D.new()
		add_child(camera)
		camera.current = true
		var terrain := get_node_or_null("Terrain3D") as Terrain3D
		check(terrain != null and is_equal_approx(terrain.data.get_height(Vector3.ZERO), 77), "Runtime did not load edited terrain")
		if terrain:
			var palette := ResourceLoader.load(terrain.assets.resource_path, "Terrain3DAssets", ResourceLoader.CACHE_MODE_IGNORE) as Terrain3DAssets
			check(palette != null and palette.texture_list.size() == 2, "Runtime could not reload the saved palette")
		finish()

func run() -> void:
	for frame in 150:
		await get_tree().process_frame
		if EditorInterface.get_edited_scene_root() == self:
			break
	if EditorInterface.get_edited_scene_root() != self:
		return
	var plugin = get_tree().root.find_child("Terrain3DEditorPlugin", true, false)
	var page = plugin.yugong if plugin else null
	check(page != null and page.title == "愚公", "Built-in Yugong page is missing")
	if not page:
		finish()
		return
	page.make_visible()
	await get_tree().process_frame
	var stage := OS.get_environment("TERRAIN3D_YUGONG_STAGE")
	if stage == "reopen":
		var saved := get_node_or_null("Terrain3D") as Terrain3D
		check(saved != null and saved.data.has_region(Vector2i.ZERO), "Saved terrain lost its regions")
		if saved:
			check(saved.assets.resource_path.ends_with("palette.res") and saved.assets.texture_list[0].albedo_texture.resource_path.ends_with("albedo.res"), "Saved material resources were not external")
			check(is_equal_approx(saved.data.get_height(Vector3.ZERO), 77.0), "Hand edit did not survive reopening")
			check(saved.data.get_control_hole(Vector3(30, 0, 30)), "Control map lost hole after reopening")
		finish()
		return

	page.generate_local()
	check(page.candidates.is_empty(), "Missing input produced a candidate")
	page.prompt.text = "东西走向的宽谷，两侧有平缓山脊"
	page.generate_local()
	check(page.candidates.size() == 1 and not has_node("Terrain3D"), "Preview changed scene")
	if page.candidates.is_empty():
		finish()
		return
	var a: Dictionary = page.candidates[0]
	check(a.recipe.shape == "valley" and a.recipe.angle == 90.0 and a.recipe.width > 0.4, "Text intent not reflected in recipe")
	var backup: PackedByteArray = a.height.get_data()
	page._variation()
	check(page.candidates[1].height.get_data() != backup and a.height.get_data() == backup, "Candidate variation changed the parent")
	var guide := Image.create_empty(80, 40, false, Image.FORMAT_RGB8)
	guide.fill(Color.RED)
	guide.fill_rect(Rect2i(40, 0, 40, 40), Color.BLUE)
	var image_path := ProjectSettings.globalize_path("user://layout.png")
	guide.save_png(image_path)
	page.load_guide(image_path)
	page.prompt.text = ""
	page.generate_local()
	var guided: Image = page.candidates.back().height
	check(guided.get_pixel(30, 127).r - guided.get_pixel(220, 127).r > 70, "Painted ridge and river were not respected")
	guide.fill(Color(0.25, 0.25, 0.25))
	guide.save_png(image_path)
	page.load_guide(image_path)
	page.image_mode.select(1)
	page.generate_local()
	var grayscale: Image = page.candidates.back().height
	check(absf(grayscale.get_pixel(20, 20).r - 30.0) < 0.5, "Gray height scale invalid")
	check(page.preview.surface.mesh != null, "Missing height mesh preview")
	page.gallery.select(0)
	page.show_candidate(0)
	check(page.image_guide == null and page.prompt.text == a.description and page.seed_input.value == a.seed, "Candidate controls did not restore")
	page._apply_current()
	var terrain: Terrain3D = get_node_or_null("Terrain3D")
	check(terrain != null and terrain.data.get_region_count() == 4, "Apply did not create a four-region Terrain3D")
	if not terrain:
		finish()
		return
	var manager: EditorUndoRedoManager = plugin.get_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(self))
	check(history.undo() and not has_node("Terrain3D"), "Undo new terrain")
	check(history.redo() and has_node("Terrain3D"), "Redo new terrain")
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(terrain)
	EditorInterface.edit_node(terrain)
	for frame in 45:
		await get_tree().process_frame
		if plugin.terrain == terrain and plugin.ui:
			break
	check(plugin.editor != null and terrain.get_editor() == plugin.editor, "Native sculpt tools did not attach")
	var settings: Dictionary = plugin.ui.tool_settings.get_settings()
	settings.merge({"size": 12.0, "strength": 100.0, "mouse_pressure": 1.0, "modifier_alt": false, "modifier_ctrl": false,
		"mesh_asset_ids": [], "texture_asset_ids": []}, true)
	plugin.editor.set_tool(Terrain3DEditor.SCULPT)
	plugin.editor.set_operation(Terrain3DEditor.ADD)
	plugin.editor.set_brush_data(settings)
	var before := terrain.data.get_height(Vector3.ZERO)
	plugin.editor.start_operation(Vector3.ZERO)
	plugin.editor.operate(Vector3.ZERO, 0.0)
	plugin.editor.stop_operation()
	var sculpted := terrain.data.get_height(Vector3.ZERO)
	check(sculpted > before, "Generated terrain could not be sculpted")
	terrain.data.set_control_hole(Vector3(30, 0, 30), true)
	page.gallery.select(3)
	page.show_candidate(3)
	page._apply_current()
	check(page.confirm.visible and is_equal_approx(terrain.data.get_height(Vector3.ZERO), sculpted), "New candidate applied without confirmation")
	page.confirm.hide()
	page._confirm_apply()
	check(absf(terrain.data.get_height(Vector3.ZERO) - 30) < 0.5, "Replace height patch")
	check(terrain.data.get_control_hole(Vector3(30, 0, 30)), "Apply overwrote control channel")
	check(history.undo() and is_equal_approx(terrain.data.get_height(Vector3.ZERO), sculpted), "Undo lost manual sculpt")
	check(history.redo() and absf(terrain.data.get_height(Vector3.ZERO) - 30) < 0.5, "Redo failed to restore candidate")
	terrain.data.set_height(Vector3.ZERO, 77.0)
	terrain.data.update_maps()
	EditorInterface.save_scene_as(scene_file_path, false)
	if OS.get_environment("YUGONG_SCREENSHOT") != "":
		page.make_visible()
		page.gallery.select(0)
		page.show_candidate(0)
		await capture_window(OS.get_environment("YUGONG_SCREENSHOT"))
	if OS.get_environment("YUGONG_LIVE_AI") == "1":
		for y in guide.get_height():
			for x in guide.get_width():
				var ridge := 16.0 - 11.0 * exp(-pow((x - 22.0) / 12.0, 2))
				guide.set_pixel(x, y, Color.SKY_BLUE if y < ridge else Color.DARK_OLIVE_GREEN)
		guide.save_png(image_path)
		page.load_guide(image_path)
		page.image_mode.select(2)
		page.prompt.text = "西北一座山峰，东南低谷"
		var count: int = page.candidates.size()
		page.generate_ai()
		while not page.pending_ai.is_empty():
			await get_tree().process_frame
		check(page.candidates.size() == count + 1 and page.candidates.back().source == "AI", "Live AI image and text planning: " + page.status.text)
		if page.candidates.size() == count + 1 and OS.get_environment("YUGONG_SCREENSHOT") != "":
			page.make_visible()
			await capture_window(OS.get_environment("YUGONG_SCREENSHOT").get_basename() + "-ai.png")
	await page._create_scene()
	var standalone := EditorInterface.get_edited_scene_root()
	check(standalone != null and standalone != self and standalone.has_node("Terrain3D"), "Standalone scene did not open with a terrain")
	if standalone and standalone != self:
		var generated := standalone.get_node_or_null("Terrain3D") as Terrain3D
		var packed := ResourceLoader.load(standalone.scene_file_path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		check(generated != null and generated.data.get_region_count() == 4 and packed.get_state().get_node_count() == 4 and standalone.get_node_or_null("Overview") is Camera3D and standalone.get_node_or_null("Sun") is DirectionalLight3D, "Standalone scene was not saved with terrain, light and camera")
		if OS.get_environment("YUGONG_SCREENSHOT") != "":
			await capture_window(OS.get_environment("YUGONG_SCREENSHOT").get_basename() + "-terrain.png")
	finish()

func capture_window(path: String) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	for frame in 32:
		await tree.process_frame
	await RenderingServer.frame_post_draw
	tree.root.get_texture().get_image().save_png(path)

func finish() -> void:
	print("Yugong ", OS.get_environment("TERRAIN3D_YUGONG_STAGE"), ": ", failures.size(), " failures")
	Engine.get_main_loop().quit(int(not failures.is_empty()))
