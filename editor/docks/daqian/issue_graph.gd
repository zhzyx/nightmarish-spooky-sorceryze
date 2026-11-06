@tool
extends VBoxContainer

signal answer_requested(node_id: String, answer: String)
signal debug_command(action: String, id: String, value: String)
signal configure_model
signal draft_changed
signal applied(issue_id: String, revision: String)

const LABELS := {"text":"文本", "image":"图片", "question":"待用户答复", "task":"Agent 任务", "join":"结果汇总"}
const DATA := Color("#64c6e8")
const AFTER := Color("#eecb86")

var workflow := {}
var debug_active := false
var debug_states := {}
var debug_models := {}
var rules: Script
var issue_id := ""
var revision := ""
var baseline := {"nodes": {}, "edges": []}
var draft := {"nodes": {}, "edges": []}
var context := {}
var answers := {}
var positions := {}
var layout_columns: Array = []
var layout_pending := false
var host_apply: Callable
var canvas: GraphEdit
var notice: Label
var add_menu: MenuButton
var apply_button: Button
var picker: FileDialog
var pending_image := ""
var clipboard_image: Callable = DisplayServer.clipboard_get_image
var menu_at := Vector2(80, 100)
var host_read: Callable
var generation := 0
var applying := false


class IssueCanvas extends GraphEdit:
	var controller
	func _is_node_hover_valid(a: StringName, ap: int, b: StringName, bp: int) -> bool:
		return controller.preview_edge(a, ap, b, bp) == ""


func _ready() -> void:
	var toolbar := HBoxContainer.new()
	add_child(toolbar)
	add_menu = MenuButton.new()
	add_menu.text = "添加节点"
	toolbar.add_child(add_menu)
	for kind in LABELS:
		add_menu.get_popup().add_item(LABELS[kind])
	add_menu.get_popup().id_pressed.connect(func(i): add_node(LABELS.keys()[i], menu_at))
	apply_button = Button.new()
	apply_button.text = "应用更改"
	apply_button.pressed.connect(apply_draft)
	toolbar.add_child(apply_button)
	var arrange := Button.new()
	arrange.text = "自动排布"
	arrange.pressed.connect(func():
		positions.clear()
		draw_graph()
		draft_changed.emit())
	toolbar.add_child(arrange)
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	toolbar.add_child(notice)
	canvas = IssueCanvas.new()
	canvas.controller = self
	canvas.name = "IssueCanvas"
	canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas.right_disconnects = true
	# Let our validator explain mismatches during hover, before GraphEdit accepts a drop.
	canvas.add_valid_connection_type(0,1)
	canvas.add_valid_connection_type(1,0)
	canvas.connection_drag_started.connect(_mark_targets)
	canvas.connection_drag_ended.connect(_reset_ports)
	canvas.zoom_min = 0.16
	canvas.zoom_max = 3.0
	canvas.connection_request.connect(connect_ports)
	canvas.disconnection_request.connect(disconnect_ports)
	canvas.popup_request.connect(func(_point):
		menu_at = (canvas.get_local_mouse_position() + canvas.scroll_offset) / canvas.zoom
		add_menu.show_popup())
	canvas.connection_drag_ended.connect(func(): canvas.queue_redraw())
	add_child(canvas)
	picker = FileDialog.new()
	picker.access = FileDialog.ACCESS_FILESYSTEM
	picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	picker.filters = PackedStringArray(["*.png,*.jpg,*.jpeg,*.webp ; 图片"])
	picker.file_selected.connect(func(path):
		var target := pending_image
		pending_image = ""
		set_image(target,Image.load_from_file(path)))
	picker.canceled.connect(func(): pending_image = "")
	add_child(picker)
	draw_graph()


## Host issues a fresh projection and a compare-and-apply port. Draft is never a status source.
func bind_issue(id: String, snapshot: Dictionary, apply_port: Callable, read_port := Callable()) -> void:
	generation += 1
	applying = false
	issue_id = id
	pending_image = ""
	revision = snapshot.revision
	baseline = snapshot.plan.duplicate(true)
	draft = baseline.duplicate(true)
	context = snapshot.context.duplicate(true)
	host_apply = apply_port
	host_read = read_port
	positions = {}
	answers = {}
	debug_models = {}
	if is_node_ready():
		draw_graph()


func add_node(kind: String, at: Vector2) -> String:
	if not LABELS.has(kind):
		return ""
	var id := "n_" + Crypto.new().generate_random_bytes(12).hex_encode()
	draft.nodes[id] = {"kind":kind, "title":LABELS[kind], "value":""}
	positions[id] = at
	menu_at = at + Vector2(42, 42)
	_render_node(id, draft.nodes[id])
	draft_changed.emit()
	return id


func _label(value: String) -> Label:
	var label := Label.new()
	label.text = value
	return label


func _render_node(id: String, item: Dictionary) -> void:
	var view := GraphNode.new()
	view.name = id
	view.title = item.title
	view.tooltip_text = str(context.get("sources", {}).get(id, ""))
	var request: Dictionary = context.get("questions",{}).get(id,{})
	var recorded: Dictionary = context.get("answers",{}).get(id,{})
	var tint: Color = {"text":Color("#375e72"),"image":Color("#655581"),"task":Color("#344f79"),"question":Color("#8a652b"),"join":Color("#37645e")}.get(item.kind,Color("#46515e"))
	if not request.is_empty() and recorded.is_empty():
		tint = Color("#8a652b")
	_tint_header(view, tint)
	view.resizable = false
	view.position_offset = positions.get(id, menu_at)
	view.dragged.connect(func(_from,to):
		positions[id] = to
		_queue_layout()
		draft_changed.emit())
	var locked: bool = id in context.get("protected_nodes", []) or context.get("states", {}).get(id, "") in rules.ACTIVE
	var accepts: bool = item.kind in ["task","join"]
	var data_row := _label("输入数据   ◉   输出数据" if accepts else "输出数据   ◉")
	view.add_child(data_row)
	view.set_slot(0, accepts, 0, DATA, true, 0, DATA)
	var order_row := _label("前置步骤   ▸   后续步骤")
	view.add_child(order_row)
	var arrow := get_theme_icon("ArrowRight", "EditorIcons")
	view.set_slot(1, true, 1, AFTER, true, 1, AFTER, arrow, arrow)
	if item.kind in ["task","text","question"]:
		var input := TextEdit.new()
		input.custom_minimum_size = Vector2(215, 78)
		input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		input.placeholder_text = "任务说明" if item.kind == "task" else "输入文字"
		input.editable = not locked
		input.text = item.get("value","")
		input.text_changed.connect(func():
			draft.nodes[id].value = input.text
			draft_changed.emit())
		view.add_child(input)
	if item.kind == "question" and (debug_active or issue_id.begins_with("https://")):
		if not recorded.is_empty() and not debug_active:
			view.add_child(_label("已答复 · " + str(recorded.actor)))
		else:
			var options: Array = request.get("options",[])
			if not options.is_empty():
				var choose := OptionButton.new()
				choose.add_item("请选择")
				for option in options:
					choose.add_item(option)
					if answers.get(id,"")==option:
						choose.select(choose.item_count-1)
				choose.item_selected.connect(func(index):
					answers[id] = choose.get_item_text(index) if index else ""
					draft_changed.emit())
				view.add_child(choose)
			else:
				var answer := TextEdit.new()
				answer.placeholder_text = "你的答复"
				answer.text = answers.get(id,"")
				answer.text_changed.connect(func():
					answers[id] = answer.text
					draft_changed.emit())
				answer.custom_minimum_size = Vector2(215,60)
				view.add_child(answer)
			var send := Button.new()
			send.text = "提交调试答复" if debug_active else "提交答复"
			send.pressed.connect(func():
				var value: String = answers.get(id,"")
				if not value.strip_edges().is_empty():
					answer_requested.emit(id,value))
			view.add_child(send)
	if item.kind == "task":
		var models := OptionButton.new()
		models.add_item("司南自动分配")
		models.set_item_metadata(0,"")
		for model in context.get("models", {}):
			models.add_item(context.get("model_names",{}).get(model,model))
			models.set_item_metadata(models.item_count - 1, model)
			if item.get("model","") == model:
				models.select(models.item_count - 1)
		for model in context.get("model_names",{}):
			if not context.get("models",{}).has(model):
				models.add_item(str(context.model_names[model]) + " · 待评测")
				models.set_item_disabled(models.item_count-1,true)
		models.disabled = locked
		models.item_selected.connect(func(index):
			draft.nodes[id].model = models.get_item_metadata(index)
			draft_changed.emit())
		view.add_child(models)
		var configure := Button.new()
		configure.text = "添加供应商 API"
		configure.pressed.connect(func(): configure_model.emit())
		view.add_child(configure)
		if not locked:
			var attach := Button.new()
			attach.text = "补充图片输入"
			attach.pressed.connect(func(): add_image_for_task(id))
			view.add_child(attach)
		var choose := OptionButton.new()
		choose.add_item("调试 · 自动分配")
		for model in ["调试 · Claude","调试 · Gemini","调试 · GPT","调试 · DeepSeek"]:
			choose.add_item(model)
			if model == debug_models.get(id,""):
				choose.select(choose.item_count-1)
		choose.item_selected.connect(func(index): debug_models[id] = choose.get_item_text(index) if index else "")
		view.add_child(choose)
		if debug_active:
			var stop := Button.new()
			stop.text = "停止该分支"
			stop.pressed.connect(func(): debug_command.emit("cancel",id,""))
			view.add_child(stop)
			var retry := Button.new()
			retry.text = "用所选调试模型重跑"
			retry.pressed.connect(func(): debug_command.emit("retry",id,debug_models.get(id,"")))
			view.add_child(retry)
	if item.kind == "image":
		var preview := TextureRect.new()
		preview.name = "Preview"
		preview.custom_minimum_size = Vector2(180, 105)
		preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		view.add_child(preview)
		var encoded: String = recorded.get("value",answers.get(id,item.get("value",""))) if not request.is_empty() else item.get("value","")
		if not encoded.is_empty():
			var img := Image.new()
			if img.load_png_from_buffer(Marshalls.base64_to_raw(encoded)) == OK:
				preview.texture = ImageTexture.create_from_image(img)
		for title in ["选择图片","粘贴截图"]:
			var button := Button.new()
			button.text = title
			button.disabled = locked and (request.is_empty() or not recorded.is_empty())
			if title == "选择图片":
				button.pressed.connect(func():
					pending_image = id
					picker.popup_centered_ratio(0.65))
			else:
				button.pressed.connect(func(): set_image(id,clipboard_image.call()))
			view.add_child(button)
		if request.get("kind") == "image":
			view.add_child(_label(str(request.prompt).left(36)))
			if recorded.is_empty():
				var submit := Button.new()
				submit.text = "提交图片"
				submit.pressed.connect(func():
					if not str(answers.get(id,"")).is_empty():
						answer_requested.emit(id,answers[id]))
				view.add_child(submit)
		else:
			var caption := LineEdit.new()
			caption.placeholder_text = "图片说明（可选）"
			caption.editable = not locked
			caption.text = item.get("caption","")
			caption.text_changed.connect(func(value):
				draft.nodes[id].caption = value
				draft_changed.emit())
			view.add_child(caption)
	if item.kind == "join" and not str(item.get("value", "")).is_empty():
		var criterion := _label(item.value)
		criterion.custom_minimum_size.x = 210
		criterion.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		view.add_child(criterion)
	if context.get("states", {}).has(id):
		view.add_child(_label(context.states[id]))
	if debug_active:
		var state_label := _label("")
		state_label.name = "DebugState"
		view.add_child(state_label)
	canvas.add_child(view)
	if debug_states.has(id):
		set_debug_state(debug_states[id])


func add_image_for_task(id: String) -> String:
	if not draft.nodes.has(id) or draft.nodes[id].kind != "task" or context.get("states",{}).get(id,"") in rules.ACTIVE:
		return ""
	var task_view := canvas.get_node(NodePath(id)) as GraphNode
	var image_id := add_node("image",task_view.position_offset - Vector2(320,0))
	var edge := {"from":image_id,"to":id,"kind":"data"}
	var error: String = rules.edge_error(draft,edge,context)
	if error:
		notice.text = error
		return image_id
	draft.edges.append(edge)
	_draw_edge(edge)
	pending_image = image_id
	draft_changed.emit()
	return image_id


func set_image(id: String, image: Image) -> void:
	if not draft.nodes.has(id) or image == null or image.is_empty():
		notice.text = "没有可读图片"
		return
	var longest := maxi(image.get_width(), image.get_height())
	if longest > 1600:
		image.resize(maxi(1, image.get_width()*1600/longest), maxi(1, image.get_height()*1600/longest), Image.INTERPOLATE_LANCZOS)
	var bytes := image.save_png_to_buffer()
	if bytes.size() > 8 * 1024 * 1024:
		notice.text = "图片超过 8 MiB，请缩小后重试"
		return
	if context.get("questions",{}).get(id,{}).get("kind","") == "image":
		if context.get("answers",{}).has(id):
			return
		answers[id] = Marshalls.raw_to_base64(bytes)
	else:
		draft.nodes[id].value = Marshalls.raw_to_base64(bytes)
	canvas.get_node(NodePath(id + "/Preview")).texture = ImageTexture.create_from_image(image)
	draft_changed.emit()


# These cards describe the framework's work. Keep them out of editable and executable plans.
func _stage(plan: Dictionary, id: String, title: String, value: String, upstream: String) -> void:
	plan.nodes[id] = {"kind":"stage", "title":title, "value":value}
	if not upstream.is_empty():
		_stage_edge(plan, upstream, id)


func _stage_edge(plan: Dictionary, source: String, target: String) -> void:
	var link := {"from":source, "to":target, "kind":"after"}
	if link not in plan.edges:
		plan.edges.append(link)


func _display_plan() -> Dictionary:
	if workflow.is_empty() or not draft.nodes.has("requirement"):
		return draft
	var plan := {"nodes":draft.nodes.duplicate(), "edges":draft.edges.duplicate()}
	var phase: String = workflow.phase
	var labels := {"draft":"等待确认发送", "submitted":"已发送，等待分析回执", "analyzing":"正在分析",
		"questions":"等待答复", "ready":"分析完成，需求已就绪", "error":"处理受阻，请查看关联对话",
		"cancelled":"已停止", "waiting_environment":"等待本地环境配置", "bound":"已关联工单",
		"blocked":"关联工单受阻", "closed":"关联工单已关闭"}
	var intake := "wf-analysis" if workflow.get("analyzed", false) else "wf-workorder"
	if intake == "wf-analysis":
		_stage(plan, intake, "偃师 · 需求分析", labels.get(phase, "等待分析回执"), "requirement")
	else:
		_stage(plan, intake, "工单登记", "等待确认创建" if phase == "draft" else "已关联工单", "requirement")
	if workflow.get("direct", false) and phase != "draft":
		var decision: Dictionary = workflow.get("routing", {})
		_stage(plan, "wf-routing", "司南 · 需求判断", decision.get("reason", "等待框架判断回执"), intake)
		intake = "wf-routing"
		if decision.get("route") == "yanshi":
			_stage(plan, "wf-analysis", "偃师 · 需求分析", "等待补充需求" if not decision.ready else "需求已整理", intake)
			intake = "wf-analysis"
	var item: Dictionary = workflow.item
	var design: Dictionary = workflow.design
	var prepare: bool = phase == "ready" or (phase == "bound" and item.get("status") in ["planned", "in-progress", "in-review"])
	if item.get("status") == "blocked":
		_stage(plan, "wf-blocked", "夸父 · 阻塞处置", "工单已标记阻塞，等待处置回执", intake)
	if prepare:
		_stage(plan, "wf-prepare", "司南 · 运行准备", "核对依赖、授权与可用执行者", intake)
		for dep in item.get("dependencies", []):
			var id := "wf-dep-" + str(dep).sha256_text().left(20)
			_stage(plan, id, "前置工单", str(dep), "")
			_stage_edge(plan, id, "wf-prepare")
	var tasks := []
	var criteria := []
	var titles := {"scope":"预计任务", "acceptance":"验收条件", "questions":"待确认"}
	var source_nodes: Dictionary = item.get("plan", {}).get("nodes", {})
	for field in titles:
		var entries: Dictionary = {}
		for id in source_nodes:
			var node: Dictionary = source_nodes[id]
			if node.title == titles[field] or (field == "questions" and item.get("questions", {}).has(id)):
				var value: String = str(item.get("questions", {}).get(id, {}).get("prompt", node.value))
				entries[value] = id
		var values: Array = design.get(field, entries.keys())
		for clause in values:
			if not clause is String or clause.is_empty():
				continue
			var key: String = entries.get(clause, "")
			if key.is_empty() or not draft.nodes.has(key):
				key = "wf-" + str(field) + "-" + clause.sha256_text().left(20)
				_stage(plan, key, titles[field], clause, "")
			if field == "scope":
				tasks.append(key)
				_stage_edge(plan, "wf-prepare" if prepare else intake, key)
			elif field == "questions":
				_stage_edge(plan, intake, key)
			else:
				criteria.append(key)
	if not criteria.is_empty():
		_stage(plan, "wf-verify", "结果验证", "按验收条件核对执行产物", "")
		for task in tasks:
			_stage_edge(plan, task, "wf-verify")
		if tasks.is_empty():
			_stage_edge(plan, "wf-prepare" if prepare else intake, "wf-verify")
		for criterion in criteria:
			_stage_edge(plan, "wf-verify", criterion)
	if prepare and item.get("development", false):
		_stage(plan, "wf-integrate", "合契 · 候选整合", "待核对变更集与候选版本", "")
		if tasks.is_empty():
			_stage_edge(plan, "wf-prepare", "wf-integrate")
		for task in tasks:
			_stage_edge(plan, task, "wf-integrate")
		if plan.nodes.has("wf-verify"):
			_stage_edge(plan, "wf-integrate", "wf-verify")
		_stage(plan, "wf-deliver", "阎罗 · 主线交付", "待门禁、主线及工单验收回读", "wf-integrate")
		for criterion in criteria:
			_stage_edge(plan, criterion, "wf-deliver")
	return plan


func _tint_header(view: GraphNode, tint: Color) -> void:
	for style in ["titlebar","titlebar_selected"]:
		var original := get_theme_stylebox(style,"GraphNode")
		if original is StyleBoxFlat:
			var colored := original.duplicate() as StyleBoxFlat
			colored.bg_color = tint.lightened(0.10) if style.ends_with("selected") else tint
			view.add_theme_stylebox_override(style,colored)


func _render_stage(id: String, item: Dictionary) -> void:
	var view := GraphNode.new()
	view.name = id
	view.title = item.title
	view.draggable = false
	view.tooltip_text = item.value
	_tint_header(view, Color("#3d5964"))
	var description := _label(item.value)
	description.custom_minimum_size.x = 210
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	view.add_child(description)
	view.add_child(Control.new())
	view.set_slot(0, true, 0, DATA, true, 0, DATA)
	view.set_slot(1, true, 1, AFTER, true, 1, AFTER)
	canvas.add_child(view)


func draw_graph() -> void:
	var plan := _display_plan()
	layout_columns.clear()
	var counts := {}
	var outgoing := {}
	var depth := {}
	for id in plan.nodes:
		counts[id] = 0
		outgoing[id] = []
		depth[id] = 0
	for edge in plan.edges:
		if counts.has(edge.to) and outgoing.has(edge.from):
			counts[edge.to] += 1
			outgoing[edge.from].append(edge.to)
	var ready := []
	for id in counts:
		if counts[id] == 0:
			ready.append(id)
	var cursor := 0
	while cursor < ready.size():
		var id = ready[cursor]
		cursor += 1
		var level: int = depth[id]
		for next in outgoing[id]:
			depth[next] = maxi(depth[next],level+1)
			counts[next] -= 1
			if counts[next] == 0:
				ready.append(next)
	canvas.clear_connections()
	for child in canvas.get_children():
		if child is GraphNode:
			canvas.remove_child(child)
			child.queue_free()
	for id in plan.nodes:
		if draft.nodes.has(id):
			_render_node(id, plan.nodes[id])
		else:
			_render_stage(id, plan.nodes[id])
	# Personal edits can order existing tasks differently from the displayed plan.
	for id in plan.nodes:
		if counts[id] > 0:
			ready.append(id)
	var last := 0
	for id in ready:
		var level: int = depth[id]
		if plan.nodes[id].kind == "join" and outgoing[id].is_empty() and level == 0:
			continue
		last = maxi(last,level)
	for id in ready:
		if plan.nodes[id].kind == "join" and outgoing[id].is_empty() and depth[id] == 0:
			depth[id] = last + 1
		var level: int = depth[id]
		while layout_columns.size() <= level:
			layout_columns.append([])
		var view := canvas.get_node(NodePath(str(id))) as GraphNode
		layout_columns[level].append(view)
		view.resized.connect(_queue_layout)
	_layout_cards()
	for edge in plan.edges:
		_draw_edge(edge, plan.nodes)


# Wrapping and theme changes can resize a card after GraphNode has sorted its children.
func _queue_layout() -> void:
	if not layout_pending:
		layout_pending = true
		_layout_cards.call_deferred()


# Only manual positions obstruct the automatic lanes. Move down to the first clear interval.
static func clear_pinned_space(rect: Rect2, obstacles: Array[Rect2], gap: float) -> Vector2:
	for obstacle in obstacles:
		if rect.intersects(obstacle.grow(gap)):
			rect.position.y = obstacle.end.y + gap
	return rect.position


func _layout_cards() -> void:
	layout_pending = false
	if layout_columns.is_empty():
		return
	var scale_factor := canvas.get_theme_default_base_scale()
	var gap := Vector2(88, 36) * scale_factor
	var obstacles: Array[Rect2] = []
	for id in positions:
		var card := canvas.get_node_or_null(NodePath(str(id))) as GraphNode
		if card:
			obstacles.append(Rect2(positions[id], card.size.max(card.get_combined_minimum_size())))
	obstacles.sort_custom(func(a: Rect2, b: Rect2): return a.position.y < b.position.y)
	var x := 48.0 * scale_factor
	var center_y := 64.0 * scale_factor
	for level in layout_columns.size():
		var column: Array = layout_columns[level]
		var height := -gap.y
		var width := 0.0
		for card: GraphNode in column:
			var extent := card.size.max(card.get_combined_minimum_size())
			width = maxf(width, extent.x)
			height += extent.y + gap.y
		if level == 0:
			center_y += height / 2.0
		var y := center_y - height / 2.0
		for card: GraphNode in column:
			var extent := card.size.max(card.get_combined_minimum_size())
			if not positions.has(String(card.name)):
				card.position_offset = clear_pinned_space(Rect2(Vector2(x, y), extent), obstacles, gap.y)
				y = card.position_offset.y
			y += extent.y + gap.y
		x += width + gap.x


func _draw_edge(edge: Dictionary, nodes := {}) -> void:
	if nodes.is_empty():
		nodes = draft.nodes
	var output := 0 if edge.kind == "data" else 1
	var input := 0
	if edge.kind == "after" and nodes[edge.to].kind in ["task","join","stage"]:
		input = 1
	canvas.connect_node(edge.from, output, edge.to, input)


func _edge(a: StringName, ap: int, b: StringName, bp: int) -> Dictionary:
	var source := canvas.get_node_or_null(NodePath(String(a))) as GraphNode
	var target := canvas.get_node_or_null(NodePath(String(b))) as GraphNode
	if not source or not target or ap < 0 or bp < 0 or ap >= source.get_output_port_count() or bp >= target.get_input_port_count():
		return {}
	var type := source.get_output_port_type(ap)
	if type != target.get_input_port_type(bp):
		return {}
	return {"from":String(a), "to":String(b), "kind":"data" if type == 0 else "after"}


func preview_edge(a: StringName, ap: int, b: StringName, bp: int) -> String:
	var edge := _edge(a,ap,b,bp)
	var error := "端口方向或类型不匹配"
	if not edge.is_empty():
		error = rules.edge_error(draft, edge, context)
		if error == "" and context.get("states", {}).get(String(b), "") in rules.ACTIVE:
			error = "目标节点已启动，输入已锁定"
	notice.text = error if error else "可以连接"
	return error


func connect_ports(a: StringName, ap: int, b: StringName, bp: int) -> void:
	if preview_edge(a,ap,b,bp) != "":
		return
	var edge := _edge(a,ap,b,bp)
	draft.edges.append(edge)
	_draw_edge(edge)
	notice.text = "连线已加入草稿"
	draft_changed.emit()


func disconnect_ports(a: StringName, ap: int, b: StringName, bp: int) -> void:
	var edge := _edge(a,ap,b,bp)
	if edge in context.get("protected_edges", []) or context.get("states", {}).get(String(b), "") in rules.ACTIVE:
		notice.text = "该连线由框架或已开始的执行保护"
		return
	if edge in draft.edges:
		draft.edges.erase(edge)
		canvas.disconnect_node(a,ap,b,bp)
		draft_changed.emit()


func apply_draft() -> void:
	if applying:
		return
	var error: String = rules.changes_error(baseline,draft,context)
	if error != "":
		notice.text = error
		return
	if not host_apply.is_valid() or not host_read.is_valid():
		notice.text = "草稿已保留，应用需要已绑定的共工工单宿主"
		return
	var original_generation := generation
	var candidate := draft.duplicate(true)
	applying = true
	notice.text = "正在核对最新工单状态…"
	var fresh: Dictionary = await host_read.call(issue_id)
	if original_generation != generation:
		return
	applying = false
	if not fresh.get("can_edit", false):
		notice.text = str(fresh.get("error","共工宿主未确认本次工单编辑权限"))
		return
	var conflicts: String = rules.changes_error(baseline, candidate, fresh.context)
	if conflicts != "":
		notice.text = conflicts
		return
	if fresh.revision != revision:
		notice.text = "工单流程版本已变更，请核对更新；个人草稿已保留"
		return
	# Source compares both the plan revision and the execution snapshot inside its write transaction.
	applying = true
	var result: Dictionary = await host_apply.call(issue_id, revision, fresh.execution_revision, candidate)
	if original_generation != generation:
		return
	applying = false
	if not result.get("ok",false):
		notice.text = result.get("error","应用失败，草稿已保留")
		return
	revision = result.revision
	baseline = candidate
	context = result.context
	notice.text = "已应用" if baseline == draft else "已应用提交版本；后续编辑仍在草稿中"
	applied.emit(issue_id, revision)

func set_debug_state(event: Dictionary) -> void:
	debug_states[event.id] = event
	var view := canvas.get_node_or_null(NodePath(str(event.id) + "/DebugState")) as Label
	if view:
		var labels := {"reserved":"已预留","running":"运行中","completed":"已完成","failed":"失败","waiting":"等待输入或证据","cancelled":"已取消","stopping":"正在停止"}
		view.text = str(labels.get(event.state,event.state)) + (" · " + str(event.model) if event.has("model") else " · 调试")
		view.tooltip_text = str(event.get("result",event.get("reason","")))

func _mark_targets(start: StringName, port: int, output: bool) -> void:
	for child in canvas.get_children():
		if not child is GraphNode:
			continue
		var view := child as GraphNode
		var count := view.get_input_port_count() if output else view.get_output_port_count()
		for index in count:
			var edge := _edge(start,port,view.name,index) if output else _edge(view.name,index,start,port)
			var legal: bool = not edge.is_empty() and rules.edge_error(draft,edge,context)=="" and context.get("states",{}).get(edge.to,"") not in rules.ACTIVE
			var color := Color("#91e7b8") if legal else Color("#646771")
			if output:
				view.set_slot_color_left(view.get_input_port_slot(index),color)
			else:
				view.set_slot_color_right(view.get_output_port_slot(index),color)


func _reset_ports() -> void:
	for child in canvas.get_children():
		if child is GraphNode:
			child.set_slot_color_left(0,DATA)
			child.set_slot_color_right(0,DATA)
			child.set_slot_color_left(1,AFTER)
			child.set_slot_color_right(1,AFTER)
