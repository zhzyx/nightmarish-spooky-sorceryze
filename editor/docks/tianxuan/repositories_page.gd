@tool
extends VBoxContainer

var controller: Node
var model: Node
var _mode := OptionButton.new()
var _repositories := OptionButton.new()
var _branches := OptionButton.new()
var _lookup := LineEdit.new()
var _lookup_button := Button.new()
var _more := Button.new()
var _status := Label.new()
var _location := Label.new()
var _tabs := TabContainer.new()
var _tree := Tree.new()
var _commits := Tree.new()
var _file := CodeEdit.new()
var _remote := CodeEdit.new()
var _message := LineEdit.new()
var _save := Button.new()
var _retry := Button.new()
var _ack := Button.new()
var _review := Button.new()
var _download := FileDialog.new()
var _download_button := Button.new()
var _query := LineEdit.new()
var _search_results := Tree.new()
var _diff_a := LineEdit.new()
var _diff_b := LineEdit.new()
var _diff := CodeEdit.new()
var _blame := CodeEdit.new()
var _confirmation := ConfirmationDialog.new()
var _intent := {}
var _download_target := {}
var _syncing := false
var _scope := ""
var _file_context := ""
var _catalog_signature := ""
var _tree_signature := ""
var _history_signature := ""
var _search_signature := ""
var _management_rows := VBoxContainer.new()
var _management_name := LineEdit.new()
var _management_ref := LineEdit.new()
var _management_message := LineEdit.new()
var _management_actions := HFlowContainer.new()
var _management_ack := Button.new()
var _management_signature := ""
var _import_name := LineEdit.new()
var _import_source := LineEdit.new()
var _import_start := Button.new()
var _import_ack := Button.new()
var _import_status := Label.new()
var _import_jobs := VBoxContainer.new()
var _import_signature := ""
var _import_scope := ""
var _import_page: ScrollContainer


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.repositories
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	var title := Label.new()
	title.text = "多宝 · 仓库"
	title.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	add_child(title)
	var tools := HFlowContainer.new()
	add_child(tools)
	for name in ["原生模块", "本地 Git"]:
		_mode.add_item(name)
	_mode.item_selected.connect(func(index: int):
		var kind := "native" if index == 0 else "git"
		model.select(kind, "")
		model.load_catalog(kind)
	)
	tools.add_child(_mode)
	_repositories.name = "NativeRepositoryChoice"
	_repositories.fit_to_longest_item = false
	_repositories.custom_minimum_size.x = 200 * float(get_meta("ui_scale", 1.0))
	_repositories.item_selected.connect(func(index: int):
		var item: Dictionary = _repositories.get_item_metadata(index)
		model.select(model.kind, item.get("name", ""), item.get("revision", ""))
	)
	tools.add_child(_repositories)
	button(tools, "刷新", "NativeRepositoryRefresh", func(): model.load_catalog(model.kind); model.refresh())
	_more.text = "加载更多"
	_more.pressed.connect(func(): model.load_catalog("native", true))
	tools.add_child(_more)
	var selection := HFlowContainer.new()
	add_child(selection)
	_lookup.placeholder_text = "原生模块名称"
	_lookup.text_submitted.connect(func(name: String): model.select("native", name.strip_edges()))
	selection.add_child(_lookup)
	_lookup_button.text = "查询模块"
	_lookup_button.pressed.connect(func(): model.select("native", _lookup.text.strip_edges()))
	selection.add_child(_lookup_button)
	_branches.name = "NativeRepositoryBranch"
	_branches.item_selected.connect(func(index: int): model.select("git", model.repository, _branches.get_item_text(index)))
	selection.add_child(_branches)
	button(selection, "读取最新版本", "NativeRepositoryHead", func(): model.select(model.kind, model.repository, model.branch if model.kind == "git" else ""))
	_location.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	_location.theme_type_variation = "TianxuanCaption"
	add_child(_location)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	_build_files()
	_build_history()
	_build_inspection()
	_build_management()
	_build_imports()
	_confirmation.title = "提交当前文件"
	_confirmation.confirmed.connect(func():
		if _intent.get("operation") == "import":
			model.start_import(_intent.values, _intent.scope)
		elif _intent.has("operation"):
			model.manage_git(_intent.operation, _intent.values, _intent.expected)
		elif _intent == _snapshot():
			model.save()
		else:
			_status.text = "文件或草稿已经变化，请重新核对后提交。"
	)
	add_child(_confirmation)
	_download.access = FileDialog.ACCESS_FILESYSTEM
	_download.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_download.file_selected.connect(func(path: String):
		if _download_target == _snapshot(false):
			model.download_native(path)
	)
	add_child(_download)
	model.changed.connect(_render)
	_render()
	model.load_catalog(model.kind)
	model.refresh_imports()


func button(parent: Node, text: String, node_name: String, action: Callable) -> Button:
	var value := Button.new()
	value.text = text
	value.name = node_name
	value.pressed.connect(action)
	parent.add_child(value)
	return value


func _build_imports() -> void:
	_import_page = ScrollContainer.new()
	_import_page.name = "导入任务"
	_import_page.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_tabs.add_child(_import_page)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_import_page.add_child(content)
	var note := Label.new()
	note.text = "导入镜像保留分支与标签。来源地址或路径由服务器读取，目标已有仓库会保留。"
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.theme_type_variation = "TianxuanCaption"
	content.add_child(note)
	_import_name.name = "NativeRepositoryImportName"
	_import_name.placeholder_text = "目标仓库名称，例如 game.git"
	_import_source.name = "NativeRepositoryImportSource"
	_import_source.placeholder_text = "仓库 URL 或服务器允许的本机路径"
	for input in [_import_name, _import_source]:
		content.add_child(input)
		input.text_changed.connect(func(_text: String):
			if not _syncing:
				model.edit_import(_import_name.text, _import_source.text)
		)
	_import_start = button(content, "创建导入任务", "NativeRepositoryImport", func():
		_intent = {"operation": "import", "values": model.import_draft(), "scope": controller.session.scope_key()}
		_confirmation.title = "确认仓库导入"
		_confirmation.dialog_text = tr("来源：%s\n目标：%s\n\n确认后由服务器创建后台导入任务。") % [str(_intent.values.get("source", "")), str(_intent.values.get("name", ""))]
		_confirmation.popup_centered()
	)
	_import_start.theme_type_variation = "TianxuanPrimaryButton"
	button(content, "刷新导入任务", "NativeRepositoryRefreshImports", func(): model.refresh_imports())
	_import_ack = button(content, "已核对任务列表，恢复导入表单", "NativeRepositoryAcknowledgeImport", func(): model.acknowledge_import())
	_import_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_import_status.theme_type_variation = "TianxuanCaption"
	content.add_child(_import_status)
	content.add_child(_import_jobs)
	_import_page.visibility_changed.connect(func(): model.observe_imports(self, _import_page.is_visible_in_tree()))


func _render_imports() -> void:
	var scope: String = controller.session.scope_key()
	var switched := scope != _import_scope
	_import_scope = scope
	var draft: Dictionary = model.import_draft()
	for pair in [[_import_name, "name"], [_import_source, "source"]]:
		var input: LineEdit = pair[0]
		if switched or not input.has_focus():
			input.text = str(draft.get(pair[1], ""))
		input.editable = model.can_import()
	_import_start.disabled = not model.can_import() or not model.import_error().is_empty()
	_import_ack.visible = not model.import_pending().is_empty()
	_import_ack.disabled = model.import_loading or model.import_saving
	_import_status.text = model.import_status
	if controller.identity().get("role") != "admin":
		_import_status.text = "导入仓库需要管理员权限。"
	elif model.import_saving:
		_import_status.text = "正在创建服务器导入任务…"
	elif model.import_loading:
		_import_status.text = "正在读取导入任务…"
	elif not model.import_pending().is_empty():
		_import_status.text = "导入创建结果待核对。以下任务均为服务器真实记录；请核对名称与来源后恢复表单。"
	var signature := JSON.stringify([scope, model.import_jobs])
	if signature == _import_signature:
		return
	_import_signature = signature
	for child in _import_jobs.get_children():
		_import_jobs.remove_child(child)
		child.queue_free()
	for job in model.import_jobs:
		var panel := PanelContainer.new()
		panel.theme_type_variation = "TianxuanCard"
		_import_jobs.add_child(panel)
		var body := VBoxContainer.new()
		panel.add_child(body)
		for text in [str(job.name), str(job.source), "%s · %s" % [str({"queued": tr("等待中"), "running": tr("导入中"), "succeeded": tr("已完成"), "failed": tr("导入失败")}.get(job.status, job.status)), str(job.phase)], str(job.get("message", "")), str(job.error) if job.get("error") != null else ""]:
			if text.is_empty():
				continue
			var label := Label.new()
			label.text = text
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			body.add_child(label)
		if job.status == "succeeded":
			button(body, "浏览已导入仓库", "NativeRepositoryOpenImport", func():
				model.select("git", str(job.name))
				_tabs.current_tab = 0
			)


func tab(title: String) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.name = title
	_tabs.add_child(box)
	return box


func _configure_tree(tree: Tree, columns: Array) -> void:
	tree.hide_root = true
	tree.columns = columns.size()
	tree.set_column_titles_visible(true)
	for index in columns.size():
		tree.set_column_title(index, columns[index])
	tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tree.custom_minimum_size.y = 120 * float(get_meta("ui_scale", 1.0))


func _build_files() -> void:
	var files := tab("文件")
	button(files, "上一级", "NativeRepositoryUp", func(): model.open_directory(model.directory.get_base_dir()))
	_tree.name = "NativeRepositoryFiles"
	_configure_tree(_tree, ["名称", "类型"])
	_tree.item_activated.connect(func():
		var selected := _tree.get_selected()
		if not selected or not selected.get_metadata(0) is Dictionary:
			return
		var entry: Dictionary = selected.get_metadata(0)
		if entry.get("type") == "tree":
			model.open_directory.call_deferred(entry.path)
		else:
			model.open_file.call_deferred(entry.path)
	)
	files.add_child(_tree)
	_file.name = "NativeRepositoryContent"
	_file.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_file.custom_minimum_size.y = 160 * float(get_meta("ui_scale", 1.0))
	_file.text_changed.connect(_edit)
	_file.text_set.connect(_edit)
	files.add_child(_file)
	_remote.editable = false
	_remote.custom_minimum_size.y = 120 * float(get_meta("ui_scale", 1.0))
	_remote.tooltip_text = "当前服务器版本；上方保留本地草稿"
	files.add_child(_remote)
	_review.text = "已比较当前版本，保留草稿重新确认"
	_review.pressed.connect(func(): model.review_draft())
	files.add_child(_review)
	_message.placeholder_text = "提交说明"
	_message.name = "NativeRepositoryCommitMessage"
	_message.text_changed.connect(func(_text: String): _edit())
	files.add_child(_message)
	var actions := HFlowContainer.new()
	files.add_child(actions)
	_save.name = "NativeRepositorySave"
	_save.theme_type_variation = "TianxuanPrimaryButton"
	_save.pressed.connect(func():
		_intent = _snapshot()
		_confirmation.title = "提交当前文件"
		_confirmation.dialog_text = model.path + "\n" + (tr("创建新的原生修订，已有修订保留。") if model.kind == "native" else tr("保存到新分支，随后可提交审查。"))
		_confirmation.popup_centered()
	)
	actions.add_child(_save)
	button(actions, "放弃草稿", "NativeRepositoryDiscard", func():
		if not model.saving and not model.draft().has("submission"):
			controller.clear_draft(model.draft_key())
	)
	_download_button.text = "另存原件…"
	_download_button.pressed.connect(func():
		_download_target = _snapshot(false)
		_download.current_file = str(model.path).get_file().validate_filename()
		_download.popup_centered_ratio(0.6)
	)
	actions.add_child(_download_button)
	_retry.text = "重试原生修订的原请求"
	_retry.pressed.connect(func(): model.retry_native())
	files.add_child(_retry)
	_ack.text = "已核对分支及提交记录，恢复编辑"
	_ack.pressed.connect(func(): model.acknowledge_unknown_git())
	files.add_child(_ack)


func _build_history() -> void:
	var history := tab("版本记录")
	_configure_tree(_commits, ["版本 / 提交", "说明", "作者"])
	_commits.item_activated.connect(func():
		var selected := _commits.get_selected()
		if selected and selected.get_metadata(0) is String:
			if model.kind == "native":
				model.select.call_deferred("native", model.repository, selected.get_metadata(0))
			else:
				_diff_b.text = selected.get_metadata(0)
				_tabs.current_tab = 3
	)
	history.add_child(_commits)


func _build_inspection() -> void:
	var search := tab("代码搜索")
	_query.placeholder_text = "搜索当前分支"
	_query.text_submitted.connect(func(text: String): model.inspect("search", text))
	search.add_child(_query)
	button(search, "搜索", "NativeRepositorySearch", func(): model.inspect("search", _query.text))
	_configure_tree(_search_results, ["文件", "行", "内容"])
	_search_results.item_activated.connect(func():
		var selected := _search_results.get_selected()
		if selected and selected.get_metadata(0) is String:
			model.open_file.call_deferred(selected.get_metadata(0))
			_tabs.current_tab = 0
	)
	search.add_child(_search_results)
	var difference := tab("差异")
	_diff_a.placeholder_text = "基础版本或分支"
	_diff_b.placeholder_text = "目标版本或分支"
	difference.add_child(_diff_a)
	difference.add_child(_diff_b)
	button(difference, "比较版本", "NativeRepositoryDiff", func(): model.inspect("diff", _diff_a.text, _diff_b.text))
	_diff.editable = false
	_diff.size_flags_vertical = Control.SIZE_EXPAND_FILL
	difference.add_child(_diff)
	var blame := tab("逐行历史")
	button(blame, "读取当前文件的逐行历史", "NativeRepositoryBlame", func(): model.inspect("blame"))
	_blame.editable = false
	_blame.size_flags_vertical = Control.SIZE_EXPAND_FILL
	blame.add_child(_blame)


func _snapshot(with_draft := true) -> Dictionary:
	var result := {"scope": controller.session.scope_key(), "repository": model.repository, "kind": model.kind, "branch": model.branch, "revision": model.revision, "path": model.path}
	if with_draft:
		result.draft = model.draft()
	return result


func _build_management() -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "分支与标签"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_tabs.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(content)
	content.add_child(_management_rows)
	_management_name.placeholder_text = "新分支或标签名称"
	_management_ref.placeholder_text = "起点提交或分支（留空使用当前分支）"
	_management_message.placeholder_text = "附注标签说明（可选）"
	content.add_child(_management_name)
	content.add_child(_management_ref)
	content.add_child(_management_message)
	content.add_child(_management_actions)
	button(_management_actions, "创建分支", "NativeRepositoryCreateBranch", _confirm_management.bind("create_branch", ""))
	button(_management_actions, "创建标签", "NativeRepositoryCreateTag", _confirm_management.bind("create_tag", ""))
	_management_ack.text = "已刷新并核对操作结果，恢复管理操作"
	_management_ack.pressed.connect(func():
		if not model.saving:
			controller.clear_draft(model.management_key())
	)
	content.add_child(_management_ack)


func _confirm_management(operation: String, name: String) -> void:
	var values := {"name": _management_name.text.strip_edges() if name.is_empty() else name, "ref": _management_ref.text.strip_edges() if not _management_ref.text.strip_edges().is_empty() else model.branch, "message": _management_message.text}
	_intent = {"operation": operation, "values": values, "expected": model.git_snapshot()}
	_confirmation.title = {"create_branch": "创建分支", "delete_branch": "删除分支", "create_tag": "创建标签", "delete_tag": "删除标签"}[operation]
	_confirmation.dialog_text = "%s · %s\n%s" % [model.repository, values.name, tr("删除后此名称将不再指向原提交。") if operation.begins_with("delete") else tr("起点：") + str(values.ref)]
	_confirmation.popup_centered()


func _edit() -> void:
	if not _syncing:
		model.update_draft(_file.text, _message.text)


func _render() -> void:
	_syncing = true
	var scope: String = controller.session.scope_key() + ":" + model.kind + ":" + model.repository
	if scope != _scope:
		_scope = scope
		_confirmation.hide()
		_download.hide()
		_intent.clear()
		_query.clear()
		_diff_a.clear()
		_diff_b.clear()
		_lookup.text = model.repository if model.kind == "native" else ""
		_management_name.clear()
		_management_ref.clear()
		_management_message.clear()
	_mode.select(0 if model.kind == "native" else 1)
	_mode.disabled = model.saving
	_repositories.disabled = model.saving
	_branches.visible = model.kind == "git"
	_branches.disabled = model.saving or model.loading
	_lookup.visible = model.kind == "native"
	_lookup_button.visible = _lookup.visible
	_lookup.editable = not model.saving
	_lookup_button.disabled = model.saving
	_more.visible = model.kind == "native" and model.catalog.get("native", {}).get("next_cursor") is String
	_more.disabled = model._catalog_pending.has("native")
	_location.text = model.repository + (" · " + model.revision.left(12) if model.kind == "native" else " · " + model.branch) + (" / " + model.path if not model.path.is_empty() else "")
	_status.text = tr(model.status)
	if model.repository.is_empty():
		_status.text = str(model.errors.get(model.kind, "请选择模块或仓库。"))
	if model.loading:
		_status.text = "正在读取当前仓库…"
	if model.catalog.get(model.kind, {}).get("available") == false:
		_status.text = "此工作区尚未配置原生存储。"
	_render_catalog()
	_render_tree()
	_render_history()
	var draft: Dictionary = model.draft()
	var content := str(draft.get("content", model.file.get("content", "")))
	var file_context := JSON.stringify([scope, model.branch, model.revision, model.path])
	var file_switched := file_context != _file_context
	_file_context = file_context
	if _file.text != content and (file_switched or not _file.has_focus()):
		_file.text = content
	if file_switched or not _message.has_focus():
		_message.text = str(draft.get("message", ""))
	_message.visible = model.kind == "git"
	_message.editable = model.editable()
	_file.editable = model.editable()
	var conflict: bool = not draft.is_empty() and model.file.has("content") and (draft.get("base_blob") != model.file.get("sha") or (model.kind == "native" and draft.get("base_revision") != model.revision))
	_remote.visible = conflict
	_review.visible = conflict
	_review.disabled = not model.editable()
	_remote.text = str(model.file.get("content", "")) if conflict else ""
	_save.text = "保存新修订" if model.kind == "native" else "保存到新分支"
	_save.disabled = not model.editable() or draft.is_empty() or conflict or content == str(model.file.get("content", ""))
	_retry.visible = model.kind == "native" and draft.has("submission")
	_ack.visible = model.kind == "git" and draft.has("submission")
	_retry.disabled = model.saving
	_ack.disabled = model.saving
	_download_button.visible = model.kind == "native"
	_download_button.disabled = model.file.is_empty()
	for index in range(2, 6):
		_tabs.set_tab_hidden(index, model.kind != "git")
	_diff.text = str(model.state.get("diff", {}).get("diff", model.errors.get("diff", "")))
	var lines: Array[String] = []
	for line in model.state.get("blame", {}).get("lines", []):
		lines.append("%s · %s · %s" % [str(line.get("sha", "")).left(8), line.get("author", ""), line.get("text", line.get("content", ""))])
	_blame.text = "\n".join(lines) if not lines.is_empty() else str(model.errors.get("blame", ""))
	_render_search()
	_render_management()
	_render_imports()
	_syncing = false


func _render_management() -> void:
	var waiting: bool = not controller.load_draft(model.management_key()).is_empty()
	var writable: bool = controller.can_edit() and not model.saving and not model.loading and not waiting
	_management_ack.visible = waiting
	_management_ack.disabled = model.saving or model.loading
	for action in _management_actions.get_children():
		action.disabled = not writable or model.repository.is_empty()
	var signature := JSON.stringify([model.state.get("branches", []), model.state.get("tags", []), writable, model.repository])
	if signature == _management_signature:
		return
	_management_signature = signature
	for child in _management_rows.get_children():
		_management_rows.remove_child(child)
		child.queue_free()
	for value in model.state.get("branches", []):
		var row := HFlowContainer.new()
		_management_rows.add_child(row)
		button(row, tr("分支 · ") + str(value), "NativeRepositoryOpenBranch", func(): model.select("git", model.repository, str(value)))
		button(row, "删除", "NativeRepositoryDeleteBranch", _confirm_management.bind("delete_branch", str(value))).disabled = not writable
	for value in model.state.get("tags", []):
		var row := HFlowContainer.new()
		_management_rows.add_child(row)
		var caption := Label.new()
		caption.text = tr("标签 · %s · %s") % [value.get("name", ""), str(value.get("sha", "")).left(10)]
		row.add_child(caption)
		button(row, "删除", "NativeRepositoryDeleteTag", _confirm_management.bind("delete_tag", str(value.get("name", "")))).disabled = not writable


func _render_catalog() -> void:
	var signature := JSON.stringify([model.kind, model.repository, model.branch, model.catalog, model.state.get("branches", [])])
	if signature == _catalog_signature:
		return
	_catalog_signature = signature
	_repositories.clear()
	_repositories.add_item("选择模块" if model.kind == "native" else "选择仓库")
	_repositories.set_item_metadata(0, {})
	var rows: Array = model.catalog.get(model.kind, {}).get("modules" if model.kind == "native" else "repos", [])
	for row in rows:
		var name: String = str(row.module) if row is Dictionary else str(row)
		_repositories.add_item(name)
		_repositories.set_item_auto_translate_mode(_repositories.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		var index := _repositories.item_count - 1
		_repositories.set_item_metadata(index, {"name": name, "revision": row.get("revision", "") if row is Dictionary else ""})
		if name == model.repository:
			_repositories.select(index)
	_branches.clear()
	for value in model.state.get("branches", []):
		_branches.add_item(str(value))
		_branches.set_item_auto_translate_mode(_branches.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
		if value == model.branch:
			_branches.select(_branches.item_count - 1)


func _render_tree() -> void:
	var signature := JSON.stringify([model.kind, model.repository, model.revision, model.directory, model.state.get("revision", {}), model.state.get("tree", {})])
	if signature == _tree_signature:
		return
	_tree_signature = signature
	_tree.clear()
	var root := _tree.create_item()
	var entries: Array = model.state.get("tree", {}).get("entries", [])
	if model.kind == "native":
		entries = []
		var names: Array = model.state.get("revision", {}).get("objects", {}).keys()
		names.sort()
		for name in names:
			entries.append({"path": name, "name": name, "type": "blob"})
	for entry in entries:
		var item := _tree.create_item(root)
		item.set_text(0, str(entry.name))
		item.set_auto_translate_mode(0, Node.AUTO_TRANSLATE_MODE_DISABLED)
		item.set_text(1, "目录" if entry.type == "tree" else "文件")
		item.set_metadata(0, entry)
		item.set_tooltip_text(0, str(entry.path))
	if entries.is_empty():
		var empty := _tree.create_item(root)
		empty.set_text(0, str(model.errors.get("tree", "此位置没有可显示的文件。")))


func _render_history() -> void:
	var signature := JSON.stringify([model.kind, model.state.get("commits", {}), model.state.get("revision", {}), model.revision])
	if signature == _history_signature:
		return
	_history_signature = signature
	_commits.clear()
	var root := _commits.create_item()
	if model.kind == "native":
		for value in [model.revision, model.state.get("revision", {}).get("parent")]:
			if not value is String or value.is_empty():
				continue
			var item := _commits.create_item(root)
			item.set_text(0, str(value).left(12))
			item.set_text(1, "当前修订" if value == model.revision else "父修订（打开后可继续向前查看）")
			item.set_metadata(0, value)
	else:
		for commit in model.state.get("commits", {}).get("commits", []):
			var item := _commits.create_item(root)
			item.set_text(0, str(commit.sha).left(10))
			item.set_text(1, str(commit.message))
			item.set_text(2, str(commit.author))
			item.set_metadata(0, commit.sha)
			item.set_tooltip_text(1, str(commit.date))


func _render_search() -> void:
	var signature := JSON.stringify(model.state.get("search", {}))
	if signature == _search_signature:
		return
	_search_signature = signature
	_search_results.clear()
	var root := _search_results.create_item()
	for result in model.state.get("search", {}).get("results", []):
		var row := _search_results.create_item(root)
		row.set_text(0, str(result.path))
		row.set_text(1, str(result.line))
		row.set_text(2, str(result.text))
		row.set_metadata(0, result.path)


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_search_signature = ""
		_tree_signature = ""
		_catalog_signature = ""
		_history_signature = ""
		_management_signature = ""
		_import_signature = ""
		_render()
