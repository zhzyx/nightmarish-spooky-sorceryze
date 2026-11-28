extends SceneTree

var failures:=0
var game:Node
var player:CharacterBody3D

func _initialize() -> void:
	run.call_deferred()

func check(value:bool,message:String) -> void:
	if not value:
		failures+=1
		push_error(message)

func photo(name:String) -> void:
	if not OS.has_environment("YUGONG_PROOF"):return
	for frame in 12:await process_frame
	await RenderingServer.frame_post_draw
	check(root.get_texture().get_image().save_png(OS.get_environment("YUGONG_PROOF").path_join(name+".png"))==OK,"Runtime screenshot")

func walk_road(plan:Dictionary,key:String,span:float) -> void:
	# Follow the same rounded path as the layout editor using the production movement and physics.
	var path:=PackedVector2Array([Vector2(plan.spawn.x,plan.spawn.z)])
	for v in plan[key]:path.append(Vector2(v.x,v.z))
	var goal:=Vector2.ZERO
	for v in plan.plateau:goal+=Vector2(v.x,v.z)
	path.append(goal/plan.plateau.size())
	for pass_index in 2:
		var rounded:=PackedVector2Array([path[0]])
		for i in path.size()-1:
			rounded.append(path[i].lerp(path[i+1],.25))
			rounded.append(path[i].lerp(path[i+1],.75))
		rounded.append(path[-1])
		path=rounded
	player.call("restart")
	var grounded:=0
	var ticks:=0
	var max_idle:=0
	var reference_y:float=player.position.y
	for i in range(1,path.size()):
		var target:=path[i]*span*.5
		var prior:=INF
		var idle:=0
		while true:
			await physics_frame
			var p:=Vector2(player.position.x,player.position.z)
			var distance:=p.distance_to(target)
			if distance<1.15:break
			if distance>=prior-.015:idle+=1
			else:idle=0
			max_idle=maxi(idle,max_idle)
			if idle>60 or ticks>18000:
				check(false,"%s blocked at %s towards %s, height %s"%[key,p,target,player.position.y])
				return
			var d:=p.direction_to(target)
			player.call("travel",Vector3(d.x,0,d.y)*17.0,1.0/60.0)
			if player.is_on_floor():grounded+=1
			check(absf(player.position.y-reference_y)<1.1,"Walking height jumped on "+key)
			reference_y=player.position.y
			prior=distance
			ticks+=1
	print("WALK ",key," ticks=",ticks," grounded=",grounded," max_idle=",max_idle)
	check(ticks>0 and grounded>ticks*.96,"Road lost ground contact")

func run() -> void:
	var record:="res://edited-result.txt" if OS.has_environment("YUGONG_TEST_EDITED") else "res://test-result.txt"
	if OS.has_environment("YUGONG_TEST_ALTERNATE"):record="res://alternate-result.txt"
	var path:=FileAccess.get_file_as_string(record).strip_edges()
	var scene:=load(path) as PackedScene
	if scene==null:quit(1);return
	game=scene.instantiate()
	root.add_child(game)
	current_scene=game
	player=game.get_node("Traveler")
	player.set_physics_process(false)
	var tr:Terrain3D=game.get_node("Terrain3D")
	var config:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(path.get_base_dir().path_join("layout.json")))
	for frame in 50:
		await physics_frame
		player.call("travel",Vector3.ZERO,1.0/60.0)
	check(player.is_on_floor() and player.get_node("Eye").current,"Player spawn/collision/camera")
	check(tr.data.get_region_count()==16 and tr.assets!=null and game.has_node("Crossing1"),"Native terrain/bridge missing after reload")
	if config.layout.has("operations"):
		check(game.has_node("SpringPavilion") and game.has_node("GoldenAsh") and game.has_node("DistantMountains") and game.has_node("Crossing1/StoneArches"),"Composed scenery missing")
		var eye:=player.get_node("Eye") as Camera3D
		var keep:=game.get_node("PlateauLandmark") as MeshInstance3D
		var crown:=keep.to_global(keep.mesh.get_aabb().get_center()+Vector3.UP*keep.mesh.get_aabb().size.y*.22)
		if config.layout.operations.sightline:
			check(eye.is_position_in_frustum(crown),"Castle outside authored spawn view")
			for i in range(1,96):
				var at:=eye.global_position.lerp(crown,float(i)/96)
				check(tr.data.get_height(at)<at.y,"Terrain obstructs the spawn-to-castle sightline")
	if config.get("origin")=="本地规则":
		var ash:=game.get_node("GoldenAsh") as MeshInstance3D
		var near:=game.get_node("CrossingView") as Camera3D
		var canopy:=ash.position+Vector3.UP*ash.mesh.get_aabb().size.y*ash.scale.y*.7
		check(near.is_position_in_frustum(canopy),"Golden tree outside bridge view")
		var clearance:=INF
		for i in range(1,100):
			var p:=near.position.lerp(canopy,float(i)/100)
			clearance=minf(clearance,p.y-tr.data.get_height(p))
		check(clearance>0,"Bank obscures the golden tree")
		print("Bridge to tree terrain clearance (m): ",clearance)
	await photo("spawn")
	if game.has_node("CrossingView"):
		for pair in [[KEY_2,"CrossingView","crossing"],[KEY_3,"GateView","gate"]]:
			var key:=InputEventKey.new()
			key.keycode=pair[0]
			key.pressed=true
			player.call("_unhandled_input",key)
			check(game.get_node(pair[1]).current,"View shortcut failed "+pair[1])
			await photo(pair[2])
		player.call("restart")
	var tab:=InputEventKey.new()
	tab.keycode=KEY_TAB
	tab.pressed=true
	player.call("_unhandled_input",tab)
	check((game.get_node("Overview") as Camera3D).current,"Overview key did not switch")
	await photo("overview")
	if DisplayServer.get_name()=="headless":
		await walk_road(config.layout,"west_road",config.span)
		await walk_road(config.layout,"east_road",config.span)
	print("Yugong playable runtime: ",failures," failures")
	quit(0 if failures==0 else 1)
