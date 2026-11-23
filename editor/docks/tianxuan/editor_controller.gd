@tool
extends Node
## Explicit editor operations. Captures are immutable message data, never tool authority.

signal changed

var workspace: Node
var status := ""
var _captured := {}


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.session.identity_changed.connect(func():
		_captured.clear()
		status = ""
		changed.emit()
	)
	workspace.changed.connect(func(topic: String):
		if topic == "conversation_selection" or topic.begins_with("draft:editor:"):
			changed.emit()
	)


func _key() -> String:
	return "editor:" + ProjectSettings.globalize_path("res://").sha256_text() + ":" + workspace.chat_draft_key(workspace.active_conversation)


func move_new_conversation(id: String) -> void:
	var value: Dictionary = workspace.load_draft(_key())
	if not value.is_empty():
		var target: String = "editor:" + ProjectSettings.globalize_path("res://").sha256_text() + ":" + workspace.chat_draft_key(id)
		if workspace.save_draft(target, value):
			workspace.clear_draft(_key())


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
	if items.is_empty():
		return {"valid": true, "references": {}, "text": ""}
	if module_id.is_empty():
		status = "请选择这些引用所属的业务模块。"
		changed.emit()
		return {"valid": false}
	var references := []
	var descriptions := PackedStringArray()
	for item in items:
		var current := {}
		if item.source == "node":
			var reference: WeakRef = _captured.get(item.object_id)
			var node: Node = reference.get_ref() if reference else null
			if node:
				current = _node_snapshot(node)
		elif item.source == "file":
			current = _file_snapshot(item.object_id)
		if current.is_empty() or str(current.snapshot).sha256_text() != item.revision:
			status = tr("引用“%s”已变化或不可用，请移除或重新选择后发送。") % item.title
			changed.emit()
			return {"valid": false}
		references.append({"kind": "editor", "object_id": item.object_id, "revision": item.revision})
		descriptions.append("### " + str(item.title) + "\n" + str(item.snapshot))
	# The separator is a persisted conversation format shared with existing clients.
	return {"valid": true, "references": {"project": workspace.identity().project, "module_id": module_id, "issue_id": null, "references": references}, "text": "\n\n---\nGodot 编辑器引用（本次消息的对象快照）：\n\n" + "\n\n".join(descriptions)}


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
