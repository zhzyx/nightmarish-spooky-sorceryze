extends SceneTree
## Real entry/workflow services with explicitly deterministic, controllable roles.

var checks: Array[String] = []
var main: Control
var controller: Node
var session: Node
var ai_before: Dictionary
const LocalModelFixture = preload("res://local_model_fixture.gd")


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native execution controls: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func wait_until(predicate: Callable, seconds := 12.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	return predicate.call()


func worker(marker: String) -> String:
	var directory := OS.get_environment("TX_EXECUTION_WORKERS")
	for name in DirAccess.get_directories_at(directory):
		if FileAccess.file_exists(directory.path_join(name).path_join(marker)):
			return name
	return ""


func run_state(key: String, expected: String) -> Dictionary:
	for attempt in 400:
		var result: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/status", {"key": key})
		if result.status != 200:
			return {}
		if expected.is_empty() or result.data.progress.state == expected:
			return result.data.progress
		await create_timer(0.1).timeout
	return {}


func issue_action(name: String) -> bool:
	await wait_until(func(): return not controller.issues.saving and not controller.issues.loading)
	await controller.issues.refresh()
	var view = main._page_instances.issues
	var button = view.find_child(name, true, false)
	if not check(button is Button and not button.disabled, "native action is available: " + name):
		print(JSON.stringify({"detail": controller.issues.detail, "status": controller.issues.status}))
		return false
	var before: Dictionary = controller.issues.detail.duplicate(true)
	button.pressed.emit()
	if not check(view._confirmation.visible and controller.issues.detail == before, "action waits for explicit version-bound confirmation: " + name):
		return false
	view._confirmation.confirmed.emit()
	view._confirmation.hide()
	return check(await wait_until(func(): return not controller.issues.saving and not controller.issues.loading and controller.issues.pending().is_empty()), "confirmed action receives a determinate service receipt: " + name)


func prepare_launch() -> bool:
	var sidebar := EditorInterface.get_base_control().find_child("TianxuanSidebarView", true, false)
	sidebar.find_child("OpenTianxuanWorkspace", true, false).pressed.emit()
	controller.navigate("home")
	var composer := main.find_child("TianxuanComposer", true, false) as TextEdit
	var current_label := main.find_child("TianxuanCurrentContext", true, false) as Label
	if not check(await wait_until(func(): return composer.is_visible_in_tree() and current_label.is_visible_in_tree() and not controller.editor_context.current_context().is_empty() and current_label.tooltip_text == str(controller.editor_context.current_context().get("text", ""))), "execution preparation opens the native composer and displays its current editor context"):
		return false
	var context: Dictionary = controller.editor_context.message_context(controller.editor_module)
	if not check(context.valid and not str(context.text).is_empty(), "execution preparation verifies the displayed context before sending"):
		return false
	var initiating_request := "生成可核验的文本，并验证暂停和恢复。"
	var expected_content: String = initiating_request + str(context.text)
	composer.text = initiating_request
	var send := main.find_child("SendTianxuanMessage", true, false) as Button
	if not check(not send.disabled, "visible execution composer enables the initiating request"):
		return false
	send.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("turns", []).size() == 1), "native conversation persists the initiating user request"):
		return false
	var conversation: Dictionary = controller.conversation()
	if not check(conversation.turns[0].content == expected_content, "local conversation preserves the exact initiating request and displayed editor context"):
		return false
	if not check(conversation.turns[0].state == "answered" and conversation.turns[0].answer == "本机 API 夹具回答：已收到原生天璇消息。", "execution preparation receives the editor's local API response"):
		return false
	if not check(await wait_until(func(): return controller.local_chat.syncing.is_empty()), "execution preparation waits for the completed local turn to synchronize"):
		return false
	var synchronized: Dictionary = await session.api_request(HTTPClient.METHOD_GET, controller.CONVERSATIONS + "/" + conversation.id)
	if not check(synchronized.status == 200 and synchronized.data.turns.size() == 1 and synchronized.data.turns[0].content == expected_content and synchronized.data.turns[0].answer == conversation.turns[0].answer and synchronized.data.turns[0].reply_source == "editor-local", "execution design uses the exact shared server copy of the initiating request, context and local reply"):
		return false
	if not check(LocalModelFixture.unchanged(ai_before), "execution preparation does not change the ordinary AIChat conversation"):
		return false
	controller.navigate("design")
	await wait_until(func(): return not controller.chat_busy())
	var stage = main.find_child("TianxuanDesignStage", true, false)
	for index in 3:
		stage.select(index)
		stage.item_selected.emit(index)
		main.find_child("TianxuanDesignTitle", true, false).text = "Pause"
		main.find_child("TianxuanDesignBody", true, false).text = "Produce deterministic accepted output in the text scope."
		main.find_child("TianxuanDesignAcceptance", true, false).text = "output must equal deterministic accepted output"
		main.find_child("SaveTianxuanDesign", true, false).pressed.emit()
		var key: String = ["direction", "plan", "design"][index]
		if not check(await wait_until(func(): return not controller.chat_busy() and not controller.design_revision(key).is_empty()), "native design stage is saved: " + key):
			return false
		main.find_child("ConfirmTianxuanDesign", true, false).pressed.emit()
		if not check(await wait_until(func(): return not controller.chat_busy() and controller.design_revision(key).get("confirmed_at") != null), "native design stage is explicitly confirmed: " + key):
			return false
	main.find_child("PublishTianxuanRequirement", true, false).pressed.emit()
	var design = main._page_instances.design
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("requirement_id") != null and design._scopes.get_child_count() > 0), "published requirement reads the installed execution capabilities"):
		return false
	if design._approve.visible:
		design._approve.pressed.emit()
		await wait_until(func(): return not design._approve.visible and not controller.chat_busy())
	for scope in design._scopes.get_children():
		if scope.get_meta("scope") == "text":
			scope.button_pressed = true
	for index in design._models.item_count:
		if design._models.get_item_metadata(index) == "installed":
			design._models.select(index)
	if not check(not design._launch.disabled, "confirmed native requirement enables explicit execution"):
		return false
	design._launch.pressed.emit()
	if not check(design._confirmation.visible and controller.conversation().get("execution") == null, "launch requires confirmation before the service creates an execution"):
		return false
	design._confirmation.confirmed.emit()
	design._confirmation.hide()
	return check(await wait_until(func(): return controller.conversation().get("execution") is Dictionary and not worker("pause-wait").is_empty(), 30.0), "native launch reaches an actual installed producer waiting at a controlled boundary")


func target_confirmation() -> bool:
	var doc: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/docs", {"title": "授权目标", "body_md": "拉杆"})
	if not check(doc.status == 200, "target fixture creates a real design document"):
		return false
	var route := "/api/v1/docs/" + str(doc.data.id) + "/versions/1"
	var signed: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/signoff", {"acceptance": "开桥"})
	var split: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route + "/tasks", {"call_id": controller.new_id(), "items": [{"title": "拉杆", "paragraph": 1, "module_id": "default", "acceptance": "开桥"}]})
	if not check(signed.status == 200 and split.status == 200, "signed design produces an actual task requiring target confirmation"):
		return false
	controller.navigate("issues", str(split.data.tasks[0].id))
	await wait_until(func(): return not controller.issues.loading and not controller.issues.detail.is_empty())
	var view = main._page_instances.issues
	view._forms.target.stage.text = "可操作原型"
	view._forms.target.criteria.text = "拉杆后桥面完全展开"
	view._buttons.target.pressed.emit()
	if not check(await wait_until(func(): return not controller.issues.saving and not controller.issues.loading and controller.issues.detail.get("task_target") is Dictionary and controller.issues.detail.task_target.status == "defined"), "native stage target persists verifiable criteria before confirmation"):
		return false
	if not await issue_action("NativeIssueConfirmTarget"):
		return false
	if not check(controller.issues.detail.task_confirmation.status == "confirmed", "native confirmation is bound to the current target and signed document revision"):
		return false
	if not await issue_action("NativeIssueConfirmTarget"):
		return false
	return check(controller.issues.detail.task_confirmation.status == "revoked", "native revoke clears the current task authorization without deleting its target")


func run() -> void:
	root.size = Vector2i(1600, 1000)
	await process_frame
	await process_frame
	main = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
	if not check(main != null, "compiled native workspace is installed"):
		return
	controller = main.get_meta("controller")
	session = controller.session
	ai_before = await LocalModelFixture.configure(self)
	if not check(not ai_before.is_empty(), "execution controls use the existing AIChat API settings with an isolated local fixture"):
		return
	await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await prepare_launch():
		return
	var entry_id: String = controller.conversation().execution.entry
	var run_id := worker("pause-wait")
	var progress := await run_state(run_id, "")
	controller.navigate("issues", str(progress.issue))
	await wait_until(func(): return not controller.issues.loading)
	if not await issue_action("NativeIssueRun_pause"):
		return
	var release := FileAccess.open(OS.get_environment("TX_EXECUTION_WORKERS").path_join("pause-go"), FileAccess.WRITE)
	release.close()
	progress = await run_state(run_id, "paused")
	if not check(not progress.is_empty() and not str(progress.get("candidate", "")).is_empty(), "pause reaches a persisted boundary after the current producer finishes"):
		return
	if not await issue_action("NativeIssueRun_resume"):
		return
	controller.navigate("home")
	await controller.execution.select(entry_id)
	for attempt in 150:
		if controller.execution.settled():
			break
		await create_timer(0.1).timeout
		await controller.execution.refresh()
	if not check(controller.execution.settled() and controller.execution.observation.failures.is_empty(), "resumed execution completes after switching away from its native views"):
		return
	var request: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/requirements", {"request_id": controller.new_id(), "title": "Revoke", "outcome": "Output", "scope": "Text", "acceptance": "output must equal deterministic accepted output"})
	var started: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/entry/execute", {"requirement": request.data.id, "call_id": controller.new_id(), "scopes": ["text"], "model": "installed"})
	if not check(started.status == 200 and await wait_until(func(): return not worker("revoke-wait").is_empty(), 20.0), "cancellation fixture has a physically running installed producer"):
		return
	run_id = worker("revoke-wait")
	progress = await run_state(run_id, "")
	controller.navigate("issues", str(progress.issue))
	await wait_until(func(): return not controller.issues.loading)
	if not await issue_action("NativeIssueRun_cancel"):
		return
	progress = await run_state(run_id, "cancelled")
	if not check(not progress.is_empty(), "native cancellation reaches the workflow's acknowledged terminal state"):
		return
	if not await target_confirmation():
		return
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
