@tool
extends EditorPlugin

# A view of the existing workbench, not another worker or source of execution authority.
const LINKS_PATH := "res://.gonggong/asset-work.json"
var workspace
var panel := VBoxContainer.new()
var toggle := Button.new()
var heading := Label.new()
var feedback := Label.new()
var rows := ItemList.new()
var details := RichTextLabel.new()
var picker := OptionButton.new()
var output_path := LineEdit.new()
var chat_host := VBoxContainer.new()
var chat_caption := Label.new()
var selection := {}
var selected_id := 0
var generation := 0
var links := {}
var links_hash := ""
var links_error := ""
var rendered_rows: Array = []
var signature := ""
var owns_chat := false
var opening := false
var action_feedback := ""
var installed := false
var scope := ""
var next_check := 0
var pending_sources := {}
var mapping := VBoxContainer.new()
var actions := HFlowContainer.new()
var drawer := VBoxContainer.new()
var inspector
var operation_panel
var question_box := VBoxContainer.new()
var reply_controls := 0
var detail_binding := {}
var detail_snapshot := {}
var answer_drafts := {}
var submitting := false

func button(parent: Control, text: String, action: Callable) -> Button:
	var control := Button.new()
	control.text = text
	control.pressed.connect(action)
	parent.add_child(control)
	return control

func build(owner_workspace) -> void:
	workspace = owner_workspace
	panel.name = "Tianshu3DPanel"
	panel.custom_minimum_size.x = 320 * panel.get_theme_default_base_scale()
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.hide()
	toggle.name = "Tianshu3DToggle"
	toggle.text = "天枢"
	toggle.toggle_mode = true
	toggle.toggled.connect(func(visible_now):
		panel.visible = visible_now
		if not visible_now: close_chat()
		else: update_view(true))
	add_control_to_container(CONTAINER_SPATIAL_EDITOR_MENU, toggle)
	add_control_to_container(CONTAINER_SPATIAL_EDITOR_SIDE_RIGHT, panel)
	installed = true
	var bar := HFlowContainer.new()
	panel.add_child(bar)
	button(bar, "工作区连接", open_connection)
	button(bar, "天枢总览", func(): close_chat(); workspace.get_parent().make_visible())
	button(bar, "刷新", func(): load_links(); workspace._manual_refresh(); update_view(true))
	button(bar, "收起", func(): toggle.button_pressed = false)
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(heading)
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(feedback)
	rows.custom_minimum_size.y = 110 * panel.get_theme_default_base_scale()
	rows.item_selected.connect(func(_index): generation += 1; close_detail(); draw_details())
	panel.add_child(rows)
	details.custom_minimum_size.y = 100 * panel.get_theme_default_base_scale()
	details.size_flags_vertical = Control.SIZE_EXPAND_FILL
	details.selection_enabled = true
	panel.add_child(details)
	panel.add_child(actions)
	button(actions, "工单详情", open_detail)
	button(actions, "答复 / 推进", open_response)
	button(actions, "工单聊天", open_chat.bind(false))
	button(actions, "新任务", open_chat.bind(true))
	button(actions, "关联与内容…", func(): mapping.visible = not mapping.visible)
	panel.add_child(drawer)
	drawer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	drawer.hide()
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	drawer.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(content)
	inspector = workspace.inspector_script.new()
	content.add_child(inspector)
	inspector.field.custom_minimum_size.y = 180
	inspector.relations.custom_minimum_size.y = 65
	# Design is read-only here; mutations continue through the existing workbench.
	inspector.save.hide()
	inspector.revert.hide()
	inspector.reload_requested.connect(open_detail)
	question_box.name = "InlineQuestions"
	content.add_child(question_box)
	operation_panel = workspace.details_script.new()
	content.add_child(operation_panel)
	operation_panel.build()
	operation_panel.custom_minimum_size.x = 0
	operation_panel.card_requested.connect(confirm_operation)
	operation_panel.status_changed.connect(show_feedback)
	operation_panel.operation_checked.connect(func(): workspace.refresh(); close_detail())
	panel.add_child(mapping)
	mapping.hide()
	picker.fit_to_longest_item = false
	picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	picker.tooltip_text = "从天枢已回读工单中选择，显式关联当前模型"
	mapping.add_child(picker)
	var binding_actions := HFlowContainer.new()
	mapping.add_child(binding_actions)
	button(binding_actions, "关联模型", bind_issue)
	button(binding_actions, "解除关联", unbind_issue)
	output_path.placeholder_text = "制作内容 / 产物路径：res://…"
	output_path.tooltip_text = "显式登记预期或已有项目内容；是否存在会单独显示，不代表已验收"
	mapping.add_child(output_path)
	button(mapping, "登记到所选工单", register_content)
	chat_caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(chat_caption)
	button(panel, "返回模型工单", close_chat)
	chat_host.name = "Tianshu3DChatHost"
	chat_host.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(chat_host)
	chat_host.hide()
	EditorInterface.get_selection().selection_changed.connect(selection_changed)
	if is_instance_valid(workspace.chat):
		workspace.chat.daqian_chat_unmounted.connect(chat_unmounted)
		workspace.chat.daqian_issue_bound.connect(issue_bound)
	var restored = EditorInterface.get_editor_settings().get_project_metadata("tianshu_spatial", "pending_sources", {})
	if restored is Dictionary: pending_sources = restored
	load_links()
	selection_changed()
	set_process(true)

func _exit_tree() -> void:
	close_chat()
	if installed:
		remove_control_from_container(CONTAINER_SPATIAL_EDITOR_MENU, toggle)
		remove_control_from_container(CONTAINER_SPATIAL_EDITOR_SIDE_RIGHT, panel)
	toggle.queue_free()
	panel.queue_free()

func current_scope() -> String:
	return str(workspace.actor.get("repo", ""))

func describe_selection() -> Dictionary:
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	var root := EditorInterface.get_edited_scene_root()
	if nodes.size() != 1 or not is_instance_valid(root): return {}
	var node = nodes[0]
	if not node is Node3D or not node.is_inside_tree() or (node != root and not root.is_ancestor_of(node)): return {}
	# Imported instance identity is the source scene, shared by all instances. A
	# built-in model is identified within its saved owner scene, never by name alone.
	var asset: String = node.scene_file_path
	var ancestor: Node = node
	while asset.is_empty() and ancestor != root:
		ancestor = ancestor.get_parent()
		asset = ancestor.scene_file_path if ancestor != root else ""
	if asset.is_empty() and node is MeshInstance3D and node.mesh:
		var resource: String = node.mesh.resource_path
		if resource.begins_with("res://") and not resource.contains("::"): asset = resource
	var scene: String = root.scene_file_path
	if scene.is_empty(): return {}
	var node_path := str(root.get_path_to(node))
	var key := asset if not asset.is_empty() else scene + "::" + node_path
	return {"key":key, "asset":asset, "scene":scene, "node":node_path, "name":str(node.name), "id":node.get_instance_id()}

func selection_changed() -> void:
	var fresh := describe_selection()
	if fresh == selection: return
	generation += 1
	selection = fresh
	action_feedback = ""
	selected_id = int(selection.get("id", 0))
	close_chat()
	output_path.clear()
	update_view(true)

func _process(_delta: float) -> void:
	# Local projection only. Network updates remain owned by the existing workbench.
	if Time.get_ticks_msec() < next_check: return
	next_check = Time.get_ticks_msec() + 250
	if describe_selection() != selection: selection_changed()
	var identity := JSON.stringify([workspace._repo(), workspace.actor])
	if scope != identity:
		scope = identity
		generation += 1
		close_chat()
		update_view(true)
	if panel.is_visible_in_tree(): update_view()

func load_links() -> void:
	links = {}
	links_error = ""
	links_hash = FileAccess.get_sha256(LINKS_PATH) if FileAccess.file_exists(LINKS_PATH) else ""
	if links_hash.is_empty(): return
	var value = JSON.parse_string(FileAccess.get_file_as_string(LINKS_PATH))
	if not value is Dictionary or value.get("version") != 1 or not value.get("repositories") is Dictionary:
		links_error = "模型关联文件无效，已保留原文件。"
		return
	links = value.repositories
	for repository in links.values():
		if not repository is Dictionary:
			links_error = "模型关联记录格式无效，已保留原文件。"
			links = {}
			return
		for entries in repository.values():
			if not entries is Dictionary or entries.values().any(func(entry): return not entry is Dictionary or not entry.get("contents", []) is Array):
				links_error = "模型关联记录格式无效，已保留原文件。"
				links = {}
				return

func save_links(candidate: Dictionary) -> bool:
	if not links_error.is_empty():
		show_feedback(links_error)
		return false
	var lock_path := ProjectSettings.globalize_path(LINKS_PATH) + ".lock"
	if DirAccess.make_dir_recursive_absolute(lock_path.get_base_dir()) != OK or DirAccess.make_dir_absolute(lock_path) != OK:
		show_feedback("模型关联正在由其他操作保存，或目录不可写。请稍后重试。")
		return false
	var result := save_locked(candidate)
	DirAccess.remove_absolute(lock_path)
	return result

func save_locked(candidate: Dictionary) -> bool:
	var current_hash := FileAccess.get_sha256(LINKS_PATH) if FileAccess.file_exists(LINKS_PATH) else ""
	if current_hash != links_hash:
		load_links()
		update_view(true)
		show_feedback("模型关联已被其他操作更新；已回读，请重新选择后保存。")
		return false
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(LINKS_PATH.get_base_dir())) != OK:
		show_feedback("无法创建模型关联目录。")
		return false
	var temporary := LINKS_PATH + "." + Crypto.new().generate_random_bytes(8).hex_encode() + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if not file:
		show_feedback("模型关联保存失败。")
		return false
	file.store_string(JSON.stringify({"version":1, "repositories":candidate}, "\t") + "\n")
	file.flush()
	var error := file.get_error()
	file.close()
	if error != OK or DirAccess.rename_absolute(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(LINKS_PATH)) != OK:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(temporary))
		show_feedback("模型关联保存失败，原记录保留。")
		return false
	action_feedback = ""
	links = candidate
	links_hash = FileAccess.get_sha256(LINKS_PATH)
	update_view(true)
	return true

func model_links() -> Dictionary:
	var repository = links.get(current_scope(), {})
	if not repository is Dictionary: return {}
	var value = repository.get(selection.get("key", ""), {})
	return value if value is Dictionary else {}

func selected_issue() -> Dictionary:
	var indices := rows.get_selected_items()
	if indices.is_empty() or indices[0] >= rendered_rows.size(): return {}
	return rendered_rows[indices[0]]

func update_view(force := false) -> void:
	if not is_instance_valid(workspace): return
	var board_rows: Array = workspace.board.get("issues", [])
	var fingerprint := JSON.stringify([selection, current_scope(), board_rows, workspace.offline, workspace.fresh_progress, model_links(), workspace.chat_work])
	if not force and fingerprint == signature: return
	signature = fingerprint
	var previous := str(selected_issue().get("url", ""))
	heading.text = "选中一个已保存场景中的 3D 模型，查看关联制作任务" if selection.is_empty() else "模型 · %s\n%s" % [selection.name, selection.key]
	feedback.text = action_feedback if not action_feedback.is_empty() else links_error if not links_error.is_empty() else ("离线 / 进度待核实" if workspace.offline or not workspace.fresh_progress else "天枢工单 · " + current_scope())
	rows.clear()
	picker.clear()
	rendered_rows.clear()
	var associated := model_links()
	for item in board_rows:
		picker.add_item("#%s %s" % [item.number, item.title])
		picker.set_item_metadata(picker.item_count - 1, item.url)
		if not selection.is_empty() and not associated.has(item.url): continue
		rendered_rows.append(item)
		var status_text: String = workspace.graph_script.FlowCanvas.state_text(workspace._display_state(item))
		rows.add_item("#%s · %s · %s" % [item.number, status_text, item.title])
		if item.url == previous: rows.select(rows.item_count - 1)
	# Keep explicit associations visible even when outside this board scope/offline.
	for url in associated:
		if rendered_rows.any(func(item): return item.get("url") == url): continue
		var entry = associated[url]
		if not entry is Dictionary: continue
		var item := {"url":url,"number":entry.get("number",0),"title":"关联工单 · 当前画板未回读","status":"未知","unverified":true}
		rendered_rows.append(item)
		rows.add_item("#%s · 待回读" % item.number)
		if url == previous: rows.select(rows.item_count - 1)
	if rows.item_count > 0 and rows.get_selected_items().is_empty(): rows.select(0)
	if not detail_binding.is_empty() and detail_binding != action_binding(): close_detail()
	draw_details()

func draw_details() -> void:
	details.clear()
	var item := selected_issue()
	if item.is_empty():
		details.add_text("尚未关联工单。选择下方工单后点击「关联模型」。" if not selection.is_empty() else "天枢缩略总览。选中模型后仅显示其显式关联工单。")
		return
	details.add_text("#%s %s\n" % [item.number, item.title])
	if not item.get("unverified", false): details.add_text(str(workspace._work_summary(item, {}).get("text", "")) + "\n")
	else: details.add_text("请在天枢总览切换项目范围并刷新；未核实前不启动此工单。\n")
	var document: Dictionary = item.get("design_document", {})
	if not document.is_empty(): details.add_text("制作需求 · " + str(document.get("path", "")) + "\n" + str(document.get("markdown", "")).left(2500) + "\n")
	var entry = model_links().get(item.url, {})
	var contents = entry.get("contents", []) if entry is Dictionary else []
	if not contents is Array: contents = []
	for path in contents:
		if not path is String: continue
		details.add_text("制作内容 · %s · %s\n" % [path, "文件已存在（未代表验收）" if FileAccess.file_exists(path) else "待制作 / 文件未找到"])
	if contents.is_empty(): details.add_text("暂无登记的制作内容或产物。")

func bind_issue() -> void:
	selection_changed()
	if selection.is_empty() or current_scope().is_empty() or picker.selected < 0 or workspace.offline:
		show_feedback("请先选择模型并连接天枢，回读要关联的工单。")
		return
	var url: String = picker.get_selected_metadata()
	var item := {}
	for row in workspace.board.get("issues", []):
		if row.url == url: item = row
	if item.is_empty(): return
	var candidate := links.duplicate(true)
	if not candidate.has(current_scope()): candidate[current_scope()] = {}
	if not candidate[current_scope()] is Dictionary: return
	if not candidate[current_scope()].has(selection.key): candidate[current_scope()][selection.key] = {}
	var entries: Dictionary = candidate[current_scope()][selection.key]
	if not entries.has(url): entries[url] = {"number":item.number,"request":item.get("request",""),"contents":[]}
	save_links(candidate)

func unbind_issue() -> void:
	var item := selected_issue()
	if selection.is_empty() or item.is_empty(): return
	var candidate := links.duplicate(true)
	if candidate.get(current_scope(), {}).has(selection.key):
		candidate[current_scope()][selection.key].erase(item.url)
		save_links(candidate)

func register_content() -> void:
	var item := selected_issue()
	var path := output_path.text.strip_edges()
	if selection.is_empty() or item.is_empty() or not model_links().has(item.get("url", "")):
		show_feedback("先将模型关联到所选工单。")
		return
	if not path.begins_with("res://") or path.contains("..") or path.contains("::") or path.length() > 1024:
		show_feedback("请输入项目内 res:// 路径。")
		return
	var candidate := links.duplicate(true)
	var entry: Dictionary = candidate[current_scope()][selection.key][item.url]
	if not entry.get("contents", []) is Array: return
	if not entry.has("contents"): entry.contents = []
	if not entry.contents.has(path): entry.contents.append(path)
	if save_links(candidate): output_path.clear()

func action_binding() -> Dictionary:
	var item := selected_issue()
	return {"root":workspace._repo(), "actor":workspace.actor.duplicate(true), "epoch":generation,
		"model":selection.duplicate(true), "url":item.get("url", ""), "request":item.get("request", ""),
		"updated":item.get("updated", ""), "source":item.get("source_sha256", "")}

func binding_current(binding: Dictionary) -> bool:
	return panel.is_visible_in_tree() and describe_selection() == selection and binding == action_binding()

func close_detail() -> void:
	detail_binding = {}
	detail_snapshot = {}
	drawer.hide()
	if not owns_chat: details.show()
	if is_instance_valid(operation_panel): operation_panel.dismiss()

func open_detail() -> Dictionary:
	var item := selected_issue().duplicate(true)
	if item.is_empty() or item.get("unverified", false):
		show_feedback("请刷新并选择已回读的工单。")
		return {}
	close_chat()
	var binding := action_binding()
	detail_binding = binding
	drawer.show()
	details.hide()
	mapping.hide()
	inspector.show()
	inspector.show_overview()
	inspector.summary.text = "#%s · %s" % [item.number, item.title]
	inspector.issue_link.hide()
	var preview: Dictionary = item.get("design_document", {}).duplicate(true)
	preview.editable = false
	inspector.set_document(preview)
	inspector.set_related([], "正在读取关联工单…", workspace.graph_script.FlowCanvas.state_text)
	inspector.feedback.text = "正在读取工单详情…"
	clear_questions()
	if workspace.offline or workspace.actor.is_empty():
		inspector.feedback.text = "离线快照 · 连接后刷新详情并答复"
		return {}
	var result: Dictionary = await workspace.read_issue_details(item)
	if not binding_current(binding) or detail_binding != binding: return {}
	var document: Dictionary = result.get("document", preview).duplicate(true)
	document.editable = false
	inspector.set_document(document)
	inspector.set_related(result.get("related", []), "暂无已核实的关联工单", workspace.graph_script.FlowCanvas.state_text)
	inspector.feedback.text = str(result.get("error", result.get("warning", "")))
	var snapshot: Dictionary = await workspace.read_graph(item.url)
	if not binding_current(binding) or detail_binding != binding: return {}
	detail_snapshot = snapshot
	draw_questions()
	var operation: Dictionary = workspace._pending_operation(item)
	if not operation.is_empty():
		operation_panel.display(item, operation, workspace.chat.render_daqian_markdown)
		operation_panel.details_confirm.text = "确认此操作"
	show_feedback(str(snapshot.error) if snapshot.has("error") else "可在此查看详情、提交答复，或进入下方工单聊天继续推进。")

	return binding

func clear_questions() -> void:
	reply_controls = 0
	for child in question_box.get_children():
		question_box.remove_child(child)
		child.queue_free()

func draft_key(id: String) -> String:
	return JSON.stringify([detail_binding.get("root"), detail_binding.get("actor"), detail_binding.get("model", {}).get("key"), detail_binding.get("url"), detail_binding.get("request"), detail_snapshot.get("revision", ""), id])

func draw_questions() -> void:
	clear_questions()
	var context: Dictionary = detail_snapshot.get("context", {})
	for id in context.get("questions", {}):
		if context.get("answers", {}).has(id): continue
		var request: Dictionary = context.questions[id]
		var prompt := Label.new()
		prompt.text = str(request.get("prompt", "待你答复"))
		prompt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		question_box.add_child(prompt)
		if not context.get("can_answer", false): continue
		reply_controls += 1
		if request.get("kind") == "image":
			button(question_box, "在工单聊天中答复图片问题", open_chat.bind(false))
			continue
		var key := draft_key(id)
		var send := Button.new()
		send.text = "提交答复"
		send.name = "SubmitInlineReply"
		var options: Array = request.get("options", [])
		if not options.is_empty():
			var choose := OptionButton.new()
			choose.name = "InlineAnswer"
			choose.disabled = submitting
			choose.add_item("请选择")
			for option in options:
				choose.add_item(str(option))
				if answer_drafts.get(key, "") == option: choose.select(choose.item_count - 1)
			choose.item_selected.connect(func(index):
				answer_drafts[key] = choose.get_item_text(index) if index else ""
				send.disabled = submitting or index == 0)
			question_box.add_child(choose)
		else:
			var input := TextEdit.new()
			input.name = "InlineAnswer"
			input.editable = not submitting
			input.placeholder_text = "你的答复"
			input.custom_minimum_size.y = 65
			input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
			input.text = str(answer_drafts.get(key, ""))
			input.text_changed.connect(func():
				answer_drafts[key] = input.text
				send.disabled = submitting or input.text.strip_edges().is_empty())
			question_box.add_child(input)
		send.disabled = submitting or str(answer_drafts.get(key, "")).strip_edges().is_empty() or (not options.is_empty() and answer_drafts.get(key) not in options)
		send.pressed.connect(submit_answer.bind(str(id)))
		question_box.add_child(send)

func submit_answer(id: String) -> void:
	var binding := detail_binding.duplicate(true)
	var snapshot := detail_snapshot.duplicate(true)
	var key := draft_key(id)
	var answer: String = str(answer_drafts.get(key, "")).strip_edges()
	var context: Dictionary = snapshot.get("context", {})
	var options: Array = context.get("questions", {}).get(id, {}).get("options", [])
	if submitting or not binding_current(binding) or not context.get("can_answer", false) or not context.get("questions", {}).has(id) or context.get("answers", {}).has(id) or answer.is_empty() or (not options.is_empty() and answer not in options): return
	submitting = true
	draw_questions()
	show_feedback("正在核对身份并提交答复…")
	var allowed: bool = await workspace._fresh_access()
	if not allowed or not binding_current(binding) or detail_binding != binding:
		submitting = false
		if drawer.visible: draw_questions()
		if detail_binding == binding:
			show_feedback("答复未发送；身份或模型工单已改变，草稿保留。" + workspace.notice.text)
		return
	var result: Dictionary = await workspace._graph_command(binding.url, "answer", {"revision":snapshot.get("revision", ""), "node":id, "value":answer})
	submitting = false
	if not binding_current(binding) or detail_binding != binding:
		if drawer.visible: draw_questions()
		return
	if not result.get("ok", false):
		draw_questions()
		show_feedback(str(result.get("error", "未收到答复回执，草稿已保留；请刷新核对。")))
		return
	answer_drafts.erase(key)
	detail_snapshot.context = result.get("context", context)
	draw_questions()
	workspace.refresh()
	show_feedback("已记录答复。可点击「答复 / 推进」在原工单聊天继续。")

func open_response() -> void:
	var binding: Dictionary = await open_detail()
	if binding.is_empty() or detail_binding != binding or not binding_current(binding): return
	if operation_panel.visible or reply_controls > 0: return
	await open_chat(false)

func approval_binding() -> Dictionary:
	var result := action_binding()
	result.visible = panel.is_visible_in_tree() and describe_selection() == selection
	result.token = workspace._pending_operation(selected_issue()).get("token", "") if drawer.visible else ""
	return result

func confirm_operation(token: String) -> void:
	var url: String = selected_issue().get("url", "")
	await operation_panel.confirm(token, approval_binding, workspace._board_command, workspace._pending_operation,
		func(verified_token): return workspace.chat.confirm_daqian_issue_approval(url, verified_token))

func show_feedback(message: String) -> void:
	action_feedback = message
	feedback.text = message

func open_connection() -> void:
	close_chat()
	workspace.get_parent().make_visible()
	workspace._open_connection()

func open_chat(new_task: bool) -> void:
	if opening:
		show_feedback("正在核对协作者身份，请稍候…")
		return
	selection_changed()
	var frozen := selection.duplicate(true)
	var epoch := generation
	var root: String = workspace._repo()
	var actor: Dictionary = workspace.actor.duplicate(true)
	var item := {} if new_task else selected_issue().duplicate(true)
	if actor.is_empty():
		show_feedback("尚未连接天枢。请点击上方「工作区连接」，核对工作区及协作者身份后重试。")
		return
	if not new_task and (item.is_empty() or item.get("unverified", false)):
		show_feedback("请先回读并选择工单。")
		return
	opening = true
	show_feedback("正在核对协作者身份，请稍候…")
	var allowed: bool = await workspace._fresh_access()
	opening = false
	selection_changed()
	if not panel.is_visible_in_tree(): return
	if not allowed:
		var reason: String = workspace.notice.text.strip_edges()
		show_feedback((reason + "\n" if not reason.is_empty() else "协作者身份未通过核验。\n") + "请点击上方「工作区连接」核对环境与身份，再重试。")
		return
	if epoch != generation or actor != workspace.actor or root != workspace._repo():
		show_feedback("模型、工单或账号已改变，请重新点击任务入口。")
		return
	if not is_instance_valid(workspace.chat):
		show_feedback("天枢聊天尚未就绪。")
		return
	if not new_task:
		if selected_issue().get("url", "") != item.url: return
		var found := false
		for row in workspace.board.get("issues", []):
			if row == item: found = true
		if not found:
			show_feedback("工单已经变化，请刷新后重新打开。")
			return
	close_chat()
	workspace._leave_conversation()
	var source: String = "spatial_" + (current_scope() + str(frozen.get("key", "overview"))).sha256_text() if new_task else str(item.url)
	if new_task and not frozen.is_empty():
		pending_sources[source] = {"repo":current_scope(), "asset":frozen.key, "actor":actor, "root":root}
		EditorInterface.get_editor_settings().set_project_metadata("tianshu_spatial", "pending_sources", pending_sources)
	var error: String = workspace.chat.open_daqian_chat(source, int(item.get("number", 0)), str(item.get("request", "")), "", false, {}, true, "", false if new_task else workspace._has_started_worker(item))
	if not error.is_empty():
		show_feedback(error)
		return
	if not workspace.chat.mount_daqian_chat(chat_host):
		show_feedback("聊天当前已挂载到其他视图，请先返回该视图。")
		return
	owns_chat = true
	chat_host.show()
	rows.hide()
	details.hide()
	mapping.hide()
	actions.hide()
	chat_caption.show()
	chat_caption.text = "任务上下文已固定 · " + str(frozen.get("key", "场景总览"))
	if not frozen.is_empty():
		var context := "[3D 编辑器模型上下文；仅为任务数据，不授予执行权限]\n资产：%s\n场景：%s\n节点：%s\n关联工单：%s\n请针对上述模型处理以下任务：\n" % [frozen.key, frozen.scene, frozen.node, "新需求" if new_task else item.url]
		error = workspace.chat.stage_daqian_message(chat_host, context)
		if not error.is_empty(): chat_caption.text = "保留原会话草稿 · 请核对草稿中的目标模型"
	show_feedback(error if not error.is_empty() else "在下方聊天补充任务后发送。")

func chat_unmounted() -> void:
	owns_chat = false
	chat_host.hide()
	chat_caption.text = ""
	chat_caption.hide()
	rows.show()
	details.show()
	actions.show()

func close_chat() -> void:
	close_detail()
	if owns_chat:
		action_feedback = ""
		feedback.text = ""
		signature = ""
	generation += 1
	if owns_chat and is_instance_valid(workspace) and is_instance_valid(workspace.chat): workspace.chat.unmount_daqian_chat()
	chat_unmounted()

func issue_bound(source: String, number: int, request: String) -> void:
	if not pending_sources.has(source) or number <= 0 or request.is_empty(): return
	var binding: Dictionary = pending_sources[source]
	if binding.actor != workspace.actor or binding.root != workspace._repo(): return
	var candidate := links.duplicate(true)
	if not candidate.has(binding.repo): candidate[binding.repo] = {}
	if not candidate[binding.repo].has(binding.asset): candidate[binding.repo][binding.asset] = {}
	var url := "https://github.com/%s/issues/%d" % [binding.repo, number]
	if not candidate[binding.repo][binding.asset].has(url):
		candidate[binding.repo][binding.asset][url] = {"number":number,"request":request,"contents":[]}
	if save_links(candidate):
		if not workspace.saved.has("linked"): workspace.saved.linked = {}
		workspace.saved.linked[source] = {"number":number,"request":request,"url":url}
		var following: Array = workspace.saved.get("following", [])
		if number not in following: following.append(number)
		workspace.saved.following = following
		workspace._save()
		workspace.refresh()
		pending_sources.erase(source)
		EditorInterface.get_editor_settings().set_project_metadata("tianshu_spatial", "pending_sources", pending_sources)
