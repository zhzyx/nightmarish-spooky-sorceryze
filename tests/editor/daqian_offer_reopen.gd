@tool
extends SceneTree

func _initialize():
	run.call_deferred()

func run():
	var chat = root.find_child("AI Chat", true, false)
	var old = JSON.parse_string(FileAccess.get_file_as_string("res://old-offer.json"))
	var deadline = Time.get_ticks_msec() + 6000
	var stopped_before_card = false
	var gate_signal = OS.get_environment("DAQIAN_DELAY_AUTHORITY")
	if not gate_signal.is_empty():
		while not FileAccess.file_exists(gate_signal) and Time.get_ticks_msec() < deadline:
			await create_timer(0.05).timeout
		var stop = chat.find_child("Stop", true, false)
		if FileAccess.file_exists(gate_signal) and not stop.disabled and chat.get_daqian_approval().is_empty():
			stop.pressed.emit()
			stopped_before_card = true
		DirAccess.remove_absolute(gate_signal)
	while chat.get_daqian_approval().is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	var offer = chat.get_daqian_approval()
	var report = {"stopped_before_card": stopped_before_card, "unexecuted": not FileAccess.file_exists(str(old.root).path_join("executions")), "offered": not offer.is_empty(), "old_accepted": chat.confirm_daqian_approval(old.token)}
	report["cwd_rejected"] = false
	for label in chat.find_children("*", "RichTextLabel", true, false):
		if label.get_parsed_text().contains("an accessible working directory"):
			report["cwd_rejected"] = true
	if not offer.is_empty():
		report["fresh"] = offer.token != old.token
		# A second window may publish a different journal while this card is open.
		var path = "res://.godot/editor/ai_chat_resume.json"
		var original = FileAccess.get_file_as_bytes(path)
		var other_offer = JSON.parse_string(original.get_string_from_utf8())
		other_offer.conversation = "another-window"
		var other = JSON.stringify(other_offer).to_utf8_buffer()
		FileAccess.open(path, FileAccess.WRITE).store_buffer(other)
		report["foreign_rejected"] = not chat.confirm_daqian_approval(offer.token)
		report["foreign_preserved"] = FileAccess.get_file_as_bytes(path) == other
		FileAccess.open(path, FileAccess.WRITE).store_buffer(original)
		for field in ["detail", "step", "actor", "request", "source_sha256", "url", "board_workspace", "root"]:
			report[field] = offer[field] == old[field]
		if OS.get_environment("DAQIAN_OFFER_DECISION") == "confirm":
			report["confirmed"] = chat.confirm_daqian_approval(offer.token)
			report["duplicate"] = chat.confirm_daqian_approval(offer.token)
			await create_timer(3).timeout
		elif OS.get_environment("DAQIAN_OFFER_DECISION") == "stop":
			FileAccess.open(path, FileAccess.WRITE).store_buffer(other)
			var composer = root.find_child("ChatInput", true, false)
			composer.text = "停止"
			root.find_child("ChatLayout", true, false).find_child("Send", true, false).pressed.emit()
			report["foreign_survived_stop"] = FileAccess.get_file_as_bytes(path) == other
	FileAccess.open("res://offer-observed.json", FileAccess.WRITE).store_string(JSON.stringify(report))
	quit()
