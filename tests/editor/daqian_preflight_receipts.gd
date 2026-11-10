extends SceneTree

class Workspace extends "res://editor/docks/daqian/workspace.gd":
	func _repo() -> String: return "/workspace"
	func _ready() -> void: pass
	var workflow_refreshes := 0
	func _sync_workflow(_redraw := true) -> void: workflow_refreshes += 1
	func _queue_save() -> void: pass
	func _exit_tree() -> void: pass

class ReboundWorkspace extends Workspace:
	signal continue_read
	func _legacy_failed_owner(_folder: String, _item: Dictionary, _request: String) -> String:
		await continue_read
		return "a".repeat(32)

class Chat extends Control:
	var looked_up := false
	func get_legacy_candidate_failure(_owner: String, _root: String, _issue: int) -> String:
		looked_up = true
		return "old account"

var failures := []
func check(ok: bool, reason: String) -> void:
	if not ok: failures.append(reason)
func _initialize() -> void: run.call_deferred()
func run() -> void:
	var original := Node.get_orphan_node_ids()
	var w := Workspace.new()
	root.add_child(w)
	w.set_process(false)
	w.actor = {"user_id":"8","repo_id":"9","repo":"fixture/repo"}
	w.fresh_progress = true
	var item := {"number":534,"url":"https://github.com/fixture/repo/issues/534","request":"daqian-direct-" + "a".repeat(20),"updated":"after-start","source_sha256":"v1","status":"in-progress"}
	var key := w._execution_key(item)
	w.saved.direct_started = {item.url:item.request}
	w.execution_turns["turn-1"] = {"root":"/workspace","actor":w.actor.duplicate(),"key":key}
	w._execution_finished({"token":"other"},"wrong",false)
	check(w.execution_turns.has("turn-1") and w._issue_action(item).kind == "view", "Unknown callback released a live turn or hid its conversation")
	w._execution_finished({"token":"turn-1"},"candidate_branch_changed",false)
	check(w._issue_action(item).kind == "resume" and w._work_summary(item,{}).state == "failed", "Bound preflight error still shown as waiting")
	w._execution_finished({"token":"turn-1"},"replayed",false)
	check("replayed" not in w._work_summary(item,{}).text, "Consumed callback was replayable")
	for field in ["request","source_sha256","url","number"]:
		var other := item.duplicate()
		other[field] = 999 if field == "number" else "other"
		check(w._work_summary(other,{}).state != "failed", "Failure leaked across " + field)
	w.actor.user_id = "other"
	check(w._work_summary(item,{}).state != "failed", "Failure leaked across actors")
	w.actor.user_id = "8"
	w.execution_turns["turn-2"] = {"root":"/workspace","actor":w.actor.duplicate(),"key":key}
	w._execution_finished({"token":"turn-2"},"",true)
	check(w._work_summary(item,{}).state != "failed", "A later successful turn retained the failure")
	w.board = {"issues":[item]}
	w.current = "https://github.com/fixture/repo/issues/999"
	var binding := {"source_ref":item.url, "source_sha256":"v1", "actor":"8", "request_ref":item.request}
	var before := w.workflow_refreshes
	w._chat_work_event("/workspace",binding,"worker","request","chat","running")
	check(w.chat_work[item.url].has("worker") and w.workflow_refreshes == before, "Background Issue refreshed the foreground workflow")
	w.current = "draft_source"
	w.saved.linked = {w.current:{"number":item.number,"request":"older-non-direct-id"}}
	w._chat_work_event("/workspace",binding,"worker","step","implement","running")
	check(w.workflow_refreshes == before + 1, "Linked draft missed a foreground progress event")
	w.current = item.url
	w._chat_work_event("/workspace",binding,"worker","request_end","chat","completed")
	check(w.chat_work[item.url].is_empty() and w.workflow_refreshes == before + 2, "Foreground Issue missed its terminal event")
	w._chat_work_event("/workspace",binding,"worker","request","chat","running")
	w.current = ""
	w.project_snapshot = w.board
	w.board = {"issues":[]}
	w._chat_work_event("/workspace",binding,"worker","request_end","chat","failed")
	check(w.chat_work[item.url].is_empty() and w._work_summary(item,{}).state == "failed", "Switching boards lost a background terminal receipt")
	var directory := OS.get_user_data_dir().path_join("failed-events-" + Crypto.new().generate_random_bytes(8).hex_encode())
	DirAccess.make_dir_recursive_absolute(directory)
	var event := {"kind":"request_end","occurred_at":"2026-01-01T12:00:01Z","request_id":item.request,
		"source_ref":item.url,"payload":{"status":"failed","binding":{"source_sha256":"v1","actor":"8","source_ref":item.url,
		"request_ref":item.request,"authority_ref":"godot-editor:user-chat:" + "a".repeat(32)}}}
	var failure_file := directory.path_join("godot-event-old.json")
	var file := FileAccess.open(failure_file,FileAccess.WRITE)
	file.store_string(JSON.stringify(event))
	file.close()
	check(await w._legacy_failed_owner(directory,item,item.request) == "a".repeat(32), "Matching legacy terminal was lost")
	for i in 64:
		file = FileAccess.open(directory.path_join("other-" + str(i)),FileAccess.WRITE)
		file.close()
	event.kind = "request"
	event.occurred_at = "2026-01-01T12:00:02Z"
	file = FileAccess.open(directory.path_join("godot-event-new.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(event))
	file.close()
	check((await w._legacy_failed_owner(directory,item,item.request)).is_empty(), "Partial event history resurrected an old failure")
	for name in DirAccess.get_files_at(directory):
		DirAccess.remove_absolute(directory.path_join(name))
	DirAccess.remove_absolute(directory)
	if Engine.is_editor_hint():
		var switched := ReboundWorkspace.new()
		var chat := Chat.new()
		switched.chat = chat
		switched.fresh_progress = true
		switched.actor = {"user_id":"8","repo":"fixture/repo"}
		switched._restore_execution_failure(item)
		switched.actor = {"user_id":"9","repo":"fixture/repo"}
		switched.continue_read.emit()
		check(not chat.looked_up and not switched.saved.has("execution_errors"), "Async legacy read crossed an account switch")
		switched.free()
		chat.free()
	w.free()
	for id in Node.get_orphan_node_ids():
		if not original.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent(): node.free()
	for message in failures: push_error(message)
	if failures.is_empty(): print("DAQIAN_PREFLIGHT_RECEIPTS_OK")
	quit(0 if failures.is_empty() else 1)
