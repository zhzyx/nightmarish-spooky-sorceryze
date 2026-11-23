extends SceneTree
## Controlled response interleavings against the real service and compiled native views.

var checks: Array[String] = []


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native concurrency: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func wait_until(predicate: Callable) -> bool:
	for _attempt in 400:
		if predicate.call():
			return true
		await create_timer(0.025).timeout
	return false


func run() -> void:
	await process_frame
	await process_frame
	var base := EditorInterface.get_base_control()
	var main = base.find_child("TianxuanWorkspaceView", true, false)
	var sidebar = base.find_child("TianxuanSidebarView", true, false)
	var controller = main.get_meta("controller")
	var session = controller.session
	var model = controller.documents
	if not check(await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace"), "authenticate against the real isolated service"):
		return
	base.find_child("ExpandTianxuan", true, false).pressed.emit()
	main._navigate("documents", "")
	var view = main._page_instances.documents
	await model.open("")
	view._tabs.current_tab = 1
	view._title.text = "Initial title"
	view._title.text_changed.emit(view._title.text)
	view._body.text = "Original A\n\nOriginal B"
	await model.save()
	if not check(not model.active_id.is_empty() and model.document.version == 1, "create the shared document"):
		return
	# Disable only unsolicited live refresh for deterministic two-request interleavings.
	model.set_process(false)
	model._close_room()
	view._body.text = "Original A\n\nLocal B"
	var response: Dictionary = await session.api_request(HTTPClient.METHOD_PATCH, model.route(), {"body_md": "Remote A\n\nOriginal B", "expected_version": 1})
	if not check(response.status == 200, "remote writer advances a disjoint paragraph"):
		return
	view._body.grab_focus()
	view._body.select(2, 0, 2, 5)
	var shortcut := InputEventKey.new()
	shortcut.keycode = KEY_S
	shortcut.pressed = true
	shortcut.ctrl_pressed = true
	shortcut.meta_pressed = true
	view._body.gui_input.emit(shortcut)
	if not check(await wait_until(func(): return not model.saving and model.draft().get("base_version") == 2), "Ctrl/Cmd+S produces the real server merge preview"):
		return
	if not check(view._body.has_focus() and view._body.text == "Remote A\n\nLocal B" and view._body.get_selected_text() == "Local", "focused editor adopts the merged baseline and preserves the local selection"):
		return
	view._body.deselect()
	view._body.set_caret_line(2)
	view._body.set_caret_column(7)
	view._body.insert_text_at_caret(" continued")
	await process_frame
	view._body.gui_input.emit(shortcut)
	if not check(await wait_until(func(): return not model.saving and model.draft().is_empty()), "continue typing and save after merge"):
		return
	response = await session.api_request(HTTPClient.METHOD_GET, model.route())
	if not check(response.data.body_md == "Remote A\n\nLocal B continued", "continued input preserves the acknowledged remote paragraph"):
		return

	# Advance the title between GET head and merge preview, not before both reads.
	view._body.text = "Remote A\n\nLocal C"
	response = await session.api_request(HTTPClient.METHOD_PATCH, model.route(), {"body_md": "Remote D\n\nLocal B continued", "expected_version": 3})
	if not check(response.status == 200, "prepare a second disjoint remote revision"):
		return
	await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native-test/title-race/" + model.active_id, {})
	await model.save()
	if not check(model.draft().base_version == 3 and not model.draft().has("submission"), "a title changed between reads cannot be adopted with a mismatched newer body baseline"):
		return
	await model.save()
	if not check(model.draft().title == "Remote title C" and model.draft().base_version == 5, "retry compares title and body from one consistent revision"):
		return
	await model.save()
	response = await session.api_request(HTTPClient.METHOD_GET, model.route())
	if not check(response.data.title == "Remote title C" and response.data.body_md == "Remote D\n\nLocal C", "saving the reconciled draft preserves both concurrent remote fields"):
		return

	main.find_child("OpenTianxuanSidebar", true, false).pressed.emit()
	sidebar._page_picker.item_selected.emit(1)
	var side_view = sidebar._page_instances.documents
	view._tabs.current_tab = 3
	view._comment.text = "Comment A"
	view._post.pressed.emit()
	await create_timer(0.1).timeout
	side_view._comment.text = "Comment B entered while A is in flight"
	if not check(await wait_until(func(): return not view._post.disabled and not controller.busy("document-action")), "delayed first comment acknowledgement arrives"):
		return
	if not check(view._comment.text == side_view._comment.text and controller.load_draft("comment:" + model.active_id).text == "Comment B entered while A is in flight", "A acknowledgement preserves B entered in the other native view"):
		return
	response = await session.api_request(HTTPClient.METHOD_GET, model.route() + "/comments")
	if not check(response.data.comments.size() == 1 and response.data.comments[0].body == "Comment A", "only the submitted comment was written"):
		return
	view._post.pressed.emit()
	if not check(await wait_until(func(): return not view._post.disabled and view._comment.text.is_empty() and side_view._comment.text.is_empty()), "acknowledging unchanged B clears the exact shared comment draft in both views"):
		return

	main._navigate("game_config", "")
	var config = controller.game_config
	var config_view = main._page_instances.game_config
	response = await session.api_request(HTTPClient.METHOD_POST, config.ROOT, {"title": "Existing configuration", "features": []})
	if not check(response.status == 201, "create an existing versioned configuration"):
		return
	config.open(response.data.id)
	if not check(config.loading and not config.editable() and not config_view._title.editable, "initial slow read keeps existing configuration controls read-only until a baseline exists"):
		return
	config_view._title.text = "Attempt before baseline"
	config_view._title.text_changed.emit(config_view._title.text)
	config_view._title.focus_exited.emit()
	if not check(config.draft().is_empty() and not config.saving, "early edit and autosave cannot produce an empty-base draft or submission"):
		return
	if not check(await wait_until(func(): return not config.loading and config.editable()), "acknowledged baseline enables normal editing"):
		return
	config.field("", "", "title", "Retained offline draft")
	config.open(config.selected)
	if not check(config.loading and config.editable() and config.draft().base.version == 1, "a cached draft with a valid baseline remains editable during refresh"):
		return
	await wait_until(func(): return not config.loading)
	await config.save()
	if not check(config.project.title == "Retained offline draft" and config.project.version == 2, "valid draft saves with its actual expected version"):
		return
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
