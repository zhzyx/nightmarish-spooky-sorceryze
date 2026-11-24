@tool
extends SceneTree

var failures: Array[String] = []
var samples: Array[Dictionary] = []

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await create_timer(1.0).timeout
	var base := EditorInterface.get_base_control()
	var scale := float(OS.get_environment("APPLE_GRAY_SCALE"))
	var host := PanelContainer.new()
	host.theme = base.theme
	base.add_child(host)
	var rows := VBoxContainer.new()
	host.add_child(rows)
	var input := LineEdit.new()
	input.placeholder_text = "搜索场景、资源与设置 Search"
	input.text = "中文输入与长路径 C:/Workspace/Scenes/Example"
	rows.add_child(input)
	var tree := Tree.new()
	tree.custom_minimum_size.y = 160
	tree.select_mode = Tree.SELECT_MULTI
	rows.add_child(tree)
	var root_item := tree.create_item()
	root_item.set_text(0, "场景 Scene")
	for index in range(12):
		var item := tree.create_item(root_item)
		item.set_text(0, "资源节点 %d — Long descriptive resource name" % index)
	var buttons := HBoxContainer.new()
	rows.add_child(buttons)
	for caption in ["取消 Cancel", "应用 Apply"]:
		var button := Button.new()
		button.text = caption
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		buttons.add_child(button)
	for width in [320, 480, 960]:
		host.size = Vector2(width * scale, 420 * scale)
		await process_frame
		await process_frame
		for button in buttons.get_children():
			var rect: Rect2 = button.get_global_rect()
			if not host.get_global_rect().encloses(rect):
				failures.append("action out of bounds at width %d" % width)
			if button.size.y < button.get_combined_minimum_size().y:
				failures.append("action height clipped at width %d" % width)
		if host.size.x > width * scale:
			failures.append("minimum size exceeds requested width %d" % width)
		samples.append({"requested_width": width, "actual_size": str(host.size), "font_size": input.get_theme_font_size("font_size")})
	if absf(input.get_theme_font_size("font_size") - 15 * scale) > 1.0:
		failures.append("actual font size does not match requested scale")
	host.queue_free()
	print(JSON.stringify({"failures": failures, "samples": samples}))
	quit(0 if failures.is_empty() else 1)
