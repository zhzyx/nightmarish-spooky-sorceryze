@tool
extends VBoxContainer

var controller: Node
var model: Node
var _owner := LineEdit.new()
var _repository := LineEdit.new()
var _catalog := OptionButton.new()
var _status := Label.new()
var _ack := Button.new()
var _tabs := TabContainer.new()
var _pulls := Tree.new()
var _releases := Tree.new()
var _queue := Tree.new()
var _reviews := VBoxContainer.new()
var _links := VBoxContainer.new()
var _workers := Label.new()
var _forms := {}
var _submit := {}
var _defaults := {}
var _queue_actions := {}
var _dialog := ConfirmationDialog.new()
var _intent := {}
var _scope := ""
var _signatures := {}
var _syncing := false
var _filter := OptionButton.new()
var _page := SpinBox.new()


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.repository_collaboration
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	var title := Label.new()
	title.text = "审查与发布"
	title.theme_type_variation = "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle"
	add_child(title)
	var toolbar := HFlowContainer.new()
	add_child(toolbar)
	_catalog.fit_to_longest_item = false
	_catalog.custom_minimum_size.x = 190 * float(get_meta("ui_scale", 1.0))
	_catalog.item_selected.connect(func(index: int):
		var full: String = _catalog.get_item_metadata(index)
		if full.count("/") == 1:
			model.select(full.get_slice("/", 0), full.get_slice("/", 1))
	)
	toolbar.add_child(_catalog)
	_owner.placeholder_text = "仓库所有者"
	_repository.placeholder_text = "仓库名称"
	toolbar.add_child(_owner)
	toolbar.add_child(_repository)
	button(toolbar, "打开", "NativeCollaborationOpen", func(): model.select(_owner.text, _repository.text))
	button(toolbar, "刷新", "NativeCollaborationRefresh", _refresh)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanCaption"
	add_child(_status)
	_ack.text = "已刷新并核对服务记录，恢复编辑"
	_ack.pressed.connect(func(): model.acknowledge_unknown())
	add_child(_ack)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	_build_pulls()
	_build_releases()
	_build_queue()
	_build_repositories()
	_dialog.title = "确认仓库操作"
	_dialog.confirmed.connect(func():
		if not _intent.is_empty():
			model.execute(_intent.operation, _intent.values, _intent.expected)
	)
	add_child(_dialog)
	model.changed.connect(_render)
	_render()
	_refresh()


func button(parent: Node, caption: String, node_name: String, action: Callable) -> Button:
	var node := Button.new()
	node.text = caption
	node.name = node_name
	node.pressed.connect(action)
	parent.add_child(node)
	return node


func label(parent: Node, caption: String, variation := "TianxuanCaption") -> Label:
	var node := Label.new()
	node.text = caption
	node.theme_type_variation = variation
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
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


func tree(parent: Node, widget: Tree, captions: Array) -> void:
	widget.hide_root = true
	widget.columns = captions.size()
	widget.set_column_titles_visible(true)
	for index in captions.size():
		widget.set_column_title(index, captions[index])
	widget.custom_minimum_size.y = 180 * float(get_meta("ui_scale", 1.0))
	parent.add_child(widget)


func form(parent: Node, operation: String, title: String, fields: Array, caption: String) -> void:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "TianxuanCard"
	parent.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	label(box, title, "TianxuanHeading")
	_forms[operation] = {}
	_defaults[operation] = {}
	for entry in fields:
		label(box, entry[1])
		var input: Control
		var type: String = entry[2]
		var initial: Variant = entry[3] if entry.size() > 3 else ""
		match type:
			"text":
				var text := TextEdit.new()
				text.custom_minimum_size.y = 90 * float(get_meta("ui_scale", 1.0))
				text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
				text.text_changed.connect(_edited.bind(operation))
				text.text_set.connect(_edited.bind(operation))
				input = text
			"bool":
				var check := CheckBox.new()
				check.text = entry[1]
				check.toggled.connect(func(_value: bool): _edited(operation))
				input = check
			"number":
				var number := SpinBox.new()
				number.min_value = -1000
				number.max_value = 1000
				number.value_changed.connect(func(_value: float): _edited(operation))
				input = number
			"choice":
				var choice := OptionButton.new()
				for option in initial:
					choice.add_item(option[1])
					choice.set_item_metadata(choice.item_count - 1, option[0])
				initial = initial[0][0]
				choice.item_selected.connect(func(_index: int): _edited(operation))
				input = choice
			_:
				var line := LineEdit.new()
				line.max_length = 1024
				line.text_changed.connect(func(_value: String): _edited(operation))
				input = line
		input.name = "NativeCollaboration_" + operation + "_" + entry[0]
		input.set_meta("kind", type)
		_forms[operation][entry[0]] = input
		_defaults[operation][entry[0]] = initial
		box.add_child(input)
	_submit[operation] = button(box, caption, "NativeCollaborationSubmit_" + operation, _confirm_form.bind(operation, caption))
	_submit[operation].theme_type_variation = "TianxuanPrimaryButton"
	if operation in ["review_pull", "merge_pull", "update_release"]:
		button(box, "放弃本机草稿并载入当前记录", "NativeCollaborationDiscard_" + operation, func(): _confirm("discard_form", {"section": operation}, "放弃本机草稿并载入当前记录"))


func _build_pulls() -> void:
	var page := tab("合并请求")
	var toolbar := HFlowContainer.new()
	page.add_child(toolbar)
	for entry in [["open", "开放"], ["closed", "已关闭"], ["all", "全部"]]:
		_filter.add_item(entry[1])
		_filter.set_item_metadata(_filter.item_count - 1, entry[0])
	_filter.item_selected.connect(func(index: int): model.filter = _filter.get_item_metadata(index); model.page = 1; model.refresh_repository())
	toolbar.add_child(_filter)
	_page.min_value = 1
	_page.max_value = 100000
	_page.value_changed.connect(func(value: float):
		if not _syncing:
			model.page = int(value)
			model.refresh_repository()
	)
	toolbar.add_child(_page)
	tree(page, _pulls, ["请求", "状态", "来源 → 目标"])
	_pulls.item_selected.connect(func():
		if not _syncing and _pulls.get_selected():
			model.select_pull.call_deferred(int(_pulls.get_selected().get_metadata(0)))
	)
	page.add_child(_reviews)
	form(page, "create_pull", "新建合并请求", [["title", "标题", "line"], ["head", "来源分支", "line"], ["base", "目标分支", "line", "main"], ["body", "说明", "text"]], "创建合并请求")
	form(page, "review_pull", "审查所选请求", [["event", "结论", "choice", [["COMMENT", "评论"], ["APPROVED", "批准"], ["REQUEST_CHANGES", "请求修改"]]], ["body", "审查意见", "text"]], "提交审查")
	form(page, "merge_pull", "合并所选请求", [["method", "合并方式", "choice", [["merge", "合并提交"], ["squash", "压缩合并"], ["rebase", "变基合并"]]]], "合并请求")
	label(page, "合并沿用服务端的分支保护、审查人数与检查要求。")


func _build_releases() -> void:
	var page := tab("发布")
	tree(page, _releases, ["发布", "标签", "状态"])
	_releases.item_selected.connect(func():
		if not _syncing and not model.saving and _releases.get_selected():
			model.release_id = int(_releases.get_selected().get_metadata(0))
			model.call_deferred("emit_signal", "changed")
	)
	var fields := [["name", "名称", "line"], ["body", "发布说明", "text"], ["draft", "草稿发布", "bool", true], ["prerelease", "预发布", "bool", false]]
	form(page, "create_release", tr("新建发布"), [["tag_name", tr("标签名称"), "line"]] + fields, tr("创建发布"))
	form(page, "update_release", "编辑所选发布", fields, "保存发布")


func _build_queue() -> void:
	var page := tab("合入队列")
	button(page, "刷新队列", "NativeQueueRefresh", func(): model.load_queue())
	_workers.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_workers.theme_type_variation = "TianxuanCaption"
	page.add_child(_workers)
	tree(page, _queue, ["候选", "来源 → 目标", "状态"])
	_queue.item_selected.connect(func():
		if not _syncing and not model.saving and _queue.get_selected():
			model.queue_id = str(_queue.get_selected().get_metadata(0))
			model.call_deferred("emit_signal", "changed")
	)
	var actions := HFlowContainer.new()
	page.add_child(actions)
	for entry in [["process_queue", "处理队列（最多五项）"], ["retry_queue", "重试所选候选"], ["cancel_queue", "取消所选候选"]]:
		_queue_actions[entry[0]] = button(actions, entry[1], "NativeQueue_" + entry[0], _confirm.bind(entry[0], {}, entry[1]))
	form(page, "enqueue", "提交合入候选", [["repo", "本地仓库名称", "line"], ["source", "来源分支", "line"], ["target", "目标分支", "line", "main"], ["title", "说明", "line"], ["priority", "优先级", "number", 0], ["issue_ref", "关联工单（可选）", "line"]], "加入合入队列")


func _build_repositories() -> void:
	var page := tab("仓库与绑定")
	page.add_child(_links)
	form(page, "link_repository", "绑定已有仓库", [["provider", "服务", "choice", [["gitea", "Gitea"], ["github", "GitHub"]]], ["owner", "所有者", "line"], ["name", "仓库名称", "line"]], "绑定仓库")
	form(page, "create_repository", "新建托管仓库", [["name", "仓库名称", "line"], ["private", "私有仓库", "bool", true], ["default_branch", "默认分支", "line", "main"]], "创建仓库")


func _refresh() -> void:
	model.load_catalog()
	model.refresh_repository()
	model.load_queue()


func _values(operation: String) -> Dictionary:
	var values := {}
	for key in _forms[operation]:
		var control: Control = _forms[operation][key]
		match str(control.get_meta("kind")):
			"bool": values[key] = control.button_pressed
			"number": values[key] = int(control.value)
			"choice": values[key] = control.get_selected_metadata()
			_: values[key] = control.text
	return values


func _edited(operation: String) -> void:
	if not _syncing:
		model.edit(operation, _values(operation))


func _confirm_form(operation: String, caption: String) -> void:
	_confirm(operation, _values(operation), caption)


func _confirm(operation: String, values: Dictionary, caption: String) -> void:
	_intent = {"operation": operation, "values": values.duplicate(true), "expected": model.snapshot()}
	_dialog.title = caption
	var selected := "%s/%s" % [model.repository_owner, model.repository]
	if operation in ["review_pull", "merge_pull"]:
		selected += " · #%d · %s → %s" % [model.pull_number, str(model.revision(operation).get("head_sha", "")), str(model.revision(operation).get("base", ""))]
	elif operation == "update_release":
		selected += tr(" · 发布 %d") % model.release_id
	elif operation in ["retry_queue", "cancel_queue"]:
		selected = tr("候选 ") + model.queue_id
	elif operation == "enqueue":
		selected = "%s · %s → %s" % [values.get("repo", ""), values.get("source", ""), values.get("target", "")]
	_dialog.dialog_text = selected + "\n" + caption + tr("。服务端权限与校验持续生效。")
	if operation == "merge_pull":
		_dialog.dialog_text += "\n" + tr("提交前会重新核对目标分支；请避免同时修改该请求的目标分支。")
	if operation == "update_release":
		_dialog.dialog_text += "\n" + tr("提交前会重新核对发布内容；托管服务不提供原子版本锁，请避免同时编辑同一发布。")
	_dialog.popup_centered()


func _render() -> void:
	_syncing = true
	var scope := JSON.stringify(model.snapshot())
	var switched := scope != _scope
	if switched:
		_scope = scope
		_dialog.hide()
		_intent.clear()
		_owner.text = model.repository_owner
		_repository.text = model.repository
	_status.text = tr(model.status)
	var configured: bool = model.data.get("configuration", {}).get("configured", false)
	if not configured:
		_status.text += tr(" 该服务尚未配置 Gitea 托管；仓库绑定和已配置的本地合入队列可单独使用。")
	for topic in model.errors:
		_status.text += "\n" + str({"configuration": tr("托管配置"), "repositories": tr("仓库"), "branches": tr("分支"), "pulls": tr("合并请求"), "releases": tr("发布"), "reviews": tr("审查"), "queue": tr("合入队列"), "queue_status": tr("队列状态"), "workers": tr("工作者"), "links": tr("仓库绑定")}.get(topic, topic)) + "：" + str(model.errors[topic])
	_ack.visible = not model.draft("pending").is_empty()
	_ack.disabled = model.saving
	_owner.editable = not model.saving
	_repository.editable = not model.saving
	_catalog.disabled = model.saving
	_page.value = model.page
	_page.editable = not model.saving
	_filter.disabled = model.saving
	var selected_release := {}
	for release in model.data.get("releases", {}).get("releases", []):
		if int(release.id) == model.release_id:
			selected_release = release
	for operation in _forms:
		var values: Dictionary = model.draft(operation)
		if values.is_empty():
			values = _defaults[operation].duplicate(true)
			if operation == "update_release":
				for key in values:
					values[key] = selected_release.get(key, values[key])
		var writable: bool = model.writable()
		if operation in ["create_repository", "create_pull", "review_pull", "merge_pull", "create_release", "update_release"]:
			writable = writable and configured
		if operation == "create_repository":
			writable = writable and controller.identity().get("role") == "admin"
		elif operation in ["create_pull", "create_release"]:
			writable = writable and not model.repository_owner.is_empty() and not model.repository.is_empty()
		elif operation in ["review_pull", "merge_pull"]:
			writable = writable and model.pull_number > 0
		elif operation == "update_release":
			writable = writable and not selected_release.is_empty()
		elif operation == "enqueue":
			writable = writable and model.data.has("queue")
		_submit[operation].disabled = not writable
		for key in _forms[operation]:
			var control: Control = _forms[operation][key]
			var value: Variant = values.get(key)
			if control is CheckBox:
				control.disabled = not writable
				control.set_pressed_no_signal(value == true)
			elif control is SpinBox:
				control.editable = writable
				if switched or not control.get_line_edit().has_focus():
					control.value = int(value)
			elif control is OptionButton:
				control.disabled = not writable
				for index in control.item_count:
					if control.get_item_metadata(index) == value:
						control.select(index)
			else:
				control.editable = writable
				if control.text != str(value) and (switched or not control.has_focus()):
					control.text = str(value)
	for operation in _queue_actions:
		_queue_actions[operation].disabled = not model.writable() or not model.data.has("queue") or (operation != "process_queue" and model.queue_id.is_empty())
	_render_rows()
	_syncing = false


func _new_data(topic: String, value: Variant) -> bool:
	var signature := JSON.stringify([controller.session.scope_key(), value])
	if _signatures.get(topic) == signature:
		return false
	_signatures[topic] = signature
	return true


func _render_rows() -> void:
	if _new_data("catalog", model.data.get("repositories", {})):
		_catalog.clear()
		_catalog.add_item("选择托管仓库")
		_catalog.set_item_metadata(0, "")
		for repo in model.data.get("repositories", {}).get("repos", []):
			var name := str(repo.get("full_name", repo.get("name", "")))
			_catalog.add_item(name)
			_catalog.set_item_auto_translate_mode(_catalog.item_count - 1, Node.AUTO_TRANSLATE_MODE_DISABLED)
			_catalog.set_item_metadata(_catalog.item_count - 1, name)
	if _new_data("pulls", [model.data.get("pulls", {}), model.pull_number]):
		_pulls.clear()
		var root := _pulls.create_item()
		for pull in model.data.get("pulls", {}).get("pulls", []):
			var row := _pulls.create_item(root)
			row.set_text(0, "#%d · %s" % [int(pull.number), pull.title])
			row.set_text(1, str(pull.state))
			row.set_text(2, "%s → %s" % [pull.head, pull.base])
			row.set_metadata(0, pull.number)
			if int(pull.number) == model.pull_number:
				row.select(0)
	if _new_data("releases", [model.data.get("releases", {}), model.release_id]):
		_releases.clear()
		var root := _releases.create_item()
		for release in model.data.get("releases", {}).get("releases", []):
			var row := _releases.create_item(root)
			row.set_text(0, str(release.name))
			row.set_auto_translate_mode(0, Node.AUTO_TRANSLATE_MODE_DISABLED)
			row.set_text(1, str(release.tag_name))
			row.set_auto_translate_mode(1, Node.AUTO_TRANSLATE_MODE_DISABLED)
			row.set_text(2, "草稿" if release.draft else "预发布" if release.prerelease else "已发布")
			row.set_metadata(0, release.id)
			if int(release.id) == model.release_id:
				row.select(0)
	if _new_data("queue", [model.data.get("queue", {}), model.queue_id]):
		_queue.clear()
		var root := _queue.create_item()
		for entry in model.data.get("queue", {}).get("items", []):
			var row := _queue.create_item(root)
			row.set_text(0, str(entry.get("title", entry.get("id", ""))))
			row.set_text(1, "%s → %s" % [entry.source, entry.target])
			row.set_text(2, str(entry.status))
			row.set_metadata(0, entry.id)
			row.set_tooltip_text(2, str(entry.get("evidence", {}).get("error", entry.get("evidence", {}).get("merge_sha", ""))))
			if entry.id == model.queue_id:
				row.select(0)
	_workers.text = tr("等待 %d 项 · 工作者 %d 个") % [int(model.data.get("queue_status", {}).get("queued", 0)), model.data.get("workers", {}).get("workers", []).size()]
	if _new_data("reviews", model.data.get("reviews", {})):
		for child in _reviews.get_children():
			_reviews.remove_child(child)
			child.queue_free()
		for review in model.data.get("reviews", {}).get("reviews", []):
			label(_reviews, "%s · %s\n%s" % [review.user, review.state, review.body])
	if _new_data("links", [model.data.get("links", {}), model.writable()]):
		for child in _links.get_children():
			_links.remove_child(child)
			child.queue_free()
		for link in model.data.get("links", {}).get("links", []):
			label(_links, "%s · %s/%s" % [link.provider, link.owner, link.name])
			button(_links, "解除此绑定", "NativeRepositoryUnlink", _confirm.bind("unlink_repository", {"id": link.id}, "解除仓库绑定")).disabled = not model.writable()


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signatures.clear()
		_render()
