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


func check_snapshot_edits(rules: Script) -> void:
	var edge := {"from": "a", "to": "b", "kind": "after"}
	var base := {"nodes": {"a": {"value": "old"}, "b": {}}, "edges": [edge]}
	var local := base.duplicate(true)
	local.nodes.a.value = "new"
	local.edges.clear()
	var live := base.duplicate(true)
	live.nodes.c = {}
	var result: Dictionary = rules.reconcile_snapshot(base, local, live)
	check(result.get("plan") == {"nodes": {"a": {"value": "new"}, "b": {}, "c": {}}, "edges": []}, "late source update discarded a local edit or disconnect")
	live.nodes.a.value = "other"
	check(rules.reconcile_snapshot(base, local, live).has("error") and local.nodes.a.value == "new", "overlapping edits did not preserve the draft")


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


func await_fixture_file(path: String) -> void:
	var deadline := Time.get_ticks_msec() + 8000
	while not FileAccess.file_exists(path) and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	check(FileAccess.file_exists(path), "fixture did not enter " + path.get_file())


func check_watcher_poll_interval(workspace) -> void:
	var child := OS.execute_with_pipe(OS.get_environment("DAQIAN_TEST_PYTHON"),
		["-c", "import sys; sys.stdout.write('unrelated\\npartial'); sys.stdout.flush(); sys.stdin.readline()"], false)
	check(not child.is_empty(), "failed to start watcher interval fixture")
	if child.is_empty():
		return
	var stream: FileAccess = child.stdio
	var deadline := Time.get_ticks_msec() + 5000
	while stream.get_length() == 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	var size := stream.get_length()
	check(size > 0, "watcher fixture produced no bytes")
	workspace.watcher = child
	workspace.watcher_poll_after = Time.get_ticks_msec() + 15_000
	workspace._process(0.0)
	check(stream.get_length() == size and workspace.watcher_buffer.is_empty(), "watcher read before its poll deadline")
	workspace.watcher_poll_after = 0
	var started := Time.get_ticks_msec()
	workspace._process(0.0)
	check(stream.get_length() == 0 and workspace.watcher_buffer == "partial", "watcher missed bytes at its poll deadline")
	check(workspace.watcher_poll_after >= started + 15_000 and workspace.watcher_poll_after <= Time.get_ticks_msec() + 15_000, "watcher did not schedule its next 15-second interval")
	check(not workspace.checking and not workspace.auto_refresh_pending and not workspace.refresh_pending, "unrelated watcher output triggered a refresh")
	workspace._stop_progress_watch()


func check_auto_refresh_interval(workspace) -> void:
	var completions := [0]
	var completed := func(): completions[0] += 1
	workspace.refresh_finished.connect(completed)
	workspace.auto_refresh_after = Time.get_ticks_msec() + 300_000
	for i in 3:
		workspace._opened()
		workspace._process(0.0)
	check(not workspace.auto_refresh_pending and not workspace.checking and completions[0] == 0, "reopening a fresh board scheduled another remote read")
	workspace.auto_refresh_after = 0
	workspace._opened()
	var started := Time.get_ticks_msec()
	workspace._process(0.0)
	check(workspace.checking and not workspace.auto_refresh_pending, "queued automatic events did not start one board read")
	check(workspace.auto_refresh_after >= started + 300_000 and workspace.auto_refresh_after <= Time.get_ticks_msec() + 300_000, "board refresh interval was not five minutes")
	# A matching progress notification arrives after the active snapshot started.
	var row := {"url":"fixture-issue", "request":"fixture-request"}
	workspace.board.issues.append(row)
	workspace._chat_work_event(workspace._repo(), {"actor":workspace.actor.user_id, "source_ref":row.url,
		"source_sha256":"test-revision", "request_ref":row.request}, "fixture", "request_end", "chat", "completed")
	workspace.board.issues.pop_back()
	if workspace.checking:
		await workspace.refresh_finished
	check(completions[0] == 1 and workspace.auto_refresh_pending, "last event during the active read was lost or replayed immediately")
	workspace.auto_refresh_after = 0
	workspace._process(0.0)
	if workspace.checking:
		await workspace.refresh_finished
	check(completions[0] == 2, "trailing board refresh did not complete")
	workspace.auto_refresh_after = Time.get_ticks_msec() + 300_000
	await workspace.refresh()
	check(completions[0] == 3, "manual refresh was throttled")
	workspace.refresh_finished.disconnect(completed)
	workspace._stop_progress_watch()


func run() -> void:
	root.content_scale_size = Vector2i(1280, 900)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	await create_timer(1.5).timeout
	var settings = EditorInterface.get_editor_settings()
	settings.set_setting("gonggong/workspace",OS.get_environment("DAQIAN_TEST_REPO"))
	root.find_child("AI Chat", true, false).set_runtime_field("workflow_python", OS.get_environment("DAQIAN_TEST_PYTHON"))
	var dock = root.find_child("Daqian", true, false)
	if not dock:
		push_error("Missing native Tianshu editor tab")
		quit(1)
		return
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	var workspace = dock.find_child("DaqianWorkspace", true, false)
	await workspace.refresh()
	if workspace.actor.get("user_id", "") != "42":
		push_error("fixture membership not verified: %s (pending=%s, checking=%s)" % [workspace.notice.text, workspace.refresh_pending, workspace.checking])
		quit(1)
		return
	# The next section supplies its own 55-row board; live receipts must not replace it.
	workspace._stop_progress_watch()
	await check_watcher_poll_interval(workspace)
	await check_auto_refresh_interval(workspace)
	var exited := OS.execute_with_pipe(OS.get_environment("DAQIAN_TEST_PYTHON"), ["-c", "pass"], false)
	check(not exited.is_empty(), "failed to start watcher exit fixture")
	if not exited.is_empty():
		var deadline := Time.get_ticks_msec() + 5000
		while OS.is_process_running(exited.pid) and Time.get_ticks_msec() < deadline:
			await process_frame
		workspace.watcher = exited
		workspace.watcher_buffer = "partial"
		workspace.watcher_poll_after = 0
		workspace._process(0.0)
		check(workspace.watcher.is_empty() and workspace.watcher_buffer.is_empty(), "exited watcher was polled or retained")
		check(workspace.auto_refresh_pending and workspace.watcher_exited, "watcher exit did not queue reconciliation and suppress automatic restart")
		workspace._stop_progress_watch()
		check(not workspace.auto_refresh_pending and not workspace.watcher_exited, "watcher reset left stale reconciliation state")
	var graph = workspace.editor
	check_snapshot_edits(workspace.rules)
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
	var editor_field: TextEdit = left_card.get_node("PlanContent")
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
	check(left_card.get_node("PlanContent") == editor_field and graph.draft == draft_before and left_wire.material == graph.canvas.materials.running, "debug isolated from editing and production")
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
	issues[9].status = "needs-decision"
	issues[7].categories = ["development"]
	issues[8].categories = ["bug"]
	workspace.board = {"repo":"fixture/board","issues":issues,"verified_at":"fixture"}
	workspace._show_board()
	await settle_layout()
	check(workspace.issue_list.visible and workspace.issue_rows.size() == 55 and workspace.board_cards.is_empty(), "list should show the 55 issues without building hidden graph cards")
	var sorted: Array = workspace.issue_list.get_root().get_children()
	check(sorted[0].get_metadata(0).number == 10 and sorted[1].get_metadata(0).number == 51, "explicit decision and pending answers must lead")
	check(sorted[2].get_metadata(0).number == 9 and sorted[3].get_metadata(0).number == 8, "category order must precede issue number")
	check(workspace.pending_menu.get_popup().get_item_index(10) == -1, "a status label without a question entered the user's todo menu")
	workspace.status.select(1)
	workspace._filter_board()
	check(not workspace.issue_rows[issues[9].url].visible, "action filter included an issue without a pending action")
	workspace.status.select(0)
	workspace._filter_board()
	var first_row: TreeItem = workspace.issue_rows[issues[0].url]
	check(first_row.get_text(1) == issues[0].title and first_row.get_text(2) == "已完成", "list lost full title or status")
	check(workspace.board_views.get_tab_rect(1).end.x <= workspace.board_views.size.x, "second view tab is clipped")
	check(workspace.result_count.text == "55 项", "visible count missing from overview")
	workspace.host = self
	workspace.issue_list.grab_focus()
	var find := InputEventKey.new()
	find.keycode = KEY_F
	find.pressed = true
	find.meta_pressed = OS.has_feature("macos")
	find.ctrl_pressed = not find.meta_pressed
	workspace.get_viewport().push_input(find, true)
	check(workspace.search.has_focus(), "platform Find shortcut did not focus search")
	workspace.search.text = "#50"
	workspace.search.text_changed.emit("#50")
	var down := InputEventKey.new()
	down.keycode = KEY_DOWN
	down.pressed = true
	workspace.get_viewport().push_input(down, true)
	check(workspace.issue_list.has_focus() and workspace.issue_list.get_selected() == workspace.issue_rows[issues[49].url], "Down did not focus the first matching issue")
	var enter := InputEventKey.new()
	enter.keycode = KEY_ENTER
	enter.pressed = true
	workspace.get_viewport().push_input(enter, true)
	check(workspace.current == issues[49].url and not workspace.issue_list.visible, "Enter did not open the selected issue")
	var hidden_row: TreeItem = workspace.issue_rows[issues[49].url]
	workspace._draw_board()
	check(is_instance_valid(hidden_row), "Refreshing a requirement rebuilt the hidden overview")
	workspace.editor.canvas.zoom = 0.29
	workspace._check_canvas_zoom()
	check(workspace.board_views.current_tab == 0 and workspace.search.text == "#50" and workspace.issue_rows[issues[49].url].is_selected(0), "zoom return lost the filtered list or selected issue")
	workspace.get_viewport().push_input(enter, true)
	workspace.return_button.pressed.emit()
	check(workspace.search.text == "#50" and workspace.issue_list.has_focus() and workspace.issue_list.get_selected() == workspace.issue_rows[issues[49].url], "return lost filter, selection or keyboard focus")
	workspace.search.grab_focus()
	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	workspace.get_viewport().push_input(escape, true)
	check(workspace.search.text.is_empty() and workspace.issue_rows[issues[0].url].visible, "Escape did not clear the search")
	workspace.board_views.current_tab = 1
	check(workspace.saved.board_view == 1 and not workspace.issue_list.visible, "graph preference or view visibility lost")
	await settle_layout()
	check_spacing(workspace.overview, "board overview")
	workspace.overview.zoom = 1.4
	workspace._zoom_detail()
	await settle_layout()
	check_spacing(workspace.overview, "expanded board")
	var pinned := workspace.overview.get_node("i_1") as GraphNode
	var full_title := pinned.get_node("OpenIssue") as Button
	check(full_title.text == issues[0].title and full_title.size.y > 2 * full_title.get_theme_font("font").get_height(full_title.get_theme_font_size("font_size")), "long overview title did not expand")
	var full_step := pinned.get_node("StepDetails").get_child(0) as Label
	check(issues[0].plan.nodes["0"].value in full_step.text and full_step.get_visible_line_count() == full_step.get_line_count(), "long overview step lost text")
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
	workspace._open_issue(issues[50])
	graph.canvas.zoom = 100
	check(is_equal_approx(graph.canvas.zoom, 1.6), "single issue detail exceeded zoom cap")
	graph.canvas.zoom = 0.29
	await settle_layout()
	check(workspace.current.is_empty() and workspace.overview.visible and workspace.board_cards.size() == 55, "zoom out from issue missed personal board")
	workspace.overview.zoom = 0.34
	var wheel := InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	wheel.pressed = true
	wheel.position = workspace.overview.get_global_rect().get_center()
	workspace.get_viewport().push_input(wheel, true)
	for frame in 250:
		await create_timer(0.025).timeout
		if workspace.project_mode:
			break
	check(workspace.project_mode and workspace.board_cards.size() == 3 and workspace.creator_sections.size() == 2 and workspace.overview.has_node("i_901"), "project board missed paginated non-personal issue or included PR")
	workspace.overview.zoom = 0.04
	await settle_layout()
	check(workspace.project_anchor.visible, "project overview has no readable outer anchor")
	for step in 20:
		workspace.overview.zoom = 0.5
		workspace._check_canvas_zoom()
	check(workspace.far_depth > 20 and workspace.overview.zoom == 1.0, "outer zoom stopped or collapsed canvas scale")
	workspace.project_anchor.pressed.emit()
	await settle_layout()
	for creator in ["writer", "未知创建人"]:
		var expected_count := "2 / 3 项" if creator == "writer" else "1 / 3 项"
		workspace.overview.zoom = 1.65
		workspace._open_creator_at(Vector2(-100000, -100000))
		check(workspace.board_views.current_tab == 1, "background zoom selected an owner")
		var region: GraphFrame = workspace.creator_sections.get(creator)
		if not is_instance_valid(region):
			check(false, "missing creator %s; sections=%s filter=%s tab=%d" % [creator, workspace.creator_sections.keys(), workspace.creator_filter.text, workspace.board_views.current_tab])
			quit(1)
			return
		var pointer: Vector2 = workspace.overview.size * 0.5
		workspace.overview.scroll_offset = (region.position_offset + Vector2(22, 22)) * workspace.overview.zoom - pointer
		await settle_layout()
		var hover_region := InputEventMouseMotion.new()
		hover_region.position = workspace.overview.get_global_transform_with_canvas() * pointer
		workspace.get_viewport().push_input(hover_region, true)
		var zoom_in := InputEventMouseButton.new()
		zoom_in.position = hover_region.position
		zoom_in.button_index = MOUSE_BUTTON_WHEEL_UP
		zoom_in.pressed = true
		workspace.get_viewport().push_input(zoom_in, true)
		await settle_layout()
		check(workspace.project_mode and workspace.issue_list.visible and workspace.creator_filter.text == creator and workspace.result_count.text == expected_count, "zoom missed creator %s got %s tab=%d zoom=%s scroll=%s pointer=%s region=%s anchor=%s" % [creator,workspace.creator_filter.text,workspace.board_views.current_tab,workspace.overview.zoom,workspace.overview.scroll_offset,pointer,region.position_offset if is_instance_valid(region) else Vector2.ZERO,workspace.zoom_anchor])
		workspace.creator_filter.select(0)
		workspace.board_views.current_tab = 1
		await settle_layout()
	await workspace._set_project(false)
	var resize_card = workspace.overview.get_node("i_5")
	var before_rect := Rect2(resize_card.position_offset, resize_card.size)
	workspace.overview.zoom = 1.0
	workspace.overview.scroll_offset = resize_card.position_offset - Vector2(40, 40)
	await settle_layout()
	var point: Vector2 = resize_card.get_global_transform_with_canvas() * Vector2(2, 10)
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = point
	var viewport: Viewport = workspace.get_viewport()
	var hover := InputEventMouseMotion.new()
	hover.position = point
	viewport.push_input(hover, true)
	viewport.push_input(press, true)
	var move := InputEventMouseMotion.new()
	move.button_mask = MOUSE_BUTTON_MASK_LEFT
	move.position = point - Vector2(24, 0)
	move.relative = Vector2(-24, 0)
	viewport.push_input(move, true)
	press.pressed = false
	press.position = move.position
	viewport.push_input(press, true)
	check(is_equal_approx(resize_card.size.x, before_rect.size.x + 24) and is_equal_approx(resize_card.position_offset.x, before_rect.position.x - 24), "left edge failed to preserve right edge")
	workspace._draw_board()
	check(is_equal_approx(workspace.overview.get_node("i_5").size.x, before_rect.size.x + 24), "redraw lost resized issue card")
	await settle_layout()
	resize_card = workspace.overview.get_node("i_5")
	point = resize_card.get_global_transform_with_canvas() * Vector2(resize_card.size.x - 2, 10)
	press.position = point
	press.pressed = true
	viewport.push_input(press, true)
	move.position = point - Vector2(12, 0)
	move.relative = Vector2(-12, 0)
	viewport.push_input(move, true)
	press.position = move.position
	press.pressed = false
	viewport.push_input(press, true)
	check(is_equal_approx(resize_card.size.x, before_rect.size.x + 12), "right edge failed to shrink card")
	var full_size: Vector2 = workspace.size
	workspace.size.x = 600 * workspace.get_theme_default_base_scale()
	workspace._adapt_layout()
	check(workspace.flow_split.vertical and workspace.details_panel.custom_minimum_size.x == 0, "narrow inspector did not stack")
	check(workspace.issue_list.columns == 3, "narrow list did not give the owner column space back to the title")
	workspace.size = full_size
	workspace._adapt_layout()
	state.plan = {"nodes":{},"edges":[]}
	state.context = {}
	workspace.host = self
	delay_detail = true
	workspace.overview.get_node("i_1/OpenIssue").pressed.emit()
	check(workspace.issue_link.uri == issues[0].url and "已完成" in workspace.work_status.text, "issue detail lost link or status")
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
	var entry: Dictionary = issues[1].duplicate(true)
	entry.merge({"number":83, "url":"https://github.com/fixture/board/issues/83", "status":"needs-decision", "analyzed":true, "decision":true, "pending_count":1,
		"node_states":{}, "questions":{"q":{"kind":"text", "prompt":"请选择验收平台"}}}, true)
	state.plan = {"nodes":{"requirement":{"kind":"text","title":"需求","value":"编辑器"},
		"q":{"kind":"question","title":"待确认","value":"请选择验收平台"}}, "edges":[]}
	entry.plan = state.plan
	state.context = {"questions":entry.questions,"answers":{},"states":{},"can_answer":true,"protected_nodes":["q"]}
	workspace.board.issues = [entry]
	workspace.fresh_progress = true
	await workspace._open_issue(entry)
	var card = graph.canvas.get_node("q")
	check(card.find_children("*","TextEdit",false,false).size() == 2, "real question must have prompt and answer together")
	state.context.answers.q = {"actor":"collaborator","value":"macOS"}
	state.context.states.q = "answered"
	entry.merge({"pending_count":0, "decision":false, "answered_count":1}, true)
	await workspace._refresh_open_states()
	card = graph.canvas.get_node("q")
	check(card.find_children("*","TextEdit",false,false).size() == 1, "external answer left a second input")
	check(card.find_children("*","Label",false,false).any(func(label): return "collaborator" in label.text and "macOS" in label.text), "receipt omitted answer or author")
	check(not "等待答复" in graph.canvas.get_node("wf-analysis").tooltip_text and "已收到答复" in workspace.work_status.text, "answered workflow still asks user to reply")
	entry.answered_count = 0
	check("工单负责人" in workspace._work_summary(entry, {}).text, "label-only Issue asks the user for input")
	workspace._show_board()
	workspace.board.issues = issues
	issues[4].decision = true
	issues[4].pending_count = 1
	state.plan = {"nodes":{"requirement":{"title":"需求", "kind":"text", "value":"选主题"}, "theme":{"title":"主题", "kind":"question", "value":"选主题"}}, "edges":[]}
	state.context = {"questions":{"theme":{"kind":"choice", "prompt":"选主题", "options":["青色","紫色"]}}, "answers":{}, "can_answer":true}
	workspace._draw_board()
	await workspace._locate_pending(5)
	var choice := graph.canvas.get_node_or_null("theme/AnswerInput") as OptionButton
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
		var personal: Dictionary = workspace.board.duplicate(true)
		var access_file = FileAccess.open(access_path,FileAccess.WRITE)
		access_file.store_string("overlap")
		access_file.close()
		var sync_dir: String = access_path.get_base_dir()
		workspace._set_project(true)
		await await_fixture_file(sync_dir.path_join("project-reading"))
		workspace.refresh()
		await await_fixture_file(sync_dir.path_join("personal-reading"))
		FileAccess.open(sync_dir.path_join("project-release"), FileAccess.WRITE).close()
		var deadline := Time.get_ticks_msec() + 8000
		while not workspace.project_mode and Time.get_ticks_msec() < deadline:
			await create_timer(0.025).timeout
		FileAccess.open(sync_dir.path_join("personal-release"), FileAccess.WRITE).close()
		await workspace.refresh()
		check(workspace.project_mode and workspace.board.get("issues", []).size() == 3, "late personal read overwrote the active project board")
		workspace.board_views.current_tab = 1
		var card_id: int = workspace.board_cards[0].get_instance_id()
		workspace.board.verified_at = "old"
		await workspace.refresh()
		check(workspace.board_cards[0].get_instance_id() == card_id and workspace.board.verified_at != "old", "timestamp-only refresh rebuilt the graph or missed the sync time")
		workspace.board_views.current_tab = 0
		var url: String = workspace.board.issues[0].url
		var row_id: int = workspace.issue_rows[url].get_instance_id()
		await workspace.refresh()
		check(workspace.issue_rows[url].get_instance_id() == row_id and is_same(workspace.issue_rows[url].get_metadata(0), workspace.board.issues[0]), "identical refresh replaced a list row or detached its issue dictionary")
		workspace.board.issues[0].title = "stale fixture"
		await workspace.refresh()
		check(workspace.issue_rows[url].get_instance_id() != row_id and workspace.issue_rows[url].get_text(1) != "stale fixture", "changed board missed a redraw")
		workspace.board_views.current_tab = 1
		await settle_layout()
		for query in ["P", "Pr", "#pr "]:
			workspace.search.text = query
			workspace.search.text_changed.emit(query)
			check(not workspace.board_layout_pending and workspace.result_count.text == "3 项", "unchanged search matches scheduled a graph layout")
		workspace.search.text = "#901"
		workspace.search.text_changed.emit(workspace.search.text)
		check(workspace.result_count.text == "1 / 3 项" and workspace.board_layout_pending, "search did not immediately update the visible graph")
		workspace.search.clear()
		workspace._filter_board()
		access_file = FileAccess.open(access_path,FileAccess.WRITE)
		access_file.store_string("offline")
		access_file.close()
		await workspace.refresh()
		check(workspace.offline and not workspace.project_mode and workspace.board == personal and workspace.actor.get("user_id") == "42", "transient network error lost the personal snapshot or exposed the project view")
		access_file = FileAccess.open(access_path,FileAccess.WRITE)
		access_file.store_string("member")
		access_file.close()
		await workspace.refresh()
		check(not workspace.offline and not workspace.project_mode and workspace.actor.get("user_id") == "42", "personal board did not recover after reconnect")
		access_file = FileAccess.open(access_path,FileAccess.WRITE)
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
