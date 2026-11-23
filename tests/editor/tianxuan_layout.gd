extends SceneTree
## The compiled controls must fit their allocated viewport, including narrow docks.

var checks: Array[String] = []
var failures: Array[Dictionary] = []


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
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
