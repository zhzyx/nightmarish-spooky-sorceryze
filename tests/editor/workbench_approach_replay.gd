@tool
extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> bool:
	if not ok:
		push_error(message)
		quit(1)
	return ok

func make_scene() -> void:
	var stage := Node2D.new()
	stage.name = "Stage"
	var actor := Node2D.new()
	actor.name = "Actor"
	stage.add_child(actor)
	actor.owner = stage
	var player := AnimationPlayer.new()
	player.name = "Player"
	stage.add_child(player)
	player.owner = stage
	var library := AnimationLibrary.new()
	var clip := Animation.new()
	for axis in ["x", "y"]:
		var track := clip.add_track(Animation.TYPE_VALUE)
		clip.track_set_path(track, NodePath("Actor:position:" + axis))
		for key in 3:
			clip.track_insert_key(track, key * 0.5, float(key * (12 if axis == "x" else 7)))
	library.add_animation("Walk", clip)
	player.add_animation_library("", library)
	player.assigned_animation = "Walk"
	var packed := PackedScene.new()
	packed.pack(stage)
	ResourceSaver.save(packed, "res://motion.tscn")
	stage.free()

func menu_action(menu: PopupMenu, prefix: String) -> bool:
	for i in menu.item_count:
		if menu.get_item_text(i).begins_with(prefix):
			menu.id_pressed.emit(menu.get_item_id(i))
			return true
	return check(false, "Missing action " + prefix)

func run() -> void:
	await create_timer(0.8).timeout
	var reopening := FileAccess.file_exists("res://motion.tscn")
	if not reopening:
		make_scene()
	EditorInterface.open_scene_from_path("res://motion.tscn")
	await create_timer(0.45).timeout
	var stage := EditorInterface.get_edited_scene_root()
	var player := stage.get_node("Player") as AnimationPlayer
	EditorInterface.edit_node(player)
	await create_timer(0.5).timeout
	var tracks := root.find_children("*", "AnimationTrackEdit", true, false)
	if not check(tracks.size() == 2, "Missing native timeline tracks"):
		return
	var menu: PopupMenu
	for button: MenuButton in root.find_children("*", "MenuButton", true, false):
		if button.tooltip_text == "Animation Tools":
			menu = button.get_popup()
	if not check(menu != null, "Missing Animation Tools"):
		return
	if not reopening:
		tracks[0].emit_signal("select_key", 2, true)
		await process_frame
		if not menu_action(menu, "Halve Approach"):
			return
		await process_frame
		var confirm: ConfirmationDialog
		for window: ConfirmationDialog in root.find_children("*", "ConfirmationDialog", true, false):
			if window.visible and window.title.begins_with("Halve Approach"):
				confirm = window
		if not check(confirm != null, "Missing candidate name dialog"):
			return
		confirm.find_children("*", "LineEdit", true, false)[0].text = "Landing"
		confirm.confirmed.emit()
		await create_timer(0.3).timeout
		if not check(player.has_animation("Landing") and EditorInterface.save_scene() == OK, "Candidate save failed"):
			return
		print("APPROACH_SAVE=", FileAccess.get_sha256("res://motion.tscn"))
		quit()
		return
	var original := player.get_animation("Walk")
	var changed := player.get_animation("Landing")
	for t in 2:
		if not check(original.track_get_key_time(t,1) == 0.5 and changed.track_get_key_time(t,1) == 0.25, "Wrong approach duration"):
			return
		for k in 3:
			if not check(original.track_get_key_value(t,k) == changed.track_get_key_value(t,k) and original.track_get_key_transition(t,k) == changed.track_get_key_transition(t,k), "Pose or transition changed"):
				return
		if not check(changed.track_get_key_time(t,2) == original.track_get_key_time(t,2), "Landing moved"):
			return
	var selection: OptionButton
	for dropdown: OptionButton in root.find_children("*", "OptionButton", true, false):
		for i in dropdown.item_count:
			if dropdown.get_item_text(i) == "Landing":
				selection = dropdown
				dropdown.select(i)
				dropdown.item_selected.emit(i)
				break
	if not check(selection != null, "Timeline clip picker missing"):
		return
	var dock = root.find_children("*", "AnimationPlayerEditor", true, false)[0]
	EditorInterface.set_main_screen_editor("2D")
	dock.make_visible()
	await create_timer(0.3).timeout
	tracks = dock.find_children("*", "AnimationTrackEdit", true, false)
	tracks[0].emit_signal("timeline_changed", 0.75, false)
	var cursor := player.current_animation_position
	if not check(cursor > 0.6, "Failed to position cursor"):
		return
	if not menu_action(menu, "Replay Source"):
		return
	var label := root.find_child("ApproachReplayRevision", true, false) as Label
	var samples := {}
	var poses := {}
	var deadline := Time.get_ticks_msec() + 7000
	while label.visible and Time.get_ticks_msec() < deadline:
		var t := player.current_animation_position
		var clip := str(player.assigned_animation)
		if t > 0.125 and t < 0.375 and (not samples.has(clip) or absf(t - 0.25) < absf(samples[clip].time - 0.25)):
			samples[clip] = {"time": t, "x":stage.get_node("Actor").position.x, "revision":label.text}
		if is_equal_approx(t, 1.0):
			poses[clip] = stage.get_node("Actor").position
		await process_frame
	if not check(poses.size() == 2 and poses.Walk == Vector2(24,14) and poses.Landing == poses.Walk, "Landing pose missing: " + str(poses)):
		return
	if not check(samples.size() == 2 and samples.Landing.x > samples.Walk.x + 2.0 and samples.Walk.revision != samples.Landing.revision, "Missing pace or revisions: " + str(samples)):
		return
	if not check(not label.visible and player.assigned_animation == "Landing" and is_equal_approx(cursor, player.current_animation_position), "Cursor or clip lost"):
		return
	# Mark a separate before/after interval from ordinary native key selections.
	var source_index := -1
	var candidate_index := -1
	for i in selection.item_count:
		if selection.get_item_text(i) == "Walk": source_index = i
		if selection.get_item_text(i) == "Landing": candidate_index = i
	selection.select(source_index)
	selection.item_selected.emit(source_index)
	await create_timer(0.15).timeout
	tracks = dock.find_children("*", "AnimationTrackEdit", true, false)
	tracks[0].emit_signal("select_key", 1, true)
	tracks[0].emit_signal("select_key", 2, false)
	await process_frame
	if not menu_action(menu, "Mark Selected Keys"):
		return
	selection.select(candidate_index)
	selection.item_selected.emit(candidate_index)
	await process_frame
	menu_action(menu, "Replay Source")
	var interval: String = label.text
	if not check(label.visible and "0.5-1.0" in interval, "Marked replay range unavailable: " + interval):
		return
	menu_action(menu, "Replay Source")
	if not check(not label.visible and player.assigned_animation == "Landing", "Cancel did not restore candidate"):
		return
	print("APPROACH_REOPEN=", JSON.stringify({"samples":samples, "marked_interval":interval, "saved":FileAccess.get_sha256("res://motion.tscn"),"restored":cursor,"landing":[changed.track_get_key_value(0,2),changed.track_get_key_value(1,2)],"middle_times":[0.5,0.25],"display_driver":DisplayServer.get_name()}))
	quit()
