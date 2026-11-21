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
	_refresh()


func _refresh(preferred_version := -1) -> void:
	_generation += 1
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
	var attempt := _generation
	var reference: Dictionary = _versions.get_item_metadata(_versions.selected)
	var route := "%s/%d" % [_route, int(reference.version)]
	var temporary := destination.get_base_dir().path_join(".gonggong-%s.tmp" % Crypto.new().generate_random_bytes(16).hex_encode())
	var empty := FileAccess.open(temporary, FileAccess.WRITE)
	if empty == null:
		_status.text = "写入失败，请重新选择保存位置"
		return
	empty.close()
	_status.text = "正在读取所选版本…"
	var reply: Dictionary = await _session.api_request(HTTPClient.METHOD_GET, route, {}, 12.0, temporary)
	if attempt == _generation:
		if reply.get("write_failed", false):
			_status.text = "写入失败，请重新选择保存位置"
		elif reply.status != 200:
			_feedback(reply.status)
		elif FileAccess.get_sha256(temporary) != reference.digest:
			_status.text = "引用已失效，文件摘要不匹配"
		elif DirAccess.rename_absolute(temporary, destination) != OK:
			_status.text = "写入失败，请重新选择保存位置"
		else:
			_status.text = "已保存所选版本　%s" % destination.get_file()
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
