extends SceneTree

const SCENE := "res://preview.tscn"
const AMBIGUOUS := "https://github.com/old/studio/issues/783"

var fixtures: Array = JSON.parse_string(OS.get_environment("U14_MODELS"))
var sidebar: Node
var business: Node
var detail: Node
var spatial: Node
var preview: Node3D
var trace := []


func _initialize() -> void:
	_run.call_deferred()


func check(ok: bool, reason: String) -> bool:
	if not ok:
		printerr("U14: ", reason)
		quit(1)
	return ok


func wait_for(predicate: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 12000
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return predicate.call()


func button(parent: Node, label: String) -> Button:
	for control in parent.find_children("*", "Button", true, false):
		if control.text == label:
			return control
	return null


func select_model(row: Dictionary) -> void:
	var selection := EditorInterface.get_selection()
	selection.clear()
	selection.add_node(preview.get_node(row.side + "/Model"))
	spatial.selection_changed()


func select_issue(url: String) -> bool:
	for index in spatial.rows.item_count:
		if spatial.rendered_rows[index].url == url:
			spatial.rows.select(index)
			spatial.rows.item_selected.emit(index)
			return true
	return false


func bind_model(index: int) -> void:
	spatial.picker.select(index)
	button(spatial.mapping, "关联模型").pressed.emit()


func matched(row: Dictionary) -> bool:
	return sidebar.is_visible_in_tree() and not business.busy and detail.get_detail().get("id") == row.issue and business.location.get("issue_id") == row.issue and business.conversation.get("id") == row.chat and business.conversation.turns.size() == 1 and business.conversation.turns[0].id == row.turn and business.composer.is_visible_in_tree()


func _run() -> void:
	root.size = Vector2i(1600, 900)
	await create_timer(1.2).timeout
	sidebar = root.find_child("AIWorkbenchSidebar", true, false)
	detail = sidebar.find_child("WorkbenchIssueDetail", true, false)
	business = root.find_child("WorkbenchBusinessModules", true, false)
	var workspace := root.find_child("DaqianWorkspace", true, false)
	spatial = workspace.spatial_workbench
	if not check(await wait_for(func(): return business.managed_identity and not business.session.get_identity().is_empty()), "native identity unavailable"): return
	if sidebar.is_visible_in_tree():
		sidebar.close()
	EditorInterface.open_scene_from_path(SCENE)
	EditorInterface.set_main_screen_editor("3D")
	await create_timer(0.4).timeout
	preview = EditorInterface.get_edited_scene_root()
	var viewport := EditorInterface.get_editor_viewport_3d()
	var camera := viewport.get_camera_3d()
	if not check(preview.scene_file_path == SCENE and is_instance_valid(camera), "preview or editor camera unavailable"): return
	var projection := camera.global_transform
	var source_screen := root.find_child("AI Chat", true, false).get_parent() as TabContainer
	var board := []
	for row in fixtures:
		board.append({"url":row.url, "number":row.number, "title":row.title, "request":"fixture-" + row.side, "status":"planned", "workers":[]})
	board.append({"url":AMBIGUOUS, "number":783, "title":fixtures[0].title, "request":"ambiguous", "status":"planned", "workers":[]})
	workspace.actor = {"repo":"old/studio", "user_id":"fixture"}
	workspace.board = {"repo":"old/studio", "issues":board}
	workspace.offline = false
	workspace.fresh_progress = true
	spatial.toggle.button_pressed = true
	await create_timer(0.3).timeout
	button(spatial.actions, "关联与内容…").pressed.emit()
	for index in fixtures.size():
		var row: Dictionary = fixtures[index]
		select_model(row)
		if not check(spatial.rows.item_count == 0 and spatial.selection.key == "res://" + row.side + "/Model.tres", "same basename alias before binding"): return
		bind_model(index)
		if index == 0:
			bind_model(2)
		if not check(spatial.model_links().has(row.url), "explicit model binding failed"): return
	spatial.load_links()
	var drafts := {}
	for index in [0, 1, 0, 1]:
		var row: Dictionary = fixtures[index]
		select_model(row)
		if not check(select_issue(row.url), "saved model has no selected row"): return
		var source := button(spatial.actions, "工单详情" if index == 0 else "工单聊天")
		if not check(source.is_visible_in_tree(), "compact button hidden"): return
		source.pressed.emit()
		if not check(await wait_for(func(): return matched(row)), "wrong mapped issue: " + spatial.feedback.text + " / " + detail._status.text + " / " + business.feedback.text): return
		var label := business.find_child("WorkbenchReference", true, false) as Button
		var asset: String = spatial.selection.key
		var path: String = SCENE + "#" + row.side + "/Model"
		if not check(label.is_visible_in_tree() and path in label.text and asset in label.text and not "失效" in label.text and not fixtures[1-index].side in label.text, "wrong or stale model reference: " + label.text): return
		if not check(business.composer.text == drafts.get(row.url, ""), "draft leaked or lost: " + row.url): return
		business.composer.text = "未发送 · " + row.side
		drafts[row.url] = business.composer.text
		if trace.is_empty():
			sidebar.find_child("ExpandWorkbench", true, false).pressed.emit()
			await process_frame
			var restore := root.find_child("RestoreWorkbenchSidebar", true, false) as Button
			if not check(restore.is_visible_in_tree() and business.composer.text == drafts[row.url], "expanded draft lost"): return
			restore.pressed.emit()
			await process_frame
		sidebar.close()
		await process_frame
		var selected := EditorInterface.get_selection().get_selected_nodes()
		if not check(source_screen.get_current_tab_control().name == &"3D" and spatial.panel.is_visible_in_tree() and EditorInterface.get_edited_scene_root() == preview and EditorInterface.get_editor_viewport_3d() == viewport and viewport.get_camera_3d() == camera and camera.global_transform.is_equal_approx(projection) and selected == [preview.get_node(row.side + "/Model")], "return changed 3D preview, camera or selection"): return
		trace.append({"action":source.text, "asset":asset, "node":path, "issue":row.issue, "chat":row.chat, "draft":business.composer.text, "turn":row.turn, "references":label.text, "viewport":str(viewport.get_instance_id()), "camera":str(camera.get_instance_id()), "camera_transform":str(camera.global_transform)})
	# A draft edited before this compact entry keeps its deliberate lack of references.
	select_model(fixtures[1])
	if not check(select_issue(fixtures[1].url), "right association missing"): return
	button(spatial.actions, "工单聊天").pressed.emit()
	if not check(await wait_for(func(): return matched(fixtures[1])), "right chat not restored"): return
	business.find_child("WorkbenchReference", true, false).pressed.emit()
	business.composer.text = "手工草稿 · 保留空引用"
	drafts[fixtures[1].url] = business.composer.text
	sidebar.close()
	await process_frame
	select_model(fixtures[0])
	if not check(select_issue(fixtures[0].url), "left association missing"): return
	button(spatial.actions, "工单详情").pressed.emit()
	if not check(await wait_for(func(): return matched(fixtures[0])), "left chat not restored"): return
	sidebar.close()
	await process_frame
	select_model(fixtures[1])
	if not check(select_issue(fixtures[1].url), "right association missing on return"): return
	button(spatial.actions, "工单聊天").pressed.emit()
	if not check(await wait_for(func(): return matched(fixtures[1])) and business.composer.text == drafts[fixtures[1].url] and not business.find_child("WorkbenchReference", true, false).visible, "route overwrote the existing unreferenced draft"): return
	sidebar.close()
	await process_frame
	select_model(fixtures[0])
	if not check(select_issue(AMBIGUOUS), "second model association missing"): return
	button(spatial.actions, "工单详情").pressed.emit()
	if not check(await wait_for(func(): return detail._status.text == "当前项目没有唯一关联的天璇工单") and detail.get_detail().is_empty() and business.composer.text == drafts[fixtures[1].url], "ambiguous link guessed an issue or touched the previous draft"): return
	print("U14_NATIVE=", JSON.stringify({"routes":trace, "ambiguous":detail._status.text, "model_links":spatial.links, "returned_from_full_view":true, "unreferenced_draft":business.composer.text}))
	quit(0)
