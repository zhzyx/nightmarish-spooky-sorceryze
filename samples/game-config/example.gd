extends Node
const ConfigClient = preload("res://game_config_client.gd")

var config = ConfigClient.new()
var damage := 10.0
var _label: Label


func _ready() -> void:
	add_child(config)
	_label = Label.new()
	_label.position = Vector2(30, 30)
	add_child(_label)
	config.snapshot_received.connect(apply_configuration)
	config.connection_changed.connect(func(_state: String): _refresh())
	_refresh()
	config.start(OS.get_environment("GAME_CONFIG_URL"), OS.get_environment("GAME_CONFIG_PROJECT_ID"))


func apply_configuration(snapshot: Dictionary) -> void:
	var candidate: Variant = ConfigClient.value_in_snapshot(snapshot, "combat", "damage")
	# The service allows 0..1000; this game's current mechanics allow only 0..100.
	# Validate ALL game dependencies before changing any live gameplay field.
	if not (candidate is int or candidate is float) or not is_finite(float(candidate)) or candidate < 0 or candidate > 100:
		config.reject(int(snapshot.version), "combat.damage must be a finite number in 0..100 for this game")
		return
	damage = float(candidate)
	config.acknowledge(int(snapshot.version))
	_refresh()


func _refresh() -> void:
	_label.text = "Live game configuration\nState: %s\nApplied version: %d\ncombat.damage: %.1f" % [config.connection_state, config.applied_version, damage]
