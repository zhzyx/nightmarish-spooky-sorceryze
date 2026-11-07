extends SceneTree


class ZoomParent extends Node2D:
	func change_scale(value: float) -> void:
		scale = Vector2.ONE * value


var failed := false


func _initialize() -> void:
	run.call_deferred()


func settle() -> void:
	for i in 5:
		await process_frame


func check(ok: bool, message: String) -> void:
	if not ok:
		failed = true
		push_error(message)


func levels(rid: RID) -> Array:
	var found := []
	for entry in TextServerManager.get_primary_interface().font_get_size_cache_info(rid):
		if entry.textures > 0 and entry.has("viewport_oversampling"):
			found.append(entry.viewport_oversampling)
	return found


func run() -> void:
	var parent := ZoomParent.new()
	parent.process_thread_group = Node.PROCESS_THREAD_GROUP_SUB_THREAD
	parent.process_thread_messages = Node.FLAG_PROCESS_THREAD_MESSAGES
	parent.oversampling_with_scale = CanvasItem.OVERSAMPLING_WITH_SCALE_ENABLED
	var label := Label.new()
	label.process_thread_group = Node.PROCESS_THREAD_GROUP_MAIN_THREAD
	label.text = "Graph"
	parent.add_child(label)
	root.add_child(parent)
	var shaped := TextLine.new()
	shaped.add_string(label.text, label.get_theme_font("font"), label.get_theme_font_size("font_size"))
	var rid: RID = TextServerManager.get_primary_interface().shaped_text_get_glyphs(shaped.get_rid())[0].font_rid
	await settle()
	var initial := levels(rid)
	for zoom in [0.85, 1.2]:
		parent.call_deferred_thread_group("change_scale", zoom)
		await settle()
		var expected := floorf(zoom * root.get_oversampling() * 64.0) / 64.0
		check(expected in levels(rid), "inherited glyph sampling missed zoom " + str(zoom))
		var before := levels(rid)
		parent.position += Vector2(10, 5)
		await settle()
		check(levels(rid) == before, "panning created another glyph scale")
	parent.call_deferred_thread_group("change_scale", 1.0)
	await settle()
	check(levels(rid) == initial, "returning to unit zoom retained obsolete glyph sizes")
	label.oversampling_with_scale = CanvasItem.OVERSAMPLING_WITH_SCALE_DISABLED
	parent.call_deferred_thread_group("change_scale", 1.2)
	await settle()
	check(levels(rid) == initial, "opted-out text inherited the parent's glyph scaling")
	parent.free()
	if not failed:
		print("DAQIAN_GRAPH_FONT_OK")
	quit(1 if failed else 0)
