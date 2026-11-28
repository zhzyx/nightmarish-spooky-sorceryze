@tool
extends Node3D

var page
var tree: SceneTree
var failures:=0

func check(value: bool,message:String) -> void:
	if not value:
		failures+=1
		push_error(message)

func _ready() -> void:
	if Engine.is_editor_hint() and OS.has_environment("YUGONG_PLAYABLE_TEST"):
		run.call_deferred()

func wait_candidate(count:int) -> bool:
	var timeout:=Time.get_ticks_msec()+210000
	while (page.worker or not page.pending_ai.is_empty()) and Time.get_ticks_msec()<timeout:
		await tree.process_frame
	check(page.candidates.size()==count,"Candidate failed: "+page.status.text)
	return page.candidates.size()==count

func check_march(candidate:Dictionary) -> void:
	var layout:Dictionary=candidate.layout
	var goal:Vector2=page.Layout.plateau_center(layout)
	check(layout.spawn.z>0 and goal.x<0 and goal.y<0 and layout.landmark=="ruin","Expected a southern start and a northwestern castle")
	check(absf(layout.river[0].z-layout.river[-1].z)>.9,"River does not traverse the map north to south")
	var west:PackedVector2Array=page.Layout.road(layout,"west_road")
	var east:PackedVector2Array=page.Layout.road(layout,"east_road")
	var west_center:=0.0
	var east_center:=0.0
	for p in west:west_center+=p.x/west.size()
	for p in east:east_center+=p.x/east.size()
	check(west_center<east_center-.035,"East and west routes do not diverge")
	var crossing_on_east:=false
	for bridge in candidate.geography.bridges:
		var deck:PackedVector3Array=bridge.deck
		var mid:=deck[deck.size()/2]
		var p:=Vector2(mid.x,mid.z)*2/float(candidate.span)
		var nearest:=INF
		for j in east.size()-1:
			nearest=minf(nearest,p.distance_to(Geometry2D.get_closest_point_to_segment(p,east[j],east[j+1])))
		if nearest<.008:crossing_on_east=true
	check(crossing_on_east,"No bridge follows the eastern road through the river")
	check(candidate.geography.goal_y>candidate.geography.spawn_y+15.0,"The destination should rise above the approach")

func check_offline_grammar() -> void:
	var brief:="西南出生，东北古树，窄河从西向东，西线过桥，小径登上高台地"
	for seed_value in [0,42,307,2147483646]:
		var p:Dictionary=page.Fieldcraft.compile_layout(brief,seed_value)
		check(page.Layout.error(p).is_empty(),"Invalid offline layout with seed "+str(seed_value))
		check(p.spawn.x<0 and p.spawn.z>0 and page.Layout.plateau_center(p).x>0 and page.Layout.plateau_center(p).y<0,"Failed to bind independent compass directions")
		check(p.landmark=="tree" and p.river[-1].x-p.river[0].x>1.6 and p.operations.road_width<100 and p.operations.plateau_rise>100 and p.operations.river_width<100,"Description did not control the generated geography")
		check(p==page.Fieldcraft.compile_layout(brief,seed_value),"Nonrepeatable offline seed")
	var compact:='{"spawn":"SW","goal":"NE","landmark":"tree","flow":"WE","bridge":"west","operations":{"river_width":70,"road_width":75,"plateau_rise":130}}'
	check(page.Fieldcraft.compile_layout(compact,42)==page.Fieldcraft.compile_layout(brief,42),"Equivalent prose and compact model intent diverged")
	check(page.Fieldcraft.compile_layout('{"spawn":"Mars"}',42).has("error"),"Invalid intent accepted")
	check(not page.Fieldcraft.compile_layout("西北出生，城堡为终点",42).has("error"),"Failed to choose a distinct default goal")
	check(page.Fieldcraft.compile_layout(brief,42)!=page.Fieldcraft.compile_layout(brief,43),"Seed did not affect layout")
	check(page.Fieldcraft.compile_layout("南侧出生、北方城堡，没有河",42).has("error"),"Unsupported brief silently received a river")

func shot(name:String) -> void:
	if not OS.has_environment("YUGONG_PROOF"):return
	check(page.is_visible_in_tree(),"Wrong editor tab before screenshot "+name)
	for frame in 12:await tree.process_frame
	RenderingServer.force_draw(false)
	check(tree.root.get_texture().get_image().save_png(OS.get_environment("YUGONG_PROOF").path_join(name+".png"))==OK,"Screenshot failed")

func run() -> void:
	tree=get_tree()
	for frame in 240:
		if EditorInterface.get_edited_scene_root()==self:break
		await tree.process_frame
	if EditorInterface.get_edited_scene_root()!=self:return
	var plugin=tree.root.find_child("Terrain3DEditorPlugin",true,false)
	print("Playable editor: opening layout page")
	page=plugin.yugong
	EditorInterface.set_main_screen_editor(page.title)
	await tree.process_frame
	page.span_input.value=1536
	page.relief_input.value=195
	page.prompt.text=page.Layout.EXAMPLE
	var offline:=OS.get_environment("YUGONG_PLAYABLE_TEST")=="offline"
	if offline:
		EditorInterface.get_editor_settings().set_setting("yugong/codex_executable","missing-offline-model")
		check_offline_grammar()
		page.offline_button.pressed.emit()
	elif OS.get_environment("YUGONG_PLAYABLE_TEST")=="astra":
		page.layout_ai.pressed.emit()
	else:
		page.generate_example()
	if not await wait_candidate(1):
		tree.quit(1)
		return
	print("Playable editor: generated first layout")
	var first:Dictionary=page.candidates[0]
	check(first.height.get_width()==1024 and not has_node("Terrain3D"),"Preview resolution or scene isolation")
	check_march(first)
	check(page.layout_map.visible and page.play_button.visible,"Layout editing and playable publish unavailable")
	EditorInterface.set_main_screen_editor(page.title)
	await tree.process_frame
	check(page.is_visible_in_tree(),"Playable layout is not the active editor page")
	await shot("layout")
	var previous:Dictionary=first.layout.duplicate(true)
	var count:=1
	if offline:
		check(first.source=="本地规则" and page.planner.process_id==-1,"Offline button invoked a model")
		page.river_scale.value=138
		page.road_scale.value=82
		page.rise_scale.value=75
		page.shape_button.pressed.emit()
		count+=1
		if not await wait_candidate(count):tree.quit(1);return
		var adjusted:Dictionary=page.candidates.back()
		check(adjusted.layout.river==previous.river and adjusted.layout.plateau==previous.plateau and adjusted.layout.east_road==previous.east_road,"Reshaping moved authored anchors")
		check(adjusted.geography.water_width>first.geography.water_width and adjusted.geography.road_width<first.geography.road_width and adjusted.geography.goal_y<first.geography.goal_y,"Channel, road and plateau operations did not affect the bake")
	for group:String in ["river","west_road","plateau"]:
		var map=page.layout_map
		for frame in 4:await tree.process_frame
		var index:=1
		var handle:Dictionary=map.plan[group][index]
		var pos2:Vector2=page.Layout.pos(handle)
		var at:Vector2=map.screen(pos2)
		var to:Vector2=map.screen(pos2.lerp(Vector2(.05,-.04),.035))
		check(map.bounds().size.x>100,"Layout map did not receive screen space")
		var down:=InputEventMouseButton.new()
		down.button_index=MOUSE_BUTTON_LEFT
		down.pressed=true
		down.position=at
		map._gui_input(down)
		var move:=InputEventMouseMotion.new()
		check(map.active==group,"Could not select "+group+" at "+str(at))
		move.position=to
		map._gui_input(move)
		down.pressed=false
		down.position=move.position
		map._gui_input(down)
		count+=1
		if not await wait_candidate(count):
			tree.quit(1)
			return
	check(first.layout==previous and first.height.get_data()!=page.candidates.back().height.get_data(),"Drag mutated parent or failed to rebake")
	print("Playable editor: three edits completed")
	page.layout_toggle.pressed.emit()
	check(page.preview.visible and not page.layout_map.visible,"3D preview unavailable")
	await shot("height")
	# Create the independent project scene through the same publish handler as the page.
	if OS.has_environment("YUGONG_TEST_PLAY_BUTTON"):page.play_button.pressed.emit()
	else:page.new_scene_button.pressed.emit()
	while page.opening:await tree.process_frame
	var result:=EditorInterface.get_edited_scene_root()
	if not result or not result.has_node("Traveler"):
		check(false,"Publish failed: "+page.status.text)
		tree.quit(1)
		return
	if OS.has_environment("YUGONG_TEST_PLAY_BUTTON"):
		for frame in 100:
			if EditorInterface.is_playing_scene():break
			await tree.process_frame
		check(EditorInterface.is_playing_scene(),"Play button did not launch generated scene")
		EditorInterface.stop_playing_scene()
	var tr:Terrain3D=result.get_node("Terrain3D")
	check(tr.region_size==256 and tr.data.get_region_count()==16,"Expected 16 native Terrain3D regions")
	check(result.has_node("River") and result.has_node("PlateauLandmark") and result.has_node("Crossing1"),"Missing generated geometry")
	var folder:=result.scene_file_path.get_base_dir()
	check(FileAccess.file_exists(folder.path_join("layout.json")),"Layout not persisted")
	page.current_layout_button.pressed.emit()
	if not await wait_candidate(count+1):
		tree.quit(1)
		return
	check(page.candidates.back().layout==page.candidates[count-1].layout,"Reloaded layout coordinates changed")
	check(page.candidates.back().height.get_data()==page.candidates[count-1].height.get_data(),"Reloaded layout changed its baked height")
	check(page.candidates.back().origin==first.source,"Layout origin was lost")
	var edited_record:=FileAccess.open("res://edited-result.txt",FileAccess.WRITE)
	edited_record.store_string(result.scene_file_path)
	edited_record.close()
	# Publish the unmodified first response as a second scene, with no dragging or seed changes.
	EditorInterface.set_main_screen_editor(page.title)
	page.gallery.select(0)
	page.show_candidate(0)
	page.new_scene_button.pressed.emit()
	while page.opening:await tree.process_frame
	var first_result:=EditorInterface.get_edited_scene_root()
	if not first_result or not first_result.has_node("Traveler") or first_result==result:
		check(false,"Could not publish the original one-sentence layout")
		tree.quit(1)
		return
	var original:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(first_result.scene_file_path.get_base_dir().path_join("layout.json")))
	check(original.layout==previous and original.origin==first.source,"The unedited scene no longer matches the first response")
	var record:=FileAccess.open("res://test-result.txt",FileAccess.WRITE)
	record.store_string(first_result.scene_file_path)
	record.close()
	if offline:
		EditorInterface.set_main_screen_editor(page.title)
		page.prompt.text='{"spawn":"SW","goal":"NE","landmark":"tree","flow":"WE","bridge":"west","operations":{"river_width":70,"road_width":75,"plateau_rise":130}}'
		page.span_input.value=512
		page.relief_input.value=90
		page.seed_input.value=307
		var alt_count:int=page.candidates.size()+1
		page.offline_button.pressed.emit()
		if not await wait_candidate(alt_count):tree.quit(1);return
		page.new_scene_button.pressed.emit()
		while page.opening:await tree.process_frame
		var alt:=EditorInterface.get_edited_scene_root()
		check(alt!=first_result and alt.has_node("Crossing1"),"Alternate brief failed to create a crossing")
		var alt_record:=FileAccess.open("res://alternate-result.txt",FileAccess.WRITE)
		alt_record.store_string(alt.scene_file_path)
		alt_record.close()
	print("Yugong playable editor: ",failures," failures; source=",first.source," bridges=",first.geography.bridges.size())
	tree.quit(0 if failures==0 else 1)
