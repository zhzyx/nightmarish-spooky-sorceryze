extends SceneTree


class Graph extends Control:
	var draft := {"nodes":{"requirement":{"value":"原文"}}}
	var baseline := {}
	var answers := {}
	var debug_models := {}
	var positions := {}
	var card_sizes := {}
	var context := {}
	var revision := ""
	var canvas := GraphEdit.new()


class Workspace extends "res://editor/docks/daqian/workspace.gd":
	var cache: String
	var fail_full_save := false
	func _write_cache(path: String, value: Dictionary) -> bool:
		return false if fail_full_save and path == cache else super(path, value)
	func _repo() -> String: return "fixture"
	func _private_path() -> String: return cache
	func _ready() -> void: pass
	func _exit_tree() -> void: pass


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var original_orphans := Node.get_orphan_node_ids()
	var w := Workspace.new()
	w.cache = OS.get_user_data_dir().path_join("draft-" + Crypto.new().generate_random_bytes(12).hex_encode())
	w.actor = {"user_id":"fixture"}
	w.picker_scope = w._repo()
	w.current = "draft_test"
	w.editor = Graph.new()
	w.notice = Label.new()
	w.add_child(w.notice)
	w.overview = GraphEdit.new()
	w.add_child(w.overview)
	w.add_child(w.editor)
	w.editor.add_child(w.editor.canvas)
	w._build_publish_dialog()
	w.category.add_item("development")
	w.publish_source = w.current
	w.save_timer = Timer.new()
	w.save_timer.one_shot = true
	w.save_timer.wait_time = 0.02
	w.save_timer.timeout.connect(w._flush_queued_save)
	w.add_child(w.save_timer)
	root.add_child(w)
	w.set_process(false)
	w.requirement_input.text = "原文"
	await process_frame
	w.saved.drafts = {"draft_second":{"graph":{"nodes":{"requirement":{"value":"第二份原文"}}}}}
	w._save()
	var initial := FileAccess.get_sha256(w.cache)
	var generation: String = w.saved.cache_generation
	var checkpoint := w._requirement_checkpoint_path(generation, w.current)
	var other_checkpoint := w._requirement_checkpoint_path(generation, "draft_second")
	var ok := true
	for i in 4:
		w.requirement_input.insert_text_at_caret("测试")
		await create_timer(0.06).timeout
		ok = ok and FileAccess.get_sha256(w.cache) == initial and FileAccess.file_exists(checkpoint)
	var latest := w.requirement_input.text
	w.current = "draft_second"
	w.publish_source = w.current
	w.requirement_input.text = "第二份修改"
	w._edit_requirement()
	await create_timer(0.06).timeout
	ok = ok and FileAccess.file_exists(checkpoint) and FileAccess.file_exists(other_checkpoint)
	# A fresh process reads the last full cache first and then restores the edit.
	w.saved = {}
	var file := FileAccess.open(w.cache, FileAccess.READ)
	w.saved = file.get_var(false)
	file.close()
	w._restore_requirement_text()
	ok = ok and w.saved.drafts.draft_test.graph.nodes.requirement.value == latest
	ok = ok and w.saved.drafts.draft_second.graph.nodes.requirement.value == "第二份修改"
	var prior := FileAccess.get_file_as_bytes(checkpoint)
	w.fail_full_save = true
	w._save()
	ok = ok and w.saved.cache_generation == generation and FileAccess.get_sha256(w.cache) == initial
	ok = ok and w.notice.text == "个人草稿保存失败"
	ok = ok and FileAccess.file_exists(checkpoint) and FileAccess.file_exists(other_checkpoint)
	w.fail_full_save = false
	w.saved.drafts.draft_test.graph.nodes.requirement.value = "旧的内存副本"
	w._save()
	ok = ok and not FileAccess.file_exists(checkpoint) and not FileAccess.file_exists(other_checkpoint)
	file = FileAccess.open(w.cache, FileAccess.READ)
	var merged: Dictionary = file.get_var(false)
	file.close()
	ok = ok and merged.drafts.draft_test.graph.nodes.requirement.value == latest
	# An old checkpoint left by a crash after rename must not overwrite this generation.
	DirAccess.make_dir_recursive_absolute(checkpoint.get_base_dir())
	file = FileAccess.open(checkpoint, FileAccess.WRITE)
	file.store_buffer(prior)
	file.close()
	w.saved.drafts.draft_test.graph.nodes.requirement.value = "新版本"
	w._restore_requirement_text()
	ok = ok and w.saved.drafts.draft_test.graph.nodes.requirement.value == "新版本"
	DirAccess.remove_absolute(checkpoint)
	DirAccess.remove_absolute(checkpoint.get_base_dir())
	DirAccess.remove_absolute(w.cache)
	w.free()
	for id in Node.get_orphan_node_ids():
		if not original_orphans.has(id) and is_instance_id_valid(id):
			var node := instance_from_id(id) as Node
			if node and not node.get_parent():
				node.free()
	if not ok:
		push_error("Requirement text autosave or checkpoint recovery failed")
		quit(1)
		return
	print("DAQIAN_REQUIREMENT_DRAFT_OK")
	quit()
