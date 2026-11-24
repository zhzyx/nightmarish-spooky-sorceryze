@tool
extends VBoxContainer
## A frozen, account-scoped specification. Preparing or adding it never runs a job.

var workbench: Node
var _record := {}
var _path := ""
var _validator: Callable
var _title := Label.new()
var _source := Label.new()
var _body := TextEdit.new()
var _status := Label.new()
var _add := Button.new()


func initialize(host: Node) -> void:
	workbench = host
	name = "TianxuanProductionHandoff"
	_title.text = "天璇制作规格"
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_title)
	_source.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_source)
	_body.name = "TianxuanProductionSpecification"
	_body.editable = false
	_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_body.custom_minimum_size.y = 140
	add_child(_body)
	_status.name = "TianxuanProductionStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	var actions := HFlowContainer.new()
	add_child(actions)
	_add.name = "AddTianxuanMeshNode"
	_add.text = "添加文字生成网格节点"
	_add.pressed.connect(add_node)
	actions.add_child(_add)
	var close := Button.new()
	close.text = "收起规格"
	close.pressed.connect(clear)
	actions.add_child(close)
	hide()


func clear() -> void:
	_record.clear()
	_path = ""
	_validator = Callable()
	_title.text = "天璇制作规格"
	_body.text = ""
	_source.text = ""
	_status.text = ""
	hide()


func _failure(message: String) -> Dictionary:
	return {"ok": false, "error": message}


func _validated(value: Dictionary) -> Dictionary:
	var keys := ["scope", "conversation", "stage", "revision", "project", "title", "body", "acceptance"]
	if value.size() != keys.size() or not value.has_all(keys):
		return {}
	for key in keys:
		if key != "revision" and not value[key] is String:
			return {}
	if not value.revision is int or value.revision <= 0 or value.revision > 2147483647:
		return {}
	if value.scope.is_empty() or value.scope.length() > 4096 or value.conversation.is_empty() or value.conversation.length() > 1024:
		return {}
	if value.stage not in ["direction", "design"] or value.title.length() > 4096 or value.body.strip_edges().is_empty():
		return {}
	if value.project != ProjectSettings.globalize_path("res://").trim_suffix("/"):
		return {}
	if JSON.stringify(value).to_utf8_buffer().size() > 131072:
		return {}
	return value.duplicate(true)


func _id(snapshot: Dictionary) -> String:
	return JSON.stringify([snapshot.project, snapshot.scope, snapshot.conversation, snapshot.stage, snapshot.revision]).sha256_text()


func _digest(snapshot: Dictionary) -> String:
	return JSON.stringify(snapshot, "", true, true).sha256_text()


func _read(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 262144:
		return {}
	var value: Variant = JSON.parse_string(file.get_as_text())
	if not value is Dictionary or value.get("format") != 1 or not value.get("snapshot") is Dictionary:
		return {}
	var snapshot: Dictionary = value.snapshot.duplicate(true)
	# JSON numbers are doubles; accept only the exact bounded revision written here.
	var revision: Variant = snapshot.get("revision")
	if not (revision is int or revision is float) or not is_finite(revision) or revision != floor(revision) or revision < 1 or revision > 2147483647:
		return {}
	snapshot.revision = int(revision)
	if _validated(snapshot).is_empty() or value.get("digest") != _digest(snapshot) or value.get("id") != _id(snapshot):
		return {}
	if value.get("state") not in ["prepared", "node_reserved", "node_created"]:
		return {}
	if value.state != "prepared" and value.get("node_id") != "tx_" + str(value.id):
		return {}
	value.snapshot = snapshot
	return value


func _write(path: String, record: Dictionary) -> bool:
	var temporary := path + "." + Crypto.new().generate_random_bytes(12).hex_encode() + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(record, "", true, true))
	file.flush()
	var error := file.get_error()
	file.close()
	if error == OK and DirAccess.rename_absolute(temporary, path) == OK:
		return true
	DirAccess.remove_absolute(temporary)
	return false


func _receipt(created: bool) -> Dictionary:
	var result := {"ok": true, "handoff_id": _record.id, "state": _record.state, "created": created}
	if _record.has("node_id"):
		result.node_id = _record.node_id
	return result


func prepare(snapshot: Dictionary, validator: Callable) -> Dictionary:
	var frozen := _validated(snapshot)
	if frozen.is_empty() or not validator.is_valid() or validator.call(frozen) != true:
		return _failure("账号、对话或已确认规格已变化，请从天璇重新进入。")
	var id := _id(frozen)
	var directory: String = workbench.state_dir.path_join("tianxuan-specifications")
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		return _failure("无法保存制作规格，请检查本机存储。")
	var path := directory.path_join(id + ".json")
	# An exclusive directory serializes cooperating editor instances. A crashed
	# writer leaves a visible storage error, never an automatic duplicate creation.
	var lock := path + ".lock"
	if DirAccess.make_dir_absolute(lock) != OK:
		return _failure("制作规格正在写入或上次写入尚未完成，请先检查本机交接记录。")
	var existing := FileAccess.file_exists(path)
	var record := _read(path) if existing else {"format": 1, "id": id, "digest": _digest(frozen), "snapshot": frozen, "state": "prepared"}
	var error := ""
	if existing and record.is_empty():
		error = "制作规格记录无效，已保留原记录；请检查本机存储。"
	elif record.digest != _digest(frozen):
		error = "同一修订的规格内容已变化，不能覆盖原交接；请保存并确认新修订。"
	elif not existing and not _write(path, record):
		error = "无法保存制作规格，请检查本机存储。"
	DirAccess.remove_absolute(lock)
	if not error.is_empty():
		return _failure(error)
	_record = record
	_path = path
	_validator = validator
	_title.text = "待制作规格 · " + frozen.title
	_source.text = "%s · 修订 %d · 对话 %s\n规格摘要：%s" % ["详细设计" if frozen.stage == "design" else "方向", frozen.revision, frozen.conversation, record.digest.substr(0, 12)]
	_body.text = prompt(frozen)
	_status.text = "尚未运行。添加节点后，请检查当前模型配置，并使用该节点的“运行并预览”。"
	_add.disabled = record.state != "prepared"
	if record.state == "node_created":
		_status.text = "此规格已添加节点，未由交接入口启动生成。请使用原节点；若节点未保存或已删除，不会自动重复添加。"
	elif record.state == "node_reserved":
		_status.text = "已保留此规格的节点编号，尚未确认是否添加成功。请检查原工作流；为避免重复，不会自动再次添加。"
	show()
	return _receipt(not existing)


func prompt(snapshot: Dictionary) -> String:
	var result := str(snapshot.title) + "\n\n" + str(snapshot.body)
	if not str(snapshot.acceptance).strip_edges().is_empty():
		result += "\n\n验收标准：\n" + str(snapshot.acceptance)
	return result


func _reserve_node() -> Dictionary:
	var lock := _path + ".lock"
	if DirAccess.make_dir_absolute(lock) != OK:
		return _failure("制作规格正在另一编辑器中处理，请稍后回读原记录。")
	var current := _read(_path)
	var result := _failure("制作规格记录已变化或无法保存，未添加节点。")
	if not current.is_empty() and current.digest == _record.digest:
		if current.state != "prepared":
			_record = current
			result = _failure("此规格已有创建记录或待核对的节点预留，不会重复添加；请检查原工作流。")
		else:
			current.state = "node_reserved"
			current.node_id = "tx_" + str(current.id)
			if _write(_path, current):
				_record = current
				result = {"ok": true}
	DirAccess.remove_absolute(lock)
	return result


func _complete_node() -> bool:
	var lock := _path + ".lock"
	if DirAccess.make_dir_absolute(lock) != OK:
		return false
	var current := _read(_path)
	var completed := false
	if not current.is_empty() and current.digest == _record.digest and current.state == "node_reserved":
		current.state = "node_created"
		if _write(_path, current):
			_record = current
			completed = true
	DirAccess.remove_absolute(lock)
	return completed


func add_node() -> Dictionary:
	if _record.is_empty():
		return _failure("请先从天璇选择已确认规格。")
	if not _validator.is_valid() or _validator.call(_record.snapshot) != true:
		_status.text = "账号、对话或已确认规格已变化，请从天璇重新进入。"
		return _failure(_status.text)
	if _record.state == "node_created":
		return _receipt(false)
	if _record.state == "node_reserved":
		_status.text = "上次节点添加结果尚未确认，请检查原工作流；不会自动重复添加。"
		return _failure(_status.text)
	var result: Dictionary = workbench.append_spec_handoff_node(_record.snapshot, "tx_" + str(_record.id), _reserve_node)
	if not result.get("ok", false):
		_status.text = str(result.get("error", "无法添加制作节点。"))
		return result
	_add.disabled = true
	if _complete_node():
		_status.text = "已添加独立网格节点，尚未运行。请检查模型与提示词，右键该节点选择“运行并预览”；已有工作流保持原样。"
	else:
		_status.text = "本次节点已添加，但完成记录未能保存。请保存并检查当前工作流；下次打开将显示待核对，不会自动重复添加。"
	return _receipt(true)
