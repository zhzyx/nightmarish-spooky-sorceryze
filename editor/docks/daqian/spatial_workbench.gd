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
var installed := false
var scope := ""
var next_check := 0
var pending_sources := {}
var mapping := VBoxContainer.new()
var actions := HFlowContainer.new()

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
	button(bar, "天枢总览", func(): close_chat(); workspace.get_parent().make_visible())
	button(bar, "刷新", func(): load_links(); workspace._manual_refresh(); update_view(true))
	button(bar, "收起", func(): toggle.button_pressed = false)
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(heading)
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(feedback)
	rows.custom_minimum_size.y = 110 * panel.get_theme_default_base_scale()
	rows.item_selected.connect(func(_index): generation += 1; draw_details())
	panel.add_child(rows)
	details.custom_minimum_size.y = 100 * panel.get_theme_default_base_scale()
	details.size_flags_vertical = Control.SIZE_EXPAND_FILL
	details.selection_enabled = true
	panel.add_child(details)
	panel.add_child(actions)
	button(actions, "工单详情", open_detail)
	button(actions, "工单聊天", open_chat.bind(false))
	button(actions, "新任务", open_chat.bind(true))
	button(actions, "关联与内容…", func(): mapping.visible = not mapping.visible)
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
		feedback.text = links_error
		return false
	var lock_path := ProjectSettings.globalize_path(LINKS_PATH) + ".lock"
	if DirAccess.make_dir_recursive_absolute(lock_path.get_base_dir()) != OK or DirAccess.make_dir_absolute(lock_path) != OK:
		feedback.text = "模型关联正在由其他操作保存，或目录不可写。请稍后重试。"
		return false
	var result := save_locked(candidate)
	DirAccess.remove_absolute(lock_path)
	return result

func save_locked(candidate: Dictionary) -> bool:
	var current_hash := FileAccess.get_sha256(LINKS_PATH) if FileAccess.file_exists(LINKS_PATH) else ""
	if current_hash != links_hash:
		load_links()
		update_view(true)
		feedback.text = "模型关联已被其他操作更新；已回读，请重新选择后保存。"
		return false
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(LINKS_PATH.get_base_dir())) != OK:
		feedback.text = "无法创建模型关联目录。"
		return false
	var temporary := LINKS_PATH + "." + Crypto.new().generate_random_bytes(8).hex_encode() + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if not file:
		feedback.text = "模型关联保存失败。"
		return false
	file.store_string(JSON.stringify({"version":1, "repositories":candidate}, "\t") + "\n")
	file.flush()
	var error := file.get_error()
	file.close()
	if error != OK or DirAccess.rename_absolute(ProjectSettings.globalize_path(temporary), ProjectSettings.globalize_path(LINKS_PATH)) != OK:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(temporary))
		feedback.text = "模型关联保存失败，原记录保留。"
		return false
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
	feedback.text = links_error if not links_error.is_empty() else ("离线 / 进度待核实" if workspace.offline or not workspace.fresh_progress else "天枢工单 · " + current_scope())
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
		feedback.text = "请先选择模型并连接天枢，回读要关联的工单。"
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
		feedback.text = "先将模型关联到所选工单。"
		return
	if not path.begins_with("res://") or path.contains("..") or path.contains("::") or path.length() > 1024:
		feedback.text = "请输入项目内 res:// 路径。"
		return
	var candidate := links.duplicate(true)
	var entry: Dictionary = candidate[current_scope()][selection.key][item.url]
	if not entry.get("contents", []) is Array: return
	if not entry.has("contents"): entry.contents = []
	if not entry.contents.has(path): entry.contents.append(path)
	if save_links(candidate): output_path.clear()

func open_detail() -> void:
	var item := selected_issue()
	if item.is_empty(): return
	close_chat()
	workspace.get_parent().make_visible()
	workspace._show_board()
	workspace._preview_board_issue(item.url)

func open_chat(new_task: bool) -> void:
	if opening: return
	selection_changed()
	var frozen := selection.duplicate(true)
	var epoch := generation
	var root: String = workspace._repo()
	var actor: Dictionary = workspace.actor.duplicate(true)
	var item := {} if new_task else selected_issue().duplicate(true)
	if not new_task and (item.is_empty() or item.get("unverified", false)):
		feedback.text = "请先回读并选择工单。"
		return
	opening = true
	var allowed: bool = await workspace._fresh_access()
	opening = false
	selection_changed()
	if not allowed or epoch != generation or actor != workspace.actor or root != workspace._repo() or not panel.is_visible_in_tree(): return
	if not is_instance_valid(workspace.chat):
		feedback.text = "天枢聊天尚未就绪。"
		return
	if not new_task:
		if selected_issue().get("url", "") != item.url: return
		var found := false
		for row in workspace.board.get("issues", []):
			if row == item: found = true
		if not found:
			feedback.text = "工单已经变化，请刷新后重新打开。"
			return
	close_chat()
	workspace._leave_conversation()
	var source: String = "spatial_" + (current_scope() + str(frozen.get("key", "overview"))).sha256_text() if new_task else str(item.url)
	if new_task and not frozen.is_empty():
		pending_sources[source] = {"repo":current_scope(), "asset":frozen.key, "actor":actor, "root":root}
		EditorInterface.get_editor_settings().set_project_metadata("tianshu_spatial", "pending_sources", pending_sources)
	var error: String = workspace.chat.open_daqian_chat(source, int(item.get("number", 0)), str(item.get("request", "")), "", false, {}, true, "", false if new_task else workspace._has_started_worker(item))
	if not error.is_empty():
		feedback.text = error
		return
	if not workspace.chat.mount_daqian_chat(chat_host):
		feedback.text = "聊天当前已挂载到其他视图，请先返回该视图。"
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
	feedback.text = error if not error.is_empty() else "在下方聊天补充任务后发送。"

func chat_unmounted() -> void:
	owns_chat = false
	chat_host.hide()
	chat_caption.text = ""
	chat_caption.hide()
	rows.show()
	details.show()
	actions.show()

func close_chat() -> void:
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
