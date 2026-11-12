extends SceneTree

func _initialize():
	call_deferred("check")

func check():
	var source = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("UNICODE_INPUT_FILE")))
	var cases = [str(source.value), "normal short text", "中文界😀'\"".repeat(2700), "a\u0301 界 😀 👨‍👩‍👧‍👦 'quotes'\nsecond line"]
	var results = []
	for surface in ["TextEdit", "RichTextLabel"]:
		if not OS.get_environment("UNICODE_INPUT_SURFACE").is_empty() and surface != OS.get_environment("UNICODE_INPUT_SURFACE"):
			continue
		for index in cases.size():
			var value = cases[index]
			print("LAYOUT_BEGIN ", surface, " ", index)
			var control = TextEdit.new() if surface == "TextEdit" else RichTextLabel.new()
			control.size = Vector2(420, 180)
			if surface == "TextEdit":
				control.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
			else:
				control.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			root.add_child(control)
			control.text = value
			await process_frame
			await process_frame
			var lines = control.get_total_visible_line_count() if surface == "TextEdit" else control.get_line_count()
			var actual = control.text
			assert(actual.to_utf8_buffer() == value.to_utf8_buffer())
			assert(lines > 0)
			if index == 0 or index == 2:
				assert(lines > 2)
			results.append({"surface": surface, "case": index, "characters": actual.length(), "sha256": actual.sha256_text(), "lines": lines})
			control.queue_free()
			await process_frame
	FileAccess.open(OS.get_environment("UNICODE_INPUT_RESULT"), FileAccess.WRITE).store_string(JSON.stringify({"ok": true, "cases": results}, "\t"))
	quit()
