@tool
extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1).timeout
	var chat := root.find_child("AI Chat", true, false)
	chat.set_runtime_field("workflow_python", OS.get_environment("G17_PYTHON"))
	EditorInterface.set_main_screen_editor("天枢")
	await process_frame
	var panel = root.find_child("DaqianWorkspace", true, false)
	if panel == null or not panel.historical_issue_button.is_visible_in_tree():
		push_error("Historical issue entry missing")
		quit(1)
		return
	panel.historical_issue_button.pressed.emit()
	await process_frame
	var dialog: AcceptDialog = panel.historical_issue_dialog
	var fields := dialog.find_children("*", "LineEdit", true, false)
	var view: TextEdit = dialog.find_children("*", "TextEdit", true, false)[0]
	var button: Button
	for child in dialog.find_children("*", "Button", true, false):
		if child.text == "读取历史工单":
			button = child
	var project := OS.get_environment("G17_PROJECT")
	var pull := OS.get_environment("G17_PULL")
	var expected := OS.get_environment("G17_REVIEW")
	var prior := ""
	var readings := []
	fields[0].text = project
	for step in range(3):
		var source := pull
		if step == 1:
			for line in prior.split("\n"):
				if line == expected:
					source = line
					break
			if source != expected:
				push_error("Archived PR did not expose the original review link")
				quit(1)
				return
		elif step == 2:
			source = OS.get_environment("G17_WRONG_PULL")
		fields[1].text = source
		button.pressed.emit()
		var deadline := Time.get_ticks_msec() + 40000
		while button.disabled and Time.get_ticks_msec() < deadline:
			await create_timer(0.05).timeout
		prior = view.text
		if button.disabled or view.editable or not view.is_visible_in_tree() or source not in prior:
			push_error("Archive reader failed: " + prior)
			quit(1)
			return
		if step == 1:
			var body := prior.substr(prior.find("\n\n") + 2)
			if body.sha256_text() != OS.get_environment("G17_BODY_SHA256"):
				push_error("Archived review body differs from original")
				quit(1)
				return
		if step == 2 and not prior.begins_with("无法读取历史工单"):
			push_error("Accepted a review under the wrong PR")
			quit(1)
			return
		readings.append({"source": source, "display_sha256": prior.sha256_text()})
	print("G17_READS=" + JSON.stringify(readings))
	quit(0)
