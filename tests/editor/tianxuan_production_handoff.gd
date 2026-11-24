extends SceneTree
## Synthetic local identity/specification only. No authentication or inference.

var checks: Array[String] = []
var panel: Node
var workspace: Node
var snapshot := {}
var commands := 0
var prepare: Callable
var clear_card: Callable


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, description: String) -> bool:
	if not ok:
		push_error(description)
		quit(1)
		return false
	checks.append(description)
	return true


func current(value: Dictionary) -> bool:
	return snapshot == value


func deliver() -> Dictionary:
	if workspace:
		return workspace.prepare_local_production()
	return panel.prepare_spec_handoff(snapshot, current)


func update_revision(revision: int, body: String = "写实猪，完整四肢与自然皮肤；不带骨骼。") -> void:
	snapshot.revision = revision
	snapshot.body = body
	if workspace:
		workspace.cache["conversation:private-handoff"].current.design = revision
		workspace.cache["conversation:private-handoff"].revisions = [{"stage": "design", "revision": revision, "confirmed_at": "fixture-confirmed", "title": snapshot.title, "body": body, "acceptance": snapshot.acceptance}]


func run() -> void:
	await process_frame
	await process_frame
	var source_mode := OS.get_environment("TX_HANDOFF_SOURCE") == "yes"
	snapshot = {"scope": "private-fixture-scope", "conversation": "private-handoff", "stage": "design", "revision": 1, "project": ProjectSettings.globalize_path("res://").trim_suffix("/"), "title": "写实猪模型", "body": "写实猪，完整四肢与自然皮肤；不带骨骼。", "acceptance": "GLB 可预览；真实视觉审核后交付。"}
	if source_mode:
		panel = load("res://addons/ainative/workbench.gd").new()
		panel.state_dir = ProjectSettings.globalize_path("user://private-handoff")
		root.add_child(panel)
		clear_card = panel.clear_spec_handoff
	else:
		workspace = EditorInterface.get_base_control().get_node("TianxuanWorkspaceController")
		if not check(workspace.has_meta("local_production_handoff") and workspace.has_meta("local_production_clear"), "compiled workspace owns production preparation and clear callables"):
			return
		# This private no-network fixture is deliberately not a real account login.
		workspace.session._identity = {"id": "private-fixture", "project": "private-fixture", "role": "editor"}
		workspace.active_conversation = "private-handoff"
		workspace.cache["conversation:private-handoff"] = {"id": "private-handoff", "title": snapshot.title, "turns": [], "current": {"design": 1}, "revisions": []}
		snapshot.scope = workspace.session.scope_key()
		update_revision(1)
		clear_card = workspace.get_meta("local_production_clear")
	var first := deliver()
	if not check(first.get("ok", false) and first.state == "prepared" and first.created, "confirmed specification creates only a prepared handoff"):
		print(first)
		return
	if not source_mode:
		panel = EditorInterface.get_base_control().find_child("AINativeWorkbench", true, false)
	if not check(panel != null and panel.spec_handoff.visible, "native MaLiang displays a separate pending specification card"):
		return
	panel.controller.command_started.connect(func(_command, _request): commands += 1)
	panel.text_edit.text = "保留原节点输入"
	if not check(panel.apply_fields(), "existing inspector fields are valid before handoff"):
		return
	var before: Dictionary = panel.serialized_workflow().duplicate(true)
	var runtime_before: Dictionary = panel.controller.runtime_snapshot().duplicate(true)
	var model_before: Dictionary = panel.service_draft().duplicate(true)
	var run_before: String = panel.run_id
	if not check(panel.spec_handoff._body.text.contains(snapshot.body) and panel.spec_handoff._status.text.contains("尚未运行"), "card shows the frozen requirements and truthful not-started state"):
		return
	var repeated := deliver()
	if not check(repeated.get("ok", false) and not repeated.created and repeated.handoff_id == first.handoff_id and panel.serialized_workflow() == before, "repeat prepare is persistent and does not alter the existing workflow"):
		return
	var changed := snapshot.duplicate(true)
	changed.body = "changed without a revision"
	var old := snapshot.duplicate(true)
	snapshot = changed
	if workspace: update_revision(1, changed.body)
	if not check(not deliver().get("ok", true), "same revision cannot silently bind different content"):
		return
	snapshot = old
	if workspace: update_revision(1)
	panel.controller.auto_step = true
	if not check(not panel.spec_handoff.add_node().get("ok", true) and panel.serialized_workflow() == before, "busy workflow refuses node creation without replacing current work"):
		return
	panel.controller.auto_step = false
	panel.active_template_id = "private-template-edit"
	if not check(not panel.spec_handoff.add_node().get("ok", true), "template editing refuses implicit changes to another workflow document"):
		return
	panel.active_template_id = ""
	update_revision(2)
	if not check(not panel.spec_handoff.add_node().get("ok", true) and panel.serialized_workflow() == before, "stale card revalidates the exact current confirmed revision before adding"):
		return
	var second := deliver()
	if not check(second.get("ok", false) and second.handoff_id != first.handoff_id, "new revision creates a distinct frozen handoff"):
		return
	var created: Dictionary = panel.spec_handoff.add_node()
	if not check(created.get("ok", false) and created.state == "node_created" and created.created, "explicit card action appends one text-to-mesh node"):
		return
	var after: Dictionary = panel.serialized_workflow()
	if not check(after.nodes.size() == before.nodes.size() + 1 and after.nodes.slice(0, before.nodes.size()) == before.nodes and after.edges == before.edges, "all existing nodes and connections are preserved"):
		print(JSON.stringify({"before": before, "after": after}))
		return
	var added: Dictionary = after.nodes.back()
	if not check(added.id == created.node_id and added.type == "text_to_mesh" and added.parameters.prompt.contains(snapshot.body) and added.parameters.prompt.contains(snapshot.acceptance) and added.source.is_empty() and added.image_context.is_empty(), "new node contains only the chosen frozen textual specification and normal mesh defaults"):
		return
	if not check(panel.service_draft() == model_before and panel.controller.runtime_snapshot() == runtime_before and panel.run_id == run_before and not panel.is_graph_busy() and commands == 0, "handoff preserves model configuration and starts no process or runtime job"):
		return
	var duplicate: Dictionary = panel.spec_handoff.add_node()
	if not check(duplicate.get("ok", false) and not duplicate.created and panel.nodes.size() == after.nodes.size(), "repeated create does not append a second node"):
		return
	clear_card.call()
	if not check(not panel.spec_handoff.visible and panel.spec_handoff._record.is_empty() and panel.spec_handoff._body.text.is_empty(), "identity cleanup hides and erases only the temporary card"):
		return
	var restored := deliver()
	if not check(restored.get("ok", false) and restored.state == "node_created" and not restored.created and panel.spec_handoff._add.disabled, "reopening reads the durable reservation and does not recreate a node"):
		return
	# A missing unsaved/deleted node is not silently regenerated on restore.
	panel.nodes = before.nodes.duplicate(true)
	panel.selected_id = ""
	panel.rebuild(false)
	clear_card.call()
	var missing := deliver()
	if not check(missing.get("ok", false) and missing.state == "node_created" and panel.nodes.size() == before.nodes.size() and panel.spec_handoff._add.disabled, "lost unsaved node remains explicitly reserved instead of automatic duplicate creation"):
		return
	update_revision(3)
	if not check(deliver().get("ok", false) and panel.spec_handoff._reserve_node().get("ok", false), "fault fixture stops after durable reservation and before graph mutation"):
		return
	clear_card.call()
	var interrupted := deliver()
	if not check(interrupted.get("ok", false) and interrupted.state == "node_reserved" and panel.spec_handoff._status.text.contains("尚未确认") and not panel.spec_handoff.add_node().get("ok", true) and panel.nodes.size() == before.nodes.size(), "reserved-only recovery never claims node creation or replays an uncertain append"):
		return
	update_revision(4)
	if not check(deliver().get("ok", false), "prepare terminal-write failure fixture"):
		return
	var lock: String = panel.spec_handoff._path + ".lock"
	var obstruct := func(_child): DirAccess.make_dir_absolute(lock)
	panel.graph.child_entered_tree.connect(obstruct, CONNECT_ONE_SHOT)
	var incomplete: Dictionary = panel.spec_handoff.add_node()
	DirAccess.remove_absolute(lock)
	if not check(incomplete.get("ok", false) and incomplete.created and incomplete.state == "node_reserved" and panel.nodes.size() == before.nodes.size() + 1 and panel.spec_handoff._status.text.contains("完成记录未能保存"), "terminal receipt failure truthfully records the appended in-memory node and durable unknown state"):
		return
	clear_card.call()
	if not check(deliver().state == "node_reserved" and not panel.spec_handoff.add_node().get("ok", true) and panel.nodes.size() == before.nodes.size() + 1, "failed terminal persistence cannot duplicate the node on reopen"):
		return
	var wrong := snapshot.duplicate(true)
	wrong.project = "/another-project"
	if not check(not panel.prepare_spec_handoff(wrong, func(_value): return true).get("ok", true), "handoff rejects a different local project even with a caller validator"):
		return
	if workspace:
		workspace.session._identity = {}
		if not check(not workspace.get_meta("local_production_handoff").call(snapshot).get("ok", true), "native host independently rejects an identity that no longer matches"):
			return
	if not check(commands == 0, "all preparation, rejection, and restore cases make zero provider calls"):
		return
	FileAccess.open(OS.get_environment("TX_REPORT"), FileAccess.WRITE).store_string(JSON.stringify({"ok": true, "checks": checks, "source_mode": source_mode, "provider_commands": commands}, "  "))
	if source_mode:
		panel.queue_free()
		await process_frame
	quit(0)
