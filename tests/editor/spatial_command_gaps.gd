@tool
extends SceneTree

var dock: Node
var folder := OS.get_environment("SPATIAL_COMMAND_DIR")

func write_json(name: String, value: Dictionary) -> void:
	var path := folder.path_join(name)
	var file := FileAccess.open(path + ".pending", FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()
	DirAccess.rename_absolute(path + ".pending", path)

func delete_doomed_player() -> void:
	var scene := EditorInterface.get_edited_scene_root()
	if scene.has_node("DoomedPlayer"):
		scene.get_node("DoomedPlayer").free()

func create_doomed_player() -> void:
	var scene := EditorInterface.get_edited_scene_root()
	var player := AnimationPlayer.new()
	player.name = "DoomedPlayer"
	scene.add_child(player)
	player.owner = scene
	var library := AnimationLibrary.new()
	var animation := Animation.new()
	var track := animation.add_track(Animation.TYPE_VALUE)
	animation.track_set_path(track, NodePath("Polygon:visible"))
	animation.track_insert_key(track, 0, true)
	animation.changed.connect(delete_doomed_player, CONNECT_ONE_SHOT)
	library.add_animation("Move", animation)
	player.add_animation_library("", library)

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
	while EditorInterface.get_resource_filesystem().is_scanning():
		await process_frame
	write_json("ready.json", {"ok": true})
	while true:
		var path := folder.path_join("command.json")
		if not FileAccess.file_exists(path):
			await process_frame
			continue
		var command: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
		DirAccess.remove_absolute(path)
		var answer := {"ok": true}
		var scene := EditorInterface.get_edited_scene_root()
		match command.action:
			"setup":
				var polygon := Polygon2D.new()
				polygon.name = "Polygon"
				polygon.polygon = PackedVector2Array([Vector2.ZERO, Vector2(10, 0), Vector2(0, 10)])
				scene.add_child(polygon)
				polygon.owner = scene
				var collision := CollisionPolygon2D.new()
				collision.name = "Collision"
				collision.polygon = polygon.polygon
				scene.add_child(collision)
				collision.owner = scene
				var spatial := Node3D.new()
				spatial.name = "Spatial"
				scene.add_child(spatial)
				spatial.owner = scene
				var mesh := MeshInstance3D.new()
				mesh.name = "Cube"
				mesh.mesh = BoxMesh.new()
				spatial.add_child(mesh)
				mesh.owner = scene
				var player := AnimationPlayer.new()
				player.name = "Player"
				scene.add_child(player)
				player.owner = scene
				var library := AnimationLibrary.new()
				var animation := Animation.new()
				animation.length = 5.0
				library.add_animation("Move", animation)
				player.add_animation_library("", library)
				if ClassDB.class_exists("TileMapLayer"):
					var layer := TileMapLayer.new()
					layer.name = "Tiles"
					var tileset := TileSet.new()
					var atlas := TileSetAtlasSource.new()
					var image := Image.create(32, 16, false, Image.FORMAT_RGBA8)
					image.fill(Color.RED)
					atlas.texture = ImageTexture.create_from_image(image)
					atlas.texture_region_size = Vector2i(16, 16)
					atlas.create_tile(Vector2i.ZERO)
					atlas.create_tile(Vector2i(1, 0))
					tileset.add_source(atlas, 0)
					layer.tile_set = tileset
					layer.set_cell(Vector2i.ZERO, 0, Vector2i.ZERO)
					scene.add_child(layer)
					layer.owner = scene
			"doomed_player":
				create_doomed_player()
			"edit_player":
				var player: AnimationPlayer = scene.get_node("Player")
				player.assigned_animation = "Move"
				EditorInterface.edit_node(player)
			"huge_scale":
				scene.get_node("Spatial").scale = Vector3(3e37, 1, 1)
			"restore_scale":
				scene.get_node("Spatial").scale = Vector3.ONE
			"select_spatial":
				EditorInterface.get_selection().clear()
				EditorInterface.get_selection().add_node(scene.get_node("Spatial"))
			"clear_selection":
				EditorInterface.get_selection().clear()
			"approve":
				var dialog := root.find_child("AIFileApproval", true, false)
				answer["visible"] = dialog != null and dialog.visible
				if answer.visible:
					dialog.hide()
					dialog.confirmed.emit()
			"mutate_polygon":
				scene.get_node("Polygon").polygon = PackedVector2Array([Vector2.ZERO, Vector2(99, 0), Vector2(0, 10)])
			"replace_polygon":
				scene.get_node("Polygon").free()
				var polygon := Polygon2D.new()
				polygon.name = "Polygon"
				polygon.polygon = PackedVector2Array([Vector2.ZERO, Vector2(10, 0), Vector2(0, 10)])
				scene.add_child(polygon)
				polygon.owner = scene
			"mutate_animation":
				scene.get_node("Player").get_animation("Move").length = 6
			"playing":
				if command.value:
					scene.get_node("Player").play("Move")
				else:
					scene.get_node("Player").stop()
			"animation_method":
				scene.get_node("Player").get_animation("Move").add_track(Animation.TYPE_METHOD)
			"mutate_tileset":
				scene.get_node("Tiles").tile_set.get_source(0).texture_region_size = Vector2i(8, 8)
			"clear_owner":
				scene.get_node("Polygon").owner = null
			"restore_owner":
				scene.get_node("Polygon").owner = scene
			"tools":
				dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = command.value
			"consultation":
				dock.find_child("ConsultationOnly", true, false).button_pressed = command.value
			"undo", "redo":
				var manager := EditorInterface.get_editor_undo_redo()
				var history := manager.get_history_undo_redo(manager.get_object_history_id(scene))
				answer["changed"] = history.undo() if command.action == "undo" else history.redo()
			"snapshot":
				var polygon: Polygon2D = scene.get_node("Polygon")
				var points: Array = []
				for point in polygon.polygon:
					points.push_back([point.x, point.y])
				answer["points"] = points
				answer["tracks"] = scene.get_node("Player").get_animation("Move").get_track_count()
				answer["animation_metadata"] = Array(scene.get_node("Player").get_animation("Move").get_meta_list())
				answer["tileset_metadata"] = Array(scene.get_node("Tiles").tile_set.get_meta_list())
			"finish":
				write_json("ack-%d.json" % int(command.id), answer)
				EditorInterface.get_editor_undo_redo().clear_history()
				quit(0)
				return
		await process_frame
		write_json("ack-%d.json" % int(command.id), answer)
