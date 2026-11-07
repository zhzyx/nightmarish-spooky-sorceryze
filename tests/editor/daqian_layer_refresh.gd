extends SceneTree

class Workspace extends "res://editor/docks/daqian/workspace.gd":
	var calls := []
	var redraws := 0
	var workflows := 0
	var detail_reads := 0
	var reply := {}
	var hold := false
	signal release
	func _ready() -> void: pass
	func _exit_tree() -> void: pass
	func _repo() -> String: return "fixture"
	func _queue_save() -> void: pass
	func _draw_board() -> void: redraws += 1
	func _sync_workflow(_force := false) -> void: workflows += 1
	func _reveal_pending_operation() -> void: pass
	func _refresh_open_states() -> void: detail_reads += 1
	func _run_board_command(_access: bool, _user: String, project: bool, request: Dictionary) -> Dictionary:
		calls.append({"project":project, "request":request})
		if hold: await release
		return reply


var failures := []

func check(ok: bool, message: String) -> void:
	if not ok: failures.append(message)

func _initialize() -> void:
	run.call_deferred()

func row(number: int) -> Dictionary:
	return {"number":number, "url":"https://github.com/test/repo/issues/%d" % number,
		"request":"request-%d" % number, "updated":"rev", "delta_stamp":"initial", "title":"old"}

func packet(updates := [], removed := [], reconcile := []) -> Dictionary:
	return {"delta":{"repo":"test/repo","repo_id":"r","user_id":"u",
		"updates":updates,"removed":removed,"reconcile":reconcile}}

func run() -> void:
	var original := Node.get_orphan_node_ids()
	var w := Workspace.new()
	w.actor = {"repo":"test/repo","repo_id":"r","user_id":"u"}
	w.picker_scope = "fixture"
	w.fresh_progress = true
	w.board = {"repo":"test/repo", "repo_id":"r", "user_id":"u", "issues":[row(1),row(2)]}
	w.project_snapshot = {"repo":"test/repo","repo_id":"r","user_id":"u","issues":[row(1),row(2),row(3)]}
	w._note_layer_read(false,{"board":w.board, "delta_version":1})
	w._note_layer_read(true,{"board":w.project_snapshot, "delta_version":1})
	root.add_child(w)
	w.set_process(false)
	w._consume_layer_events(Time.get_ticks_msec())
	check(w.calls.is_empty(), "idle scheduler did work")
	w.current = w.board.issues[0].url
	for project in [false,true]:
		w._mark_layer_event("request-1",project)
		w._mark_layer_event("request-2",project)
		w._mark_layer_event("request-2",project)
	var started := Time.get_ticks_msec()
	w.reply = packet()
	w._consume_layer_events(started)
	check(w.calls.size() == 1 and w.calls[0].request.items.size() == 1 and w.calls[0].request.items[0].number == 1, "visible issue not isolated")
	check(w.redraws == 0 and w.workflows == 0 and w.detail_reads == 0, "unchanged receipt redrew or reread")
	w._consume_layer_events(started + 9000)
	check(w.calls.size() == 1, "same-scope hidden issue ran early")
	var change := row(2)
	change.title = "changed"
	change.delta_stamp = "new"
	w.reply = packet([change])
	w._consume_layer_events(started + 10_000)
	check(w.calls.size() == 2 and w.calls[1].request.items.size() == 1 and w.board.issues[1].title == "changed" and w.workflows == 0, "background row failed to merge quietly")
	w._consume_layer_events(started + 19_000)
	check(w.calls.size() == 2, "other board ran early")
	w._consume_layer_events(started + 20_000)
	check(w.calls.size() == 3 and w.calls[2].project and w.calls[2].request.items.size() == 2 and w.project_snapshot.issues[1].title == "changed" and w.redraws == 0, "other layer did not coalesce quietly")
	w.reply = packet()
	w._manual_refresh()
	check(w.calls.size() == 4 and w.calls.back().request.mode == "source" and w.calls.back().request.items.size() == 1, "manual detail refresh fetched whole board")
	w._mark_layer_event("request-1",false)
	w.reply = packet([row(1)])
	w.hold = true
	w._consume_layer_events(Time.get_ticks_msec())
	w.board.issues[0].updated = "newer"
	w.release.emit()
	w.hold = false
	check(w.board.issues[0].updated == "newer" and w.workflows == 0, "stale receipt overwrote changed row")
	w._mark_layer_event("request-1",false)
	w.reply = packet()
	w.hold = true
	w._consume_layer_events(Time.get_ticks_msec())
	w._note_layer_read(false,{"board":w.board,"delta_version":1})
	w.release.emit()
	w.hold = false
	check(w.layer_dirty[false].has(1), "event consumed across concurrent full read")
	w._consume_layer_events(Time.get_ticks_msec())
	# A cross-window source write upgrades an already queued pure progress event.
	w._mark_layer_event("request-1",false)
	w._mark_layer_event("source:request-1",false)
	check(w.layer_dirty[false][1].source, "typed source event failed to upgrade progress")
	w.hold = true
	w._consume_layer_events(Time.get_ticks_msec())
	w._mark_layer_event("request-1",false)
	w._note_layer_read(false,{"board":w.board,"delta_version":1})
	w.release.emit()
	w.hold = false
	check(w.layer_dirty[false][1].source, "full read downgraded in-flight source event")
	w._consume_layer_events(Time.get_ticks_msec())
	check(w.calls.back().request.mode == "source", "cross-window change only consulted the local snapshot")
	w._mark_layer_event("request-1",false)
	w.reply = packet()
	w.reply.delta.source_required = [1]
	w._consume_layer_events(Time.get_ticks_msec())
	check(w.layer_dirty[false][1].source, "legacy start receipt did not promote its issue")
	w.reply = packet()
	w._consume_layer_events(Time.get_ticks_msec())
	check(w.calls.back().request.mode == "source", "legacy start was never checked against its issue")
	w.reply = {}
	w._mark_layer_event("request-1",false)
	w._consume_layer_events(Time.get_ticks_msec())
	check(w.layer_dirty[false].get(1, {}).get("retried",false), "missing response lost event")
	w._consume_layer_events(Time.get_ticks_msec() + 15_000)
	check(not w.layer_dirty[false].has(1), "failure retries are unbounded")
	w._mark_layer_event("daqian-direct-00000000000000000001",false)
	check(w.layer_discovery.get(false,0) >= w.layer_full_after[false], "unknown event bypassed full refresh cooldown")
	w.free()
	for id in Node.get_orphan_node_ids():
		if not original.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent(): node.free()
	for message in failures: push_error(message)
	if failures.is_empty(): print("DAQIAN_LAYER_REFRESH_OK")
	quit(0 if failures.is_empty() else 1)
