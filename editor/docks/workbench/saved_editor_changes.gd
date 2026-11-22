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

func capture_starts(selected: Array) -> Dictionary:
	var starts := {}
	for ref: Dictionary in selected:
		var locator := str(ref.get("object_id", ""))
		var path := local_path(locator)
		if ref.get("kind") == "editor" and not path.is_empty() and FileAccess.get_sha256(path) == ref.revision:
			var baseline := selected_state(locator, path)
			if FileAccess.get_sha256(path) == ref.revision:
				starts[locator] = baseline
	return starts

func accept(conversation: String, selected: Array, delivered: Array, starts: Dictionary) -> void:
	if chat != conversation:
		targets.clear()
		chat = conversation
	for item: Dictionary in delivered:
		if targets.has(item.object_id):
			targets[item.object_id].revision = item.revision
	# A newly selected set replaces the previous task targets.
	if not selected.is_empty():
		var next: Dictionary = targets.duplicate(true) if panel.continue_work.button_pressed else {}
		for ref: Dictionary in selected:
			var locator := str(ref.get("object_id", ""))
			var path := local_path(locator)
			if ref.get("kind") == "editor" and not path.is_empty():
				var target: Dictionary = targets.get(locator, {}) if panel.continue_work.button_pressed else {}
				if target.is_empty():
					target = {"start_revision":ref.revision, "receipt":targets.get(locator, {}).get("receipt", {})}
					if starts.has(locator):
						target["starting_state"] = starts[locator]
				target.revision = ref.revision
				if next.has(locator) or next.size() < 16:
					next[locator] = target
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
		var continuing: bool = panel.continue_work.button_pressed
		if revision.is_empty() or (revision == target.revision and not continuing):
			continue
		var current := {"object_id":locator, "revision":revision, "previous_revision":target.revision}
		if path.get_extension() == "gd":
			var file := FileAccess.open(path, FileAccess.READ)
			if not file or file.get_length() > 1024*1024:
				continue
			var source := file.get_as_text()
			if not continuing and source.replace("\r\n", "\n").sha256_text() == target.revision:
				continue
			current.merge(script_excerpt(locator, source))
		else:
			current.dependencies = dependencies(path)
		var starting: Dictionary = target.get("starting_state", {})
		var latest := selected_state(locator, path) if continuing or not starting.get("tracks", {}).is_empty() else {}
		var complete: bool = starting.get("tracks_complete", true) and latest.get("tracks_complete", true)
		var tracks: Array = changed_tracks(starting.get("tracks", {}), latest.get("tracks", {})) if target.has("starting_state") and complete else []
		if not complete:
			current.animation_detail = "track_or_key_limit"
		if not tracks.is_empty():
			current.animation_changes = tracks
		if continuing:
			current.start_revision = target.get("start_revision", target.revision)
			current.starting_state = starting.get("properties", starting) if target.has("starting_state") else null
			current.latest_state = latest.get("properties", latest)
		if FileAccess.get_sha256(path) != revision:
			continue
		var receipt: Dictionary = target.get("receipt", {})
		current.source = receipt.get("source") if receipt.get("revision") == revision else "disk_readback"
		current.actor = receipt.get("actor") if receipt.get("revision") == revision else null
		result.append(current)
	return result

func property_value(value: Variant) -> Variant:
	if value is Resource:
		return value.resource_path if value.resource_path.begins_with("res://") else value.get_class()
	if value == null or value is bool or value is int or value is float:
		return value
	if typeof(value) in [TYPE_STRING, TYPE_STRING_NAME, TYPE_NODE_PATH, TYPE_VECTOR2, TYPE_VECTOR3, TYPE_COLOR, TYPE_QUATERNION]:
		return panel.redact_reference(str(value).left(512))
	return null

func clip_tracks(clip: Animation, name: String, tracks: Dictionary, budget: Dictionary) -> void:
	if not budget.complete:
		return
	var occurrences := {}
	for index in clip.get_track_count():
		var path := str(clip.track_get_path(index))
		var type := clip.track_get_type(index)
		var identity := JSON.stringify([name, path, type])
		var ordinal := int(occurrences.get(identity, 0))
		occurrences[identity] = ordinal + 1
		var id := JSON.stringify([name, path, type, ordinal])
		var keys := {}
		budget.keys_left -= clip.track_get_key_count(index)
		if tracks.size() >= 128 or budget.keys_left < 0:
			budget.complete = false
			return
		for k in clip.track_get_key_count(index):
			var time := clip.track_get_key_time(index, k)
			var value: Variant = clip.track_get_key_value(index, k)
			var digest_value: Variant = property_value(value) if value is Object else value
			var data := var_to_bytes([digest_value, clip.track_get_key_transition(index, k)])
			var checksum := HashingContext.new()
			checksum.start(HashingContext.HASH_SHA256)
			checksum.update(data)
			keys[var_to_str(time)] = {"time":time, "value":property_value(value), "sha256":checksum.finish().hex_encode()}
		tracks[id] = {"animation":name, "path":path, "type":type, "ordinal":ordinal, "keys":keys,
			"revision":JSON.stringify(keys).sha256_text()}

func library_tracks(library: AnimationLibrary, prefix: String, tracks: Dictionary, budget: Dictionary) -> void:
	for name in library.get_animation_list():
		clip_tracks(library.get_animation(name), prefix.path_join(name) if not prefix.is_empty() else str(name), tracks, budget)

func selected_state(locator: String, path: String) -> Dictionary:
	if path.get_extension() == "gd":
		var file := FileAccess.open(path, FileAccess.READ)
		return script_excerpt(locator, file.get_as_text()) if file and file.get_length() <= 1024*1024 else {}
	var resource := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
	var values := {}
	var tracks := {}
	var budget := {"keys_left":2048, "complete":true}
	if resource is PackedScene and locator.contains("#"):
		var selection := locator.get_slice("#", 1)
		var state: SceneState = resource.get_state()
		for n in state.get_node_count():
			if str(state.get_node_path(n)).trim_prefix("./") != selection:
				continue
			for p in state.get_node_property_count(n):
				var name := str(state.get_node_property_name(n, p))
				var value: Variant = state.get_node_property_value(n, p)
				if value is AnimationLibrary and name.begins_with("libraries/"):
					library_tracks(value, name.trim_prefix("libraries/"), tracks, budget)
				elif name != "script" and values.size() < 96:
					var readable: Variant = property_value(value)
					if readable != null:
						values[name] = readable
			break
	elif resource is Animation:
		clip_tracks(resource, resource.resource_name, tracks, budget)
	elif resource is AnimationLibrary:
		library_tracks(resource, "", tracks, budget)
	elif resource and not resource.get_script() and not resource is PackedScene:
		for property in resource.get_property_list():
			if int(property.usage) & PROPERTY_USAGE_STORAGE and values.size() < 96:
				var readable: Variant = property_value(resource.get(property.name))
				if readable != null:
					values[property.name] = readable
	return {"properties":values, "tracks":tracks if budget.complete else {}, "tracks_complete":budget.complete}

func changed_tracks(before: Dictionary, after: Dictionary) -> Array:
	var changed := []
	var all_ids := before.duplicate()
	all_ids.merge(after)
	for id in all_ids:
		var old: Dictionary = before.get(id, {})
		var current: Dictionary = after.get(id, {})
		if old.get("revision") == current.get("revision"):
			continue
		var identity: Dictionary = old if current.is_empty() else current
		var delta := {"animation":identity.animation, "path":identity.path, "type":identity.type, "ordinal":identity.ordinal,
			"before_revision":old.get("revision"), "revision":current.get("revision"), "keys":[]}
		var old_keys: Dictionary = old.get("keys", {})
		var new_keys: Dictionary = current.get("keys", {})
		var times := old_keys.duplicate()
		times.merge(new_keys)
		for time in times:
			if old_keys.get(time) != new_keys.get(time):
				delta.keys.append({"time":float(time), "before":old_keys.get(time), "after":new_keys.get(time)})
		changed.append(delta)
	return changed
