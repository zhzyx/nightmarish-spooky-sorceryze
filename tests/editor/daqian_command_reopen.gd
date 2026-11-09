@tool
extends SceneTree

func _initialize() -> void:
	observe.call_deferred()

func observe() -> void:
	var deadline := Time.get_ticks_msec() + 30000
	var watched := false
	var rejected := false
	var stopped := false
	var text := ""
	var journal_path := "res://.godot/editor/ai_chat_resume.json"
	while Time.get_ticks_msec() < deadline:
		await create_timer(0.2).timeout
		text = ""
		var dock := root.find_child("AI Chat", true, false)
		for label in dock.find_children("*", "RichTextLabel", true, false):
			text += label.get_parsed_text()
		if not watched and FileAccess.file_exists(journal_path) and text.contains("原命令仍在运行") and OS.has_environment("DAQIAN_RELEASE_MARKER"):
			watched = true
			if OS.has_environment("DAQIAN_STOP_WATCH"):
				var stop: Button = dock.find_child("Stop", true, false)
				if not stop.disabled:
					stop.pressed.emit()
					stopped = true
			FileAccess.open(OS.get_environment("DAQIAN_RELEASE_MARKER"), FileAccess.WRITE).close()
			if stopped:
				await create_timer(2.0).timeout
				continue
		rejected = text.contains("原命令的工作者或授权绑定已变化") and FileAccess.file_exists("res://.fixture/changed-authority")
		if not FileAccess.file_exists(journal_path) or rejected:
			break
	var result := {"journal": FileAccess.file_exists(journal_path), "stopped": stopped, "watched": watched, "rejected": rejected, "text": text}
	FileAccess.open("res://observed.json", FileAccess.WRITE).store_string(JSON.stringify(result))
	quit()
