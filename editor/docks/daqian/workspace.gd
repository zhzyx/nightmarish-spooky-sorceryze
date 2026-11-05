@tool
extends VBoxContainer

var rules: Script
var graph_script: Script
var models_script: Script
var models_dialog: AcceptDialog
var editor
var overview: GraphEdit
var notice: Label
var search: LineEdit
var status: OptionButton
var owner_filter: OptionButton
var follow: SpinBox
var board := {}
var saved := {}
var actions: HBoxContainer
var chat: Control
var current := ""
var pending_menu: MenuButton
var draft_menu: MenuButton
var pending_result := ""
var reader_pid := -1
var return_button: Button
var io_timer: Timer
var save_timer: Timer
var picker_scope := ""
var started := false
var debug_process := {}
var debug_timer: Timer
var debug_buffer := PackedByteArray()
var debug_issue := ""
var debug_states := {}
var debug_history: Array = []
var debug_seed := ""
const DEBUG_MODELS := ["调试 · Claude","调试 · Gemini","调试 · GPT","调试 · DeepSeek"]
var host: Object
var selection_epoch := 0


func _ready() -> void:
	var row := HBoxContainer.new()
	add_child(row)
	return_button = _button(row, "工单总图", _show_board)
	_button(row, "新建需求", _new_requirement)
	draft_menu = MenuButton.new()
	draft_menu.text = "个人草稿"
	draft_menu.about_to_popup.connect(_list_drafts)
	draft_menu.get_popup().id_pressed.connect(_restore_personal)
	row.add_child(draft_menu)
	_button(row, "刷新", refresh)
	search = LineEdit.new()
	search.placeholder_text = "搜索编号或标题"
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search.text_changed.connect(func(_text): _filter_board())
	row.add_child(search)
	pending_menu = MenuButton.new()
	pending_menu.text = "待办"
	pending_menu.get_popup().id_pressed.connect(_locate_pending)
	row.add_child(pending_menu)
	status = OptionButton.new()
	status.item_selected.connect(func(_index): _filter_board())
	row.add_child(status)
	owner_filter = OptionButton.new()
	owner_filter.item_selected.connect(func(_index): _filter_board())
	row.add_child(owner_filter)
	follow = SpinBox.new()
	follow.min_value = 1
	follow.max_value = 99999999
	follow.tooltip_text = "要主动跟进的工单编号"
	row.add_child(follow)
	_button(row, "跟进", _follow)
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(notice)
	actions = HBoxContainer.new()
	add_child(actions)
	_button(actions, "仅推演", _chat_action.bind("preview"))
	_button(actions, "创建并执行", _chat_action.bind("execute"))
	_button(actions, "关联对话", _chat_action.bind("discuss"))
	_button(actions, "调试运行", _start_debug)
	_button(actions, "结束调试", _stop_debug)
	overview = GraphEdit.new()
	overview.name = "IssueOverview"
	overview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	overview.zoom_min = 0.1
	overview.zoom_max = 3.0
	overview.minimap_enabled = true
	overview.gui_input.connect(func(_event): _zoom_detail.call_deferred())
	overview.popup_request.connect(func(_position): _new_requirement())
	add_child(overview)
	editor = graph_script.new()
	editor.rules = rules
	editor.visible = false
	editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	models_dialog = models_script.new()
	add_child(models_dialog)
	models_dialog.connect("catalog_changed",_catalog_changed)
	editor.debug_command.connect(_debug_command)
	editor.configure_model.connect(func(): models_dialog.popup_centered())
	editor.draft_changed.connect(_queue_save)
	editor.answer_requested.connect(_answer_question)
	add_child(editor)
	save_timer = Timer.new()
	save_timer.one_shot = true
	save_timer.wait_time = 0.4
	save_timer.timeout.connect(_save)
	add_child(save_timer)
	debug_timer = Timer.new()
	debug_timer.wait_time = 0.08
	debug_timer.timeout.connect(_debug_update)
	add_child(debug_timer)
	io_timer = Timer.new()
	io_timer.wait_time = 0.15
	io_timer.timeout.connect(_receive)
	add_child(io_timer)
	visibility_changed.connect(_opened)
	get_window().files_dropped.connect(_drop_images)
	_load_personal()
	var last: String = saved.get("last_view","")
	_show_board()
	if not last.is_empty() and saved.get("drafts",{}).has(last):
		var prior: Dictionary = saved.drafts[last]
		_show_issue(last,{"revision":prior.revision,"plan":prior.baseline,"context":prior.get("context",{})})
	_attach_chat.call_deferred()
	_opened.call_deferred()


func _button(parent: Control, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _opened() -> void:
	if is_visible_in_tree() and not started:
		started = true
		refresh()


func _repo() -> String:
	var settings := EditorInterface.get_editor_settings()
	if settings.has_setting("gonggong/workspace"):
		return str(settings.get_setting("gonggong/workspace")).strip_edges()
	return ""


func _private_path() -> String:
	var scope := _repo().sha256_text().left(24)
	return EditorInterface.get_editor_paths().get_project_settings_dir().path_join("daqian-" + scope + ".cache")


func _load_personal() -> void:
	picker_scope = _repo()
	saved = {}
	if FileAccess.file_exists(_private_path()):
		var file := FileAccess.open(_private_path(), FileAccess.READ)
		if file and file.get_length() > 0:
			var value = file.get_var(false)
			if value is Dictionary:
				saved = value
	board = saved.get("board", {})
	if saved.has("zoom"):
		overview.zoom = saved.zoom
		overview.scroll_offset = saved.scroll


func _capture() -> void:
	if not current.is_empty():
		if not saved.has("drafts"):
			saved.drafts = {}
		saved.drafts[current] = {"revision":editor.revision, "graph":editor.draft.duplicate(true),
			"positions":editor.positions.duplicate(true), "baseline":editor.baseline.duplicate(true),
			"context":editor.context.duplicate(true),"zoom":editor.canvas.zoom,"scroll":editor.canvas.scroll_offset,
			"answers":editor.answers.duplicate(),"debug_models":editor.debug_models.duplicate()}
	saved.last_view = current
	saved.zoom = overview.zoom
	saved.scroll = overview.scroll_offset
	saved.board = board


func _queue_save() -> void:
	if is_instance_valid(save_timer):
		save_timer.start()


func _save() -> void:
	if picker_scope != _repo():
		return
	_capture()
	var path := _private_path()
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if file:
		file.store_var(saved)
		file.close()
		if DirAccess.rename_absolute(path + ".tmp", path) != OK:
			notice.text = "个人草稿保存失败"


func _exit_tree() -> void:
	_stop_debug(false)
	if is_instance_valid(editor) and is_instance_valid(overview):
		_save()


func _show_board() -> void:
	selection_epoch += 1
	if not current.is_empty():
		_save()
	current = ""
	saved.last_view = ""
	editor.hide()
	actions.hide()
	overview.show()
	return_button.hide()
	_draw_board()


func _draw_board() -> void:
	for child in overview.get_children():
		if child is GraphNode:
			overview.remove_child(child)
			child.queue_free()
	overview.clear_connections()
	var statuses := ["全部状态", "待我处理"]
	var owners := ["全部负责人"]
	var rows: Array = board.get("issues", [])
	pending_menu.get_popup().clear()
	var by_url := {}
	for index in rows.size():
		var item: Dictionary = rows[index]
		var card := GraphNode.new()
		card.name = "i_" + str(item.number)
		card.title = "#%s  %s" % [item.number, item.title]
		card.tooltip_text = item.url
		card.position_offset = saved.get("positions", {}).get(item.url, Vector2(38 + index % 5 * 375, 75 + index / 5 * 177))
		card.position_offset_changed.connect(func():
			if not saved.has("positions"):
				saved.positions = {}
			saved.positions[item.url] = card.position_offset
			_queue_save())
		var label := Label.new()
		label.text = item.status + ("  ·  需要决定" if item.decision else "")
		if item.decision:
			label.modulate = Color("#edbe66")
		card.add_child(label)
		if item.decision:
			pending_menu.get_popup().add_item("#%s  %s" % [item.number,item.title],int(item.number))
		var detail := VBoxContainer.new()
		detail.name = "StepDetails"
		for node in item.get("plan",{}).get("nodes",{}).values():
			if node.kind == "text":
				continue
			var line := Label.new()
			line.text = str(node.title) + " · " + str(node.value).left(32)
			line.tooltip_text = node.value
			detail.add_child(line)
		card.add_child(detail)
		card.set_slot(0, true, 0, Color.GRAY, true, 0, Color.GRAY)
		_button(card, "查看流程", _open_issue.bind(item))
		overview.add_child(card)
		by_url[item.url] = card.name
		if item.status not in statuses:
			statuses.append(item.status)
		for name_text in item.owners:
			if name_text not in owners:
				owners.append(name_text)
	for item in rows:
		for dep in item.dependencies:
			if by_url.has(dep):
				overview.connect_node(by_url[dep], 0, by_url[item.url], 0)
	pending_menu.text = "待办 (%d)" % pending_menu.get_popup().item_count
	var dock := get_parent() as EditorDock
	if dock:
		dock.title = "大千" if pending_menu.get_popup().item_count == 0 else "大千 (%d)" % pending_menu.get_popup().item_count
	_zoom_detail()
	_fill_filter(status, statuses)
	_fill_filter(owner_filter, owners)
	_filter_board()
	notice.text = "已核实 %s · %s 个工单" % [board.verified_at,rows.size()] if board.has("verified_at") else "跟进工单或创建需求以开始"


func _zoom_detail() -> void:
	for card in overview.get_children():
		if card is GraphNode and card.has_node("StepDetails"):
			card.get_node("StepDetails").visible = overview.zoom >= 1.2


func _locate_pending(number: int) -> void:
	_show_board()
	status.select(0)
	owner_filter.select(0)
	search.clear()
	_filter_board()
	var card := overview.get_node_or_null(NodePath("i_" + str(number))) as GraphNode
	if card:
		overview.scroll_offset = (card.position_offset + card.size * 0.5) * overview.zoom - overview.size * 0.5
		card.selected = true


func _fill_filter(control: OptionButton, values: Array) -> void:
	var selected := control.text
	control.clear()
	for value in values:
		control.add_item(value)
		if selected == value:
			control.select(control.item_count-1)


func _filter_board() -> void:
	if not is_instance_valid(status) or not is_instance_valid(owner_filter):
		return
	for item in board.get("issues", []):
		var node := overview.get_node_or_null(NodePath("i_" + str(item.number))) as GraphNode
		if not node:
			continue
		var query := search.text.strip_edges().to_lower().trim_prefix("#")
		var matches := query.is_empty() or query in str(item.number) or query in str(item.title).to_lower()
		node.visible = matches and (status.selected <= 0 or (status.selected == 1 and item.decision) or status.text == item.status) and (owner_filter.selected <= 0 or owner_filter.text in item.owners)


func _follow() -> void:
	var numbers: Array = saved.get("following", [])
	if int(follow.value) not in numbers:
		numbers.append(int(follow.value))
	saved.following = numbers
	_save()
	refresh()


func refresh() -> void:
	if reader_pid != -1:
		return
	if _repo() != picker_scope:
		current = ""
		_load_personal()
		_show_board()
	var bridge := _repo().path_join("customizations/components/godot-host/daqian/board.py")
	if not _repo().is_absolute_path() or not FileAccess.file_exists(bridge):
		notice.text = "请在 AI 对话的共工设置中选择包含大千接入的仓库。可继续编排个人草稿。"
		return
	var settings := EditorInterface.get_editor_settings()
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	pending_result = EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-" + Crypto.new().generate_random_bytes(12).hex_encode() + ".json")
	var args := PackedStringArray([bridge, "--repo", _repo(), "--result", pending_result, "--follow"])
	for number in saved.get("following", []):
		args.append(str(number))
	reader_pid = OS.create_process(python,args)
	if reader_pid < 0:
		notice.text = "无法启动共工 Python 工单入口；已保留快照"
		return
	notice.text = "正在回读工单与依赖…"
	io_timer.start()


func _receive() -> void:
	if not FileAccess.file_exists(pending_result) and OS.is_process_running(reader_pid):
		return
	io_timer.stop()
	reader_pid = -1
	var value = null
	if FileAccess.file_exists(pending_result):
		value = JSON.parse_string(FileAccess.get_file_as_string(pending_result))
		DirAccess.remove_absolute(pending_result)
	if not value is Dictionary or not value.has("board"):
		notice.text = "工单读取失败 · 上次核实 %s" % board.get("verified_at","尚无快照")
		if value is Dictionary:
			notice.text += " · " + str(value.get("error",""))
		return
	board = value.board
	_draw_board()
	_queue_save()


func _open_issue(item: Dictionary) -> void:
	var plan: Dictionary = item.get("plan", rules.new_plan()).duplicate(true)
	plan.nodes["requirement"] = {"kind":"text","title":"需求 · #" + str(item.number),"value":item.title}
	var ctx := {"protected_nodes":plan.nodes.keys(),"sources":item.get("sources", {}),"states":{"requirement":item.status}}
	if item.decision:
		plan.nodes["decision"] = {"kind":"question","title":"待决定","value":""}
		plan.edges.append({"from":"requirement","to":"decision","kind":"after"})
		ctx.protected_nodes.append("decision")
	ctx.protected_edges = plan.edges.duplicate(true)
	var snapshot := {"revision":item.updated,"plan":plan,"context":ctx}
	selection_epoch += 1
	var epoch := selection_epoch
	notice.text = "正在读取 #" + str(item.number) + " 的最新流程…"
	var port: Object = host if is_instance_valid(host) else self
	var live: Dictionary = await port.read_graph(item.url)
	if epoch != selection_epoch:
		return
	if live.has("plan"):
		snapshot = live
	_show_issue(item.url, snapshot)
	if live.has("source_mode"):
		notice.text = item.url + (" · 共享计划宿主" if live.source_mode == "shared_host" else " · 当前安装的计划")
	if live.has("error"):
		notice.text = str(live.error) + " · 显示最近工单快照"


func _list_drafts() -> void:
	draft_menu.get_popup().clear()
	for id in saved.get("drafts", {}):
		if not str(id).begins_with("draft_"):
			continue
		var requirement: Dictionary = saved.drafts[id].graph.nodes.get("requirement", {})
		var title := str(requirement.get("value", "")).strip_edges().get_slice("\n", 0).left(60)
		draft_menu.get_popup().add_item(title if title else "未命名需求")
		draft_menu.get_popup().set_item_metadata(draft_menu.get_popup().item_count - 1, id)


func _restore_personal(index: int) -> void:
	var id: String = draft_menu.get_popup().get_item_metadata(index)
	_show_issue(id, {"revision":"", "plan":rules.new_plan(), "context":{}})


func _new_requirement() -> void:
	selection_epoch += 1
	var plan: Dictionary = rules.new_plan()
	plan.nodes["requirement"] = {"kind":"text","title":"需求","value":""}
	var key := "draft_" + Crypto.new().generate_random_bytes(10).hex_encode()
	_show_issue(key, {"revision":"","plan":plan,"context":{}})
	_save()


func _show_issue(id: String, snapshot: Dictionary) -> void:
	if not current.is_empty():
		_save()
	current = id
	var port: Object = host if is_instance_valid(host) else self
	var apply_port := Callable(port,"apply_graph") if id.begins_with("https://") else Callable()
	var read_port := Callable(port,"read_graph") if id.begins_with("https://") else Callable()
	editor.debug_active = current == debug_issue and not debug_process.is_empty()
	editor.debug_states = debug_states.duplicate(true) if editor.debug_active else {}
	editor.bind_issue(id,snapshot,apply_port,read_port)
	var stored: Dictionary = saved.get("drafts", {}).get(id,{})
	if stored.has("graph"):
		editor.draft = stored.graph
		editor.positions = stored.positions
		editor.answers = stored.get("answers",{})
		editor.debug_models = stored.get("debug_models",{})
		editor.canvas.zoom = stored.get("zoom",1.0)
		editor.canvas.scroll_offset = stored.get("scroll",Vector2.ZERO)
		editor.revision = stored.revision
		editor.baseline = stored.baseline
		editor.draw_graph()
	editor.show()
	actions.show()
	actions.get_child(0).visible = id.begins_with("draft_")
	actions.get_child(1).visible = id.begins_with("draft_") and not saved.get("linked", {}).has(id)
	overview.hide()
	return_button.show()
	notice.text = id if id.begins_with("https://") else "个人需求草稿"


func _drop_images(paths: PackedStringArray) -> void:
	if not is_visible_in_tree() or not editor.is_visible_in_tree() or not editor.canvas.get_global_rect().has_point(editor.canvas.get_global_mouse_position()):
		return
	for path in paths:
		if path.get_extension().to_lower() in ["png", "jpg", "jpeg", "webp"]:
			var image := Image.load_from_file(path)
			if image and not image.is_empty():
				var at: Vector2 = (editor.canvas.get_local_mouse_position() + editor.canvas.scroll_offset) / editor.canvas.zoom
				editor.set_image(editor.add_node("image",at),image)


func read_graph(id: String) -> Dictionary:
	return await _graph_command(id,"read",{})


func apply_graph(id: String, revision: String, execution_revision: String, plan: Dictionary) -> Dictionary:
	return await _graph_command(id,"apply",{"revision":revision,"execution_revision":execution_revision,"plan":plan})


func _graph_command(id: String, action: String, request: Dictionary) -> Dictionary:
	var number := id.get_file()
	var expected := "https://github.com/" + str(board.get("repo", "")) + "/issues/" + number
	if id != expected or not number.is_valid_int() or int(number) <= 0:
		return {"error":"工单与当前绑定仓库不匹配"}
	var path := _repo().path_join("customizations/components/godot-host/daqian/graph_host.py")
	if not _repo().is_absolute_path() or not FileAccess.file_exists(path):
		return {"error":"未连接工单流程宿主"}
	var settings := EditorInterface.get_editor_settings()
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	var stem := EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-" + Crypto.new().generate_random_bytes(12).hex_encode())
	var result_path := stem + ".result"
	var req_path := stem + ".request"
	var args := PackedStringArray([path, "--repo",_repo(),"--number",number,"--result",result_path,action])
	if action == "apply":
		var f := FileAccess.open(req_path,FileAccess.WRITE)
		if not f:
			return {"error":"无法保存本次提交请求"}
		f.store_string(JSON.stringify(request))
		f.close()
		args.append_array(["--request",req_path])
	var pid := OS.create_process(python,args)
	if pid >= 0:
		while not FileAccess.file_exists(result_path) and OS.is_process_running(pid):
			await get_tree().create_timer(0.12).timeout
	if FileAccess.file_exists(req_path):
		DirAccess.remove_absolute(req_path)
	if FileAccess.file_exists(result_path):
		var result = JSON.parse_string(FileAccess.get_file_as_string(result_path))
		DirAccess.remove_absolute(result_path)
		if result is Dictionary:
			return result
	return {"error":"没有收到宿主回执，请回读原工单后再操作"}

func _attach_chat() -> void:
	chat = get_tree().root.find_child("AI Chat", true, false)
	if chat and chat.has_signal("daqian_issue_bound"):
		chat.connect("daqian_issue_bound",_issue_bound)
		chat.connect("daqian_preview_received",_preview_received)


func _issue_bound(source: String, number: int, request_id: String) -> void:
	if not saved.has("linked"):
		saved.linked = {}
	saved.linked[source] = {"number":number,"request":request_id}
	var numbers: Array = saved.get("following",[])
	if number not in numbers:
		numbers.append(number)
	saved.following = numbers
	if current == source:
		actions.get_child(1).hide()
	_save()
	refresh()


func _chat_action(action: String) -> void:
	if not chat or not chat.has_method("open_daqian_chat"):
		notice.text = "无法取得共工 AI 对话入口"
		return
	var binding: Dictionary = saved.get("linked",{}).get(current,{})
	for item in board.get("issues",[]):
		if item.url == current:
			binding = item
	var message := ""
	if action != "discuss":
		message = str(editor.draft.nodes.get("requirement",{}).get("value","")).strip_edges()
		if message.is_empty():
			notice.text = "请先填写需求"
			return
	if action == "preview":
		message = "仅推演。按共工偃师的需求结构整理以下需求，只输出 JSON 对象，scope、acceptance、questions 各为字符串数组。列出适用步骤和真实需要决定的问题。\n" + message
	_save()
	var error: String = chat.open_daqian_chat(current, int(binding.get("number",0)),str(binding.get("request","")),message,action=="preview")
	if not error.is_empty():
		notice.text = error


func _preview_received(source: String, text: String) -> void:
	var body := text.strip_edges()
	if body.begins_with("```json") and body.ends_with("```"):
		body = body.trim_prefix("```json").trim_suffix("```").strip_edges()
	var proposal = JSON.parse_string(body)
	if not proposal is Dictionary or not saved.get("drafts",{}).has(source):
		return
	for field in ["scope","acceptance","questions"]:
		if not proposal.get(field) is Array or proposal[field].size() > 20:
			return
		for value in proposal[field]:
			if not value is String or value.strip_edges().is_empty() or value.length() > 2000:
				return
	var plan: Dictionary = saved.drafts[source].graph.duplicate(true)
	for field in ["scope","acceptance","questions"]:
		for value in proposal[field]:
			var id := "pred_" + (str(field) + str(value)).sha256_text().left(24)
			if plan.nodes.has(id):
				continue
			var kind: String = {"scope":"task","acceptance":"join","questions":"question"}[field]
			var title: String = {"scope":"预计任务","acceptance":"预计验收","questions":"待确认"}[field]
			plan.nodes[id] = {"kind":kind,"title":title,"value":value}
			if kind == "task":
				plan.edges.append({"from":"requirement","to":id,"kind":"data"})
	saved.drafts[source].graph = plan
	if current == source:
		editor.draft = plan
		editor.draw_graph()
	_save()


func _answer_question(id: String, answer: String) -> void:
	if debug_issue == current and not debug_process.is_empty():
		_debug_command("answer",id,answer)
		return
	if not chat or not editor.draft.nodes.has(id):
		return
	for item in board.get("issues",[]):
		if item.url == current and not str(item.request).is_empty():
			var question: Dictionary = editor.draft.nodes[id]
			var message := "答复工单 #%s 的问题「%s」\n%s" % [item.number,question.get("value",question.title),answer]
			var error: String = chat.open_daqian_chat(current,int(item.number),item.request,message,false)
			notice.text = error if error else "已交给关联对话，等待共工回执"
			return
	notice.text = "工单尚无可验证的需求绑定，答复保留在节点上"

func _catalog_changed() -> void:
	if not current.begins_with("https://"):
		editor.notice.text = "配置已保存，执行节点将按实测能力分配模型"
		return
	var id := current
	var snapshot: Dictionary = await read_graph(id)
	if current == id and snapshot.has("context"):
		editor.context = snapshot.context
		editor.draw_graph()
		editor.notice.text = "已回读模型库；能力证据不足的型号保留待评测状态"

func _start_debug() -> void:
	if not debug_process.is_empty():
		notice.text = "已有调试会话，请结束后再启动"
		return
	var test_ctx: Dictionary = editor.context.duplicate(true)
	var capabilities: Dictionary = test_ctx.get("models",{})
	for label in DEBUG_MODELS:
		capabilities[label] = ["text","image"]
	test_ctx.models = capabilities
	var error: String = rules.changes_error(editor.baseline,editor.draft,test_ctx)
	if error:
		notice.text = error
		return
	var path := _repo().path_join("customizations/components/godot-host/daqian/debug_session.mjs")
	if not _repo().is_absolute_path() or not FileAccess.file_exists(path):
		notice.text = "请在 AI 对话中绑定包含大千调试宿主的仓库"
		return
	var settings := EditorInterface.get_editor_settings()
	var node: String = str(settings.get_setting("ai_chat/cli_node")) if settings.has_setting("ai_chat/cli_node") else ""
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	if node.is_empty():
		node = "node"
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	debug_issue = current
	debug_buffer = PackedByteArray()
	debug_states.clear()
	debug_history.clear()
	var plan: Dictionary = editor.draft.duplicate(true)
	for id in plan.nodes:
		if plan.nodes[id].kind == "task":
			plan.nodes[id].model = editor.debug_models.get(id,"")
	debug_seed = EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-loopback-" + Crypto.new().generate_random_bytes(12).hex_encode() + ".json")
	var file := FileAccess.open(debug_seed,FileAccess.WRITE)
	if not file:
		notice.text = "无法暂存本次调试请求"
		return
	file.store_string(JSON.stringify({"action":"start","plan":plan,"python":python}))
	file.close()
	debug_process = OS.execute_with_pipe(node,[path,debug_seed],false)
	if debug_process.is_empty():
		DirAccess.remove_absolute(debug_seed)
		notice.text = "无法启动 Node 调试宿主，请核对可执行路径"
		debug_issue = ""
		return
	editor.debug_active = true
	editor.draw_graph()
	debug_timer.start()
	notice.text = "调试运行 · 仅使用本机协议夹具"


func _debug_command(action: String,id: String,value: String) -> void:
	if debug_process.is_empty() or debug_issue != current:
		return
	var pipe: FileAccess = debug_process.stdio
	debug_timer.start()
	pipe.store_line(JSON.stringify({"action":action,"id":id,"model":value,"value":value}))
	pipe.flush()


func _debug_update() -> void:
	var pipe: FileAccess = debug_process.stdio
	if pipe.get_length()>0:
		debug_buffer.append_array(pipe.get_buffer(pipe.get_length()))
	var newline := debug_buffer.find(10)
	while newline >= 0:
		var event = JSON.parse_string(debug_buffer.slice(0,newline).get_string_from_utf8())
		debug_buffer = debug_buffer.slice(newline+1)
		if event is Dictionary and event.has("id"):
			debug_states[event.id] = event
			debug_history.append(event)
			if current == debug_issue:
				editor.set_debug_state(event)
		elif event is Dictionary and event.has("error"):
			notice.text = event.error
		elif event is Dictionary and event.get("idle",false):
			debug_timer.stop()
			notice.text = "本轮调试已就绪或结束 · 可答复、重跑或结束调试"
		newline = debug_buffer.find(10)
	if not OS.is_process_running(debug_process.pid):
		_stop_debug()


func _stop_debug(redraw := true) -> void:
	if debug_process.is_empty():
		return
	# Closing stdin lets the host terminate its own workers and close the fixture socket.
	debug_process.clear()
	if not debug_seed.is_empty() and FileAccess.file_exists(debug_seed):
		DirAccess.remove_absolute(debug_seed)
	debug_seed = ""
	debug_issue = ""
	debug_states.clear()
	if is_instance_valid(debug_timer):
		debug_timer.stop()
	if is_instance_valid(editor):
		editor.debug_active = false
		editor.debug_states.clear()
		if redraw and editor.is_inside_tree():
			editor.draw_graph()
