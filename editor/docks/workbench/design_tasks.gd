@tool
extends VBoxContainer

var session: Node
var signoff: Node
var dialog := ConfirmationDialog.new()
var form := VBoxContainer.new()
var paragraph := OptionButton.new()
var module := OptionButton.new()
var task_title := LineEdit.new()
var acceptance := TextEdit.new()
var add_item := Button.new()
var staged := ItemList.new()
var remove := Button.new()
var status := Label.new()
var items: Array[Dictionary] = []
var generation := 0
var route := ""
var call_id := ""


func _ready() -> void:
	hide()
	session = get_parent()
	if not session.is_node_ready():
		await session.ready
	signoff = session.get_node("WorkbenchDesignSignoff")
	signoff.split.pressed.connect(_open)
	signoff.dialog.add_child(dialog)
	signoff.dialog.visibility_changed.connect(func(): if not signoff.dialog.visible: dialog.hide())
	dialog.visibility_changed.connect(_visibility_changed)
	dialog.dialog_hide_on_ok = false
	dialog.confirmed.connect(_submit)
	dialog.get_cancel_button().text = "关闭"
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(510, 380) * EditorInterface.get_editor_scale()
	dialog.add_child(box)
	box.add_child(form)
	paragraph.tooltip_text = "来源段落"
	form.add_child(paragraph)
	module.tooltip_text = "目标业务模块"
	form.add_child(module)
	task_title.placeholder_text = "工单标题"
	task_title.max_length = 256
	form.add_child(task_title)
	acceptance.placeholder_text = "这项任务的验收条件"
	acceptance.custom_minimum_size.y = 60 * EditorInterface.get_editor_scale()
	acceptance.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	form.add_child(acceptance)
	add_item.text = "加入拆单清单"
	add_item.pressed.connect(_stage)
	form.add_child(add_item)
	staged.custom_minimum_size.y = 70 * EditorInterface.get_editor_scale()
	box.add_child(staged)
	remove.text = "移除所选条目"
	remove.pressed.connect(_remove_selected)
	box.add_child(remove)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)


func _visibility_changed() -> void:
	if not dialog.visible:
		generation += 1
		items.clear()
		staged.clear()
		module.clear()
		paragraph.clear()
		task_title.clear()
		acceptance.clear()
		call_id = ""
		route = ""
		status.text = ""


func _open() -> void:
	if dialog.visible or not signoff.split.is_visible_in_tree():
		return
	var attempt := generation
	route = "/api/v1/docs/%s/versions/%d/tasks" % [signoff.document_id.uri_encode(), signoff.version]
	dialog.title = "拆为模块任务 · %s · v%d" % [signoff.document_id, signoff.version]
	dialog.get_ok_button().text = "生成工单"
	dialog.get_ok_button().disabled = true
	form.show()
	remove.show()
	add_item.disabled = true
	for i in signoff.view.paragraphs.item_count:
		paragraph.add_item(signoff.view.paragraphs.get_item_text(i))
	status.text = "正在读取项目模块…"
	dialog.popup_centered()
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/business-modules")
	if generation != attempt:
		return
	if reply.status == 200:
		for entry: Dictionary in reply.data.get("modules", []):
			module.add_item(str(entry.name))
			module.set_item_metadata(module.item_count - 1, entry.id)
	add_item.disabled = module.item_count == 0 or paragraph.item_count == 0
	status.text = "没有可用的段落或模块。" if add_item.disabled else "为每个条目选择来源段落和模块，填写标题及验收条件。"


func _stage() -> void:
	var item := {"paragraph": paragraph.selected + 1, "module_id": module.get_selected_metadata(),
		"title": task_title.text.strip_edges(), "acceptance": acceptance.text.strip_edges()}
	if item.title.is_empty() or item.acceptance.is_empty() or item.acceptance.length() > 8000:
		status.text = "请输入工单标题和 1 至 8000 字的验收条件。"
		return
	if items.has(item) or items.size() >= 50:
		status.text = "条目已存在，或已达到每次 50 项的上限。"
		return
	items.append(item)
	staged.add_item("第 %d 段 · %s · %s" % [item.paragraph, module.get_item_text(module.selected), item.title])
	staged.set_item_tooltip(staged.item_count - 1, item.acceptance)
	task_title.clear()
	acceptance.clear()
	status.text = "待生成 %d 张工单。" % items.size()
	dialog.get_ok_button().disabled = false


func _remove_selected() -> void:
	var selected := staged.get_selected_items()
	if selected.is_empty():
		return
	items.remove_at(selected[0])
	staged.remove_item(selected[0])
	dialog.get_ok_button().disabled = items.is_empty()
	status.text = "待生成 %d 张工单。" % items.size()


func _submit() -> void:
	if dialog.get_ok_button().disabled or items.is_empty():
		return
	if not task_title.text.strip_edges().is_empty() or not acceptance.text.strip_edges().is_empty():
		status.text = "请将正在编辑的条目加入清单，或清空后生成。"
		return
	var attempt := generation
	if call_id.is_empty():
		call_id = JSON.stringify([session.get_identity().project, route, items]).sha256_text()
	dialog.get_ok_button().disabled = true
	form.hide()
	remove.hide()
	status.text = "正在生成工单…"
	var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, route, {"call_id": call_id, "items": items})
	if generation != attempt:
		return
	var labels := _receipt_labels(reply.data.get("tasks")) if reply.status == 200 else PackedStringArray()
	if labels.size() == items.size():
		status.text = "已生成：" + "、".join(labels)
	elif reply.status in [0, 200] or reply.status >= 500:
		status.text = "回执待核对，请重试同一请求。"
		dialog.get_ok_button().text = "重试生成"
		dialog.get_ok_button().disabled = false
	else:
		status.text = "生成失败（%d）。请关闭并重新核对修订、条目和权限。" % reply.status


func _receipt_labels(tasks: Variant) -> PackedStringArray:
	var labels := PackedStringArray()
	if not tasks is Array or tasks.size() != items.size():
		return labels
	var ids := {}
	for index in items.size():
		var task: Variant = tasks[index]
		if not task is Dictionary or not task.get("id") is String or task.id.is_empty() or ids.has(task.id):
			return PackedStringArray()
		var item := items[index]
		var source: Variant = task.get("design_source")
		if not source is Dictionary or task.get("title") != item.title or int(task.get("number", 0)) <= 0:
			return PackedStringArray()
		if source.get("document_id") != signoff.document_id or int(source.get("version", 0)) != signoff.version:
			return PackedStringArray()
		if source.get("project") != session.get_identity().project or source.get("module_id") != item.module_id:
			return PackedStringArray()
		if int(source.get("paragraph", 0)) != item.paragraph or source.get("acceptance") != item.acceptance:
			return PackedStringArray()
		ids[task.id] = true
		labels.append("#%d %s" % [int(task.number), task.title])
	return labels
