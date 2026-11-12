extends Node2D

var speed: float = 240.0


func move_direction(direction: Vector2, delta: float) -> void:
	position += direction.normalized() * speed * delta


func _process(delta: float) -> void:
	move_direction(Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down"), delta)
