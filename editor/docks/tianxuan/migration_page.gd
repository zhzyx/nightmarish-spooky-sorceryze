@tool
extends VBoxContainer

var controller: Node
var model: Node
var _status := Label.new()
var _summary := Label.new()
var _tabs := TabContainer.new()
var _query := LineEdit.new()
var _records := VBoxContainer.new()
var _details := VBoxContainer.new()
var _commits := VBoxContainer.new()
var _path := LineEdit.new()
var _commit := LineEdit.new()
var _file := CodeEdit.new()
var _requirement := LineEdit.new()
var _entry := OptionButton.new()
var _entry_label := Label.new()
var _entry_save := Button.new()
var _title := LineEdit.new()
var _start := Button.new()
var _result := Button.new()
var _dialog := ConfirmationDialog.new()
var _destination := FileDialog.new()
var _intent := {}
var _download := {}
var _offset := 0
var _related_offset := 0
var _body_offset := 0
var _git_offset := 0
var _record_id := ""
var _git_args := {}
var _scope := ""
var _signatures := {}
var _syncing := false
var _entry_value := ""


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.migration
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	label(self, "迁移与历史", "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle")
	label(self, "已导入的历史保持只读。新任务通过当前项目或需求配置的入口创建。")
	_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary.theme_type_variation = "TianxuanCaption"
	add_child(_summary)
	button(self, "刷新迁移状态", "NativeMigrationRefresh", func(): model.refresh())
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	var records := tab("来源记录")
	_query.placeholder_text = "编号、标题或路径"
	_query.max_length = 256
	records.add_child(_query)
	button(records, "搜索归档", "NativeMigrationSearch", func(): _offset = 0; _search())
	records.add_child(_records)
	records.add_child(_details)
	var history := tab("代码历史")
	label(history, "仓库内文件路径（可选）")
	history.add_child(_path)
	label(history, "原始提交 ID（可选）")
	history.add_child(_commit)
	button(history, "查看历史", "NativeMigrationCommits", func():
		_git_args = {}
		if not _path.text.strip_edges().is_empty():
			_git_args.path = _path.text.strip_edges()
		if not _commit.text.strip_edges().is_empty():
			_git_args.commit = _commit.text.strip_edges()
		_git_offset = 0
		_history()
		if _git_args.has("path"):
			model.read("file", _git_args)
	)
	history.add_child(_commits)
	_file.editable = false
	_file.custom_minimum_size.y = 280 * float(get_meta("ui_scale", 1.0))
	_file.size_flags_vertical = Control.SIZE_EXPAND_FILL
	history.add_child(_file)
	var tasks := tab("新任务入口")
	label(tasks, "项目使用当前账号绑定的项目；可为单个需求设置入口。")
	_requirement.placeholder_text = "需求文档 ID（可选）"
	tasks.add_child(_requirement)
	button(tasks, "读取入口", "NativeMigrationEntry", func(): model.load_entry(_requirement.text))
	tasks.add_child(_entry_label)
	for choice in [["existing", "现有入口"], ["tianxuan", "天璇"]]:
		_entry.add_item(choice[1])
		_entry.set_item_metadata(_entry.item_count - 1, choice[0])
	tasks.add_child(_entry)
	_entry_save = button(tasks, "保存所选入口", "NativeMigrationSaveEntry", func(): _ask("entry", {"entry": _entry.get_selected_metadata()}, "更改此项目或需求的新任务入口。历史记录保持只读。"))
	label(tasks, "新任务标题")
	_title.max_length = 512
	_title.name = "NativeMigrationTaskTitle"
	_title.text_changed.connect(func(text: String):
		if not _syncing:
			model.edit(text)
	)
	tasks.add_child(_title)
	_start = button(tasks, tr("新建任务"), "NativeMigrationStart", func(): _ask("start", {}, tr("通过当前入口创建任务：") + _title.text))
	_start.theme_type_variation = "TianxuanPrimaryButton"
	_result = button(tasks, "打开新任务", "NativeMigrationOpenTask", _open_task)
	_dialog.confirmed.connect(func():
		if _intent.get("operation") == "entry":
			model.set_entry(_intent.values.entry, _intent.expected)
		elif _intent.get("operation") == "start":
			model.start(_intent.expected)
	)
	add_child(_dialog)
	_destination.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_destination.access = FileDialog.ACCESS_FILESYSTEM
	_destination.file_selected.connect(func(path: String):
		if not _download.is_empty():
			model.download(_download.id, path, _download.expected)
	)
	add_child(_destination)
	model.changed.connect(_render)
	_render()
	model.refresh()


func label(parent: Node, caption: String, variation := "TianxuanCaption") -> Label:
	var node := Label.new()
	node.text = caption
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.theme_type_variation = variation
	parent.add_child(node)
	return node


func button(parent: Node, caption: String, node_name: String, action: Callable) -> Button:
	var node := Button.new()
	node.text = caption
	node.name = node_name
	node.pressed.connect(action)
	parent.add_child(node)
	return node


func tab(caption: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = caption
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_tabs.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(box)
	return box


func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func _new(topic: String, value: Variant) -> bool:
	var signature := JSON.stringify([_scope, value])
	if _signatures.get(topic) == signature:
		return false
	_signatures[topic] = signature
	return true


func _search() -> void:
	model.read("search", {"query": _query.text.strip_edges(), "offset": _offset, "limit": 10})


func _history() -> void:
	var args: Dictionary = _git_args.duplicate()
	args.offset = _git_offset
	args.limit = 10
	model.read("commits", args)


func _open_source(id: String) -> void:
	var parsed := RegEx.create_from_string("^github:([^/]+/[^/]+)/commit/([0-9a-f]{40}|[0-9a-f]{64})$").search(id)
	if parsed and id.begins_with("github:" + str(model.publication.get("source", "")) + "/"):
		_commit.text = parsed.get_string(2)
		_path.clear()
		_git_args = {"commit": _commit.text}
		_git_offset = 0
		_tabs.current_tab = 1
		_history()
		return
	_record_id = id
	_related_offset = 0
	_body_offset = 0
	model.data.erase("body")
	model.read("detail", {"source_id": id, "offset": 0, "limit": 10})


func _paging(parent: Node, offset: int, more: bool, previous: Callable, next: Callable) -> void:
	var row := HFlowContainer.new()
	parent.add_child(row)
	button(row, "上一页", "NativeMigrationPrevious", previous).disabled = offset <= 0
	label(row, tr("第 %d 页") % (offset / 10 + 1))
	button(row, "下一页", "NativeMigrationNext", next).disabled = not more


func _record_button(parent: Node, record: Dictionary) -> void:
	var title := str(record.get("title", record.get("path", record.get("source_id", ""))))
	button(parent, title if not title.is_empty() else str(record.source_id), "NativeMigrationRecord", _open_source.bind(str(record.source_id))).auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED


func _ask(operation: String, values: Dictionary, text: String) -> void:
	_intent = {"operation": operation, "values": values, "expected": model.snapshot()}
	_dialog.dialog_text = text
	_dialog.popup_centered()


func _open_task() -> void:
	var task: Dictionary = model.data.get("task", {})
	if task.has("issue_id"):
		controller.navigate("issues", str(task.issue_id))
	elif str(task.get("url", "")).begins_with("https://github.com/"):
		OS.shell_open(task.url)


func _render() -> void:
	_syncing = true
	var scope: String = controller.session.scope_key() + ":" + str(model.publication.get("catalog_revision", "")) + ":" + model.requirement
	if scope != _scope:
		_scope = scope
		_dialog.hide()
		_destination.hide()
		_intent.clear()
		_download.clear()
		_requirement.text = model.requirement
		_title.text = str(model.draft().get("title", ""))
	_summary.text = "当前项目尚无已发布的迁移记录。"
	if model.publication.get("available", false):
		var publication: Dictionary = model.publication
		_summary.text = tr("来源：%s\n原始提交：%s\n导入：%s · 发布：%s\n记录摘要：%s") % [publication.get("source", ""), publication.get("revision", ""), publication.get("imported_at", tr("未知")), publication.get("published_at", tr("未知")), publication.get("records_sha256", "")]
		var names := {"commit": "提交", "requirement": "需求", "issue": "工单", "pull": "合并请求", "issue_comment": "评论", "review": "审查", "review_comment": "审查评论", "commit_comment": "提交评论", "attachment": "附件"}
		for kind in publication.get("counts", {}):
			_summary.text += "\n%s：%d" % [str(names.get(kind, kind)), int(publication.counts[kind])]
	_status.text = tr(model.status)
	for topic in model.errors:
		_status.text += "\n" + str(model.errors[topic])
	_entry_label.text = tr("当前入口：") + str({"existing": tr("现有入口"), "tianxuan": tr("天璇")}.get(model.entry, tr("尚未读取")))
	if _entry_value != model.entry:
		_entry_value = model.entry
		_entry.select(1 if model.entry == "tianxuan" else 0)
	_entry.disabled = model.saving or controller.identity().get("role") != "admin"
	_entry_save.disabled = _entry.disabled or model.entry.is_empty() or model.draft().has("submission")
	_requirement.editable = not model.saving and not model.draft().has("submission")
	_title.editable = not model.saving and not model.draft().has("submission") and controller.can_edit()
	if not _title.has_focus():
		_title.text = str(model.draft().get("title", ""))
	_start.disabled = model.saving or not controller.can_edit() or model.entry.is_empty() or _title.text.strip_edges().is_empty()
	_start.text = "核对并重试原请求" if model.draft().has("submission") else "新建任务"
	_result.visible = not model.data.get("task", {}).is_empty()
	_result.disabled = not model.data.get("task", {}).has("issue_id") and not str(model.data.get("task", {}).get("url", "")).begins_with("https://github.com/")
	if _new("search", model.data.get("search", {})):
		clear(_records)
		var found: Dictionary = model.data.get("search", {})
		label(_records, tr("%d 条归档记录") % int(found.get("total", 0)), "TianxuanHeading")
		for record in found.get("items", []):
			_record_button(_records, record)
			label(_records, str(record.kind))
		_paging(_records, int(found.get("offset", 0)), int(found.get("offset", 0)) + 10 < int(found.get("total", 0)), func(): _offset = maxi(0, _offset - 10); _search(), func(): _offset += 10; _search())
	if _new("detail", [model.data.get("detail", {}), model.data.get("body", {})]):
		clear(_details)
		var detail: Dictionary = model.data.get("detail", {})
		if detail.has("record"):
			var record: Dictionary = detail.record
			_record_id = str(record.source_id)
			label(_details, str(record.content.get("title", record.content.get("path", record.source_id))), "TianxuanHeading").auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
			label(_details, record.source_id)
			var markdown: Control = get_meta("markdown_script").new()
			_details.add_child(markdown)
			markdown.set_markdown(str(detail.get("document", {}).get("text", record.content.get("body", ""))))
			for name in record.content:
				if name not in ["title", "body", "path"]:
					label(_details, "%s：%s" % [name, str(record.content[name])])
			if record.get("truncated", false):
				button(_details, "分页读取完整正文", "NativeMigrationBody", func(): _body_offset = 0; model.read("body", {"source_id": _record_id, "offset": 0}))
			if model.data.has("body"):
				var body: Dictionary = model.data.body
				label(_details, str(body.get("text", ""))).auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
				button(_details, "上一段", "NativeMigrationBodyPrevious", func(): _body_offset = maxi(0, _body_offset - 16384); model.read("body", {"source_id": _record_id, "offset": _body_offset})).disabled = _body_offset <= 0
				button(_details, "下一段", "NativeMigrationBodyNext", func(): _body_offset = int(body.next_offset); model.read("body", {"source_id": _record_id, "offset": _body_offset})).disabled = body.get("next_offset") == null
			if record.kind == "attachment":
				button(_details, "保存归档附件", "NativeMigrationAttachment", func():
					_download = {"id": record.source_id, "expected": model.snapshot()}
					_destination.current_file = "archived-attachment.bin"
					_destination.popup_centered_ratio(0.7)
				)
			for source in record.get("relations", []):
				button(_details, tr("关联来源：") + str(source), "NativeMigrationRelation", _open_source.bind(str(source)))
			for group in ["comments", "reverse"]:
				label(_details, (tr("评论") if group == "comments" else tr("引用此记录")) + " · %d" % int(detail.get(group, {}).get("total", 0)), "TianxuanHeading")
				for related in detail.get(group, {}).get("items", []):
					_record_button(_details, related)
					if group == "comments":
						label(_details, str(related.get("content", {}).get("body", ""))).auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
			_paging(_details, _related_offset, _related_offset + 10 < maxi(int(detail.comments.total), int(detail.reverse.total)), func(): _related_offset = maxi(0, _related_offset - 10); model.read("detail", {"source_id": _record_id, "offset": _related_offset, "limit": 10}), func(): _related_offset += 10; model.read("detail", {"source_id": _record_id, "offset": _related_offset, "limit": 10}))
	if _new("commits", model.data.get("commits", {})):
		clear(_commits)
		var history: Dictionary = model.data.get("commits", {})
		for commit in history.get("items", []):
			label(_commits, str(commit.subject), "TianxuanHeading").auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
			label(_commits, "%s · %s" % [commit.author, commit.oid])
			button(_commits, "读取此版本" if _git_args.has("path") else "选择此提交", "NativeMigrationCommit", func():
				_commit.text = commit.oid
				if _git_args.has("path"):
					model.read("file", {"commit": commit.oid, "path": _git_args.path})
			)
		_paging(_commits, _git_offset, history.get("next_offset") != null, func(): _git_offset = maxi(0, _git_offset - 10); _history(), func(): _git_offset += 10; _history())
	_file.text = str(model.data.get("file", {}).get("text", ""))
	_syncing = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signatures.clear()
		_render()
