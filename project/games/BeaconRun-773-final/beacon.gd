extends Node2D


func reached(player_position: Vector2) -> bool:
	return position.distance_to(player_position) <= 28.0
