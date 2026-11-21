extends SceneTree

const LOCATION := "/api/v1/business-modules/default/location"
var session: Node
var checks: Array[String] = []
var late_status := -1


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, label: String) -> bool:
	if ok:
		checks.append(label)
	else:
		printerr("D14 failed: " + label)
		quit(1)
	return ok


func field(node_name: String) -> LineEdit:
	return session.find_child(node_name, true, false) as LineEdit


func button(node_name: String) -> Button:
	return session.find_child(node_name, true, false) as Button


func submit(email: String, secret: String, project: String) -> void:
	if not field("AccountSecret").is_visible_in_tree():
		button("ChooseAccount").pressed.emit()
	field("AccountEmail").text = email
	field("AccountSecret").text = secret
	field("BusinessProject").text = project
	button("Authenticate").pressed.emit()


func wait_for_user(expected: String) -> bool:
	for frame in 900:
		if session.get_identity().get("id", "") == expected:
			return true
		await process_frame
	return false


func late_read() -> void:
	var result: Dictionary = await session.api_request(HTTPClient.METHOD_GET, LOCATION)
	late_status = result.status


func run() -> void:
	root.size = Vector2i(1600, 900)
	await create_timer(1.0).timeout
	var dock := root.find_child("AIWorkbenchSidebar", true, false) as EditorDock
	if not check(dock != null, "native sidebar"):
		return
	var palette := EditorInterface.get_command_palette()
	var shortcut := InputEventShortcut.new()
	shortcut.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(shortcut)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not check(results.get_selected().get_metadata(0) == search.text, "open workbench command"):
		return
	results.item_activated.emit()
	await process_frame
	session = dock.find_child("WorkbenchBusinessSession", true, false)
	if not check(session != null and session.has_method("api_request"), "business session mounted"):
		return
	var account_a := OS.get_environment("D14_USER_A")
	var account_b := OS.get_environment("D14_USER_B")
	var project := "studio/game"
	var email := "first@example.invalid"
	var password := OS.get_environment("D14_PASSWORD")
	var key := OS.get_environment("D14_PERSONAL_KEY")
	submit(email, password, project)
	if not check(await wait_for_user(account_a) and field("AccountSecret").text.is_empty(), "account password verified and field cleared"):
		return
	if not check(session.get_identity().role == "admin" and session.get_identity().project == project, "verified admin and project"):
		return
	var response: Dictionary = await session.api_request(HTTPClient.METHOD_GET, LOCATION)
	if not check(response.status == 200 and response.data.location.position == "first-private-position", "first account private position"):
		return
	late_read()
	submit("", key, project)
	if not check(session.get_identity().is_empty(), "previous identity cleared synchronously"):
		return
	if not check(await wait_for_user(account_b) and session.get_identity().role == "viewer", "personal key verified for second account"):
		return
	for frame in 900:
		if late_status >= 0:
			break
		await process_frame
	if not check(late_status == 0, "old account response discarded"):
		return
	response = await session.api_request(HTTPClient.METHOD_GET, LOCATION + "?unused=1")
	if not check(response.status == 200 and response.data.location.position == "second-private-position", "second account private position with project query"):
		return
	response = await session.api_request(HTTPClient.METHOD_PUT, LOCATION, {"position": "unauthorized"})
	if not check(response.status == 403 and session.get_identity().id == account_b, "viewer write denied by server, session retained"):
		return
	# Revoke this disposable key through the real admin service in the runner.
	var flag := FileAccess.open(OS.get_environment("D14_REVOKE"), FileAccess.WRITE)
	flag.close()
	for frame in 900:
		if FileAccess.file_exists(OS.get_environment("D14_REVOKED")):
			break
		await process_frame
	response = await session.api_request(HTTPClient.METHOD_GET, LOCATION)
	var status := session.find_child("SessionStatus", true, false) as Label
	if not check(response.status == 401 and session.get_identity().is_empty() and "重新认证" in status.text and field("AccountSecret").is_visible_in_tree(), "revocation prompts native reauthentication"):
		printerr("status=", response.status, ", reauth=", "重新认证" in status.text, ", form=", field("AccountSecret").get_parent().visible, ", acknowledged=", FileAccess.file_exists(OS.get_environment("D14_REVOKED")))
		return
	response = await session.api_request(HTTPClient.METHOD_PUT, LOCATION, {"position": "after-revocation"})
	if not check(response.status == 401, "write rejected while signed out"):
		return
	submit(email, password, "studio/other")
	if not check(await wait_for_user(account_a), "reauthenticated"):
		return
	response = await session.api_request(HTTPClient.METHOD_GET, LOCATION)
	if not check(response.status == 200 and response.data.location == null, "different project isolated"):
		return
	submit(email, password, project)
	if not check(await wait_for_user(account_a), "returned to first project"):
		return
	response = await session.api_request(HTTPClient.METHOD_GET, LOCATION)
	if not check(response.status == 200 and response.data.location.position == "first-private-position", "original location restored"):
		return
	button("SignOut").pressed.emit()
	if not check(session.get_identity().is_empty(), "explicit logout clears identity"):
		return
	print("D14_CHECKS=" + JSON.stringify(checks))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
