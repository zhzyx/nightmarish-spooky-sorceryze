extends SceneTree
# Decode and resize reference images with Godot; no Python imaging dependency.

func _initialize():
	run.call_deferred()


func run():
	var args = OS.get_cmdline_user_args()
	if args.size() != 1:
		quit(2)
		return
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not config is Dictionary or not config.get("images") is Array:
		quit(2)
		return
	var prepared = []
	for item in config.images:
		var image = Image.load_from_file(str(item.input))
		if image == null or image.is_empty():
			printerr("Reference image decode failed")
			quit(1)
			return
		var width = image.get_width()
		var height = image.get_height()
		var scale = minf(1.0, 1024.0 / float(maxi(width, height)))
		if scale < 1.0:
			image.resize(maxi(1, roundi(width * scale)), maxi(1, roundi(height * scale)), Image.INTERPOLATE_LANCZOS)
		if image.save_png(str(item.output)) != OK:
			printerr("Reference image write failed")
			quit(1)
			return
		prepared.append({"path": item.output, "sha256": FileAccess.get_sha256(str(item.output))})
	var stream = FileAccess.open(str(config.report), FileAccess.WRITE)
	if stream == null:
		quit(1)
		return
	stream.store_string(JSON.stringify({"images": prepared}, "\t"))
	stream.close()
	quit()
