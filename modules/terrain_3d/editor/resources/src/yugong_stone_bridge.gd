@tool
extends RefCounted

static func quad(mesh:SurfaceTool, a:Vector3, b:Vector3, c:Vector3, d:Vector3, color:Color) -> void:
	var normal:=(c-a).cross(b-a).normalized()
	for vertex in [a,b,c,a,c,d]:
		mesh.set_color(color)
		mesh.set_normal(normal)
		var uv:Vector2
		if absf(normal.y)>.8:uv=Vector2(vertex.x,vertex.z)
		elif absf(normal.x)>absf(normal.z):uv=Vector2(vertex.z,-vertex.y)
		else:uv=Vector2(vertex.x,-vertex.y)
		mesh.set_uv(uv*.21)
		mesh.add_vertex(vertex)

# The arch stations follow the very same curved, graded center line as the walkable deck.
static func build(deck:PackedVector3Array, width:float, bed:float) -> ArrayMesh:
	var path:=Curve3D.new()
	for p in deck:path.add_point(p)
	var length:=path.get_baked_length()
	var count:=clampi(roundi(length/maxf(9.0,width*3.7)),1,65)
	if count%2==0:count+=1
	var bay:=length/count
	var mesh:=SurfaceTool.new()
	var stone:=StandardMaterial3D.new()
	stone.vertex_color_use_as_albedo=true
	stone.vertex_color_is_srgb=true
	stone.cull_mode=BaseMaterial3D.CULL_DISABLED
	mesh.begin(Mesh.PRIMITIVE_TRIANGLES)
	mesh.set_material(stone)
	for i in count:
		var previous:=PackedVector3Array()
		for j in 17:
			var u:=j/16.0
			var station:=(i+u)*bay
			var p:=path.sample_baked(station)
			p.y-=.09
			var tangent:=path.sample_baked(minf(length,station+.2))-path.sample_baked(maxf(0,station-.2))
			var side:=Vector3(-tangent.z,0,tangent.x).normalized()*width*.95
			var headroom:=maxf(.22,minf(bay*.68,p.y-bed))
			var curve:=sqrt(maxf(0,1-pow((u-.5)/.43,2)))
			var depth:=width*.23+(1-curve)*headroom
			var down:=Vector3.DOWN*depth
			var left:=p-side
			var right:=p+side
			var row:=PackedVector3Array([left,right,left+down,right+down])
			if j>0:
				var tint:=Color("#938570").lerp(Color("#ab9b7d"),float((i+j)%3)*.16)
				quad(mesh,previous[0],row[0],row[2],previous[2],tint)
				quad(mesh,row[1],previous[1],previous[3],row[3],tint)
				quad(mesh,row[2],row[3],previous[3],previous[2],tint.darkened(.14))
			previous=row
		var p:=path.sample_baked(i*bay)
		var tangent:=path.sample_baked(minf(length,i*bay+.3))-p
		tangent.y=0
		tangent=tangent.normalized()
		var side:=Vector3(-tangent.z,0,tangent.x)*width*.96
		var foot:=tangent*bay*.065
		var corners:=[p-side-foot,p+side-foot,p+side+foot,p-side+foot]
		for k in 4:
			var a:Vector3=corners[k]
			var b:Vector3=corners[(k+1)%4]
			quad(mesh,a,b,Vector3(b.x,bed,b.z),Vector3(a.x,bed,a.z),Color("#938570"))
	return mesh.commit()
