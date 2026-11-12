extends SceneTree

func _initialize() -> void:
	call_deferred("verify")

func verify() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	await process_frame
	game.set_process(false)
	game.player.set_process(false)
	game.restart_game()
	assert(game.player.position == Vector2(80, 200))
	assert(game.beacon.position == Vector2(600, 200))
	assert(not game.won)
	game.player.move_direction(Vector2(3, 4), 0.5)
	assert(game.player.position.is_equal_approx(Vector2(152, 296)))
	game.check_goal()
	assert(not game.won)
	game.player.position = game.beacon.position
	game.check_goal()
	assert(game.won)
	game.restart_game()
	assert(game.player.position == Vector2(80, 200))
	assert(game.beacon.position == Vector2(600, 200))
	assert(not game.won)
	print("LIVE_GAME_PLAYABLE_OK")
	quit()
