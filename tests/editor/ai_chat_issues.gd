@tool
extends SceneTree

var dock: Control
var host: VBoxContainer
var failures: Array[String] = []
var received := {}
var cancelled := {}

func _initialize():
	run.call_deferred()

func check(ok: bool, message: String) -> bool:
	if not ok:
		failures.append(message)
		push_error(message)
	return ok

func open_issue(number: int, message := "") -> bool:
	var url := "https://github.com/fixture/concurrency/issues/%d" % number
	var selection := {} if message.is_empty() else {"backend": 0, "id": "fixture"}
	var error: String = dock.open_daqian_chat(url, number, "request-%d" % number, message, true, selection, true)
	return check(error.is_empty(), error) and check(dock.mount_daqian_chat(host), "Cannot mount issue %d" % number)

func wait_for_file(file: String) -> bool:
	var deadline := Time.get_ticks_msec() + 14000
	while not FileAccess.file_exists("res://" + file) and Time.get_ticks_msec() < deadline:
		await create_timer(0.04).timeout
	return check(FileAccess.file_exists("res://" + file), "Model never received " + file)

func finish():
	FileAccess.open("res://steering-report.json", FileAccess.WRITE).store_string(JSON.stringify({
		"passed": failures.is_empty(), "failures": failures, "received": received, "cancelled": cancelled}))
	quit(0 if failures.is_empty() else 1)

func run():
	await create_timer(1.0).timeout
	dock = root.find_child("AI Chat", true, false)
	var settings = EditorInterface.get_editor_settings()
	var workspace := ProjectSettings.globalize_path("res://").trim_suffix("/")
	settings.set_setting("gonggong/workspace", workspace)
	settings.set_project_metadata("daqian_access", workspace.sha256_text(), {"actor":{
		"repo_id":"fixture", "user_id":"tester", "repo":"fixture/concurrency"}})
	var controls = dock.get_ai_settings_control()
	controls.find_child("APIEndpoint", true, false).text = OS.get_environment("STEERING_ENDPOINT")
	controls.find_child("APIKey", true, false).text = "isolated-fixture-key"
	controls.find_child("APIModel", true, false).text = "fixture"
	controls.find_child("AllowTools", true, false).button_pressed = false
	host = VBoxContainer.new()
	root.add_child(host)
	dock.daqian_preview_received.connect(func(source, reply): received[source] = JSON.parse_string(reply).result)
	dock.daqian_preview_failed.connect(func(source, reason): cancelled[source] = reason)
	if OS.get_environment("STEERING_CASE") == "restore":
		if open_issue(2):
			check(host.find_child("ChatInput", true, false).text == "draft B", "B lost draft on restart")
			var content := ""
			for label in host.find_children("*", "RichTextLabel", true, false):
				content += label.get_parsed_text()
			check("ISSUE_B_REPLY" in content and "ISSUE_A" not in content, "B history not isolated on restart")
			dock.unmount_daqian_chat()
		if open_issue(1):
			check(host.find_child("ChatInput", true, false).text == "draft A", "A lost draft on restart")
			dock.unmount_daqian_chat()
		finish()
		return
	# An older saved Issue in the primary tab set must still open while A runs.
	if not open_issue(2):
		finish()
		return
	host.find_child("ChatInput", true, false).text = "existing draft B"
	dock.unmount_daqian_chat()
	if not open_issue(1, "ISSUE_A") or not await wait_for_file("ISSUE_A"):
		finish()
		return
	host.find_child("ChatInput", true, false).text = "draft A"
	dock.unmount_daqian_chat()
	if not open_issue(2):
		finish()
		return
	var existing = host.find_child("ChatInput", true, false)
	check(existing.text == "existing draft B", "Archived B lost its draft")
	existing.text = ""
	if not open_issue(2, "ISSUE_B") or not await wait_for_file("ISSUE_B"):
		finish()
		return
	var input = host.find_child("ChatInput", true, false)
	check(input.text.is_empty(), "B inherited A draft")
	input.text = "draft B"
	dock.unmount_daqian_chat()
	if not open_issue(1):
		finish()
		return
	check(host.find_child("ChatInput", true, false).text == "draft A", "A lost its draft")
	host.find_child("Stop", true, false).pressed.emit()
	dock.unmount_daqian_chat()
	if not open_issue(2):
		finish()
		return
	check(host.find_child("ChatInput", true, false).text == "draft B", "B lost its draft")
	check(not host.find_child("Stop", true, false).disabled, "Stopping A cancelled B")
	FileAccess.open("res://release-response", FileAccess.WRITE).store_string("ok")
	var deadline := Time.get_ticks_msec() + 10000
	while received.is_empty() and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	check(received == {"https://github.com/fixture/concurrency/issues/2": "ISSUE_B_REPLY"}, "Incorrect completion " + str(received))
	check(cancelled.has("https://github.com/fixture/concurrency/issues/1") and cancelled.size() == 1, "Incorrect cancellation " + str(cancelled))
	dock.unmount_daqian_chat()
	finish()
