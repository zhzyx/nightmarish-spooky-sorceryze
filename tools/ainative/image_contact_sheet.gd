extends SceneTree
# Pixel composition also works with the headless renderer: no blank Viewport
# screenshot, font dependency, input mutation, or third-party Python package.
const GLYPHS = {
	"R":["11110","10001","10001","11110","10100","10010","10001"],
	"E":["11111","10000","10000","11110","10000","10000","11111"],
	"F":["11111","10000","10000","11110","10000","10000","10000"],
	"0":["01110","10001","10011","10101","11001","10001","01110"],
	"1":["00100","01100","00100","00100","00100","00100","01110"],
	"2":["01110","10001","00001","00010","00100","01000","11111"],
	"3":["11110","00001","00001","01110","00001","00001","11110"],
	"4":["00010","00110","01010","10010","11111","00010","00010"],
	"5":["11111","10000","10000","11110","00001","00001","11110"],
	"6":["01110","10000","10000","11110","10001","10001","01110"],
	"7":["11111","00001","00010","00100","01000","01000","01000"],
	"8":["01110","10001","10001","01110","10001","10001","01110"],
	" ":["00000","00000","00000","00000","00000","00000","00000"],
}

func stamp(board: Image, text: String, origin: Vector2i):
	for index in text.length():
		var glyph: Array = GLYPHS.get(text.substr(index, 1), GLYPHS[" "])
		for y in 7:
			for x in 5:
				if glyph[y][x] == "1":
					board.fill_rect(Rect2i(origin + Vector2i(index * 24 + x * 4, y * 4), Vector2i(4, 4)), Color("f2f5fa"))

func _initialize():
	var arguments = OS.get_cmdline_user_args()
	if arguments.size() != 1:
		quit(2)
		return
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(arguments[0]))
	if not parsed is Dictionary or not parsed.get("inputs") is Array or parsed.inputs.size() < 2 or parsed.inputs.size() > 8:
		quit(2)
		return
	var output = str(parsed.get("output", ""))
	if not output.is_absolute_path() or output.get_extension().to_lower() != "png":
		quit(2)
		return
	var columns = 2 if parsed.inputs.size() <= 4 else 3
	var rows = ceili(float(parsed.inputs.size()) / columns)
	var board = Image.create_empty(columns * 512, rows * 560, false, Image.FORMAT_RGBA8)
	for index in parsed.inputs.size():
		var source = parsed.inputs[index]
		if not source is Dictionary or not str(source.get("path", "")).is_absolute_path() or not str(source.get("label", "")) is String:
			quit(2)
			return
		var image = Image.load_from_file(str(source.path))
		if image == null or image.is_empty() or image.get_width() > 8192 or image.get_height() > 8192:
			quit(2)
			return
		var origin = Vector2i((index % columns) * 512, (index / columns) * 560)
		board.fill_rect(Rect2i(origin, Vector2i(512, 560)), Color("20242b"))
		board.fill_rect(Rect2i(origin + Vector2i(8, 8), Vector2i(496, 544)), Color("303642"))
		stamp(board, "REF " + str(index + 1), origin + Vector2i(20, 10))
		image.convert(Image.FORMAT_RGBA8)
		var scale = minf(496.0 / image.get_width(), 496.0 / image.get_height())
		var size = Vector2i(maxi(1, roundi(image.get_width() * scale)), maxi(1, roundi(image.get_height() * scale)))
		image.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
		board.blit_rect(image, Rect2i(Vector2i.ZERO, size), origin + Vector2i(8, 48) + (Vector2i(496, 496) - size) / 2)
	if board.save_png(output) != OK:
		quit(3)
		return
	print("REFERENCE_BOARD: " + output)
	quit(0)
