extends SceneTree
# Fixed interpreter for declarative modeling plans. Model output is never code.

const MAX_PLAN_BYTES = 256 * 1024
const MAX_GLB_BYTES = 64 * 1024 * 1024
const PRIMITIVES = ["box", "sphere", "cylinder", "capsule", "torus"]

func _initialize():
	_run.call_deferred()

static func _keys(value: Dictionary, expected: Array) -> bool:
	if value.size() != expected.size(): return false
	for key in expected:
		if not value.has(key): return false
	return true

static func _name_ok(value) -> bool:
	if not value is String or value.is_empty() or value.length() > 80 or value.strip_edges().is_empty() or value != value.strip_edges(): return false
	for character in ['.', '/', '\\', ':', '@', '%', '"']:
		if value.contains(character): return false
	for index in value.length():
		var code = value.unicode_at(index)
		if code < 32 or code == 127: return false
	return true

static func _numbers(value, count: int, minimum: float, maximum: float) -> bool:
	if not value is Array or value.size() != count: return false
	for number in value:
		if typeof(number) not in [TYPE_INT, TYPE_FLOAT]: return false
		if not is_finite(float(number)) or float(number) < minimum or float(number) > maximum: return false
	return true

static func validate_plan(plan) -> String:
	if not plan is Dictionary or not _keys(plan, ["version", "name", "parts"]): return "plan_fields_invalid"
	if typeof(plan.version) not in [TYPE_INT, TYPE_FLOAT] or plan.version != 1: return "plan_version_invalid"
	if not _name_ok(plan.name): return "plan_name_invalid"
	if not plan.parts is Array or plan.parts.is_empty() or plan.parts.size() > 64: return "plan_parts_invalid"
	var names = {}
	for part in plan.parts:
		if not part is Dictionary or not _keys(part, ["name", "primitive", "position", "rotation_degrees", "size", "color"]): return "part_fields_invalid"
		if not _name_ok(part.name) or names.has(part.name): return "part_name_invalid"
		names[part.name] = true
		if not part.primitive is String or part.primitive not in PRIMITIVES: return "primitive_invalid"
		if not _numbers(part.position, 3, -100, 100): return "position_invalid"
		if not _numbers(part.rotation_degrees, 3, -3600, 3600): return "rotation_invalid"
		if not _numbers(part.size, 3, 0.001, 100): return "size_invalid"
		if not _numbers(part.color, 4, 0, 1): return "color_invalid"
	return ""

static func _vector(values: Array) -> Vector3:
	return Vector3(values[0], values[1], values[2])

static func create_scene(plan: Dictionary) -> Node3D:
	if not validate_plan(plan).is_empty(): return null
	var scene = Node3D.new()
	scene.name = plan.name
	for part in plan.parts:
		var mesh: PrimitiveMesh
		match part.primitive:
			"box":
				mesh = BoxMesh.new()
				mesh.size = Vector3.ONE
			"sphere":
				mesh = SphereMesh.new()
				mesh.radius = 0.5
				mesh.height = 1.0
				mesh.radial_segments = 16
				mesh.rings = 8
			"cylinder":
				mesh = CylinderMesh.new()
				mesh.top_radius = 0.5
				mesh.bottom_radius = 0.5
				mesh.height = 1.0
				mesh.radial_segments = 16
			"capsule":
				mesh = CapsuleMesh.new()
				mesh.radius = 0.25
				mesh.height = 1.0
				mesh.radial_segments = 16
				mesh.rings = 8
			"torus":
				mesh = TorusMesh.new()
				mesh.inner_radius = 0.25
				mesh.outer_radius = 0.5
				mesh.rings = 16
				mesh.ring_segments = 8
		var material = StandardMaterial3D.new()
		material.albedo_color = Color(part.color[0], part.color[1], part.color[2], part.color[3])
		material.roughness = 0.75
		if part.color[3] < 1.0: material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mesh.material = material
		var instance = MeshInstance3D.new()
		instance.name = part.name
		instance.mesh = mesh
		instance.position = _vector(part.position)
		instance.rotation_degrees = _vector(part.rotation_degrees)
		instance.scale = _vector(part.size)
		scene.add_child(instance)
		instance.owner = scene
	return scene

static func geometry_summary(scene: Node3D) -> Dictionary:
	var vertices = 0
	var triangles = 0
	var bounds = AABB()
	var initialized = false
	var meshes = scene.find_children("*", "MeshInstance3D", true, false)
	for instance in meshes:
		if instance.mesh == null: return {"ok":false, "error":"mesh_missing"}
		for surface in instance.mesh.get_surface_count():
			var arrays = instance.mesh.surface_get_arrays(surface)
			var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var indices = arrays[Mesh.ARRAY_INDEX]
			if positions.is_empty(): return {"ok":false, "error":"geometry_empty"}
			vertices += positions.size()
			triangles += (indices.size() if indices != null and not indices.is_empty() else positions.size()) / 3
			for point in positions:
				var transformed = instance.transform * point
				if not transformed.is_finite(): return {"ok":false, "error":"geometry_nonfinite"}
				if initialized: bounds = bounds.expand(transformed)
				else:
					bounds = AABB(transformed, Vector3.ZERO)
					initialized = true
	return {"ok":initialized and vertices > 0 and triangles > 0, "parts":meshes.size(), "vertices":vertices, "triangles":triangles,
		"bounds_min":[bounds.position.x, bounds.position.y, bounds.position.z],
		"bounds_max":[bounds.end.x, bounds.end.y, bounds.end.z]}

static func export_plan(plan, output_path: String, parent: Node = null) -> Dictionary:
	var problem = validate_plan(plan)
	if not problem.is_empty(): return {"ok":false, "error":problem}
	if not output_path.is_absolute_path() or output_path.get_extension().to_lower() != "glb": return {"ok":false, "error":"output_path_invalid"}
	if FileAccess.file_exists(output_path) or FileAccess.file_exists(output_path + ".receipt.json"): return {"ok":false, "error":"output_exists"}
	if not DirAccess.dir_exists_absolute(output_path.get_base_dir()): return {"ok":false, "error":"output_directory_missing"}
	var scene = create_scene(plan)
	if parent != null: parent.add_child(scene)
	var summary = geometry_summary(scene)
	if not summary.ok or summary.parts != plan.parts.size():
		scene.free()
		return {"ok":false, "error":"geometry_invalid"}
	var state = GLTFState.new()
	var document = GLTFDocument.new()
	var error = document.append_from_scene(scene, state)
	if error == OK: error = document.write_to_filesystem(state, output_path)
	scene.free()
	if error != OK: return {"ok":false, "error":"glb_export_failed", "code":error}
	var file = FileAccess.open(output_path, FileAccess.READ)
	if file == null: return {"ok":false, "error":"glb_missing"}
	var length = file.get_length()
	var magic = file.get_buffer(4).get_string_from_ascii()
	file.close()
	if length <= 20 or length > MAX_GLB_BYTES or magic != "glTF": return {"ok":false, "error":"glb_invalid"}
	summary["bytes"] = length
	summary["sha256"] = FileAccess.get_sha256(output_path)
	return summary

func _run():
	var arguments = OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("modeling_builder requires PLAN.json OUTPUT.glb")
		quit(2)
		return
	var input = FileAccess.open(arguments[0], FileAccess.READ)
	if input == null or input.get_length() > MAX_PLAN_BYTES:
		push_error("modeling plan missing or oversized")
		quit(2)
		return
	var parser = JSON.new()
	var error = parser.parse(input.get_as_text())
	input.close()
	if error != OK:
		push_error("modeling plan JSON invalid")
		quit(2)
		return
	var result = export_plan(parser.data, arguments[1], root)
	if not result.ok:
		push_error("modeling build failed: " + str(result.get("error", "unknown")))
		quit(1)
		return
	var receipt = FileAccess.open(arguments[1] + ".receipt.json", FileAccess.WRITE)
	if receipt == null:
		push_error("modeling receipt could not be created")
		quit(1)
		return
	receipt.store_string(JSON.stringify(result, "  "))
	receipt.flush()
	var write_error = receipt.get_error()
	receipt.close()
	if write_error != OK:
		quit(1)
		return
	print("MALIANG_MODELING_BUILD_OK " + JSON.stringify(result))
	quit(0)
