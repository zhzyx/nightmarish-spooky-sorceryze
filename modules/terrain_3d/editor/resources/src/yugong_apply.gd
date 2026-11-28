@tool
extends RefCounted

const Expedition = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_expedition.gd")

static func new_directory() -> String:
	var path := "res://yugong/land_" + ResourceUID.id_to_text(ResourceUID.create_id()).trim_prefix("uid://")
	return path if DirAccess.make_dir_recursive_absolute(path) == OK else ""

static func save_resource(resource: Resource, path: String) -> bool:
	if ResourceSaver.save(resource, path, ResourceSaver.FLAG_COMPRESS) != OK:
		return false
	resource.resource_path = path
	return true

static func solid_texture(folder: String, name: String, color: Color) -> ImageTexture:
	var pixels := Image.create_empty(32, 32, false, Image.FORMAT_RGBA8)
	pixels.fill(color)
	pixels.generate_mipmaps()
	var texture := ImageTexture.create_from_image(pixels)
	return texture if save_resource(texture, folder.path_join(name)) else null

static func default_assets(folder: String) -> Terrain3DAssets:
	if DirAccess.make_dir_recursive_absolute(folder) != OK:
		return null
	var albedo := solid_texture(folder, "albedo.res", Color(1, 1, 1, 0.5))
	var normal := solid_texture(folder, "normal.res", Color(0.5, 0.5, 1, 1))
	if not albedo or not normal:
		return null
	var assets := Terrain3DAssets.new()
	var layers: Array[Terrain3DTextureAsset] = []
	for tint in [Color("#81945c"), Color("#918776")]:
		var tex := Terrain3DTextureAsset.new()
		tex.id = layers.size()
		tex.name = "草坡" if layers.is_empty() else "岩面"
		tex.albedo_texture = albedo
		tex.normal_texture = normal
		tex.albedo_color = tint
		layers.append(tex)
	assets.texture_list = layers
	return assets if save_resource(assets, folder.path_join("palette.res")) else null

static func add_terrain(manager: EditorUndoRedoManager, root: Node, height: Image, span: float, folder: String, geography: Dictionary = {}) -> Terrain3D:
	var assets := default_assets(folder.path_join("materials")) if geography.is_empty() else Expedition.assets(folder.path_join("materials"))
	if not assets:
		return null
	var ground_material:=Terrain3DMaterial.new()
	if geography.get("fieldcraft",false):
		var path:=folder.path_join("materials/march_ground.tres")
		if not Expedition.copy_file(Expedition.ART+"march_ground.tres",path):return null
		ground_material=ResourceLoader.load(path,"Terrain3DMaterial") as Terrain3DMaterial
		if not ground_material:return null
	var terrain := Terrain3D.new()
	terrain.name = "Terrain3D"
	terrain.region_size = mini(256,height.get_width() / 2)
	terrain.vertex_spacing = span / height.get_width()
	terrain.data_directory = folder
	terrain.material = ground_material
	terrain.material.world_background = Terrain3DMaterial.NONE
	terrain.assets = assets
	if not geography.is_empty():
		terrain.material.projection_enabled = true
		terrain.material.dual_scaling_enabled = true
		terrain.collision_mode = Terrain3DCollision.FULL_GAME
	var corner := -Vector3(span, 0, span) * 0.5
	var maps: Array[Image] = [height, geography.get("control"), geography.get("color")]
	manager.create_action("愚公 · 添加地形", UndoRedo.MERGE_DISABLE, root)
	manager.add_do_method(root, "add_child", terrain, true)
	manager.add_do_method(terrain, "set_owner", root)
	# Import once. The node retains its regions and subsequent native brush edits across undo/redo.
	manager.add_do_reference(terrain)
	manager.add_undo_method(root, "remove_child", terrain)
	manager.commit_action()
	terrain.data.import_images(maps, corner, 0.0, 1.0)
	if terrain.get_collision().is_editor_mode():
		terrain.get_collision().update(Vector2i.MAX, true)
	return terrain

static func apply_patch(manager: EditorUndoRedoManager, terrain: Terrain3D, height: Image, span: float, center: Vector2) -> String:
	var spacing := terrain.vertex_spacing
	var samples := roundi(span / spacing)
	if samples < 2 or samples > 2048:
		return "当前顶点间距下需要 %d 个采样。请调整地形宽度，使每边保持在 2 到 2048 个采样之间。" % samples
	var data := terrain.data
	var start := Vector2i(roundi(center.x / spacing) - floori(samples * 0.5), roundi(center.y / spacing) - floori(samples * 0.5))
	var first := Vector2i(floori(float(start.x) / terrain.region_size), floori(float(start.y) / terrain.region_size))
	var end := start + Vector2i.ONE * (samples - 1)
	var last := Vector2i(floori(float(end.x) / terrain.region_size), floori(float(end.y) / terrain.region_size))
	var half := Terrain3DData.REGION_MAP_SIZE / 2
	if first.x < -half or first.y < -half or last.x >= half or last.y >= half:
		return "应用范围超出 Terrain3D 区域边界，请调整中心或宽度。"
	var maps: Array[Image] = [height.duplicate(), null, null]
	maps[0].resize(samples, samples, Image.INTERPOLATE_BILINEAR)
	# Store immutable pre-apply height maps. Unaffected channels and regions stay in place.
	var original := {}
	for z in range(first.y, last.y + 1):
		for x in range(first.x, last.x + 1):
			var loc := Vector2i(x, z)
			if data.has_region(loc):
				original[loc] = data.get_region(loc).get_height_map().duplicate()
			else:
				original[loc] = null
	var folder := ""
	if terrain.data_directory.is_empty():
		folder = new_directory()
		if folder.is_empty():
			return "无法创建地形数据目录。"
	manager.create_action("愚公 · 应用候选高度", UndoRedo.MERGE_DISABLE, terrain)
	if not folder.is_empty():
		manager.add_do_method(terrain, "_change_editor_data_directory", "", folder)
	var corner := Vector3(start.x * spacing, 0, start.y * spacing)
	manager.add_do_method(data, "import_images", maps, corner, 0.0, 1.0)
	# Undo methods run in insertion order. Restore maps before detaching a new directory.
	for loc: Vector2i in original:
		if original[loc] != null:
			var region := data.get_region(loc)
			manager.add_undo_method(region, "set_height_map", original[loc])
			manager.add_undo_method(region, "set_modified", true)
		else:
			manager.add_undo_method(data, "remove_regionl", loc, false)
	manager.add_undo_method(data, "update_maps")
	var area := AABB(corner, Vector3(samples * spacing, 1, samples * spacing))
	manager.add_do_method(terrain.get_instancer(), "update_transforms", area)
	manager.add_undo_method(terrain.get_instancer(), "update_transforms", area)
	if terrain.get_collision().is_editor_mode():
		manager.add_do_method(terrain.get_collision(), "update", Vector2i.MAX, true)
		manager.add_undo_method(terrain.get_collision(), "update", Vector2i.MAX, true)
	if not folder.is_empty():
		manager.add_undo_method(terrain, "_change_editor_data_directory", folder, "")
	manager.commit_action()
	return ""
