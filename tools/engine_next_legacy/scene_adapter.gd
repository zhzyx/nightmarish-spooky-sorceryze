extends SceneTree


func _fail(code: String, message: String) -> void:
	print(JSON.stringify({"ok": false, "code": code, "message": message}))
	quit(1)


func _arguments() -> Dictionary:
	var result = {}
	var values = OS.get_cmdline_user_args()
	if values.size() % 2 != 0:
		return {}
	var index = 0
	while index < values.size():
		if not values[index].begins_with("--"):
			return {}
		result[values[index].substr(2)] = values[index + 1]
		index += 2
	return result


func _json_file(path: String) -> Variant:
	var file = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return null
	var parser = JSON.new()
	if parser.parse(file.get_as_text()) != OK:
		return null
	return parser.data


func _write_json(path: String, value: Variant) -> bool:
	if FileAccess.file_exists(path):
		return false
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(value, "\t", true, true) + "\n")
	return file.get_error() == OK


func _load_package(next_asset: String, package: String) -> Dictionary:
	var output = []
	var status = OS.execute(next_asset, PackedStringArray(["inspect", "--package", package]), output, true)
	if status != 0 or output.is_empty():
		_fail("package_inspect", "next_asset inspect rejected the package")
		return {}
	var identity = JSON.parse_string(output[0])
	if not identity is Dictionary or not identity.get("valid", false):
		_fail("package_inspect", "package identity is malformed")
		return {}
	var scene = _json_file(package.path_join("Scene.json"))
	var manifest = _json_file(package.path_join("AssetManifest.json"))
	if not scene is Dictionary or not manifest is Dictionary:
		_fail("package_read", "Scene or AssetManifest is unreadable")
		return {}
	return {"scene": scene, "manifest": manifest, "identity": identity, "path": package}


func _find_asset(manifest: Dictionary, asset_id: String) -> Dictionary:
	for asset in manifest.get("assets", []):
		if asset.get("asset_id", "") == asset_id:
			return asset
	return {}


func _copy_asset(package: String, asset: Dictionary, work_dir: String) -> String:
	var digest = asset.get("content_sha256", "")
	var media_type = asset.get("media_type", "")
	var extension = ""
	match media_type:
		"model/gltf-binary":
			extension = ".glb"
		"image/png":
			extension = ".png"
		"image/jpeg":
			extension = ".jpg"
		_:
			return ""
	var target_dir = work_dir.path_join("resolved")
	if DirAccess.make_dir_recursive_absolute(target_dir) != OK:
		return ""
	var target = target_dir.path_join(asset.get("asset_id", "asset") + extension)
	var bytes = FileAccess.get_file_as_bytes(package.path_join("blobs").path_join(digest))
	if bytes.is_empty() or FileAccess.get_sha256(package.path_join("blobs").path_join(digest)) != digest:
		return ""
	var file = FileAccess.open(target, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_buffer(bytes)
	return target


func _find_mesh(node: Node) -> Mesh:
	if node is MeshInstance3D and node.mesh != null:
		return node.mesh
	if node is ImporterMeshInstance3D and node.get_mesh() != null:
		return node.get_mesh().get_mesh()
	for child in node.get_children():
		var mesh = _find_mesh(child)
		if mesh != null:
			return mesh
	return null


func _mesh_from_file(path: String) -> Mesh:
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(path, state, 0) != OK:
		return null
	var generated = document.generate_scene(state)
	if generated == null:
		return null
	var mesh = _find_mesh(generated)
	generated.free()
	return mesh


func _build_nodes(package: Dictionary, work_dir: String) -> Dictionary:
	var scene: Dictionary = package.scene
	var world = Node3D.new()
	world.name = "M3Scene"
	world.set_meta("scene_id", scene.get("scene_id", ""))
	world.set_meta("scene_revision", scene.get("scene_revision", ""))
	world.set_meta("simulation", scene.get("simulation", {}))
	var nodes = {}
	var entities: Array = scene.get("entities", []).duplicate(true)
	entities.sort_custom(func(left, right): return int(left.entity_id) < int(right.entity_id))
	for entity in entities:
		var node: Node3D = null
		match entity.get("node_type", ""):
			"Node3D":
				node = Node3D.new()
			"MeshInstance3D":
				node = MeshInstance3D.new()
			_:
				world.free()
				return {}
		var entity_id = int(entity.entity_id)
		node.name = entity.name
		node.set_meta("entity_id", entity_id)
		node.set_meta("gameplay_kind", entity.gameplay.kind)
		node.set_meta("asset_refs", entity.get("assets", []).duplicate(true))
		var transform: Dictionary = entity.transform
		var translation = transform.translation
		var rotation = transform.rotation_xyzw
		var scale = transform.scale
		var basis = Basis(Quaternion(rotation[0], rotation[1], rotation[2], rotation[3])).scaled(Vector3(scale[0], scale[1], scale[2]))
		node.transform = Transform3D(basis, Vector3(translation[0], translation[1], translation[2]))
		var resolved = {}
		for ref in entity.get("assets", []):
			var asset = _find_asset(package.manifest, ref.asset_id)
			if asset.is_empty() or asset.get("revision", "") != ref.revision or asset.get("content_sha256", "") != ref.content_sha256:
				world.free()
				return {}
			var resolved_path = _copy_asset(package.path, asset, work_dir)
			if resolved_path.is_empty():
				world.free()
				return {}
			if ref.role == "mesh":
				var mesh = _mesh_from_file(resolved_path)
				if mesh == null or not node is MeshInstance3D:
					world.free()
					return {}
				node.mesh = mesh
			elif ref.role == "texture":
				var image = Image.load_from_file(resolved_path)
				if image == null or image.is_empty():
					world.free()
					return {}
			resolved[ref.role] = {"asset_id": ref.asset_id, "revision": ref.revision, "content_sha256": ref.content_sha256}
		node.set_meta("resolved_assets", resolved)
		nodes[entity_id] = node
		world.add_child(node)
	for entity in entities:
		var entity_id = int(entity.entity_id)
		var parent_id = int(entity.parent_entity_id)
		if parent_id == 0:
			continue
		if not nodes.has(parent_id):
			world.free()
			return {}
		nodes[entity_id].reparent(nodes[parent_id], false)
	return {"world": world, "nodes": nodes}


func _set_owner(node: Node, owner: Node) -> void:
	for child in node.get_children():
		child.owner = owner
		_set_owner(child, owner)


func _collect_nodes(node: Node, output: Dictionary) -> void:
	if node.has_meta("entity_id"):
		output[int(node.get_meta("entity_id"))] = node
	for child in node.get_children():
		_collect_nodes(child, output)


func _compare_nodes(scene: Dictionary, actual: Dictionary, world: Node) -> bool:
	if world.get_meta("scene_id", "") != scene.get("scene_id", "") or world.get_meta("scene_revision", "") != scene.get("scene_revision", ""):
		return false
	if world.get_meta("simulation", {}) != scene.get("simulation", {}):
		return false
	for entity in scene.get("entities", []):
		var entity_id = int(entity.entity_id)
		if not actual.has(entity_id):
			return false
		var node: Node3D = actual[entity_id]
		if node.name != entity.name or node.get_meta("gameplay_kind", "") != entity.gameplay.kind:
			return false
		var parent_id = int(entity.parent_entity_id)
		if parent_id == 0 and node.get_parent() != world:
			return false
		if parent_id != 0 and (not actual.has(parent_id) or node.get_parent() != actual[parent_id]):
			return false
		var refs: Array = entity.get("assets", [])
		if node.get_meta("asset_refs", []) != refs:
			return false
		var resolved: Dictionary = node.get_meta("resolved_assets", {})
		if resolved.size() != refs.size():
			return false
		for ref in refs:
			if not resolved.has(ref.role):
				return false
			var binding = resolved[ref.role]
			if binding.get("asset_id", "") != ref.asset_id or binding.get("revision", "") != ref.revision or binding.get("content_sha256", "") != ref.content_sha256:
				return false
			if ref.role == "mesh" and (not node is MeshInstance3D or node.mesh == null):
				return false
		var transform: Dictionary = entity.transform
		var translation = transform.translation
		var rotation = transform.rotation_xyzw
		var scale = transform.scale
		var expected = Transform3D(Basis(Quaternion(rotation[0], rotation[1], rotation[2], rotation[3])).scaled(Vector3(scale[0], scale[1], scale[2])), Vector3(translation[0], translation[1], translation[2]))
		if not node.transform.is_equal_approx(expected):
			return false
	return actual.size() == scene.get("entities", []).size()


func _asset_id(path: String) -> String:
	var value = path.get_file().get_basename()
	var regex = RegEx.new()
	if regex.compile("^[A-Za-z0-9][A-Za-z0-9._-]*$") != OK or regex.search(value) == null:
		return ""
	return value


func _attr(config: ConfigFile, section: String, key: String, default: Variant) -> Variant:
	return config.get_value(section, "__attr_" + key, default)


func _import_scene(input: String, source_root: String, request_output: String, stage_root: String) -> Dictionary:
	if not input.simplify_path().begins_with(source_root.simplify_path().rstrip("/") + "/"):
		_fail("input_escape", "input scene must be inside source-root")
		return {}
	var source_file = FileAccess.open(input, FileAccess.READ)
	if source_file == null:
		_fail("scene_read", "unable to read input scene")
		return {}
	var source = source_file.get_as_text()
	var attribute_parser = RegEx.new()
	if attribute_parser.compile("([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(\"(?:[^\"\\\\]|\\\\.)*\"|[^\\s\\]]+)") != OK:
		_fail("parser_setup", "unable to initialize the attribute parser")
		return {}
	var normalized = ""
	for line in source.split("\n"):
		var trimmed = line.strip_edges()
		if trimmed.begins_with("[gd_scene") or trimmed.begins_with("[ext_resource") or trimmed.begins_with("[node"):
			if trimmed.begins_with("[gd_scene"):
				line = line.replace("[gd_scene", "[scene_meta")
			elif trimmed.begins_with("[ext_resource"):
				line = line.replace("[ext_resource", "[asset_meta")
			if not trimmed.begins_with("[node"):
				line += "\n__present = true"
			for match in attribute_parser.search_all(trimmed):
				line += "\n__attr_" + match.get_string(1) + " = " + match.get_string(2)
		normalized += line + "\n"
	var config = ConfigFile.new()
	if config.parse(normalized) != OK:
		_fail("scene_parse", "only parseable .tscn input is accepted")
		return {}
	var scene = {"schema_version": 1, "scene_id": "", "scene_revision": "", "simulation": {"fixed_step_ms": 16, "max_speed": 8}, "entities": []}
	var extensions = {}
	var nodes = []
	for section in config.get_sections():
		var keys = config.get_section_keys(section)
		if section.begins_with("scene_meta"):
			for key in keys:
				var normalized_key = key.trim_prefix("__attr_") if key.begins_with("__attr_") else key
				if key != "__present" and normalized_key not in ["format", "load_steps", "scene_id", "scene_revision", "fixed_step_ms", "max_speed"]:
					_fail("unsupported_scene_property", "Unsupported gd_scene property: " + key)
					return {}
			if _attr(config, section, "format", 0) != 3:
				_fail("scene_format", "only format=3 is accepted")
				return {}
			scene.scene_id = _attr(config, section, "scene_id", "")
			scene.scene_revision = _attr(config, section, "scene_revision", "")
			scene.simulation.fixed_step_ms = _attr(config, section, "fixed_step_ms", 16)
			scene.simulation.max_speed = _attr(config, section, "max_speed", 8)
		elif section.begins_with("asset_meta "):
			for key in keys:
				var normalized_key = key.trim_prefix("__attr_") if key.begins_with("__attr_") else key
				if key != "__present" and normalized_key not in ["type", "path", "id"]:
					_fail("unsupported_external", "UID and unsupported external fields are rejected: " + key)
					return {}
			var path = str(_attr(config, section, "path", ""))
			if not path.begins_with("res://") or path.contains("..") or path.contains("\\"):
				_fail("external_uri", "only local res:// asset paths are accepted")
				return {}
			var id = str(_attr(config, section, "id", ""))
			extensions[id] = {"path": path, "declared_type": _attr(config, section, "type", "")}
		elif section.begins_with("node "):
			for key in keys:
				var normalized_key = key.trim_prefix("__attr_") if key.begins_with("__attr_") else key
				if key != "__present" and normalized_key not in ["name", "type", "parent", "transform", "metadata/entity_id", "metadata/gameplay_kind", "metadata/mesh_resource", "metadata/texture_resource"]:
					_fail("unsupported_node_property", "Scripts, inheritance and unmapped properties are rejected: " + key)
					return {}
			var values = {}
			for key in keys:
				values[key] = config.get_value(section, key)
				if key.begins_with("__attr_"):
					values[key.trim_prefix("__attr_")] = values[key]
			nodes.append(values)
		else:
			_fail("unsupported_section", "Only gd_scene, ext_resource and node sections are accepted: " + section)
			return {}
	if scene.scene_id.is_empty() or scene.scene_revision.is_empty() or nodes.is_empty():
		_fail("missing_scene_identity", "scene identity and at least one node are required")
		return {}
	var request_assets = {}
	var paths = {}
	var names = {}
	var used_extensions = {}
	for node in nodes:
		var name = str(node.get("name", ""))
		var type = str(node.get("type", ""))
		if type not in ["Node3D", "MeshInstance3D"] or name.is_empty() or names.has(name):
			_fail("unsupported_node", "only uniquely named Node3D/MeshInstance3D nodes are accepted")
			return {}
		names[name] = true
		var entity_id = int(node.get("metadata/entity_id", 0))
		var kind = str(node.get("metadata/gameplay_kind", ""))
		if entity_id <= 0 or kind not in ["player_spawn", "static"]:
			_fail("gameplay_metadata", "positive entity_id and supported gameplay_kind are required")
			return {}
		var parent_id = 0
		var node_path = ""
		if node.has("parent"):
			var parent_path = str(node.parent)
			if parent_path == ".":
				parent_path = ""
			if not paths.has(parent_path):
				_fail("missing_parent", "parent node must already exist")
				return {}
			parent_id = paths[parent_path]
			node_path = parent_path.path_join(name)
		elif not paths.is_empty():
			_fail("multiple_roots", "only one root node is accepted")
			return {}
		paths[node_path] = entity_id
		var transform = {"translation": [0, 0, 0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]}
		if node.has("transform"):
			if typeof(node.transform) != TYPE_TRANSFORM3D:
				_fail("transform_type", "transform must be Transform3D")
				return {}
			var value: Transform3D = node.transform
			transform.translation = [value.origin.x, value.origin.y, value.origin.z]
			var scale = value.basis.get_scale()
			transform.scale = [scale.x, scale.y, scale.z]
			var quaternion = value.orthonormalized().basis.get_rotation_quaternion()
			transform.rotation_xyzw = [quaternion.x, quaternion.y, quaternion.z, quaternion.w]
		var refs = []
		for role in ["mesh", "texture"]:
			var key = "metadata/" + role + "_resource"
			if not node.has(key):
				continue
			var extension_id = str(node[key])
			if not extensions.has(extension_id):
				_fail("missing_asset", "asset reference must name a declared ext_resource")
				return {}
			var extension = extensions[extension_id]
			var resource_path: String = extension.path
			var suffix = resource_path.get_extension().to_lower()
			var asset_type = ""
			var media_type = ""
			var declared_type = ""
			if role == "mesh" and suffix == "glb":
				asset_type = "mesh"
				media_type = "model/gltf-binary"
				declared_type = "PackedScene"
			elif role == "texture" and suffix in ["png", "jpg", "jpeg"]:
				asset_type = "image"
				media_type = "image/png" if suffix == "png" else "image/jpeg"
				declared_type = "Texture2D"
			else:
				_fail("asset_type", "asset role and extension must match the whitelist")
				return {}
			if extension.declared_type != declared_type:
				_fail("asset_declaration", "ext_resource type does not match its role")
				return {}
			var asset_id = _asset_id(resource_path)
			if asset_id.is_empty():
				_fail("asset_id", "asset filename cannot form a stable AssetId")
				return {}
			var local_path = source_root.path_join(resource_path.trim_prefix("res://"))
			if not FileAccess.file_exists(local_path):
				_fail("missing_asset", "referenced local asset does not exist")
				return {}
			var digest = FileAccess.get_sha256(local_path)
			if request_assets.has(asset_id) and request_assets[asset_id].path != resource_path.get_file():
				_fail("duplicate_asset", "duplicate AssetId with different source")
				return {}
			request_assets[asset_id] = {"path": resource_path.get_file(), "local_path": local_path, "type": asset_type, "media_type": media_type, "digest": digest}
			used_extensions[extension_id] = true
			refs.append({"role": role, "asset_id": asset_id, "revision": digest, "content_sha256": digest})
		if type == "MeshInstance3D" and refs.filter(func(ref): return ref.role == "mesh").size() != 1:
			_fail("mesh_reference", "MeshInstance3D requires exactly one mesh resource")
			return {}
		if type == "Node3D" and refs.filter(func(ref): return ref.role == "mesh").size() != 0:
			_fail("mesh_reference", "Node3D cannot contain a mesh resource")
			return {}
		scene.entities.append({"entity_id": entity_id, "name": name, "node_type": type, "parent_entity_id": parent_id, "transform": transform, "gameplay": {"kind": kind}, "assets": refs})
	for extension_id in extensions:
		if not used_extensions.has(extension_id):
			_fail("unused_asset", "unused external resources are rejected")
			return {}
	if DirAccess.make_dir_recursive_absolute(stage_root) != OK:
		_fail("stage_create", "unable to create staged asset directory")
		return {}
	var assets = []
	for asset_id in request_assets:
		var asset: Dictionary = request_assets[asset_id]
		var target = stage_root.path_join(asset.path)
		var bytes = FileAccess.get_file_as_bytes(asset.local_path)
		var file = FileAccess.open(target, FileAccess.WRITE)
		if bytes.is_empty() or file == null:
			_fail("stage_write", "unable to stage source asset")
			return {}
		file.store_buffer(bytes)
		assets.append({"asset_id": asset_id, "revision": asset.digest, "type": asset.type, "media_type": asset.media_type, "dependencies": [], "source": {"kind": "godot_whitelist_import", "importer_version": "1"}, "path": asset.path})
	var request = {"schema_version": 1, "scene": scene, "assets": assets}
	if not _write_json(request_output, request):
		_fail("request_write", "request output must not exist and must be writable")
		return {}
	return request


func _run() -> void:
	var args = _arguments()
	var action = args.get("action", "")
	if action in ["verify", "publish"]:
		for required in ["package", "next-asset", "work-dir"]:
			if not args.has(required):
				_fail("arguments", "missing --" + required)
				return
		if action == "publish" and (not args.has("output") or FileAccess.file_exists(args.output)):
			_fail("no_clobber", "publish output must be new")
			return
		var package = _load_package(args["next-asset"], args.package)
		if package.is_empty():
			return
		var built = _build_nodes(package, args["work-dir"])
		if built.is_empty():
			_fail("scene_build", "unable to instantiate legacy nodes or resources")
			return
		var actual: Dictionary = built.nodes
		var instance: Node = null
		if args.has("scene"):
			var packed = ResourceLoader.load(args.scene)
			if packed == null or not packed is PackedScene:
				built.world.free()
				_fail("scene_load", "published scene cannot be loaded")
				return
			instance = packed.instantiate()
			actual = {}
			_collect_nodes(instance, actual)
		if not _compare_nodes(package.scene, actual, instance if instance != null else built.world):
			if instance != null:
				instance.free()
			built.world.free()
			_fail("semantic_mismatch", "legacy nodes differ from the neutral scene")
			return
		if action == "publish":
			_set_owner(built.world, built.world)
			var packed_scene = PackedScene.new()
			if packed_scene.pack(built.world) != OK or ResourceSaver.save(packed_scene, args.output) != OK:
				built.world.free()
				_fail("publish", "unable to save legacy scene")
				return
		print(JSON.stringify({"ok": true, "action": action, "scene_id": package.scene.scene_id, "scene_revision": package.scene.scene_revision, "package_digest": package.identity.package_digest, "entity_count": actual.size()}))
		if args.has("scene"):
			instance.free()
		built.world.free()
		quit(0)
	elif action == "import":
		for required in ["input", "source-root", "request-output", "stage-root"]:
			if not args.has(required):
				_fail("arguments", "missing --" + required)
				return
		var request = _import_scene(args.input, args["source-root"], args["request-output"], args["stage-root"])
		if not request.is_empty():
			print(JSON.stringify({"ok": true, "action": action, "entity_count": request.scene.entities.size(), "asset_count": request.assets.size(), "request": args["request-output"]}))
			quit(0)
	else:
		_fail("arguments", "expected verify, publish or import")


func _init() -> void:
	call_deferred("_run")
