@tool
extends RefCounted
const Interop = preload('res://addons/ainative/interop.gd')
const Garments = preload('res://addons/ainative/garments.gd')
const FACE_KEYS = ['face_width','jaw_width','nose_width']
const CHANNELS = ['jawOpen','mouthSmile','mouthFrown','browDown','eyeBlink','lookLeft','lookRight','lookUp','lookDown']

static func dna(source_sha: String, body: Dictionary, face: Dictionary, mapping_version: String = 'rain33-v1') -> Dictionary:
	var result = {'schema_version':1,'mapping_version':mapping_version,'source_sha256':source_sha,'body':body.duplicate(true),'face':face.duplicate(true)}
	result.revision = Interop.revision(result)
	return result

static func validate(value: Dictionary) -> String:
	if value.get('schema_version')!=1 or not value.get('mapping_version','') is String or value.mapping_version.is_empty(): return 'Unsupported CharacterDNA version'
	if not value.get('source_sha256','') is String or value.source_sha256.length()!=64: return 'Source SHA256 required'
	for c in value.source_sha256:
		if not c in '0123456789abcdef': return 'Lowercase source SHA256 required'
	if not value.get('body') is Dictionary or not value.get('face') is Dictionary: return 'Body and face objects required'
	var error = Garments.shape_error(value.body)
	if error: return error
	for key in value.face:
		if not key in FACE_KEYS: return 'Unknown face parameter: '+str(key)
		var v = value.face[key]
		if not (v is float or v is int) or not is_finite(float(v)) or v<-.5 or v>.5: return 'Face parameter outside calibrated -0.5..0.5: '+key
	var copy = value.duplicate(true)
	copy.erase('revision')
	if value.get('revision','')!=Interop.revision(copy): return 'CharacterDNA revision mismatch'
	return ''

# Stable per-channel priority; equal priority uses later layer. No bone writes.
# Explicit mouth ownership prevents expression/viseme additive overdrive.
static func arbitrate(layers: Array) -> Dictionary:
	var output = {}
	var owners = {}
	var ordered = layers.duplicate(true)
	for layer in ordered:
		if not layer is Dictionary or not layer.get('channels') is Dictionary: return {'error':'Invalid face layer'}
		var priority = layer.get('priority',0)
		if not (priority is float or priority is int) or not is_finite(float(priority)): return {'error':'Finite layer priority required'}
	# Insertion sort is stable, unlike Array.sort_custom's unspecified ties.
	for i in range(1,ordered.size()):
		var j = i
		while j>0 and ordered[j-1].get('priority',0)>ordered[j].get('priority',0):
			var previous = ordered[j-1]
			ordered[j-1] = ordered[j]
			ordered[j] = previous
			j -= 1
	for layer in ordered:
		if not layer is Dictionary or not layer.get('channels') is Dictionary: return {'error':'Invalid face layer'}
		var weight = layer.get('weight',1.0)
		if not (weight is float or weight is int) or not is_finite(float(weight)) or weight<0 or weight>1: return {'error':'Face layer weight outside 0..1'}
		for key in layer.channels:
			if not key in CHANNELS: return {'error':'Unknown face channel: '+str(key)}
			var v = layer.channels[key]
			if not (v is float or v is int) or not is_finite(float(v)) or v<0 or v>1: return {'error':'Face channel outside 0..1: '+key}
			output[key] = lerpf(output.get(key,0.0),float(v),float(weight))
			owners[key] = layer.get('id','unnamed')
	for pair in [['lookLeft','lookRight'],['lookUp','lookDown'],['mouthSmile','mouthFrown']]:
		var total = output.get(pair[0],0.0)+output.get(pair[1],0.0)
		if total>1:
			for key in pair: output[key] /= total
	return {'channels':output,'owners':owners,'head_neck_writes':0}

static func apply_face(scene: Node3D, value: Dictionary, layers: Array) -> Dictionary:
	var error = validate(value)
	if error: return {'error':error}
	var binding = scene.get_meta('face_binding',{})
	if not binding is Dictionary or binding.get('schema_version')!=1 or binding.get('mapping_version')!=value.mapping_version or binding.get('source_sha256')!=value.source_sha256: return {'error':'FaceBinding source/version mismatch; explicit asset mapping required'}
	if not binding.get('morphs') is Dictionary: return {'error':'FaceBinding semantic morph map required'}
	var mapped_names = {}
	for semantic in binding.morphs:
		if not semantic is String or not binding.morphs[semantic] is String: return {'error':'FaceBinding morph names must be strings'}
		if mapped_names.has(binding.morphs[semantic]): return {'error':'Conflicting semantic morph mapping'}
		mapped_names[binding.morphs[semantic]] = true
	if not binding.get('correctives',[]) is Array: return {'error':'FaceBinding correctives must be an array'}
	for correction in binding.get('correctives',[]):
		if not correction is Dictionary or not correction.get('morph') is String or not correction.get('parameter') in FACE_KEYS or not correction.get('channel') in CHANNELS: return {'error':'Unsupported corrective mapping'}
		if mapped_names.has(correction.morph): return {'error':'Conflicting corrective morph mapping'}
		mapped_names[correction.morph] = true
	var mixed = arbitrate(layers)
	if mixed.has('error'): return mixed
	var required = value.face.keys()+value.body.keys()+mixed.channels.keys()
	var available = []
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		for i in mi.get_blend_shape_count(): available.append(str(mi.mesh.get_blend_shape_name(i)))
	for key in required:
		if not binding.morphs.has(key) or not binding.morphs[key] in available: return {'error':'Unsupported semantic morph: '+str(key)}
	for correction in binding.get('correctives',[]):
		if not correction.morph in available: return {'error':'Corrective morph missing'}
	var writes = 0
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		for i in mi.get_blend_shape_count():
			var raw_name = str(mi.mesh.get_blend_shape_name(i))
			var key = ''
			for semantic in binding.morphs:
				if binding.morphs[semantic]==raw_name: key = semantic
			if key in FACE_KEYS:
				mi.set_blend_shape_value(i,value.face.get(key,0.0))
				writes += 1
			elif key in Garments.SHAPE_KEYS:
				mi.set_blend_shape_value(i,value.body.get(key,1.0)-1.0)
				writes += 1
			elif key in CHANNELS:
				mi.set_blend_shape_value(i,mixed.channels.get(key,0.0))
				writes += 1
			for correction in binding.get('correctives',[]):
				if correction.morph==raw_name:
					mi.set_blend_shape_value(i,value.face.get(correction.parameter,0.0)*mixed.channels.get(correction.channel,0.0))
					writes += 1
	if writes==0: return {'error':'No supported semantic morphs; explicit asset mapping required'}
	scene.set_meta('character_dna',value.duplicate(true))
	scene.set_meta('face_layers',layers.duplicate(true))
	var rest_revision = Interop.revision({'dna':value.revision,'face_binding':binding,'asset_sha256':binding.get('asset_sha256','')})
	scene.set_meta('scalp_binding',{'revision':rest_revision,'pose_revision':Interop.revision({'rest_revision':rest_revision,'channels':mixed.channels}),'mapping_version':value.mapping_version,'geometry_space':'mesh-local; skin follows body skeleton','body_owns_head_neck':true})
	mixed['morph_writes'] = writes
	return mixed

static func mediapipe_layer(frame: Dictionary) -> Dictionary:
	var groups = frame.get('blendshapes',[])
	if not groups is Array or groups.is_empty() or not groups[0] is Array: return {'error':'Missing detected face blendshapes'}
	var values = {}
	for item in groups[0]:
		if not item is Dictionary: return {'error':'Invalid MediaPipe category'}
		values[item.get('name','')] = item.get('coefficient',0.0)
	var channels = {'jawOpen':values.get('jawOpen',0.0)}
	for key in ['mouthSmile','mouthFrown','browDown','eyeBlink']:
		var a = values.get(key+'Left',0.0)
		var b = values.get(key+'Right',0.0)
		if not (a is float or a is int) or not (b is float or b is int): return {'error':'Invalid MediaPipe coefficient'}
		channels[key] = (a+b)*.5
	var layer = {'id':'mediapipe-expression','priority':0,'channels':channels}
	var checked = arbitrate([layer])
	return checked if checked.has('error') else layer

static func garment_cache_key(value: Dictionary, profile: Dictionary, spec: Dictionary) -> String:
	return Interop.revision({'dna':value.revision,'profile':profile.revision,'garment':spec,'fit_version':'reviewed-axis-cage-v1'})

# Always receives immutable base, never the previously fitted assembly.
static func refit(base: Node3D, profile: Dictionary, value: Dictionary, path: String, spec: Dictionary) -> Dictionary:
	var error = validate(value)
	if error: return {'error':error}
	var result = Garments.fit(path,spec,base,profile,value.body)
	if result.has('error'): return result
	# Garments.fit rebuilds surface arrays without morphs. Restore immutable
	# mapped morph meshes on the body; the independent garment retains its new fit.
	if base.has_meta('face_binding'):
		for original in base.find_children('*','MeshInstance3D',true,false):
			if original.get_blend_shape_count()==0: continue
			var derived = result.scene.get_node(base.get_path_to(original))
			var preserved = ArrayMesh.new()
			preserved.blend_shape_mode = original.mesh.blend_shape_mode
			for i in original.mesh.get_blend_shape_count(): preserved.add_blend_shape(original.mesh.get_blend_shape_name(i))
			for surface in original.mesh.get_surface_count():
				var arrays = original.mesh.surface_get_arrays(surface).duplicate(true)
				arrays[Mesh.ARRAY_INDEX] = derived.mesh.surface_get_arrays(surface)[Mesh.ARRAY_INDEX]
				preserved.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays,original.mesh.surface_get_blend_shape_arrays(surface))
				preserved.surface_set_material(surface,original.mesh.surface_get_material(surface))
			derived.mesh = preserved
		var mixed = apply_face(result.scene,value,base.get_meta('face_layers',[]))
		if mixed.has('error'):
			result.scene.free()
			return mixed
	result.scene.set_meta('character_dna',value.duplicate(true))
	result.scene.set_meta('garment_cache_key',garment_cache_key(value,profile,spec))
	result.scene.set_meta('garment_dna_revision',value.revision)
	result.scene.set_meta('garment_fit_stale',false)
	return result

static func stage(scene: Node3D, path: String) -> String:
	if FileAccess.file_exists(path) or path.get_extension()!='tscn': return 'New .tscn version required; overwrite refused'
	if scene.get_meta('garment_fit_stale',false): return 'Garment fit is stale; refit before saving'
	var error = validate(scene.get_meta('character_dna',{}))
	if error: return error
	var player = scene.get_node_or_null('BodyMotion')
	if player is AnimationPlayer and player.assigned_animation!='':
		scene.set_meta('body_playback',{'name':player.assigned_animation,'time':player.current_animation_position,'playing':player.is_playing()})
	preload('res://addons/ainative/rigging.gd').owners(scene,scene)
	var packed = PackedScene.new()
	if packed.pack(scene)!=OK or ResourceSaver.save(packed,path)!=OK: return 'Save failed'
	return ''
