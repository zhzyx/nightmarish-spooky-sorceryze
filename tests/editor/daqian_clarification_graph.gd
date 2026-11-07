extends SceneTree

var failed := false
var graph
var submissions: Array[String] = []
var edits: Array[String] = []


func check(ok: bool, reason: String) -> void:
	if not ok:
		failed = true
		push_error(reason)


func _initialize() -> void:
	run.call_deferred()


func check_graph() -> void:
	graph.draw_graph()
	var plan: Dictionary = graph._display_plan()
	for edge in plan.edges:
		check(plan.nodes.has(edge.from) and plan.nodes.has(edge.to), "missing projected edge endpoint")
		check(graph.canvas.is_node_connected(edge.from, 1, edge.to, 1), "missing native step wire: " + str(edge))


func linked(source: String, target: String) -> bool:
	return graph.canvas.is_node_connected(source, 1, target, 1)


func click(button: Button) -> void:
	var point := button.get_global_transform_with_canvas() * (button.size / 2)
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		root.push_input(event, true)


func run() -> void:
	graph = preload("res://editor/docks/daqian/issue_graph.gd").new()
	graph.rules = preload("res://editor/docks/daqian/graph_rules.gd")
	graph.graph_layout = preload("res://editor/docks/daqian/graph_layout.gd")
	root.add_child(graph)
	root.size = Vector2i(1100, 720)
	graph.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	graph.draft = {"nodes":{"requirement":{"kind":"text","title":"需求","value":"测试"}}, "edges":[]}
	var questions := ["交付到哪个平台？", "需要哪些资源？"]
	graph.workflow = {"phase":"questions", "direct":true, "item":{"status":"planned"},
		"design":{"questions":questions}, "routing":{"route":"yanshi","ready":false,"questions":questions}}
	graph.clarification_draft_changed.connect(func(text): edits.append(text))
	graph.clarification_submitted.connect(func(text): submissions.append(text))
	check_graph()
	var active: GraphNode = graph.canvas.get_node("wf-clarification")
	check(active.get_node("FlowState").text == "待你答复", "missing pending answer status")
	check(active.get_theme_stylebox("panel").border_width_left >= 2, "pending answer input lacks highlight")
	check(graph.canvas.find_children("FillAnswer", "Button", true, false).size() == 1, "questions must share one answer action")
	for i in questions.size():
		var question := "wf-clarification-question-0-%d" % i
		check(linked("wf-analysis", question) and linked(question, "wf-clarification"), "question does not lead to input")
		check(graph.canvas.get_node(NodePath(question + "/FlowState")).text == "待确认", "unanswered question marked complete")
	for i in 4: await process_frame
	graph.focus_flow_node("wf-clarification")
	for i in 2: await process_frame
	click(active.get_node("FillAnswer"))
	await process_frame
	var input := active.get_node("AnswerInput") as TextEdit
	check(input.is_visible_in_tree() and input.has_focus(), "click failed to focus inline answer")
	var key := InputEventKey.new()
	key.pressed = true
	key.unicode = "测".unicode_at(0)
	root.push_input(key, true)
	await process_frame
	check(input.text == "测" and edits.back() == "测" and graph.canvas.get_node("wf-clarification") == active, "normal typing lost focus, draft, or card identity")
	key.unicode = 0
	key.keycode = KEY_ESCAPE
	root.push_input(key, true)
	await process_frame
	check(not input.visible and submissions.is_empty() and input.text == "测", "Escape lost or submitted answer")
	check(graph.focus_clarification() and input.visible, "toolbar could not reopen the inline field")
	graph.draw_graph()
	for i in 3: await process_frame
	active = graph.canvas.get_node("wf-clarification")
	input = active.get_node("AnswerInput") as TextEdit
	check(input.text == "测" and input.visible and input.has_focus(), "identical question redraw lost the open answer")
	graph.focus_flow_node("wf-clarification")
	await process_frame
	click(active.get_node("AnswerActions/SubmitAnswer"))
	check(submissions == ["测"] and not graph.canvas.has_node("wf-prepare"), "inline submit or readiness is incorrect")

	graph.workflow.clarification_history = [{"questions":questions,"answer":"Windows，使用现有资源。"}]
	graph.workflow.phase = "routing"
	graph.workflow.routing = {}
	graph.workflow.design = {}
	check_graph()
	var answered := "wf-clarification-answer-0"
	check(graph.canvas.get_node(NodePath(answered)).get_node("FlowState").text == "已答复", "lost accepted answer")
	check(graph.canvas.get_node("wf-clarification-question-0-0/FlowState").text == "已完成", "accepted question still pending")
	check(not graph.canvas.has_node("wf-clarification") and not graph.canvas.has_node("wf-prepare"), "missing receipt produced an actionable node")
	check(graph.canvas.get_node("wf-analysis").tooltip_text != "等待补充需求", "empty receipt presented stale questions")
	graph.workflow.phase = "questions"
	graph.workflow.routing = {"route":"yanshi","ready":false,"questions":["需要兼容哪些版本？"]}
	graph.clarification_draft = ""
	check_graph()
	check(graph.canvas.get_node("wf-clarification/AnswerInput").text.is_empty() and not graph.canvas.has_node(NodePath(answered + "/AnswerInput")), "new question or historical card inherited the input")
	check(linked(answered, "wf-clarification-question-1-0") and linked("wf-clarification-question-1-0", "wf-clarification"), "second round detached from first answer")
	graph.workflow.judging = true
	check_graph()
	check(not graph.canvas.has_node("wf-clarification"), "duplicate reply exposed while judging")

	graph.workflow.judging = false
	graph.workflow.phase = "bound"
	graph.workflow.clarification_history.append({"questions":["需要兼容哪些版本？"],"answer":"当前版本。"})
	graph.workflow.routing = {"route":"yanshi","ready":true,"questions":[]}
	graph.workflow.design = {"scope":["制作图标","更新说明"],"acceptance":["验证结果"]}
	check_graph()
	for clause in graph.workflow.design.scope:
		var task := "wf-scope-" + str(clause).sha256_text().left(20)
		check(linked("wf-clarification-answer-1", task) and linked(task, "wf-verify"), "accepted answer did not branch into parallel tasks and verification")
	check(not graph.canvas.has_node("wf-clarification"), "validated answers left a stale input")
	graph.free()
	if not failed:
		print("DAQIAN_CLARIFICATION_GRAPH_OK")
	quit(1 if failed else 0)
