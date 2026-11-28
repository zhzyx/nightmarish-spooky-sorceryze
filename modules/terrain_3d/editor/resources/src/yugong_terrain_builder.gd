@tool
extends RefCounted

const Layout = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout.gd")

static func grid(line: PackedVector2Array, n: int) -> PackedVector2Array:
	var out:=PackedVector2Array()
	for p in line:
		out.append((p+Vector2.ONE)*(n*0.5))
	return out

# A narrow raster around each polyline stores lateral distance to the nearest segment.
static func corridor(line: PackedVector2Array, n: int, radius: float) -> Dictionary:
	var dist:=PackedFloat32Array()
	dist.resize(n*n)
	dist.fill(radius*radius)
	for i in line.size()-1:
		var a:=line[i]
		var b:=line[i+1]
		var step:=b-a
		var squared:=step.length_squared()
		if squared<0.000001: continue
		var low:Vector2=a.min(b)-Vector2.ONE*radius
		var high:Vector2=a.max(b)+Vector2.ONE*radius
		for z in range(maxi(0,floori(low.y)),mini(n,ceili(high.y)+1)):
			for x in range(maxi(0,floori(low.x)),mini(n,ceili(high.x)+1)):
				var id:=z*n+x
				var delta:=Vector2(x,z)-a
				var u:=clampf(delta.dot(step)/squared,0,1)
				var dd:=(delta-step*u).length_squared()
				if dd<dist[id]:
					dist[id]=dd
	return {"dist":dist}

static func base(plan: Dictionary, seed_value: int, relief: float, goal: float, start: float) -> Image:
	var n:=192
	var noise:=FastNoiseLite.new()
	noise.seed=seed_value
	noise.frequency=2.4
	noise.fractal_octaves=5
	var rim:=Layout.points(plan.plateau)
	var valleys:=PackedFloat32Array()
	valleys.resize(n*n)
	var spawn:=Layout.pos(plan.spawn)
	var open_start:bool=plan.get("operations",{}).get("sightline",false)
	for z in n:
		for x in n:
			var p:=Vector2(x,z)*2.0/n-Vector2.ONE
			var f:=noise.get_noise_2dv(p)
			var y:=relief*(.32+.23*f+.065*sin(p.x*6+p.y*2))
			for ridge: Dictionary in plan.ridges:
				var v:=(p-Layout.pos(ridge))/float(ridge.radius)
				y+=relief*.65*float(ridge.height)*exp(-v.length_squared()*1.6)*(.85+.28*f)
			var pd:=2.0
			for i in rim.size():
				pd=minf(pd,p.distance_to(Geometry2D.get_closest_point_to_segment(p,rim[i],rim[(i+1)%rim.size()])))
			var inside:=Geometry2D.is_point_in_polygon(p,rim)
			var mesa:=1.0 if inside else 1.0-smoothstep(0,.14,pd)
			y=lerpf(y,goal+relief*.014*f,mesa)
			y=lerpf(start,y,smoothstep(.035 if open_start else .014,.24 if open_start else .085,p.distance_to(spawn)))
			valleys[z*n+x]=clampf(y,0,relief)
	return Image.create_from_data(n,n,false,Image.FORMAT_RF,valleys.to_byte_array())

static func build(plan: Dictionary, seed_value: int, span: float, relief: float) -> Dictionary:
	var n:=1024 if span>=256 else (512 if span>=128 else 256)
	var spacing:=span/n
	var river:=grid(Layout.smooth_line(Layout.points(plan.river)),n)
	var ops:Dictionary=plan.get("operations",{})
	var rw:=maxf(2.0,n*.009*float(ops.get("river_width",100))/100)
	var bank:=rw*4.4
	var river_field:=corridor(river,n,bank)
	var river_sq:PackedFloat32Array=river_field.dist
	var roads:Array[Dictionary]=[]
	var origin:Vector2=(Layout.pos(plan.spawn)+Vector2.ONE)*(n*.5)
	var direction:Vector2=(Layout.plateau_center(plan)-Layout.pos(plan.spawn))*(n*.5)
	var grade:=direction/direction.length_squared()
	var road_width:=maxf(n*.0031*float(ops.get("road_width",100))/100,1.8)
	for key in ["west_road","east_road"]:
		var line:=grid(Layout.road(plan,key),n)
		var field:=corridor(line,n,road_width*8)
		field.line=line
		roads.append(field)
	var ridge_width:=n*.057
	var ridge_dist:=PackedFloat32Array()
	if plan.has("ridge_road"):
		var ridge_line:=grid(Layout.road(plan,plan.ridge_road),n)
		ridge_dist=corridor(ridge_line,n,ridge_width).dist
	var start:=relief*.35
	var goal:=start+minf(relief*.43*float(ops.get("plateau_rise",100))/100,direction.length()*spacing*.21)
	var sea:=relief*.125
	var protect_view:bool=ops.get("sightline",false)
	var height:=base(plan,seed_value,relief,goal,start)
	height.resize(n,n,Image.INTERPOLATE_CUBIC)
	var hs:=height.get_data().to_float32_array()
	var grit:=FastNoiseLite.new()
	grit.seed=seed_value+17
	grit.frequency=.042
	var mask:=PackedFloat32Array()
	mask.resize(n*n)
	var left:PackedFloat32Array=roads[0].dist
	var right:PackedFloat32Array=roads[1].dist
	var bridges:Array[Dictionary]=[]
	for road in roads:
		bridges.append_array(crossings(road,river_sq,n,rw*2.6,start,goal,span,origin,grade))
	for z in n:
		for x in n:
			var id:=z*n+x
			var rd:=sqrt(river_sq[id])
			var river_mix:=smoothstep(rw*.82,bank,rd)
			var y:=hs[id]+relief*.016*grit.get_noise_2d(x*spacing,z*spacing)
			var bed:=sea-relief*.027+relief*.035*smoothstep(rw*.5,rw*1.3,rd)
			y=lerpf(bed,y,river_mix)
			var d:=sqrt(minf(left[id],right[id]))
			var delta:=Vector2(x,z)-origin
			var u:=clampf(delta.dot(grade),0,1)
			var road_y:=lerpf(start,goal,u)
			if not ridge_dist.is_empty() and ridge_dist[id]<ridge_width*ridge_width:
				# Build up both flanks under the inland road. Leave riverbanks and bridge approaches open.
				var lateral:=sqrt(ridge_dist[id])
				var flank:=road_y-lateral*spacing*.35-relief*.009
				var fill:=(1-smoothstep(road_width,ridge_width,lateral))*smoothstep(bank*.55,bank,rd)
				y=lerpf(y,maxf(y,flank),fill)
			if protect_view:
				# Keep the foreground open, then taper the cut toward the landmark.
				var lateral:=delta.distance_to(direction*u)
				var margin:=lerpf(n*.070,n*.034,u)
				var ceiling:=road_y+lerpf(.6,maxf(2.0,span*.007),u)
				y=lerpf(minf(y,ceiling),y,smoothstep(margin,margin*3.2,lateral))
			var dry:=smoothstep(rw*1.18,rw*1.67,rd)
			y=lerpf(y,road_y,(1.0-smoothstep(road_width*1.3,road_width*8,d))*dry)
			hs[id]=y
			mask[id]=(1.0-smoothstep(road_width*.77,road_width*1.40,d))*dry
	var bits:=PackedByteArray()
	var rgba:=PackedByteArray()
	bits.resize(n*n*4)
	rgba.resize(n*n*4)
	for z in n:
		for x in n:
			var id:=z*n+x
			var slope:=Vector2(hs[z*n+mini(x+1,n-1)]-hs[z*n+maxi(x-1,0)],hs[mini(z+1,n-1)*n+x]-hs[maxi(z-1,0)*n+x]).length()/(2*spacing)
			var path:=mask[id]
			var layer:=2 if path>.12 else 1
			var blend:=path if layer==2 else smoothstep(.30,.84,slope)
			bits.encode_u32(id*4,(layer<<22)|(roundi(blend*255)<<14))
			var variation:=grit.get_noise_2d(x*spacing*.15,z*spacing*.15)
			rgba[id*4]=roundi(221+16*variation)
			rgba[id*4+1]=roundi(217+18*variation)
			rgba[id*4+2]=roundi(187+19*variation+16*blend)
			rgba[id*4+3]=128
	height=Image.create_from_data(n,n,false,Image.FORMAT_RF,hs.to_byte_array())
	return {"height":height,"control":Image.create_from_data(n,n,false,Image.FORMAT_RF,bits),
		"color":Image.create_from_data(n,n,false,Image.FORMAT_RGBA8,rgba),"bridges":bridges,"fieldcraft":not ops.is_empty(),
		"water_y":sea,"water_width":rw*spacing,"road_width":road_width*spacing,"spawn_y":start,"goal_y":goal}

static func crossings(road: Dictionary, distances: PackedFloat32Array, n: int, limit: float, start: float, goal: float, span: float, origin: Vector2, grade: Vector2) -> Array[Dictionary]:
	var result:Array[Dictionary]=[]
	var line:PackedVector2Array=road.line
	var previous:=Vector3.ZERO
	var has_previous:=false
	var deck:=PackedVector3Array()
	for i in line.size()-1:
		var length:=line[i].distance_to(line[i+1])
		var steps:=maxi(1,ceili(length/1.5))
		for j in steps:
			var u:=float(j)/steps
			var p:=line[i].lerp(line[i+1],u)
			var idx:=clampi(roundi(p.y),0,n-1)*n+clampi(roundi(p.x),0,n-1)
			var world:=(p/n-Vector2.ONE*.5)*span
			var point:=Vector3(world.x,lerpf(start,goal,clampf((p-origin).dot(grade),0,1))+.06,world.y)
			if distances[idx]<=limit*limit:
				if deck.is_empty() and has_previous:deck.append(previous)
				deck.append(point)
			elif not deck.is_empty():
				deck.append(point)
				if deck.size()>2: result.append({"deck":deck})
				deck=PackedVector3Array()
			previous=point
			has_previous=true
	if deck.size()>2: result.append({"deck":deck})
	return result
