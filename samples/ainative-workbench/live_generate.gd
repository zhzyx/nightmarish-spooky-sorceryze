extends SceneTree
# Real backend required. Arguments: reference PNG, new receipt JSON, optional screenshot.
var panel
var failures = 0

func check(ok: bool, message: String):
	print(("PASS " if ok else "FAIL ") + message)
	if not ok: failures += 1

func wait_idle():
	var deadline = Time.get_ticks_msec() + 900000
	while not panel.jobs.is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	check(panel.jobs.is_empty(), "real editor operation completed")

func _initialize():
	call_deferred("run")

func run():
	var args = OS.get_cmdline_user_args()
	if args.size() < 2 or FileAccess.file_exists(args[1]):
		printerr("Expected reference image and NEW receipt path")
		quit(2)
		return
	var original_hash = FileAccess.get_sha256(args[0])
	panel = load("res://addons/ainative/workbench.gd").new()
	root.add_child(panel)
	await process_frame
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "comfy_provider:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.state_dir = ProjectSettings.globalize_path("user://live-generate-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("executor.sqlite")
	panel.nodes = []; panel.edges = []
	panel.generator_choice.select(0)
	panel.add_generator()
	panel.params_edit.text = '{"prompt":"a friendly humanoid robot in blue armor","seed":42}'
	panel.context_edit.text = args[0]
	panel.text_edit.text = "front view, full body, plain white background"
	panel.path_edit.text = panel.state_dir.path_join("context-workflow.json")
	panel.save_graph()
	var portable = JSON.parse_string(FileAccess.get_file_as_string(panel.path_edit.text))
	check(portable is Dictionary, "real workflow saved")
	if not portable is Dictionary: quit(1); return
	check(portable.nodes[0].image_context == "" and portable.nodes[0].image_context_snapshot.content_sha256 == original_hash, "reference embedded with its actual byte hash")
	panel.open_graph()
	var ticks = panel.heartbeat
	panel.current = {}
	panel.start_run()
	await wait_idle()
	check(panel.current.get("state") == "succeeded" and panel.heartbeat > ticks + 5, "Godot Run generated through real provider while editor remained active")
	if panel.current.get("state") != "succeeded":
		printerr(panel.status.text)
		quit(1)
		return
	var node = panel.current.nodes[panel.selected_id]
	check(node.provider == "comfy" and node.request.node == "text_to_image" and node.request.parameters.seed == 42, "actual typed node accepted editor integer transport")
	var reference_found = false
	var text_found = false
	for context in node.request.context:
		if context.has("text"): text_found = context.text == panel.text_edit.text
		if context.has("artifact"):
			for asset in panel.current.manifest.artifacts:
				if asset.id == context.artifact.id and asset.revision == context.artifact.revision:
					reference_found = asset.payload.content_sha256 == original_hash
	check(reference_found and text_found, "actual generation retained both image and text context")
	var output_ref = node.job.outputs.result
	var output_hash = ""
	for asset in panel.current.manifest.artifacts:
		if asset.id == output_ref.id and asset.revision == output_ref.revision:
			output_hash = asset.payload.content_sha256
			var usage = asset.payload.provenance.usage
			check(usage.image_usage == "img2img_initial_latent" and usage.effective_prompt.contains(panel.text_edit.text), "provider used both contexts in actual inference")
	panel.request_preview()
	await wait_idle()
	check(panel.texture.texture != null and panel.preview_run == panel.run_id, "actual generated context result previewed")
	check(FileAccess.get_sha256(args[0]) == original_hash, "reference image bytes preserved")
	if args.size() > 2:
		await process_frame
		await RenderingServer.frame_post_draw
		check(root.get_texture().get_image().save_png(args[2]) == OK, "real context workflow captured")
	var receipt = {"run_id": panel.run_id, "node": panel.selected_id, "db": panel.db, "workflow": panel.path_edit.text, "reference_sha256": original_hash, "output_sha256": output_hash, "failures": failures}
	var stream = FileAccess.open(args[1], FileAccess.WRITE)
	stream.store_string(JSON.stringify(receipt, "\t"))
	stream.close()
	print("AINATIVE_LIVE_GENERATE failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
