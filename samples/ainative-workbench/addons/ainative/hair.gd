@tool
extends RefCounted
const I = preload('res://addons/ainative/interop.gd')
const C = preload('res://addons/ainative/customization.gd')

static func validate_source(spec: Dictionary) -> String:
	for key in ['path','sha256','mesh_path','source_sha256']:
		if not spec.get(key) is String: return 'Select a hair source and its provenance.'
	if FileAccess.get_sha256(spec.path)!=spec.sha256 or FileAccess.get_sha256(spec.mesh_path)!=spec.source_sha256: return 'Hair source changed; select the verified version again.'
	var data = JSON.parse_string(FileAccess.get_file_as_string(spec.path))
	if not data is Dictionary or data.get('source_sha256')!=spec.source_sha256: return 'Hair provenance does not match.'
	if data.get('schema_version')!=1 or not data.get('vertices') is Array or not data.get('samples') is Array or data.vertices.size()!=data.samples.size(): return 'Unsupported hair surface.'
	for key in ['columns','rows']:
		if not (data.get(key) is int or data.get(key) is float) or not is_finite(float(data[key])) or data[key]!=int(data[key]) or data[key]<2 or data[key]>128: return 'Invalid guide layout.'
	if data.columns*data.rows!=data.vertices.size(): return 'Invalid guide layout.'
	for point in data.vertices:
		if not point is Array or point.size()!=3: return 'Invalid hair point.'
		for v in point:
			if not (v is float or v is int) or not is_finite(float(v)): return 'Invalid hair coordinate.'
	return verify_mapping(data,spec.mesh_path)

static func accessor_offset(doc: Dictionary,index: int,element: int,expected: String,bytes: int,binary_size: int) -> int:
	if index<0 or index>=doc.get('accessors',[]).size(): return -1
	var accessor = doc.accessors[index]
	if accessor.get('type')!=expected or element<0 or element>=accessor.get('count',0): return -1
	var view_index = int(accessor.get('bufferView',-1))
	if view_index<0 or view_index>=doc.get('bufferViews',[]).size(): return -1
	var view = doc.bufferViews[view_index]
	var stride = int(view.get('byteStride',bytes))
	var relative = int(accessor.get('byteOffset',0))+element*stride
	var offset = int(view.get('byteOffset',0))+relative
	if stride<bytes or relative<0 or relative+bytes>int(view.get('byteLength',0)) or offset<0 or offset+bytes>binary_size: return -1
	return offset

static func verify_mapping(data: Dictionary,path: String) -> String:
	var raw = FileAccess.get_file_as_bytes(path)
	if raw.size()<28 or raw.decode_u32(0)!=0x46546c67 or raw.decode_u32(4)!=2: return 'Unsupported original hair mesh.'
	var json_size = raw.decode_u32(12)
	if json_size+28>raw.size(): return 'Invalid original hair mesh.'
	var doc = JSON.parse_string(raw.slice(20,20+json_size).get_string_from_utf8())
	if not doc is Dictionary or not doc.get('meshes') is Array or doc.meshes.is_empty(): return 'Invalid original hair mesh.'
	var primitives = doc.meshes[0].get('primitives',[])
	if primitives.size()!=1: return 'This reviewed source adapter requires one mesh primitive.'
	var primitive = primitives[0]
	var positions = int(primitive.get('attributes',{}).get('POSITION',-1))
	var indices = int(primitive.get('indices',-1))
	if positions<0 or indices<0 or positions>=doc.get('accessors',[]).size() or indices>=doc.accessors.size(): return 'Source position/index mapping missing.'
	if int(doc.accessors[positions].get('componentType',0))!=5126 or not int(doc.accessors[indices].get('componentType',0)) in [5123,5125]: return 'Unsupported source accessor encoding.'
	var binary = raw.slice(28+json_size)
	var index_bytes = 2 if doc.accessors[indices].componentType==5123 else 4
	for i in data.samples.size():
		var sample = data.samples[i]
		if not sample is Dictionary: return 'Invalid source triangle mapping.'
		var id = sample.get('source_triangle',-1)
		if not (id is int or id is float) or not is_finite(float(id)) or id<0 or id!=int(id): return 'Invalid source triangle mapping.'
		var weights = sample.get('barycentric',[])
		if not weights is Array or weights.size()!=3: return 'Invalid source barycentric mapping.'
		var reconstructed = Vector3.ZERO
		var sum = 0.0
		for corner in 3:
			var weight = weights[corner]
			if not (weight is int or weight is float) or not is_finite(float(weight)) or weight<-.00001 or weight>1.00001: return 'Invalid source barycentric mapping.'
			sum += weight
			var io = accessor_offset(doc,indices,int(id)*3+corner,'SCALAR',index_bytes,binary.size())
			if io<0: return 'Source triangle is outside the original mesh.'
			var vertex = binary.decode_u16(io) if index_bytes==2 else binary.decode_u32(io)
			var po = accessor_offset(doc,positions,vertex,'VEC3',12,binary.size())
			if po<0: return 'Source vertex is outside the original mesh.'
			reconstructed += Vector3(binary.decode_float(po),binary.decode_float(po+4),binary.decode_float(po+8))*weight
		var point = data.vertices[i]
		if absf(sum-1.0)>.00001 or reconstructed.distance_to(Vector3(point[0],point[1],point[2]))>.00001: return 'Derived hair no longer matches its original source triangles.'
	return ''

static func bind(scene: Node3D, spec: Dictionary) -> Dictionary:
	var error = validate_source(spec)
	if error: return {'error':error}
	var scalp = scene.get_meta('scalp_binding',{})
	if scalp.get('revision','').is_empty(): return {'error':'Apply the face shape before binding hair.'}
	if spec.has('binding_revision') and spec.binding_revision!=scalp.revision: return {'error':'Scalp changed; rebind hair before loading this version.'}
	var sk = I.skeleton(scene)
	var face_binding = scene.get_meta('face_binding',{})
	if sk==null or not face_binding.get('body_mapping') is Dictionary: return {'error':'Mapped head skeleton required.'}
	var head_index = sk.find_bone(face_binding.body_mapping.head)
	if head_index<0: return {'error':'Mapped head bone is missing.'}
	var head_mesh: MeshInstance3D
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		if str(mi.name)=='GEO-rain-head': head_mesh = mi
	if head_mesh==null: return {'error':'Reviewed scalp surface is missing.'}
	var points = head_mesh.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX].duplicate()
	for shape in head_mesh.get_blend_shape_count():
		var amount = head_mesh.get_blend_shape_value(shape)
		if amount==0: continue
		var target = head_mesh.mesh.surface_get_blend_shape_arrays(0)[shape][Mesh.ARRAY_VERTEX]
		var base = head_mesh.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		for i in points.size(): points[i] += (target[i]-base[i])*amount
	var bounds = AABB(points[0],Vector3.ZERO)
	for p in points: bounds = bounds.expand(p)
	var data = JSON.parse_string(FileAccess.get_file_as_string(spec.path))
	var head_rest = sk.get_bone_global_rest(head_index)
	var fitted = []
	var roots = []
	var width = bounds.size.x*.5
	var top = bounds.end.y
	var rear = bounds.position.z
	var cap_vertices = []
	var cap_indices = []
	var cap_source_triangles = []
	var scalp_triangles = head_mesh.mesh.surface_get_arrays(0)[Mesh.ARRAY_INDEX]
	for index in range(0,scalp_triangles.size(),3):
		var polygon = []
		for j in 3:
			var p = points[scalp_triangles[index+j]]
			var q = points[scalp_triangles[index+(j+1)%3]]
			var dp = cap_distance(p,bounds)
			var dq = cap_distance(q,bounds)
			if dp>=0: polygon.append(p)
			if (dp>=0)!=(dq>=0): polygon.append(p.lerp(q,dp/(dp-dq)))
		if polygon.size()<3: continue
		cap_source_triangles.append(index/3)
		var first = cap_vertices.size()
		for p in polygon:
			var cap_center = Vector3(bounds.get_center().x,top-.10,bounds.get_center().z)
			var raised = p+(p-cap_center).normalized()*.006
			var local = head_rest.affine_inverse()*raised
			cap_vertices.append([local.x,local.y,local.z])
		for j in range(1,polygon.size()-1): cap_indices.append_array([first,first+j,first+j+1])
	for c in int(data.columns):
		var x = (float(c)/(data.columns-1)*2-1)*width*.85
		var desired = Vector3(x,top-.035,rear+.025)
		var best = 0
		var best_triangle = 0
		var best_bary = [1.0,0.0,0.0]
		var scalp_point = points[0]
		var distance = INF
		for i in range(0,scalp_triangles.size(),3):
			var closest = triangle_projection(desired,points[scalp_triangles[i]],points[scalp_triangles[i+1]],points[scalp_triangles[i+2]])
			var d = closest.point.distance_squared_to(desired)
			if d<distance:
				distance = d
				best = scalp_triangles[i]
				best_triangle = i/3
				best_bary = closest.bary
				scalp_point = closest.point
		roots.append({'scalp_vertex':best,'scalp_triangle':best_triangle,'barycentric':best_bary,'position':[scalp_point.x,scalp_point.y,scalp_point.z],'guide':c})
		var cap_center = Vector3(bounds.get_center().x,top-.10,bounds.get_center().z)
		var root: Vector3 = scalp_point+(scalp_point-cap_center).normalized()*.003
		for r in int(data.rows):
			var t = float(r)/(data.rows-1)
			var source = data.vertices[r*int(data.columns)+c]
			var start = data.vertices[c]
			var p = root+Vector3((source[0]-start[0])*.30,-t*.27,-(source[2]-start[2])*.16-t*.04-.006*smoothstep(0,.2,t))
			var local = head_rest.affine_inverse()*p
			fitted.append([local.x,local.y,local.z])
	var runtime = preload('res://addons/ainative/hair_runtime.gd').new()
	runtime.name = 'IndependentHair'
	runtime.set_meta('authored_scalp_cap',{'vertices':cap_vertices,'indices':cap_indices,'source_scalp_triangles':cap_source_triangles,'origin':'Author clipped/interpolated current morphed scalp triangles; not AI geometry'})
	runtime.set_meta('hair_data',{'spec':spec.duplicate(true),'scalp_revision':scalp.revision,'head_bone':face_binding.body_mapping.head,'vertices':fitted,'roots':roots,'columns':int(data.columns),'rows':int(data.rows),'lod':0,'cards':false,'hat':false,'source_kind':data.source_kind,'limitations':data.limitations,'head_neck_writes':0})
	var config = runtime.get_meta('hair_data')
	config.source_record = data.duplicate(true)
	config.binding_digest = binding_digest(config,runtime.get_meta('authored_scalp_cap'))
	runtime.set_meta('hair_data',config)
	var old = scene.get_node_or_null('IndependentHair')
	if old!=null:
		scene.remove_child(old)
		old.free()
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		if str(mi.name)=='GEO-rain-hair_main':
			mi.visible = false
			mi.set_meta('hair_hidden_reason','Independent generated posterior hairstyle replaces original Rain static hair')
	scene.add_child(runtime)
	scene.set_meta('hair_binding',{'scalp_revision':scalp.revision,'source_sha256':spec.source_sha256,'selection_sha256':spec.sha256,'roots':roots,'strands':false})
	return {'hair':runtime,'root_count':roots.size(),'scalp_revision':scalp.revision}

static func cap_distance(p: Vector3,bounds: AABB) -> float:
	var posterior = 1.0-smoothstep(bounds.position.z,bounds.end.z,p.z)
	return p.y-(bounds.end.y-.055-.04*posterior)

static func triangle_projection(p: Vector3,a: Vector3,b: Vector3,c: Vector3) -> Dictionary:
	var ab = b-a
	var ac = c-a
	var ap = p-a
	var denominator = ab.dot(ab)*ac.dot(ac)-ab.dot(ac)*ab.dot(ac)
	if absf(denominator)>.000000000001:
		var v = (ac.dot(ac)*ap.dot(ab)-ab.dot(ac)*ap.dot(ac))/denominator
		var w = (ab.dot(ab)*ap.dot(ac)-ab.dot(ac)*ap.dot(ab))/denominator
		if v>=0 and w>=0 and v+w<=1: return {'point':a+ab*v+ac*w,'bary':[1-v-w,v,w]}
	var best = {'point':a,'bary':[1.0,0.0,0.0]}
	var distance = p.distance_squared_to(a)
	var vertices = [a,b,c]
	for i in 3:
		var next = (i+1)%3
		var edge = vertices[next]-vertices[i]
		var t = clampf((p-vertices[i]).dot(edge)/maxf(edge.length_squared(),.000000000001),0,1)
		var q = vertices[i]+edge*t
		if q.distance_squared_to(p)<distance:
			distance = q.distance_squared_to(p)
			var bary = [0.0,0.0,0.0]
			bary[i] = 1-t
			bary[next] = t
			best = {'point':q,'bary':bary}
	return best

static func binding_digest(data: Dictionary,cap: Dictionary) -> String:
	return I.revision({'scalp':data.get('scalp_revision'),'source':data.get('spec',{}).get('source_sha256'),'selection':data.get('spec',{}).get('sha256'),'head':data.get('head_bone'),'vertices':data.get('vertices'),'roots':data.get('roots'),'columns':data.get('columns'),'rows':data.get('rows'),'cap':cap,'source_record':data.get('source_record')})

static func runtime_error(scene: Node3D,data,cap) -> String:
	if not data is Dictionary or not cap is Dictionary: return 'Invalid saved hair binding.'
	for key in ['columns','rows','lod']:
		var v = data.get(key,-1)
		if not (v is int or v is float) or not is_finite(float(v)) or v!=int(v): return 'Invalid saved hair layout.'
	if data.lod<0 or data.lod>2 or data.columns<2 or data.columns>128 or data.rows<2 or data.rows>128: return 'Invalid saved hair layout.'
	if not data.get('hat') is bool or not data.get('cards') is bool: return 'Invalid saved hair display settings.'
	if not data.get('vertices') is Array or data.vertices.size()!=data.columns*data.rows or not data.get('roots') is Array or data.roots.size()!=data.columns: return 'Invalid saved hair guides.'
	if not cap.get('vertices') is Array or not cap.get('indices') is Array or cap.indices.size()%3!=0: return 'Invalid saved scalp cap.'
	for points in [data.vertices,cap.vertices]:
		for p in points:
			if not p is Array or p.size()!=3: return 'Invalid saved hair point.'
			for v in p:
				if not (v is int or v is float) or not is_finite(float(v)): return 'Invalid saved hair coordinate.'
	for i in cap.indices:
		if not (i is int or i is float) or i!=int(i) or i<0 or i>=cap.vertices.size(): return 'Invalid saved scalp triangle.'
	var sk = I.skeleton(scene)
	if sk==null or not data.get('head_bone') is String or sk.find_bone(data.head_bone)<0: return 'Saved head binding is missing.'
	if not data.get('spec') is Dictionary or not data.get('source_record') is Dictionary: return 'Saved source provenance is missing.'
	if data.get('scalp_revision')!=scene.get_meta('scalp_binding',{}).get('revision'): return 'Scalp changed; rebind hair.'
	var count = -1
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		if str(mi.name)=='GEO-rain-head': count = mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX].size()
	for root in data.roots:
		if not root is Dictionary or not (root.get('scalp_vertex') is int or root.get('scalp_vertex') is float) or root.scalp_vertex!=int(root.scalp_vertex) or root.scalp_vertex<0 or root.scalp_vertex>=count: return 'Saved scalp root is invalid.'
	if data.get('binding_digest')!=binding_digest(data,cap): return 'Saved hair binding integrity mismatch.'
	return ''

static func stage(scene: Node3D, path: String) -> String:
	if scene.get_meta('hair_binding',{}).get('scalp_revision')!=scene.get_meta('scalp_binding',{}).get('revision'): return 'Scalp changed; rebind before saving.'
	var hair = scene.get_node_or_null('IndependentHair')
	if hair==null: return 'Bind hair before saving.'
	var data = hair.get_meta('hair_data')
	var error = runtime_error(scene,data,hair.get_meta('authored_scalp_cap'))
	if error: return error
	if data.spec.has('path') or data.spec.has('mesh_path'):
		error = validate_source(data.spec)
		if error: return error
	var portable = scene.duplicate()
	var portable_hair = portable.get_node('IndependentHair')
	var embedded = data.duplicate(true)
	embedded.spec.erase('path')
	embedded.spec.erase('mesh_path')
	portable_hair.set_meta('hair_data',embedded)
	error = C.stage(portable,path)
	portable.free()
	return error
