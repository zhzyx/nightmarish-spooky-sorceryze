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
var publish_button: Button
var publish_dialog: ConfirmationDialog
var requirement_input: TextEdit
var route: OptionButton
var category: OptionButton
var choose_execution_model := CheckButton.new()
var model_label: Label
var direct_in_flight := {}
var starting_direct := {}
var model_options: OptionButton
var manual_model: LineEdit
var publish_status: Label
var publish_backend := -1
var publish_source := ""
var publish_generation := 0
var submitting := false
var chat: Control
var current := ""
var pending_menu: MenuButton
var draft_menu: MenuButton
var actor := {}
var checking := false
var offline := false
var toolbar: HBoxContainer
var return_button: Button
var save_timer: Timer
var picker_scope := ""
var debug_process := {}
var debug_timer: Timer
var debug_buffer := PackedByteArray()
var debug_issue := ""
var debug_states := {}
var debug_history: Array = []
var debug_sessions := {}
var history_dialog: AcceptDialog
var history_view: TextEdit
var debug_serial := 0
const DEBUG_MODELS := ["调试 · Claude","调试 · Gemini","调试 · GPT","调试 · DeepSeek"]
var host: Object
var selection_epoch := 0


func _ready() -> void:
	var row := HBoxContainer.new()
	toolbar = row
	add_child(row)
	return_button = _button(row, "工单总图", _show_board)
	_button(row, "新建需求", _compose_requirement)
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
	publish_button = _button(actions, "发布需求…", _publish_or_follow)
	_build_publish_dialog()
	_button(actions, "关联对话", _chat_action.bind("discuss"))
	_button(actions, "调试运行", _start_debug)
	_button(actions, "结束调试", _stop_debug)
	_button(actions, "调试记录", _show_debug_history)
	history_dialog = AcceptDialog.new()
	history_dialog.title = "此工单的本机调试记录"
	history_view = TextEdit.new()
	history_view.editable = false
	history_view.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	history_view.custom_minimum_size = Vector2(560,320)
	history_dialog.add_child(history_view)
	add_child(history_dialog)
	overview = GraphEdit.new()
	overview.name = "IssueOverview"
	overview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	overview.zoom_min = 0.1
	overview.zoom_max = 3.0
	overview.minimap_enabled = true
	overview.gui_input.connect(func(_event): _zoom_detail.call_deferred())
	overview.popup_request.connect(func(_position): _compose_requirement())
	add_child(overview)
	editor = graph_script.new()
	editor.rules = rules
	editor.visible = false
	editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	models_dialog = models_script.new()
	add_child(models_dialog)
	models_dialog.connect("catalog_changed",_catalog_changed)
	editor.debug_command.connect(_debug_command)
	editor.configure_model.connect(_open_models)
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
	visibility_changed.connect(_opened)
	get_window().files_dropped.connect(_drop_images)
	_gate_visibility(false)
	notice.text = "等待核对当前仓库协作者身份"
	_attach_chat.call_deferred()
	_opened.call_deferred()


func _button(parent: Control, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _opened() -> void:
	if is_visible_in_tree():
		refresh()


func _repo() -> String:
	var settings := EditorInterface.get_editor_settings()
	if settings.has_setting("gonggong/workspace"):
		return str(settings.get_setting("gonggong/workspace")).strip_edges()
	return ""


func _private_path() -> String:
	var scope := (_repo() + "|" + str(actor.get("repo_id","")) + "|" + str(actor.get("user_id",""))).sha256_text().left(24)
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
	if actor.is_empty() or picker_scope != _repo():
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
	_stop_debug(false,true)
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
	var waiting_inputs := 0
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
			waiting_inputs += maxi(1,int(item.get("pending_count",1)))
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
	pending_menu.text = "待办 (%d)" % waiting_inputs
	var dock := get_parent() as EditorDock
	if dock:
		dock.title = "大千" if waiting_inputs == 0 else "大千 (%d)" % waiting_inputs
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
	if actor.is_empty():
		return
	var numbers: Array = saved.get("following", [])
	if int(follow.value) not in numbers:
		numbers.append(int(follow.value))
	saved.following = numbers
	_save()
	refresh()


func _gate_visibility(opened: bool) -> void:
	for child in toolbar.get_children():
		child.visible = opened or child is Button and child.text == "刷新"
	return_button.visible = opened and not current.is_empty()
	actions.visible = opened and not current.is_empty()
	overview.visible = opened and current.is_empty()
	editor.visible = opened and not current.is_empty()
	if not opened:
		models_dialog.hide()
		publish_dialog.hide()
		history_dialog.hide()
		history_view.clear()
		draft_menu.get_popup().hide()


func _forget(reason: String) -> void:
	selection_epoch += 1
	_stop_debug(false,true)
	_save()
	actor = {}
	offline = false
	board = {}
	saved = {}
	current = ""
	editor.generation += 1
	editor.draft = rules.new_plan()
	editor.baseline = rules.new_plan()
	editor.context = {}
	editor.positions = {}
	editor.answers = {}
	editor.draw_graph()
	_gate_visibility(false)
	get_parent().title = "大千"
	notice.text = reason


func _access_key() -> String:
	return _repo().sha256_text()


func _board_command(access_only: bool, expected := "") -> Dictionary:
	var root := _repo()
	var bridge := root.path_join("customizations/components/godot-host/daqian/board.py")
	if not root.is_absolute_path() or not FileAccess.file_exists(bridge):
		return {"denied":true,"error":"请在 AI 对话的共工设置中绑定当前 Git 仓库"}
	var settings := EditorInterface.get_editor_settings()
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	var path := EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-" + Crypto.new().generate_random_bytes(12).hex_encode() + ".json")
	var args := PackedStringArray([bridge,"--repo",root,"--result",path])
	if access_only:
		args.append("--access-only")
	else:
		args.append("--follow")
		for number in saved.get("following",[]):
			args.append(str(number))
	if expected != "":
		args.append_array(["--expected-user",expected])
	var pid := OS.create_process(python,args)
	if pid < 0:
		return {"denied":true,"error":"无法启动共工身份核验入口"}
	while not FileAccess.file_exists(path) and OS.is_process_running(pid):
		await get_tree().create_timer(0.12).timeout
	if not FileAccess.file_exists(path):
		return {"denied":true,"error":"未收到共工身份回执"}
	var value = JSON.parse_string(FileAccess.get_file_as_string(path))
	DirAccess.remove_absolute(path)
	if root != _repo() or not value is Dictionary:
		return {"denied":true,"error":"工作区已切换或回执无效"}
	return value


func _fresh_access() -> bool:
	if actor.is_empty():
		return false
	var check: Dictionary = await _board_command(true,actor.user_id)
	if not check.has("access"):
		if check.get("denied",true):
			EditorInterface.get_editor_settings().set_project_metadata("daqian_access",_access_key(),{})
			_forget(str(check.get("error","仓库协作资格未核实")))
		else:
			notice.text = "当前离线，须重新核实协作者身份后提交"
		return false
	return check.access == actor


func _open_models() -> void:
	if await _fresh_access():
		models_dialog.user_id = actor.user_id
		models_dialog.popup_centered()


func refresh() -> void:
	if checking:
		while checking:
			await get_tree().process_frame
		return
	checking = true
	var previous := actor.duplicate()
	_gate_visibility(false)
	notice.text = "正在核对当前仓库的协作资格…"
	var response: Dictionary = await _board_command(true)
	var settings := EditorInterface.get_editor_settings()
	var auth: Dictionary = response.get("access",{})
	offline = false
	if auth.is_empty():
		var prior: Dictionary = settings.get_project_metadata("daqian_access",_access_key(),{})
		var last_login: String = response.get("offline_login","")
		if not response.get("denied",true) and not last_login.is_empty() and prior.get("actor",{}).get("login","")==last_login and Time.get_unix_time_from_system()-float(prior.get("checked",0)) < 86400:
			auth = prior.actor
			offline = true
		else:
			settings.set_project_metadata("daqian_access",_access_key(),{})
			_forget(str(response.get("error","当前账号的仓库协作身份未核实")))
			checking = false
			return
	else:
		settings.set_project_metadata("daqian_access",_access_key(),{"actor":auth,"checked":Time.get_unix_time_from_system()})
	if previous != auth or picker_scope != _repo():
		_stop_debug(false,true)
		current = ""
		actor = auth
		_load_personal()
		var last: String = saved.get("last_view","")
		_show_board()
		if saved.get("drafts",{}).has(last):
			var prior: Dictionary = saved.drafts[last]
			_show_issue(last,{"revision":prior.revision,"plan":prior.baseline,"context":prior.get("context",{})})
	_gate_visibility(true)
	if offline:
		notice.text = "离线个人快照 · " + str(actor.login) + " · 上次核实 " + str(board.get("verified_at","未知"))
	else:
		var value: Dictionary = await _board_command(false,actor.user_id)
		if value.has("board") and value.board.user_id == actor.get("user_id",""):
			board = value.board
			_draw_board()
			_sync_workflow()
			_queue_save()
		elif value.get("denied",true):
			settings.set_project_metadata("daqian_access",_access_key(),{})
			_forget(str(value.get("error","仓库协作身份已变更")))
		else:
			offline = true
			notice.text = "工单来源暂不可用 · 最近核实 " + str(board.get("verified_at","未知"))
	checking = false


func _open_issue(item: Dictionary) -> void:
	if actor.is_empty():
		return
	var plan: Dictionary = item.get("plan", rules.new_plan()).duplicate(true)
	plan.nodes["requirement"] = {"kind":"text","title":"需求 · #" + str(item.number),"value":plan.nodes.get("requirement", {}).get("value", item.title)}
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
	if live.get("denied",false):
		_forget(str(live.error))
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


func _compose_requirement() -> void:
	_new_requirement()
	_open_publish()


func _build_publish_dialog() -> void:
	publish_dialog = ConfirmationDialog.new()
	publish_dialog.title = "发布需求"
	publish_dialog.dialog_hide_on_ok = false
	publish_dialog.get_ok_button().text = "确认发送并开始分析"
	publish_dialog.get_cancel_button().text = "保存为草稿"
	var fields := VBoxContainer.new()
	publish_dialog.add_child(fields)
	route = OptionButton.new()
	route.add_item("直接创建工单")
	route.add_item("请偃师分析后建单")
	route.item_selected.connect(_select_route)
	fields.add_child(route)
	category = OptionButton.new()
	category.tooltip_text = "工单类别"
	category.item_selected.connect(func(_index): _update_publish_form())
	fields.add_child(category)
	var prompt := Label.new()
	prompt.text = "需求内容"
	fields.add_child(prompt)
	requirement_input = TextEdit.new()
	requirement_input.custom_minimum_size = Vector2(360, 144)
	requirement_input.size_flags_vertical = Control.SIZE_EXPAND_FILL
	requirement_input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	requirement_input.placeholder_text = "描述你希望完成的需求"
	requirement_input.text_changed.connect(_edit_requirement)
	fields.add_child(requirement_input)
	choose_execution_model.text = "指定开始推进时使用的模型"
	choose_execution_model.toggled.connect(func(_on): _select_route(route.selected))
	fields.add_child(choose_execution_model)
	model_label = Label.new()
	model_label.text = "偃师分析模型"
	fields.add_child(model_label)
	model_options = OptionButton.new()
	model_options.item_selected.connect(_select_publish_model)
	fields.add_child(model_options)
	manual_model = LineEdit.new()
	manual_model.placeholder_text = "输入当前连接支持的模型 ID"
	manual_model.max_length = 128
	manual_model.text_changed.connect(func(_value): _update_publish_form())
	fields.add_child(manual_model)
	publish_status = Label.new()
	publish_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(publish_status)
	add_child(publish_dialog)
	publish_dialog.confirmed.connect(_confirm_publish)
	publish_dialog.visibility_changed.connect(_publish_visibility_changed)


func _publish_or_follow() -> void:
	var binding := _direct_binding()
	if not binding.is_empty():
		_start_or_view_direct(binding)
	elif saved.get("submitted", {}).has(current) or saved.get("linked", {}).has(current):
		_chat_action("discuss")
	else:
		_open_publish()


func _direct_binding() -> Dictionary:
	var binding: Dictionary = saved.get("linked", {}).get(current, {})
	if binding.is_empty():
		for row in board.get("issues", []):
			if row.url == current:
				binding = row
				break
	if not str(binding.get("request", "")).begins_with("daqian-direct-"):
		return {}
	for row in board.get("issues", []):
		if row.url == binding.get("url", ""):
			if row.get("request", "") != binding.request or row.number != binding.number:
				return {"error":"工单绑定已改变，请核对原始需求标识。"}
			return row
	return binding


func _start_or_view_direct(binding: Dictionary) -> void:
	if binding.has("error"):
		notice.text = binding.error
		return
	var source := current
	if not await _fresh_access() or source != current:
		return
	if binding != _direct_binding():
		notice.text = "工单已更新，请重新确认。"
		return
	var url: String = binding.url
	if not is_instance_valid(chat):
		notice.text = "无法取得共工 AI 对话入口"
		return
	var started: bool = saved.get("direct_started", {}).has(url)
	if not started and (binding.get("closed", false) or binding.get("status") not in ["planned","in-progress","in-review"]):
		notice.text = "当前工单状态不支持开始推进，请先处理待决定或阻塞事项。"
		return
	var message := "" if started else "核对已绑定工单 #%d 的最新需求、依赖和验收条件，按共工流程开始推进。" % int(binding.number)
	var selection := {}
	if not started:
		var catalog: Dictionary = chat.get_daqian_models()
		selection = saved.get("execution_models", {}).get(url, {"backend":catalog.backend, "id":catalog.current})
		if selection.backend != catalog.backend:
			notice.text = "推进模型所属的后端已改变，请切回创建时选择的 AI 后端后开始。"
			return
		if starting_direct.has(url):
			return
		var user := actor.duplicate()
		var root := _repo()
		var start := {"issue_number":int(binding.number), "request_id":binding.request, "expected_user":user.user_id,
			"expected_revision":binding.get("updated", binding.get("revision", ""))}
		starting_direct[url] = true
		var args := PackedStringArray([root.path_join("tools/gonggong_bridge.py"), "issue-start", "--workspace", root])
		var result: Dictionary = await _host_command(args, "--out", start)
		starting_direct.erase(url)
		if source != current or user != actor or root != _repo():
			return
		if result.get("ok") != true or result.get("status") not in ["status:in-progress","status:in-review"]:
			notice.text = str(result.get("error", "未取得开始推进回执，请刷新后核对。"))
			return
	var error: String = chat.open_daqian_chat(url, int(binding.number), binding.request, message, false, selection)
	if not error.is_empty():
		notice.text = error
		return
	if not saved.has("direct_started"):
		saved.direct_started = {}
	saved.direct_started[url] = true
	publish_button.text = "查看推进对话"
	_save()


func _open_publish() -> void:
	if actor.is_empty() or not current.begins_with("draft_") or saved.get("linked", {}).has(current) or saved.get("submitted", {}).has(current):
		return
	if not editor.draft.nodes.has("requirement"):
		notice.text = "草稿缺少需求节点"
		return
	var available := is_instance_valid(chat) and chat.has_method("get_daqian_models")
	route.set_item_disabled(1, not available)
	var catalog: Dictionary = chat.get_daqian_models() if available else {"backend":-1, "options":[], "current":""}
	publish_backend = catalog.backend
	var pending: Dictionary = saved.get("direct_pending", {}).get(current, {})
	var analyzed: bool = _analysis_route(current) and available and pending.is_empty()
	route.select(1 if analyzed else 0)
	category.clear()
	var labels_path := _repo().path_join(".github/labels.json")
	if FileAccess.file_exists(labels_path):
		var labels = JSON.parse_string(FileAccess.get_file_as_string(labels_path))
		if labels is Array:
			for item in labels:
				var name_text := str(item.get("name", ""))
				if name_text.begins_with("type:"):
					var kind := name_text.trim_prefix("type:")
					category.add_item(str(item.get("description", kind)))
					category.set_item_metadata(category.item_count - 1, kind)
					if kind == pending.get("category", saved.get("categories", {}).get(current, "development")):
						category.select(category.item_count - 1)
	var execution_model: Dictionary = saved.get("execution_models", {}).get(current, {})
	choose_execution_model.set_pressed_no_signal(not execution_model.is_empty() and execution_model.get("backend") == publish_backend)
	var stored: Dictionary = saved.get("publish_models", {}).get(current, {}) if analyzed else execution_model
	var chosen: String = stored.get("id", catalog.current) if stored.get("backend", -1) == publish_backend else catalog.current
	publish_source = current
	requirement_input.text = pending.get("outcome", str(editor.draft.nodes.requirement.value))
	model_options.clear()
	var selected := -1
	for option in catalog.options:
		model_options.add_item(option.label)
		var index := model_options.item_count - 1
		model_options.set_item_metadata(index, option.id)
		if option.id == chosen:
			selected = index
	model_options.add_item("手动填写模型 ID")
	model_options.select(selected if selected >= 0 else model_options.item_count - 1)
	manual_model.text = chosen
	_select_route(route.selected)
	publish_dialog.popup_centered_clamped(Vector2i(540, 360))
	requirement_input.grab_focus()


func _analysis_route(id: String) -> bool:
	return saved.get("routes", {}).get(id, saved.get("intake", {}).has(id) or saved.get("submitted", {}).has(id) or saved.get("publish_models", {}).has(id))


func _select_route(index: int) -> void:
	var analysis := index == 1
	if not saved.has("routes"):
		saved.routes = {}
	saved.routes[current] = analysis
	category.visible = not analysis
	choose_execution_model.visible = not analysis and publish_backend >= 0
	model_label.text = "偃师分析模型" if analysis else "推进模型"
	model_label.visible = analysis or (choose_execution_model.visible and choose_execution_model.button_pressed)
	model_options.visible = model_label.visible
	var pending: bool = saved.get("direct_pending", {}).has(current)
	route.disabled = pending
	category.disabled = pending
	requirement_input.editable = not pending
	publish_dialog.get_ok_button().text = "确认发送并开始分析" if analysis else ("核对建单回执" if pending else "确认创建工单")
	publish_status.text = "确认后由偃师分析需求，并在关联对话中继续推进。" if analysis else ("将按原需求标识核对上次建单结果。" if pending else "按原文登记到当前仓库。工单建立后可开始推进。")
	_select_publish_model(model_options.selected)
	_sync_workflow()


func _selected_model() -> String:
	if manual_model.visible:
		return manual_model.text.strip_edges()
	return str(model_options.get_selected_metadata())


func _select_publish_model(index: int) -> void:
	manual_model.visible = model_options.visible and index == model_options.item_count - 1
	_update_publish_form()


func _update_publish_form() -> void:
	var message := requirement_input.text.strip_edges()
	var missing_model := manual_model.visible and manual_model.text.strip_edges().is_empty()
	var too_long := (message.length() if route.selected == 1 else requirement_input.text.length()) > 16000
	const LIMIT_HINT := "需求正文最多 16000 个字符，请缩短后发送。"
	if too_long:
		publish_status.text = LIMIT_HINT
	elif publish_status.text == LIMIT_HINT:
		publish_status.text = "确认后由偃师分析需求，并在关联对话中继续推进。" if route.selected == 1 else "按原文登记到当前仓库。工单建立后可开始推进。"
	publish_dialog.get_ok_button().disabled = submitting or message.is_empty() or too_long or missing_model or (route.selected == 0 and category.selected < 0) or direct_in_flight.has(current)
	if publish_source == current and not current.is_empty():
		if route.selected == 1:
			if not saved.has("publish_models"):
				saved.publish_models = {}
			saved.publish_models[current] = {"backend":publish_backend, "id":_selected_model()}
		elif category.selected >= 0:
			if not saved.has("execution_models"):
				saved.execution_models = {}
			if model_options.visible:
				saved.execution_models[current] = {"backend":publish_backend, "id":_selected_model()}
			elif choose_execution_model.visible:
				saved.execution_models.erase(current)
			if not saved.has("categories"):
				saved.categories = {}
			saved.categories[current] = category.get_selected_metadata()
		_queue_save()


func _edit_requirement() -> void:
	if publish_source == current and editor.draft.nodes.has("requirement"):
		editor.draft.nodes.requirement.value = requirement_input.text
		_update_publish_form()


func _publish_visibility_changed() -> void:
	if not publish_dialog.visible:
		publish_generation += 1
		submitting = false
		if publish_source == current and not current.is_empty():
			editor.draw_graph()
			_save()
		publish_source = ""


func _confirm_publish() -> void:
	if submitting or publish_dialog.get_ok_button().disabled or publish_source != current or not publish_dialog.visible:
		return
	submitting = true
	var generation := publish_generation
	var source := publish_source
	var selected := {"backend":publish_backend, "id":_selected_model()}
	var model_chosen := model_options.visible
	var analysis := route.selected == 1
	var kind := str(category.get_selected_metadata()) if category.selected >= 0 else ""
	var message := requirement_input.text.strip_edges() if analysis else requirement_input.text
	var epoch := selection_epoch
	publish_dialog.get_ok_button().disabled = true
	publish_status.text = "正在核对协作者身份…"
	var allowed := await _fresh_access()
	if generation != publish_generation:
		return
	submitting = false
	_update_publish_form()
	if not allowed or epoch != selection_epoch or source != current or saved.get("linked", {}).has(source):
		publish_status.text = "发送已中止，请回到草稿核对工单和协作者身份。"
		return
	if analysis != (route.selected == 1) or (model_chosen != model_options.visible) or (model_chosen and selected.id != _selected_model()) or (not analysis and kind != category.get_selected_metadata()) or message != (requirement_input.text.strip_edges() if analysis else requirement_input.text):
		publish_status.text = "需求或模型已变更，请重新确认。"
		return
	if not analysis:
		await _publish_direct(source, message, kind)
		return
	_save()
	var error: String = chat.open_daqian_chat(source, 0, "", message, false, selected)
	if not error.is_empty():
		publish_status.text = error
		return
	if not saved.has("submitted"):
		saved.submitted = {}
	saved.submitted[source] = true
	_sync_workflow()
	publish_button.text = "查看分析进度"
	publish_dialog.hide()
	_save()
	notice.text = "已发送至偃师，请在关联对话中查看分析进度。"


func _publish_direct(source: String, message: String, kind: String) -> void:
	if direct_in_flight.has(source):
		return
	var user: Dictionary = actor.duplicate()
	var root := _repo()
	var request := {"draft_id":source, "expected_user":user.user_id, "category":kind,
		"title":message.strip_edges().get_slice("\n", 0).strip_edges().left(120), "outcome":message}
	var settings := EditorInterface.get_editor_settings()
	var node_runtime := str(settings.get_setting("ai_chat/cli_node")) if settings.has_setting("ai_chat/cli_node") else ""
	if node_runtime.is_absolute_path():
		request.node_runtime = node_runtime
	if not saved.has("direct_pending"):
		saved.direct_pending = {}
	saved.direct_pending[source] = request
	direct_in_flight[source] = true
	_select_route(0)
	publish_status.text = "正在创建或核对工单…"
	_save()
	var args := PackedStringArray([root.path_join("tools/gonggong_bridge.py"), "issue-direct", "--workspace", root])
	var result: Dictionary = await _host_command(args, "--out", request)
	direct_in_flight.erase(source)
	if user != actor or root != _repo():
		return
	var number := int(result.get("number", 0))
	var request_id := "daqian-direct-" + source.trim_prefix("draft_")
	var url := "https://github.com/%s/issues/%d" % [user.repo, number]
	var verified: bool = (result.get("ok") == true and number > 0
		and result.get("request_id") == request_id and result.get("url") == url
		and result.get("status") in ["planned", "needs-decision", "in-progress", "in-review", "blocked"]
		and result.get("revision") is String and not result.revision.is_empty())
	if not verified:
		if result.get("reconcile_required", true) == false:
			saved.direct_pending.erase(source)
		if publish_source == source and publish_dialog.visible:
			_select_route(0)
			publish_status.text = str(result.get("error", "未取得完整建单回执，请核对原请求。"))
		_save()
		return
	saved.direct_pending.erase(source)
	if saved.get("execution_models", {}).has(source):
		saved.execution_models[url] = saved.execution_models[source].duplicate()
	if publish_source == source:
		publish_dialog.hide()
	_issue_bound(source, number, request_id, {"url":url,"revision":result.revision,"status":result.status})
	_sync_workflow()
	_save()
	if current == source:
		publish_button.text = "开始推进"
		notice.text = "已核对工单 #%d · %s" % [number, result.status]


func _new_requirement() -> void:
	if actor.is_empty():
		return
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
	_select_debug(current)
	editor.debug_active = debug_sessions.has(current)
	editor.debug_states = debug_states.duplicate(true)
	editor.workflow = {}
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
	_sync_workflow()
	editor.show()
	actions.show()
	actions.get_child(0).visible = id.begins_with("draft_")
	publish_button.visible = id.begins_with("draft_")
	publish_button.text = "查看分析进度" if saved.get("submitted", {}).has(id) or saved.get("linked", {}).has(id) else "发布需求…"
	_update_direct_action()
	overview.hide()
	return_button.show()
	notice.text = id if id.begins_with("https://") else "个人需求草稿"


func _update_direct_action() -> void:
	var binding := _direct_binding()
	publish_button.disabled = false
	if binding.is_empty():
		return
	publish_button.show()
	if binding.has("error"):
		publish_button.text = "需求标识已改变"
		publish_button.disabled = true
	elif saved.get("direct_started", {}).has(binding.url):
		publish_button.text = "查看推进对话"
	elif binding.get("closed", false) or binding.get("status") not in ["planned","in-progress","in-review"]:
		publish_button.text = "工单已关闭" if binding.get("closed", false) else "等待工单就绪"
		publish_button.disabled = true
	else:
		publish_button.text = "开始推进"


func _drop_images(paths: PackedStringArray) -> void:
	if not is_visible_in_tree() or not editor.is_visible_in_tree() or not editor.canvas.get_global_rect().has_point(editor.canvas.get_global_mouse_position()):
		return
	insert_dropped_images(paths,(editor.canvas.get_local_mouse_position()+editor.canvas.scroll_offset)/editor.canvas.zoom)


func insert_dropped_images(paths: PackedStringArray,at: Vector2) -> void:
	if actor.is_empty() or not editor.visible:
		return
	for path in paths:
		if path.get_extension().to_lower() in ["png", "jpg", "jpeg", "webp"]:
			var image := Image.load_from_file(path)
			if image and not image.is_empty():
				var target: String = editor.pending_image
				if target.is_empty() or not editor.draft.nodes.has(target):
					target = editor.add_node("image",at)
				editor.set_image(target,image)
				editor.pending_image = ""


func read_graph(id: String) -> Dictionary:
	return await _graph_command(id,"read",{})


func apply_graph(id: String, revision: String, execution_revision: String, plan: Dictionary) -> Dictionary:
	return await _graph_command(id,"apply",{"revision":revision,"execution_revision":execution_revision,"plan":plan})


func _graph_command(id: String, action: String, request: Dictionary) -> Dictionary:
	if actor.is_empty() or offline:
		return {"error":"需要已核实的当前仓库协作账号"}
	var number := id.get_file()
	var expected := "https://github.com/" + str(board.get("repo", "")) + "/issues/" + number
	if id != expected or not number.is_valid_int() or int(number) <= 0:
		return {"error":"工单与当前绑定仓库不匹配"}
	var path := _repo().path_join("customizations/components/godot-host/daqian/graph_host.py")
	if not _repo().is_absolute_path() or not FileAccess.file_exists(path):
		return {"error":"未连接工单流程宿主"}
	var args := PackedStringArray([path, "--repo",_repo(),"--number",number,"--expected-user",actor.user_id,action])
	return await _host_command(args, "--result", request)


func _host_command(args: PackedStringArray, output_flag: String, request: Dictionary) -> Dictionary:
	var settings := EditorInterface.get_editor_settings()
	var python: String = str(settings.get_setting("gonggong/python")) if settings.has_setting("gonggong/python") else ""
	if python.is_empty():
		python = "python" if OS.has_feature("windows") else "python3"
	var stem := EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-" + Crypto.new().generate_random_bytes(12).hex_encode())
	var result_path := stem + ".result"
	var req_path := stem + ".request"
	args.append_array([output_flag, result_path])
	if not request.is_empty():
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
		chat.connect("daqian_requirement_phase",_requirement_phase)
		chat.connect("daqian_preview_received",_preview_received)


func _requirement_phase(source: String, phase: String, design: Dictionary) -> void:
	if not saved.get("drafts", {}).has(source) and source != current:
		return
	if not saved.has("intake"):
		saved.intake = {}
	var receipt: Dictionary = saved.intake.get(source, {})
	receipt.phase = phase
	if not design.is_empty():
		receipt.design = design.duplicate(true)
		receipt.erase("issue_design")
		receipt.erase("observed_decision")
	saved.intake[source] = receipt
	_sync_workflow()
	_save()


func _sync_workflow() -> void:
	if current.is_empty() or not editor.draft.nodes.has("requirement"):
		return
	var source := current
	var binding: Dictionary = saved.get("linked", {}).get(source, {})
	var item: Dictionary = {}
	for row in board.get("issues", []):
		if (row.url == current and binding.is_empty()) or (row.number == binding.get("number", 0) and (not str(binding.get("request","")).begins_with("daqian-direct-") or row.get("request","") == binding.request)):
			item = row
			break
	if current.begins_with("https://") and not item.is_empty():
		for key in saved.get("linked", {}):
			if saved.linked[key].number == item.number:
				source = key
				break
	var receipt: Dictionary = saved.get("intake", {}).get(source, {})
	var phase: String = receipt.get("phase", "submitted" if saved.get("submitted", {}).has(source) else "draft")
	if receipt.is_empty() and not item.is_empty():
		phase = "questions" if item.get("decision", false) else "bound"
	var design: Dictionary = receipt.get("design", {}).duplicate()
	if not item.is_empty():
		var clauses := {"scope":[], "acceptance":[], "questions":[]}
		var titles := {"预计任务":"scope", "验收条件":"acceptance", "待确认":"questions"}
		for id in item.get("plan", {}).get("nodes", {}):
			var node: Dictionary = item.plan.nodes[id]
			if item.get("questions", {}).has(id):
				clauses.questions.append(item.questions[id].prompt)
			elif titles.has(node.title):
				clauses[titles[node.title]].append(node.value)
		if not receipt.is_empty():
			if not receipt.has("issue_design"):
				receipt.issue_design = clauses.duplicate(true)
			for field in clauses:
				if clauses[field] != receipt.issue_design[field]:
					design[field] = clauses[field]
		if item.get("closed", false):
			phase = "closed"
		elif item.get("status") == "needs-decision":
			if not receipt.is_empty():
				receipt.observed_decision = true
			phase = "questions"
			if not clauses.questions.is_empty():
				design.questions = clauses.questions
		elif item.get("status") == "blocked":
			phase = "blocked"
		elif receipt.get("observed_decision", false) and phase == "questions" and item.get("status") == "in-progress" and not item.get("decision", false):
			phase = "bound"
			design.questions = clauses.questions
	var direct: bool = str(binding.get("request", item.get("request", ""))).begins_with("daqian-direct-")
	if direct and item.is_empty() and binding.has("status") and not _direct_binding().has("error"):
		item = {"status":binding.status}
		phase = "bound"
	var analyzed: bool = not direct and (item.get("analyzed", false) or not receipt.is_empty() or (source.begins_with("draft_") and _analysis_route(source)))
	_update_direct_action()
	var facts := {"phase":phase, "design":design, "item":item, "analyzed":analyzed}
	if editor.workflow != facts:
		editor.workflow = facts.duplicate(true)
		editor.draw_graph()


func _issue_bound(source: String, number: int, request_id: String, details := {}) -> void:
	if actor.is_empty() or picker_scope != _repo() or (source != current and not saved.get("drafts", {}).has(source)):
		return
	if not saved.has("linked"):
		saved.linked = {}
	saved.linked[source] = {"number":number,"request":request_id}
	saved.linked[source].merge(details)
	var numbers: Array = saved.get("following",[])
	if number not in numbers:
		numbers.append(number)
	saved.following = numbers
	if current == source:
		publish_button.text = "查看分析进度"
	_save()
	refresh()


func _chat_action(action: String) -> void:
	if not await _fresh_access():
		return
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
	var error: String = chat.open_daqian_chat(binding.get("url", current), int(binding.get("number",0)),str(binding.get("request","")),message,action=="preview")
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
	if not await _fresh_access():
		return
	if debug_sessions.has(current):
		_debug_command("answer",id,answer)
		return
	if not editor.draft.nodes.has(id):
		return
	var target := current
	var response: Dictionary = await _graph_command(target,"answer",{"revision":editor.revision,"node":id,"value":answer})
	if current != target:
		return
	if not response.get("ok",false):
		notice.text = str(response.get("error","未收到答复回执，草稿已保留"))
		return
	editor.context = response.context
	for item in board.get("issues",[]):
		if item.url==current:
			item.pending_count = response.context.questions.size()-response.context.answers.size()
			item.decision = item.pending_count>0
	_draw_board()
	editor.answers.erase(id)
	editor.draw_graph()
	_save()
	notice.text = "已按当前协作者身份记录答复 · " + id


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

func _select_debug(target: String) -> void:
	var session: Dictionary = debug_sessions.get(target,{})
	debug_issue = target if not session.is_empty() else ""
	debug_states = session.get("states",{})
	debug_history = session.get("history",[])


func _start_debug() -> void:
	var target := current
	if not await _fresh_access() or target != current:
		return
	if debug_sessions.has(target):
		notice.text = "当前工单已在调试中"
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
	var plan: Dictionary = editor.draft.duplicate(true)
	for id in plan.nodes:
		if plan.nodes[id].kind == "task":
			plan.nodes[id].model = editor.debug_models.get(id,"")
		if editor.context.get("answers",{}).has(id):
			plan.nodes[id].value = editor.context.answers[id].value
			if plan.nodes[id].kind == "question":
				plan.nodes[id].kind = "text"
		elif editor.context.get("questions",{}).get(id,{}).get("kind","") == "image":
			plan.nodes[id].pending_image = true
	var debug_seed := EditorInterface.get_editor_paths().get_cache_dir().path_join("daqian-loopback-" + Crypto.new().generate_random_bytes(12).hex_encode() + ".json")
	var file := FileAccess.open(debug_seed,FileAccess.WRITE)
	if not file:
		notice.text = "无法暂存本次调试请求"
		return
	debug_serial += 1
	file.store_string(JSON.stringify({"action":"start","issue":target,"plan":plan,"python":python,"serial":debug_serial}))
	file.close()
	if debug_process.is_empty():
		debug_buffer = PackedByteArray()
		debug_process = OS.execute_with_pipe(node,[path,debug_seed],false)
		if debug_process.is_empty():
			DirAccess.remove_absolute(debug_seed)
			notice.text = "无法启动 Node 调试宿主，请核对可执行路径"
			return
	else:
		var pipe: FileAccess = debug_process.stdio
		pipe.store_line(JSON.stringify({"action":"start_file","file":debug_seed,"serial":debug_serial}))
		pipe.flush()
	debug_sessions[target] = {"states":{},"history":[],"seed":debug_seed,"instance":debug_seed.get_file().get_basename()}
	_select_debug(target)
	editor.debug_active = true
	editor.draw_graph()
	debug_timer.start()
	notice.text = "调试运行 · 仅使用本机协议夹具"


func _debug_command(action: String,id: String,value: String) -> void:
	var target := current
	if action == "retry" and (not await _fresh_access() or target != current):
		return
	if debug_process.is_empty() or not debug_sessions.has(current):
		return
	var pipe: FileAccess = debug_process.stdio
	debug_timer.start()
	debug_serial += 1
	pipe.store_line(JSON.stringify({"action":action,"issue":current,"id":id,"model":value,"value":value,"serial":debug_serial}))
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
			var target: String = event.get("issue","")
			var session: Dictionary = debug_sessions.get(target,{})
			if not session.is_empty():
				session.states[event.id] = event
				session.history.append(event)
				if not saved.has("debug_receipts"):
					saved.debug_receipts = {}
				if not saved.debug_receipts.has(target):
					saved.debug_receipts[target] = []
				var receipt: Dictionary = event.duplicate()
				receipt.instance = session.instance
				saved.debug_receipts[target].append(receipt)
				_queue_save()
				if current == target:
					editor.set_debug_state(event)
		elif event is Dictionary and event.has("error"):
			notice.text = event.error
		elif event is Dictionary and event.get("idle",false) and int(event.get("serial",-1)) == debug_serial:
			debug_timer.stop()
			notice.text = "本轮调试已就绪或结束 · 可答复、重跑或结束调试"
		newline = debug_buffer.find(10)
	if not OS.is_process_running(debug_process.pid):
		_stop_debug(true,true)


func _stop_debug(redraw := true, all_issues := false) -> void:
	if debug_process.is_empty():
		return
	var targets: Array = debug_sessions.keys() if all_issues else [current]
	for target in targets:
		if not debug_sessions.has(target):
			continue
		var seed: String = debug_sessions[target].seed
		if not seed.is_empty() and FileAccess.file_exists(seed):
			DirAccess.remove_absolute(seed)
		debug_sessions.erase(target)
		if not all_issues and not debug_sessions.is_empty():
			debug_serial += 1
			var pipe: FileAccess = debug_process.stdio
			pipe.store_line(JSON.stringify({"action":"stop_issue","issue":target,"serial":debug_serial}))
			pipe.flush()
			debug_timer.start()
	if debug_sessions.is_empty():
		debug_process.clear()
		if is_instance_valid(debug_timer):
			debug_timer.stop()
	_select_debug(current)
	if is_instance_valid(editor):
		editor.debug_active = debug_sessions.has(current)
		editor.debug_states = debug_states.duplicate(true)
		if redraw and editor.is_inside_tree():
			editor.draw_graph()

func _show_debug_history() -> void:
	if actor.is_empty():
		return
	var lines := PackedStringArray()
	for event in saved.get("debug_receipts",{}).get(current,[]):
		var when_text := Time.get_datetime_string_from_unix_time(int(float(event.get("at",0))/1000.0),true)
		var node: Dictionary = editor.draft.nodes.get(event.id,{})
		var row := "%s UTC  %s  ·  %s" % [when_text,node.get("title",event.id),event.state]
		if event.has("run"):
			row += "  ·  #%s" % event.run
		if event.has("model"):
			row += "  ·  " + str(event.model)
		if event.has("worker"):
			row += "  ·  PID " + str(event.worker)
		if event.has("result") or event.has("reason"):
			row += "\n" + str(event.get("result",event.get("reason","")))
		lines.append(row)
	history_view.text = "\n".join(lines) if not lines.is_empty() else "当前工单尚无调试记录"
	history_dialog.popup_centered()
