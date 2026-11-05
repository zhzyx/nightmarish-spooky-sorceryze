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

var debug_active := false
var debug_states := {}
var debug_models := {}
var rules: Script
var issue_id := ""
var revision := ""
var baseline := {"nodes": {}, "edges": []}
var draft := {"nodes": {}, "edges": []}
var context := {}
var positions := {}
var host_apply: Callable
var canvas: GraphEdit
var notice: Label
var add_menu: MenuButton
var apply_button: Button
var picker: FileDialog
var pending_image := ""
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
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	toolbar.add_child(notice)
	canvas = IssueCanvas.new()
	canvas.controller = self
	canvas.name = "IssueCanvas"
	canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas.right_disconnects = true
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
	picker.file_selected.connect(func(path): set_image(pending_image, Image.load_from_file(path)))
	add_child(picker)
	draw_graph()


## Host issues a fresh projection and a compare-and-apply port. Draft is never a status source.
func bind_issue(id: String, snapshot: Dictionary, apply_port: Callable, read_port := Callable()) -> void:
	generation += 1
	applying = false
	issue_id = id
	revision = snapshot.revision
	baseline = snapshot.plan.duplicate(true)
	draft = baseline.duplicate(true)
	context = snapshot.context.duplicate(true)
	host_apply = apply_port
	host_read = read_port
	positions = {}
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
	view.resizable = false
	view.position_offset = positions.get(id, Vector2(50 + (canvas.get_child_count() % 4) * 300, 120))
	view.position_offset_changed.connect(func(): positions[id] = view.position_offset)
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
		var answer := TextEdit.new()
		answer.placeholder_text = "你的答复"
		answer.custom_minimum_size = Vector2(215,60)
		view.add_child(answer)
		var send := Button.new()
		send.text = "提交答复"
		send.pressed.connect(func():
			if not answer.text.strip_edges().is_empty():
				answer_requested.emit(id,answer.text.strip_edges()))
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
		var encoded: String = item.get("value","")
		if not encoded.is_empty():
			var img := Image.new()
			if img.load_png_from_buffer(Marshalls.base64_to_raw(encoded)) == OK:
				preview.texture = ImageTexture.create_from_image(img)
		for title in ["选择图片","粘贴截图"]:
			var button := Button.new()
			button.text = title
			button.disabled = locked
			if title == "选择图片":
				button.pressed.connect(func():
					pending_image = id
					picker.popup_centered_ratio(0.65))
			else:
				button.pressed.connect(func(): set_image(id, DisplayServer.clipboard_get_image()))
			view.add_child(button)
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
	draft.nodes[id].value = Marshalls.raw_to_base64(bytes)
	canvas.get_node(NodePath(id + "/Preview")).texture = ImageTexture.create_from_image(image)
	draft_changed.emit()


func draw_graph() -> void:
	canvas.clear_connections()
	for child in canvas.get_children():
		if child is GraphNode:
			canvas.remove_child(child)
			child.queue_free()
	for id in draft.nodes:
		_render_node(id, draft.nodes[id])
	for edge in draft.edges:
		_draw_edge(edge)


func _draw_edge(edge: Dictionary) -> void:
	var output := 0 if edge.kind == "data" else 1
	var input := 0
	if edge.kind == "after" and draft.nodes[edge.to].kind in ["task","join"]:
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
		view.text = "调试 · " + str(event.state) + " " + str(event.get("model",""))
		view.tooltip_text = str(event.get("result",event.get("reason","")))
