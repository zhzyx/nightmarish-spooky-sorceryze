extends SceneTree
const Client = preload("res://game_config_client.gd")
var client = Client.new()
var damage := 10.0
var reconnected := false


func _initialize() -> void:
	root.add_child(client)
	client.snapshot_received.connect(_apply)
	client.connection_changed.connect(func(state: String): _event({"state": state}))
	client.start(OS.get_environment("GAME_CONFIG_URL"), OS.get_environment("GAME_CONFIG_PROJECT_ID"), "Godot headless acceptance")
	create_timer(45).timeout.connect(func(): quit(2))


func _event(message: Dictionary) -> void:
	print("GAME_CONFIG_EVENT " + JSON.stringify(message))


func _apply(snapshot: Dictionary) -> void:
	if int(snapshot.version) == 1:
		create_timer(0.75).timeout.connect(func(): _commit(snapshot))
	else:
		_commit(snapshot)


func _commit(snapshot: Dictionary) -> void:
	if Client.value_in_snapshot(snapshot, "combat", "large_content") != "配置".repeat(150000):
		_event({"error": "Large snapshot content was not preserved"})
		quit(3)
		return
	var value: Variant = Client.value_in_snapshot(snapshot, "combat", "damage")
	if not (value is int or value is float) or not is_finite(float(value)) or value < 0 or value > 100:
		client.reject(int(snapshot.version), "Game damage constraint rejected")
		_event({"rejected": int(snapshot.version), "damage": damage, "applied": client.applied_version})
		return
	damage = float(value)
	client.acknowledge(int(snapshot.version))
	_event({"applied": int(snapshot.version), "damage": damage})
	if int(snapshot.version) == 2 and not reconnected:
		reconnected = true
		# Defer to let the first receipt reach the service, then sever the socket.
		# The client's retry loop (not a second start call) must recover.
		create_timer(0.5).timeout.connect(func(): client._socket.close())
