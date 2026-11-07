extends SceneTree
# Real controls and the offline Executor; no desktop input or model inference.
var panel
var failures = 0
var checks: Array = []
var fixture_image = ""
var fixture_mesh = ""

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
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating, "context action finishes without blocking the editor")

func make_node(id: String, source: String, pos: Vector2) -> Dictionary:
	return {"id": id, "type": "copy", "version": "1", "provider": "local-copy", "source": source, "image_context": "", "text": "", "parameters": {"delay": 0.0, "fail": false}, "x": pos.x, "y": pos.y}

func reset_graph():
	panel.context_menu.hide()
	panel.preview_history.clear()
	panel.clear_preview()
	panel.current = {}
	panel.run_id = ""
	panel.preview_target = ""
	panel.nodes = [make_node("a", fixture_image, Vector2(50, 90)), make_node("b", "", Vector2(430, 90)), make_node("c", fixture_mesh, Vector2(50, 340))]
	panel.edges = [{"from": "a", "to": "b", "input": "source", "output": "result"}]
	panel.graph.zoom = 1.0
	panel.graph.scroll_offset = Vector2.ZERO
	panel.rebuild()
	panel.select_node("a")

func point_on_node(id: String) -> Vector2:
	var node = panel.graph.get_node(id)
	return node.position + Vector2(35, 35) * panel.graph.zoom

func popup_at(point: Vector2):
	panel.context_menu.hide()
	panel.graph.popup_request.emit(point)

func menu_index(text: String) -> int:
	for i in panel.context_menu.item_count:
		if panel.context_menu.get_item_text(i) == text: return i
	return -1

func menu_has(text: String) -> bool:
	return menu_index(text) >= 0

func activate(text: String) -> bool:
	var index = menu_index(text)
	if not check(index >= 0, "context action is discoverable: " + text): return false
	if not check(not panel.context_menu.is_item_disabled(index), "context action is enabled: " + text): return false
	var id = panel.context_menu.get_item_id(index)
	panel.context_menu.hide()
	panel.context_menu.id_pressed.emit(id)
	return true

func viewport_click(point: Vector2, mouse_button: int):
	var motion = InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	root.push_input(motion, true)
	var click = InputEventMouseButton.new()
	click.button_index = mouse_button
	click.position = point
	click.global_position = point
	click.pressed = true
	root.push_input(click, true)
	await process_frame
	click = click.duplicate()
	click.pressed = false
	root.push_input(click, true)
	await process_frame

func selected_ids() -> Array:
	var result: Array = []
	for node in panel.graph.get_children():
		if node is GraphNode and node.selected: result.append(str(node.name))
	result.sort()
	return result

func select_many(ids: Array):
	for node in panel.graph.get_children():
		if node is GraphNode: node.selected = str(node.name) in ids

func run():
	root.size = Vector2i(1440, 1000)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	panel.state_dir = ProjectSettings.globalize_path("user://context-menu-test-" + str(Time.get_ticks_usec()))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	fixture_image = ProjectSettings.globalize_path("res://fixtures/sample.png")
	fixture_mesh = ProjectSettings.globalize_path("res://fixtures/sample.glb")
	var image_hash = FileAccess.get_sha256(fixture_image)
	var mesh_hash = FileAccess.get_sha256(fixture_mesh)
	if not check(panel.get("context_menu") is PopupMenu and panel.has_method("show_context_menu"), "workbench exposes its context menu controls"):
		await finish()
		return
	reset_graph()
	await settle()
	var toolbar_labels: Array = []
	for child in panel.native_sections.bar.get_children():
		if child is Button and child.visible: toolbar_labels.append(child.text)
	check(not toolbar_labels.has("+ 离线复制节点") and not toolbar_labels.has("+ 生成节点") and not toolbar_labels.has("删除选中节点") and not toolbar_labels.has("重试选中节点"), "object editing buttons are removed from the visible toolbar")
	check(toolbar_labels.size() <= 5 and not panel.path_edit.is_visible_in_tree() and not panel.generator_choice.is_visible_in_tree(), "toolbar remains compact with workflow path and node type picker moved out")
	var original_serial = panel.serial
	popup_at(Vector2(panel.graph.size.x - 30, panel.graph.size.y - 30))
	check(menu_has("添加节点…") and not menu_has("运行并预览"), "blank canvas offers creation rather than stale selected-node actions")
	check(panel.serial == original_serial and panel.jobs.is_empty(), "opening a menu never starts inference")
	if activate("添加节点…"):
		await settle()
		check(panel.node_picker.visible, "blank-canvas action opens the searchable node picker")
		panel.node_picker_search.text = "网格"
		panel.filter_node_picker("网格")
		var kinds: Array = []
		for i in panel.node_picker_list.item_count: kinds.append(panel.node_picker_list.get_item_metadata(i))
		check(kinds.has("text_to_mesh") and kinds.has("image_to_mesh") and not kinds.has("text_to_image"), "node search filters generation types by their Chinese names")
		panel.node_picker.hide()
	# Node creation must use the canvas coordinate under a zoomed/scrolled click.
	panel.context_menu.hide()
	panel.graph.zoom = 1.5
	panel.graph.scroll_offset = Vector2(140, 90)
	await settle()
	var create_position = Vector2(220, 260)
	popup_at(create_position)
	var actual_scroll = panel.graph.scroll_offset
	var expected_position = (create_position + actual_scroll) / panel.graph.zoom
	var before_count = panel.nodes.size()
	panel.create_context_node("text_to_mesh")
	await settle()
	var created: Dictionary = panel.nodes.back()
	check(panel.nodes.size() == before_count + 1 and created.type == "text_to_mesh", "right-click creation preserves the selected machine node kind")
	check(Vector2(created.x, created.y).distance_to(expected_position) < 1.0, "created node is placed at the clicked canvas coordinate after zoom and scroll")
	reset_graph()
	await settle()
	select_many(["a"])
	panel.select_node("a")
	panel.text_edit.text = "pending inspector text before switching targets"
	popup_at(point_on_node("c"))
	check(panel.nodes[0].text == "pending inspector text before switching targets", "switching right-click targets retains pending inspector edits")
	check(panel.context_node_ids == ["c"] and panel.selected_id == "c", "right-click targets the node under the pointer instead of the previous inspector selection")
	check(menu_has("运行并预览") and menu_has("编辑提示词与参数") and menu_has("复制节点") and menu_has("删除节点"), "node menu contains the primary editing and execution actions")
	if activate("编辑提示词与参数"):
		await settle()
		check(panel.text_edit.has_focus() or panel.params_edit.has_focus(), "edit action focuses the node's detailed fields")
	# Preserve selection and deep-copy fields plus only the selected internal links.
	reset_graph()
	await settle()
	panel.nodes[0]["source_snapshot"] = {"content_base64": Marshalls.raw_to_base64(FileAccess.get_file_as_bytes(fixture_image)), "content_sha256": image_hash, "extension": ".png"}
	select_many(["a", "b"])
	popup_at(point_on_node("a"))
	check(selected_ids() == ["a", "b"] and panel.context_node_ids.size() == 2, "right-click inside a selected set preserves the multi-selection")
	check(menu_has("复制选中节点") and menu_has("删除选中节点") and not menu_has("运行并预览"), "multi-selection offers valid batch edits without an ambiguous batch run")
	if activate("复制选中节点"):
		await settle()
		var clones = panel.nodes.filter(func(n): return n.id not in ["a", "b", "c"])
		check(clones.size() == 2, "batch copy creates one distinct node for each selected node")
		var clone_ids: Array = []
		for clone in clones: clone_ids.append(clone.id)
		var copied_edges = panel.edges.filter(func(e): return e.from in clone_ids and e.to in clone_ids)
		check(copied_edges.size() == 1 and panel.edges.size() == 2, "batch copy remaps the selected internal connection")
		var source_clones = clones.filter(func(n): return n.has("source_snapshot"))
		if check(source_clones.size() == 1, "embedded source snapshot is retained in the copied node"):
			source_clones[0].parameters.delay = 3
			source_clones[0].source_snapshot.extension = ".modified"
			check(panel.nodes[0].parameters.delay == 0.0 and panel.nodes[0].source_snapshot.extension == ".png", "copied parameters and embedded snapshots do not alias the originals")
		select_many(clone_ids)
		popup_at(point_on_node(clone_ids[0]))
		if activate("删除选中节点"):
			check(panel.nodes.size() == 3 and panel.edges.size() == 1, "batch delete removes copied nodes and their incident connection only")
	reset_graph()
	await settle()
	var from_node = panel.graph.get_node("a")
	var to_node = panel.graph.get_node("b")
	var start = from_node.position + from_node.get_output_port_position(0) * panel.graph.zoom
	var end = to_node.position + to_node.get_input_port_position(0) * panel.graph.zoom
	var line: PackedVector2Array = panel.graph.get_connection_line(start, end)
	var edge_point = line[0].lerp(line[line.size() - 1], 0.5)
	popup_at(edge_point)
	check(not panel.context_connection.is_empty() and menu_has("断开连接"), "right-click on a rendered connection selects its disconnect action")
	if activate("断开连接"):
		check(panel.edges.is_empty() and panel.nodes.size() == 3, "connection action removes the selected edge without deleting nodes")
	# Use real viewport dispatch over the retained fallback button, whose BaseButton
	# mouse filtering must not swallow the primary right-click interaction.
	reset_graph()
	await settle()
	var run_button: Button
	for child in panel.graph.get_node("a").find_children("*", "Button", true, false):
		if child.text == "运行并预览": run_button = child
	if check(run_button != null, "node retains a discoverable run fallback"):
		var button_point = run_button.get_global_transform() * (run_button.size * 0.5)
		var serial_before_pointer = panel.serial
		await viewport_click(button_point, MOUSE_BUTTON_RIGHT)
		check(panel.context_menu.visible and panel.context_node_ids == ["a"], "real viewport right-click over the node run button opens its context menu")
		check(panel.serial == serial_before_pointer and panel.jobs.is_empty(), "right-clicking the run fallback does not activate generation")
		panel.context_menu.hide()
	# Disabled item reasons and stale context must be enforced in the action handler too.
	reset_graph()
	await settle()
	panel.nodes[0].source = ""
	panel.select_node("a")
	popup_at(point_on_node("a"))
	var run_index = menu_index("运行并预览")
	check(run_index >= 0 and panel.context_menu.is_item_disabled(run_index) and not panel.context_menu.get_item_tooltip(run_index).is_empty(), "missing required input disables execution with a visible explanation")
	reset_graph()
	await settle()
	panel.nodes[0].type = "text_to_image"
	panel.nodes[0].provider = "comfy"
	panel.nodes[0].source = ""
	panel.nodes[0].parameters = {"prompt": "", "seed": 1}
	panel.nodes[0].text = "a valid instruction supplied through node context"
	panel.select_node("a")
	popup_at(point_on_node("a"))
	run_index = menu_index("运行并预览")
	check(run_index >= 0 and not panel.context_menu.is_item_disabled(run_index), "generation accepts the effective prompt from node instructions without a parameter prompt")
	panel.nodes[0].text = ""
	panel.select_node("a")
	popup_at(point_on_node("a"))
	run_index = menu_index("运行并预览")
	check(run_index >= 0 and panel.context_menu.is_item_disabled(run_index), "text generation without parameter or instruction prompt remains disabled")
	panel.nodes[0].type = "image_to_mesh"
	panel.nodes[0].source = fixture_image
	panel.nodes[0].text = ""
	panel.select_node("a")
	popup_at(point_on_node("a"))
	run_index = menu_index("运行并预览")
	check(run_index >= 0 and not panel.context_menu.is_item_disabled(run_index), "image-to-mesh permits a source image without a text prompt")
	reset_graph()
	await settle()
	panel.creating = true
	popup_at(point_on_node("a"))
	run_index = menu_index("运行并预览")
	var delete_index = menu_index("删除节点")
	check(run_index >= 0 and panel.context_menu.is_item_disabled(run_index) and delete_index >= 0 and panel.context_menu.is_item_disabled(delete_index), "busy nodes disable duplicate execution and destructive edits")
	panel.creating = false
	panel.context_menu.hide()
	popup_at(point_on_node("a"))
	var stale_count = panel.nodes.size()
	var stale_delete_id = panel.context_menu.get_item_id(menu_index("删除节点"))
	panel.nodes[0].text = "changed after the menu opened"
	panel.context_menu.id_pressed.emit(stale_delete_id)
	check(panel.nodes.size() == stale_count, "an action from a stale menu cannot delete a changed model")
	reset_graph()
	await settle()
	panel.path_edit.text = panel.state_dir.path_join("same-id-workflow.json")
	panel.save_graph()
	panel.open_graph()
	await settle()
	popup_at(point_on_node("a"))
	stale_delete_id = panel.context_menu.get_item_id(menu_index("删除节点"))
	panel.open_graph()
	panel.context_menu.id_pressed.emit(stale_delete_id)
	check(panel.nodes.size() == 3 and panel.nodes.any(func(n): return n.id == "a"), "reopening an identical workflow invalidates old menu actions even when node IDs are reused")
	# Drive run/preview and history through the actual PopupMenu signal.
	reset_graph()
	await settle()
	popup_at(point_on_node("a"))
	if activate("运行并预览"):
		await wait_idle()
		check(panel.preview_node == "a" and panel.preview_resource is ImageTexture, "node menu automatically previews the real decoded image")
		popup_at(point_on_node("a"))
		var preview_index = menu_index("查看已有结果")
		check(preview_index >= 0 and not panel.context_menu.is_item_disabled(preview_index) and menu_has("预览历史"), "successful node enables existing-result and history actions")
		var history_index = menu_index("预览历史")
		if history_index >= 0 and not panel.context_menu.is_item_disabled(history_index):
			panel.context_history_menu.id_pressed.emit(0)
			panel.context_menu.hide()
			await settle()
			check(panel.preview_node == "a" and panel.preview_history.get("a", []).size() == 1, "history submenu restores the correct node's prior result")
		panel.nodes[0].source = fixture_mesh
		panel.select_node("a")
		popup_at(point_on_node("a"))
		if activate("运行并预览"):
			await wait_idle()
			check(panel.preview_node == "a" and panel.preview_scene != null and panel.preview_history.a.size() == 2, "right-click rerun previews a real mesh while retaining the previous image")
	# A failed node exposes retry while a normal pending node does not.
	panel.params_edit.text = '{"delay":0,"fail":true}'
	panel.text_edit.text = "failed-node-menu-test"
	panel.apply_fields()
	popup_at(point_on_node("a"))
	if activate("运行并预览"):
		await wait_idle()
		popup_at(point_on_node("a"))
		var retry_index = menu_index("重试节点")
		check(panel.current.get("state") == "failed" and retry_index >= 0 and not panel.context_menu.is_item_disabled(retry_index), "confirmed provider failure enables node retry")
		if activate("重试节点"):
			await wait_idle()
			check(panel.current.nodes.a.attempt == 1, "retry menu item invokes the durable executor retry path")
	panel.context_menu.hide()
	# Current keyboard/context pointer listeners must route to the same menu.
	reset_graph()
	await settle()
	var ctrl_click = InputEventMouseButton.new()
	ctrl_click.button_index = MOUSE_BUTTON_LEFT
	ctrl_click.ctrl_pressed = true
	ctrl_click.pressed = true
	ctrl_click.position = point_on_node("a")
	panel.graph.gui_input.emit(ctrl_click)
	check(panel.context_menu.visible and panel.context_node_ids == ["a"], "Control-click opens the node context menu on macOS")
	panel.context_menu.hide()
	var context_key = InputEventKey.new()
	context_key.keycode = KEY_F10
	context_key.shift_pressed = true
	context_key.pressed = true
	panel.graph.gui_input.emit(context_key)
	check(panel.context_menu.visible, "Shift-F10 provides a keyboard context-menu entry point")
	panel.context_menu.hide()
	select_many(["c"])
	var keyboard_copy_count = panel.nodes.size()
	panel.graph.duplicate_nodes_request.emit()
	check(panel.nodes.size() == keyboard_copy_count + 1, "GraphEdit duplicate shortcut uses the same contextual copy implementation")
	var keyboard_clone = panel.nodes.back().id
	panel.graph.delete_nodes_request.emit([StringName(keyboard_clone)])
	check(panel.nodes.size() == keyboard_copy_count, "GraphEdit delete shortcut removes the requested node using contextual safeguards")
	# Position clamping is measured against the actual usable popup parent rectangle.
	for window_size in [Vector2i(1100, 800), Vector2i(1440, 1000)]:
		root.size = window_size
		await settle()
		popup_at(panel.graph.size - Vector2(2, 2))
		await settle()
		var menu_rect = Rect2i(panel.context_menu.position, panel.context_menu.size)
		var window_rect = Rect2i(root.position, root.size)
		check(window_rect.encloses(menu_rect), "context menu remains inside the window at size " + str(window_size))
		panel.context_menu.hide()
		check(panel.graph.size.y > 300 and panel.native_sections.advanced.size_flags_vertical & Control.SIZE_EXPAND_FILL, "context menus preserve the canvas vertical expansion at size " + str(window_size))
	check(FileAccess.get_sha256(fixture_image) == image_hash and FileAccess.get_sha256(fixture_mesh) == mesh_hash, "context editing and preview preserve source file bytes")
	await finish()

func finish():
	var receipt = {"ok": failures == 0, "checks": checks, "failures": failures, "inference": "offline copy provider; no AI model calls"}
	var path = OS.get_environment("AINATIVE_CONTEXT_MENU_REPORT")
	if not path.is_empty():
		var output = FileAccess.open(path, FileAccess.WRITE)
		if output: output.store_string(JSON.stringify(receipt, "  ")); output.close()
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	print("AINATIVE_CONTEXT_MENU failures=" + str(failures))
	quit(0 if failures == 0 else 1)
