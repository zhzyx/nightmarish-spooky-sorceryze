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
	func open_daqian_chat(source, number, request, message, preview, selection, embedded) -> String:
		last = [source, number, request, message, preview, selection, embedded]
		return ""

func _initialize() -> void:
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
	panel._build_canvas_chat()
	panel._sync_canvas_scope()
	panel._load_canvas_models()
	panel.canvas_models.select(1)
	panel.canvas_message.text = "执行当前操作"
	panel._send_canvas_message()
	var turn := panel.canvas_turn.duplicate(true)
	var local_ok: bool = panel.chat.last[5].id == "second" and panel.chat.last[4] and "#42" in panel.chat.last[3]
	panel._finish_canvas_turn(turn, '{"route":"execute","text":"执行"}')
	var execute_ok: bool = panel.chat.last[0] == panel.current and panel.chat.last[1] == 42 and not panel.chat.last[4]
	panel._finish_canvas_turn(turn, '{"route":"project","text":"跨工单"}')
	var project_ok: bool = panel.canvas_turn.project and "全项目工单" in panel.chat.last[3]
	panel._finish_canvas_turn(panel.canvas_turn, '{"route":"requirement","text":"新的需求"}')
	var draft_ok: bool = panel.new_drafts == 1 and panel.published_form and panel.editor.draft.nodes.requirement.value == "新的需求"
	panel.current = ""
	panel._sync_canvas_scope()
	panel._finish_canvas_turn(turn, '{"route":"requirement","text":"旧回执"}')
	var stale_ok := panel.new_drafts == 1 and panel.canvas_log.text.is_empty()
	for id in Node.get_orphan_node_ids():
		if not original_orphans.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent():
				node.free()
	if not (local_ok and execute_ok and project_ok and draft_ok and stale_ok):
		push_error("Canvas chat routing regression")
		quit(1)
	else:
		print("DAQIAN_CANVAS_CHAT_OK")
		quit()
