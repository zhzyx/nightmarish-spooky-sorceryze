extends SceneTree

# Run with --headless --path <repository> --script tests/editor/daqian_canvas_chat.gd.
class Workspace extends "res://editor/docks/daqian/workspace.gd":
	var new_drafts := 0
	var published_form := false
	func _repo() -> String:
		return "/test"
	func _fresh_access() -> bool:
		return true
	func _board_command(_only: bool, _expected := "", _project := false) -> Dictionary:
		return {"board":{"user_id":"u", "repo_id":"r", "issues":[]}}
	func _new_requirement() -> void:
		new_drafts += 1
	func _save() -> void:
		pass
	func _open_publish() -> void:
		published_form = true
	func _mount_conversation(_binding: Dictionary, _next := "") -> void:
		pass

class Graph extends Control:
	var draft := {"nodes":{"requirement":{"value":"existing"}}}
	func draw_graph() -> void:
		pass

class Chat extends Control:
	var last := []
	func get_daqian_models() -> Dictionary:
		return {"backend":0, "current":"first", "options":[{"id":"second"}]}
	func open_daqian_chat(source, number, request, message, preview, selection, embedded, preview_receipt := "") -> String:
		last = [source, number, request, message, preview, selection, embedded, preview_receipt]
		return ""

func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var original_orphans := Node.get_orphan_node_ids()
	var panel := Workspace.new()
	panel.creator_filter = OptionButton.new()
	panel.editor = Graph.new()
	panel.chat = Chat.new()
	panel.overview = GraphEdit.new()
	panel.empty_state = CenterContainer.new()
	panel.apply_model = Button.new()
	panel.notice = Label.new()
	panel.actor = {"user_id":"u", "repo_id":"r"}
	panel.current = "https://github.com/test/project/issues/42"
	panel.board = {"issues":[{"url":panel.current, "number":42, "title":"Example", "request":"issue-42", "status":"open"}]}
	panel.canvas_script = preload("res://editor/docks/daqian/canvas_context.gd")
	panel._build_canvas_chat()
	panel._sync_canvas_scope()
	panel._load_canvas_models()
	panel.canvas_panel.canvas_models.select(1)
	var chat = panel.chat
	var canvas = panel.canvas_panel
	var issue: String = panel.current
	canvas.canvas_message.text = "执行当前操作"
	canvas.send_requested.emit()
	var source: String = chat.last[0]
	var first_receipt: String = chat.last[7]
	var local_ok: bool = chat.last[5].id == "second" and chat.last[4] and "#42" in chat.last[3]
	panel._preview_received(first_receipt, '{"route":"execute","text":"执行"}')
	await process_frame
	var execute_ok: bool = chat.last[0] == issue and chat.last[1] == 42 and not chat.last[4]
	canvas.canvas_message.text = "查看相关工单"
	canvas.send_requested.emit()
	local_ok = local_ok and chat.last[0] == source and chat.last[7] != first_receipt
	panel._preview_received(chat.last[7], '{"route":"project","text":"跨工单"}')
	await process_frame
	var project_ok: bool = "全项目工单" in chat.last[3]
	panel._preview_received(chat.last[7], '{"route":"requirement","text":"新的需求"}')
	await process_frame
	var draft_ok: bool = panel.new_drafts == 1 and panel.published_form and panel.editor.draft.nodes.requirement.value == "新的需求"
	canvas.canvas_message.text = "需要新工单吗"
	canvas.send_requested.emit()
	panel._preview_received(chat.last[7], '{"route":"project","text":"跨工单"}')
	await process_frame
	var stale_action: String = chat.last[7]
	canvas.canvas_message.text = "当前进度"
	canvas.send_requested.emit()
	var late_answer: String = chat.last[7]
	canvas.canvas_message.text = "工单草稿"
	panel.current = ""
	panel._sync_canvas_scope()
	panel._preview_received(stale_action, '{"route":"requirement","text":"旧回执"}')
	await process_frame
	var stale_ok: bool = panel.new_drafts == 1 and canvas.canvas_log.text.is_empty()
	panel.project_mode = true
	panel._sync_canvas_scope()
	var isolated: bool = panel.canvas_panel.canvas_models.get_selected_metadata() == "first"
	panel.canvas_panel.canvas_message.text = "项目草稿"
	panel.creator_filter.add_item("所有创建人")
	panel.creator_filter.add_item("alice")
	panel.creator_filter.select(1)
	panel._sync_canvas_scope()
	isolated = isolated and panel.canvas_panel.canvas_message.text.is_empty()
	panel._preview_received(late_answer, '{"route":"answer","text":"延迟回复"}')
	panel._preview_received(late_answer, '{"route":"answer","text":"重复回执"}')
	await process_frame
	isolated = isolated and panel.canvas_panel.canvas_log.text.is_empty()
	panel.current = issue
	panel._sync_canvas_scope()
	isolated = isolated and panel.canvas_panel.canvas_message.text == "工单草稿"
	isolated = isolated and "延迟回复" in panel.canvas_panel.canvas_log.text and "重复回执" not in panel.canvas_panel.canvas_log.text
	isolated = isolated and panel.canvas_panel.canvas_models.get_selected_metadata() == "second"
	for id in Node.get_orphan_node_ids():
		if not original_orphans.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent():
				node.free()
	if not (local_ok and execute_ok and project_ok and draft_ok and stale_ok and isolated):
		push_error("Canvas chat routing regression")
		quit(1)
	else:
		print("DAQIAN_CANVAS_CHAT_OK")
		quit()
