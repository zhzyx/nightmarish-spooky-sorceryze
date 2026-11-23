@tool
extends RefCounted
## Bounded self-contained GLB previews. No project imports, scripts or external URIs.

const PREVIEW_EXTENSIONS := ["GODOT_single_root", "KHR_materials_unlit", "KHR_materials_emissive_strength", "KHR_materials_pbrSpecularGlossiness", "KHR_texture_transform", "KHR_node_visibility"]


static func _integer(value: Variant, maximum: int) -> bool:
	return (value is float or value is int) and is_finite(float(value)) and float(value) == floor(float(value)) and value >= 0 and value <= maximum


static func _safe_json(value: Variant, depth := 0) -> bool:
	if depth > 64:
		return false
	if value is Dictionary:
		for key in value:
			if key == "uri":
				return false
			if key == "extensions":
				if not value[key] is Dictionary:
					return false
				for extension in value[key]:
					if extension not in PREVIEW_EXTENSIONS:
						return false
			if not _safe_json(value[key], depth + 1):
				return false
	elif value is Array:
		for item in value:
			if not _safe_json(item, depth + 1):
				return false
	elif value is float:
		return is_finite(value) and absf(value) <= 1.0e12
	return true


static func _big32(bytes: PackedByteArray, offset: int) -> int:
	return int(bytes[offset]) << 24 | int(bytes[offset + 1]) << 16 | int(bytes[offset + 2]) << 8 | int(bytes[offset + 3])


static func image_dimensions(bytes: PackedByteArray) -> Vector2i:
	if bytes.size() >= 33 and bytes.slice(0, 16).hex_encode() == "89504e470d0a1a0a0000000d49484452":
		return Vector2i(_big32(bytes, 16), _big32(bytes, 20))
	if bytes.size() > 4 and bytes[0] == 0xff and bytes[1] == 0xd8:
		var offset := 2
		while offset + 4 < bytes.size():
			if bytes[offset] != 0xff:
				break
			while offset < bytes.size() and bytes[offset] == 0xff:
				offset += 1
			if offset + 3 >= bytes.size():
				break
			var marker := bytes[offset]
			offset += 1
			if marker in [0xd8, 0xd9, 0xda]:
				break
			var length := int(bytes[offset]) * 256 + bytes[offset + 1]
			if length < 2 or offset + length > bytes.size():
				break
			if marker in [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf] and length >= 8:
				return Vector2i(int(bytes[offset + 5]) * 256 + bytes[offset + 6], int(bytes[offset + 3]) * 256 + bytes[offset + 4])
			offset += length
	return Vector2i.ZERO


static func _acyclic_nodes(nodes: Array) -> bool:
	if nodes.size() > 4096:
		return false
	var counts: Array[int] = []
	counts.resize(nodes.size())
	counts.fill(0)
	var depths: Array[int] = []
	depths.resize(nodes.size())
	depths.fill(0)
	for node in nodes:
		if not node is Dictionary or not node.get("children", []) is Array:
			return false
		for child in node.get("children", []):
			if not _integer(child, nodes.size() - 1):
				return false
			counts[int(child)] += 1
			if counts[int(child)] > 1:
				return false
	var ready: Array[int] = []
	for index in nodes.size():
		if counts[index] == 0:
			ready.append(index)
	var visited := 0
	while not ready.is_empty():
		var index: int = ready.pop_back()
		if depths[index] > 64:
			return false
		visited += 1
		for child in nodes[index].get("children", []):
			depths[int(child)] = depths[index] + 1
			counts[int(child)] -= 1
			if counts[int(child)] == 0:
				ready.append(int(child))
	return visited == nodes.size()


static func validate_glb(bytes: PackedByteArray) -> String:
	if bytes.size() < 28 or bytes.size() > 32 * 1024 * 1024 or bytes.decode_u32(0) != 0x46546c67 or bytes.decode_u32(4) != 2 or bytes.decode_u32(8) != bytes.size() or bytes.decode_u32(16) != 0x4e4f534a:
		return "预览需要 32 MiB 以内的有效 GLB 2.0 文件。"
	var json_end := 20 + bytes.decode_u32(12)
	if json_end > 4 * 1024 * 1024 or json_end + 8 > bytes.size() or bytes.decode_u32(json_end + 4) != 0x004e4942 or json_end + 8 + bytes.decode_u32(json_end) != bytes.size():
		return "模型需要完整的内嵌几何数据。"
	var parsed: Variant = JSON.parse_string(bytes.slice(20, json_end).get_string_from_utf8())
	if not parsed is Dictionary or not _safe_json(parsed):
		return "模型包含外部资源、扩展或无效数值，请下载原件核对。"
	var document: Dictionary = parsed
	if not document.get("asset") is Dictionary or document.asset.get("version") != "2.0" or not document.get("buffers") is Array or document.buffers.size() != 1 or not document.get("meshes") is Array or document.meshes.is_empty() or document.meshes.size() > 4096:
		return "预览支持标准、自包含的 GLB 2.0 网格。"
	for key in ["extensionsRequired", "extensionsUsed"]:
		if not document.get(key, []) is Array:
			return "模型扩展列表无效。"
		for extension in document.get(key, []):
			if extension not in PREVIEW_EXTENSIONS:
				return "模型包含尚不支持的预览扩展，请下载原件核对。"
	var binary_size := bytes.size() - json_end - 8
	if not document.buffers[0] is Dictionary or not _integer(document.buffers[0].get("byteLength"), binary_size):
		return "模型缓冲区长度无效。"
	if not document.get("accessors") is Array or document.accessors.size() > 16384:
		return "模型缺少有效的几何数据。"
	var total := 0
	for accessor in document.accessors:
		if not accessor is Dictionary or not _integer(accessor.get("count"), 2000000) or accessor.count < 1:
			return "模型几何数据超出预览范围。"
		total += int(accessor.count)
	if total > 8000000 or not document.get("nodes", []) is Array or not _acyclic_nodes(document.get("nodes", [])):
		return "模型节点或几何数据超出预览范围。"
	var views: Variant = document.get("bufferViews", [])
	if not views is Array:
		return "模型缓冲区定义无效。"
	for view in views:
		if not view is Dictionary or view.get("buffer") != 0 or not _integer(view.get("byteOffset", 0), binary_size) or not _integer(view.get("byteLength"), binary_size) or int(view.get("byteOffset", 0)) + int(view.byteLength) > binary_size:
			return "模型缓冲区越界。"
	var images: Variant = document.get("images", [])
	if not images is Array or images.size() > 64:
		return "模型纹理数量超出预览范围。"
	var pixels := 0
	for picture in images:
		if not picture is Dictionary or not _integer(picture.get("bufferView"), views.size() - 1) or picture.get("mimeType") not in ["image/png", "image/jpeg"]:
			return "模型预览仅支持内嵌 PNG 或 JPEG 纹理。"
		var view: Dictionary = views[int(picture.bufferView)]
		var offset := json_end + 8 + int(view.get("byteOffset", 0))
		var dimensions := image_dimensions(bytes.slice(offset, offset + int(view.byteLength)))
		if dimensions.x <= 0 or dimensions.y <= 0 or dimensions.x > 16384 or dimensions.y > 16384 or int(dimensions.x) * int(dimensions.y) > 16777216:
			return "模型纹理尺寸超出预览范围。"
		pixels += int(dimensions.x) * int(dimensions.y)
	if pixels > 33554432:
		return "模型纹理总量超出预览范围。"
	return ""


static func _bounds(node: Node, transform: Transform3D, found: Dictionary) -> void:
	var current: Transform3D = transform * node.transform if node is Node3D else transform
	if node is MeshInstance3D and node.mesh:
		var box: AABB = current * node.get_aabb()
		found.box = box if not found.has("box") else found.box.merge(box)
		found.meshes = int(found.get("meshes", 0)) + 1
	for child in node.get_children():
		_bounds(child, current, found)


static func _renderable(node: Node) -> Node:
	# Editor imports retain ImporterMeshInstance3D for the import pipeline.
	# Convert this preview tree locally without changing registered GLTF extensions.
	if node.is_class("ImporterMeshInstance3D"):
		var mesh := MeshInstance3D.new()
		mesh.name = node.name
		mesh.transform = node.transform
		mesh.skin = node.get_skin()
		mesh.skeleton = node.get_skeleton_path()
		mesh.visible = node.visible
		mesh.layers = node.get_layer_mask()
		mesh.cast_shadow = node.get_cast_shadows_setting()
		for property in ["visibility_range_begin", "visibility_range_begin_margin", "visibility_range_end", "visibility_range_end_margin", "visibility_range_fade_mode"]:
			mesh.set(property, node.get(property))
		var imported = node.get_mesh()
		if imported:
			mesh.mesh = imported.get_mesh()
		node.replace_by(mesh)
		node.free()
		node = mesh
	for child in node.get_children():
		_renderable(child)
	return node


static func decode_glb(bytes: PackedByteArray) -> Dictionary:
	var error := validate_glb(bytes)
	if not error.is_empty():
		return {"error": error}
	if not ClassDB.can_instantiate("GLTFDocument") or not ClassDB.can_instantiate("GLTFState"):
		return {"error": "此编辑器未启用 GLTF 预览，可下载原件核对。"}
	var document = ClassDB.instantiate("GLTFDocument")
	var state = ClassDB.instantiate("GLTFState")
	state.create_animations = false
	state.handle_binary_image_mode = 3 # Embed decoded textures; never extract into the project.
	if document.append_from_buffer(bytes, "", state) != OK:
		return {"error": "Godot 无法解析此模型，可下载原件核对。"}
	var root: Node = document.generate_scene(state)
	if not root:
		return {"error": "此模型没有可显示的场景。"}
	root = _renderable(root)
	var found := {}
	_bounds(root, Transform3D.IDENTITY, found)
	if not found.has("box") or not found.box.position.is_finite() or not found.box.size.is_finite() or found.box.size.length() > 1.0e9:
		root.free()
		return {"error": "此模型缺少有效的网格边界。"}
	var scene := PackedScene.new()
	var packed := scene.pack(root)
	root.free()
	return {"scene": scene, "bounds": found.box, "meshes": found.meshes} if packed == OK else {"error": "无法创建模型预览。"}
