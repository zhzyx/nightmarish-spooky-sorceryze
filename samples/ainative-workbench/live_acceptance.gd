extends SceneTree
# Replay actual Executor runs supplied by the host; this script never invents outputs.
var panel
var failures = 0

func check(ok: bool, message: String):
	print(("PASS " if ok else "FAIL ") + message)
	if not ok:
		failures += 1

func wait_idle():
	var deadline = Time.get_ticks_msec() + 60000
	while not panel.jobs.is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty(), "live host operation completed")

func _initialize():
	call_deferred("run")

func vertex_count(scene: Node) -> int:
	var meshes = scene.find_children("*", "MeshInstance3D", true, false)
	if scene is MeshInstance3D: meshes.append(scene)
	var vertices = 0
	for instance in meshes:
		for surface in range(instance.mesh.get_surface_count()):
			vertices += instance.mesh.surface_get_array_len(surface)
	return vertices

func run():
	var args = OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("Expected path to host live-runs.json")
		quit(2)
		return
	var records = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not records is Array or records.size() < 4:
		printerr("Expected four or more actual run receipts")
		quit(2)
		return
	panel = load("res://addons/ainative/workbench.gd").new()
	root.add_child(panel)
	await process_frame
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.factory_edit.text = "comfy_provider:factory"
	panel.state_dir = ProjectSettings.globalize_path("user://live-test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	var kinds = []
	var runs = []
	for record in records:
		check(not record.run_id in runs, "distinct actual run for each flow")
		runs.append(record.run_id)
		panel.db = record.db
		panel.run_id = record.run_id
		panel.selected_id = "generate"
		var before = FileAccess.get_sha256(record.file)
		panel.current = {}
		panel.launch("status", {"run": panel.run_id})
		await wait_idle()
		var valid_run = panel.current.get("state") == "succeeded" and panel.current.get("id") == record.run_id
		check(valid_run, record.kind + " actual Executor succeeded")
		if not valid_run: continue
		var node = panel.current.get("nodes", {}).get("generate", {})
		var valid_node = node.get("provider") == "comfy" and node.get("request", {}).get("node") == record.kind
		check(valid_node, "actual provider and node kind match receipt")
		if not valid_node: continue
		panel.nodes = [{"id": "generate", "type": record.kind, "version": node.request.version,
			"provider": node.provider, "source": "", "image_context": "", "text": "",
			"parameters": node.request.parameters, "x": 40, "y": 60}]
		panel.edges = []
		panel.rebuild()
		panel.select_node("generate")
		kinds.append(record.kind)
		var output_ref = node.get("job", {}).get("outputs", {}).get("result", {})
		var output_hash = ""
		for asset in panel.current.get("manifest", {}).get("artifacts", []):
			if asset.id == output_ref.get("id") and asset.revision == output_ref.get("revision"):
				output_hash = asset.get("payload", {}).get("content_sha256", "")
		check(not before.is_empty() and before == output_hash, "supplied artifact bytes match actual Executor output")
		if before.is_empty() or before != output_hash: continue
		panel.request_preview()
		await wait_idle()
		check(not panel.preview_token.is_empty() and panel.preview_run == record.run_id and panel.preview_node == "generate", "preview belongs to this actual run")
		var preview_vertices = 0
		if record.kind.ends_with("image"):
			check(panel.texture.texture != null, record.kind + " actual generated image preview")
			if panel.texture.texture != null:
				var expected = Image.load_from_file(record.file)
				var observed = panel.texture.texture.get_image()
				expected.convert(Image.FORMAT_RGBA8)
				observed.convert(Image.FORMAT_RGBA8)
				check(expected.get_data() == observed.get_data(), "preview pixels equal generated artifact")
			panel.target_edit.text = panel.state_dir.path_join(record.kind + ".tres")
		else:
			check(panel.preview_scene != null, record.kind + " actual generated Mesh preview")
			if panel.preview_scene != null:
				preview_vertices = vertex_count(panel.preview_scene)
				check(preview_vertices > 3, "generated mesh has nontrivial geometry: " + str(preview_vertices))
			panel.target_edit.text = panel.state_dir.path_join(record.kind + ".tscn")
		if args.size() > 1:
			await process_frame
			await RenderingServer.frame_post_draw
			var capture_path = args[1].path_join(record.kind + "-preview.png")
			check(root.get_texture().get_image().save_png(capture_path) == OK, "actual workbench preview captured")
		panel.review_publish()
		check(not FileAccess.file_exists(panel.target_edit.text), "publication awaits confirmation")
		panel.confirm_publish()
		panel.dialog.hide()
		await wait_idle()
		var resource = ResourceLoader.load(panel.target_edit.text, "", ResourceLoader.CACHE_MODE_IGNORE)
		check(resource is Texture2D if record.kind.ends_with("image") else resource is PackedScene, "published generated asset reloads")
		if resource is PackedScene:
			var instance = resource.instantiate()
			check(vertex_count(instance) == preview_vertices and preview_vertices > 3, "reloaded scene preserves generated geometry count")
			instance.free()
		check(FileAccess.get_sha256(record.file) == before, "original generated bytes preserved")
	for kind in ["text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh"]:
		check(kind in kinds, "real flow covered: " + kind)
	print("AINATIVE_LIVE_ACCEPTANCE failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
