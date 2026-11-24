@tool
extends SceneTree

var failures: Array[String] = []
var presses := 0

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1.0).timeout
	var base := EditorInterface.get_base_control()
	var viewport := SubViewport.new()
	viewport.size = Vector2i(800, 600)
	viewport.handle_input_locally = true
	base.add_child(viewport)
	var button := Button.new()
	button.text = "交互检查"
	button.position = Vector2(400, 200)
	button.size = Vector2(200, 60)
	viewport.add_child(button)
	button.pressed.connect(func(): presses += 1)
	await process_frame
	var motion := InputEventMouseMotion.new()
	motion.position = button.get_global_rect().get_center()
	viewport.push_input(motion)
	await process_frame
	if button.get_draw_mode() != BaseButton.DRAW_HOVER:
		failures.append("pointer hover did not reach the actual button")
	var click := InputEventMouseButton.new()
	click.position = motion.position
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	viewport.push_input(click)
	if button.get_draw_mode() != BaseButton.DRAW_PRESSED:
		failures.append("pointer down did not enter pressed state")
	click = click.duplicate()
	click.pressed = false
	viewport.push_input(click)
	if presses != 1:
		failures.append("pointer activation must emit exactly once")
	button.grab_focus()
	var key := InputEventKey.new()
	key.keycode = KEY_SPACE
	key.pressed = true
	viewport.push_input(key)
	key = key.duplicate()
	key.pressed = false
	viewport.push_input(key)
	if presses != 2:
		failures.append("keyboard activation must emit exactly once")
	button.disabled = true
	click = click.duplicate()
	click.pressed = true
	viewport.push_input(click)
	click = click.duplicate()
	click.pressed = false
	viewport.push_input(click)
	if presses != 2 or button.get_draw_mode() != BaseButton.DRAW_DISABLED:
		failures.append("disabled control accepted input or lost disabled appearance")
	viewport.queue_free()
	await process_frame
	print(JSON.stringify({"failures": failures, "presses": presses, "input_scope": "private headless viewport only; no OS input"}))
	quit(0 if failures.is_empty() else 1)
