extends SceneTree

var checks: Array[String] = []


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Tianxuan connect: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func status_is(view: Control, message: String) -> bool:
	var deadline := Time.get_ticks_msec() + 18000
	while view._status.text != view.tr(message) and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	return view._status.text == view.tr(message)


func connect_button(view: Control) -> Button:
	for node in view._login.get_children():
		if node is Button and node.text == "连接服务":
			return node
	return null


func set_response_mode(value: String) -> void:
	var file := FileAccess.open(OS.get_environment("TX_RESPONSE_MODE"), FileAccess.WRITE)
	file.store_string(value)
	file.close()


func run() -> void:
	await process_frame
	await process_frame
	var view: Control = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
	if not check(view != null, "native workspace mounted"):
		return
	if OS.get_environment("TX_SOURCE_LOADED") == "1":
		var session_script: Script = load("res://session_controller.gd")
		var override := OS.get_environment("TIANXUAN_API")
		OS.unset_environment("TIANXUAN_API")
		var fresh_session: Node = session_script.new()
		OS.set_environment("TIANXUAN_API", override)
		var default_origin: String = fresh_session.origin
		fresh_session.free()
		if not check(default_origin == OS.get_environment("TX_DEFAULT_ORIGIN"), "unconfigured session starts with the production HTTPS address"):
			return
		var session: Node = session_script.new()
		root.add_child(session)
		var workspace := (load("res://workspace_controller.gd") as Script).new() as Node
		workspace.set_meta("session_controller", session)
		root.add_child(workspace)
		var candidate := (load("res://workspace_view.gd") as Script).new() as Control
		candidate.set_meta("scripts", view.get_meta("scripts"))
		candidate.set_meta("controller", workspace)
		root.add_child(candidate)
		view = candidate
	if not check(view._address.text == OS.get_environment("TX_EXPECT_ORIGIN"), "initial service field reflects the selected address"):
		print("Actual service field: ", view._address.text)
		return
	if OS.get_environment("TX_TEST_BUTTON") == "1":
		if not await exercise_button(view):
			return
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)


func exercise_button(view: Control) -> bool:
	var ready := "服务已连接，请登录工作区。"
	var busy := "正在连接服务…"
	var failed := "无法读取服务登录配置，请检查地址和编辑器代理后重试。"
	var button := connect_button(view)
	if not check(button != null and not button.disabled, "ordinary connect button available"):
		return false
	if not check(await status_is(view, ready) and not view._submit.disabled, "initial loopback service reached with the editor proxy configured"):
		return false
	view._address.text = "https://connect-probe.invalid"
	button.pressed.emit()
	if not check(view._status.text == view.tr(busy) and view._submit.disabled, "click immediately exposes pending status"):
		return false
	if not check(await status_is(view, failed) and not button.disabled and view._submit.disabled, "proxy failure leaves a usable retry button"):
		return false
	view._address.text = OS.get_environment("TIANXUAN_API")
	set_response_mode("unavailable")
	button.pressed.emit()
	if not check(await status_is(view, failed) and not button.disabled, "service error permits retry at the same address"):
		return false
	set_response_mode("keys")
	button.pressed.emit()
	if not check(view._status.text == view.tr(busy) and await status_is(view, ready), "retry shows progress then successful completion"):
		return false
	if not check(not view._submit.disabled and view._mode.item_count == 1 and view._mode.get_item_text(0) == "个人访问密钥", "keys deployment exposes only its supported login method"):
		return false
	set_response_mode("legacy")
	button.pressed.emit()
	if not check(await status_is(view, ready) and not view._submit.disabled and view._mode.item_count == 1, "legacy deployment retains its existing login method"):
		return false
	set_response_mode("unknown")
	button.pressed.emit()
	if not check(await status_is(view, failed) and view._submit.disabled and not button.disabled, "unsupported deployment configuration remains retryable"):
		return false
	set_response_mode("accounts")
	button.pressed.emit()
	if not check(await status_is(view, ready) and view._mode.item_count == 2 and view._mode.get_item_text(0) == "账号与密码", "accounts deployment also offers password login"):
		return false
	if not check(await view.session.authenticate("", "fixture-viewer-key", "workspace"), "private viewer signed in"):
		return false
	var identity: Dictionary = view.session.get_identity()
	set_response_mode("unavailable")
	button.pressed.emit()
	if not check(view._status.text == view.tr(busy) and await status_is(view, failed), "signed-in viewer sees pending and failure feedback on the same service"):
		return false
	set_response_mode("keys")
	button.pressed.emit()
	return check(await status_is(view, "服务已连接。") and view.session.get_identity() == identity, "signed-in retry confirms connection and preserves identity")
