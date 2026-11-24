@tool
extends Node
## Explicit editor operations. Captures are immutable message data, never tool authority.

signal changed

var workspace: Node
var status := ""
var _captured := {}
var _current_contexts := {}
var _current_error := ""
var _context_views: Array[WeakRef] = []
var _context_timer := Timer.new()


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.session.identity_changed.connect(func():
		_captured.clear()
		_current_contexts.clear()
		_current_error = ""
		status = ""
		changed.emit()
	)
	workspace.changed.connect(func(topic: String):
		if topic == "conversation_selection" or topic.begins_with("draft:editor:"):
			_current_error = ""
			changed.emit()
	)
	_context_timer.wait_time = 0.5
	_context_timer.timeout.connect(_poll_current_context)
	add_child(_context_timer)
	_context_timer.start()


func observe_context(view: Control) -> void:
	for reference in _context_views:
		if reference.get_ref() == view:
			return
	_context_views.append(weakref(view))


func _poll_current_context() -> void:
	for index in range(_context_views.size() - 1, -1, -1):
		var view: Control = _context_views[index].get_ref()
		if not view:
			_context_views.remove_at(index)
		elif view.is_visible_in_tree():
			capture_current_context()
			return


func _read_current_context(verify := false) -> Dictionary:
	var host: Node = workspace.get_meta("model_host", null)
	if not is_instance_valid(host) or not host.has_method("editor_context"):
		return {}
	# The provider knows editor credentials; this consumer also owns a distinct
	# Tianxuan identity. Normalize at this boundary before storing or comparing.
	return _redact_current_value(host.editor_context(verify))


func _redact_current_value(value: Variant) -> Variant:
	if value is String:
		return workspace.session.redact_credentials(value)
	if value is Dictionary:
		var result := {}
		for key in value:
			result[key] = _redact_current_value(value[key])
		return result
	if value is Array:
		var result := []
		for item in value:
			result.append(_redact_current_value(item))
		return result
	return value


func capture_current_context() -> void:
	if workspace.identity().is_empty() or workspace.chat_busy():
		return
	var current := _read_current_context()
	if current != current_context():
		_current_contexts[_key()] = current.duplicate(true)
		_current_error = ""
		changed.emit()


func current_context() -> Dictionary:
	return _current_contexts.get(_key(), {}).duplicate(true)


func current_context_status() -> String:
	if not _current_error.is_empty():
		return tr(_current_error)
	var current := current_context()
	if str(current.get("source", "")).is_empty():
		return tr("当前现场 · 请在原编辑窗口选择内容")
	var selection := str(current.get("selection_text", ""))
	var detail := tr(str(current.error)) if not str(current.get("error", "")).is_empty() else selection if not selection.is_empty() else tr("未选中内容")
	return tr("当前现场 · %s · %s") % [str(current.source), detail]


func _key() -> String:
	return _key_for(workspace.active_conversation)


func _key_for(conversation_id: String) -> String:
	return "editor:" + ProjectSettings.globalize_path("res://").sha256_text() + ":" + workspace.chat_draft_key(conversation_id)


func move_new_conversation(id: String) -> void:
	var previous := _key_for("")
	var target := _key_for(id)
	if _current_contexts.has(previous):
		_current_contexts[target] = _current_contexts[previous].duplicate(true)
		_current_contexts.erase(previous)
	var value: Dictionary = workspace.load_draft(previous)
	if not value.is_empty():
		if workspace.save_draft(target, value):
			workspace.clear_draft(previous)


func attachments() -> Array:
	return workspace.load_draft(_key()).get("attachments", []).duplicate(true)


func _store(items: Array) -> void:
	if not workspace.save_draft(_key(), {"attachments": items}):
		status = "无法保存引用，请先检查设备存储。"
	changed.emit()


func remove(index: int) -> void:
	var items := attachments()
	if index >= 0 and index < items.size():
		items.remove_at(index)
		_store(items)


func _add(value: Dictionary, object: Object = null) -> void:
	if value.is_empty():
		return
	var items := attachments()
	for index in items.size():
		if items[index].object_id == value.object_id:
			items.remove_at(index)
			break
	if items.size() >= 16:
		status = "每条消息最多附加 16 项引用。"
		changed.emit()
		return
	value.revision = str(value.snapshot).sha256_text()
	if object:
		_captured[value.object_id] = weakref(object)
	items.append(value)
	status = "已加入引用；发送时会再次核对原对象。"
	_store(items)


func _node_snapshot(node: Node) -> Dictionary:
	var root := EditorInterface.get_edited_scene_root()
	if not root or not is_instance_valid(node) or (node != root and not root.is_ancestor_of(node)):
		return {}
	var path := str(root.get_path_to(node))
	var scene := root.scene_file_path
	var id := scene if not scene.is_empty() else "unsaved-scene://%s/%s" % [OS.get_process_id(), root.get_instance_id()]
	id += "#" + path
	var values := [tr("场景：") + scene, tr("节点：") + path, tr("类型：") + node.get_class()]
	if node is Node3D:
		values.append(tr("变换：") + str(node.transform))
	elif node is Node2D:
		values.append(tr("变换：") + str(node.transform))
	elif node is Control:
		values.append(tr("位置：%s；尺寸：%s") % [node.position, node.size])
	var script: Script = node.get_script()
	if script:
		values.append(tr("脚本：") + script.resource_path)
	return {"object_id": id, "title": str(node.name), "snapshot": "\n".join(values), "source": "node"}


func attach_nodes() -> void:
	var selection := EditorInterface.get_selection().get_selected_nodes()
	if selection.is_empty():
		status = "请先在场景树中选中节点。"
		changed.emit()
	for node in selection:
		_add(_node_snapshot(node), node)


func _file_snapshot(path: String) -> Dictionary:
	var source := path.get_slice("::", 0)
	if not safe_project_path(source) or not FileAccess.file_exists(source):
		return {}
	var file := FileAccess.open(source, FileAccess.READ)
	if not file or file.get_length() > 128 * 1024 * 1024:
		return {}
	var size := file.get_length()
	file.close()
	var digest := FileAccess.get_sha256(source)
	if digest.is_empty():
		return {}
	var description := tr("资源：%s\n大小：%d 字节\n内容 SHA-256：%s") % [path, size, digest]
	if source.get_extension().to_lower() in ["gd", "gdshader", "tscn", "tres"] and size <= 4096:
		description += "\n\n" + workspace.session.redact_credentials(FileAccess.get_file_as_string(source))
	return {"object_id": path, "title": path.get_file(), "snapshot": description, "source": "file", "file_digest": digest}


func attach_resources() -> void:
	var paths := EditorInterface.get_selected_paths()
	var inspected := EditorInterface.get_inspector().get_edited_object()
	if inspected is Resource and inspected.resource_path.begins_with("res://") and not paths.has(inspected.resource_path):
		paths.append(inspected.resource_path)
	var count := 0
	for path in paths:
		var value := _file_snapshot(path)
		if not value.is_empty():
			_add(value)
			count += 1
	if count == 0:
		status = "请在文件系统或检查器选择已保存的项目资源（单文件不超过 128 MB）。"
		changed.emit()


func message_context(module_id: String) -> Dictionary:
	var items := attachments()
	var current := current_context()
	if current.is_empty() and not _read_current_context().is_empty():
		capture_current_context()
		_current_error = "当前现场已更新，请核对引用后再次发送。草稿已保留。"
		changed.emit()
		return {"valid": false}
	if not current.is_empty() and (not str(current.get("error", "")).is_empty() or current != _read_current_context(true)):
		_current_error = "当前现场已变化或不可用，请核对更新后的引用再发送。草稿已保留。"
		changed.emit()
		return {"valid": false}
	var current_references: Array = current.get("references", [])
	var merged := current_references.duplicate(true)
	for item in items:
		var reference := {"kind": "editor", "object_id": item.object_id, "revision": item.revision}
		if not merged.has(reference):
			merged.append(reference)
	if merged.size() > 16:
		_current_error = "当前现场与保留引用合计超过 16 项，请缩小选区或移除保留引用。草稿已保留。"
		changed.emit()
		return {"valid": false}
	if not items.is_empty() and module_id.is_empty():
		status = "请选择这些引用所属的业务模块。"
		changed.emit()
		return {"valid": false}
	var references := []
	var descriptions := PackedStringArray()
	for item in items:
		var live := {}
		if item.source == "node":
			var reference: WeakRef = _captured.get(item.object_id)
			var node: Node = reference.get_ref() if reference else null
			if node:
				live = _node_snapshot(node)
		elif item.source == "file":
			live = _file_snapshot(item.object_id)
		if live.is_empty() or str(live.snapshot).sha256_text() != item.revision:
			status = tr("引用“%s”已变化或不可用，请移除或重新选择后发送。") % item.title
			changed.emit()
			return {"valid": false}
		references.append({"kind": "editor", "object_id": item.object_id, "revision": item.revision})
		descriptions.append("### " + str(item.title) + "\n" + str(item.snapshot))
	# Automatic context is consultation data. Only explicit attachments acquire
	# the user's chosen business-module scope; opening a view never changes it.
	var snapshot := {} if references.is_empty() else {"project": workspace.identity().project, "module_id": module_id, "issue_id": null, "references": references}
	var text := "" if descriptions.is_empty() else "\n\n---\nGodot 编辑器保留引用（辅助资料）：\n\n" + "\n\n".join(descriptions)
	if not str(current.get("text", "")).is_empty():
		text += "\n\n[当前编辑现场：本轮主要处理对象；仅为咨询数据，不改变业务模块]\n来源：" + str(current.get("source", "")) + "\n" + JSON.stringify(current_references) + "\n" + str(current.text)
	if not _current_error.is_empty():
		_current_error = ""
		changed.emit()
	return {"valid": true, "references": snapshot, "text": text}


static func safe_project_path(path: String) -> bool:
	if not path.begins_with("res://") or path != path.simplify_path() or path.contains("\\"):
		return false
	var relative := path.trim_prefix("res://")
	if relative.is_empty() or ":" in relative:
		return false
	var folder := DirAccess.open("res://")
	if not folder:
		return false
	var accumulated := ""
	for part in relative.split("/"):
		if part in ["", ".", "..", ".godot", ".git"]:
			return false
		accumulated = accumulated.path_join(part)
		if folder.is_link(accumulated):
			return false
	return true


func open_file(path: String, line := 1) -> void:
	if not safe_project_path(path) or not FileAccess.file_exists(path):
		status = "文件不在当前项目内，或已不存在。"
		changed.emit()
		return
	EditorInterface.select_file(path)
	if ResourceLoader.exists(path):
		var resource := ResourceLoader.load(path)
		if resource is Script:
			EditorInterface.edit_script(resource, maxi(0, line - 1), 0, true)
		elif resource is PackedScene:
			EditorInterface.open_scene_from_path(path)
		elif resource:
			EditorInterface.edit_resource(resource)
	status = tr("已定位 ") + path
	changed.emit()


func import_asset(source: String, destination: String) -> void:
	if not safe_project_path(destination) or not FileAccess.file_exists(source) or not DirAccess.dir_exists_absolute(destination.get_base_dir()):
		status = "请选择已有的项目目录及有效来源文件。"
		changed.emit()
		return
	if FileAccess.file_exists(destination):
		status = "目标文件已存在，请使用其他文件名。"
		changed.emit()
		return
	var file := FileAccess.open(source, FileAccess.READ)
	if not file or file.get_length() > 128 * 1024 * 1024:
		status = "无法读取来源文件，或文件超过本次导入的 128 MB 上限。"
		changed.emit()
		return
	file.close()
	var digest := FileAccess.get_sha256(source)
	var temporary: String = destination.get_base_dir().path_join(".tianxuan-import-" + workspace.new_id())
	var error := DirAccess.copy_absolute(source, temporary)
	if error == OK and not digest.is_empty() and FileAccess.get_sha256(temporary) == digest:
		var install: Callable = workspace.get_meta("install_asset_if_absent")
		error = install.call(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(destination))
	else:
		error = ERR_CANT_CREATE
	DirAccess.remove_absolute(temporary)
	if error == OK:
		EditorInterface.get_resource_filesystem().scan()
		status = tr("已复制资源，编辑器正在扫描并导入：") + destination
	else:
		status = tr("导入未完成（%d），现有资源未被替换。") % error
	changed.emit()
