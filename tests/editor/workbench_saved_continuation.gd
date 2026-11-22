extends "res://changes.gd"

func make_motion() -> void:
	var stage := Node2D.new()
	stage.name = "Stage"
	var actor := Node2D.new()
	actor.name = "Actor"
	stage.add_child(actor)
	actor.owner = stage
	actor.position.x = 5.0
	var player := AnimationPlayer.new()
	player.name = "Player"
	stage.add_child(player)
	player.owner = stage
	var library := AnimationLibrary.new()
	var clip := Animation.new()
	for axis in ["x", "y"]:
		var track := clip.add_track(Animation.TYPE_VALUE)
		clip.track_set_path(track, NodePath("Actor:position:" + axis))
		for i in 3:
			clip.track_insert_key(track, i * 0.5, float(i * (12 if axis == "x" else 7)))
	library.add_animation("Walk", clip)
	player.add_animation_library("", library)
	player.assigned_animation = "Walk"
	var packed := PackedScene.new()
	packed.pack(stage)
	ResourceSaver.save(packed, "res://motion.tscn")
	stage.free()

func run() -> void:
	await create_timer(0.8).timeout
	await open_sidebar()
	sidebar = root.find_child("AIWorkbenchSidebar",true,false)
	panel = sidebar.find_child("WorkbenchBusinessModules",true,false)
	var session = sidebar.find_child("WorkbenchBusinessSession",true,false)
	var until := Time.get_ticks_msec()+15000
	while session.get_identity().is_empty() and Time.get_ticks_msec()<until:
		await process_frame
	if not require(await choose(panel,1),"Cannot load modules"):
		return
	var idx := -1
	for i in panel.picker.item_count:
		if panel.picker.get_item_metadata(i)=="default":
			idx = i
	if not require(await choose(panel,idx),"Cannot open module"):
		return
	var doc := OS.get_environment("EDIT_DOCUMENT")
	if OS.get_environment("SAVE_PHASE")=="reopen":
		if not require(panel.continue_work.button_pressed and panel.preserve_note.text == "保留三个现场的人工修改", "Continuation scope did not survive restart"):
			return
		var reply := await send_turn(panel.composer.text+"\n继续当前工作")
		if not require(reply.has("document_edits"), "Missing saved document"):
			return
		print("SAVE_RESULT=reopen")
		quit()
		return
	panel.continue_work.button_pressed=true
	panel.preserve_note.text="保留三个现场的人工修改"
	sidebar.close()
	EditorInterface.set_main_screen_editor("Script")
	EditorInterface.edit_script(load("res://actor.gd"))
	await process_frame
	var code := EditorInterface.get_script_editor().get_current_editor().get_base_editor() as CodeEdit
	code.grab_focus()
	code.select(2,0,2,code.get_line(2).length())
	await open_sidebar()
	if (await send_turn("固定起始版 <tianxuan-doc://%s/1/2>" % doc)).is_empty():
		return
	sidebar.close()
	make_motion()
	EditorInterface.open_scene_from_path("res://motion.tscn")
	EditorInterface.set_main_screen_editor("2D")
	await create_timer(0.4).timeout
	var actor := EditorInterface.get_edited_scene_root().get_node("Actor") as Node2D
	var player := EditorInterface.get_edited_scene_root().get_node("Player") as AnimationPlayer
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(actor)
	EditorInterface.get_selection().add_node(player)
	await open_sidebar()
	if (await send_turn("同时固定动画和节点")).is_empty():
		return
	var baseline: Dictionary = panel.saved_changes.targets["res://motion.tscn#Player"].starting_state.tracks
	if not require(baseline.size()==2,"Baseline animation tracks missing"):
		return
	code.set_line(2,"\treturn 29")
	EditorInterface.get_script_editor().save_all_scripts()
	sidebar.close()
	EditorInterface.edit_node(player)
	await create_timer(0.5).timeout
	var tracks := root.find_children("*","AnimationTrackEdit",true,false)
	if not require(tracks.size()==2,"Expected two native timeline tracks"):
		return
	tracks[0].emit_signal("select_key",1,true)
	await create_timer(0.3).timeout
	var key := EditorInterface.get_inspector().get_edited_object()
	if not require(key and key.get_class()=="AnimationTrackKeyEdit" and key.get("value")==12.0,"Incorrect timeline key"):
		return
	key.set("value",18.0)
	actor.position.x=37.5
	EditorInterface.mark_scene_as_unsaved()
	if not require(EditorInterface.save_scene()==OK,"Scene save failed"):
		return
	var revised: Dictionary = panel.saved_changes.selected_state("res://motion.tscn#Player","res://motion.tscn").tracks
	for id in baseline:
		if baseline[id].path.ends_with(":y") and not require(baseline[id].revision==revised[id].revision, "Untouched y track changed"):
			return
	# Open the existing document without adding another editor selection.
	var view = session.find_child("WorkbenchDocuments",true,false)
	await view.open_document(doc,1,2,true)
	view.edit.pressed.emit()
	view.draft_body.text = view.draft_body.text.replace("原来第 2 段", "人工修订的第 2 段")
	view.composer.get_ok_button().pressed.emit()
	until = Time.get_ticks_msec()+15000
	while view.reference.get("version")!=2 and Time.get_ticks_msec()<until:
		await process_frame
	if not require(panel.composer.text.contains("<tianxuan-doc-edit://"),"Document save was not queued"):
		return
	print("TRACK_REVISIONS=",JSON.stringify({"before":baseline,"after":revised}))
	print("SAVE_RESULT=save")
	quit()
