@tool
extends Control

signal edited(plan: Dictionary)
signal edit_rejected(reason: String)
const Layout=preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout.gd")
const INKS:=[Color("#fff1b7"),Color("#d7a55a"),Color("#63bfdf"),Color("#ffda81"),Color("#e0efe7"),Color("#a3a997")]
var plan:Dictionary={}
var active:=""
var index:=-1
var snapshot:Dictionary={}
var relief_texture:ImageTexture

func set_plan(value:Dictionary, height:Image) -> void:
	plan=value.duplicate(true)
	active=""
	index=-1
	var img:=height.duplicate() as Image
	img.resize(180,180,Image.INTERPOLATE_BILINEAR)
	var terrain:=Image.create_empty(180,180,false,Image.FORMAT_RGB8)
	for z in 180:
		for x in 180:
			var h:=img.get_pixel(x,z).r
			var lighting:=clampf(.48+(img.get_pixel(maxi(x-1,0),z).r-h)*.093+(img.get_pixel(x,maxi(z-1,0)).r-h)*.07,.11,.97)
			terrain.set_pixel(x,z,Color("#26362e").lerp(Color("#92926c"),lighting))
	relief_texture=ImageTexture.create_from_image(terrain)
	queue_redraw()

func bounds() -> Rect2:
	var extent:=maxf(10,minf(size.x-14,size.y-14))
	return Rect2((size-Vector2.ONE*extent)*.5,Vector2.ONE*extent)

func screen(p:Vector2) -> Vector2:
	var r:=bounds()
	return r.position+(p+Vector2.ONE)*.5*r.size

func handles(key:String) -> Array:
	return [plan.spawn] if key=="spawn" else plan[key]

func _draw() -> void:
	if plan.is_empty():return
	draw_texture_rect(relief_texture,bounds(),false)
	for j in Layout.GROUPS.size():
		var key:String=Layout.GROUPS[j]
		var line:=PackedVector2Array()
		if key in ["west_road","east_road"]: line=Layout.road(plan,key)
		elif key=="river": line=Layout.smooth_line(Layout.points(plan.river))
		elif key=="plateau":
			line=Layout.points(plan.plateau)
			line.append(line[0])
		for i in line.size():line[i]=screen(line[i])
		if line.size()>1:draw_polyline(line,INKS[j],2,true)
		var points_array:=handles(key)
		for i in points_array.size():
			var p:=screen(Layout.pos(points_array[i]))
			draw_circle(p,5.6,Color("#263127"))
			draw_circle(p,4.1,INKS[j])
	draw_string(get_theme_default_font(),bounds().position+Vector2(6,16),"北 ↑",HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color.WHITE)

func _gui_input(event:InputEvent) -> void:
	if plan.is_empty():return
	if event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT:
		if event.pressed:
			var best:=10.0
			active=""
			for key in Layout.GROUPS:
				var list:=handles(key)
				for i in list.size():
					var d:=screen(Layout.pos(list[i])).distance_to(event.position)
					if d<best:
						best=d
						active=key
						index=i
			if not active.is_empty():snapshot=plan.duplicate(true)
		elif not active.is_empty():
			active=""
			var issue:=Layout.error(plan)
			if not issue.is_empty():
				plan=snapshot
				edit_rejected.emit(issue)
			elif plan!=snapshot:edited.emit(plan.duplicate(true))
			queue_redraw()
		accept_event()
	elif event is InputEventMouseMotion and not active.is_empty():
		var r:=bounds()
		var p:Vector2=((event.position-r.position)/r.size*2-Vector2.ONE).clamp(Vector2(-.98,-.98),Vector2(.98,.98))
		var handle:Dictionary=handles(active)[index]
		handle.x=Layout.Fieldcraft.coordinate(p.x) if plan.has("operations") else p.x
		handle.z=Layout.Fieldcraft.coordinate(p.y) if plan.has("operations") else p.y
		queue_redraw()
		accept_event()
