@tool
extends SceneTree

var failures := []
var state := {}
var writes := 0
var delay_detail := false
signal release_detail


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, reason: String) -> void:
	if not value:
		failures.append(reason)
		push_error(reason)


func check_spacing(canvas: GraphEdit, scenario: String) -> void:
	var bounds: Array[Rect2] = []
	for card in canvas.get_children():
		if card is GraphNode:
			var rect := Rect2(card.position_offset, card.size)
			for other in bounds:
				if rect.grow(8).intersects(other):
					check(false, "%s: %s overlaps another card" % [scenario, card.name])
					return
			bounds.append(rect)


func settle_layout() -> void:
	for frame in 5:
		await process_frame


func read_graph(_id):
	if delay_detail:
		await release_detail
	return state.duplicate(true)


func apply_graph(_id, revision, execution_revision, draft):
	if revision != state.revision or execution_revision != state.execution_revision:
		return {"ok":false, "error":"版本冲突"}
	writes += 1
	state.plan = draft.duplicate(true)
	state.revision = str(writes)
	return {"ok":true,"revision":state.revision,"context":state.context}


func run() -> void:
	await create_timer(1.5).timeout
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace",OS.get_environment("DAQIAN_TEST_REPO"))
	settings.set_setting("gonggong/python",OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	if not dock:
		push_error("Missing native Daqian editor tab")
		quit(1)
		return
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	var workspace = dock.find_child("DaqianWorkspace", true, false)
	await workspace.refresh()
	check(workspace.actor.get("user_id","")=="42","fixture collaborator membership was not verified")
	var graph = workspace.editor
	workspace._new_requirement()
	state = {"plan":{"nodes":{},"edges":[]},"revision":"0","execution_revision":"0",
		"context":{"models":{"vision":["image"],"text":["text"]},"states":{}}, "can_edit":true}
	graph.bind_issue("repo#1",state,apply_graph,read_graph)
	var source = graph.add_node("image",Vector2.ZERO)
	var left = graph.add_node("task",Vector2(300,-100))
	var right = graph.add_node("task",Vector2(300,200))
	var merge = graph.add_node("join",Vector2(650,0))
	var img := Image.create_empty(4,4,false,Image.FORMAT_RGB8)
	img.fill(Color.ORANGE)
	graph.set_image(source,img)
	await process_frame
	graph.draft.nodes[left].model = "text"
	check(graph.preview_edge(source,0,left,0).contains("图片"),"text model accepted image")
	graph.draft.nodes[left].model = "vision"
	graph.connect_ports(source,0,left,0)
	graph.connect_ports(source,0,right,0)
	graph.connect_ports(left,0,merge,0)
	graph.connect_ports(right,0,merge,0)
	check(graph.draft.edges.size() == 4, "fan out and join")
	var left_wire: Line2D = graph.canvas.lines[[StringName(source), 0, StringName(left), 0]]
	var right_wire: Line2D = graph.canvas.lines[[StringName(source), 0, StringName(right), 0]]
	var left_card: GraphNode = graph.canvas.get_node(NodePath(left))
	var right_card: GraphNode = graph.canvas.get_node(NodePath(right))
	var editor_field: TextEdit = left_card.get_node("PlanText")
	graph.context.states = {source:"completed", left:"running"}
	graph.refresh_states()
	check(left_card.get_node("FlowState").text == "运行中" and not editor_field.editable, "active state and edit lock")
	check(right_card.get_node("FlowState").text == "待制作" and graph.running_nodes.visible, "pending parallel branch")
	check(left_wire.material == graph.canvas.materials.running and right_wire.material == graph.canvas.materials.pending, "per-branch wire materials")
	var draft_before: Dictionary = graph.draft.duplicate(true)
	graph.debug_active = true
	graph.refresh_states()
	graph.set_debug_state({"id":source, "state":"completed"})
	graph.set_debug_state({"id":left, "state":"running"})
	graph.set_debug_state({"id":right, "state":"running"})
	check(graph.running_nodes.text.begins_with("调试运行中（2）") and right_wire.material == left_wire.material, "two simultaneous debug branches")
	graph.set_debug_state({"id":left, "state":"completed"})
	check(left_wire.material == graph.canvas.materials.done and right_wire.material == graph.canvas.materials.running, "completed branch stopped flowing")
	graph.set_debug_state({"id":right, "state":"failed"})
	check(right_wire.material == graph.canvas.materials.failed and not graph.running_nodes.visible, "failure stopped activity")
	graph.debug_active = false
	graph.refresh_states()
	check(left_card.get_node("PlanText") == editor_field and graph.draft == draft_before and left_wire.material == graph.canvas.materials.running, "debug isolated from editing and production")
	graph.context.states.clear()
	graph.refresh_states()
	check(editor_field.editable and left_wire.material == graph.canvas.materials.pending, "clear state restores draft control")
	check(graph.preview_edge(source,0,left,0).contains("相同"),"duplicate accepted")
	check(graph.preview_edge(merge,1,left,1).contains("循环"),"mixed cycle accepted")
	check(graph.preview_edge(source,0,left,1).contains("不匹配"),"mixed ports accepted")
	graph.apply_draft()
	check(writes == 1 and state.plan.edges.size() == 4,"group was not applied atomically")
	graph.disconnect_ports(source,0,left,0)
	graph.draft.nodes[left].value = "new input"
	state.context.states[left] = "running"
	state.execution_revision = "1"
	graph.apply_draft()
	check(writes == 1 and state.plan.edges.size()==4 and graph.draft.edges.size()==3,"running target changed or draft discarded")
	state.context.states.clear()
	graph.context.protected_edges = [graph.draft.edges[0]]
	var edge = graph.draft.edges[0]
	graph.disconnect_ports(edge.from,0,edge.to,0)
	check(graph.draft.edges.size()==3,"removed protected connection")
	graph.positions.clear()
	graph.draft.edges.append({"from":source, "to":left, "kind":"data"})
	graph.draw_graph()
	await settle_layout()
	check_spacing(graph.canvas, "parallel tasks")
	var first := graph.canvas.get_node(NodePath(left)) as GraphNode
	var second := graph.canvas.get_node(NodePath(right)) as GraphNode
	var join := graph.canvas.get_node(NodePath(merge)) as GraphNode
	var midpoint := (minf(first.position_offset.y, second.position_offset.y)
		+ maxf(first.position_offset.y + first.size.y, second.position_offset.y + second.size.y)) / 2.0
	check(absf(join.position_offset.y + join.size.y / 2.0 - midpoint) < 2, "join misaligned with branches")
	var previous := first.position_offset
	first.position_offset = second.position_offset
	first.dragged.emit(previous, first.position_offset)
	await settle_layout()
	check_spacing(graph.canvas, "drag onto automatic task")
	graph.draw_graph()
	await settle_layout()
	check_spacing(graph.canvas, "restored drag position")
	check(graph.canvas.get_node(NodePath(left)).position_offset == graph.positions[left], "moved pinned task")
	graph.draft = {"nodes":{"requirement":{"kind":"text","title":"需求","value":"布局验证"}}, "edges":[]}
	graph.workflow = {"phase":"ready", "item":{}, "design":{"scope":["步骤一", "包含换行的阶段描述".repeat(40), "步骤三"], "acceptance":["验收"]}}
	graph.draw_graph()
	await settle_layout()
	check(graph.canvas.has_node("wf-verify"), "missing generated verification stage")
	check_spacing(graph.canvas, "generated workflow with wrapped stages")
	var original: Vector2 = graph.canvas.get_node("wf-verify").position_offset
	graph.draw_graph()
	await settle_layout()
	check(graph.canvas.get_node("wf-verify").position_offset == original, "unstable generated layout")
	graph.workflow = {}
	var issues := []
	for i in range(55):
		var url := "https://github.com/fixture/board/issues/" + str(i+1)
		issues.append({"number":i+1,"url":url,"title":"需求 " + str(i+1),"owners":["tester"],
			"status":"in-progress","closed":false,"request":"test","updated":"fixture","decision":i==50,
			"dependencies":[issues[i-1].url] if i>0 else [],"plan":{"nodes":{},"edges":[]}})
	issues[0].title = "包含长标题的工单".repeat(20)
	for step in 12:
		issues[0].plan.nodes[str(step)] = {"kind":"task","title":"预计任务","value":"详细步骤".repeat(12)}
	issues[0].status = "done"
	issues[2].closed = true
	workspace.board = {"repo":"fixture/board","issues":issues,"verified_at":"fixture"}
	workspace._show_board()
	await settle_layout()
	check_spacing(workspace.overview, "board overview")
	workspace.overview.zoom = 1.4
	workspace._zoom_detail()
	await settle_layout()
	check_spacing(workspace.overview, "expanded board")
	var pinned := workspace.overview.get_node("i_1") as GraphNode
	previous = pinned.position_offset
	pinned.position_offset = workspace.overview.get_node("i_2").position_offset
	pinned.dragged.emit(previous, pinned.position_offset)
	await settle_layout()
	check_spacing(workspace.overview, "drag onto automatic issue")
	check(workspace.saved.positions[issues[0].url] == pinned.position_offset, "board drag was not saved")
	check(workspace.overview.get_connection_list().size()==54,"historical dependency chain")
	var board_wire: Line2D = workspace.overview.lines[[&"i_1", 0, &"i_2", 0]]
	check(board_wire.material == workspace.overview.materials.running, "board dependency flows toward active Issue")
	check(workspace.overview.get_node("i_3").get_meta("flow_state") == "closed", "closed Issue kept open status")
	workspace.search.text = "#50"
	workspace._filter_board()
	check(workspace.overview.get_node("i_50").visible and not workspace.overview.get_node("i_5").visible,"large board search")
	check(not board_wire.visible, "filtered wire visible without endpoints")
	workspace._locate_pending(51)
	check(workspace.overview.get_node("i_51").selected,"waiting issue navigation")
	state.plan = {"nodes":{},"edges":[]}
	state.context = {}
	workspace.host = self
	delay_detail = true
	workspace._open_issue(issues[0])
	check(workspace.current == issues[0].url and graph.visible, "cached detail must appear before remote reply")
	workspace._open_issue(issues[1])
	var edited = graph.add_node("text",Vector2.ZERO)
	var input: TextEdit = graph.canvas.get_node(NodePath(edited)).find_children("*","TextEdit",false,false)[0]
	input.grab_focus()
	input.text = "草稿输入"
	input.text_changed.emit()
	release_detail.emit()
	check(workspace.current == issues[1].url and graph.draft.nodes.has(edited), "late reply replaced selection or erased edits")
	check(is_instance_valid(input) and input.has_focus(), "background reply stole draft input focus")
	delay_detail = false
	await graph.apply_draft()
	check(state.plan.nodes.has(edited) and state.plan.nodes[edited].value == "草稿输入", "edits made before source read could not be applied")
	delay_detail = true
	workspace._show_board()
	workspace._open_issue(issues[2])
	release_detail.emit()
	check(graph.revision == state.revision and graph.draft == state.plan, "clean snapshot did not advance to live plan")
	workspace._show_board()
	delay_detail = false
	issues[4].decision = true
	issues[4].pending_count = 1
	state.plan = {"nodes":{"requirement":{"title":"需求", "kind":"text", "value":"选主题"}, "theme":{"title":"主题", "kind":"question", "value":"选主题"}}, "edges":[]}
	state.context = {"questions":{"theme":{"kind":"choice", "prompt":"选主题", "options":["青色","紫色"]}}, "answers":{}}
	workspace._draw_board()
	await workspace._locate_pending(5)
	var choice := graph.canvas.get_node_or_null("theme/ReplyInput") as OptionButton
	check(workspace.current == issues[4].url and choice != null and choice.has_focus(), "pending item did not open the correct issue and focus its choice field")
	if choice:
		var submit := graph.canvas.get_node("theme/SubmitReply") as Button
		check(submit.disabled, "empty choice can be submitted")
		choice.select(1)
		choice.item_selected.emit(1)
		check(not submit.disabled and graph.answers.theme == "青色", "chosen reply was lost")
	workspace._show_board()
	workspace.search.text = "no-such-title"
	workspace._filter_board()
	check(workspace.empty_state.visible and workspace.reset_filters.visible, "empty search needs a recovery action")
	workspace.reset_filters.pressed.emit()
	check(workspace.overview.visible and not workspace.empty_state.visible, "clear filters did not restore the overview")
	workspace.host = null
	delay_detail = false
	workspace.board = {}
	workspace._show_board()
	var access_path = OS.get_environment("DAQIAN_TEST_ACCESS_FILE")
	if not access_path.is_empty():
		var calls := access_path.get_base_dir().path_join("daqian-auth-calls")
		var before := FileAccess.get_file_as_string(calls)
		await workspace.refresh()
		check("verify" in before and FileAccess.get_file_as_string(calls) == before,"warm refresh repeated remote verification")
		var access_file = FileAccess.open(access_path,FileAccess.WRITE)
		access_file.store_string("switch")
		access_file.close()
		await workspace.refresh()
		check(workspace.actor.get("user_id")=="84" and not workspace.saved.has("drafts"),"another account inherited personal drafts")
		access_file=FileAccess.open(access_path,FileAccess.WRITE)
		access_file.store_string("denied")
		access_file.close()
		await workspace.refresh()
		workspace._new_requirement()
		check(workspace.actor.is_empty() and not workspace.editor.visible and not workspace.overview.visible,"revoked member can still view or edit")
	print("DAQIAN_GRAPH_TEST ", "passed" if failures.is_empty() else failures)
	quit(0 if failures.is_empty() else 1)
