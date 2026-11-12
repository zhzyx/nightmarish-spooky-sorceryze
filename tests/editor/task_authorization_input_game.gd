extends Node

var observed := false
var press_usec := -1
var release_usec := -1
var peak_strength := 0.0
var min_pressed_strength := 1.0
var max_frame_usec := 0
var previous_usec := -1

func _ready():
	get_tree().create_timer(30).timeout.connect(get_tree().quit)

func _process(_delta):
	var now := Time.get_ticks_usec()
	if previous_usec >= 0:
		max_frame_usec = maxi(max_frame_usec, now - previous_usec)
	previous_usec = now
	var pressed := Input.is_action_pressed("fixture_move")
	var strength := Input.get_action_strength("fixture_move")
	if pressed:
		observed = true
		if press_usec < 0:
			press_usec = now
		peak_strength = maxf(peak_strength, strength)
		min_pressed_strength = minf(min_pressed_strength, strength)
	elif press_usec >= 0 and release_usec < 0:
		release_usec = now
	var f = FileAccess.open("res://game-state.json.pending", FileAccess.WRITE)
	f.store_string(JSON.stringify({"observed": observed, "pressed": pressed,
		"strength": strength, "peak_strength": peak_strength,
		"min_pressed_strength": min_pressed_strength, "press_usec": press_usec,
		"release_usec": release_usec, "max_frame_usec": max_frame_usec,
		"duration_seconds": float(release_usec - press_usec) / 1000000.0}))
	f.close()
	DirAccess.rename_absolute("res://game-state.json.pending", "res://game-state.json")
