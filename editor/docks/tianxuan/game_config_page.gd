@tool
extends VBoxContainer

var controller: Node
var model: Node
var _status := Label.new()
var _projects := OptionButton.new()
var _query := LineEdit.new()
var _title := LineEdit.new()
var _save := Button.new()
var _ack := Button.new()
var _tree := Tree.new()
var _tabs := TabContainer.new()
var _editor := VBoxContainer.new()
var _comparison := VBoxContainer.new()
var _history := VBoxContainer.new()
var _clients := VBoxContainer.new()
var _validation := Label.new()
var _filter := OptionButton.new()
var _feature := ""
var _entry := ""
var _fields := {}
var _choices := {}
var _conflict_version := 0
var _comparison_snapshot := {}
var _context := ""
var _tree_signature := ""
var _catalog_signature := ""
var _editor_signature := ""
var _history_signature := ""
var _client_signature := ""
var _syncing := false
var _add := ConfirmationDialog.new()
var _add_id := LineEdit.new()
var _add_name := LineEdit.new()
var _add_feature := ""
var _confirm := ConfirmationDialog.new()
var _intent := {}


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.game_config
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	label(self, "游戏配置", "TianxuanTitle" if not get_meta("compact", false) else "TianxuanHeading")
	label(self, "按功能组织参数与内容。字段编辑结束后保存；客户端回报应用结果后显示生效。")
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	_projects.fit_to_longest_item = false
	_projects.custom_minimum_size.x = 220 * float(get_meta("ui_scale", 1.0))
	_projects.item_selected.connect(func(index: int): model.open(str(_projects.get_item_metadata(index))))
	toolbar.add_child(_projects)
	button(toolbar, "新建项目", "NativeConfigNew", func(): model.open(""))
	button(toolbar, "刷新", "NativeConfigRefresh", func(): model.refresh_list(); model.refresh())
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	_ack.text = "已核对项目列表，恢复创建表单"
	_ack.pressed.connect(func(): model.acknowledge_create())
	add_child(_ack)
	label(self, "项目名称")
	_title.name = "NativeConfigTitle"
	_title.max_length = 200
	_title.text_changed.connect(func(text: String):
		if not _syncing:
			model.field("", "", "title", text)
	)
	_title.focus_exited.connect(_autosave)
	add_child(_title)
	var actions := HFlowContainer.new()
	add_child(actions)
	_save = button(actions, "保存配置", "NativeConfigSave", func(): model.save())
	_save.theme_type_variation = "TianxuanPrimaryButton"
	button(actions, "放弃本机草稿", "NativeConfigDiscard", func(): _ask("discard", {}, "放弃此项目的本机草稿并显示服务端版本。"))
	button(actions, "关联文档", "NativeConfigDocument", func():
		if not model.selected.is_empty():
			controller.navigate("documents", model.selected)
	)
	_validation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_validation.theme_type_variation = "TianxuanCaption"
	add_child(_validation)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	var fields_page := tab("参数与内容")
	var filters := HFlowContainer.new()
	fields_page.add_child(filters)
	_query.placeholder_text = "搜索名称或稳定 ID"
	_query.text_changed.connect(func(_value: String): _render_tree())
	filters.add_child(_query)
	for item in [["all", "全部条目"], ["parameter", "参数"], ["content", "内容"]]:
		_filter.add_item(item[1])
		_filter.set_item_metadata(_filter.item_count - 1, item[0])
	_filter.item_selected.connect(func(_index: int): _render_tree())
	filters.add_child(_filter)
	button(filters, "添加功能", "NativeConfigAddFeature", _ask_add.bind(false))
	button(filters, "添加条目", "NativeConfigAddEntry", _ask_add.bind(true))
	button(filters, "删除所选", "NativeConfigRemove", func(): _ask("remove", {"feature": _feature, "entry": _entry}, "删除所选功能或条目；保存后生成新版本。"))
	_tree.hide_root = true
	_tree.custom_minimum_size.y = 170 * float(get_meta("ui_scale", 1.0))
	_tree.item_selected.connect(func():
		if not _syncing and _tree.get_selected():
			var value: Dictionary = _tree.get_selected().get_metadata(0)
			_feature = value.feature
			_entry = value.entry
			_render.call_deferred()
	)
	fields_page.add_child(_tree)
	fields_page.add_child(_editor)
	var conflicts_page := tab("比较与冲突")
	button(conflicts_page, "比较本机与服务端修改", "NativeConfigCompare", func(): model.compare(); _render_conflicts())
	conflicts_page.add_child(_comparison)
	button(conflicts_page, "采用核对后的合并草稿", "NativeConfigMerge", func():
		if _comparison_snapshot == model.snapshot():
			model.compare(_choices, true)
			_render_conflicts()
	)
	var history_page := tab("版本记录")
	button(history_page, "刷新版本", "NativeConfigHistory", func(): model.history())
	history_page.add_child(_history)
	var clients_page := tab("在线客户端")
	label(clients_page, "保存不等于生效。下方只显示服务端收到的当前版本应用回执。")
	clients_page.add_child(_clients)
	_add.title = "添加配置项"
	var box := VBoxContainer.new()
	_add.add_child(box)
	label(box, "稳定 ID · 字母开头，最多 64 位")
	_add_id.name = "NativeConfigItemId"
	_add_id.max_length = 64
	box.add_child(_add_id)
	label(box, "显示名称")
	_add_name.name = "NativeConfigItemName"
	_add_name.max_length = 200
	box.add_child(_add_name)
	_add.confirmed.connect(func():
		model.add_item(_add_feature, _add_id.text, _add_name.text)
		_feature = _add_id.text if _add_feature.is_empty() else _add_feature
		_entry = "" if _add_feature.is_empty() else _add_id.text
		_render()
		_autosave()
	)
	add_child(_add)
	_confirm.confirmed.connect(_confirmed)
	add_child(_confirm)
	model.changed.connect(_render)
	_render()
	model.refresh_list()


func label(parent: Node, text: String, variation := "TianxuanCaption") -> Label:
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


func tab(caption: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = caption
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	_tabs.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(box)
	return box


func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func _autosave() -> void:
	if not _syncing and not model.selected.is_empty() and not model.draft().is_empty() and not model.outdated():
		model.save()


func _ask_add(entry: bool) -> void:
	if not model.editable() or (entry and _feature.is_empty()):
		return
	_add_feature = _feature if entry else ""
	_add_id.clear()
	_add_name.clear()
	_add.title = "添加条目" if entry else "添加功能"
	_add.popup_centered(Vector2i(420, 180) * float(get_meta("ui_scale", 1.0)))


func _ask(operation: String, values: Dictionary, text: String) -> void:
	_intent = {"operation": operation, "values": values, "expected": model.snapshot()}
	_confirm.dialog_text = text
	_confirm.popup_centered()


func _confirmed() -> void:
	if _intent.is_empty() or _intent.expected != model.snapshot():
		return
	match _intent.operation:
		"discard": model.discard()
		"remove": model.remove_item(_intent.values.feature, _intent.values.entry); _autosave()
		"restore": model.restore(int(_intent.values.version), _intent.expected)


func _render_tree() -> void:
	var value: Dictionary = model.values()
	var signature := JSON.stringify([value.features, _query.text, _filter.get_selected_metadata(), _feature, _entry])
	if signature == _tree_signature:
		return
	_tree_signature = signature
	var was_syncing := _syncing
	_syncing = true
	_tree.clear()
	var root := _tree.create_item()
	var query := _query.text.to_lower()
	for feature in value.features:
		var matching: Array = feature.entries.filter(func(entry: Dictionary): return (_filter.get_selected_metadata() == "all" or entry.kind == _filter.get_selected_metadata()) and (query.is_empty() or query in (feature.name + feature.id + entry.name + entry.id).to_lower()))
		if matching.is_empty() and not query.is_empty() and not query in (feature.name + feature.id).to_lower():
			continue
		var row := _tree.create_item(root)
		row.set_text(0, "%s · %s" % [feature.name, feature.id])
		row.set_metadata(0, {"feature": feature.id, "entry": ""})
		if _feature == feature.id and _entry.is_empty():
			row.select(0)
		for entry in matching:
			var item := _tree.create_item(row)
			item.set_text(0, "%s · %s" % [entry.name, entry.id])
			item.set_metadata(0, {"feature": feature.id, "entry": entry.id})
			if _feature == feature.id and _entry == entry.id:
				item.select(0)
	_syncing = was_syncing


func _field(name: String, caption: String, type := "line", options := []) -> void:
	label(_editor, caption)
	var control: Control
	if type == "choice":
		var select := OptionButton.new()
		for option in options:
			select.add_item(str(option[1]))
			select.set_item_metadata(select.item_count - 1, option[0])
		select.item_selected.connect(func(index: int):
			if not _syncing:
				model.field(_feature, _entry, name, select.get_item_metadata(index))
				_autosave()
		)
		control = select
	elif type == "text":
		var edit := TextEdit.new()
		edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		edit.custom_minimum_size.y = 95 * float(get_meta("ui_scale", 1.0))
		var edited := func():
			if not _syncing:
				model.field(_feature, _entry, name, edit.text)
		edit.text_changed.connect(edited)
		edit.text_set.connect(edited)
		edit.focus_exited.connect(_autosave)
		control = edit
	else:
		var edit := LineEdit.new()
		edit.max_length = 4096
		edit.text_changed.connect(func(text: String):
			if not _syncing:
				model.field(_feature, _entry, name, text)
		)
		edit.focus_exited.connect(_autosave)
		control = edit
	control.name = "NativeConfigField_" + name
	_fields[name] = control
	_editor.add_child(control)


func _render_editor(switched: bool) -> void:
	var item := {}
	var features: Array = model.values().features
	for feature in features:
		if feature.id == _feature:
			item = feature
			if not _entry.is_empty():
				item = {}
				for entry in feature.entries:
					if entry.id == _entry:
						item = entry
	var references := [["", "选择引用条目"]]
	for feature in features:
		for entry in feature.entries:
			references.append([JSON.stringify({"feature_id": feature.id, "entry_id": entry.id}), feature.name + " / " + entry.name])
	var signature := JSON.stringify([_context, _feature, _entry, item.get("type"), item.is_empty()])
	if signature != _editor_signature:
		_editor_signature = signature
		_fields.clear()
		clear(_editor)
		if item.is_empty():
			label(_editor, "选择一个功能或条目，或添加新的配置项。")
		else:
			label(_editor, _feature + ("/" + _entry if not _entry.is_empty() else ""), "TianxuanHeading")
			_field("name", "显示名称")
			_field("description", "说明", "text")
			if _entry.is_empty():
				_field("document_id", "关联文档 ID（可选）")
			else:
				_field("kind", "分类", "choice", [["parameter", "参数"], ["content", "内容"]])
				_field("type", "类型", "choice", [["number", "数值"], ["integer", "整数"], ["boolean", "布尔"], ["string", "文本"], ["enum", "枚举"], ["json", "JSON"], ["reference", "引用"]])
				if item.type == "enum":
					_field("options", "枚举选项 · 每行一项", "text")
				for field in ["value", "default"]:
					var caption := "当前值" if field == "value" else "默认值"
					match str(item.type):
						"boolean": _field(field, caption, "choice", [["false", "否"], ["true", "是"]])
						"reference": _field(field, caption, "choice", references)
						"enum":
							var options: Array = [["", "请选择"]]
							for option in str(item.options).split("\n", false):
								options.append([option, option])
							_field(field, caption, "choice", options)
						"json", "string": _field(field, caption, "text")
						_: _field(field, caption)
				if item.type in ["number", "integer"]:
					_field("min", "最小值（可选）")
					_field("max", "最大值（可选）")
	for name in _fields:
		var control: Control = _fields[name]
		var value := str(item.get(name, ""))
		if control is OptionButton:
			control.disabled = not model.editable()
			if name in ["value", "default"] and item.get("type") in ["enum", "reference"]:
				control.clear()
				var options: Array = references if item.type == "reference" else [["", "请选择"]]
				if item.type == "enum":
					for option in str(item.options).split("\n", false):
						options.append([option, option])
				for option in options:
					control.add_item(str(option[1]))
					control.set_item_metadata(control.item_count - 1, option[0])
			control.select(-1)
			for index in control.item_count:
				var option: String = control.get_item_metadata(index)
				if option == value or (item.get("type") == "reference" and name in ["value", "default"] and JSON.parse_string(option) == JSON.parse_string(value)):
					control.select(index)
		else:
			control.editable = model.editable()
			if control.text != value and (switched or not control.has_focus()):
				control.text = value


func _render_conflicts() -> void:
	clear(_comparison)
	_comparison_snapshot = model.snapshot()
	if not model.outdated():
		label(_comparison, "当前没有需要合并的远程版本。")
		return
	if _conflict_version != int(model.project.version):
		_choices.clear()
		_conflict_version = int(model.project.version)
	label(_comparison, tr("本机基于 v%d · 服务端 v%d。不同字段的修改会自动合并；同一字段需逐项选择。") % [int(model.draft().base.version), _conflict_version])
	for conflict in model.conflicts:
		label(_comparison, str(conflict.path), "TianxuanHeading")
		label(_comparison, tr("本机：") + str(conflict.local) + tr("\n服务端：") + str(conflict.remote))
		var select := OptionButton.new()
		for option in [["", "请选择保留内容"], ["local", "保留本机"], ["remote", "采用服务端"]]:
			select.add_item(option[1])
			select.set_item_metadata(select.item_count - 1, option[0])
		select.item_selected.connect(func(index: int): _choices[conflict.path] = select.get_item_metadata(index))
		_comparison.add_child(select)


func _render() -> void:
	_syncing = true
	var context: String = controller.session.scope_key() + ":" + model.selected
	var switched := context != _context
	if switched:
		_context = context
		_feature = ""
		_entry = ""
		_choices.clear()
		_add.hide()
		_confirm.hide()
		_intent.clear()
		clear(_comparison)
	var value: Dictionary = model.values()
	_title.editable = model.editable()
	if switched or not _title.has_focus():
		_title.text = value.title
	_status.text = "%s · v%d%s\n%s" % [model.connection, int(model.project.get("version", 0)), tr(" · 本机草稿") if not model.draft().is_empty() else "", model.status]
	if model.outdated():
		_status.text += tr("\n服务端已有新版本，请到「比较与冲突」核对后保存。")
	_save.disabled = not model.editable() or model.draft().is_empty() or model.outdated()
	_save.text = "创建项目" if model.selected.is_empty() else "保存配置"
	_ack.visible = model.selected.is_empty() and model.draft().has("submission")
	_ack.disabled = model.saving
	_projects.disabled = model.saving or model.draft().has("submission")
	_validation.text = "\n".join(model.validation)
	var signature := JSON.stringify([model.projects, model.selected])
	if signature != _catalog_signature:
		_catalog_signature = signature
		_projects.clear()
		_projects.add_item("新项目")
		_projects.set_item_metadata(0, "")
		for project in model.projects:
			_projects.add_item("%s · v%d" % [project.title, int(project.version)])
			_projects.set_item_metadata(_projects.item_count - 1, project.id)
			if project.id == model.selected:
				_projects.select(_projects.item_count - 1)
	_render_tree()
	_render_editor(switched)
	if _conflict_version != int(model.project.get("version", 0)):
		_choices.clear()
		clear(_comparison)
		label(_comparison, "点击比较，查看当前版本与本机草稿的差异。")
	var history_signature := JSON.stringify([_context, model.versions, model.editable(), model.draft().is_empty()])
	if history_signature != _history_signature:
		_history_signature = history_signature
		clear(_history)
		for version in model.versions:
			label(_history, "v%d · %s" % [int(version.version), str(version.get("created_at", ""))])
			button(_history, tr("恢复为此版本"), "NativeConfigRestore_%d" % int(version.version), _ask.bind("restore", {"version": version.version}, tr("将当前配置恢复为 v%d 的内容；会生成一个新版本。") % int(version.version))).disabled = not model.editable() or not model.draft().is_empty()
	var clients_signature := JSON.stringify([_context, model.clients, model.project.get("version", 0)])
	if clients_signature != _client_signature:
		_client_signature = clients_signature
		clear(_clients)
		if model.clients.is_empty():
			label(_clients, "尚无在线游戏客户端回执。")
		for client in model.clients:
			var state := str({"pending": "等待应用", "applied": "已应用", "failed": "应用失败"}.get(client.status, client.status))
			label(_clients, "%s · %s · v%d\n%s" % [client.name, state, int(client.version), client.get("error", "")])
	_syncing = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_client_signature = ""
		_editor_signature = ""
		_tree_signature = ""
		_catalog_signature = ""
		_history_signature = ""
		_render()
