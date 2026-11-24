@tool
extends "res://approach.gd"

const CLIPS = ["Walk", "Landing"]
const POSES = [Vector2(35, 96), Vector2(93, 46), Vector2(155, 36), Vector2(250, 79)]
const TIMES = [0.0, 0.25, 0.5, 1.0]

func initialize_motion():
	var stage := Node2D.new()
	stage.name = "Stage"
	var actor := Polygon2D.new()
	actor.name = "Actor"
	actor.polygon = PackedVector2Array([Vector2(0,-15), Vector2(12,0), Vector2(0,15), Vector2(-12,0)])
	actor.color = Color("#efa03a")
	stage.add_child(actor)
	actor.owner = stage
	actor.position = POSES[0]
	var ground := Line2D.new()
	ground.name = "Ground"
	ground.points = PackedVector2Array([Vector2(15,112),Vector2(280,112)])
	ground.width = 2
	stage.add_child(ground)
	ground.owner = stage
	var player := AnimationPlayer.new()
	player.name = "Player"
	stage.add_child(player)
	player.owner = stage
	var clip := Animation.new()
	clip.step = 1.0 / 24.0
	for axis in 2:
		var track := clip.add_track(Animation.TYPE_VALUE)
		clip.track_set_path(track, NodePath("Actor:position:" + ["x", "y"][axis]))
		for k in TIMES.size():
			clip.track_insert_key(track, TIMES[k], POSES[k][axis])
	var library := AnimationLibrary.new()
	library.add_animation("Walk", clip)
	player.add_animation_library("", library)
	player.assigned_animation = "Walk"
	var packed := PackedScene.new()
	packed.pack(stage)
	var saved := ResourceSaver.save(packed, "res://motion.tscn")
	stage.free()
	return saved

func select_clip(picker, clip):
	for i in picker.item_count:
		if picker.get_item_text(i) == clip:
			picker.select(i)
			picker.item_selected.emit(i)
			return true
	return false

func run():
	var phase := OS.get_environment("Q03_PHASE")
	await create_timer(0.8).timeout
	if phase == "initial":
		if check(initialize_motion() == OK, "Initial save failed"):
			print("Q03=" + JSON.stringify({"sha256": FileAccess.get_sha256("res://motion.tscn")}))
			quit()
		return
	EditorInterface.open_scene_from_path("res://motion.tscn")
	await create_timer(0.5).timeout
	var stage := EditorInterface.get_edited_scene_root()
	var player := stage.get_node("Player") as AnimationPlayer
	var actor := stage.get_node("Actor") as Polygon2D
	EditorInterface.edit_node(player)
	EditorInterface.set_main_screen_editor("2D")
	await create_timer(0.5).timeout
	var dock: Control = root.find_children("*", "AnimationPlayerEditor", true, false).front()
	dock.make_visible()
	var menu: PopupMenu
	var picker: OptionButton
	for button: MenuButton in dock.find_children("*", "MenuButton", true, false):
		if button.tooltip_text == "Animation Tools":
			menu = button.get_popup()
	for button: OptionButton in dock.find_children("*", "OptionButton", true, false):
		for i in button.item_count:
			if button.get_item_text(i) == "Walk":
				picker = button
	if not check(menu != null and picker != null and select_clip(picker, "Walk"), "Animation controls unavailable"):
		return
	await create_timer(0.25).timeout
	var tracks := dock.find_children("*", "AnimationTrackEdit", true, false)
	if not check(tracks.size() == 2, "Timeline tracks unavailable"):
		return
	var result := {}
	if phase == "manual":
		tracks[1].emit_signal("select_key", 3, true)
		await create_timer(0.2).timeout
		var inspector := EditorInterface.get_inspector().get_edited_object()
		if not check(inspector != null and inspector.get("value") == 79.0, "Landing key inspector unavailable"):
			return
		inspector.set("value", 96.0)
		await process_frame
		if not check(player.get_animation("Walk").track_get_key_value(1,3) == 96.0, "Landing edit failed"):
			return
		var source_frames := []
		var source := player.get_animation("Walk")
		for k in source.track_get_key_count(0):
			source_frames.append(roundi(source.track_get_key_time(0,k) * 24))
		result = {"frame":24, "before":[250,79], "after":[250,96], "source_frames":source_frames}
	elif phase == "produce":
		var action: Dictionary = JSON.parse_string(OS.get_environment("Q03_ACTION"))
		var key := player.get_animation("Walk").track_find_key(0, float(action.protected_frame) / 24.0, Animation.FIND_MODE_EXACT)
		if not check(action.action == "halve_approach" and key >= 0, "Invalid retime request"):
			return
		tracks[0].emit_signal("select_key", key, true)
		await process_frame
		if not menu_action(menu, "Halve Approach"):
			return
		await process_frame
		var dialog: ConfirmationDialog
		for window: ConfirmationDialog in root.find_children("*","ConfirmationDialog",true,false):
			if window.visible and window.title.begins_with("Halve Approach"):
				dialog = window
		if not check(dialog != null, "Retiming dialog unavailable"):
			return
		dialog.find_children("*","LineEdit",true,false)[0].text = action.candidate_clip
		dialog.confirmed.emit()
		await create_timer(0.25).timeout
		if not check(player.has_animation("Landing"), "Candidate clip absent"):
			return
	elif phase == "replay":
		# Mark the complete interval independently of the retime range so the
		# native A/B player also displays the untouched landing and second half.
		tracks[0].emit_signal("select_key", 0, true)
		tracks[0].emit_signal("select_key", 3, false)
		await process_frame
		if not menu_action(menu, "Mark Selected Keys") or not select_clip(picker, "Landing"):
			return
		await create_timer(0.2).timeout
		tracks = dock.find_children("*", "AnimationTrackEdit", true, false)
		tracks[0].emit_signal("timeline_changed", 0.75, false)
		if not check(is_equal_approx(player.current_animation_position,0.75), "Original cursor unavailable"):
			return
		if not menu_action(menu,"Replay Source"):
			return
		var label := dock.find_child("ApproachReplayRevision",true,false) as Label
		var samples := {}
		var landing := {}
		var deadline := Time.get_ticks_msec() + 6500
		while label.visible and Time.get_ticks_msec() < deadline:
			var t := player.current_animation_position
			var clip := str(player.assigned_animation)
			if not samples.has(clip) or absf(t - 0.125) < absf(samples[clip].time - 0.125):
				samples[clip] = {"time":t,"xy":[actor.position.x,actor.position.y],"label":label.text}
			if is_equal_approx(t,1.0):
				landing[clip] = [actor.position.x,actor.position.y]
			await process_frame
		if not check(not label.visible and samples.size() == 2 and landing.size() == 2 and player.assigned_animation == "Landing" and is_equal_approx(player.current_animation_position,0.75), "A/B replay or cursor restoration failed"):
			return
		if not check(samples.Landing.xy[0] > samples.Walk.xy[0] + 10 and landing.Walk == [250.0,96.0] and landing.Landing == landing.Walk, "A/B pace or landing mismatch"):
			return
		var frames := {}
		var keyframes := {}
		for clip in CLIPS:
			select_clip(picker, clip)
			await process_frame
			frames[clip] = []
			keyframes[clip] = []
			var animation := player.get_animation(clip)
			for track in animation.get_track_count():
				var keys := []
				for k in animation.track_get_key_count(track):
					keys.append([animation.track_get_key_time(track,k)*24,animation.track_get_key_value(track,k),animation.track_get_key_transition(track,k)])
				keyframes[clip].append(keys)
			for frame in 25:
				player.seek(frame / 24.0,true)
				frames[clip].append([actor.position.x,actor.position.y])
		if not check(frames.Walk.slice(12) == frames.Landing.slice(12) and frames.Walk[3] != frames.Landing[3], "Unexpected frame differences"):
			return
		result = {"fps":24,"frames":frames,"keys":keyframes,"replay":samples,"landing":landing,"restored_cursor":0.75,"viewport":actor.get_viewport().get_class(),"display_driver":DisplayServer.get_name()}
	else:
		check(false,"Unknown probe phase")
		return
	if phase != "replay" and not check(EditorInterface.save_scene() == OK, "Scene save failed"):
		return
	result["sha256"] = FileAccess.get_sha256("res://motion.tscn")
	print("Q03=" + JSON.stringify(result))
	quit()
