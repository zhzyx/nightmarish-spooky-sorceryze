@tool
extends "res://probe.gd"

func run() -> void:
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false)
	var config = dock.get_ai_settings_control()
	config.find_child("APIEndpoint", true, false).text = OS.get_environment("U15_ENDPOINT")
	var key: LineEdit = config.find_child("APIKey", true, false)
	key.text = "fixture-restored-placeholder"
	key.text_changed.emit(key.text)
	dock.find_child("APIModel", true, false).text = "fixture"
	var rows = dock.find_child("WorkbenchReferenceRows", true, false)
	var queue = dock.find_child("QueuedMessages", true, false)
	if not _check(rows.get_child_count() == 1 and "restored selection [REDACTED]" in rows.get_child(0).text and dock.get_meta("queue_paused", false), "Restored excerpt and paused queue"): return
	var label: Label = queue.find_children("*", "Label", true, false).front()
	if not _check("fixture-restored-placeholder" not in label.tooltip_text and "[REDACTED]" in label.tooltip_text, "Restored queue preview"): return
	dock.find_child("ResumeMessageQueue", true, false).pressed.emit()
	var deadline := Time.get_ticks_msec() + 18000
	while not FileAccess.file_exists("res://received") and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	if not _check(FileAccess.file_exists("res://received") and rows.get_child_count() == 1, "Restored queue did not send independently of draft"): return
	print("QUEUE_RESTORED")
	quit()
