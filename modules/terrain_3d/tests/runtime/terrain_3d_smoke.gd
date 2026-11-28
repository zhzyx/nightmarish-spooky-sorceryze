extends Node
## Exercises native Terrain3D registration, built-in resources, and collisions in a clean project.

var failures := 0
var checks := 0


func check(value: bool, description: String) -> void:
	checks += 1
	if not value:
		failures += 1
		push_error(description)


func matches_region_map(data: Terrain3DData, locations: Array) -> bool:
	var expected := PackedInt32Array()
	expected.resize(Terrain3DData.REGION_MAP_SIZE * Terrain3DData.REGION_MAP_SIZE)
	expected.fill(0)
	for i in locations.size():
		expected[Terrain3DData.get_region_map_index(locations[i])] = i + 1
	return data.get_region_map() == expected


func _ready() -> void:
	run.call_deferred()


func run() -> void:
	check(CVars.has_variable("r.Terrain3D.Mode") and CVars.has_variable("r.Terrain3D.VTHeight"),
			"Terrain CVars must exist before the first Terrain3D instance")
	CVars.set_value("r.Terrain3D.Mode", 0)

	var camera := Camera3D.new()
	camera.position = Vector3(8, 12, 8)
	add_child(camera)
	camera.make_current()
	var terrain := Terrain3D.new()
	terrain.region_size = Terrain3D.SIZE_64
	terrain.free_editor_textures = false
	terrain.collision_mode = Terrain3DCollision.FULL_GAME
	terrain.ocean_enabled = true
	var ocean := terrain.ocean_material as ShaderMaterial
	check(ocean != null and ocean.shader != null and ocean.shader.code.contains("uniform sampler2D foam_noise_texture"),
			"The built-in ocean must supply its shader")
	var sea_level = ocean.get_shader_parameter("sea_level") if ocean else null
	check(typeof(sea_level) == TYPE_FLOAT and is_equal_approx(sea_level, 5.0),
			"The built-in ocean must preserve the authored sea level")
	var foam = ocean.get_shader_parameter("foam_noise_texture") if ocean else null
	check(foam is NoiseTexture2D and foam.seamless and foam.noise is FastNoiseLite
			and foam.noise.noise_type == FastNoiseLite.TYPE_CELLULAR,
			"The built-in ocean must supply a seamless cellular foam texture")

	var custom := ShaderMaterial.new()
	terrain.ocean_material = custom
	terrain.ocean_enabled = false
	terrain.ocean_enabled = true
	check(terrain.ocean_material == custom, "Toggling the ocean must preserve the user's material")
	terrain.ocean_enabled = false
	add_child(terrain)
	terrain.set_camera(camera)
	terrain.set_clipmap_target(camera)
	check(terrain.get_clipmap_target() == camera, "Terrain must track the target by ObjectID")
	check(CVars.get_value("r.Terrain3D.Mode") == 0, "Creating terrain must preserve the explicit startup mode")
	check(terrain.data != null and terrain.collision != null and terrain.instancer != null,
			"Entering the scene must initialize the native data, collision, and instancer objects")

	check(matches_region_map(terrain.data, []), "An empty terrain must have zero in every region slot")
	var region := terrain.data.add_region_blank(Vector2i.ZERO) if terrain.data else null
	check(region != null and region.get_height_map() != null and region.get_height_map().get_width() == 64,
			"Terrain must create a 64-cell region in memory")
	check(matches_region_map(terrain.data, [Vector2i.ZERO]), "Only the authored region may have a layer index")
	for frame in 5:
		await get_tree().physics_frame
	var origin := Vector3(8, 12, 8)
	var ray := Vector3(0, -24, 0)
	var hit := terrain.get_raycast_result(origin, ray)
	check(hit.has("position") and hit.has("shape") and hit.get("collider") == terrain and absf(hit.position.y) < 0.05,
			"A ray must return the terrain body and the flat heightfield intersection")
	check(terrain.get_raycast_result(origin, ray, 1, true).is_empty(),
			"An explicit terrain exclusion must filter the same ray")
	terrain.data.remove_regionl(Vector2i.ZERO)
	check(matches_region_map(terrain.data, []), "Removing the last region must clear every slot")
	terrain.free()
	camera.free()
	await get_tree().process_frame
	print("Terrain3D native runtime: ", checks - failures, "/", checks, " checks passed")
	get_tree().quit(1 if failures else 0)
