@tool
extends Node

# Only track objects selected through the native picker and actually sent in this conversation.
var targets := {}
var chat := ""
var panel

func _ready() -> void:
	panel = get_parent()

func restore(record: Dictionary, conversation: String) -> void:
	chat = conversation
	targets = record.get("saved_editor_targets", {}).duplicate(true) if conversation == str(record.get("conversation_id", "")) else {}

func safe_project_path(path: String) -> String:
	if not path.begins_with("res://") or path.simplify_path() != path:
		return ""
	# A selected project path can be replaced by a symlink between rounds.
	var directory := DirAccess.open("res://")
	var components := path.trim_prefix("res://").split("/")
	for i in components.size():
		if not directory or directory.is_link(components[i]):
			return ""
		if i + 1 < components.size() and directory.change_dir(components[i]) != OK:
			return ""
	return path

func local_path(locator: String) -> String:
	var path := locator.get_slice("#", 0).get_slice("::", 0)
	return safe_project_path(path) if path.get_extension() in ["gd", "tres", "tscn", "res", "scn"] else ""

func resource_saved(resource: Resource) -> void:
	if resource:
		saved(resource.resource_path)

func saved(path: String) -> void:
	if chat.is_empty() or chat != str(panel.location.get("conversation_id", "")) or not panel.managed_identity:
		return
	var actor = panel.session.get_identity().get("id")
	if actor == null:
		return
	var digest := ""
	for locator: String in targets:
		if local_path(locator) == path and not path.is_empty():
			if digest.is_empty():
				digest = FileAccess.get_sha256(path)
			if not digest.is_empty():
				targets[locator].receipt = {"revision":digest, "actor":actor, "source":"editor_save"}
	if not digest.is_empty():
		panel._save_draft()

func accept(conversation: String, selected: Array, delivered: Array) -> void:
	if chat != conversation:
		targets.clear()
		chat = conversation
	for item: Dictionary in delivered:
		if targets.has(item.object_id):
			targets[item.object_id].revision = item.revision
	# A newly selected set replaces the previous task targets.
	if not selected.is_empty():
		var next := {}
		for ref: Dictionary in selected:
			var locator := str(ref.get("object_id", ""))
			var path := local_path(locator)
			if ref.get("kind") == "editor" and not path.is_empty():
				next[locator] = {"revision":ref.revision, "receipt":targets.get(locator, {}).get("receipt", {})}
		targets = next

func script_excerpt(locator: String, source: String) -> Dictionary:
	var range_pattern := RegEx.new()
	range_pattern.compile("#L([0-9]+):([0-9]+)-L([0-9]+):([0-9]+)$")
	var selection := range_pattern.search(locator)
	if not selection:
		return {}
	var lines := source.replace("\r\n", "\n").split("\n")
	var start := int(selection.get_string(1)) - 1
	var end := int(selection.get_string(3)) - 1
	if start < 0 or start >= lines.size() or end < start:
		return {"selection_missing":true}
	# Preserve the operator's column range as well as their selected lines.
	var end_column := int(selection.get_string(4)) - 1
	if end >= lines.size():
		end = lines.size() - 1
		end_column = lines[end].length()
	var excerpt := lines.slice(start, end + 1)
	excerpt[-1] = excerpt[-1].left(end_column)
	excerpt[0] = excerpt[0].substr(int(selection.get_string(2)) - 1)
	return {"first_line":start + 1, "last_line":end + 1, "text":panel.redact_reference("\n".join(excerpt))}

func dependencies(path: String) -> Dictionary:
	var pinned := {}
	for dependency in ResourceLoader.get_dependencies(path):
		var parts := dependency.split("::")
		var source := parts[-1] if parts.size() > 1 else parts[0]
		if source.begins_with("uid://"):
			source = ResourceUID.get_id_path(ResourceUID.text_to_id(source))
		if source.begins_with("res://") and source.simplify_path() == source:
			var digest := ""
			if not safe_project_path(source).is_empty() and FileAccess.file_exists(source):
				digest = FileAccess.get_sha256(source)
			pinned[source] = null if digest.is_empty() else digest
	return pinned

func changes() -> Array:
	var result := []
	if chat.is_empty() or chat != str(panel.location.get("conversation_id", "")):
		return result
	for locator: String in targets:
		var path := local_path(locator)
		if path.is_empty() or not FileAccess.file_exists(path):
			continue
		var revision := FileAccess.get_sha256(path)
		var target: Dictionary = targets[locator]
		if revision.is_empty() or revision == target.revision:
			continue
		var current := {"object_id":locator, "revision":revision, "previous_revision":target.revision}
		if path.get_extension() == "gd":
			var file := FileAccess.open(path, FileAccess.READ)
			if not file or file.get_length() > 1024*1024:
				continue
			var source := file.get_as_text()
			if source.replace("\r\n", "\n").sha256_text() == target.revision:
				continue
			current.merge(script_excerpt(locator, source))
		else:
			current.dependencies = dependencies(path)
		if FileAccess.get_sha256(path) != revision:
			continue
		var receipt: Dictionary = target.get("receipt", {})
		current.source = receipt.get("source") if receipt.get("revision") == revision else "disk_readback"
		current.actor = receipt.get("actor") if receipt.get("revision") == revision else null
		result.append(current)
	return result
