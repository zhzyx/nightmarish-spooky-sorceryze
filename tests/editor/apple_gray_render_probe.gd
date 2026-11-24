extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	root.hide()
	var viewport := SubViewport.new()
	viewport.size = Vector2i(320, 200)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	for x in range(80):
		var stripe := ColorRect.new()
		stripe.position = Vector2(x * 4, 0)
		stripe.size = Vector2(4, 200)
		stripe.color = Color.WHITE if x % 2 else Color.BLACK
		viewport.add_child(stripe)
	var panel := PanelContainer.new()
	panel.position = Vector2(20, 20)
	panel.size = Vector2(280, 160)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.91, 0.91, 0.92)
	style.set_corner_radius_all(12)
	panel.add_theme_stylebox_override("panel", style)
	panel.add_theme_constant_override("background_blur", 3)
	viewport.add_child(panel)
	await process_frame
	RenderingServer.force_draw(false)
	await process_frame
	var image := viewport.get_texture().get_image()
	var output := OS.get_environment("APPLE_GRAY_RENDER_OUTPUT")
	image.save_png(output + "/glass.png")
	var low := 1.0
	var high := 0.0
	for x in range(40, 280):
		var value := image.get_pixel(x, 100).r
		low = minf(low, value)
		high = maxf(high, value)
	panel.add_theme_constant_override("background_blur", 0)
	await process_frame
	RenderingServer.force_draw(false)
	await process_frame
	var opaque := viewport.get_texture().get_image()
	opaque.save_png(output + "/opaque.png")
	var opaque_difference := absf(opaque.get_pixel(80, 100).r - opaque.get_pixel(84, 100).r)
	var failures: Array[String] = []
	if high - low < 0.005 or high - low > 0.16:
		failures.append("backdrop must be visible but blurred: " + str(high - low))
	if opaque_difference > 0.005:
		failures.append("opaque fallback still samples the backdrop")
	var timings := {}
	for radius in [0, 3]:
		panel.add_theme_constant_override("background_blur", radius)
		await process_frame
		var measured: Array[float] = []
		for frame in range(35):
			var start := Time.get_ticks_usec()
			RenderingServer.force_draw(false)
			RenderingServer.force_sync()
			if frame >= 5:
				measured.append((Time.get_ticks_usec() - start) / 1000.0)
		measured.sort()
		timings[str(radius)] = {"median_ms": measured[15], "p95_ms": measured[28], "frames": 30}
	# A later panel must see opaque drawing inserted after the first glass panel.
	var intervening := ColorRect.new()
	intervening.position = Vector2(40, 40)
	intervening.size = Vector2(240, 120)
	intervening.color = Color(1, 0, 0)
	viewport.add_child(intervening)
	var second := PanelContainer.new()
	second.position = Vector2(60, 60)
	second.size = Vector2(200, 80)
	second.add_theme_stylebox_override("panel", style)
	second.add_theme_constant_override("background_blur", 3)
	viewport.add_child(second)
	await process_frame
	RenderingServer.force_draw(false)
	RenderingServer.force_sync()
	var overlap := viewport.get_texture().get_image()
	overlap.save_png(output + "/overlapping-glass.png")
	var overlap_color := overlap.get_pixel(160, 100)
	if overlap_color.r - overlap_color.g < 0.15:
		failures.append("later glass panel sampled a stale backdrop: " + str(overlap_color))
	var report := {"failures": failures, "overlap_color": str(overlap_color), "backdrop_range": high-low, "opaque_difference": opaque_difference, "renderer": RenderingServer.get_current_rendering_method(), "synchronized_frame_timings": timings, "scope": "one 280x160 panel in a 320x200 offscreen viewport; not a full-editor benchmark"}
	var file := FileAccess.open(output + "/render.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report))
	print(JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
