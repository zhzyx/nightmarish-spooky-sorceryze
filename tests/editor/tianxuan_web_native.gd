extends SceneTree
## Cross-client test against the real service and an unchanged Web client.

var checks: Array[String] = []
var state_path := OS.get_environment("TX_STATE")
var command_path := OS.get_environment("TX_COMMAND")


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native/Web collaboration: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func wait_until(predicate: Callable, seconds := 60.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < end:
		if predicate.call():
			return true
		await create_timer(0.05).timeout
	return false


func command(stage: String) -> bool:
	if not FileAccess.file_exists(command_path):
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(command_path))
	return parsed is Dictionary and parsed.get("stage") == stage


func publish(stage: String, model: Node) -> void:
	var file := FileAccess.open(state_path + ".tmp", FileAccess.WRITE)
	file.store_string(JSON.stringify({"stage": stage, "document": model.active_id, "version": model.document.get("version", 0), "checks": checks}))
	file.close()
	DirAccess.rename_absolute(state_path + ".tmp", state_path)


func run() -> void:
	await process_frame
	await process_frame
	var base := EditorInterface.get_base_control()
	var main = base.find_child("TianxuanWorkspaceView", true, false)
	var controller = main.get_meta("controller")
	var model = controller.documents
	if not check(await controller.session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace"), "native editor authenticates independently of the browser"):
		return
	base.find_child("ExpandTianxuan", true, false).pressed.emit()
	main._navigate("documents", "")
	var view = main._page_instances.documents
	await model.open("")
	view._title.text = "跨端协作文档"
	view._title.text_changed.emit(view._title.text)
	view._body.text = "原生段落 A\n\n共同段落 B"
	view._save.pressed.emit()
	if not check(await wait_until(func(): return not model.saving and not model.active_id.is_empty() and model.draft().is_empty()), "native controls create the shared document through the actual service"):
		return
	publish("native_saved", model)
	if not check(await wait_until(func(): return command("web_saved")), "browser completed its first real edit"):
		return
	if not check(await wait_until(func(): return "Web 修改 B" in str(model.document.get("body_md", "")) and model.collaborators.size() == 2), "native document receives the Web edit and two distinct collaborator identities"):
		return
	if not check(model._room != null and model._room.get_ready_state() == WebSocketPeer.STATE_OPEN, "native collaboration uses an authenticated live WebSocket"):
		return
	publish("web_observed", model)
	if not check(await wait_until(func(): return command("native_offline")), "native TCP transport outage has been activated"):
		return
	view._body.text = "原生离线修改 A\n\nWeb 修改 B"
	view._save.pressed.emit()
	if not check(await wait_until(func(): return not model.saving and model.draft().has("submission") and not controller.session.online), "disconnected native save retains the exact submission and draft"):
		return
	var original: Dictionary = model.draft().submission.duplicate(true)
	publish("native_offline_retained", model)
	if not check(await wait_until(func(): return command("native_online")), "native TCP transport restored"):
		return
	if not check(await wait_until(func(): return model.draft().is_empty() and model.document.get("body_md") == original.body_md), "native reconnect synchronizes the retained draft without another save action"):
		return
	publish("native_resynced", model)
	if not check(await wait_until(func(): return command("web_offline_saved")), "browser recovered and saved its own offline draft"):
		return
	if not check(await wait_until(func(): return "Web 离线修改 B" in str(model.document.get("body_md", ""))), "native view receives the browser's recovered offline changes"):
		return
	publish("web_resynced", model)
	if not check(await wait_until(func(): return command("web_conflicting_draft")), "browser has an unsubmitted overlapping edit"):
		return
	view._body.text = "原生最终修改 A\n\nWeb 离线修改 B"
	view._save.pressed.emit()
	if not check(await wait_until(func(): return not model.saving and model.draft().is_empty() and "原生最终修改 A" in str(model.document.get("body_md", ""))), "native controls save their independently edited version"):
		return
	publish("native_conflicting_saved", model)
	if not check(await wait_until(func(): return command("web_resolved")), "browser explicitly resolved the overlapping edit"):
		return
	if not check(await wait_until(func(): return model.document.get("body_md") == "双方确认的最终内容 A\n\nWeb 离线修改 B"), "native view receives the explicitly resolved cross-client document"):
		return
	publish("complete", model)
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
