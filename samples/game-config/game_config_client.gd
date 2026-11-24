extends Node
## Snapshots are candidates until game code validates, applies, then acknowledges.
signal snapshot_received(snapshot: Dictionary)
signal configuration_changed(version: int)
signal connection_changed(state: String)
signal protocol_error(message: String)

var connection_state := "stopped"
var applied_version := 0
var _valid: Dictionary = {}
var _candidate: Dictionary = {}
var _socket := WebSocketPeer.new()
var _url := ""
var _project_key := ""
var _name := "Godot runtime"
var _running := false
var _opened := false
var _retry_at := 0
var _retry_delay := 1.0
var _ping_at := 0
var _connect_deadline := 0
var _last_message_at := 0


func start(base_url: String, project_id: String, client_name := "Godot runtime") -> Error:
	stop()
	if OS.get_environment("TIANXUAN_TOKEN").is_empty():
		_set_state("missing_credentials")
		return ERR_UNAUTHORIZED
	if not (base_url.begins_with("https://") or base_url.begins_with("http://")):
		_set_state("invalid_url")
		return ERR_INVALID_PARAMETER
	if project_id.is_empty() or base_url.contains("?") or base_url.contains("#") or base_url.contains("@"):
		_set_state("invalid_url")
		return ERR_INVALID_PARAMETER
	var key := base_url.trim_suffix("/") + "/" + project_id
	if key != _project_key:
		_project_key = key
		_valid = {}
		applied_version = 0
	_url = base_url.trim_suffix("/").replace("https://", "wss://").replace("http://", "ws://")
	_url += "/api/v1/ws/game-config/" + project_id.uri_encode() + "?kind=runtime"
	_name = client_name
	_running = true
	_retry_delay = 1.0
	_connect()
	return OK


func stop() -> void:
	_running = false
	_socket.close()
	_opened = false
	_candidate = {}
	_set_state("stopped")


func _connect() -> void:
	_socket = WebSocketPeer.new()
	# Service snapshots allow 1 MiB of features, plus the JSON envelope.
	_socket.inbound_buffer_size = 2 * 1024 * 1024
	# Never include credentials in URLs, resources, emitted events, or logs.
	_socket.handshake_headers = PackedStringArray(["Authorization: Bearer " + OS.get_environment("TIANXUAN_TOKEN")])
	_opened = false
	_set_state("connecting")
	_connect_deadline = Time.get_ticks_msec() + 10000
	if _socket.connect_to_url(_url) != OK:
		_schedule_retry()


func _process(_delta: float) -> void:
	if not _running:
		return
	var now := Time.get_ticks_msec()
	if connection_state == "reconnecting":
		if now >= _retry_at:
			_connect()
		return
	_socket.poll()
	var state := _socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _opened:
			_opened = true
			_last_message_at = now
			_send({"type": "subscribe", "name": _name})
			_ping_at = now + 10000
			_set_state("connected")
		while _socket.get_available_packet_count() > 0:
			_last_message_at = now
			var decoded: Variant = JSON.parse_string(_socket.get_packet().get_string_from_utf8())
			if decoded is Dictionary:
				_handle_message(decoded)
			else:
				protocol_error.emit("Invalid JSON message")
		if now - _last_message_at > 30000:
			_schedule_retry()
			return
		if now >= _ping_at:
			_send({"type": "ping"})
			_ping_at = now + 10000
	elif state == WebSocketPeer.STATE_CLOSED or now >= _connect_deadline and not _opened:
		_schedule_retry()


func _exit_tree() -> void:
	stop()


func _schedule_retry() -> void:
	_socket.close()
	_candidate = {}
	_opened = false
	_retry_at = Time.get_ticks_msec() + int(_retry_delay * 1000)
	_retry_delay = minf(_retry_delay * 2.0, 30.0)
	_set_state("reconnecting")


func _set_state(value: String) -> void:
	if connection_state != value:
		connection_state = value
		connection_changed.emit(value)


func _send(message: Dictionary) -> Error:
	if _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return ERR_CONNECTION_ERROR
	return _socket.send_text(JSON.stringify(message))


func _handle_message(message: Dictionary) -> void:
	if message.get("type") != "snapshot":
		return
	var project: Variant = message.get("project")
	if not project is Dictionary or not _valid_structure(project):
		protocol_error.emit("Invalid snapshot structure")
		return
	var version := int(project.version)
	if version < applied_version or version < int(_candidate.get("version", 0)):
		protocol_error.emit("Stale snapshot ignored")
		return
	_retry_delay = 1.0
	_candidate = project.duplicate(true)
	snapshot_received.emit(project.duplicate(true))


func _valid_structure(project: Dictionary) -> bool:
	var version: Variant = project.get("version")
	if not (version is int or version is float) or version < 1 or version != int(version):
		return false
	if not project.get("features") is Array:
		return false
	var feature_ids := {}
	for feature: Variant in project.features:
		if not feature is Dictionary or not feature.get("id") is String or not feature.get("entries") is Array:
			return false
		if feature_ids.has(feature.id):
			return false
		feature_ids[feature.id] = true
		var entry_ids := {}
		for entry: Variant in feature.entries:
			if not entry is Dictionary or not entry.get("id") is String or not entry.has("value"):
				return false
			if entry_ids.has(entry.id):
				return false
			entry_ids[entry.id] = true
	return true


## Call only AFTER the application has validated and atomically applied this candidate.
## Locally committed state remains valid even if sending the receipt fails; reconnect
## supplies an authoritative candidate again, which must be applied/acknowledged again.
func acknowledge(version: int) -> Error:
	if _candidate.is_empty() or int(_candidate.version) != version:
		return ERR_INVALID_PARAMETER
	_valid = _candidate.duplicate(true)
	_candidate = {}
	applied_version = version
	configuration_changed.emit(version)
	return _send({"type": "applied", "version": version})


func reject(version: int, reason := "Game validation failed") -> Error:
	if _candidate.is_empty() or int(_candidate.version) != version:
		return ERR_INVALID_PARAMETER
	_candidate = {}
	# Callers must use a fixed diagnostic, never a value, credential, or server body.
	return _send({"type": "failed", "version": version, "error": reason.left(160)})


func get_value(feature_id: String, entry_id: String, fallback: Variant = null) -> Variant:
	return value_in_snapshot(_valid, feature_id, entry_id, fallback)


static func value_in_snapshot(snapshot: Dictionary, feature_id: String, entry_id: String, fallback: Variant = null) -> Variant:
	for feature: Dictionary in snapshot.get("features", []):
		if feature.get("id") == feature_id:
			for entry: Dictionary in feature.get("entries", []):
				if entry.get("id") == entry_id:
					var value: Variant = entry.get("value", fallback)
					return value.duplicate(true) if value is Dictionary or value is Array else value
	return fallback


func get_snapshot() -> Dictionary:
	return _valid.duplicate(true)
