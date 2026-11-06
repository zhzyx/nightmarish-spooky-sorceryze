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
	var issues := []
	for i in range(55):
		var url := "https://github.com/fixture/board/issues/" + str(i+1)
		issues.append({"number":i+1,"url":url,"title":"需求 " + str(i+1),"owners":["tester"],
			"status":"in-progress","closed":false,"request":"test","updated":"fixture","decision":i==50,
			"dependencies":[issues[i-1].url] if i>0 else [],"plan":{"nodes":{},"edges":[]}})
	workspace.board = {"repo":"fixture/board","issues":issues,"verified_at":"fixture"}
	workspace._show_board()
	check(workspace.overview.get_connection_list().size()==54,"historical dependency chain")
	workspace.search.text = "#50"
	workspace._filter_board()
	check(workspace.overview.get_node("i_50").visible and not workspace.overview.get_node("i_5").visible,"large board search")
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
