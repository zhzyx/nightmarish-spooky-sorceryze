@tool
extends VBoxContainer

const STAGES := ["direction", "plan", "design"]
const LABELS := ["方向", "策划", "详细设计"]
var controller: Node
var ui_scale := 1.0
var _stage := OptionButton.new()
var _title := LineEdit.new()
var _body := TextEdit.new()
var _acceptance := TextEdit.new()
var _status := Label.new()
var _save := Button.new()
var _confirm_stage := Button.new()
var _suggest := Button.new()
var _publish := Button.new()
var _discard := Button.new()
var _saved: RichTextLabel
var _history := OptionButton.new()
var _history_body: RichTextLabel
var _return_reason := LineEdit.new()
var _return := Button.new()
var _execution := VBoxContainer.new()
var _review: RichTextLabel
var _approve := Button.new()
var _scopes := VBoxContainer.new()
var _models := OptionButton.new()
var _launch := Button.new()
var _execution_status := Label.new()
var _tasks := Tree.new()
var _progress := ProgressBar.new()
var _confirmation := ConfirmationDialog.new()
var _launch_payload := {}
var _updating := false
var _context := ""
var _capabilities_signature := ""
var _history_signature := ""
var _poll := Timer.new()


func _ready() -> void:
	controller = get_meta("controller")
	ui_scale = float(get_meta("ui_scale", 1.0))
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	var heading := Label.new()
	heading.text = "从讨论到已确认需求"
	heading.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(heading)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(page)
	var navigation := HFlowContainer.new()
	page.add_child(navigation)
	_button(navigation, "返回对话", func(): controller.navigate("home"))
	_button(navigation, "刷新状态", _refresh)
	for label in LABELS:
		_stage.add_item(label)
	_stage.name = "TianxuanDesignStage"
	_stage.item_selected.connect(func(_index: int): _changed("stage"))
	page.add_child(_stage)
	_title.placeholder_text = "需求标题"
	_title.name = "TianxuanDesignTitle"
	_title.text_changed.connect(func(_text: String): _edit())
	page.add_child(_title)
	_body.name = "TianxuanDesignBody"
	_body.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_body.custom_minimum_size.y = 210 * ui_scale
	_body.placeholder_text = "描述本阶段的方案…"
	_body.text_changed.connect(_edit)
	_body.text_set.connect(_edit)
	page.add_child(_body)
	_acceptance.name = "TianxuanDesignAcceptance"
	_acceptance.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_acceptance.custom_minimum_size.y = 120 * ui_scale
	_acceptance.placeholder_text = "验收标准"
	_acceptance.text_changed.connect(_edit)
	_acceptance.text_set.connect(_edit)
	page.add_child(_acceptance)
	var actions := HFlowContainer.new()
	page.add_child(actions)
	_suggest = _button(actions, "从对话生成或补充", func(): controller.suggest_design(STAGES[_stage.selected]))
	_save = _button(actions, "保存新修订", func(): controller.save_design(STAGES[_stage.selected]))
	_save.name = "SaveTianxuanDesign"
	_confirm_stage = _button(actions, "确认此修订", _confirm_revision)
	_confirm_stage.name = "ConfirmTianxuanDesign"
	_confirm_stage.theme_type_variation = "TianxuanPrimaryButton"
	_discard = _button(actions, "采用已保存版本", func(): controller.clear_draft(controller.design_key(STAGES[_stage.selected])))
	_saved = _markdown(page)
	_history.name = "TianxuanDesignHistory"
	_history.item_selected.connect(_read_history)
	page.add_child(_history)
	_history_body = _markdown(page)
	_return_reason.placeholder_text = "退回原因"
	page.add_child(_return_reason)
	_return = _button(page, "退回此阶段重新修订", _return_revision)
	_publish = _button(page, "保存已确认需求", _publish_requirement)
	_publish.name = "PublishTianxuanRequirement"
	_publish.theme_type_variation = "TianxuanPrimaryButton"
	page.add_child(_execution)
	_build_execution()
	_confirmation.confirmed.connect(_start_execution)
	add_child(_confirmation)
	_poll.wait_time = 5.0
	_poll.timeout.connect(_refresh_execution)
	add_child(_poll)
	controller.changed.connect(_changed)
	visibility_changed.connect(func():
		if is_visible_in_tree():
			_refresh()
		else:
			_poll.stop()
	)
	_changed("identity")
	_refresh()


func _button(parent: Node, caption: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = caption
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _markdown(parent: Node) -> RichTextLabel:
	var label: RichTextLabel = get_meta("markdown_script").new()
	label.ui_scale = ui_scale
	label.set_meta("controller", controller)
	parent.add_child(label)
	return label


func _edit() -> void:
	if not _updating:
		controller.update_design_draft(STAGES[_stage.selected], _body.text, _title.text, _acceptance.text)


func _refresh() -> void:
	if not controller.active_conversation.is_empty():
		controller.refresh_conversation(controller.active_conversation)
	controller.load_execution()


func _confirm_revision() -> void:
	var stage: String = STAGES[_stage.selected]
	var revision: Dictionary = controller.design_revision(stage)
	if not _confirm_stage.disabled and not revision.is_empty():
		controller.change_conversation("/design/" + stage + "/confirm", {"revision": revision.revision})


func _return_revision() -> void:
	var stage: String = STAGES[_stage.selected]
	var revision: Dictionary = controller.design_revision(stage)
	if not _return.disabled and not revision.is_empty() and not _return_reason.text.strip_edges().is_empty():
		controller.change_conversation("/design/" + stage + "/return", {"revision": revision.revision, "reason": _return_reason.text.strip_edges()})


func _publish_requirement() -> void:
	if not _publish.disabled:
		await controller.change_conversation("/requirement", {"lang": controller.language})
		controller.load_execution()


func _read_history(index: int) -> void:
	var revision: Dictionary = _history.get_item_metadata(index)
	_history_body.set_markdown("## " + str(revision.get("title", "")) + "\n\n" + str(revision.body) + "\n\n" + str(revision.get("acceptance", "")))


func _build_execution() -> void:
	var heading := Label.new()
	heading.text = "需求执行"
	heading.theme_type_variation = "TianxuanHeading"
	_execution.add_child(heading)
	_button(_execution, "执行观测与内容发布", func():
		var execution: Variant = controller.conversation().get("execution")
		if execution is Dictionary:
			controller.navigate("execution", str(execution.entry))
	)
	_button(_execution, "打开已保存需求", func():
		var id: String = controller.conversation().get("requirement_id", "")
		if not id.is_empty():
			controller.documents.open(id)
			controller.navigate("documents")
	)
	_review = _markdown(_execution)
	_approve = _button(_execution, "确认当前需求版本", func():
		var review: Dictionary = controller.cache.get("requirement-review:" + controller.active_conversation, {})
		if review.has("version"):
			await controller.change_conversation("/requirement-review", {"document_version": review.version})
			controller.load_execution()
	)
	_execution_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_execution.add_child(_execution_status)
	_execution.add_child(_scopes)
	_execution.add_child(_models)
	_launch = _button(_execution, "启动已确认需求", _prepare_execution)
	_launch.theme_type_variation = "TianxuanPrimaryButton"
	_execution.add_child(_progress)
	_tasks.columns = 3
	_tasks.set_column_title(0, "工单")
	_tasks.set_column_title(1, "状态")
	_tasks.set_column_title(2, "实际模型")
	_tasks.column_titles_visible = true
	_tasks.hide_root = true
	_tasks.custom_minimum_size.y = 180 * ui_scale
	_tasks.item_activated.connect(func():
		var item := _tasks.get_selected()
		if item and item.get_metadata(0) is String:
			controller.navigate("issues", item.get_metadata(0))
	)
	_execution.add_child(_tasks)


func _prepare_execution() -> void:
	if _launch.disabled:
		return
	var choices := []
	for choice in _scopes.get_children():
		if choice is CheckBox and choice.button_pressed:
			choices.append(choice.get_meta("scope"))
	if choices.is_empty():
		_execution_status.text = "请至少选择一项执行范围。"
		return
	var current: Dictionary = controller.conversation()
	_launch_payload = {"requirement_version": current.requirement_version, "scopes": choices}
	if _models.selected > 0:
		_launch_payload.model = _models.get_item_metadata(_models.selected)
	_launch_payload.context = _context
	_launch_payload.version = current.version
	_confirmation.dialog_text = tr("启动需求 v%d？\n\n执行范围：%s\n模型：%s") % [int(current.requirement_version), "、".join(choices), _models.get_item_text(_models.selected)]
	_confirmation.popup_centered()


func _start_execution() -> void:
	var payload := _launch_payload.duplicate(true)
	_launch_payload.clear()
	if payload.get("context") != _context or payload.get("version") != controller.conversation().get("version"):
		_execution_status.text = "需求已变化，请刷新后重新确认执行。"
		return
	payload.erase("context")
	payload.erase("version")
	await controller.change_conversation("/execution", payload)
	controller.load_execution()


func _refresh_execution() -> void:
	if is_visible_in_tree():
		controller.load_execution()


func _changed(_topic: String) -> void:
	_updating = true
	var current: Dictionary = controller.conversation()
	var context: String = controller.session.scope_key() + ":" + controller.active_conversation
	if context != _context:
		_context = context
		_confirmation.hide()
		_launch_payload.clear()
		_stage.select(0)
		_return_reason.clear()
	var stage: String = STAGES[_stage.selected]
	var revision: Dictionary = controller.design_revision(stage)
	var local: Dictionary = controller.load_draft(controller.design_key(stage))
	var shown: Dictionary = revision if local.is_empty() else local
	var editing: bool = controller.design_open(stage) and not controller.chat_busy()
	if _body.text != str(shown.get("body", "")):
		_body.text = str(shown.get("body", ""))
	if _title.text != str(shown.get("title", "")):
		_title.text = str(shown.get("title", ""))
	if _acceptance.text != str(shown.get("acceptance", "")):
		_acceptance.text = str(shown.get("acceptance", ""))
	for field in [_body, _title, _acceptance]:
		field.editable = editing
	_title.visible = stage == "design"
	_acceptance.visible = stage == "design"
	var complete := not _body.text.strip_edges().is_empty() and _body.text.length() <= 8000
	if stage == "design":
		complete = complete and not _title.text.strip_edges().is_empty() and _title.text.length() <= 150 and not _acceptance.text.strip_edges().is_empty() and _acceptance.text.length() <= 8000
	_save.disabled = not editing or local.is_empty() or not complete
	_suggest.disabled = not editing or controller.busy("design-suggestion")
	_confirm_stage.disabled = not editing or revision.is_empty() or not local.is_empty() or revision.get("confirmed_at") != null
	_discard.disabled = local.is_empty() or controller.chat_busy()
	_return.disabled = not editing or revision.is_empty() or not local.is_empty()
	_status.text = "先在工作台中创建或选择一段对话。" if current.is_empty() else str(controller.errors.get("design", "先确认方向，再逐步完善策划与详细设计。"))
	_saved.visible = not local.is_empty() and local.get("based_on", 0) != revision.get("revision", 0)
	if _saved.visible:
		_saved.set_markdown(tr("### 服务器上的当前修订\n\n") + str(revision.get("body", "")) + "\n\n" + str(revision.get("acceptance", "")))
	var all_confirmed := not current.is_empty()
	var all_saved := true
	for index in STAGES.size():
		var item: Dictionary = controller.design_revision(STAGES[index])
		_stage.set_item_text(index, LABELS[index] + (tr(" · 已确认") if item.get("confirmed_at") != null else ""))
		all_confirmed = all_confirmed and item.get("confirmed_at") != null
		all_saved = all_saved and controller.load_draft(controller.design_key(STAGES[index])).is_empty()
	_publish.visible = current.get("requirement_id") == null
	_publish.disabled = not all_confirmed or not all_saved or not controller.can_edit() or controller.chat_busy()
	var signature := JSON.stringify([stage, current.get("revisions", [])])
	if signature != _history_signature:
		_history_signature = signature
		_history.clear()
		_history_body.clear()
		for item in current.get("revisions", []):
			if item.stage == stage:
				_history.add_item(tr("修订 %d%s") % [int(item.revision), tr(" · 曾确认") if item.get("confirmed_at") != null else ""])
				_history.set_item_metadata(_history.item_count - 1, item)
		if _history.item_count:
			_history.select(_history.item_count - 1)
			_read_history(_history.item_count - 1)
	_execution.visible = current.get("requirement_id") != null
	if _execution.visible:
		_render_execution(current)
	_updating = false


func _render_execution(current: Dictionary) -> void:
	var review: Dictionary = controller.cache.get("requirement-review:" + str(current.id), {})
	var needs_review: bool = review.get("version") != review.get("approved_version")
	_review.visible = needs_review
	_approve.visible = needs_review
	_approve.disabled = controller.chat_busy() or not controller.can_edit()
	if needs_review:
		_review.set_markdown(tr("## 审阅需求 v%d\n\n%s\n\n%s") % [int(review.version), review.title, review.body_md])
	var execution: Variant = current.get("execution")
	var has_execution := execution is Dictionary
	_scopes.visible = not has_execution
	_models.visible = not has_execution
	_launch.visible = not has_execution
	_tasks.visible = has_execution
	_progress.visible = has_execution
	_launch.disabled = controller.chat_busy() or not controller.can_edit() or needs_review or review.is_empty() or _scopes.get_child_count() == 0
	if not has_execution:
		_poll.stop()
		var capabilities: Dictionary = controller.cache.get("execution-capabilities", {})
		var signature := JSON.stringify(capabilities)
		if signature != _capabilities_signature:
			_capabilities_signature = signature
			for child in _scopes.get_children():
				_scopes.remove_child(child)
				child.queue_free()
			for scope in capabilities.get("scopes", {}):
				var choice := CheckBox.new()
				choice.text = str(scope)
				choice.set_meta("scope", scope)
				_scopes.add_child(choice)
			_models.clear()
			_models.add_item("按任务能力选择")
			for profile in capabilities.get("models", []):
				_models.add_item(str(profile.id))
				_models.set_item_metadata(_models.item_count - 1, profile.id)
		_execution_status.text = str(controller.errors.get("execution-capabilities", "请选择已准入的执行范围。" if not capabilities.is_empty() else "正在读取执行服务…"))
		_launch.disabled = controller.chat_busy() or not controller.can_edit() or needs_review or review.is_empty() or _scopes.get_child_count() == 0
		return
	var key := "execution:" + str(execution.entry)
	var status: Dictionary = controller.cache.get(key, {})
	var progress: Dictionary = status.get("progress", {})
	_execution_status.text = str(controller.errors.get(key, tr("%s · %d / %d 项工单完成") % [tr("已派发") if status.get("state") == "delivered" else str(status.get("state", tr("读取中"))), int(progress.get("done", 0)), int(progress.get("total", 0))]))
	_progress.value = float(progress.get("percent", 0))
	_tasks.clear()
	var root := _tasks.create_item()
	var settled: bool = status.get("state") == "delivered" and not status.get("tasks", []).is_empty()
	for task in status.get("tasks", []):
		var row := _tasks.create_item(root)
		row.set_text(0, str(task.get("title", task.get("task", ""))))
		row.set_text(1, str(task.get("state", "")))
		row.set_text(2, str(task.observed_model) if task.get("observed_model") != null else "未观测")
		row.set_metadata(0, task.get("issue_id", ""))
		settled = settled and task.get("state") in ["accepted", "failed", "stopped", "superseded", "closed-unresolved"]
	if not settled and is_visible_in_tree():
		if _poll.is_stopped():
			_poll.start()
	else:
		_poll.stop()


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_capabilities_signature = ""
		_history_signature = ""
		_changed("")
