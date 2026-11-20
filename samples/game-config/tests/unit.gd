extends SceneTree
const Client = preload("res://game_config_client.gd")
var failures := 0


func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		printerr("FAIL: " + message)


func snapshot(version: int, value: Variant) -> Dictionary:
	return {"version": version, "features": [{"id": "combat", "entries": [{"id": "damage", "value": value}]}]}


func _initialize() -> void:
	var client = Client.new()
	root.add_child(client)
	client._handle_message({"type": "snapshot", "project": snapshot(1, 10)})
	check(client.applied_version == 0, "receipt must not be automatic")
	check(client.get_value("combat", "damage", -1) == -1, "candidate cannot change valid values")
	check(client.acknowledge(2) == ERR_INVALID_PARAMETER, "future receipt is rejected")
	client.acknowledge(1)
	check(client.applied_version == 1 and client.get_value("combat", "damage") == 10, "explicit application commits atomically")
	client._handle_message({"type": "snapshot", "project": snapshot(2, 900)})
	client.reject(2)
	check(client.applied_version == 1 and client.get_value("combat", "damage") == 10, "failed application keeps last valid values")
	client._handle_message({"type": "snapshot", "project": snapshot(3, {"nested": [1]})})
	client.acknowledge(3)
	var external: Dictionary = client.get_value("combat", "damage")
	external.nested.append(2)
	check(client.get_value("combat", "damage").nested.size() == 1, "reads cannot mutate valid values")
	var copy: Dictionary = client.get_snapshot()
	copy.features.clear()
	check(client.get_snapshot().features.size() == 1, "snapshot reads are isolated")
	client._handle_message({"type": "snapshot", "project": snapshot(2, 40)})
	check(client.acknowledge(2) == ERR_INVALID_PARAMETER, "stale snapshot is ignored")
	client._handle_message({"type": "snapshot", "project": {"version": 4, "features": "bad"}})
	check(client.acknowledge(4) == ERR_INVALID_PARAMETER, "malformed snapshot is ignored")
	client._handle_message({"type": "snapshot", "project": snapshot(3, {"nested": [1]})})
	client.acknowledge(3)
	check(client.applied_version == 3, "same authoritative version can be acknowledged after reconnect")
	client.free()
	print("GAME_CONFIG_UNIT " + JSON.stringify({"passed": failures == 0, "failures": failures}))
	quit(0 if failures == 0 else 1)
