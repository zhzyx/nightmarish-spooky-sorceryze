@tool
extends VBoxContainer

var controller: Node
var kind := "requirements"
var _query := LineEdit.new()
var _scope := OptionButton.new()
var _status := Label.new()
var _rows := VBoxContainer.new()
var _more := Button.new()
var _signature := ""
var _refresh := Button.new()


func _ready() -> void:
	controller = get_meta("controller")
	kind = str(get_meta("page_kind"))
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	var title := Label.new()
	title.text = {"requirements": "需求库", "search": "搜索工作区", "runs": "运行记录"}[kind]
	title.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	add_child(title)
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	_query.placeholder_text = "输入关键词…"
	_query.custom_minimum_size.x = 200 * float(get_meta("ui_scale", 1.0))
	_query.text_submitted.connect(func(_text: String): _load())
	toolbar.add_child(_query)
	_query.visible = kind == "search"
	for entry in [["all", "全部"], ["docs", "文档"], ["requirements", "需求"], ["issues", "工单"], ["repos", "仓库"]]:
		_scope.add_item(entry[1])
		_scope.set_item_metadata(_scope.item_count - 1, entry[0])
	toolbar.add_child(_scope)
	_scope.visible = kind == "search"
	_refresh.text = "搜索" if kind == "search" else "刷新"
	_refresh.pressed.connect(_load)
	toolbar.add_child(_refresh)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_rows)
	_more.text = "加载更多"
	_more.pressed.connect(func(): controller.load_library(kind, true))
	add_child(_more)
	controller.changed.connect(_changed)
	visibility_changed.connect(func():
		if is_visible_in_tree() and not controller.cache.has("library:" + kind) and kind != "search":
			_load()
	)
	_changed("")
	if kind != "search":
		_load()


func _load() -> void:
	if kind == "search" and _query.text.strip_edges().is_empty():
		_status.text = "输入关键词后搜索文档、需求、工单和仓库。"
		return
	controller.load_library(kind, false, _query.text.strip_edges(), str(_scope.get_selected_metadata()))


func _label(parent: Node, text: String, variation := "") -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.theme_type_variation = variation
	parent.add_child(label)
	return label


func _link(parent: Node, title: String, page: String, id: String, content := false) -> void:
	var button := Button.new()
	button.text = title
	if content:
		button.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	button.pressed.connect(func(): controller.navigate(page, id))
	parent.add_child(button)


func _changed(topic: String) -> void:
	if topic == "identity":
		_query.clear()
		_scope.select(0)
	var key := "library:" + kind
	var data: Dictionary = controller.cache.get(key, {})
	_refresh.disabled = controller.busy(key)
	_more.disabled = _refresh.disabled
	_more.visible = data.get("next_cursor") is String and not str(data.next_cursor).is_empty()
	_status.text = str(controller.errors.get(key, ""))
	if _status.text.is_empty():
		if controller.busy(key):
			_status.text = "正在读取…"
		elif data.get("available") == false:
			_status.text = "此工作区尚未配置执行服务。"
		elif data.is_empty():
			_status.text = "输入关键词开始搜索。" if kind == "search" else "暂无记录。"
		else:
			_status.text = tr("%d 条记录") % data.get("items", []).size()
	var signature := JSON.stringify([controller.session.scope_key(), data])
	if signature == _signature:
		return
	_signature = signature
	for child in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()
	for item in data.get("items", []):
		var card := PanelContainer.new()
		card.theme_type_variation = "TianxuanCard"
		_rows.add_child(card)
		var content := VBoxContainer.new()
		card.add_child(content)
		if kind == "runs":
			_label(content, str(item.title), "TianxuanHeading").auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
			_label(content, "已派发" if item.state == "delivered" else str(item.state), "TianxuanCaption")
			_link(content, "查看执行观测与发布", "execution", str(item.id))
			_link(content, "查看需求", "documents", item.requirement_id)
			for task in item.get("tasks", []):
				_link(content, "%s · %s" % [task.title, task.state], "issues", task.issue_id)
			if item.get("tasks_truncated", false):
				_label(content, "此记录仅展示前 12 个可见工单。", "TianxuanCaption")
		else:
			_label(content, str(item.get("kind", "需求")), "TianxuanCaption")
			_link(content, str(item.get("title", item.id)), str(item.get("target", "documents")), str(item.id), true)
			_label(content, str(item.get("subtitle", "v%d · %s" % [int(item.get("version", 0)), item.get("status", "")])))
			if kind == "requirements":
				if item.get("request_id") is String:
					_label(content, tr("需求编号：") + str(item.request_id), "TianxuanCaption")
				if item.get("progress") is Dictionary:
					var progress := ProgressBar.new()
					progress.value = clampf(float(item.progress.get("percent", 0)), 0, 100)
					content.add_child(progress)
					_label(content, tr("%d / %d 项工单完成") % [int(item.progress.get("done", 0)), int(item.progress.get("total", 0))], "TianxuanCaption")
				else:
					_label(content, str(item.get("progress_error", "尚无进度回执。")), "TianxuanCaption")


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signature = ""
		_changed("")
