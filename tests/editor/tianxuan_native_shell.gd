extends SceneTree

var checks: Array[String] = []
const LocalModelFixture = preload("res://local_model_fixture.gd")


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native Tianxuan shell: " + description)
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
	root.size = Vector2i(1600, 1000)
	await process_frame
	await process_frame
	var base := EditorInterface.get_base_control()
	var main = base.find_child("TianxuanWorkspaceView", true, false)
	var sidebar = base.find_child("TianxuanSidebarView", true, false)
	if not check(main != null and sidebar != null, "main-screen and dockable native Views are installed"):
		return
	if not check(base.find_children("*", "WebPlatformDock", true, false).is_empty(), "Tianxuan entry creates no WebView container"):
		return
	var controller = main.get_meta("controller")
	var session = controller.session
	if not check(sidebar.get_meta("controller") == controller and session.get_parent() == base, "both Views share an editor-owned controller and transport"):
		return
	var legacy = base.find_child("WorkbenchBusinessSession", true, false)
	if not check(legacy.get_meta("session_controller") == session, "existing native workbench shares the same identity"):
		return
	var ai_before: Dictionary = await LocalModelFixture.configure(self)
	if not check(not ai_before.is_empty(), "existing AIChat API controls use only the isolated local model fixture"):
		return
	sidebar.find_child("ExpandTianxuan", true, false).pressed.emit()
	var submit: Button = main.find_child("AuthenticateTianxuan", true, false)
	if not check(await wait_until(func(): return main._auth_mode == "accounts" and not submit.disabled), "native login reads the real service configuration"):
		return
	main.find_child("TianxuanEmail", true, false).text = "first@example.invalid"
	main.find_child("TianxuanCredential", true, false).text = OS.get_environment("TX_PASSWORD")
	submit.pressed.emit()
	if not check(await wait_until(func(): return not session.get_identity().is_empty() and main._current_page == "home"), "native controls authenticate and open the workspace"):
		return
	sidebar.find_child("ExpandTianxuan", true, false).pressed.emit()
	await process_frame
	var composer: TextEdit = main.find_child("TianxuanComposer", true, false)
	if not check(composer != null and composer.is_visible_in_tree(), "native conversation composer is visible in main workspace"):
		return
	composer.text = "验证原生天璇消息与 Web 共用会话"
	var send: Button = main.find_child("SendTianxuanMessage", true, false)
	if not check(not send.disabled, "editing the native composer enables sending"):
		return
	send.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("turns", []).size() == 1), "native message is persisted by the existing conversation API"):
		return
	var conversation: Dictionary = controller.conversation()
	if not check(conversation.turns[0].state == "answered" and conversation.turns[0].answer == "本机 API 夹具回答：已收到原生天璇消息。" and conversation.turns[0].reply_source == "editor-local", "native conversation displays the actual local API reply"):
		print(JSON.stringify({"local_turn": conversation.turns[0], "model": controller.local_chat.configuration()}))
		return
	if not check(await wait_until(func(): return controller.local_chat.syncing.is_empty()), "completed local reply finishes business-service synchronization"):
		return
	var synchronized: Dictionary = await session.api_request(HTTPClient.METHOD_GET, controller.CONVERSATIONS + "/" + conversation.id)
	if not check(synchronized.status == 200 and synchronized.data.turns[0].answer == conversation.turns[0].answer and synchronized.data.turns[0].reply_source == "editor-local", "shared conversation API returns the exact completed local reply"):
		return
	if not check(LocalModelFixture.unchanged(ai_before), "local Tianxuan inference leaves ordinary AIChat conversation and draft unchanged"):
		return
	main.find_child("OpenTianxuanSidebar", true, false).pressed.emit()
	sidebar._page_picker.item_selected.emit(0)
	if not check(await wait_until(func(): return sidebar.is_visible_in_tree() and sidebar._current_page == "home"), "normal native action opens the compact sidebar"):
		return
	composer.text = "保留中文草稿，不发出新消息"
	var side_composer: TextEdit = sidebar.find_child("TianxuanComposer", true, false)
	if not check(side_composer.text == composer.text and sidebar.get_meta("controller").active_conversation == conversation.id, "both Views share the same active conversation and unsent draft"):
		return
	sidebar.get_parent().close()
	if not check(controller.load_draft(controller.chat_draft_key(conversation.id)).text == composer.text, "closing the sidebar preserves the exact unsent draft"):
		return
	if not check(main.theme.get_stylebox("panel", "TianxuanCard") is StyleBoxFlat and main.theme.get_font_size("font_size", "TianxuanTitle") > main.theme.default_font_size, "native visual surface and typography tokens are active"):
		return
	main.find_child("TianxuanPage_documents", true, false).pressed.emit()
	var document_title: LineEdit = main.find_child("TianxuanDocumentTitle", true, false)
	var document_body: TextEdit = main.find_child("TianxuanDocumentBody", true, false)
	if not check(document_title != null and document_body != null and main._current_page == "documents", "document navigation mounts the compiled native page"):
		return
	main._page_instances.documents._tabs.current_tab = 1
	document_title.text = "在编辑器内完成设计"
	document_body.text = "# 原生文档\n\n保留版本、共享和离线草稿。"
	main.find_child("SaveTianxuanDocument", true, false).pressed.emit()
	if not check(await wait_until(func(): return not controller.documents.active_id.is_empty() and not controller.documents.saving), "native document form saves through the real service"):
		return
	if not check(controller.documents.document.title == document_title.text and controller.documents.document.version == 1, "native document fields match the acknowledged server revision"):
		return
	main.find_child("OpenTianxuanSidebar", true, false).pressed.emit()
	sidebar._page_picker.item_selected.emit(1)
	if not check(sidebar.find_child("TianxuanDocumentBody", true, false).text == document_body.text, "main workspace and compact sidebar share the document revision"):
		return
	document_body.text += "\n\n尚未提交的中文草稿。"
	if not check(sidebar.find_child("TianxuanDocumentBody", true, false).text == document_body.text, "native document edits immediately share the durable draft"):
		return
	await process_frame
	await process_frame
	if not check(document_body.size.x > 250 and document_body.size.y >= 280 * main.ui_scale, "main document editor has usable native layout geometry"):
		return
	var document_view = main._page_instances.documents
	var before_format: String = document_body.text
	document_body.select(0, 2, 0, 6)
	document_view._format_buttons[0].pressed.emit()
	if not check(document_body.text.begins_with("# **原生文档**") and document_body.get_selected_text() == "原生文档" and document_view._edit_preview.get_parsed_text().contains("原生文档"), "native formatting preserves the selected text and updates the real preview"):
		return
	document_body.undo()
	await process_frame
	await process_frame
	if not check(document_body.text == before_format and controller.documents.draft().body_md == before_format, "native formatting is one undoable edit and undo updates the shared draft"):
		return
	document_view._editor_mode.select(2)
	document_view._editor_mode.item_selected.emit(2)
	if not check(not document_body.visible and document_view._edit_preview_scroll.visible, "native document view supports a dedicated preview mode"):
		return
	document_view._editor_mode.select(0)
	document_view._editor_mode.item_selected.emit(0)
	main.find_child("TianxuanPage_design", true, false).pressed.emit()
	var stage: OptionButton = main.find_child("TianxuanDesignStage", true, false)
	if not check(stage != null, "compiled native requirement stages are reachable from the workspace"):
		return
	if not check(await wait_until(func(): return not controller.chat_busy()), "native requirement page finishes refreshing before editing"):
		return
	var design_view: Control = main._page_instances.design
	var next_design: Button = design_view.find_child("TianxuanDesignNext", true, false)
	var design_progress: Label = design_view.find_child("TianxuanDesignProgress", true, false)
	var design_hint: Label = design_view.find_child("TianxuanDesignNextHint", true, false)
	var execution_placeholder: Control = design_view.find_child("TianxuanRequirementExecution", true, false)
	var launch: Button = design_view.find_child("LaunchTianxuanRequirement", true, false)
	var launch_status: Label = design_view.find_child("TianxuanExecutionStatus", true, false)
	if not check(next_design != null and design_progress != null and design_hint != null and execution_placeholder != null and launch != null and launch_status != null, "native requirement page exposes its stage summary, next action and execution prerequisites"):
		return
	if not check(next_design.text.contains("生成") and not next_design.disabled, "an empty current stage names draft generation as its explicit next action"):
		return
	next_design.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.load_draft(controller.design_key("direction")).get("body", "") == "本机 API 夹具设计建议：保持已有目标，补充实现与验收。"), "native requirement suggestion uses the same local API connection"):
		return
	if not check(LocalModelFixture.unchanged(ai_before), "local design suggestion also leaves ordinary AIChat conversation unchanged"):
		return
	for index in 3:
		if index > 0:
			var before_next: Dictionary = controller.conversation().duplicate(true)
			if not check(next_design.text.contains("继续") and not next_design.disabled, "confirming a stage exposes the next unfinished stage"):
				return
			next_design.pressed.emit()
			if not check(stage.selected == index and controller.conversation() == before_next, "cross-stage Next only selects the target; it does not generate, save or confirm"):
				return
		main.find_child("TianxuanDesignTitle", true, false).text = "原生完整需求"
		main.find_child("TianxuanDesignBody", true, false).text = "阶段 %d：明确目标、范围及实现行为。" % index
		main.find_child("TianxuanDesignAcceptance", true, false).text = "原生控件提交并回读服务端正式需求。"
		if not check(next_design.text.contains("保存") and not next_design.disabled, "the current stage's explicit Next action saves its edited revision"):
			return
		next_design.pressed.emit()
		var stage_name: String = ["direction", "plan", "design"][index]
		if not check(await wait_until(func(): return not controller.chat_busy() and not controller.design_revision(stage_name).is_empty()), "native design saves stage " + stage_name):
			return
		if index == 1:
			var returned_revision: int = controller.design_revision(stage_name).revision
			design_view._history_toggle.pressed.emit()
			design_view._return_reason.text = "隔离夹具：补充策划范围后重新确认。"
			design_view._return.pressed.emit()
			if not check(await wait_until(func(): return not controller.chat_busy() and controller.design_revision(stage_name).get("returned_at") != null), "native revision history returns the saved plan with an explicit reason"):
				return
			if not check(design_view._confirm_stage.disabled and design_view._next_action == "suggest" and not next_design.disabled and design_hint.text.contains("保存新修订"), "a returned revision explains that a new revision is required instead of offering confirmation"):
				return
			design_view._history_toggle.pressed.emit()
			design_view._body.text = "阶段 1：补充策划范围，明确目标、范围及实现行为。"
			if not check(design_view._next_action == "save" and not next_design.disabled, "editing a returned plan exposes an explicit save action for the replacement revision"):
				return
			next_design.pressed.emit()
			if not check(await wait_until(func(): return not controller.chat_busy() and controller.design_revision(stage_name).get("revision", 0) > returned_revision and controller.design_revision(stage_name).get("returned_at") == null), "saving a returned plan creates a new unreturned revision before confirmation"):
				return
		if not check(next_design.text.contains("确认") and controller.design_revision(stage_name).get("confirmed_at") == null, "saving a revision leaves confirmation as a separate explicit action"):
			return
		next_design.pressed.emit()
		if not check(await wait_until(func(): return not controller.chat_busy() and controller.design_revision(stage_name).get("confirmed_at") != null), "native design explicitly confirms stage " + stage_name):
			return
		if index == 0:
			var direction_spec: Dictionary = controller.local_production_specification()
			if not check(not direction_spec.has("error") and direction_spec.title == controller.conversation().title and direction_spec.acceptance == "", "confirmed direction handoff normalizes nullable fields and uses the conversation title"):
				print(JSON.stringify({"direction_specification": {"error": direction_spec.get("error"), "title": direction_spec.get("title"), "acceptance": direction_spec.get("acceptance")}, "conversation_title": controller.conversation().get("title"), "chat_busy": controller.chat_busy()}))
				return
			if not check(design_progress.is_visible_in_tree() and design_progress.text.contains("方向") and design_progress.text.contains("策划") and design_progress.text.contains("详细设计") and design_progress.text.contains("已确认") and not design_hint.text.is_empty(), "the direction-confirmed state explains all three stages and the concrete next action"):
				return
			if not check(execution_placeholder.is_visible_in_tree() and launch.is_visible_in_tree() and launch.disabled and not launch_status.text.is_empty() and design_view._publish.disabled, "direction confirmation keeps an explained execution placeholder visible while publishing and launch remain gated"):
				return
			if not check(not design_view._history_body.is_visible_in_tree(), "confirmed history is folded instead of duplicating the current stage content"):
				return
	stage.select(0)
	stage.item_selected.emit(0)
	design_view._body.text = "未保存的方向修订必须先处理"
	if not check(controller.local_production_specification().has("error"), "an earlier unsaved stage draft blocks local production handoff even after all saved revisions were confirmed"):
		return
	stage.select(2)
	stage.item_selected.emit(2)
	var before_draft_review: Dictionary = controller.conversation().duplicate(true)
	next_design.pressed.emit()
	if not check(stage.selected == 0 and design_view._body.text == "未保存的方向修订必须先处理" and design_view._publish.disabled and controller.conversation() == before_draft_review, "Next locates an earlier unsaved draft without silently saving it or publishing the requirement"):
		return
	design_view._discard.pressed.emit()
	if not check(next_design.text == "保存已确认需求" and not next_design.disabled, "only three confirmed stages with no unsaved drafts expose publishing as the next action"):
		return
	next_design.pressed.emit()
	if not check(await wait_until(func(): return controller.conversation().get("requirement_id") != null), "three confirmed native stages publish the real shared requirement"):
		return
	var requirement: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs/" + str(controller.conversation().requirement_id))
	if not check(requirement.status == 200 and requirement.data.title == "原生完整需求", "Web-compatible document API reads the requirement produced by native controls"):
		return
	if not check(next_design.text == "查看启动条件", "a saved requirement offers an explicit route to execution prerequisites"):
		return
	next_design.pressed.emit()
	if not check(await wait_until(func(): return not controller.busy("execution-capabilities") and controller.errors.has("execution-capabilities")), "the native requirement page receives the actual unconfigured execution-service result"):
		return
	if not check(execution_placeholder.is_visible_in_tree() and launch.is_visible_in_tree() and launch.disabled and not launch_status.text.is_empty() and controller.conversation().get("execution") == null and not design_view._confirmation.visible, "an unavailable service shows its blocking reason without opening confirmation or starting execution"):
		return
	main.find_child("TianxuanPage_home", true, false).pressed.emit()
	EditorInterface.open_scene_from_path("res://fixture.tscn")
	if not check(await wait_until(func(): return EditorInterface.get_edited_scene_root() != null), "editor integration opens the isolated project scene"):
		return
	var scene := EditorInterface.get_edited_scene_root()
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(scene)
	main.find_child("TianxuanEditorActions", true, false).get_popup().id_pressed.emit(0)
	if not check(controller.editor_context.attachments().size() == 1, "native editor action captures the selected scene node"):
		return
	var context: Dictionary = controller.editor_context.message_context(OS.get_environment("TX_MODULE"))
	if not check(context.valid and context.references.references[0].kind == "editor" and "Node2D" in context.text, "node reference freezes its identity, revision and readable snapshot"):
		return
	controller.editor_module = OS.get_environment("TX_MODULE")
	if not check(await wait_until(func(): return not controller.chat_busy()), "editor context waits for the current conversation revision"):
		return
	composer.text = "分析当前选中节点"
	send.pressed.emit()
	if not check(await wait_until(func(): return not controller.chat_busy() and controller.conversation().get("turns", []).size() == 2), "native message sends the explicitly selected editor context"):
		return
	var contextual_turn: Dictionary = controller.conversation().turns[1]
	if not check(contextual_turn.context_snapshot.references[0] == context.references.references[0] and "Node2D" in contextual_turn.content, "service persists the exact editor reference and its readable snapshot"):
		return
	scene.position.x += 1
	if not check(not controller.editor_context.message_context(OS.get_environment("TX_MODULE")).valid, "changed scene selection is rejected until explicitly recaptured"):
		return
	controller.editor_context.remove(0)
	controller.editor_context.open_file("res://linked.gd", 3)
	if not check(await wait_until(func():
		var script: Script = EditorInterface.get_script_editor().get_current_script()
		return script != null and script.resource_path == "res://linked.gd"
	), "native file navigation opens the requested project script"):
		return
	main.find_child("TianxuanEditorActions", true, false).get_popup().id_pressed.emit(1)
	if not check(controller.editor_context.attachments().size() == 1 and controller.editor_context.attachments()[0].object_id == "res://linked.gd", "native editor action attaches the selected saved resource"):
		return
	controller.editor_context.remove(0)
	var home = main._page_instances.home
	home._import_source.file_selected.emit(OS.get_environment("TX_IMPORT_SOURCE"))
	home._import_destination.file_selected.emit("res://imported.tres")
	home._import_source.hide()
	home._import_destination.hide()
	if not check(FileAccess.file_exists("res://imported.tres") and FileAccess.get_sha256("res://imported.tres") == FileAccess.get_sha256(OS.get_environment("TX_IMPORT_SOURCE")), "native import dialog installs the selected asset with exact bytes"):
		return
	if not check(await wait_until(func(): return not EditorInterface.get_resource_filesystem().is_scanning()), "editor scan completes after native asset installation"):
		return
	var imported: Resource = ResourceLoader.load("res://imported.tres")
	if not check(imported != null and imported.resource_name == "Native import fixture", "imported asset is usable by the native resource loader"):
		return
	var before := FileAccess.get_sha256("res://imported.tres")
	controller.editor_context.import_asset(OS.get_environment("TX_IMPORT_SOURCE"), "res://imported.tres")
	if not check(FileAccess.get_sha256("res://imported.tres") == before and "已存在" in controller.editor_context.status, "asset import preserves an existing destination"):
		return
	if not check(not controller.editor_context.safe_project_path("res://../outside.tres") and not controller.editor_context.safe_project_path("res://.godot/private"), "native file operations reject traversal and editor private state"):
		return
	sidebar.find_child("ExpandTianxuan", true, false).pressed.emit()
	main.find_child("TianxuanPage_requirements", true, false).pressed.emit()
	if not check(await wait_until(func(): return controller.cache.has("library:requirements") and not controller.busy("library:requirements")), "native requirement library loads from the existing document service"):
		return
	if not check(controller.cache["library:requirements"].items.size() == 1 and controller.cache["library:requirements"].items[0].title == "原生完整需求", "requirement library contains the requirement created in native design flow"):
		return
	main.find_child("TianxuanPage_search", true, false).pressed.emit()
	main._page_instances.search._query.text = "原生"
	main._page_instances.search._refresh.pressed.emit()
	if not check(await wait_until(func(): return controller.cache.has("library:search") and not controller.busy("library:search")), "native search completes its real service scopes"):
		return
	if not check(not controller.cache["library:search"].items.is_empty(), "native search finds persisted workspace content"):
		return
	main.find_child("TianxuanPage_runs", true, false).pressed.emit()
	if not check(await wait_until(func(): return controller.cache.has("library:runs") and not controller.busy("library:runs")), "native run history reads actual execution availability"):
		return
	if not check(controller.cache["library:runs"].available == false, "unconfigured execution service is shown as unavailable without simulated runs"):
		return
	main.find_child("TianxuanPage_issues", true, false).pressed.emit()
	var issue_model = controller.issues
	var issue_view = main._page_instances.issues
	if not check(await wait_until(func(): return issue_model.catalog.has("modules") and not issue_model.listing), "compiled native issue page reads the real project catalog"):
		return
	main.find_child("NativeIssueNew", true, false).pressed.emit()
	var issue_title: LineEdit = main.find_child("NativeIssue_create_title", true, false)
	issue_title.text = "编辑器创建的原生工单"
	issue_title.text_changed.emit(issue_title.text)
	var issue_module: OptionButton = main.find_child("NativeIssue_create_module_id", true, false)
	for index in issue_module.item_count:
		if issue_module.get_item_metadata(index) == OS.get_environment("TX_MODULE"):
			issue_module.select(index)
			issue_module.item_selected.emit(index)
	main.find_child("NativeIssue_create_acceptance", true, false).text = "原生控件创建、编辑并回读实际工单"
	await process_frame
	var create_issue: Button = main.find_child("NativeIssueSave_create", true, false)
	if not check(not create_issue.disabled and create_issue.is_visible_in_tree(), "native issue creation form exposes a usable submit action"):
		return
	create_issue.pressed.emit()
	if not check(await wait_until(func(): return not issue_model.selected.is_empty() and not issue_model.loading and not issue_model.saving), "native issue controls create and read back the same authoritative issue"):
		return
	var created_issue: Dictionary = issue_model.detail.duplicate(true)
	controller.navigate("issues", created_issue.id)
	if not check(await wait_until(func(): return not issue_model.loading and sidebar._page_instances.has("issues")), "native issue navigation reaches both main workspace and compact sidebar"):
		return
	var issue_type: LineEdit = main.find_child("NativeIssue_classification_type", true, false)
	issue_type.text = "feature"
	issue_type.text_changed.emit(issue_type.text)
	if not check(sidebar.find_child("NativeIssue_classification_type", true, false).text == "feature", "issue classification draft is shared immediately between both native Views"):
		return
	main.find_child("NativeIssueSave_classification", true, false).pressed.emit()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.detail.type == "feature"), "native issue classification saves using the server's comparison contract"):
		return
	issue_view._tabs.current_tab = 1
	main.find_child("NativeIssue_plan_estimated_minutes", true, false).value = 120
	main.find_child("NativeIssueSave_plan", true, false).pressed.emit()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.work.plan.estimated_minutes == 120), "native plan form saves estimated effort in the shared work projection"):
		return
	main.find_child("NativeIssue_log_minutes", true, false).value = 35
	main.find_child("NativeIssueSave_log", true, false).pressed.emit()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.work.logged_minutes == 35), "native time form records a real work log"):
		return
	issue_view._tabs.current_tab = 2
	main.find_child("NativeIssue_comment_body", true, false).text = "已核对原生表单与服务回读一致。"
	await process_frame
	main.find_child("NativeIssueSave_comment", true, false).pressed.emit()
	var comment_saved := await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.comments.comments.size() == 1)
	if not comment_saved:
		print(JSON.stringify({"issue_status": issue_model.status, "comment_draft": issue_model.draft("comment"), "comments": issue_model.sections.get("comments"), "pending": issue_model.pending()}))
	if not check(comment_saved, "native discussion form creates a selectable acceptance evidence comment"):
		return
	issue_view._tabs.current_tab = 4
	for issue_stage in ["planned", "in-progress", "in-review"]:
		main.find_child("NativeIssueAdvance_" + issue_stage, true, false).pressed.emit()
		if not check(issue_view._confirmation.visible and issue_model.detail.status != issue_stage, "workflow action waits for the user's explicit native confirmation: " + issue_stage):
			return
		issue_view._confirmation.confirmed.emit()
		issue_view._confirmation.hide()
		if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.detail.status == issue_stage), "native workflow confirmation reads back the new stage: " + issue_stage):
			return
	main.find_child("NativeIssueAccept", true, false).pressed.emit()
	if not check(issue_view._confirmation.get_ok_button().disabled, "native acceptance requires selecting an existing evidence comment"):
		return
	issue_view._evidence.select(1)
	issue_view._evidence.item_selected.emit(1)
	issue_view._confirmation.confirmed.emit()
	issue_view._confirmation.hide()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.lifecycle.accepted == issue_model.sections.comments.comments[0].id), "native acceptance records the selected comment at the reviewed revision"):
		return
	main.find_child("NativeIssueClose", true, false).pressed.emit()
	issue_view._confirmation.confirmed.emit()
	issue_view._confirmation.hide()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.detail.status == "done"), "native lifecycle controls close only the accepted issue revision"):
		return
	main.find_child("NativeIssueReopen", true, false).pressed.emit()
	issue_view._confirmation.confirmed.emit()
	issue_view._confirmation.hide()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.detail.status != "done"), "native lifecycle can explicitly reopen the issue to its recorded previous stage"):
		return
	var flow_view = main.find_child("NativeIssueFlowEditor", true, false)
	flow_view._name.text = "原生人工判断"
	flow_view._add_stage.pressed.emit()
	if not check(await wait_until(func(): return flow_view._stage_controls.has("原生人工判断") and sidebar.find_child("NativeIssueFlowEditor", true, false)._stage_controls.has("原生人工判断")), "native flow stage drafts remain shared between both workspace views"):
		return
	flow_view._stage_controls["原生人工判断"].progress.value = 85
	flow_view._stage_controls["原生人工判断"].human.button_pressed = true
	for index in flow_view._from.item_count:
		if flow_view._from.get_item_metadata(index) == "原生人工判断":
			flow_view._from.select(index)
		if flow_view._to.get_item_metadata(index) == issue_model.detail.status:
			flow_view._to.select(index)
	flow_view._add_edge.pressed.emit()
	if not check(await wait_until(func(): return not flow_view._save.disabled), "native flow form validates percentage, human decision and outgoing route"):
		return
	flow_view._save.pressed.emit()
	if not check(flow_view._dialog.visible and not issue_model.sections.flow.configured, "native flow save requires confirmation of the visible configuration"):
		return
	flow_view._dialog.confirmed.emit()
	flow_view._dialog.hide()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.flow.configured and issue_model.draft("flow").is_empty()), "confirmed native flow saves through the actual versioned service"):
		return
	issue_view._tabs.current_tab = 5
	var assets = issue_view._form_tabs["附件与候选"].get_child(0)
	assets._upload.file_selected.emit(OS.get_environment("TX_IMPORT_SOURCE"))
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.artifacts.artifacts.size() == 1), "native file picker uploads an immutable issue attachment"):
		return
	var artifact_reference: Dictionary = issue_model.sections.artifacts.artifacts[0]
	var original_text := FileAccess.get_file_as_string(OS.get_environment("TX_IMPORT_SOURCE"))
	if not check(await wait_until(func(): return issue_model.previews.get(str(artifact_reference.version), {}).get("text") == original_text), "artifact preview retains the exact digest-verified source text including CRLF"):
		return
	if not check(assets._texts[0].text == original_text.replace("\r\n", "\n"), "native CodeEdit presents CRLF text with its normal line representation"):
		return
	assets._download_buttons[0].pressed.emit()
	var downloaded := ProjectSettings.globalize_path("res://downloaded-artifact.tres")
	assets._destination.file_selected.emit(downloaded)
	assets._destination.hide()
	if not check(await wait_until(func(): return FileAccess.file_exists(downloaded) and FileAccess.get_sha256(downloaded) == artifact_reference.digest), "native artifact save installs exactly the selected immutable version"):
		return
	var preserve := FileAccess.open(downloaded, FileAccess.WRITE)
	preserve.store_string("已有本地版本必须保留")
	preserve.close()
	await issue_model.download_artifact(artifact_reference, downloaded)
	if not check(FileAccess.get_file_as_string(downloaded) == "已有本地版本必须保留" and "已保留" in issue_model.status, "native artifact download preserves different local content and requests another filename"):
		return
	var model_source := FileAccess.get_file_as_bytes(OS.get_environment("TX_MODEL_SOURCE"))
	var model_candidate: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches", {"request_key": controller.new_id(), "changes": [{"module": "native-control-model", "base": null, "reads": null, "edits": {"triangle.glb": Marshalls.raw_to_base64(model_source)}}]})
	issue_view._forms.asset.kind.select(1)
	issue_view._forms.asset.kind.item_selected.emit(1)
	for key in {"module": "native-control-model", "revision": model_candidate.data.revisions["native-control-model"], "path": "triangle.glb"}:
		var value: String = {"module": "native-control-model", "revision": model_candidate.data.revisions["native-control-model"], "path": "triangle.glb"}[key]
		issue_view._forms.asset[key].text = value
		issue_view._forms.asset[key].text_changed.emit(value)
	issue_view._buttons.asset.pressed.emit()
	if not check(await wait_until(func(): return not issue_model.loading and not issue_model.saving and issue_model.sections.work.assets.has("model")), "native art revision form submits a fixed module revision for human review"):
		return
	for index in assets._choices[0].item_count:
		if assets._choices[0].get_item_metadata(index).kind == "model":
			assets._choices[0].select(index)
			assets._choices[0].item_selected.emit(index)
	var model_ready := await wait_until(func(): return is_instance_valid(assets._models[0]) and assets._model_panels[0].is_visible_in_tree())
	if not check(model_ready, "compiled native artifact panel displays the selected mesh in its own 3D viewport"):
		return
	var preview_mesh = assets._models[0].find_children("*", "MeshInstance3D", true, false)[0]
	if not check(preview_mesh.mesh.get_surface_count() == 1 and preview_mesh.mesh.surface_get_material(0) != null and assets._models[0].find_children("*", "ImporterMeshInstance3D", true, false).is_empty(), "editor GLTF preview converts import-only nodes and retains the actual surface material"):
		return
	var camera_before: Vector3 = assets._cameras[0].position
	assets._model_panels[0].get_child(1).get_child(0).pressed.emit()
	if not check(assets._cameras[0].position != camera_before and assets._bounds[0].size.x == 2, "native camera controls orbit the imported model's real bounds"):
		return
	issue_view._view_mode.select(1)
	issue_view._view_mode.item_selected.emit(1)
	main.find_child("NativeIssueList", true, false).pressed.emit()
	if not check(issue_view._board.get_child_count() > 0 and issue_view._board_scroll.is_visible_in_tree(), "native kanban groups the real issue list into visible status columns"):
		return
	var repository_fixture: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches", {"request_key": controller.new_id(), "changes": [{"module": "native-shell-repository", "base": null, "reads": null, "edits": {"README.md": Marshalls.raw_to_base64("原生模块内容".to_utf8_buffer())}}]})
	if not check(repository_fixture.status == 200, "native repository fixture is stored through the authenticated candidate API"):
		return
	main.find_child("TianxuanPage_repos", true, false).pressed.emit()
	var repository_view = main._page_instances.repos
	var repository_model = controller.repositories
	repository_view._lookup.text = "native-shell-repository"
	repository_view._lookup_button.pressed.emit()
	if not check(await wait_until(func(): return not repository_model.loading and repository_model.state.has("revision")), "native repository lookup reads its immutable revision and object tree"):
		return
	var repository_file: TreeItem = repository_view._tree.get_root().get_first_child()
	repository_file.select(0)
	repository_view._tree.item_activated.emit()
	if not check(await wait_until(func(): return repository_model.file.get("content") == "原生模块内容" and repository_view._file.text == "原生模块内容"), "native repository tree opens the digest-verified object in CodeEdit"):
		return
	controller.navigate("repos")
	repository_view._file.text = "原生控件编辑后的模块内容"
	if not check(sidebar._page_instances.repos._file.text == repository_view._file.text, "repository edit draft is shared by the workspace and sidebar"):
		return
	repository_view._save.pressed.emit()
	repository_view._confirmation.confirmed.emit()
	repository_view._confirmation.hide()
	if not check(await wait_until(func(): return not repository_model.saving and not repository_model.loading and repository_model.file.get("content") == "原生控件编辑后的模块内容"), "native repository controls save and verify a new revision"):
		return
	repository_view._mode.select(1)
	repository_view._mode.item_selected.emit(1)
	if not check(await wait_until(func(): return repository_model.catalog.has("git")), "native local Git chooser lists only the isolated service repositories"):
		return
	for index in repository_view._repositories.item_count:
		if repository_view._repositories.get_item_metadata(index).get("name") == "fixture.git":
			repository_view._repositories.select(index)
			repository_view._repositories.item_selected.emit(index)
	if not check(await wait_until(func(): return repository_model.repository == "fixture.git" and not repository_model.loading and repository_model.state.has("tree")), "native Git selection loads the branch, history and file tree"):
		return
	var git_file: TreeItem = repository_view._tree.get_root().get_first_child()
	while git_file != null:
		if git_file.get_metadata(0).get("path") == "README.md":
			git_file.select(0)
			repository_view._tree.item_activated.emit()
			break
		git_file = git_file.get_next()
	if not check(await wait_until(func(): return repository_view._file.text == "原生仓库测试\n"), "native Git file tree opens the selected tracked text file"):
		return
	repository_view._file.text = "通过原生控件编辑 Git 文件\n"
	repository_view._message.text = "Native controls commit"
	repository_view._message.text_changed.emit(repository_view._message.text)
	repository_view._save.pressed.emit()
	repository_view._confirmation.confirmed.emit()
	repository_view._confirmation.hide()
	if not check(await wait_until(func(): return not repository_model.saving and not repository_model.loading and repository_model.branch != "main" and repository_model.file.get("content") == "通过原生控件编辑 Git 文件\n"), "native Git save creates a fresh branch and reads back its exact content"):
		return
	repository_view._tabs.current_tab = 3
	repository_view._diff_a.text = "main"
	repository_view._diff_b.text = repository_model.branch
	main.find_child("NativeRepositoryDiff", true, false).pressed.emit()
	if not check(await wait_until(func(): return "通过原生控件编辑 Git 文件" in repository_view._diff.text), "native diff control displays the real changed lines between the two branches"):
		return
	var edited_branch: String = repository_model.branch
	repository_view._tabs.current_tab = repository_view._tabs.get_tab_count() - 1
	repository_view._import_name.text = "native-control-import.git"
	repository_view._import_source.text = OS.get_environment("TX_IMPORT_REPOSITORY")
	repository_view._import_source.text_changed.emit(repository_view._import_source.text)
	if not check(await wait_until(func(): return not repository_view._import_start.disabled), "native import form enables only for a complete administrator request"):
		return
	repository_view._import_start.pressed.emit()
	if not check(repository_view._confirmation.visible and repository_model.import_jobs.is_empty(), "native repository import waits for confirmation before creating a server task"):
		return
	repository_view._confirmation.confirmed.emit()
	repository_view._confirmation.hide()
	if not check(await wait_until(func(): return not repository_model.import_loading and repository_model.import_jobs.any(func(job: Dictionary): return job.name == "native-control-import.git" and job.status == "succeeded")), "confirmed native controls display a real completed Git mirror import"):
		return
	main.find_child("NativeRepositoryOpenImport", true, false).pressed.emit()
	if not check(await wait_until(func(): return repository_model.repository == "native-control-import.git" and not repository_model.loading and repository_view._tree.get_root().get_child_count() > 0), "native import receipt opens the actual imported repository file tree"):
		return
	main.find_child("TianxuanPage_repository_collaboration", true, false).pressed.emit()
	var collaboration_view = main._page_instances.repository_collaboration
	var collaboration_model = controller.repository_collaboration
	if not check(await wait_until(func(): return collaboration_model.data.has("links") and collaboration_model.data.has("queue") and not collaboration_model.busy("workers")), "native collaboration page reads repository bindings and the real isolated queue"):
		return
	collaboration_view._tabs.current_tab = 3
	collaboration_view._forms.link_repository.owner.text = "fixture"
	collaboration_view._forms.link_repository.owner.text_changed.emit("fixture")
	collaboration_view._forms.link_repository.name.text = "native-ui"
	collaboration_view._forms.link_repository.name.text_changed.emit("native-ui")
	collaboration_view._submit.link_repository.pressed.emit()
	if not check(collaboration_view._dialog.visible and collaboration_model.data.links.links.is_empty(), "native repository binding waits for confirmation of the displayed repository"):
		return
	collaboration_view._dialog.confirmed.emit()
	collaboration_view._dialog.hide()
	if not check(await wait_until(func(): return not collaboration_model.saving and collaboration_model.data.links.links.size() == 1), "native repository binding is persisted by the existing service"):
		return
	collaboration_view._tabs.current_tab = 2
	for field in {"repo": "fixture.git", "source": edited_branch, "target": "main", "title": "原生控件队列测试"}:
		var text: String = {"repo": "fixture.git", "source": edited_branch, "target": "main", "title": "原生控件队列测试"}[field]
		collaboration_view._forms.enqueue[field].text = text
		collaboration_view._forms.enqueue[field].text_changed.emit(text)
	collaboration_view._submit.enqueue.pressed.emit()
	collaboration_view._dialog.confirmed.emit()
	collaboration_view._dialog.hide()
	if not check(await wait_until(func(): return not collaboration_model.saving and collaboration_model.data.queue.items.size() == 1), "native queue form submits the source branch and reads its durable candidate"):
		return
	collaboration_view._queue.get_root().get_first_child().select(0)
	if not check(await wait_until(func(): return not collaboration_view._queue_actions.cancel_queue.disabled), "native queue selection finishes before rebuilding its visible rows"):
		return
	collaboration_view._queue_actions.cancel_queue.pressed.emit()
	collaboration_view._dialog.confirmed.emit()
	collaboration_view._dialog.hide()
	if not check(await wait_until(func(): return not collaboration_model.saving and collaboration_model.data.queue.items[0].status == "cancelled"), "native queue cancellation applies to the explicitly selected candidate"):
		return
	main.find_child("TianxuanPage_game_config", true, false).pressed.emit()
	var config_view = main._page_instances.game_config
	var config_model = controller.game_config
	config_view._title.text = "原生控件配置"
	config_view._title.text_changed.emit(config_view._title.text)
	config_view._save.pressed.emit()
	if not check(await wait_until(func(): return not config_model.saving and not config_model.selected.is_empty() and config_model.project.get("version") == 1), "native configuration form creates a versioned project"):
		return
	main.find_child("NativeConfigAddFeature", true, false).pressed.emit()
	config_view._add_id.text = "combat"
	config_view._add_name.text = "战斗配置"
	config_view._add.confirmed.emit()
	config_view._add.hide()
	if not check(await wait_until(func(): return not config_model.saving and config_model.project.get("features", []).size() == 1), "native configuration adds and automatically saves a feature with its stable ID"):
		return
	main.find_child("NativeConfigAddEntry", true, false).pressed.emit()
	config_view._add_id.text = "damage"
	config_view._add_name.text = "伤害"
	config_view._add.confirmed.emit()
	config_view._add.hide()
	if not check(await wait_until(func(): return not config_model.saving and config_model.project.features[0].entries.size() == 1 and config_view._fields.has("value")), "native configuration renders the typed entry controls from the shared model"):
		return
	controller.navigate("game_config")
	config_view._fields.value.text = "42"
	config_view._fields.value.text_changed.emit("42")
	if not check(sidebar._page_instances.game_config.model.values().features[0].entries[0].value == "42", "both native configuration Views share the same durable field draft"):
		return
	config_view._fields.value.focus_exited.emit()
	if not check(await wait_until(func(): return not config_model.saving and config_model.project.features[0].entries[0].value == 42 and config_model.draft().is_empty()), "leaving a native value field saves its typed number and verifies the new version"):
		return
	config_view._tabs.current_tab = 2
	main.find_child("NativeConfigHistory", true, false).pressed.emit()
	if not check(await wait_until(func(): return config_model.versions.size() == 4), "native configuration version history exposes every acknowledged field save"):
		return
	var before_restore := int(config_model.project.version)
	main.find_child("NativeConfigRestore_3", true, false).pressed.emit()
	if not check(config_view._confirm.visible and config_model.project.version == before_restore, "native configuration restoration waits for explicit version confirmation"):
		return
	config_view._confirm.confirmed.emit()
	config_view._confirm.hide()
	if not check(await wait_until(func(): return not config_model.saving and config_model.project.version == before_restore + 1 and config_model.project.features[0].entries[0].value == 0), "native configuration restoration creates and reads back a new version of the selected historical content"):
		return
	main.find_child("TianxuanPage_migration", true, false).pressed.emit()
	var migration_view = main._page_instances.migration
	var migration_model = controller.migration
	if not check(await wait_until(func(): return migration_model.publication.get("available", false) and not migration_model.entry.is_empty()), "native migration page reads the published archive receipt and current task entry"):
		return
	migration_view._query.text = "原生归档"
	main.find_child("NativeMigrationSearch", true, false).pressed.emit()
	if not check(await wait_until(func(): return migration_model.data.get("search", {}).get("total") == 1), "native archive search uses the current published catalog"):
		return
	migration_view._records.find_child("NativeMigrationRecord", true, false).pressed.emit()
	if not check(await wait_until(func(): return migration_model.data.get("detail", {}).get("record", {}).get("source_id") == "github:fixture/repo/issue/14" and migration_view._details.find_children("*", "RichTextLabel", false, false).size() == 1), "native archive detail renders the historical body and related comments"):
		return
	await migration_model.read("detail", {"source_id": "github:fixture/repo/attachment/42"})
	main.find_child("NativeMigrationAttachment", true, false).pressed.emit()
	var archive_destination := ProjectSettings.globalize_path("res://archived-original.bin")
	migration_view._destination.file_selected.emit(archive_destination)
	migration_view._destination.hide()
	if not check(await wait_until(func(): return FileAccess.file_exists(archive_destination) and FileAccess.get_file_as_string(archive_destination) == "Native archive attachment\n"), "native archive file dialog saves the verified immutable attachment bytes"):
		return
	migration_view._tabs.current_tab = 1
	migration_view._path.text = "README.md"
	main.find_child("NativeMigrationCommits", true, false).pressed.emit()
	if not check(await wait_until(func(): return migration_view._file.text == "原生仓库测试\n" and migration_model.data.get("commits", {}).get("items", []).size() == 1), "native archive code controls read the original imported file and commit history"):
		return
	main.find_child("TianxuanPage_accounts", true, false).pressed.emit()
	var accounts_view = main._page_instances.accounts
	var accounts_model = controller.accounts
	if not check(await wait_until(func(): return accounts_model.data.has("keys") and accounts_model.data.has("links")), "native account page reads the verified member, key and identity records"):
		return
	for field in {"email": "ui-member@example.invalid", "name": "原生控件成员"}:
		var value: String = {"email": "ui-member@example.invalid", "name": "原生控件成员"}[field]
		accounts_view._forms.create_account[field].text = value
		accounts_view._forms.create_account[field].text_changed.emit(value)
	accounts_view._submit.create_account.pressed.emit()
	if not check(accounts_view._dialog.visible and accounts_model.issued_secret.is_empty(), "native account creation waits for explicit confirmation before changing access"):
		return
	accounts_view._dialog.confirmed.emit()
	accounts_view._dialog.hide()
	if not check(await wait_until(func(): return not accounts_model.saving and not accounts_model.issued_secret.is_empty() and accounts_model.data.get("users", {}).get("users", []).size() == 3), "native account controls create the intended member and display the one-time initial credential"):
		return
	main.find_child("NativeAccountsHideSecret", true, false).pressed.emit()
	if not check(accounts_model.issued_secret.is_empty() and accounts_view._secret.text.is_empty() and not accounts_view._secret_panel.visible, "hiding a newly issued credential clears it from the shared model and native view"):
		return
	session.reset()
	if not check(main._current_page == "account" and sidebar._current_page == "account" and legacy.get_identity().is_empty(), "logout clears all native surfaces together"):
		return
	session.set_origin("http://127.0.0.1:1")
	if not check(main._address.text == session.origin and sidebar._address.text == session.origin, "service changes synchronize the displayed login destination in both native Views"):
		return
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
