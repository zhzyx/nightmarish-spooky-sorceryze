@tool
extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1).timeout
	var dock := root.find_child("AI Chat", true, false)
	dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
	dock.find_child("ConsultationOnly", true, false).button_pressed = false
	var pid := OS.get_process_id()
	var file := FileAccess.open("res://lock-ready-%d.json" % pid, FileAccess.WRITE)
	file.store_string(JSON.stringify({"pid": pid}))
	file.close()
	while not FileAccess.file_exists("res://lock-finish-%d" % pid):
		await process_frame
	quit()
