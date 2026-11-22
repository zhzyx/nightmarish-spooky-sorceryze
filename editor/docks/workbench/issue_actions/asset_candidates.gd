@tool
extends VBoxContainer

const SECTION := "workbench_asset_candidates"
const PREVIEW_BYTES := 8 * 1024 * 1024

var detail: Node
var key := ""
var pairs := {}
var entries := OptionButton.new()
var reopen := Button.new()
var dialog := AcceptDialog.new()
var columns := HBoxContainer.new()
var status := Label.new()
var current := ""


func _ready() -> void:
	detail = get_parent()
	detail.detail_changed.connect(_refresh)
	reopen.text = "比较本机资产候选…"
	reopen.pressed.connect(func(): _open(str(entries.get_selected_metadata())))
	add_child(entries)
	add_child(reopen)
	dialog.title = "选择本机资产版本"
	dialog.get_ok_button().text = "关闭"
	add_child(dialog)
	var box := VBoxContainer.new()
	dialog.add_child(box)
	box.add_child(columns)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)
	_refresh()


func _refresh() -> void:
	dialog.hide()
	current = ""
	entries.clear()
	pairs = {}
	key = ""
	hide()
	var issue: Dictionary = detail.get_detail()
	var session = detail.get_parent()
	var identity: Dictionary = session.get_identity()
	if issue.is_empty() or identity.is_empty():
		return
	key = JSON.stringify([session._origin, identity.id, identity.project, issue.id]).sha256_text()
	pairs = EditorInterface.get_editor_settings().get_project_metadata(SECTION, key, {})
	for id: String in pairs:
		_add_entry(id)
	visible = not pairs.is_empty()


func _add_entry(id: String) -> void:
	var pair: Dictionary = pairs[id]
	entries.add_item("%s · #%d · %s" % [str(pair.original).get_file(), int(pair.ref.version), str(pair.ref.revision).left(12)])
	entries.set_item_metadata(entries.item_count - 1, id)
	entries.set_item_tooltip(entries.item_count - 1, pair.original)


func preserve(temporary: String, original: String, ref: Dictionary) -> String:
	var human := FileAccess.get_sha256(original)
	if key.is_empty() or human.is_empty():
		return "无法读取已有原件，请另选保存位置"
	var extension := original.get_extension()
	var filename := "candidate-%s" % str(ref.digest)
	if not extension.is_empty():
		filename += "." + extension
	var candidate := original.get_base_dir().path_join(filename)
	var install: Callable = detail.get_meta("install_asset_if_absent")
	var result: int = install.call(temporary, candidate)
	if result == ERR_ALREADY_EXISTS and FileAccess.get_sha256(candidate) != ref.digest:
		# A person may also have edited a previously exported candidate. Preserve that file too.
		candidate = original.get_base_dir().path_join(Crypto.new().generate_random_bytes(8).hex_encode() + "-" + filename)
		result = install.call(temporary, candidate)
	if result != OK and (result != ERR_ALREADY_EXISTS or FileAccess.get_sha256(candidate) != ref.digest):
		return "独立候选路径不可用，请另选保存位置"
	var id := JSON.stringify([original, human, candidate, ref.module, ref.revision, ref.path]).sha256_text()
	if not pairs.has(id):
		pairs[id] = {"original": original, "original_digest": human, "candidate": candidate, "ref": ref.duplicate(true), "selected": {}}
		EditorInterface.get_editor_settings().set_project_metadata(SECTION, key, pairs)
		_add_entry(id)
	for index in entries.item_count:
		if entries.get_item_metadata(index) == id:
			entries.select(index)
			break
	show()
	_open(id)
	return "已保留本机原件及独立候选　%s" % candidate


func _open(id: String) -> void:
	if not pairs.has(id):
		return
	current = id
	var pair: Dictionary = pairs[id]
	for child in columns.get_children():
		columns.remove_child(child)
		child.queue_free()
	_card("本机原件", pair.original, pair.original_digest)
	_card("工单候选", pair.candidate, pair.ref.digest)
	status.text = "请选择要使用的版本" if pair.selected.is_empty() else "上次选定　%s" % pair.selected.path
	dialog.popup_centered()


func _card(title: String, path: String, digest: String) -> void:
	var card := VBoxContainer.new()
	card.custom_minimum_size.x = 260 * EditorInterface.get_editor_scale()
	columns.add_child(card)
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	label.text = "%s\n%s\nSHA-256 %s" % [title, path, digest]
	card.add_child(label)
	var select := Button.new()
	select.text = "选用%s" % title
	select.pressed.connect(_choose.bind(path, digest))
	var file := FileAccess.open(path, FileAccess.READ)
	if not file or FileAccess.get_sha256(path) != digest:
		label.text += "\n原件已变化或不可读，请重新保存候选"
		select.disabled = true
	elif file.get_length() <= PREVIEW_BYTES:
		var bytes := file.get_buffer(file.get_length())
		var checksum := HashingContext.new()
		checksum.start(HashingContext.HASH_SHA256)
		checksum.update(bytes)
		if checksum.finish().hex_encode() != digest:
			label.text += "\n预览时原件已变化，请重新保存候选"
			select.disabled = true
		elif not _preview(card, bytes):
			label.text += "\n%d 字节 · %s" % [bytes.size(), bytes.slice(0, 32).hex_encode()]
	else:
		label.text += "\n%d 字节（超过预览上限）" % file.get_length()
	card.add_child(select)


func _choose(path: String, digest: String) -> void:
	if not dialog.visible or not pairs.has(current):
		return
	var pair: Dictionary = pairs[current]
	if FileAccess.get_sha256(pair.original) != pair.original_digest or FileAccess.get_sha256(pair.candidate) != pair.ref.digest:
		status.text = "资产已变化，请重新保存候选"
		return
	pair.selected = {"path": path, "digest": digest}
	EditorInterface.get_editor_settings().set_project_metadata(SECTION, key, pairs)
	status.text = "已选定　%s" % path


func _preview(card: VBoxContainer, bytes: PackedByteArray) -> bool:
	if bytes.size() >= 24 and bytes.slice(0, 8).hex_encode() == "89504e470d0a1a0a":
		# PNG dimensions are big-endian; bound allocation before invoking the decoder.
		var header := StreamPeerBuffer.new()
		header.data_array = bytes.slice(16, 24)
		header.big_endian = true
		var width := header.get_u32()
		var height := header.get_u32()
		if width < 1 or height < 1 or width > 4096 or height > 4096:
			return false
		var image := Image.new()
		if image.load_png_from_buffer(bytes) != OK:
			return false
		var texture := TextureRect.new()
		texture.custom_minimum_size.y = 150
		texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		texture.texture = ImageTexture.create_from_image(image)
		card.add_child(texture)
		return true
	return _model_preview(card, bytes)


func _model_preview(card: VBoxContainer, bytes: PackedByteArray) -> bool:
	if bytes.size() < 28 or bytes.decode_u32(0) != 0x46546c67 or bytes.decode_u32(4) != 2 or bytes.decode_u32(8) != bytes.size():
		return false
	var end := 20 + bytes.decode_u32(12)
	if end > bytes.size() - 8 or bytes.decode_u32(16) != 0x4e4f534a or bytes.decode_u32(end + 4) != 0x004e4942 or bytes.decode_u32(end) != bytes.size() - end - 8:
		return false
	var description: Variant = JSON.parse_string(bytes.slice(20, end).get_string_from_utf8())
	if not description is Dictionary or not description.get("accessors") is Array or not description.get("buffers") is Array:
		return false
	# Only preview self-contained geometry. Leave extensions and external resources for their native consumer.
	var pending: Array = [description]
	while not pending.is_empty():
		var item: Variant = pending.pop_back()
		if item is Dictionary:
			if item.has("uri") or item.has("extensions"):
				return false
			pending.append_array(item.values())
		elif item is Array:
			pending.append_array(item)
	if description.buffers.size() != 1 or not description.buffers[0] is Dictionary:
		return false
	var length: Variant = description.buffers[0].get("byteLength")
	if not (length is int or length is float) or length <= 0 or length > bytes.size() - end - 8:
		return false
	var elements := 0
	for accessor: Variant in description.accessors:
		if not accessor is Dictionary:
			return false
		var count: Variant = accessor.get("count")
		if not (count is int or count is float) or count <= 0 or count > 2000000 or floor(count) != count:
			return false
		elements += int(count)
		if elements > 2000000:
			return false
	if not ClassDB.class_exists("GLTFDocument"):
		return false
	var document = ClassDB.instantiate("GLTFDocument")
	var state = ClassDB.instantiate("GLTFState")
	state.handle_binary_image_mode = 0 # Discard images in geometry previews.
	if document.append_from_buffer(bytes, "", state) != OK:
		return false
	var scene: Node3D = document.generate_scene(state)
	if scene == null:
		return false
	# Display only meshes. Keep scripts, cameras, lights and animations out of the editor scene.
	var viewport := SubViewport.new()
	viewport.size = Vector2i(260, 150)
	viewport.own_world_3d = true
	var model := Node3D.new()
	viewport.add_child(model)
	var bounds := AABB()
	var meshes := _collect_meshes(scene, Transform3D.IDENTITY, model)
	scene.free()
	if meshes == 0:
		viewport.free()
		return false
	for i in meshes:
		var instance := model.get_child(i) as MeshInstance3D
		var box := instance.transform * instance.get_aabb()
		bounds = box if i == 0 else bounds.merge(box)
	var view := SubViewportContainer.new()
	view.custom_minimum_size = Vector2(260, 150)
	view.stretch = true
	card.add_child(view)
	view.add_child(viewport)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40, -30, 0)
	viewport.add_child(light)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	var radius := maxf(0.01, bounds.size.length() * 0.5)
	camera.position = bounds.get_center() + Vector3(0.6, 0.4, 1).normalized() * radius * 3
	camera.near = radius * 0.01
	camera.far = radius * 8
	camera.look_at(bounds.get_center())
	camera.current = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	return true


func _collect_meshes(node: Node, parent_transform: Transform3D, model: Node3D) -> int:
	var transform := parent_transform
	if node is Node3D:
		transform *= node.transform
	var mesh: Mesh
	if node is MeshInstance3D:
		mesh = node.mesh
	elif node is ImporterMeshInstance3D and node.mesh:
		mesh = node.mesh.get_mesh()
	if mesh:
		var instance := MeshInstance3D.new()
		instance.mesh = mesh
		instance.transform = transform
		model.add_child(instance)
	for child in node.get_children():
		_collect_meshes(child, transform, model)
	return model.get_child_count()
