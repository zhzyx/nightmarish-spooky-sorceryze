@tool
extends VBoxContainer
## Typed flow definition editor. Drafts and version checks belong to the issue model.

var controller: Node
var model: Node
var _rows := VBoxContainer.new()
var _edges := VBoxContainer.new()
var _name := LineEdit.new()
var _from := OptionButton.new()
var _to := OptionButton.new()
var _note := Label.new()
var _remote := Label.new()
var _save := Button.new()
var _review := Button.new()
var _add_stage := Button.new()
var _add_edge := Button.new()
var _discard := Button.new()
var _dialog := ConfirmationDialog.new()
var _intent := {}
var _stage_controls := {}
var _stage_ids: Array = []
var _edge_signature := ""
var _scope := ""
var _syncing := false


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.issues
	label(self, "阶段与流转路径", "TianxuanHeading")
	label(self, "保留当前阶段和完成阶段 done。人工判断点由审核者确认下一阶段。")
	_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_note)
	add_child(_rows)
	_name.placeholder_text = "新阶段名称"
	_name.max_length = 64
	_name.name = "NativeFlowNewStage"
	add_child(_name)
	_add_stage = button(self, "添加阶段", "NativeFlowAddStage", func():
		var id := _name.text.strip_edges()
		var values: Dictionary = model.flow_values()
		if id.is_empty() or values.stages.size() >= 64 or values.stages.any(func(stage: Dictionary): return stage.id == id):
			_note.text = "请输入唯一的阶段名称，最多 64 个阶段。"
			return
		values.stages.append({"id": id, "progress": 0, "human": false})
		model.edit("flow", values)
		_name.clear()
	)
	label(self, "允许的流转路径", "TianxuanHeading")
	add_child(_edges)
	for choice in [_from, _to]:
		choice.fit_to_longest_item = false
		add_child(choice)
	_from.name = "NativeFlowFrom"
	_to.name = "NativeFlowTo"
	_add_edge = button(self, "添加路径", "NativeFlowAddEdge", func():
		if _from.selected < 0 or _to.selected < 0:
			return
		var edge := {"from": _from.get_selected_metadata(), "to": _to.get_selected_metadata()}
		var values: Dictionary = model.flow_values()
		if edge.from == edge.to or edge.from in ["done", "cancelled"] or edge in values.edges or values.edges.size() >= 512:
			_note.text = "请选择不同的有效阶段，不可重复路径，也不能从终态出发。"
			return
		values.edges.append(edge)
		model.edit("flow", values)
	)
	_remote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_remote)
	_review = button(self, "已比较双方配置，保留草稿重新确认", "NativeFlowReview", func(): model.review_draft("flow"))
	_save = button(self, "保存流程配置", "NativeFlowSave", func():
		_intent = {"snapshot": model.action_snapshot(), "draft": model.draft("flow").duplicate(true)}
		_dialog.dialog_text = tr("确认将下方阶段与路径应用于当前工单？\n\n") + describe(model.flow_values())
		_dialog.popup_centered(Vector2i(520, 440) * float(get_meta("ui_scale", 1.0)))
	)
	_save.theme_type_variation = "TianxuanPrimaryButton"
	_discard = button(self, "放弃流程草稿", "NativeFlowDiscard", func():
		if model.editable():
			controller.clear_draft(model.draft_key("flow"))
	)
	_dialog.title = "确认流程配置"
	_dialog.confirmed.connect(func():
		if _intent.get("snapshot") == model.action_snapshot() and _intent.get("draft") == model.draft("flow"):
			model.submit("flow")
		else:
			_note.text = "配置或服务器版本已变化，请重新核对后保存。"
	)
	add_child(_dialog)
	model.changed.connect(func(): _render.call_deferred())
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


func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func describe(value: Dictionary) -> String:
	var lines: Array[String] = []
	for stage in value.get("stages", []):
		lines.append("%s · %d%% · %s" % [stage.id, int(stage.progress), tr("人工判断") if stage.human else tr("普通阶段")])
	for edge in value.get("edges", []):
		lines.append("%s → %s" % [edge.from, edge.to])
	return "\n".join(lines)


func _edit_stage(id: String, key: String, value: Variant) -> void:
	if _syncing:
		return
	var values: Dictionary = model.flow_values()
	for stage in values.stages:
		if stage.id == id:
			stage[key] = value
	model.edit("flow", values)


func _build_stages(values: Dictionary) -> void:
	clear(_rows)
	_stage_controls.clear()
	for stage in values.stages:
		var id := str(stage.id)
		var panel := PanelContainer.new()
		panel.theme_type_variation = "TianxuanInset"
		_rows.add_child(panel)
		var row := HFlowContainer.new()
		panel.add_child(row)
		label(row, id, "TianxuanHeading")
		var progress := SpinBox.new()
		progress.name = "NativeFlowProgress"
		progress.min_value = 0
		progress.max_value = 100 if id == "done" else 99
		progress.suffix = "%"
		progress.value_changed.connect(func(value: float): _edit_stage(id, "progress", int(value)))
		row.add_child(progress)
		var human := CheckBox.new()
		human.text = "人工判断"
		human.toggled.connect(func(value: bool): _edit_stage(id, "human", value))
		row.add_child(human)
		var remove := button(row, "移除", "NativeFlowRemoveStage", func():
			if id in ["done", model.sections.get("flow", {}).get("status")]:
				return
			var edited: Dictionary = model.flow_values()
			edited.stages = edited.stages.filter(func(item: Dictionary): return item.id != id)
			edited.edges = edited.edges.filter(func(edge: Dictionary): return edge.from != id and edge.to != id)
			model.edit("flow", edited)
		)
		_stage_controls[id] = {"progress": progress, "human": human, "remove": remove}
	for choice in [_from, _to]:
		var previous: Variant = choice.get_selected_metadata() if choice.selected >= 0 else null
		choice.clear()
		for stage in values.stages:
			choice.add_item(str(stage.id))
			choice.set_item_metadata(choice.item_count - 1, stage.id)
			if stage.id == previous:
				choice.select(choice.item_count - 1)


func _render() -> void:
	if not is_node_ready():
		return
	_syncing = true
	var scope: String = controller.session.scope_key() + ":" + model.selected
	if scope != _scope:
		_scope = scope
		_stage_ids.clear()
		_edge_signature = ""
		_dialog.hide()
		_intent.clear()
		_name.clear()
	var values: Dictionary = model.flow_values()
	var ids: Array = values.stages.map(func(stage: Dictionary): return stage.id)
	if ids != _stage_ids:
		_stage_ids = ids
		_build_stages(values)
	var enabled: bool = model.editable() and model.sections.has("flow") and not model.sections.get("lifecycle", {}).get("managed", false) and model.detail.get("status") not in ["done", "cancelled"]
	for stage in values.stages:
		var controls: Dictionary = _stage_controls[stage.id]
		controls.progress.editable = enabled and stage.id != "done"
		if not controls.progress.get_line_edit().has_focus():
			controls.progress.value = int(stage.progress)
		controls.human.disabled = not enabled
		controls.human.set_pressed_no_signal(stage.human)
		controls.remove.disabled = not enabled or stage.id in ["done", model.sections.get("flow", {}).get("status")]
	var signature := JSON.stringify([values.edges, enabled])
	if signature != _edge_signature:
		_edge_signature = signature
		clear(_edges)
		for edge in values.edges:
			var row := HFlowContainer.new()
			_edges.add_child(row)
			label(row, "%s → %s" % [edge.from, edge.to])
			button(row, "删除路径", "NativeFlowRemoveEdge", func():
				var edited: Dictionary = model.flow_values()
				edited.edges.erase(edge)
				model.edit("flow", edited)
			).disabled = not enabled
	var outdated: bool = model.draft_outdated("flow")
	_remote.visible = outdated
	_review.visible = outdated
	_review.disabled = not enabled
	if outdated:
		_remote.text = tr("服务器流程已更新；上方保留你的草稿。当前服务器配置：\n") + describe(model.sections.get("flow", {}))
	_note.text = model.flow_error(values)
	_save.disabled = not enabled or outdated or model.draft("flow").is_empty() or not _note.text.is_empty()
	_discard.disabled = not model.editable() or model.draft("flow").is_empty()
	_add_stage.disabled = not enabled or values.stages.size() >= 64
	_add_edge.disabled = not enabled or values.edges.size() >= 512
	_name.editable = enabled
	_from.disabled = not enabled
	_to.disabled = not enabled
	_syncing = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_edge_signature = ""
		_render()
