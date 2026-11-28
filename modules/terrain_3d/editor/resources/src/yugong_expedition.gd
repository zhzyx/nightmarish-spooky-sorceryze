@tool
extends RefCounted

const Layout=preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout.gd")
const ART="@TERRAIN3D_EDITOR_ROOT@/landscape/"
const StoneBridge=preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_stone_bridge.gd")
const WALKER="@TERRAIN3D_EDITOR_ROOT@/src/yugong_traveler.gd"

static func copy_file(source:String,target:String) -> bool:
	return DirAccess.copy_absolute(ProjectSettings.globalize_path(source),ProjectSettings.globalize_path(target))==OK

static func assets(folder:String) -> Terrain3DAssets:
	if DirAccess.make_dir_recursive_absolute(folder)!=OK:return null
	var files:=["ground037_alb_ht","rock023_alb_ht","loam","ground037_nrm_rgh","rock023_nrm_rgh"]
	var textures:Array[Texture2D]=[]
	for key in files:
		var path:=folder.path_join(key+".res")
		if not copy_file(ART+key+".res",path):return null
		var tex:=ResourceLoader.load(path,"Texture2D") as Texture2D
		if not tex:return null
		textures.append(tex)
	if not copy_file(ART+"CREDITS.txt",folder.path_join("CREDITS.txt")):return null
	var palette:=Terrain3DAssets.new()
	var layers:Array[Terrain3DTextureAsset]=[]
	for i in 3:
		var layer:=Terrain3DTextureAsset.new()
		layer.id=i
		layer.name=["草甸","岩壁","古道"][i]
		layer.albedo_texture=textures[i]
		layer.normal_texture=textures[4 if i==1 else 3]
		layer.uv_scale=.17 if i==1 else .34
		layer.detiling_rotation=[.43,.037,.30][i]
		layer.detiling_shift=[.50,.57,.57][i]
		layers.append(layer)
	palette.texture_list=layers
	var path:=folder.path_join("palette.res")
	if ResourceSaver.save(palette,path,ResourceSaver.FLAG_COMPRESS)!=OK:return null
	palette.resource_path=path
	return palette

static func attach(root:Node, parent:Node, child:Node, label:String) -> void:
	child.name=label
	parent.add_child(child,true)
	child.owner=root

static func ground(c:Dictionary, p:Vector2) -> float:
	var n:int=c.height.get_width()
	var uv:Vector2=(p/c.span+Vector2.ONE*.5)*n
	return c.height.get_pixel(clampi(roundi(uv.x),0,n-1),clampi(roundi(uv.y),0,n-1)).r

static func surface(tint:Color, roughness:float=.91) -> StandardMaterial3D:
	var m:=StandardMaterial3D.new()
	m.albedo_color=tint
	m.roughness=roughness
	m.cull_mode=BaseMaterial3D.CULL_DISABLED
	return m

static func ribbon(line:PackedVector3Array, width:float, mat:Material) -> ArrayMesh:
	var builder:=SurfaceTool.new()
	builder.begin(Mesh.PRIMITIVE_TRIANGLES)
	builder.set_material(mat)
	var sides:=PackedVector3Array()
	for i in line.size():
		var tangent:=line[mini(i+1,line.size()-1)]-line[maxi(i-1,0)]
		sides.append(Vector3(-tangent.z,0,tangent.x).normalized()*width)
	for i in line.size()-1:
		var a:=line[i]+sides[i]
		var b:=line[i]-sides[i]
		var c:=line[i+1]+sides[i+1]
		var d:=line[i+1]-sides[i+1]
		for v:Vector3 in [a,b,c,b,d,c]:
			builder.set_normal(Vector3.UP)
			builder.add_vertex(v)
	return builder.commit()

static func mesh_node(root:Node,parent:Node,mesh:Mesh,label:String) -> MeshInstance3D:
	var item:=MeshInstance3D.new()
	item.mesh=mesh
	attach(root,parent,item,label)
	return item

static func add_crossing(root:Node,deck:PackedVector3Array,width:float,index:int,crafted:bool,bed:float) -> void:
	var body:=StaticBody3D.new()
	attach(root,root,body,"Crossing%d"%index)
	# Sink both ends into dry road and rise gradually above the clipped river bank.
	var approach:=deck.duplicate()
	var distance:=PackedFloat32Array([0.0])
	for i in range(1,deck.size()):
		distance.append(distance[-1]+deck[i].distance_to(deck[i-1]))
	for i in deck.size():
		var from_end:=minf(distance[i],distance[-1]-distance[i])
		approach[i].y+=lerpf(-1.05,.28,smoothstep(0,maxf(5.0,width*1.2),from_end))
	var mesh:=ribbon(approach,width,surface(Color("#8d806a")))
	mesh_node(root,body,mesh,"Deck")
	var hit:=CollisionShape3D.new()
	var shape:=mesh.create_trimesh_shape()
	shape.backface_collision=true
	hit.shape=shape
	attach(root,body,hit,"WalkableDeck")
	if crafted:
		mesh_node(root,body,StoneBridge.build(approach,width,bed),"StoneArches")
		return
	var last:=deck[0]-Vector3(100,0,0)
	for p in deck:
		if p.distance_to(last)<maxf(8.0,width*3):continue
		last=p
		var pier:=CylinderMesh.new()
		pier.radial_segments=8
		pier.top_radius=width*.65
		pier.bottom_radius=width*.88
		pier.height=maxf(1,p.y+1)
		pier.material=surface(Color("#736e5d"))
		mesh_node(root,body,pier,"Pier").position=p-Vector3.UP*(pier.height*.5+.1)

static func populate(root:Node3D,c:Dictionary,folder:String) -> bool:
	var plan:Dictionary=c.layout
	var crafted:=plan.has("operations")
	var size_m:float=c.span
	var decor:=folder.path_join("landmarks")
	if DirAccess.make_dir_recursive_absolute(decor)!=OK:return false
	var src:=folder.path_join("traveler.gd")
	if not copy_file(WALKER,src):return false
	var script:=ResourceLoader.load(src,"GDScript") as GDScript
	if not script or script.get_instance_base_type() != &"CharacterBody3D":return false
	var file:=FileAccess.open(folder.path_join("layout.json"),FileAccess.WRITE)
	if not file:return false
	file.store_string(JSON.stringify({"version":Layout.VERSION,"description":c.description,"span":size_m,"relief":c.relief,"seed":c.seed,"origin":c.origin,"layout":plan},"\t",true,true))
	file.close()
	var geo:Dictionary=c.geography
	var channel:=PackedVector3Array()
	for p in Layout.smooth_line(Layout.points(plan.river)):
		channel.append(Vector3(p.x*size_m*.5,geo.water_y,p.y*size_m*.5))
	mesh_node(root,root,ribbon(channel,geo.water_width,surface(Color("#508e90"),.24)),"River")
	for i in geo.bridges.size():
		add_crossing(root,geo.bridges[i].deck,maxf(2.1,geo.road_width*1.12),i+1,crafted,geo.water_y-c.relief*.06)
	var target:=Layout.plateau_center(plan)*size_m*.5
	var marker:Mesh
	if plan.landmark=="cairn":
		var cairn:=PrismMesh.new()
		cairn.size=Vector3(7,12,6)
		cairn.material=surface(Color("#a5987d"))
		marker=cairn
	else:
		var asset: String="ruin" if plan.landmark=="ruin" else "ash"
		var path:=decor.path_join(asset+".res")
		if not copy_file(ART+asset+".res",path):return false
		marker=ResourceLoader.load(path,"Mesh")
	if not marker:return false
	var landmark:=mesh_node(root,root,marker,"PlateauLandmark")
	# Offset the landmark behind the arrival point, leaving the road end open.
	var from:=Layout.pos(plan.spawn)*size_m*.5
	var back:=(target-from).normalized()
	var k:=clampf(size_m/1536,.15,2.5)
	var site:=target+back*23*k
	landmark.position=Vector3(site.x,ground(c,site),site.y)
	landmark.scale=Vector3.ONE*k*(3.5 if plan.landmark=="tree" else (1.24 if crafted and plan.landmark=="ruin" else 1.0))
	if crafted and not compose_march(root,c,decor,from,site):return false
	var oak_path:=decor.path_join("oak.res")
	if not copy_file(ART+"oak.res",oak_path):return false
	var trees:=MultiMesh.new()
	trees.mesh=ResourceLoader.load(oak_path,"Mesh")
	trees.transform_format=MultiMesh.TRANSFORM_3D
	var rng:=RandomNumberGenerator.new()
	rng.seed=int(c.seed)+291
	var transforms:Array[Transform3D]=[]
	var bits:PackedByteArray=geo.control.get_data()
	var n:int=c.height.get_width()
	for i in clampi(roundi(size_m*.48),60,1000):
		var p:=Vector2(rng.randf_range(-.47,.47),rng.randf_range(-.47,.47))*size_m
		if crafted and plan.operations.sightline and p.distance_to(Geometry2D.get_closest_point_to_segment(p,from,site))<size_m*.016:continue
		if p.distance_to(target)<size_m*.08 or p.distance_to(from)<size_m*.035:continue
		var ix:=clampi(roundi((p.x/size_m+.5)*n),0,n-1)
		var iz:=clampi(roundi((p.y/size_m+.5)*n),0,n-1)
		var control:=bits.decode_u32((iz*n+ix)*4)
		var y:=ground(c,p)
		if y<geo.water_y+3 or ((control>>14)&255)>48:continue
		var tree_scale:=rng.randf_range(.40,1.03)*clampf(k,.65,1.2)
		transforms.append(Transform3D(Basis(Vector3.UP,rng.randf_range(-PI,PI)).scaled(Vector3.ONE*tree_scale),Vector3(p.x,y-.2,p.y)))
	trees.instance_count=transforms.size()
	for i in transforms.size():trees.set_instance_transform(i,transforms[i])
	var grove:=MultiMeshInstance3D.new()
	grove.multimesh=trees
	attach(root,root,grove,"WindOaks")
	var player:=CharacterBody3D.new()
	player.set_script(script)
	var birthplace:=Vector3(from.x,ground(c,from)+1.30,from.y)
	player.position=birthplace
	player.set("spawn_position",birthplace)
	var first_turn:=Layout.pos(plan.west_road[0])*size_m*.5
	if crafted and plan.operations.sightline:
		var ash_position:Vector3=root.get_node("GoldenAsh").position
		var towards_tree:=from.direction_to(Vector2(ash_position.x,ash_position.z))
		first_turn=from+(back*.78+towards_tree*.22).normalized()*float(c.span)*.3
		player.set("initial_pitch",atan2(ground(c,site)+marker.get_aabb().size.y*landmark.scale.y*.58-birthplace.y,maxf(1.0,from.distance_to(site))))
	player.set("initial_heading",atan2(from.x-first_turn.x,from.y-first_turn.y))
	player.set("landmark_name",{"ruin":"台地残堡","tree":"台地古树","cairn":"台地石冢"}[plan.landmark])
	player.set("destination",Vector3(target.x,ground(c,target)+8,target.y))
	attach(root,root,player,"Traveler")
	var hit:=CollisionShape3D.new()
	var capsule:=CapsuleShape3D.new()
	capsule.radius=.43
	capsule.height=1.8
	hit.shape=capsule
	attach(root,player,hit,"Capsule")
	var eye:=Camera3D.new()
	eye.position.y=.72
	if crafted:eye.fov=62
	eye.far=maxf(2000,size_m*3)
	eye.environment=(root.get_node("Overview") as Camera3D).environment
	attach(root,player,eye,"Eye")
	var guide:=CanvasLayer.new()
	attach(root,player,guide,"Guide")
	var hint:=Label.new()
	hint.position=Vector2(18,14)
	hint.add_theme_constant_override("outline_size",5)
	hint.add_theme_color_override("font_outline_color",Color("#30332d"))
	attach(root,guide,hint,"Hint")
	return true

# Reuse individual art assets; placement is derived from this candidate's terrain and routes.
static func compose_march(root:Node3D, c:Dictionary, decor:String, spawn:Vector2, goal:Vector2) -> bool:
	for filename in ["pavilion.res","horizon.res","ash.res","march_sky.res","evening_sky.gdshader","river.gdshader"]:
		if not copy_file(ART+filename,decor.path_join(filename)):return false
	var environment:Environment=(root.get_node("Overview") as Camera3D).environment
	var sky_material:=ShaderMaterial.new()
	sky_material.shader=load(decor.path_join("evening_sky.gdshader"))
	var clouds:=load(decor.path_join("march_sky.res")) as Texture2D
	var water_material:=ShaderMaterial.new()
	water_material.shader=load(decor.path_join("river.gdshader"))
	if not sky_material.shader or not water_material.shader or not clouds:return false
	sky_material.set_shader_parameter("clouds",clouds)
	environment.sky.sky_material=sky_material
	environment.fog_enabled=true
	environment.fog_density=.38/c.span
	environment.fog_light_color=Color("#acafa7")
	environment.fog_sky_affect=.18
	var sun:=root.get_node("Sun") as DirectionalLight3D
	sun.light_color=Color("#ffebce")
	sun.rotation_degrees=Vector3(-32,-38,0)
	(root.get_node("River") as MeshInstance3D).material_override=water_material
	var k:=float(c.span)/1536.0
	var forward:=spawn.direction_to(goal)
	var right:=Vector2(-forward.y,forward.x)
	var horizon:=mesh_node(root,root,load(decor.path_join("horizon.res")),"DistantMountains")
	horizon.scale=Vector3.ONE*k
	horizon.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var entry:=spawn+(forward*36-right*14)*k
	var pavilion:=mesh_node(root,root,load(decor.path_join("pavilion.res")),"SpringPavilion")
	pavilion.scale=Vector3.ONE*k
	pavilion.position=Vector3(entry.x,ground(c,entry)-.25*k,entry.y)
	pavilion.rotation.y=atan2(-forward.x,-forward.y)
	var geo:Dictionary=c.geography
	var masonry:=pavilion.mesh.surface_get_material(0) as StandardMaterial3D
	for i in geo.bridges.size():
		var arches:=root.get_node("Crossing%d/StoneArches"%(i+1)) as MeshInstance3D
		var stone:=arches.mesh.surface_get_material(0) as StandardMaterial3D
		stone.albedo_texture=masonry.albedo_texture
		var mesh_path:=decor.path_join("crossing_%02d.res"%(i+1))
		if ResourceSaver.save(arches.mesh,mesh_path,ResourceSaver.FLAG_COMPRESS)!=OK:return false
		arches.mesh.resource_path=mesh_path
	var tree_mesh:=load(decor.path_join("ash.res")) as Mesh
	var tree_height:=tree_mesh.get_aabb().size.y*6.3*k
	var tree_site:=goal+right*float(c.span)*.14
	var bridge_mid:=Vector3.ZERO
	var crossing_eye:=Vector3.ZERO
	if not geo.bridges.is_empty():
		# Frame a bridge opening from the riverbank; find a dry site on the opposite side for the tree.
		var best:=-INF
		var spawn_eye:=Vector3(spawn.x,ground(c,spawn)+1.95,spawn.y)
		for crossing in geo.bridges:
			var deck:PackedVector3Array=crossing.deck
			var curve:=Curve3D.new()
			for p in deck:curve.add_point(p)
			var length:=curve.get_baked_length()
			var center:=curve.sample_baked(length*.5)
			var tangent:=curve.sample_baked(length*.54)-curve.sample_baked(length*.46)
			var lateral:=Vector2(tangent.x,tangent.z).normalized()
			var axis:=Vector2(-lateral.y,lateral.x)
			var mid:=Vector2(center.x,center.z)
			for side:float in [1.0,-1.0]:
				for offset:float in [.08,.125,.16]:
					for bend:float in [-.085,-.045,.045,.085]:
						var p:=mid+(axis*offset*side+lateral*bend)*float(c.span)
						if maxf(absf(p.x),absf(p.y))>c.span*.46:continue
						var terrain_y:=ground(c,p)
						if terrain_y<geo.water_y+2*k:continue
						var facing:=mid.direction_to(p)
						var crown:=Vector3(p.x,terrain_y+tree_height*.7,p.y)
						for distance_factor:float in [1.0,1.6,2.2]:
							var distance:=clampf((center.y-geo.water_y)*distance_factor,40*k,140*k)
							var shore:=mid-facing*distance
							if maxf(absf(shore.x),absf(shore.y))>c.span*.49:continue
							var eye:=Vector3(shore.x,maxf(ground(c,shore),geo.water_y)+3.5*k,shore.y)
							var arch_y:=lerpf(eye.y,crown.y,distance/(distance+mid.distance_to(p)))
							var clearance:=ray_clearance(c,eye,crown)
							var spawn_clear:=ray_clearance(c,spawn_eye,crown)
							var score:=minf(2*k,clearance)*3+minf(2*k,spawn_clear)*2.2
							score-=maxf(0,arch_y-(center.y-5*k))*4
							score-=absf(arch_y-lerpf(geo.water_y,center.y,.65))*.18
							score-=maxf(0,absf(forward.angle_to(spawn.direction_to(p)))-.55)*70*k
							score+=minf(distance,95*k)*.07+right.dot(p-spawn)*.009
							if score>best:
								best=score
								tree_site=p
								bridge_mid=center
								crossing_eye=eye
	var ash:=mesh_node(root,root,tree_mesh,"GoldenAsh")
	ash.scale=Vector3.ONE*k*6.3
	ash.position=Vector3(tree_site.x,ground(c,tree_site),tree_site.y)
	if crossing_eye!=Vector3.ZERO:
		var crown:=ash.position+Vector3.UP*tree_height*.70
		observation(root,environment,"CrossingView",crossing_eye,crown.lerp(bridge_mid,.48),c.span)
	var arrival:=goal-forward*float(c.span)*.084
	observation(root,environment,"GateView",Vector3(arrival.x,ground(c,arrival)+3*k,arrival.y),
		Vector3(goal.x,ground(c,goal)+22*k,goal.y),c.span)
	return true

static func ray_clearance(c:Dictionary, origin:Vector3, target:Vector3) -> float:
	var clearance:=INF
	for i in range(1,48):
		var p:=origin.lerp(target,float(i)/48)
		clearance=minf(clearance,p.y-ground(c,Vector2(p.x,p.z)))
	return clearance

static func observation(root:Node3D, env:Environment, label:String, eye:Vector3, aim:Vector3, span:float) -> void:
	var camera:=Camera3D.new()
	camera.fov=59
	camera.far=maxf(2000,span*4)
	camera.environment=env
	camera.transform=Transform3D(Basis.looking_at(aim-eye),eye)
	attach(root,root,camera,label)
