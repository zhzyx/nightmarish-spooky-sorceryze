extends SceneTree
## The compiled controls must fit their allocated viewport, including narrow docks.

var checks: Array[String] = []
var failures: Array[Dictionary] = []
var geometry_samples: Array[Dictionary] = []
var design_geometry_samples: Array[Dictionary] = []
const LocalModelFixture = preload("res://local_model_fixture.gd")


func _initialize() -> void:
	run.call_deferred()


func settle() -> void:
	for _index in 8:
		await process_frame


func horizontal_overflow(node: Node, width: float, found: Array) -> void:
	if node is Window or (node is CanvasItem and not node.is_visible_in_tree()):
		return
	# Explicit horizontal scrollers (for example the kanban board) own overflow.
	if node is ScrollContainer and node.horizontal_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED:
		return
	if node is Control and (node is BaseButton or node is LineEdit or node is TextEdit or node is Tree or node is Label):
		var rect: Rect2 = node.get_global_rect()
		if rect.position.x < -1 or rect.end.x > width + 1:
			found.append({"node": str(node.get_path()), "left": rect.position.x, "right": rect.end.x})
	for child in node.get_children():
		horizontal_overflow(child, width, found)


func contrast(a: Color, b: Color) -> float:
	var left := a.srgb_to_linear().get_luminance()
	var right := b.srgb_to_linear().get_luminance()
	return (maxf(left, right) + 0.05) / (minf(left, right) + 0.05)


func check(condition: bool, description: String) -> bool:
	if condition:
		checks.append(description)
	else:
		failures.append({"home_interaction": description})
	return condition


func wait_until(predicate: Callable, seconds := 8.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	return predicate.call()


func append_history(controller: Node, key: String, content: String) -> void:
	var route := "/api/v1/workspace/conversations/" + key
	var current: Dictionary = await controller.session.api_request(HTTPClient.METHOD_GET, route)
	var response: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, route + "/local-turns", {"id": controller.new_id(), "expected_version": current.data.version, "content": content, "answer": "已保存的历史回复。\n\n".repeat(8), "model": "layout-history"})
	check(response.status == 200, "Layout history fixture saves an answered turn through the existing local sync API")
	await controller.refresh_conversation(key)
	await settle()


func home_interactions(main: Control, viewport: SubViewport) -> void:
	var controller: Node = main.get_meta("controller")
	var configured: Dictionary = await LocalModelFixture.configure(self)
	if not check(not configured.is_empty(), "Home interactions configure the existing API controls with private fixture credentials"):
		return
	var key: String = controller.new_id()
	var old_id: String = controller.new_id()
	var route := "/api/v1/workspace/conversations/" + key
	await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/workspace/conversations", {"id": key})
	# Seed the old unanswered server history that the user could not continue.
	# This is the isolated, unconfigured test service, never an external model.
	var seeded: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, route + "/turns", {"id": old_id, "expected_version": 0, "content": "给我生成一头猪的写实模型"})
	if not check(seeded.status == 200 and seeded.data.turns[0].state == "unanswered", "Recovery fixture contains an actual preserved unanswered server turn"):
		return
	var original: Dictionary = seeded.data.turns[0].duplicate(true)
	await controller.select_conversation(key)
	var view: Control = main.get_script().new()
	for entry in ["controller", "scripts"]:
		view.set_meta(entry, main.get_meta(entry))
	viewport.size = Vector2i(1000, 760)
	viewport.add_child(view)
	view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	view._navigate("home", "")
	await settle()
	var home: Control = view._page_instances.home
	home.composer.text = "保留这段尚未发送的中文草稿。"
	await settle()
	var draft: String = home.composer.text
	var resume: Button = home.find_child("ResumeTianxuanMessage_" + old_id, true, false)
	if not check(resume != null and not resume.disabled and resume.is_visible_in_tree(), "An unanswered old turn exposes an enabled native Continue action"):
		view.queue_free()
		return
	resume.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("turns", []).size() == 2 and controller.local_chat.syncing.is_empty()), "Native Continue receives and synchronizes the real local HTTP reply"):
		view.queue_free()
		return
	await settle()
	var turns: Array = controller.conversation().turns
	check(turns[0] == original and turns[1].state == "answered" and str(turns[1].answer).contains("本机 API 夹具回答"), "Continuing appends the local answer without replacing the original failed request")
	check(home.composer.text == draft and controller.load_draft(controller.chat_draft_key(key)).get("text") == draft, "Native Continue preserves the visible and durable unsent draft")
	resume = home.find_child("ResumeTianxuanMessage_" + old_id, true, false)
	check(resume.disabled and not resume.tooltip_text.is_empty(), "A continued request is disabled with an explicit explanation")
	var next: Button = home.find_child("TianxuanNextRequirement", true, false)
	check(next != null and next.text == "整理为需求", "The completed reply offers a visible requirement-and-execution next step")
	next.pressed.emit()
	check(view._current_page == "design", "The reply action opens the existing native requirement workflow")
	view._navigate("home", "")
	for index in 5:
		await append_history(controller, key, "用于阅读位置回归的历史消息 %d" % index)
	var bar: VScrollBar = home.scroll.get_v_scroll_bar()
	home.scroll.scroll_vertical = int((bar.max_value - bar.page) * 0.25)
	var reading: int = home.scroll.scroll_vertical
	await append_history(controller, key, "在底部追加的新消息，不应打断上方阅读")
	check(abs(home.scroll.scroll_vertical - reading) <= 1, "Refreshing appended history preserves an earlier reading position")
	home.scroll.scroll_vertical = int(bar.max_value)
	await append_history(controller, key, "停留底部时继续跟随的新消息")
	check(bar.max_value - bar.page - bar.value <= 2, "Readers already at the bottom follow newly appended messages")
	home.composer.text = "LAYOUT_DELAYED_REPLY 原生进度和停止回归"
	home.send.pressed.emit()
	if check(await wait_until(func(): return home._progress_row.visible and controller.local_chat.busy()), "An active real local request exposes progress and cancellation"):
		await settle()
		var first_card: int = home.history.get_child(0).get_instance_id()
		var initial_progress: String = home._progress_status.text
		home.scroll.scroll_vertical = reading
		await create_timer(1.2).timeout
		check(controller.local_chat.progress().elapsed_seconds >= 1 and home._progress_status.text != initial_progress and not home.stop.disabled, "Waiting progress displays real elapsed time and an enabled Stop action")
		check(home.history.get_child(0).get_instance_id() == first_card and abs(home.scroll.scroll_vertical - reading) <= 1, "The elapsed-time timer does not rebuild history or move the reading position")
		home.stop.pressed.emit()
		await wait_until(func(): return not controller.local_chat.busy())
		check(not home._progress_row.visible and home._progress_timer.is_stopped(), "Stopping clears the active progress timer and keeps the request readable")
		await create_timer(2.0).timeout
		check(controller.conversation().turns.back().state == "unanswered", "A late cancelled HTTP response does not replace the stopped turn")
	home._context_panel.hide()
	EditorInterface.get_selection().clear()
	home._editor_tools.get_popup().id_pressed.emit(0)
	check(home._context_panel.visible and home._editor_status.is_visible_in_tree() and not home._editor_status.text.is_empty(), "Attaching without a selected node shows a visible explanation")
	EditorInterface.open_scene_from_path("res://fixture.tscn")
	await wait_until(func(): return EditorInterface.get_edited_scene_root() != null)
	var scene := EditorInterface.get_edited_scene_root()
	EditorInterface.get_selection().add_node(scene)
	controller.editor_module = ""
	home._editor_tools.get_popup().id_pressed.emit(0)
	home._context_panel.hide()
	home.composer.text = "检查引用模块"
	home.send.pressed.emit()
	check(home._context_panel.visible and home._editor_status.is_visible_in_tree() and not controller.local_chat.busy(), "Sending an attachment without a module reveals the validation failure")
	controller.editor_module = OS.get_environment("TX_MODULE")
	scene.position += Vector2(1, 0)
	home._context_panel.hide()
	home.send.pressed.emit()
	check(home._context_panel.visible and home._editor_status.is_visible_in_tree() and not controller.local_chat.busy(), "A changed editor reference blocks sending with a visible explanation")
	for index in range(controller.editor_context.attachments().size() - 1, -1, -1):
		controller.editor_context.remove(index)
	controller.clear_draft(controller.chat_draft_key(key))
	check(LocalModelFixture.unchanged(configured), "Recovery, progress and cancellation leave ordinary AIChat conversation and draft unchanged")
	await controller.select_conversation("")
	view.queue_free()
	await settle()


func home_vertical_layout(main: Control, viewport: SubViewport) -> void:
	var theme_script: Script = main.get_meta("scripts").theme
	for scale in [1.0, 1.5, 2.0]:
		for mode in [{"compact": false, "width": 960}, {"compact": false, "width": 480}, {"compact": true, "width": 340}]:
			var view: Control = main.get_script().new()
			for key in ["controller", "scripts"]:
				view.set_meta(key, main.get_meta(key))
			view.set_meta("compact", mode.compact)
			viewport.add_child(view)
			# Recreate the home page at each real font/style scale. Merely testing
			# palette token values would miss the vertical allocation regression.
			if view._page_instances.has("home"):
				var old: Control = view._page_instances.home
				old.get_parent().remove_child(old)
				old.queue_free()
				view._page_instances.erase("home")
			view.ui_scale = scale
			view.custom_minimum_size = Vector2(280 if mode.compact else 430, 240) * scale
			view.theme = theme_script.build(EditorInterface.get_editor_theme(), scale, true)
			view._navigate("home", "")
			for height in [420, 560, 760]:
				viewport.size = Vector2i(roundi(mode.width * scale), roundi(height * scale))
				view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
				view._responsive()
				await settle()
				var home: Control = view._page_instances.home
				var history: Control = home.find_child("TianxuanConversationHistory", true, false)
				var composer: Control = home.find_child("TianxuanComposer", true, false)
				var send: Control = home.find_child("SendTianxuanMessage", true, false)
				var sample := {"compact": mode.compact, "scale": scale, "viewport": viewport.size, "home": home.size, "history_height": history.size.y, "composer_height": composer.size.y, "send_bottom": send.get_global_rect().end.y}
				geometry_samples.append(sample)
				if history.size.y < home.size.y * 0.4 or history.size.y < composer.size.y * 2 or send.get_global_rect().end.y > viewport.size.y + 1 or view.size.y > viewport.size.y + 1:
					failures.append({"home_vertical_allocation": sample})
				else:
					checks.append("Conversation history remains primary at %d×%d logical pixels, %.1fx (%s)" % [mode.width, height, scale, "dock" if mode.compact else "workspace"])
			view.queue_free()
			await settle()


func design_flow_geometry(main: Control, viewport: SubViewport) -> void:
	var controller: Node = main.get_meta("controller")
	var key: String = controller.new_id()
	var route := "/api/v1/workspace/conversations/" + key
	await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/workspace/conversations", {"id": key})
	var turn: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, route + "/local-turns", {"id": controller.new_id(), "expected_version": 0, "content": "生成猪模型的需求", "answer": "先确认模型规格，再逐步完善策划与设计。", "model": "isolated-layout-history"})
	if not check(turn.status == 200, "Design layout fixture stores a completed discussion without calling a provider"):
		return
	var saved: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, route + "/design/direction/drafts", {"expected_version": turn.data.version, "body": "已确认的方向：保留猪模型的体型、材质和可检验规格。\n\n".repeat(30)})
	if not check(saved.status == 200, "Design layout fixture saves a substantive direction revision"):
		return
	var confirmed: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, route + "/design/direction/confirm", {"expected_version": saved.data.version, "revision": saved.data.current.direction})
	if not check(confirmed.status == 200 and confirmed.data.get("requirement_id") == null and confirmed.data.get("execution") == null, "Direction-only fixture preserves the remaining design and production gates"):
		return
	await controller.select_conversation(key)
	var theme_script: Script = main.get_meta("scripts").theme
	for scale in [1.0, 1.5, 2.0]:
		for mode in [{"compact": false, "width": 960}, {"compact": false, "width": 480}, {"compact": true, "width": 340}]:
			var view: Control = main.get_script().new()
			for name in ["controller", "scripts"]:
				view.set_meta(name, main.get_meta(name))
			view.set_meta("compact", mode.compact)
			viewport.add_child(view)
			view.ui_scale = scale
			view.custom_minimum_size = Vector2(280 if mode.compact else 430, 240) * scale
			view.theme = theme_script.build(EditorInterface.get_editor_theme(), scale, true)
			view._navigate("design", "")
			await wait_until(func(): return not controller.chat_busy())
			var design: Control = view._page_instances.design
			design._stage.select(0)
			design._stage.item_selected.emit(0)
			var progress: Label = design.find_child("TianxuanDesignProgress", true, false)
			var next: Button = design.find_child("TianxuanDesignNext", true, false)
			var hint: Label = design.find_child("TianxuanDesignNextHint", true, false)
			var execution: Control = design.find_child("TianxuanRequirementExecution", true, false)
			var launch: Button = design.find_child("LaunchTianxuanRequirement", true, false)
			var reason: Label = design.find_child("TianxuanExecutionStatus", true, false)
			if not check(progress != null and next != null and hint != null and execution != null and launch != null and reason != null, "Direction-confirmed layout retains a stage summary, next action and explained execution placeholder"):
				failures.append({"direction_confirmed_regression": {"direction_confirmed": controller.design_revision("direction").get("confirmed_at") != null, "selected_stage": design._stage.selected, "execution_visible": design._execution.visible, "publish_disabled": design._publish.disabled, "next_exists": next != null}})
				view.queue_free()
				await controller.select_conversation("")
				return
			for height in [460, 680]:
				viewport.size = Vector2i(roundi(mode.width * scale), roundi(height * scale))
				view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
				view._responsive()
				await settle()
				var hint_scroll: Node = hint.get_parent()
				while hint_scroll != null and not hint_scroll is ScrollContainer:
					hint_scroll = hint_scroll.get_parent()
				if hint_scroll is ScrollContainer:
					hint_scroll.ensure_control_visible(hint)
					await settle()
				var hint_area: Rect2 = hint_scroll.get_global_rect() if hint_scroll is ScrollContainer else view.get_global_rect()
				var hint_reachable := hint.is_visible_in_tree() and hint.get_global_rect().intersects(hint_area)
				var scroll: Node = launch.get_parent()
				while scroll != null and not scroll is ScrollContainer:
					scroll = scroll.get_parent()
				if scroll is ScrollContainer:
					scroll.ensure_control_visible(launch)
					await settle()
				var overflow := []
				horizontal_overflow(view, viewport.size.x, overflow)
				var next_rect: Rect2 = next.get_global_rect()
				var summary_rect: Rect2 = progress.get_global_rect()
				var launch_rect: Rect2 = launch.get_global_rect()
				var reason_rect: Rect2 = reason.get_global_rect()
				var scroll_rect: Rect2 = scroll.get_global_rect() if scroll is ScrollContainer else design.get_global_rect()
				var sample := {"compact": mode.compact, "scale": scale, "viewport": viewport.size, "next": next_rect, "summary": summary_rect, "hint_reachable": hint_reachable, "launch": launch_rect, "reason": reason_rect, "scroll": scroll_rect, "page_height": view.size.y}
				design_geometry_samples.append(sample)
				var fits := next_rect.position.y >= 0 and next_rect.end.y <= viewport.size.y + 1 and summary_rect.end.y <= viewport.size.y + 1 and view.size.y <= viewport.size.y + 1 and overflow.is_empty()
				var reachable := hint_reachable and launch_rect.position.y >= scroll_rect.position.y - 1 and launch_rect.end.y <= scroll_rect.end.y + 1 and reason_rect.intersects(scroll_rect)
				var explains: bool = execution.is_visible_in_tree() and launch.is_visible_in_tree() and launch.disabled and next.text.contains("策划") and not hint.text.is_empty() and not reason.text.is_empty() and not design._history_body.is_visible_in_tree()
				if not fits or not reachable or not explains:
					failures.append({"design_flow_geometry": sample, "fits": fits, "reachable": reachable, "explains": explains, "overflow": overflow.slice(0, 1)})
				else:
					checks.append("Direction-confirmed design keeps Next visible and its blocked launch reachable at %d×%d, %.1fx (%s)" % [mode.width, height, scale, "dock" if mode.compact else "workspace"])
			view.queue_free()
			await settle()
	await controller.select_conversation("")
	await settle()


func run() -> void:
	await settle()
	var main = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
	var controller = main.get_meta("controller")
	var theme_script = main.get_meta("scripts").theme
	for dark in [true, false]:
		var palette: Dictionary = theme_script.palette(dark)
		for pair in [[palette.text, palette.canvas], [palette.muted, palette.canvas], [palette.text, palette.surface], [Color.WHITE, palette.accent_fill]]:
			if contrast(pair[0], pair[1]) < 4.5:
				failures.append({"theme": "dark" if dark else "light", "contrast": contrast(pair[0], pair[1])})
			else:
				checks.append("%s text contrast meets 4.5:1" % ("dark" if dark else "light"))
		for scale in [1.0, 1.5, 2.0]:
			var theme: Theme = theme_script.build(EditorInterface.get_editor_theme(), scale, dark)
			if theme.default_font_size != roundi(14 * scale) or theme.get_stylebox("focus", "Button").border_width_left != roundi(2 * scale):
				failures.append({"theme_scale": scale})
			else:
				checks.append("%s theme scales text and focus at %.1fx" % ["dark" if dark else "light", scale])
	if not await controller.session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace"):
		push_error("Layout fixture authentication failed")
		quit(1)
		return
	var global_locale := TranslationServer.get_locale()
	main._language_choice.select(1)
	main._language_choice.item_selected.emit(1)
	await controller.documents.open("")
	controller.documents.update_draft("工单", "# 工作台\n\n账号与权限")
	await controller.documents.save()
	if controller.documents.document.get("lang") != "en":
		failures.append({"new_document_language": controller.documents.document.get("lang")})
	else:
		checks.append("New native documents persist the selected content language through the actual service")
	await controller.documents.refresh_list()
	main._navigate("documents", "")
	await settle()
	var document_view = main._page_instances.documents
	controller.documents.update_draft("工单", "# 工作台\n\n账号与权限\n本机草稿")
	await settle()
	document_view._body.select(0, 2, 0, 4)
	var draft: Dictionary = controller.documents.draft().duplicate(true)
	var scope: String = controller.session.scope_key()
	for language in ["zh", "en", "zh"]:
		main._language_choice.item_selected.emit(0 if language == "zh" else 1)
		await settle()
		var sidebar = EditorInterface.get_base_control().find_child("TianxuanSidebarView", true, false)
		if controller.language != language or sidebar._language_choice.selected != (0 if language == "zh" else 1) or TranslationServer.get_locale() != global_locale:
			failures.append({"locale_isolation": language})
		elif document_view._body.get_selected_text() != "工作" or controller.documents.draft() != draft or controller.session.scope_key() != scope or main._current_page != "documents":
			failures.append({"locale_state_preservation": language})
		else:
			checks.append("Switching to %s synchronizes both views and retains identity, page, draft, selection and editor locale" % language)
		var navigation: Button = main.find_child("TianxuanPage_issues", true, false)
		if navigation.atr(navigation.text) != ("Issues" if language == "en" else "工单") or document_view._preview.get_parsed_text() != "工单\n\n工作台\n\n账号与权限\n本机草稿":
			failures.append({"translated_navigation_or_authored_body": language, "body": document_view._preview.get_parsed_text()})
		else:
			checks.append("%s navigation is translated while authored Markdown remains unchanged" % language)
		if document_view._picker.get_selected_metadata() != controller.documents.active_id or document_view._picker.get_item_auto_translate_mode(document_view._picker.selected) != Node.AUTO_TRANSLATE_MODE_DISABLED:
			failures.append({"authored_title_translation": language})
		else:
			checks.append("Authored document title stays literal in %s" % language)
	var viewport := SubViewport.new()
	viewport.size = Vector2i(1200, 900)
	root.add_child(viewport)
	await home_interactions(main, viewport)
	await home_vertical_layout(main, viewport)
	await design_flow_geometry(main, viewport)
	for language in ["zh", "en"]:
		controller.set_language(language, false)
		for compact in [false, true]:
			var view: Control = main.get_script().new()
			for key in ["controller", "scripts"]:
				view.set_meta(key, main.get_meta(key))
			view.set_meta("compact", compact)
			viewport.add_child(view)
			view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
			var widths := [1200, 760, 480] if not compact else [420, 320]
			for width in widths:
				viewport.size = Vector2i(width, 900)
				for page in ["home", "documents", "design", "requirements", "issues", "repos", "repository_collaboration", "game_config", "runs", "execution", "search", "migration", "accounts", "account"]:
					view._navigate(page, "")
					view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
					await settle()
					if not view._page_instances[page].is_visible_in_tree():
						failures.append({"page_not_visible": page, "language": language})
					var overflow := []
					horizontal_overflow(view, width, overflow)
					if not overflow.is_empty():
						failures.append({"compact": compact, "width": width, "page": page, "language": language, "overflow_count": overflow.size(), "first_overflow": overflow[0]})
					if view.size.x > width + 1:
						failures.append({"compact": compact, "width": width, "page": page, "language": language, "actual": view.size.x, "minimum": view.get_combined_minimum_size().x})
					else:
						checks.append("%s at %d px (%s) fits the viewport" % [page, width, "dock" if compact else "workspace"])
			view.queue_free()
			await settle()
	viewport.queue_free()
	await settle()
	if not failures.is_empty():
		print(JSON.stringify({"layout_failures": failures}))
		quit(1)
		return
	print(JSON.stringify({"passed": true, "checks": checks, "conversation_layout": geometry_samples, "design_layout": design_geometry_samples}))
	quit(0)
