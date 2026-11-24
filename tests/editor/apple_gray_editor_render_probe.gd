@tool
extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	root.hide()
	root.size = Vector2i(1440, 900)
	await create_timer(1.0).timeout
	var settings := EditorInterface.get_editor_settings()
	EditorInterface.open_scene_from_path("res://sample.tscn")
	await create_timer(0.3).timeout
	EditorInterface.edit_node(EditorInterface.get_edited_scene_root())
	var output := OS.get_environment("APPLE_GRAY_RENDER_OUTPUT")
	var records := []
	for preset in ["Apple Gray", "Apple Gray Dark"]:
		settings.set_setting("interface/theme/color_preset", preset)
		root.propagate_notification(10000)
		await create_timer(0.3).timeout
		RenderingServer.viewport_set_active(root.get_viewport_rid(), true)
		RenderingServer.force_draw(false)
		RenderingServer.force_sync()
		var image := root.get_texture().get_image()
		if image == null or image.is_empty():
			push_error("Editor viewport did not render")
			quit(1)
			return
		var name := "editor-light.png" if preset == "Apple Gray" else "editor-dark.png"
		image.save_png(output + "/" + name)
		records.append({"preset": preset, "image": name, "size": str(image.get_size())})
		EditorInterface.set_main_screen_editor("2D")
		EditorInterface.set_distraction_free_mode(false)
		await create_timer(0.3).timeout
		RenderingServer.viewport_set_active(root.get_viewport_rid(), true)
		RenderingServer.force_draw(false)
		RenderingServer.force_sync()
		var workspace_image := root.get_texture().get_image()
		var workspace_name := "workspace-light.png" if preset == "Apple Gray" else "workspace-dark.png"
		workspace_image.save_png(output + "/" + workspace_name)
		records.append({"preset": preset, "image": workspace_name, "size": str(workspace_image.get_size())})
		var gallery := make_gallery()
		EditorInterface.get_base_control().add_child(gallery)
		await process_frame
		await process_frame
		RenderingServer.viewport_set_active(root.get_viewport_rid(), true)
		RenderingServer.force_draw(false)
		RenderingServer.force_sync()
		var gallery_name := "controls-light.png" if preset == "Apple Gray" else "controls-dark.png"
		root.get_texture().get_image().save_png(output + "/" + gallery_name)
		records.append({"preset": preset, "image": gallery_name, "scope": "inherited editor theme: multi-selection, focus, disabled, input, tabs"})
		gallery.queue_free()
		await process_frame
		EditorInterface.set_main_screen_editor("AI Chat")
	var file := FileAccess.open(output + "/editor-render.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(records))
	print(JSON.stringify(records))
	quit()

func make_gallery() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", EditorInterface.get_base_control().get_theme_stylebox("panel", "PopupMenu"))
	panel.position = Vector2(240, 160)
	panel.size = Vector2(900, 580)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 20)
	panel.add_child(margin)
	var column := VBoxContainer.new()
	margin.add_child(column)
	var title := Label.new()
	title.text = "公共控件 · 中文与 English · 选择 / 键盘焦点 / 禁用"
	column.add_child(title)
	var buttons := HBoxContainer.new()
	column.add_child(buttons)
	for caption in ["普通操作", "已选中", "不可用", "键盘焦点"]:
		var button := Button.new()
		button.text = caption
		button.toggle_mode = caption == "已选中"
		button.button_pressed = button.toggle_mode
		button.disabled = caption == "不可用"
		buttons.add_child(button)
		if caption == "键盘焦点":
			button.grab_focus.call_deferred()
	var input := LineEdit.new()
	input.text = "中文项目 / assets / a-long-resource-name.tres"
	column.add_child(input)
	var tabs := TabBar.new()
	for caption in ["场景", "资源", "历史记录"]:
		tabs.add_tab(caption)
	column.add_child(tabs)
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(row)
	var tree := Tree.new()
	tree.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tree.select_mode = Tree.SELECT_MULTI
	tree.hide_root = true
	row.add_child(tree)
	var parent := tree.create_item()
	for index in range(8):
		var item := tree.create_item(parent)
		item.set_text(0, "场景节点 %d · 长名称检查" % index)
		if index in [1, 3]:
			item.select(0)
	var list := ItemList.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.select_mode = ItemList.SELECT_MULTI
	row.add_child(list)
	for index in range(8):
		list.add_item("资源 %d · material.tres" % index)
	list.select(1, false)
	list.select(3, false)
	var fold := FoldableContainer.new()
	fold.title = "展开内容 · 折叠面板"
	column.add_child(fold)
	var label := Label.new()
	label.text = "字体、间距与圆角继承公共主题"
	fold.add_child(label)
	return panel
