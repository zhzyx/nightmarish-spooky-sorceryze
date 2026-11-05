@tool
extends SceneTree

var failures := []
var state := {}
var writes := 0


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, reason: String) -> void:
	if not value:
		failures.append(reason)
		push_error(reason)


func read_graph(_id):
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
	var dock = root.find_child("Daqian", true, false)
	if not dock:
		push_error("Missing native Daqian editor tab")
		quit(1)
		return
	dock.get_parent().current_tab = dock.get_parent().get_tab_idx_from_control(dock)
	await process_frame
	var workspace = dock.find_child("DaqianWorkspace", true, false)
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
	print("DAQIAN_GRAPH_TEST ", "passed" if failures.is_empty() else failures)
	quit(0 if failures.is_empty() else 1)
