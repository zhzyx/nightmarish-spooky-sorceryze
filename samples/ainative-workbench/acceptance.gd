extends SceneTree
var panel
var failures = 0
func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	if not ok: failures += 1
func wait_idle():
	var deadline = Time.get_ticks_msec() + 30000
	while (not panel.jobs.is_empty() or panel.auto_step) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step, "subprocess completed without blocking frame loop")
func _initialize():
	call_deferred("run")
func run():
	panel = load("res://addons/ainative/workbench.gd").new()
	root.size = Vector2i(1400, 900)
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.state_dir = ProjectSettings.globalize_path("user://test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("jobs.sqlite")
	var source = ProjectSettings.globalize_path("res://fixtures/sample.png")
	var mesh = ProjectSettings.globalize_path("res://fixtures/sample.gltf")
	var before = FileAccess.get_sha256(source)
	panel.source_edit.text = source
	panel.context_edit.text = source
	panel.text_edit.text = "Keep red and green reference"
	panel.params_edit.text = '{"delay":0.5,"fail":false}'
	panel.apply_fields()
	var first = panel.selected_id
	panel.add_node()
	var second = panel.selected_id
	panel.params_edit.text = '{"delay":0.5,"fail":false}'
	panel.apply_fields()
	panel.connect_nodes(first, 0, second, 0)
	panel.path_edit.text = panel.state_dir.path_join("graph.json")
	panel.save_graph()
	var original = FileAccess.get_file_as_string(panel.path_edit.text)
	check(not original.contains(source) and original.contains("source_snapshot"), "portable graph embeds content without source paths")
	panel.nodes = []; panel.edges = []
	panel.open_graph()
	check(JSON.parse_string(JSON.stringify(panel.model())) == JSON.parse_string(original), "save/reopen preserves nodes edges positions parameters text image context")
	var saved_graph = FileAccess.get_file_as_string(panel.path_edit.text)
	panel.source_edit.text = panel.state_dir.path_join("missing.png")
	panel.save_graph()
	check(FileAccess.get_file_as_string(panel.path_edit.text) == saved_graph, "bad source preserves previous workflow")
	panel.source_edit.text = ""
	panel.apply_fields()
	var valid_model = JSON.stringify(panel.model())
	var invalid = FileAccess.open(panel.path_edit.text, FileAccess.WRITE)
	invalid.store_string('{"format":1,"nodes":[],"edges":[{}]}')
	invalid.close()
	panel.open_graph()
	check(JSON.stringify(panel.model()) == valid_model, "malformed edge rejected without replacing graph")
	panel.path_edit.text = source
	panel.save_graph()
	check(FileAccess.get_sha256(source) == before, "save workflow refuses source PNG target")
	var ticks = panel.heartbeat
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.heartbeat > ticks + 5, "real Executor succeeds while editor heartbeat advances")
	panel.select_node(second)
	panel.request_preview()
	await wait_idle()
	check(panel.texture.texture != null, "real PNG decoded into image preview")
	panel.target_edit.text = panel.state_dir.path_join("image.tres")
	panel.review_publish()
	check(not FileAccess.file_exists(panel.target_edit.text), "review does not publish before human confirmation")
	panel.confirm_publish()
	panel.dialog.hide()
	await wait_idle()
	check(ResourceLoader.load(panel.target_edit.text, "", ResourceLoader.CACHE_MODE_IGNORE) is Texture2D, "published image .tres reloads")
	var published_hash = FileAccess.get_sha256(panel.target_edit.text)
	panel.review_publish(); panel.confirm_publish(); panel.dialog.hide()
	await wait_idle()
	check(FileAccess.get_sha256(panel.target_edit.text) == published_hash and panel.status.text.contains("失败"), "existing target cannot be overwritten")
	panel.nodes = []; panel.edges = []; panel.add_node()
	panel.source_edit.text = mesh
	panel.params_edit.text = '{"delay":0,"fail":false}'
	panel.start_run(); await wait_idle()
	panel.request_preview(); await wait_idle()
	check(panel.preview_scene != null and panel.preview_scene.find_children("*", "MeshInstance3D", true, false).size() > 0, "real glTF mesh decoded for viewport")
	var glb_document = GLTFDocument.new()
	var glb_state = GLTFState.new()
	check(glb_document.append_from_file("res://fixtures/sample.glb", glb_state) == OK, "real embedded GLB decodes")
	if "--capture" in OS.get_cmdline_user_args():
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://acceptance-preview.png"))
	panel.target_edit.text = panel.state_dir.path_join("mesh.tscn")
	panel.review_publish(); panel.confirm_publish(); panel.dialog.hide(); await wait_idle()
	var packed = ResourceLoader.load(panel.target_edit.text, "", ResourceLoader.CACHE_MODE_IGNORE)
	check(packed is PackedScene, "published mesh .tscn reloads")
	if packed is PackedScene:
		var instance = packed.instantiate()
		check(instance.find_children("*", "MeshInstance3D", true, false).size() > 0, "reloaded scene contains actual mesh")
		instance.free()
	panel.params_edit.text = '{"delay":0,"fail":true}'
	panel.start_run(); await wait_idle()
	check(panel.current.state == "failed", "true Executor failed status")
	panel.retry_node(); await wait_idle()
	check(panel.current.nodes[panel.selected_id].attempt == 1 and panel.current.state == "failed", "retry increments real attempt; persistent demo failure remains failed")
	panel.params_edit.text = '{"delay":2,"fail":false}'
	panel.start_run()
	await create_timer(0.5).timeout
	panel.cancel_run(); await wait_idle()
	panel.launch("status", {"run": panel.run_id}); await wait_idle()
	check(panel.current.state == "cancelled", "cancellation is durable despite late provider return")
	check(FileAccess.get_sha256(source) == before, "source bytes unchanged across success failure cancellation and collision")
	panel.start_run()
	panel.cancel_run()
	await wait_idle()
	check(panel.current.state == "cancelled", "immediate cancel during create applies to newly created run")
	var marker = panel.state_dir.path_join("lookup.txt")
	OS.set_environment("AINATIVE_LOOKUP_MARKER", marker)
	panel.factory_edit.text = "test_editor_host:reconcile_factory"
	panel.params_edit.text = '{"delay":0,"fail":false}'
	panel.text_edit.text = "unique reconcile fixture"
	panel.start_run(); await wait_idle()
	check(panel.current.state == "reconcile" and FileAccess.get_file_as_string(marker).replace("\r", "") == "submit\n", "unknown submit pauses without blind retry")
	panel.resume_run(); await wait_idle()
	check(panel.current.state == "reconcile" and FileAccess.get_file_as_string(marker).replace("\r", "") == "submit\nlookup\n", "explicit Resume performs exactly one lookup without another submission")
	print("AINATIVE_ACCEPTANCE failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
