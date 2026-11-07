@tool
extends VBoxContainer

signal graph_rebuilding
signal stage_controls_requested(id: String, card: GraphNode)
signal workflow_reply_requested
signal clarification_draft_changed(text: String)
signal clarification_submitted(text: String)
signal answer_requested(node_id: String, answer: String)
signal debug_command(action: String, id: String, value: String)
signal confirm_operation(token: String)
signal show_operation_details(token: String)
signal configure_model
signal draft_changed
signal applied(issue_id: String, revision: String)

const LABELS := {"text":"文本", "image":"图片", "question":"待用户答复", "task":"Agent 任务", "join":"结果汇总"}
const DATA := Color("#64c6e8")
const AFTER := Color("#eecb86")

var workflow := {}
var clarification_draft := ""
var debug_active := false
var debug_states := {}
var debug_models := {}
var rules: Script
var graph_layout: Script
var issue_id := ""
var revision := ""
var baseline := {"nodes": {}, "edges": []}
var draft := {"nodes": {}, "edges": []}
var context := {}
var answers := {}
var positions := {}
var card_sizes := {}
var layout_columns: Array = []
var layout_pending := false
var host_apply: Callable
var canvas: IssueCanvas
var running_nodes: Label
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
signal graph_projection_finished
var graph_projection_generation := 0
var graph_projection_pending := false
var graph_projection_suspended := false
const GRAPH_SLICE_US := 3000


# Keep the GraphEdit wire for hit testing, dragging, zoom and the minimap.
# Only its material changes. A shared static shader lets idle graphs stop repainting.
class FlowCanvas extends GraphEdit:
	const COLORS := {"pending": Color("#8290a5"), "running": Color("#45c9ff"),
		"done": Color("#69d5a3"), "waiting": Color("#efbf70"), "failed": Color("#f18e87"),
		"cancelled": Color("#ad9bb5"), "unknown": Color("#a5a6b3")}
	const LABELS := {"awaiting_answer":"待你答复", "open_question":"待确认", "awaiting_approval":"待你确认", "unknown":"执行结果待核实", "pending":"待制作", "running":"运行中", "done":"已完成", "planned":"待制作",
		"open":"待制作", "in-progress":"进行中", "in-review":"待验收", "completed":"已完成",
		"dispatched":"已派发", "reserved":"已预留", "waiting":"等待输入或证据", "answered":"已答复",
		"needs-decision":"待决策", "failed":"失败", "blocked":"已阻塞", "cancelled":"已取消",
		"closed":"已关闭", "stopping":"正在停止", "reconcile_required":"待核实"}
	const WIRE := """
shader_type canvas_item;
render_mode unshaded;
uniform vec4 ink : source_color;
void fragment() {
	float rim = abs(UV.y * 2.0 - 1.0);
	float coverage = 1.0 - smoothstep(0.52, 1.0, rim);
	vec3 hue = ink.rgb;
	FLOW
	COLOR = vec4(hue, ink.a * coverage);
}"""
	var materials := {}
	var lines := {}

	func _init() -> void:
		# GraphEdit scales its cards; rasterize their glyphs at the resulting viewport scale.
		oversampling_with_scale = CanvasItem.OVERSAMPLING_WITH_SCALE_ENABLED

	static func category(state: String) -> String:
		match state:
			"running", "in-progress": return "running"
			"done", "completed", "answered": return "done"
			"open_question", "awaiting_answer", "awaiting_approval", "reserved", "dispatched", "stopping", "waiting", "needs-decision", "in-review", "reconcile_required": return "waiting"
			"blocked", "failed": return "failed"
			"cancelled", "closed": return "cancelled"
			"planned", "pending", "open": return "pending"
		return "unknown"

	static func state_text(state: String) -> String:
		return LABELS.get(state, "待核实 · " + state)

	var badge_styles := {}

	func status_ink(state: String) -> Color:
		var color: Color = COLORS[category(state)]
		var surface := get_theme_color("base_color", "Editor")
		if surface.get_luminance() > 0.42:
			return color.darkened(0.58)
		return color.lerp(Color.WHITE, 0.16)

	func status_badge(state: String) -> StyleBoxFlat:
		var ink := status_ink(state)
		var radius := roundi(5 * get_theme_default_base_scale())
		var key := [ink, radius]
		if not badge_styles.has(key):
			var badge := StyleBoxFlat.new()
			badge.set_corner_radius_all(radius)
			badge.bg_color = Color(ink, 0.16)
			badge.content_margin_left = radius
			badge.content_margin_right = radius
			badge_styles[key] = badge
		return badge_styles[key]

	func mark_card(view: GraphNode, label: Label, state: String, suffix := "") -> void:
		var color := status_ink(state)
		view.set_meta("flow_state", state)
		label.text = state_text(state) + suffix
		label.add_theme_color_override("font_color", color)
		label.add_theme_stylebox_override("normal", status_badge(state))
		for style in ["titlebar", "titlebar_selected", "panel", "panel_selected"]:
			var base := get_theme_stylebox(style, "GraphNode") as StyleBoxFlat
			if base:
				var box := base.duplicate() as StyleBoxFlat
				var selected: bool = style.ends_with("_selected")
				var surface := get_theme_color("base_color", "Editor")
				box.bg_color = surface.lerp(color, 0.12 if style.begins_with("titlebar") else 0.045)
				box.border_color = get_theme_color("accent_color", "Editor") if selected else surface.lerp(color, 0.28)
				box.set_border_width_all(roundi((2 if selected else 1) * get_theme_default_base_scale()))
				if state == "awaiting_answer":
					box.border_color = color
					box.set_border_width_all(maxi(2, roundi(3 * get_theme_default_base_scale())))
				view.add_theme_stylebox_override(style, box)


	func connect_flow(source: StringName, output: int, target: StringName, input: int) -> void:
		var key := [source, output, target, input]
		if lines.has(key) or connect_node(source, output, target, input) != OK:
			return
		# This engine creates one native Line2D synchronously for each new connection.
		var line := get_node("_connection_layer").get_child(-1) as Line2D
		lines[key] = line
		_style_wire(key)

	func _style_wire(key: Array) -> void:
		var source := get_node(NodePath(key[0])) as GraphNode
		var target := get_node(NodePath(key[2])) as GraphNode
		var state := category(target.get_meta("flow_state", "pending"))
		var upstream := category(source.get_meta("flow_state", "pending"))
		if state == "running" and upstream != "done":
			state = "pending" if upstream == "running" else upstream
		if not materials.has(state):
			var shader := Shader.new()
			var flow := ""
			if state == "running":
				flow = """
				float wave = fract(UV.x * 3.0 - TIME * 0.85);
				float pulse = smoothstep(0.35, 0.91, wave) * (1.0 - smoothstep(0.91, 1.0, wave));
				hue = mix(ink.rgb * 0.65, vec3(1.0), pulse);"""
			elif state == "pending":
				flow = "coverage *= mix(0.26, 0.82, smoothstep(0.12, 0.22, fract(UV.x * 14.0)));"
			shader.code = WIRE.replace("FLOW", flow)
			var wire := ShaderMaterial.new()
			wire.shader = shader
			wire.set_shader_parameter("ink", COLORS[state])
			materials[state] = wire
		lines[key].material = materials[state]
		lines[key].visible = source.visible and target.visible

	func refresh_wires(id := &"") -> void:
		for key in lines:
			if id == &"" or key[0] == id or key[2] == id:
				_style_wire(key)

	func update_filtered_wires(changed_cards: Dictionary) -> void:
		for key in lines:
			if changed_cards.has(key[0]) or changed_cards.has(key[2]):
				var included: bool = get_node(NodePath(key[0])).visible and get_node(NodePath(key[2])).visible
				if lines[key].visible != included:
					lines[key].visible = included

	func clear_flow() -> void:
		lines.clear()
		clear_connections()

	func disconnect_flow(source: StringName, output: int, target: StringName, input: int) -> void:
		lines.erase([source, output, target, input])
		disconnect_node(source, output, target, input)


class SizeableCard extends GraphNode:
	signal geometry_edited
	var edge := Vector2i.ZERO
	var start_pointer := Vector2.ZERO
	var start_rect := Rect2()

	func _edges(at: Vector2) -> Vector2i:
		var margin := 5.0 * get_theme_default_base_scale()
		return Vector2i(int(at.x >= size.x - margin) - int(at.x <= margin), int(at.y >= size.y - margin) - int(at.y <= margin))

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				edge = _edges(event.position)
				if edge == Vector2i.ZERO:
					return
				start_pointer = get_global_transform() * event.position
				start_rect = Rect2(position_offset, size)
			elif edge != Vector2i.ZERO:
				edge = Vector2i.ZERO
			else:
				return
			accept_event()
		elif event is InputEventMouseMotion:
			var hit := _edges(event.position) if edge == Vector2i.ZERO else edge
			if hit.x and hit.y:
				mouse_default_cursor_shape = CURSOR_FDIAGSIZE if hit.x == hit.y else CURSOR_BDIAGSIZE
			elif hit.x:
				mouse_default_cursor_shape = CURSOR_HSIZE
			elif hit.y:
				mouse_default_cursor_shape = CURSOR_VSIZE
			else:
				mouse_default_cursor_shape = CURSOR_ARROW
			if edge != Vector2i.ZERO:
				var xform := get_global_transform()
				var delta := xform.affine_inverse().basis_xform(xform * event.position - start_pointer)
				size = (start_rect.size + Vector2(edge) * delta).max(get_combined_minimum_size())
				position_offset = start_rect.position + (start_rect.size - size) * Vector2(int(edge.x < 0), int(edge.y < 0))
				geometry_edited.emit()
				accept_event()


class IssueCanvas extends FlowCanvas:
	var controller
	func _is_node_hover_valid(a: StringName, ap: int, b: StringName, bp: int) -> bool:
		return controller.preview_edge(a, ap, b, bp) == ""


func _ready() -> void:
	visibility_changed.connect(func():
		if graph_projection_suspended and is_visible_in_tree():
			draw_graph(true))
	var toolbar := HFlowContainer.new()
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
	running_nodes = Label.new()
	running_nodes.name = "RunningNodes"
	running_nodes.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	running_nodes.add_theme_color_override("font_color", FlowCanvas.COLORS.running)
	add_child(running_nodes)
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
	canvas.zoom_max = 1.6
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
func bind_issue(id: String, snapshot: Dictionary, apply_port: Callable, read_port := Callable(), render_now := true) -> void:
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
	card_sizes = {}
	answers = {}
	debug_models = {}
	if is_node_ready() and render_now:
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
	var view := SizeableCard.new()
	view.name = id
	view.title = item.title
	var heading := view.get_titlebar_hbox().get_child(0) as Label
	heading.custom_minimum_size.x = 210
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	view.tooltip_text = str(context.get("sources", {}).get(id, ""))
	var request: Dictionary = context.get("questions",{}).get(id,{})
	var recorded: Dictionary = context.get("answers",{}).get(id,{})
	view.resizable = false
	view.position_offset = positions.get(id, menu_at)
	view.dragged.connect(func(_from,to):
		positions[id] = to
		_queue_layout()
		draft_changed.emit())
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
		input.size_flags_vertical = Control.SIZE_EXPAND_FILL
		input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		input.scroll_fit_content_height = true
		input.placeholder_text = "任务说明" if item.kind == "task" else "输入文字"
		input.name = "PlanContent"
		input.text = request.get("prompt", item.get("value","")) if item.kind == "question" else item.get("value","")
		input.text_changed.connect(func():
			draft.nodes[id].value = input.text
			draft_changed.emit())
		view.add_child(input)
	if item.kind == "question" and (debug_active or not request.is_empty()):
		if not recorded.is_empty() and not debug_active:
			var receipt := _label("已答复 · %s\n%s" % [recorded.actor, recorded.value])
			receipt.custom_minimum_size.x = 215
			receipt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			view.add_child(receipt)
		elif debug_active or context.get("can_answer", false):
			var send := Button.new()
			send.disabled = str(answers.get(id, "")).strip_edges().is_empty()
			var options: Array = request.get("options",[])
			if not options.is_empty():
				var choose := OptionButton.new()
				choose.name = "AnswerInput"
				send.disabled = answers.get(id, "") not in options
				choose.add_item("请选择")
				for option in options:
					choose.add_item(option)
					if answers.get(id,"")==option:
						choose.select(choose.item_count-1)
				choose.item_selected.connect(func(index):
					answers[id] = choose.get_item_text(index) if index else ""
					send.disabled = index == 0
					draft_changed.emit())
				view.add_child(choose)
			else:
				var answer := TextEdit.new()
				answer.name = "AnswerInput"
				answer.placeholder_text = "你的答复"
				answer.text = answers.get(id,"")
				answer.text_changed.connect(func():
					answers[id] = answer.text
					send.disabled = answer.text.strip_edges().is_empty()
					draft_changed.emit())
				answer.custom_minimum_size = Vector2(215,60)
				answer.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
				answer.scroll_fit_content_height = true
				view.add_child(answer)
			send.name = "SubmitReply"
			send.text = "提交调试答复" if debug_active else "提交答复"
			send.pressed.connect(func():
				var value: String = answers.get(id,"")
				if view.get_parent() == canvas and not value.strip_edges().is_empty() and (options.is_empty() or value in options):
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
		models.name = "PlanModel"
		models.item_selected.connect(func(index):
			draft.nodes[id].model = models.get_item_metadata(index)
			draft_changed.emit())
		view.add_child(models)
		var configure := Button.new()
		configure.text = "添加供应商 API"
		configure.pressed.connect(func(): configure_model.emit())
		view.add_child(configure)
		var attach := Button.new()
		attach.name = "Attach"
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
			button.name = "PickImage" if title == "选择图片" else "PasteImage"
			if title == "选择图片":
				button.pressed.connect(func():
					pending_image = id
					picker.popup_centered_ratio(0.65))
			else:
				button.pressed.connect(func(): set_image(id,clipboard_image.call()))
			view.add_child(button)
		if request.get("kind") == "image":
			var prompt := _label(request.prompt)
			prompt.custom_minimum_size.x = 215
			prompt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			view.add_child(prompt)
			if recorded.is_empty() and (debug_active or context.get("can_answer", false)):
				var submit := Button.new()
				submit.text = "提交图片"
				submit.pressed.connect(func():
					if not str(answers.get(id,"")).is_empty():
						answer_requested.emit(id,answers[id]))
				view.add_child(submit)
		else:
			var caption := LineEdit.new()
			caption.placeholder_text = "图片说明（可选）"
			caption.name = "Caption"
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
	_add_state_row(view)
	canvas.add_child(view)
	if card_sizes.has(id):
		view.size = card_sizes[id]
	view.geometry_edited.connect(func():
		card_sizes[id] = view.size
		positions[id] = view.position_offset
		_queue_layout()
		draft_changed.emit())
	_update_card(view)


func _add_state_row(view: GraphNode) -> void:
	var label := Label.new()
	label.name = "FlowState"
	view.add_child(label)


func _node_state(id: String) -> String:
	if id == "wf-clarification":
		return "awaiting_answer"
	if id.begins_with("wf-clarification-answer-"):
		return "answered"
	if id.begins_with("wf-clarification-question-"):
		var current_round: int = workflow.get("clarification_history", []).size()
		return "open_question" if id.begins_with("wf-clarification-question-%d-" % current_round) else "completed"
	if id == "wf-operation":
		return workflow.get("operation", {}).get("state", "pending")
	if debug_active:
		return debug_states.get(id, {}).get("state", "pending")
	if context.get("states", {}).has(id):
		return context.states[id]
	if context.get("answers", {}).has(id):
		return "answered"
	if context.get("questions", {}).has(id):
		return "waiting"
	var phase: String = workflow.get("phase", "draft")
	match id:
		"wf-worker": return workflow.get("progress", {}).get("state", "waiting")
		"requirement", "wf-workorder":
			return "completed" if phase != "draft" or issue_id.begins_with("https://") else "pending"
		"wf-routing":
			if workflow.get("routing_stage") == "yanshi": return "completed"
			if workflow.get("judging", false): return "running"
			if not workflow.get("routing", {}).is_empty(): return "completed"
		"wf-analysis":
			if phase == "analyzing" or workflow.get("routing_stage") == "yanshi": return "running"
			if phase in ["questions", "submitted", "waiting_environment"]: return "waiting"
			if phase == "error": return "failed"
			if phase == "cancelled": return "cancelled"
			if not workflow.get("clarification_history", []).is_empty(): return "completed"
			if workflow.get("analyzed", false) or workflow.get("routing", {}).get("ready", false): return "completed"
		"wf-blocked": return "blocked"
	return "pending"


func _update_card(view: GraphNode) -> void:
	var state := _node_state(view.name)
	var event: Dictionary = debug_states.get(String(view.name), {}) if debug_active else {}
	var suffix := " · 调试" if debug_active else ""
	if event.has("model"):
		suffix += " · " + str(event.model)
	var label: Label = view.get_node("FlowState")
	label.tooltip_text = str(event.get("result", event.get("reason", "")))
	canvas.mark_card(view, label, state, suffix)
	var id := String(view.name)
	var locked: bool = id in context.get("protected_nodes", []) or context.get("states", {}).get(id, "") in rules.ACTIVE
	for field in ["PlanContent", "Caption"]:
		if view.has_node(NodePath(field)):
			view.get_node(NodePath(field)).editable = not locked
	if view.has_node("PlanModel"):
		view.get_node("PlanModel").disabled = locked
		view.get_node("Attach").visible = not locked
	if view.has_node("PickImage"):
		var disabled: bool = locked and (not context.get("can_answer", false) or not context.get("questions", {}).has(id) or context.get("answers", {}).has(id))
		view.get_node("PickImage").disabled = disabled
		view.get_node("PasteImage").disabled = disabled


func _update_running_nodes() -> void:
	var names := PackedStringArray()
	for child in canvas.get_children():
		if child is GraphNode and FlowCanvas.category(child.get_meta("flow_state", "pending")) == "running":
			var item: Dictionary = draft.nodes.get(String(child.name), {})
			var title: String = item.get("value", "").get_slice("\n", 0).left(40) if item.get("kind") == "task" else ""
			names.append(title if not title.is_empty() else child.title)
	running_nodes.visible = not names.is_empty()
	running_nodes.text = ("调试运行中" if debug_active else "运行中") + "（%d）  " % names.size() + "、".join(names)
	running_nodes.tooltip_text = running_nodes.text


func refresh_states() -> void:
	for child in canvas.get_children():
		if child is GraphNode:
			_update_card(child)
	canvas.refresh_wires()
	_update_running_nodes()


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
	if not plan.nodes.has(source) or not plan.nodes.has(target):
		return
	var link := {"from":source, "to":target, "kind":"after"}
	if link not in plan.edges:
		plan.edges.append(link)


func _clarification_round(plan: Dictionary, upstream: String, index: int, questions: Array, answer: String) -> String:
	var answered := not answer.is_empty()
	var destination := "wf-clarification-answer-%d" % index if answered else "wf-clarification"
	_stage(plan, destination, "需求答复" if answered else "填写答复", answer if answered else "", "")
	for i in questions.size():
		var id := "wf-clarification-question-%d-%d" % [index, i]
		_stage(plan, id, "偃师提问", questions[i], upstream)
		_stage_edge(plan, id, destination)
	return destination


func _display_plan() -> Dictionary:
	if workflow.is_empty() or not draft.nodes.has("requirement"):
		return draft
	var plan := {"nodes":draft.nodes.duplicate(), "edges":draft.edges.duplicate()}
	var phase: String = workflow.phase
	var labels := {"draft":"等待确认发送", "submitted":"已发送，等待分析回执", "analyzing":"正在分析",
		"questions":"等待答复", "ready":"分析完成，需求已就绪", "error":"处理受阻，请查看关联对话",
		"cancelled":"已停止", "waiting_environment":"等待本地环境配置", "bound":"已关联工单",
		"blocked":"关联工单受阻", "closed":"关联工单已关闭"}
	var intake := "wf-analysis" if workflow.get("analyzed", false) and not workflow.get("direct", false) else "wf-workorder"
	if intake == "wf-analysis":
		_stage(plan, intake, "偃师 · 需求分析", labels.get(phase, "等待分析回执"), "requirement")
	else:
		_stage(plan, intake, "工单登记", "等待确认创建" if phase == "draft" else "已关联工单", "requirement")
	if workflow.get("direct", false) and phase != "draft":
		var decision: Dictionary = workflow.get("routing", {})
		var stage: String = workflow.get("routing_stage", "")
		var waiting := "司南正在判断需求" if stage == "sinan" else "等待框架判断回执"
		if stage == "yanshi":
			waiting = "已转交偃师分析"
		_stage(plan, "wf-routing", "司南 · 需求判断", waiting if not stage.is_empty() else decision.get("reason", waiting), intake)
		intake = "wf-routing"
		var history: Array = workflow.get("clarification_history", [])
		if stage == "yanshi" or decision.get("route") == "yanshi" or not history.is_empty():
			var detail := "已记录需求答复"
			if stage == "yanshi":
				detail = "偃师正在分析需求"
			elif decision.get("ready", false):
				detail = "需求已整理"
			elif not decision.get("questions", []).is_empty():
				detail = "等待补充需求"
			_stage(plan, "wf-analysis", "偃师 · 需求分析", detail, intake)
			intake = "wf-analysis"
			for i in history.size():
				var turn: Dictionary = history[i]
				intake = _clarification_round(plan, intake, i, turn.questions, turn.answer)
			if phase == "questions" and not workflow.get("judging", false) and not decision.get("questions", []).is_empty() and workflow.item.get("status") == "planned" and not workflow.item.get("closed", false):
				intake = _clarification_round(plan, intake, history.size(), decision.questions, "")
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
	var progress: Dictionary = workflow.get("progress", {})
	if not progress.is_empty():
		_stage(plan, "wf-worker", "当前工作者", progress.text, "wf-prepare" if prepare else intake)
	var operation: Dictionary = workflow.get("operation", {})
	if not operation.is_empty():
		_stage(plan, "wf-operation", operation.summary, operation.get("caption", ""), "wf-worker" if not progress.is_empty() else intake)
	var tasks := []
	var criteria := []
	var titles := {"scope":"预计任务", "acceptance":"验收条件", "questions":"待确认"}
	var source_nodes: Dictionary = item.get("plan", {}).get("nodes", {})
	for field in titles:
		if field == "questions" and workflow.get("direct", false):
			continue
		var entries: Dictionary = {}
		for id in source_nodes:
			var node: Dictionary = source_nodes[id]
			if node.title == titles[field] or (field == "scope" and node.title == "范围与验收") or (field == "questions" and item.get("questions", {}).has(id)):
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
				if prepare and intake.begins_with("wf-clarification-answer-"):
					_stage_edge(plan, intake, key)
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


func focus_flow_node(id: String) -> void:
	var card := canvas.get_node_or_null(NodePath(id)) as GraphNode
	if card:
		canvas.scroll_offset = (card.position_offset + card.size * 0.5) * canvas.zoom - canvas.size * 0.5
		card.selected = true
		var field := card.get_node_or_null("AnswerInput") as Control
		if field and field.is_visible_in_tree():
			field.grab_focus()


func focus_clarification() -> bool:
	if not is_instance_valid(canvas):
		return false
	var card := canvas.get_node_or_null("wf-clarification") as GraphNode
	if not card:
		return false
	_set_clarification_open(card, true)
	focus_flow_node("wf-clarification")
	return true


func _set_clarification_open(card: GraphNode, opened: bool) -> void:
	card.get_node("FillAnswer").visible = not opened
	card.get_node("AnswerInput").visible = opened
	card.get_node("AnswerActions").visible = opened
	if card.has_node("AnswerChoices"):
		card.get_node("AnswerChoices").visible = opened
	card.reset_size()
	_queue_layout()


func _clarification_scope() -> Array:
	var item: Dictionary = workflow.get("item", {})
	return [issue_id, item.get("url", ""), item.get("request", ""), item.get("updated", item.get("revision", "")), workflow.get("routing", {}).get("questions", [])]


# The existing work-order format marks an explicit list as 【选择】prompt | option | option.
# Keep the original question untouched for the authority check when submitting the answer.
func _add_answer_choices(card: GraphNode, input: TextEdit) -> void:
	var choices := VBoxContainer.new()
	for question: String in workflow.get("routing", {}).get("questions", []):
		if not question.begins_with("【选择】") and not question.begins_with("[选择]"):
			continue
		var parts := question.substr(4).split("|")
		if parts.size() < 3: continue
		var prompt := parts[0].strip_edges()
		var options := PackedStringArray()
		for i in range(1, parts.size()):
			var value := parts[i].strip_edges()
			if not value.is_empty() and value not in options: options.append(value)
		if options.size() < 2 or prompt.is_empty(): continue
		var picker := OptionButton.new()
		picker.tooltip_text = prompt
		picker.add_item(prompt)
		picker.fit_to_longest_item = false
		var prefix := prompt + "："
		for value in options:
			picker.add_item(value)
			if prefix + value in input.text.split("\n"): picker.select(picker.item_count - 1)
		choices.add_child(picker)
		picker.item_selected.connect(func(index):
			var lines := input.text.split("\n", false)
			for i in range(lines.size() - 1, -1, -1):
				if lines[i].begins_with(prefix) and lines[i].trim_prefix(prefix) in options:
					lines.remove_at(i)
			if index > 0: lines.append(prefix + picker.get_item_text(index))
			input.text = "\n".join(lines))
	if choices.get_child_count() == 0:
		choices.free()
		return
	choices.name = "AnswerChoices"
	card.add_child(choices)
	choices.hide()


func _add_clarification_editor(card: GraphNode) -> void:
	card.set_meta("clarification_scope", _clarification_scope().duplicate(true))
	var input := TextEdit.new()
	input.name = "AnswerInput"
	input.placeholder_text = "填写对本轮问题的答复"
	input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	input.scroll_fit_content_height = true
	input.custom_minimum_size = Vector2(280, 100) * get_theme_default_base_scale()
	input.text = clarification_draft
	_add_answer_choices(card, input)
	card.add_child(input)
	var actions := HBoxContainer.new()
	actions.name = "AnswerActions"
	card.add_child(actions)
	var submit := Button.new()
	submit.name = "SubmitAnswer"
	submit.text = "提交答复"
	actions.add_child(submit)
	var cancel := Button.new()
	cancel.name = "CancelAnswer"
	cancel.text = "取消"
	actions.add_child(cancel)
	var update := func(text: String):
		submit.disabled = text.length() > 4000 or text.strip_edges().is_empty()
	update.call(input.text)
	# TextEdit emits text_changed deferred; navigation can replace this card in the same frame.
	input.lines_edited_from.connect(func(_from: int, _to: int):
		if card.get_parent() == canvas:
			clarification_draft = input.text
			update.call(clarification_draft)
			clarification_draft_changed.emit(clarification_draft))
	var close_editor := func():
		_set_clarification_open(card, false)
		card.get_node("FillAnswer").grab_focus()
	cancel.pressed.connect(close_editor)
	input.gui_input.connect(func(event: InputEvent):
		if event is InputEventKey and event.pressed and not input.has_ime_text() and event.keycode == KEY_ESCAPE:
			input.accept_event()
			close_editor.call())
	submit.pressed.connect(func():
		var text := input.text
		if card.get_parent() == canvas and text.length() <= 4000 and not text.strip_edges().is_empty():
			clarification_submitted.emit(text))
	input.hide()
	actions.hide()


func pending_question() -> String:
	if context.get("can_answer", false):
		for id in context.get("questions", {}):
			if not context.get("answers", {}).has(id) and draft.nodes.has(id):
				return id
	return ""


func _render_stage(id: String, item: Dictionary) -> void:
	var view := SizeableCard.new()
	view.name = id
	view.title = item.title
	var heading := view.get_titlebar_hbox().get_child(0) as Label
	heading.custom_minimum_size.x = 210
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	view.draggable = false
	view.tooltip_text = item.value
	if id == "wf-clarification":
		var reply := Button.new()
		reply.name = "FillAnswer"
		reply.text = "填写答复"
		reply.custom_minimum_size.x = 210
		reply.pressed.connect(focus_clarification)
		view.add_child(reply)
	else:
		var description := _label(item.value)
		description.custom_minimum_size.x = 210
		description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		description.mouse_filter = Control.MOUSE_FILTER_IGNORE
		view.add_child(description)
	view.add_child(Control.new())
	view.set_slot(0, true, 0, DATA, true, 0, DATA)
	view.set_slot(1, true, 1, AFTER, true, 1, AFTER)
	_add_state_row(view)
	canvas.add_child(view)
	if card_sizes.has(id):
		view.size = card_sizes[id]
	view.geometry_edited.connect(func():
		card_sizes[id] = view.size
		positions[id] = view.position_offset
		_queue_layout()
		draft_changed.emit())
	_update_card(view)
	stage_controls_requested.emit(id, view)
	if id == "wf-clarification":
		_add_clarification_editor(view)
	if id == "wf-worker" and workflow.item.get("status") == "needs-decision":
		var target := pending_question()
		var caption := ""
		if not target.is_empty():
			caption = "前往待确认事项"
		elif workflow.progress.state == "pending":
			for key in draft.nodes:
				if draft.nodes[key].title in ["预计任务", "范围与验收"]:
					target = key
					caption = "查看后续工作"
					break
		if not target.is_empty():
			var navigate := Button.new()
			navigate.text = caption
			navigate.pressed.connect(focus_flow_node.bind(target))
			view.add_child(navigate)
	if id.begins_with("wf-questions-") and workflow.get("phase") == "questions":
		var reply := Button.new()
		reply.name = "FillAnswer"
		reply.text = "填写答复"
		reply.pressed.connect(func(): workflow_reply_requested.emit())
		view.add_child(reply)
	if id == "wf-operation":
		view.set_meta("ai_control_exclude", true)
		if _node_state(id) == "awaiting_approval":
			_add_approval_actions(view, workflow.operation.token)


func _add_approval_actions(view: GraphNode, token: String) -> void:
	var row := HBoxContainer.new()
	row.name = "ApprovalActions"
	view.add_child(row)
	var decision := OptionButton.new()
	decision.name = "Decision"
	decision.add_item("选择操作")
	decision.add_item("查看详情")
	decision.add_item("执行已预览的操作")
	row.add_child(decision)
	var confirm := Button.new()
	confirm.name = "Confirm"
	confirm.text = "确认"
	confirm.disabled = true
	row.add_child(confirm)
	decision.item_selected.connect(func(index): confirm.disabled = index == 0)
	confirm.pressed.connect(func():
		if view.get_parent() != canvas: return
		if decision.selected == 1:
			show_operation_details.emit(token)
		elif decision.selected == 2:
			confirm_operation.emit(token))



func await_graph_projection() -> void:
	while graph_projection_pending:
		await graph_projection_finished


func _continue_graph_projection(epoch: int) -> bool:
	if epoch != graph_projection_generation:
		return false
	if is_visible_in_tree():
		return true
	graph_projection_pending = false
	graph_projection_suspended = true
	graph_projection_finished.emit()
	return false


func update_workflow(facts: Dictionary, redraw: bool) -> void:
	var previous := _display_plan() if redraw and not graph_projection_pending else {}
	workflow = facts.duplicate(true)
	if redraw:
		draw_graph(issue_id.begins_with("https://"), previous)


func draw_graph(staged := false, previous := {}) -> void:
	graph_projection_generation += 1
	var epoch := graph_projection_generation
	graph_projection_suspended = staged and not is_visible_in_tree()
	graph_projection_pending = not graph_projection_suspended
	if graph_projection_suspended:
		graph_projection_finished.emit()
		return
	graph_rebuilding.emit()
	var plan := _display_plan()
	var old := canvas.get_node_or_null("wf-clarification") as GraphNode
	var reopen := false
	var refocus := false
	var caret := Vector2i.ZERO
	if old and plan.nodes.has("wf-clarification") and old.get_meta("clarification_scope") == _clarification_scope():
		var field := old.get_node("AnswerInput") as TextEdit
		reopen = field.visible
		refocus = field.has_focus()
		caret = Vector2i(field.get_caret_column(), field.get_caret_line())
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
	var retained := {}
	if not previous.is_empty():
		for child in canvas.get_children():
			if not child is GraphNode:
				continue
			var id := String(child.name)
			# Interactive workflow stages bind actions to the current receipt when rendered.
			if draft.nodes.has(id) or id.begins_with("wf-scope-") or id.begins_with("wf-acceptance-") or id.begins_with("wf-dep-"):
				if plan.nodes.has(id) and plan.nodes[id] == previous.nodes.get(id):
					retained[id] = true
	if retained.is_empty():
		canvas.clear_flow()
	else:
		var unchanged_wires := {}
		for edge in plan.edges:
			if retained.has(edge.from) and retained.has(edge.to):
				unchanged_wires[_wire_key(edge, plan.nodes)] = true
		for key in canvas.lines.keys():
			if not unchanged_wires.has(key):
				canvas.disconnect_flow(key[0], key[1], key[2], key[3])
	var deadline := Time.get_ticks_usec() + GRAPH_SLICE_US
	for child in canvas.get_children():
		if child is GraphNode and not retained.has(String(child.name)):
			child.hide()
	for child in canvas.get_children():
		if child is GraphNode and not retained.has(String(child.name)):
			canvas.remove_child(child)
			child.queue_free()
			if staged and Time.get_ticks_usec() >= deadline:
				await get_tree().process_frame
				if not _continue_graph_projection(epoch):
					return
				deadline = Time.get_ticks_usec() + GRAPH_SLICE_US
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
		if retained.has(id):
			_update_card(canvas.get_node(NodePath(str(id))))
		elif draft.nodes.has(id):
			_render_node(id, plan.nodes[id])
		else:
			_render_stage(id, plan.nodes[id])
		var view := canvas.get_node(NodePath(str(id))) as GraphNode
		layout_columns[level].append(view)
		if not view.resized.is_connected(_queue_layout):
			view.resized.connect(_queue_layout)
		if staged and Time.get_ticks_usec() >= deadline:
			_queue_layout()
			await get_tree().process_frame
			if not _continue_graph_projection(epoch):
				return
			deadline = Time.get_ticks_usec() + GRAPH_SLICE_US
	_layout_cards()
	for edge in plan.edges:
		_draw_edge(edge, plan.nodes)
		if staged and Time.get_ticks_usec() >= deadline:
			await get_tree().process_frame
			if not _continue_graph_projection(epoch):
				return
			deadline = Time.get_ticks_usec() + GRAPH_SLICE_US
	_update_running_nodes()
	if reopen:
		var card := canvas.get_node("wf-clarification") as GraphNode
		_set_clarification_open(card, true)
		var field := card.get_node("AnswerInput") as TextEdit
		field.set_caret_line(caret.y)
		field.set_caret_column(caret.x)
		if refocus:
			field.grab_focus()
	graph_projection_pending = false
	graph_projection_finished.emit()


# Wrapping and theme changes can resize a card after GraphNode has sorted its children.
func _queue_layout() -> void:
	if not layout_pending:
		layout_pending = true
		_layout_cards.call_deferred()


func _layout_cards() -> void:
	layout_pending = false
	graph_layout.arrange_flow(canvas, layout_columns, positions)


func _draw_edge(edge: Dictionary, nodes := {}) -> void:
	if nodes.is_empty():
		nodes = draft.nodes
	var key := _wire_key(edge, nodes)
	canvas.connect_flow(key[0], key[1], key[2], key[3])


func _wire_key(edge: Dictionary, nodes: Dictionary) -> Array:
	var output := 0 if edge.kind == "data" else 1
	var input := 0
	if edge.kind == "after" and nodes[edge.to].kind in ["task","join","stage"]:
		input = 1
	return [StringName(edge.from), output, StringName(edge.to), input]


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
		canvas.disconnect_flow(a,ap,b,bp)
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
	refresh_states()
	notice.text = "已应用" if baseline == draft else "已应用提交版本；后续编辑仍在草稿中"
	applied.emit(issue_id, revision)

func set_debug_state(event: Dictionary) -> void:
	debug_states[event.id] = event
	var view := canvas.get_node_or_null(NodePath(str(event.id))) as GraphNode
	if debug_active and view:
		_update_card(view)
		canvas.refresh_wires(view.name)
		_update_running_nodes()


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
