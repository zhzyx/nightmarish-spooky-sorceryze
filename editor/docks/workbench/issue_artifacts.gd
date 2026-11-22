@tool
extends VBoxContainer

var _detail: Node
var _session: Node
var _generation := 0
var _route := ""
var _versions := OptionButton.new()
var _upload := Button.new()
var _source := FileDialog.new()
var _save := Button.new()
var _status := Label.new()
var _picker := FileDialog.new()
var compare := Button.new()
var comparison := AcceptDialog.new()
var design := Button.new()
var sides := HBoxContainer.new()
var difference := Label.new()
var selectors: Array[OptionButton] = []
var fields: Array[Label] = []
var previews: Array[TextureRect] = []
var content: Array[Label] = []
var side_requests: Array[int] = [0, 0]
var destinations: Array[FileDialog] = []


func _ready() -> void:
	_detail = get_parent()
	_session = _detail.get_parent()
	_detail.detail_changed.connect(_refresh)
	var title := Label.new()
	title.text = "附件与产物"
	add_child(title)
	_versions.name = "IssueArtifactVersions"
	_versions.fit_to_longest_item = false
	_versions.item_selected.connect(_selected)
	add_child(_versions)
	_upload.name = "UploadIssueArtifact"
	_upload.text = "添加本机文件…"
	_upload.pressed.connect(func(): _source.popup_centered_ratio(0.55))
	add_child(_upload)
	_source.name = "IssueArtifactSource"
	_source.title = "选择工单附件"
	_source.access = FileDialog.ACCESS_FILESYSTEM
	_source.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_source.file_selected.connect(_upload_file)
	add_child(_source)
	_save.name = "SaveIssueArtifact"
	_save.text = "另存所选版本…"
	_save.pressed.connect(_choose_destination)
	add_child(_save)
	_status.name = "IssueArtifactStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_picker.name = "IssueArtifactDestination"
	_picker.title = "保存所选版本"
	_picker.access = FileDialog.ACCESS_FILESYSTEM
	_picker.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_picker.file_selected.connect(_download)
	add_child(_picker)
	compare.text = "并排比较候选…"
	compare.pressed.connect(open_comparison)
	add_child(compare)
	comparison.title = "创意候选比较"
	comparison.get_ok_button().text = "关闭"
	comparison.visibility_changed.connect(_comparison_visibility)
	add_child(comparison)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(650, 310) * EditorInterface.get_editor_scale()
	comparison.add_child(box)
	box.add_child(design)
	design.pressed.connect(func(): comparison.hide(); _detail._open_design_source())
	box.add_child(sides)
	box.add_child(difference)
	for index in 2:
		var side := VBoxContainer.new()
		side.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		sides.add_child(side)
		var selector := OptionButton.new()
		selector.fit_to_longest_item = false
		selector.item_selected.connect(_comparison_selected.bind(index))
		selectors.append(selector)
		side.add_child(selector)
		var field := Label.new()
		field.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
		fields.append(field)
		side.add_child(field)
		var open := Button.new()
		open.text = "打开 %s 原件" % ("A" if index == 0 else "B")
		open.pressed.connect(_open_original.bind(index))
		side.add_child(open)
		var save_original := Button.new()
		save_original.text = "另存完整原件…"
		side.add_child(save_original)
		var destination := FileDialog.new()
		destination.title = "保存此栏所选原件"
		destination.access = FileDialog.ACCESS_FILESYSTEM
		destination.file_mode = FileDialog.FILE_MODE_SAVE_FILE
		comparison.add_child(destination)
		destinations.append(destination)
		save_original.pressed.connect(_choose_original.bind(index))
		destination.file_selected.connect(_save_original.bind(index))
		var preview := TextureRect.new()
		preview.custom_minimum_size.y = 128
		preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		previews.append(preview)
		side.add_child(preview)
		var label := Label.new()
		label.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
		side.add_child(label)
		content.append(label)
	_refresh()


func _comparison_visibility() -> void:
	if comparison.visible:
		return
	for index in 2:
		side_requests[index] += 1
		previews[index].texture = null
		content[index].text = ""
		selectors[index].clear()
		fields[index].text = ""
		destinations[index].hide()


func open_comparison() -> void:
	if _versions.item_count < 2 or _detail.get_detail().is_empty():
		return
	var source: Variant = _detail.get_detail().get("design_source")
	design.visible = source is Dictionary
	if design.visible:
		design.text = "来源设计　%s · v%d 第 %d 段" % [source.document_id, int(source.version), int(source.paragraph)]
	for index in 2:
		var selector := selectors[index]
		selector.clear()
		for row in _versions.item_count:
			selector.add_item(_versions.get_item_text(row))
			selector.set_item_metadata(row, _versions.get_item_metadata(row).duplicate(true))
		selector.select(1 - index)
	for index in 2:
		_comparison_selected(selectors[index].selected, index)
	comparison.popup_centered()


func _comparison_selected(row: int, index: int) -> void:
	destinations[index].hide()
	side_requests[index] += 1
	content[index].text = ""
	previews[index].texture = null
	var ref: Dictionary = selectors[index].get_item_metadata(row)
	fields[index].text = "%s · %s\n%s @ %s\nSHA-256 %s" % [ref.kind, ref.path, ref.module, ref.revision, ref.digest]
	var other: Dictionary = selectors[1 - index].get_selected_metadata()
	difference.text = "两个候选的文件内容相同" if ref.digest == other.digest else "两个候选的文件内容不同"


func _choose_original(index: int) -> void:
	var ref: Dictionary = selectors[index].get_selected_metadata()
	destinations[index].current_file = str(ref.path).get_file().validate_filename()
	destinations[index].popup_centered_ratio(0.55)


func _save_original(destination: String, index: int) -> void:
	if comparison.visible and selectors[index].selected >= 0:
		await _download_reference(destination, selectors[index].get_selected_metadata(), index)


func _open_original(index: int) -> void:
	if not comparison.visible:
		return
	side_requests[index] += 1
	var ticket := side_requests[index]
	var ref: Dictionary = selectors[index].get_selected_metadata()
	var temporary := EditorInterface.get_editor_paths().get_cache_dir().path_join("judgment-%s.tmp" % Crypto.new().generate_random_bytes(16).hex_encode())
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, "%s/%d" % [_route, int(ref.version)], {}, 15.0, temporary)
	if ticket == side_requests[index] and comparison.visible:
		if reply.status == 200 and FileAccess.get_sha256(temporary) == ref.digest:
			var file := FileAccess.open(temporary, FileAccess.READ)
			if file:
				var size := file.get_length()
				var prefix := file.get_buffer(mini(64, size))
				content[index].text = "%s · %d 字节\n%s" % [ref.path, size, prefix.hex_encode()]
				if prefix.size() >= 24 and prefix.slice(0, 8).hex_encode() == "89504e470d0a1a0a" and size <= 8 * 1024 * 1024:
					file.big_endian = true
					file.seek(16)
					var width := file.get_32()
					var height := file.get_32()
					if width > 0 and height > 0 and width <= 4096 and height <= 4096:
						file.seek(0)
						var image := Image.new()
						if image.load_png_from_buffer(file.get_buffer(size)) == OK:
							previews[index].texture = ImageTexture.create_from_image(image)
				file.close()
		else:
			content[index].text = "无法读取或核对所选原件（%d）" % reply.status
	if FileAccess.file_exists(temporary):
		DirAccess.remove_absolute(temporary)


func _refresh(preferred_version := -1) -> void:
	_generation += 1
	comparison.hide()
	compare.disabled = true
	_source.hide()
	_upload.disabled = true
	_versions.disabled = false
	_picker.hide()
	_versions.clear()
	_versions.hide()
	_save.disabled = true
	_status.text = ""
	var issue: Dictionary = _detail.get_detail()
	visible = not issue.is_empty()
	if not visible:
		return
	var attempt := _generation
	_route = "/api/v1/issues/by-number/%d/artifacts" % int(issue.number)
	_status.text = "正在读取附件与产物…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, _route)
	if attempt != _generation:
		return
	if reply.status != 200 or not reply.data.get("artifacts") is Array:
		_feedback(reply.status)
		return
	_upload.disabled = not issue.get("can_classify", false)
	var selected_index := 0
	for reference: Dictionary in reply.data.artifacts:
		var kind: String = {"concept": "概念图", "model": "模型", "attachment": "附件"}.get(reference.kind, "产物")
		_versions.add_item("%s · %s · #%d (%s)" % [kind, reference.path, int(reference.version), str(reference.revision).left(12)])
		_versions.set_item_metadata(_versions.item_count - 1, reference)
		if int(reference.version) == preferred_version:
			selected_index = _versions.item_count - 1
	compare.disabled = _versions.item_count < 2
	_versions.visible = _versions.item_count > 0
	_save.disabled = not _versions.visible
	if _versions.visible:
		_versions.select(selected_index)
		_selected(selected_index)
		if preferred_version > 0:
			var reference: Dictionary = _versions.get_item_metadata(selected_index)
			if int(reference.version) == preferred_version:
				_status.text = "附件 #%d 已绑定 · SHA-256 %s" % [preferred_version, reference.digest]
	else:
		_status.text = "此工单暂无可查看的附件或产物"


func _selected(index: int) -> void:
	_generation += 1
	var reference: Dictionary = _versions.get_item_metadata(index)
	_versions.tooltip_text = "%s\n%s\n%s\nSHA-256 %s" % [reference.module, reference.path, reference.revision, reference.digest]
	_status.text = ""


func _upload_file(path: String) -> void:
	if _upload.disabled or not is_visible_in_tree():
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_status.text = "无法读取所选文件"
		return
	var size := file.get_length()
	if size > 1024 * 1024:
		_status.text = "单个附件最多 1 MiB"
		return
	var content := file.get_buffer(size)
	if content.size() != size or file.get_length() != size:
		_status.text = "文件读取不完整，请重新选择"
		return
	file.close()
	_generation += 1
	var attempt := _generation
	_upload.disabled = true
	_versions.disabled = true
	_save.disabled = true
	_status.text = "正在上传附件…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_POST, _route, {
		"name": path.get_file(), "content": Marshalls.raw_to_base64(content) if size else "",
	})
	if attempt != _generation:
		return
	if reply.status == 200 and int(reply.data.get("version", 0)) > 0:
		await _refresh(int(reply.data.version))
		return
	_upload.disabled = false
	_versions.disabled = false
	_save.disabled = not _versions.visible
	match int(reply.status):
		0, 500, 502, 503, 504:
			_status.text = "尚未收到上传回执，请重新选择同一文件核对"
		403:
			_status.text = "没有权限为此工单添加附件"
		413:
			_status.text = "单个附件最多 1 MiB"
		_:
			_status.text = "附件上传失败（%d），请重新读取工单" % int(reply.status)


func _choose_destination() -> void:
	if _versions.selected < 0:
		return
	var reference: Dictionary = _versions.get_item_metadata(_versions.selected)
	_picker.current_file = str(reference.path).get_file().validate_filename()
	_picker.popup_centered_ratio(0.55)


func _download(destination: String) -> void:
	if not visible or _versions.selected < 0:
		return
	await _download_reference(destination, _versions.get_item_metadata(_versions.selected))


func _download_reference(destination: String, reference: Dictionary, side := -1) -> void:
	var attempt := _generation
	var selection := side_requests[side] if side >= 0 else 0
	var feedback := content[side] if side >= 0 else _status
	var route := "%s/%d" % [_route, int(reference.version)]
	var temporary := destination.get_base_dir().path_join(".gonggong-%s.tmp" % Crypto.new().generate_random_bytes(16).hex_encode())
	var empty := FileAccess.open(temporary, FileAccess.WRITE)
	if empty == null:
		feedback.text = "写入失败，请重新选择保存位置"
		return
	empty.close()
	feedback.text = "正在读取所选版本…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, route, {}, 12.0, temporary)
	if attempt == _generation and (side < 0 or selection == side_requests[side]):
		if reply.get("write_failed", false):
			feedback.text = "写入失败，请重新选择保存位置"
		elif reply.status != 200:
			feedback.text = "无法读取所选原件（%d）" % reply.status if side >= 0 else ""
			if side < 0:
				_feedback(reply.status)
		elif FileAccess.get_sha256(temporary) != reference.digest:
			feedback.text = "引用已失效，文件摘要不匹配"
		elif DirAccess.rename_absolute(temporary, destination) != OK:
			feedback.text = "写入失败，请重新选择保存位置"
		else:
			feedback.text = "已保存所选版本　%s" % destination.get_file()
	if FileAccess.file_exists(temporary):
		DirAccess.remove_absolute(temporary)


func _feedback(status: int) -> void:
	match status:
		403:
			_status.text = "没有权限查看此工单或原始文件"
		404, 409:
			_status.text = "引用已失效，找不到所选版本的文件"
		_:
			_status.text = "无法读取附件或产物，请重新读取工单"
