@tool
extends VBoxContainer

const STATES := {"pending": "等待规划", "planned": "已规划", "ready": "等待执行", "reserved": "已分配", "running": "运行中", "held": "待核对", "produced": "已产出", "failed": "执行失败", "delivered": "已派发", "accepted": "已验收", "stopped": "已停止", "superseded": "已替代", "closed-unresolved": "关闭待解"}
var controller: Node
var model: Node
var _status := Label.new()
var _entry := LineEdit.new()
var _progress := ProgressBar.new()
var _tasks := VBoxContainer.new()
var _roles := VBoxContainer.new()
var _failures := VBoxContainer.new()
var _releases := VBoxContainer.new()
var _past := VBoxContainer.new()
var _head := Label.new()
var _target := OptionButton.new()
var _rollback := Button.new()
var _retry := Button.new()
var _dialog := ConfirmationDialog.new()
var _intent := {}
var _signature := ""
var _history_signature := ""
var _scope := ""


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.execution
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	label(self, "执行观测与内容发布", "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle")
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	_entry.placeholder_text = "执行编号"
	_entry.custom_minimum_size.x = 220 * float(get_meta("ui_scale", 1.0))
	toolbar.add_child(_entry)
	button(toolbar, "读取执行记录", "NativeExecutionRead", func(): model.select(_entry.text.strip_edges()))
	button(toolbar, "刷新", "NativeExecutionRefresh", func(): model.refresh())
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	add_child(_progress)
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(tabs)
	var observations := tab(tabs, "观测回执")
	observations.add_child(_failures)
	label(observations, "生产工单", "TianxuanHeading")
	observations.add_child(_tasks)
	label(observations, "角色调用", "TianxuanHeading")
	observations.add_child(_roles)
	var releases := tab(tabs, "内容发布")
	_head.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	releases.add_child(_head)
	_target.fit_to_longest_item = false
	releases.add_child(_target)
	_rollback = button(releases, "回退到所选已验收版本", "NativeExecutionRollback", func():
		if _target.selected <= 0:
			return
		_intent = {"target": _target.get_selected_metadata(), "expected": model.snapshot()}
		_dialog.dialog_text = tr("当前稳定版本：%s\n恢复内容来源：%s\n\n确认后生成回退回执并重新读取发布状态。") % [str(model.releases.get("head", "")), str(_intent.target)]
		_dialog.popup_centered()
	)
	_retry = button(releases, "核对并重试原回退请求", "NativeExecutionRetryRollback", func(): model.retry_rollback())
	releases.add_child(_releases)
	var earlier := tab(tabs, "以往执行")
	earlier.add_child(_past)
	_dialog.confirmed.connect(func():
		if not _intent.is_empty():
			model.rollback(_intent.target, _intent.expected)
	)
	add_child(_dialog)
	model.changed.connect(_render)
	controller.changed.connect(func(_topic: String): _render())
	visibility_changed.connect(func(): model.observe(self, is_visible_in_tree()))
	model.observe(self, is_visible_in_tree())
	if model.selected.is_empty():
		var current: Variant = controller.conversation().get("execution")
		if current is Dictionary:
			model.select(str(current.entry))
	_render()


func label(parent: Node, text: String, variation := "TianxuanCaption") -> Label:
	var node := Label.new()
	node.text = text
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.theme_type_variation = variation
	parent.add_child(node)
	return node


func button(parent: Node, text: String, node_name: String, action: Callable) -> Button:
	var node := Button.new()
	node.text = text
	node.name = node_name
	node.pressed.connect(action)
	parent.add_child(node)
	return node


func tab(parent: Node, title: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(box)
	return box


func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func counts(value: Variant) -> String:
	if not value is Dictionary:
		return "未回报"
	var parts: Array[String] = []
	for item in [["totalTokens", "总令牌"], ["inputTokens", "输入"], ["cachedInputTokens", "缓存输入"], ["cacheWriteInputTokens", "缓存写入"], ["outputTokens", "输出"], ["reasoningOutputTokens", "推理输出"]]:
		var amount: Variant = value.get(item[0])
		if (amount is float or amount is int) and is_finite(float(amount)) and amount >= 0 and amount <= 9007199254740991.0 and float(amount) == floor(float(amount)):
			parts.append("%s %d" % [item[1], int(amount)])
	return " · ".join(parts) if not parts.is_empty() else "未回报"


func observation(parent: Node, value: Dictionary, role: bool) -> void:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "TianxuanCard"
	parent.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	if role:
		label(box, str({"yanshi": "偃师", "reviewer": "审查者"}.get(value.get("role", ""), value.get("role", "角色"))), "TianxuanHeading")
	elif value.get("issue_id") is String:
		button(box, str(value.get("title", tr("执行工单"))), "NativeExecutionIssue", func(): controller.navigate("issues", str(value.issue_id))).auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	else:
		label(box, str(value.get("title", tr("执行工单"))), "TianxuanHeading").auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	if not role:
		label(box, str(STATES.get(value.get("state", ""), value.get("state", ""))))
		label(box, tr("任务编号：") + str(value.get("task", "")))
	var actual_model: Variant = value.get("observed_model")
	var source: Variant = value.get("source" if role else "observation_source")
	label(box, tr("观测模型：") + (str(actual_model) if actual_model is String and not actual_model.strip_edges().is_empty() else tr("未观测")))
	label(box, tr("观测来源：") + (str(source) if source is String and not source.strip_edges().is_empty() else tr("未回报")))
	var usage: Variant = value.get("reported_usage" if role else "usage")
	if usage is Dictionary:
		label(box, tr("供应方原始用量 · 最近一次\n") + counts(usage.get("last")))
		label(box, tr("供应方原始用量 · 会话累计\n") + counts(usage.get("total")))
	else:
		label(box, "供应方原始用量未回报。")


func _render() -> void:
	var scope: String = controller.session.scope_key() + ":" + model.selected
	if scope != _scope:
		_scope = scope
		_entry.text = model.selected
		_dialog.hide()
		_intent.clear()
	_entry.editable = not model.saving and model.pending().is_empty()
	var report: Dictionary = model.observation
	_status.text = tr(model.status)
	if not model.action_status.is_empty():
		_status.text += "\n" + model.action_status
	if not report.is_empty():
		_status.text += tr("\n%s · %d / %d 项工单完成") % [tr(STATES.get(report.get("state", ""), report.get("state", ""))), int(report.get("progress", {}).get("done", 0)), int(report.get("progress", {}).get("total", 0))]
		if report.get("requested_profile") is String:
			_status.text += tr("\n所选模型档案：") + str(report.requested_profile)
	_progress.visible = not report.is_empty()
	_progress.value = float(report.get("progress", {}).get("percent", 0))
	var signature := JSON.stringify([_scope, report, controller.conversation().get("past_executions", [])])
	if signature != _signature:
		_signature = signature
		for section in [_tasks, _roles, _failures, _past]:
			clear(section)
		for task in report.get("tasks", []):
			observation(_tasks, task, false)
		for call in report.get("role_calls", []):
			observation(_roles, call, true)
		if report.get("role_calls", []).is_empty():
			label(_roles, "暂无角色调用观测回执。")
		for failure in report.get("failures", []):
			label(_failures, "执行异常", "TianxuanHeading")
			if failure is Dictionary:
				for key in failure:
					label(_failures, str(key) + "：" + str(failure[key]))
			else:
				label(_failures, str(failure))
		for past in controller.conversation().get("past_executions", []):
			button(_past, tr("需求 v%d · %s") % [int(past.requirement_version), str(past.entry)], "NativeExecutionPast", func(): model.select(str(past.entry)))
	_head.text = tr("当前稳定版本：") + str(model.releases.get("head", "—"))
	if not model.release_error.is_empty():
		_head.text += "\n" + model.release_error
	if not model.receipt.is_empty():
		_head.text += tr("\n回退回执：") + model.receipt
	var history_signature := JSON.stringify([_scope, model.releases])
	if history_signature != _history_signature:
		_history_signature = history_signature
		clear(_releases)
		_target.clear()
		_target.add_item("选择已验收的历史版本")
		_target.set_item_metadata(0, "")
		for event in model.releases.get("events", []):
			label(_releases, "#%d · %s" % [int(event.sequence), str(event.selection)], "TianxuanHeading")
			label(_releases, tr("候选版本：") + str(event.candidate))
			label(_releases, "已验收" if event.get("accepted", false) else "尚未验收")
			if event.get("restored_from") is String:
				label(_releases, tr("恢复来源：") + str(event.restored_from))
			if event.get("modules") is Dictionary:
				for module in event.modules:
					label(_releases, "%s · %s" % [module, str(event.modules[module])])
			elif event.get("modules") is Array:
				for module in event.modules:
					label(_releases, str(module))
			if event.get("accepted", false) and event.selection != model.releases.get("head"):
				_target.add_item("#%d · %s" % [int(event.sequence), str(event.selection)])
				_target.set_item_metadata(_target.item_count - 1, event.selection)
	_rollback.disabled = model.saving or model.loading or not model.pending().is_empty() or not controller.can_edit() or _target.item_count < 2
	_target.disabled = _rollback.disabled
	_retry.visible = not model.pending().is_empty()
	_retry.disabled = model.saving or model.loading or not controller.can_edit()


func _exit_tree() -> void:
	if is_instance_valid(model):
		model.observe(self, false)


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signature = ""
		_history_signature = ""
		_render()
