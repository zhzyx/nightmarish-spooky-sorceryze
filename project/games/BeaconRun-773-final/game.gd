extends Node2D

@onready var player = $Player
@onready var beacon = $Beacon
var won: bool = false

func restart_game() -> void:
	player.position = Vector2(80, 200)
	beacon.position = Vector2(600, 200)
	won = false
	update_label()

func _ready() -> void:
	restart_game()

func check_goal() -> void:
	if beacon.reached(player.position):
		won = true
	update_label()

func update_label() -> void:
	$Label.text = "BEACON RUN\nArrows move • Reach the gold diamond • Enter restarts\n" + ("VICTORY! Beacon reached!" if won else "Find the beacon!")

func _process(_delta: float) -> void:
	check_goal()
	if Input.is_action_just_pressed("ui_accept"):
		restart_game()
