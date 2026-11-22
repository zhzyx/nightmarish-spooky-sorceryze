extends SceneTree
## Custom workflow template UI, persistence, expansion and offline execution acceptance.
var panel
var failures = 0
var checks: Array = []
var fixture_image = ""

func check(ok: bool, label: String) -> bool:
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed": ok, "label": label})
	if not ok: failures += 1
	return ok

func _initialize():
	run.call_deferred()

func settle():
	for i in 5: await process_frame

func wait_idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, "template execution finishes without blocking the editor")

func make_copy(id: String, source: String, position: Vector2) -> Dictionary:
	return {"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": source, "image_context": "", "text": "", "parameters": {"delay": 0.0, "fail": false}, "x": position.x, "y": position.y}

func add_instance(template_id: String) -> String:
	panel.context_position = Vector2(240 + panel.nodes.size() * 30, 160)
	panel.context_node_ids = []
	panel.context_connection = {}
	panel._remember_context()
	panel.create_context_node(panel.CUSTOM_TEMPLATE + ":" + template_id)
	return str(panel.nodes.back().id)

func run():
	root.size = Vector2i(1440, 1000)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = ProjectSettings.globalize_path("user://workflow-template-test-" + str(Time.get_ticks_usec()))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.python_edit.text = "python3"
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	fixture_image = ProjectSettings.globalize_path("res://fixtures/sample.png")
	panel.create_custom_template()
	await settle()
	var template_id = panel.active_template_id
	check(not template_id.is_empty() and panel.custom_templates.has(template_id), "create opens an independent custom template tab")
	check(panel.workflow_tabs.tab_count == 2 and panel.workflow_tabs.get_tab_title(0) == "制作 Mesh", "main Mesh workflow and template have separate tabs")
	check(panel.nodes.size() == 2 and panel.nodes.all(panel.WorkflowTemplate.is_fixed_node), "new template contains exactly the fixed input and output nodes")
	var input_node = panel.graph.get_node(panel.WorkflowTemplate.INPUT_ID) as GraphNode
	var output_node = panel.graph.get_node(panel.WorkflowTemplate.OUTPUT_ID) as GraphNode
	check(not input_node.is_slot_enabled_left(1) and input_node.is_slot_enabled_right(1) and output_node.is_slot_enabled_left(1) and not output_node.is_slot_enabled_right(1), "fixed boundary nodes expose only the correct external directions")
	panel.rename_active_template("图像清理流程")
	check(panel.template_name(template_id) == "图像清理流程" and panel.active_template_id == template_id and panel.workflow_tabs.get_tab_title(1) == "图像清理流程", "rename updates the tab without changing the stable template ID")
	panel.select_node(panel.WorkflowTemplate.INPUT_ID)
	panel.delete_node()
	check(panel.nodes.size() == 2 and panel.status.text.contains("不能删除"), "single delete cannot remove a fixed input node")
	panel.graph.delete_nodes_request.emit([StringName(panel.WorkflowTemplate.OUTPUT_ID)])
	check(panel.nodes.size() == 2 and panel.status.text.contains("不能删除"), "keyboard delete cannot remove a fixed output node")
	panel.context_node_ids = [panel.WorkflowTemplate.INPUT_ID]
	panel._remember_context()
	check(panel.duplicate_context_nodes().is_empty() and panel.nodes.size() == 2, "fixed boundary nodes cannot be duplicated")
	var internal = make_copy("inside", "", Vector2(330, 160))
	panel.nodes.append(internal)
	panel.edges = [
		{"from": panel.WorkflowTemplate.INPUT_ID, "to": "inside", "input": "source", "output": "result"},
		{"from": "inside", "to": panel.WorkflowTemplate.OUTPUT_ID, "input": "source", "output": "result"}
	]
	panel.rebuild()
	panel.switch_workflow_document("")
	await settle()
	check(panel.custom_templates[template_id].nodes.size() == 3 and panel.custom_templates[template_id].edges.size() == 2, "switching tabs captures template nodes and internal connections")
	panel.filter_node_picker("图像清理")
	var metadata: Array = []
	for index in panel.node_picker_list.item_count: metadata.append(panel.node_picker_list.get_item_metadata(index))
	check(metadata.has(panel.CUSTOM_TEMPLATE + ":" + template_id), "reusable template appears in the existing searchable node picker")
	panel.nodes = [make_copy("source", fixture_image, Vector2(40, 100)), make_copy("sink", "", Vector2(760, 100))]
	panel.edges = []
	panel.rebuild()
	var first = add_instance(template_id)
	var second = add_instance(template_id)
	panel.edges = [
		{"from": "source", "to": first, "input": "source", "output": "result"},
		{"from": "source", "to": second, "input": "source", "output": "result"},
		{"from": first, "to": "sink", "input": "source", "output": "result"}
	]
	panel.rebuild()
	var expanded = panel.execution_model(false)
	check(expanded.get("error", "").is_empty() and expanded.nodes.size() == 4, "two template instances expand into isolated executable nodes")
	check(not expanded.nodes.any(func(node): return node.get("type", "") in [panel.CUSTOM_TEMPLATE, panel.TEMPLATE_INPUT, panel.TEMPLATE_OUTPUT]), "executable graph contains neither template instances nor boundary nodes")
	check(expanded.nodes.any(func(node): return node.id == first + "__inside") and expanded.nodes.any(func(node): return node.id == second + "__inside"), "reused internal IDs are namespaced by each instance")
	check(panel.template_target_aliases.get(first, "") == first + "__inside" and panel.template_target_aliases.get(second, "") == second + "__inside", "each external template node maps to its own final output")
	var fingerprint = panel._cache_fingerprint(first)
	panel.custom_templates[template_id].name = "仅修改显示名"
	check(panel._cache_fingerprint(first) == fingerprint, "template display rename does not invalidate executable caches")
	panel.custom_templates[template_id].nodes.filter(func(node): return node.id == "inside")[0].parameters.delay = 0.01
	check(panel._cache_fingerprint(first) != fingerprint, "template content changes invalidate instance caches")
	panel.custom_templates[template_id].name = "图像清理流程"
	panel.select_node(first)
	panel.run_node_preview(first)
	await wait_idle()
	check(panel.current.get("state", "") == "succeeded", "template instance executes through the real offline executor")
	check(panel.preview_history.get(first, []).size() == 1 and panel.preview_history[first][0].node == first, "expanded output is recorded in the external template instance history")
	check(panel.preview_node == first and panel.preview_resource is ImageTexture, "template instance preview displays the internal final image")
	panel.path_edit.text = panel.state_dir.path_join("custom-template-workflow.json")
	panel.save_graph()
	var saved = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	check(saved is Dictionary and saved.get("custom_templates", []).size() == 1 and saved.custom_templates[0].id == template_id, "workflow serialization includes the reusable template definition")
	panel.open_graph()
	await settle()
	check(panel.active_template_id.is_empty() and panel.custom_templates.has(template_id) and panel.workflow_tabs.tab_count == 2, "reopen restores the main graph and template tab")
	check(panel.custom_templates[template_id].name == "图像清理流程" and panel.custom_templates[template_id].nodes.size() == 3, "reopen preserves template name and edited internal graph")
	check(panel.preview_history.get(first, []).size() == 1, "reopen restores the external template instance result")
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state", "") == "succeeded" and not panel.preview_history.get(second, []).is_empty(), "full workflow runs and previews a second instance of the same template")
	panel.open_custom_template(template_id)
	await settle()
	check(panel.nodes.size() == 3 and panel.nodes.filter(panel.WorkflowTemplate.is_fixed_node).size() == 2, "template tab restores both fixed boundaries and its internal node")
	check(not panel._template_can_insert(template_id), "a template cannot be inserted into itself")
	panel.nodes.filter(func(node): return node.id == "inside")[0].source = fixture_image
	panel.run_node_preview("inside")
	await wait_idle()
	check(panel.current.get("state", "") == "succeeded" and not panel.preview_history.get("inside", []).is_empty(), "internal nodes can run directly inside the template editor tab")
	var direct = panel.WorkflowTemplate.create_definition("direct", "直通模板")
	direct.edges = [{"from": panel.WorkflowTemplate.INPUT_ID, "to": panel.WorkflowTemplate.OUTPUT_ID, "input": "source", "output": "result"}]
	var rejected = panel.WorkflowTemplate.expand({"nodes": [{"id": "instance", "type": panel.CUSTOM_TEMPLATE, "template_id": "direct"}], "edges": []}, {"direct": direct})
	check(not rejected.error.is_empty() and rejected.error.contains("内部处理节点"), "direct input-to-output templates fail explicitly instead of creating a dangling execution target")
	await finish()

func finish():
	var receipt = {"ok": failures == 0, "checks": checks, "failures": failures, "inference": "offline copy provider; no AI model calls"}
	var path = OS.get_environment("AINATIVE_WORKFLOW_TEMPLATE_REPORT")
	if not path.is_empty():
		var output = FileAccess.open(path, FileAccess.WRITE)
		if output: output.store_string(JSON.stringify(receipt, "  ")); output.close()
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	print("AINATIVE_WORKFLOW_TEMPLATE failures=" + str(failures))
	quit(0 if failures == 0 else 1)
