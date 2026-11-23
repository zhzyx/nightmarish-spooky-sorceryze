@tool
extends VBoxContainer

var controller: Node
var model: Node
var ui_scale := 1.0
var _syncing := false
var _context := ""
var _catalog_signature := ""
var _list_signature := ""
var _detail_signature := ""
var _browsing := true
var _status := Label.new()
var _heading := Label.new()
var _query := LineEdit.new()
var _label_query := LineEdit.new()
var _status_filter := OptionButton.new()
var _view_mode := OptionButton.new()
var _list := Tree.new()
var _board_scroll := ScrollContainer.new()
var _board := HBoxContainer.new()
var _browse := VBoxContainer.new()
var _editor := VBoxContainer.new()
var _tabs := TabContainer.new()
var _form_tabs := {}
var _forms := {}
var _buttons := {}
var _conflicts := {}
var _review := {}
var _summary := VBoxContainer.new()
var _comments := VBoxContainer.new()
var _relationships := VBoxContainer.new()
var _flow := VBoxContainer.new()
var _history := VBoxContainer.new()
var _logs := VBoxContainer.new()
var _retry := Button.new()
var _ack := Button.new()
var _confirmation := ConfirmationDialog.new()
var _evidence := OptionButton.new()
var _intent := {}
var _new_form := VBoxContainer.new()
var _detail := VBoxContainer.new()
var _catalog_ready := false
var _target_form: VBoxContainer
var _task_actions := VBoxContainer.new()
var _dependency := SpinBox.new()
var _add_dependency := Button.new()
const STATES := {"backlog": "待排期", "planned": "已计划", "in-progress": "进行中", "blocked": "受阻", "in-review": "待评审", "done": "已完成", "cancelled": "已取消"}


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.issues
	_browsing = model.selected.is_empty()
	ui_scale = float(get_meta("ui_scale", 1.0))
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	_heading.text = "工单"
	_heading.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	add_child(_heading)
	var tools := HFlowContainer.new()
	add_child(tools)
	button(tools, "所有工单", "NativeIssueList", func(): _browsing = true; _render())
	button(tools, "新建工单", "NativeIssueNew", func():
		if not model.saving:
			_browsing = false
			model.open("")
	)
	button(tools, "刷新", "NativeIssueRefresh", _refresh)
	_status.theme_type_variation = "TianxuanCaption"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_retry.text = "核对后重试原请求"
	_retry.pressed.connect(func(): model.retry())
	add_child(_retry)
	_ack.text = "已核对服务器结果，恢复编辑"
	_ack.pressed.connect(func(): model.acknowledge_unknown())
	add_child(_ack)
	_build_browse()
	_build_detail()
	_build_confirmation()
	model.changed.connect(_render)
	controller.navigation_requested.connect(func(page: String, _id: String):
		if page == "issues":
			_browsing = _id.is_empty()
			_render()
	)
	visibility_changed.connect(func():
		if is_visible_in_tree() and not _catalog_ready:
			_refresh()
	)
	_render()
	_refresh()


func label(parent: Node, text: String, variation := "") -> Label:
	var node := Label.new()
	node.text = text
	node.theme_type_variation = variation
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
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


func _build_browse() -> void:
	_browse.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_browse)
	var tools := HFlowContainer.new()
	_browse.add_child(tools)
	_query.name = "NativeIssueQuery"
	_query.placeholder_text = "搜索标题、正文或验收条件"
	_query.custom_minimum_size.x = 220 * ui_scale
	_query.text_submitted.connect(func(_value: String): _search())
	tools.add_child(_query)
	_label_query.placeholder_text = "标签"
	_label_query.custom_minimum_size.x = 100 * ui_scale
	_label_query.text_submitted.connect(func(_value: String): _search())
	tools.add_child(_label_query)
	for entry in [["", "全部状态"], ["backlog", "待排期"], ["planned", "已计划"], ["in-progress", "进行中"], ["blocked", "受阻"], ["in-review", "待评审"], ["done", "已完成"], ["cancelled", "已取消"]]:
		_status_filter.add_item(entry[1])
		_status_filter.set_item_metadata(_status_filter.item_count - 1, entry[0])
	_status_filter.item_selected.connect(func(_index: int): _search())
	tools.add_child(_status_filter)
	button(tools, "搜索", "NativeIssueSearch", _search)
	for entry in ["列表", "看板", "路线图", "待我判断"]:
		_view_mode.add_item(entry)
	_view_mode.item_selected.connect(func(_index: int): _list_signature = ""; _render())
	tools.add_child(_view_mode)
	_list.name = "NativeIssuesTree"
	_list.hide_root = true
	_list.columns = 3
	_list.set_column_title(0, "工单")
	_list.set_column_title(1, "状态 / 计划")
	_list.set_column_title(2, "进度")
	_list.set_column_titles_visible(true)
	_list.set_column_expand_ratio(0, 3)
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.item_activated.connect(func():
		var item := _list.get_selected()
		if item and item.get_metadata(0) is String:
			_open.call_deferred(item.get_metadata(0))
	)
	_browse.add_child(_list)
	_board_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_browse.add_child(_board_scroll)
	_board_scroll.add_child(_board)
	_board.size_flags_vertical = Control.SIZE_EXPAND_FILL


func tab(title: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	_tabs.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(content)
	_form_tabs[title] = content
	return content


func field(parent: Node, section: String, key: String, caption: String, kind := "text") -> Control:
	if not _forms.has(section):
		_forms[section] = {}
	label(parent, caption, "TianxuanCaption")
	var input: Control
	match kind:
		"multiline", "labels":
			var text := TextEdit.new()
			text.custom_minimum_size.y = 110 * ui_scale
			text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
			text.text_changed.connect(_edited.bind(section))
			text.text_set.connect(_edited.bind(section))
			input = text
		"choice":
			var choice := OptionButton.new()
			choice.item_selected.connect(func(_index: int):
				if section == "field" and key == "key" and not _syncing:
					_syncing = true
					_forms.field.value.text = str(model.sections.get("work", {}).get("plan", {}).get("custom_fields", {}).get(choice.get_selected_metadata(), ""))
					_syncing = false
				_edited(section)
			)
			input = choice
		"number", "parent":
			var number := SpinBox.new()
			number.min_value = 0
			number.max_value = 100000000
			number.step = 1
			number.value_changed.connect(func(_value: float): _edited(section))
			input = number
		_:
			var text := LineEdit.new()
			text.max_length = 512
			text.text_changed.connect(func(_value: String): _edited(section))
			input = text
	input.name = "NativeIssue_" + section + "_" + key
	input.set_meta("field_kind", kind)
	input.set_meta("caption", caption)
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(input)
	_forms[section][key] = input
	return input


func save(parent: Node, section: String, caption: String) -> void:
	_conflicts[section] = label(parent, "", "TianxuanCaption")
	_review[section] = button(parent, tr("已比较服务器内容，保留草稿重新确认"), "NativeIssueReview_" + section, func(): model.review_draft(section))
	var node := button(parent, caption, "NativeIssueSave_" + section, func():
		if section == "create":
			model.create()
		elif section == "definition":
			model.define_field()
		else:
			model.submit(section)
	)
	node.theme_type_variation = "TianxuanPrimaryButton"
	_buttons[section] = node
	button(parent, tr("放弃此处草稿"), "NativeIssueDiscard_" + section, func():
		if not model.saving and model.pending().is_empty():
			controller.clear_draft(model.draft_key(section))
	)


func card(parent: Node, caption: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "TianxuanCard"
	parent.add_child(panel)
	var content := VBoxContainer.new()
	panel.add_child(content)
	label(content, caption, "TianxuanHeading")
	return content


func _build_detail() -> void:
	_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_editor)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_editor.add_child(scroll)
	scroll.add_child(_new_form)
	_new_form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field(_new_form, "create", "title", "工单标题")
	field(_new_form, "create", "module_id", "业务模块", "choice")
	field(_new_form, "create", "type", "类型")
	field(_new_form, "create", "body_md", "说明", "multiline")
	field(_new_form, "create", "acceptance", "验收条件", "multiline")
	save(_new_form, "create", "创建工单")
	_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_editor.add_child(_detail)
	_detail.add_child(_summary)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_child(_tabs)
	var overview := tab("概览")
	var body: Control = get_meta("markdown_script").new()
	body.name = "NativeIssueBody"
	body.set_meta("controller", controller)
	overview.add_child(body)
	var owner := card(overview, "归属")
	field(owner, "assignee", "assignee_id", "负责人", "choice")
	save(owner, "assignee", "更新负责人")
	field(owner, "module", "module_id", "业务模块", "choice")
	save(owner, "module", "更新模块")
	var classification := card(overview, "分类")
	field(classification, "classification", "type", "类型")
	field(classification, "classification", "labels", "标签（每行一个）", "labels")
	save(classification, "classification", "保存分类")
	_target_form = card(overview, "任务阶段目标")
	field(_target_form, "target", "stage", "目标阶段")
	field(_target_form, "target", "criteria", "可验证的到达条件", "multiline")
	save(_target_form, "target", "保存阶段目标")
	_target_form.add_child(_task_actions)
	var planning := tab("计划与工时")
	var plan := card(planning, "计划")
	for entry in [["iteration", "迭代"], ["milestone", "里程碑"], ["roadmap", "路线图"], ["status", "计划说明"]]:
		field(plan, "plan", entry[0], entry[1])
	field(plan, "plan", "estimated_minutes", "预计工时（分钟）", "number")
	save(plan, "plan", "保存计划")
	var custom := card(planning, "项目字段")
	field(custom, "field", "key", "自定义文本字段", "choice")
	var custom_value: LineEdit = field(custom, "field", "value", "字段值")
	custom_value.max_length = 2000
	save(custom, "field", "保存字段值")
	field(custom, "definition", "key", "新文本字段标识（字母开头）")
	field(custom, "definition", "label", "字段名称")
	save(custom, "definition", "定义项目字段")
	var time := card(planning, "工时")
	field(time, "log", "minutes", "本次工时（分钟）", "number")
	field(time, "log", "note", "工作内容")
	save(time, "log", "登记工时")
	planning.add_child(_logs)
	var discussion := tab("讨论")
	discussion.add_child(_comments)
	field(discussion, "comment", "body", "新评论", "multiline")
	field(discussion, "comment", "parent_id", "回复评论", "choice")
	save(discussion, "comment", "发表回复")
	var relations := tab("关联")
	relations.add_child(_relationships)
	field(relations, "hierarchy", "parent_number", "父工单编号（0 表示取消父工单）", "parent")
	save(relations, "hierarchy", "保存父子关系")
	label(relations, "上游工单编号", "TianxuanCaption")
	_dependency.min_value = 1
	_dependency.max_value = 2147483647
	_dependency.step = 1
	_dependency.name = "NativeIssueDependencyNumber"
	relations.add_child(_dependency)
	_add_dependency.text = "添加上游依赖"
	_add_dependency.name = "NativeIssueAddDependency"
	_add_dependency.pressed.connect(func(): model.add_dependency(int(_dependency.value), model.action_snapshot()))
	relations.add_child(_add_dependency)
	var flow_tab := tab("流程与验收")
	flow_tab.add_child(_flow)
	_flow.add_child(_history)
	var flow_editor: Control = get_meta("flow_script").new()
	flow_editor.name = "NativeIssueFlowEditor"
	flow_editor.set_meta("controller", controller)
	flow_editor.set_meta("ui_scale", ui_scale)
	flow_tab.add_child(flow_editor)
	var assets: Control = get_meta("asset_script").new()
	assets.set_meta("controller", controller)
	assets.set_meta("ui_scale", ui_scale)
	var asset_tab := tab("附件与候选")
	asset_tab.add_child(assets)
	var submit_asset := card(asset_tab, "提交美术修订")
	var kind: OptionButton = field(submit_asset, "asset", "kind", "资产类型", "choice")
	for pair in [["concept", "概念图"], ["model", "三维模型"]]:
		kind.add_item(pair[1])
		kind.set_item_metadata(kind.item_count - 1, pair[0])
	field(submit_asset, "asset", "module", "原生模块名称")
	field(submit_asset, "asset", "revision", "固定修订 ID")
	field(submit_asset, "asset", "path", "修订中的资产路径")
	save(submit_asset, "asset", "提交人工确认")


func _build_confirmation() -> void:
	_confirmation.title = "确认工单操作"
	_confirmation.dialog_text = ""
	var content := VBoxContainer.new()
	content.custom_minimum_size.x = 320 * ui_scale
	_confirmation.add_child(content)
	label(content, "本次判断与当前工单、内容版本和交付物版本绑定。", "TianxuanCaption")
	_evidence.tooltip_text = "选择本工单中作为验收证据的评论"
	_evidence.item_selected.connect(func(_index: int): _confirmation.get_ok_button().disabled = _evidence.get_selected_metadata() == null)
	content.add_child(_evidence)
	_confirmation.confirmed.connect(func():
		if _intent.is_empty():
			return
		var values: Dictionary = _intent.values.duplicate(true)
		if _intent.operation == "accept":
			if _evidence.selected < 0 or _evidence.get_selected_metadata() == null:
				return
			values.comment = _evidence.get_selected_metadata()
		model.action(_intent.operation, values, _intent.snapshot)
		_intent.clear()
	)
	add_child(_confirmation)


func _confirm(operation: String, values: Dictionary, caption: String) -> void:
	_intent = {"operation": operation, "values": values.duplicate(true), "snapshot": model.action_snapshot()}
	_evidence.visible = operation == "accept"
	_choices(_evidence, model.sections.get("comments", {}).get("comments", []), "请选择验收证据评论", "id", "body")
	_confirmation.get_ok_button().disabled = operation == "accept"
	_confirmation.title = "%s · #%d" % [caption, int(model.detail.get("number", 0))]
	_confirmation.get_ok_button().text = caption
	_confirmation.popup_centered()


func _open(id: String) -> void:
	if not model.saving:
		_browsing = false
		model.open(id)


func _search() -> void:
	model.refresh_list({"q": _query.text, "label": _label_query.text, "status": _status_filter.get_selected_metadata()})


func _refresh() -> void:
	if controller.identity().is_empty():
		return
	_catalog_ready = true
	model.load_catalog()
	model.refresh_list(model.filters)
	if not model.selected.is_empty():
		model.refresh()


func _edited(section: String) -> void:
	if _syncing:
		return
	var values := {}
	for key in _forms[section]:
		var input: Control = _forms[section][key]
		match str(input.get_meta("field_kind")):
			"choice":
				values[key] = input.get_selected_metadata() if input.selected >= 0 else null
			"number", "parent":
				values[key] = int(input.value)
				if input.get_meta("field_kind") == "parent" and input.value == 0:
					values[key] = null
			"labels":
				values[key] = []
				for entry in input.text.split("\n", false):
					if not entry.strip_edges().is_empty():
						values[key].append(entry.strip_edges())
			_:
				values[key] = input.text
	model.edit(section, values)


func _choices(input: OptionButton, entries: Array, empty: String, key := "id", title := "name") -> void:
	input.clear()
	if not empty.is_empty():
		input.add_item(empty)
		input.set_item_metadata(0, null)
	for entry in entries:
		input.add_item(str(entry.get(title, entry.get(key, ""))).left(100))
		input.set_item_auto_translate_mode(input.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		input.set_item_metadata(input.item_count - 1, entry.get(key))


func _render() -> void:
	if not is_node_ready():
		return
	_syncing = true
	var context: String = controller.session.scope_key() + ":" + model.selected
	var switched: bool = context != _context
	if switched:
		_context = context
		_confirmation.hide()
		_intent.clear()
		_detail_signature = ""
		if controller.identity().is_empty():
			_query.clear()
			_label_query.clear()
			_status_filter.select(0)
			_catalog_ready = false
		_dependency.value = 1
	_browse.visible = _browsing
	_editor.visible = not _browsing
	_new_form.get_parent().visible = model.selected.is_empty()
	_detail.visible = not model.selected.is_empty()
	var pending: Dictionary = model.pending()
	_retry.visible = not pending.is_empty() and pending.get("replayable", false)
	_ack.visible = not pending.is_empty() and not pending.get("replayable", false)
	_retry.disabled = model.saving
	_ack.disabled = model.saving or model.loading
	_status.text = tr(model.status)
	if _browsing:
		_status.text = str(model.section_errors.get("list", tr("正在读取工单…") if model.listing else tr("%d 个工单") % model.items.size()))
	elif model.loading:
		_status.text = "正在读取工单与关联信息…"
	elif not pending.is_empty() and _status.text.is_empty():
		_status.text = "存在待核对的写入请求，草稿已保留。"
	_render_catalog()
	_render_list()
	_render_detail()
	var defaults := _defaults()
	var target_writable: bool = model.detail.get("design_source") is Dictionary and controller.identity().get("id") == (model.detail.assignee.id if model.detail.get("assignee") is Dictionary else model.detail.get("created_by"))
	_target_form.get_parent().visible = model.detail.get("design_source") is Dictionary
	_add_dependency.disabled = not model.editable() or not model.sections.has("flow") or model.detail.get("status") in ["done", "cancelled"] or model.sections.get("lifecycle", {}).get("managed", false)
	_dependency.editable = not _add_dependency.disabled
	for section in _forms:
		var draft: Dictionary = model.draft(section)
		var values: Dictionary = draft.get("values", defaults.get(section, {}))
		for key in _forms[section]:
			var input: Control = _forms[section][key]
			var value: Variant = values.get(key)
			var enabled: bool = model.editable() and (section != "target" or target_writable)
			if input is OptionButton:
				input.disabled = not enabled or input.item_count == 0
				if section == "field" and key == "key" and not draft.is_empty():
					input.disabled = true
				input.select(-1)
				for index in input.item_count:
					if input.get_item_metadata(index) == value:
						input.select(index)
			elif input is SpinBox:
				input.editable = enabled
				if switched or not input.get_line_edit().has_focus():
					input.value = int(value) if value != null else 0
			else:
				input.editable = enabled
				var text := "\n".join(value) if value is Array else (str(value) if value != null else "")
				if input.text != text and (switched or not input.has_focus()):
					input.text = text
		if _buttons.has(section):
			_buttons[section].disabled = not model.editable() or draft.is_empty() or (section == "target" and not target_writable)
			var outdated: bool = model.draft_outdated(section)
			_review[section].visible = outdated
			_review[section].disabled = not model.editable()
			_conflicts[section].visible = outdated
			if outdated:
				var lines: Array[String] = ["服务器已更新。以下是当前内容；上方保留你的草稿："]
				for key in _forms[section]:
					var remote: Variant = defaults.get(section, {}).get(key)
					lines.append("%s：%s" % [_forms[section][key].get_meta("caption"), "、".join(remote) if remote is Array else str(remote) if remote != null else tr("未设置")])
				_conflicts[section].text = "\n".join(lines)
				_buttons[section].disabled = true
			if section in ["plan", "log", "field", "asset"]:
				_buttons[section].disabled = _buttons[section].disabled or not model.sections.has("work")
	_syncing = false


func _render_catalog() -> void:
	var signature := JSON.stringify([model.catalog, model.sections.get("comments", {})])
	if signature == _catalog_signature:
		return
	_catalog_signature = signature
	var modules: Array = model.catalog.get("modules", {}).get("modules", [])
	_choices(_forms.create.module_id, modules, "请选择模块")
	_choices(_forms.module.module_id, modules, "请选择模块")
	_choices(_forms.assignee.assignee_id, model.catalog.get("users", {}).get("users", []), "未分配")
	_choices(_forms.field.key, model.catalog.get("fields", {}).get("fields", []), "请选择字段", "key", "label")
	_choices(_forms.comment.parent_id, model.sections.get("comments", {}).get("comments", []), "独立评论", "id", "body")


func _defaults() -> Dictionary:
	var detail: Dictionary = model.detail
	var parent: Variant = model.sections.get("hierarchy", {}).get("parent")
	var fields: Dictionary = model.sections.get("work", {}).get("plan", {}).get("custom_fields", {})
	var field_key: Variant = _forms.field.key.get_selected_metadata() if _forms.field.key.selected >= 0 else null
	return {
		"create": {"type": "task"},
		"asset": {"kind": "concept"},
		"classification": {"type": detail.get("type", ""), "labels": detail.get("labels", [])},
		"assignee": {"assignee_id": detail.assignee.id if detail.get("assignee") is Dictionary else null},
		"module": {"module_id": detail.get("module_id")},
		"plan": model.sections.get("work", {}).get("plan", {}),
		"hierarchy": {"parent_number": parent.number if parent is Dictionary else null},
		"field": {"key": field_key, "value": fields.get(field_key, "")},
		"target": detail.task_target if detail.get("task_target") is Dictionary else {},
	}


func _render_list() -> void:
	_list.visible = _view_mode.selected != 1
	_board_scroll.visible = not _list.visible
	var signature := JSON.stringify([model.items, model.catalog.get("roadmap"), model.catalog.get("judgments"), _view_mode.selected])
	if signature == _list_signature:
		return
	_list_signature = signature
	_list.clear()
	clear(_board)
	var root := _list.create_item()
	var rows: Array = model.items
	if _view_mode.selected == 2:
		rows = model.catalog.get("roadmap", {}).get("items", [])
	elif _view_mode.selected == 3:
		rows = model.catalog.get("judgments", {}).get("items", [])
	var columns := {}
	var groups := {}
	for entry in rows:
		var status := str(entry.get("status", ""))
		var title := "%s%s" % ["#%d · " % int(entry.number) if entry.has("number") else "", entry.get("title", tr("工单"))]
		var group: TreeItem = root
		if _view_mode.selected == 2:
			var plan: Dictionary = entry.get("plan", {})
			var group_key := "%s / %s / %s" % [plan.get("roadmap", ""), plan.get("milestone", ""), plan.get("iteration", "")]
			if not groups.has(group_key):
				group = _list.create_item(root)
				group.set_text(0, group_key if group_key != " /  / " else "未排期")
				groups[group_key] = group
			group = groups[group_key]
		var item := _list.create_item(group)
		item.set_text(0, title)
		item.set_auto_translate_mode(0, Node.AUTO_TRANSLATE_MODE_DISABLED)
		item.set_tooltip_text(0, title)
		item.set_metadata(0, str(entry.get("issue_id", entry.get("id", ""))))
		item.set_text(1, STATES.get(status, status))
		if entry.has("progress"):
			item.set_text(2, "%d%%" % int(entry.progress))
		if _view_mode.selected != 1:
			continue
		if not columns.has(status):
			var column := VBoxContainer.new()
			column.custom_minimum_size.x = 250 * ui_scale
			_board.add_child(column)
			label(column, STATES.get(status, status), "TianxuanHeading")
			columns[status] = column
		var card := PanelContainer.new()
		card.theme_type_variation = "TianxuanCard"
		columns[status].add_child(card)
		var content := VBoxContainer.new()
		card.add_child(content)
		label(content, title)
		label(content, str(entry.get("type", "")), "TianxuanCaption")
		button(content, "查看详情", "OpenIssueCard", _open.bind(str(entry.id)))
	if rows.is_empty():
		var empty := _list.create_item(root)
		empty.set_text(0, "没有匹配的工单")
		empty.set_selectable(0, false)


func _render_detail() -> void:
	var signature := JSON.stringify([model.detail, model.sections, model.section_errors, model.editable()])
	if signature == _detail_signature:
		return
	_detail_signature = signature
	for parent in [_summary, _comments, _relationships, _logs, _task_actions]:
		clear(parent)
	# Preserve the history container while rebuilding action controls.
	for child in _flow.get_children():
		if child != _history:
			_flow.remove_child(child)
			child.queue_free()
	clear(_history)
	var detail: Dictionary = model.detail
	if detail.is_empty():
		_form_tabs["概览"].get_node("NativeIssueBody").set_markdown("")
		return
	label(_summary, "#%d · %s" % [int(detail.number), detail.title], "TianxuanHeading")
	var owner := str(detail.assignee.name) if detail.get("assignee") is Dictionary else "未分配"
	label(_summary, "%s  ·  %s  ·  %s" % [tr(STATES.get(detail.status, detail.status)), owner, detail.get("type", "")], "TianxuanCaption")
	var confirmation: Dictionary = detail.task_confirmation if detail.get("task_confirmation") is Dictionary else {}
	if not confirmation.is_empty():
		var confirmed: bool = confirmation.get("status") == "confirmed"
		label(_task_actions, "已确认启动" if confirmed else "待负责人逐项核对目标后确认启动", "TianxuanCaption")
		var writable: bool = model.editable() and confirmation.get("responsible_user") == controller.identity().get("id") and detail.get("task_target", {}).get("status") == "defined"
		if not confirmed and detail.status in ["done", "cancelled"]:
			writable = false
		button(_task_actions, "撤销本项确认" if confirmed else "核对并确认启动本项", "NativeIssueConfirmTarget", _confirm.bind("revoke_task" if confirmed else "confirm_task", {}, "撤销本项确认" if confirmed else "确认启动本项")).disabled = not writable
	_form_tabs["概览"].get_node("NativeIssueBody").set_markdown(str(detail.get("body_md", "")) + tr("\n\n## 验收条件\n") + str(detail.get("acceptance", "")))
	for entry in model.sections.get("comments", {}).get("comments", []):
		var card := PanelContainer.new()
		card.theme_type_variation = "TianxuanCard"
		_comments.add_child(card)
		var content := VBoxContainer.new()
		card.add_child(content)
		label(content, "%s · %s%s" % [entry.get("author", entry.get("created_by", "")), entry.get("created_at", ""), tr(" · 回复") if entry.get("parent_id") != null else ""], "TianxuanCaption")
		var markdown: Control = get_meta("markdown_script").new()
		markdown.set_meta("controller", controller)
		content.add_child(markdown)
		markdown.set_markdown(str(entry.get("body", "")))
	var hierarchy: Dictionary = model.sections.get("hierarchy", {})
	if hierarchy.get("parent") is Dictionary:
		_issue_link(_relationships, "父工单", hierarchy.parent)
	for child in hierarchy.get("children", []):
		_issue_link(_relationships, "子工单", child)
	if detail.get("requirement_id") is String:
		button(_relationships, "查看来源需求", "NativeIssueRequirement", func(): controller.navigate("documents", detail.requirement_id))
	if detail.get("design_source") is Dictionary:
		button(_relationships, tr("阅读来源设计 · v%d") % int(detail.design_source.version), "NativeIssueSource", func(): controller.navigate("documents", detail.design_source.document_id))
	for link in model.sections.get("external", {}).get("links", []):
		var url := str(link.get("external_id", ""))
		if url.begins_with("https://") or url.begins_with("http://"):
			button(_relationships, tr("打开关联 · ") + str(link.get("system", "")), "NativeIssueExternal", func(): OS.shell_open(url))
	var work: Dictionary = model.sections.get("work", {})
	label(_logs, tr("已登记 %d 分钟") % int(work.get("logged_minutes", 0)), "TianxuanHeading")
	for entry in work.get("logs", []):
		label(_logs, tr("%d 分钟 · %s\n%s") % [int(entry.minutes), entry.note, entry.get("created_at", "")], "TianxuanCaption")
	var flow: Dictionary = model.sections.get("flow", {})
	var lifecycle: Dictionary = model.sections.get("lifecycle", {})
	label(_flow, tr("流程进度 %d%%") % int(flow.get("progress", 0)), "TianxuanHeading")
	var progress := ProgressBar.new()
	progress.value = float(flow.get("progress", 0))
	_flow.add_child(progress)
	var human := false
	for stage in flow.get("stages", []):
		if stage.id == detail.status:
			human = bool(stage.human)
	for dep in flow.get("dependencies", []):
		_issue_link(_relationships, tr("上游 · ") + (tr("已验收") if dep.get("accepted", false) else tr("尚未验收")), dep)
		var ids: Array = []
		for other in flow.get("dependencies", []):
			if other.id != dep.id:
				ids.append(other.id)
		button(_relationships, "移除此上游依赖", "NativeIssueRemoveDependency", _confirm.bind("dependencies", {"dependencies": ids}, "移除上游依赖")).disabled = not model.editable() or lifecycle.get("managed", false)
	var execution: Dictionary = detail.execution_progress if detail.get("execution_progress") is Dictionary else {}
	if not execution.is_empty():
		label(_flow, tr("运行 · ") + str(execution.get("id", "")), "TianxuanHeading")
		label(_flow, str(execution.get("control", {}).get("summary", "")), "TianxuanCaption")
		for operation in detail.get("execution_control_actions", []):
			if operation not in ["pause", "resume", "cancel"]:
				continue
			var caption: String = {"pause": "完成当前步骤后暂停", "resume": "核对后恢复运行", "cancel": "取消此运行"}[operation]
			button(_flow, caption, "NativeIssueRun_" + operation, _confirm.bind(operation, {}, caption)).disabled = not model.editable()
	if lifecycle.get("managed", false):
		label(_flow, "此工单由执行服务管理，状态随真实执行更新。", "TianxuanCaption")
	else:
		for edge in flow.get("edges", []):
			if edge.from != detail.status or edge.to == "done":
				continue
			var target := str(edge.to)
			var caption: String = (tr("人工确认 → ") if human else tr("推进到 ")) + tr(STATES.get(target, target))
			button(_flow, caption, "NativeIssueAdvance_" + target, _confirm.bind("judge" if human else "advance", {"to_status": target}, caption)).disabled = not model.editable()
	if not lifecycle.is_empty():
		label(_flow, "当前版本已验收" if lifecycle.get("accepted", false) else "当前版本尚未验收", "TianxuanCaption")
		if not lifecycle.get("accepted", false) and lifecycle.get("can_close", false) and not lifecycle.get("managed", false):
			button(_flow, "验收当前版本", "NativeIssueAccept", _confirm.bind("accept", {}, "验收当前版本")).disabled = not model.editable()
		if lifecycle.get("can_close", false):
			button(_flow, "关闭工单", "NativeIssueClose", _confirm.bind("close", {}, "关闭工单")).disabled = not model.editable() or not lifecycle.get("accepted", false)
		if not str(lifecycle.get("reopen_to", "")).is_empty():
			button(_flow, "重新打开 / 退回", "NativeIssueReopen", _confirm.bind("reopen", {}, "重新打开 / 退回")).disabled = not model.editable()
	for entry in lifecycle.get("history", []):
		label(_history, tr("%s · %s\n证据：%s") % [entry.get("kind", entry.get("action", "")), entry.get("created_at", ""), entry.get("evidence", "")], "TianxuanCaption")
	_flow.move_child(_history, _flow.get_child_count() - 1)
	for section in ["work", "flow", "hierarchy", "comments", "lifecycle"]:
		if model.section_errors.has(section):
			label(_summary, "%s：%s" % [section, model.section_errors[section]], "TianxuanCaption")


func _issue_link(parent: Node, prefix: String, issue: Dictionary) -> void:
	button(parent, "%s · %s%s" % [prefix, "#%d " % int(issue.number) if issue.has("number") else "", issue.get("title", tr("工单"))], "NativeLinkedIssue", _open.bind(str(issue.id)))


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_detail_signature = ""
		_list_signature = ""
		_catalog_signature = ""
		_render()
