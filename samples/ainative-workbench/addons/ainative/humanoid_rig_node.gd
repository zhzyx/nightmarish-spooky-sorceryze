@tool
extends RefCounted
## Local node adapter for the existing anatomical template and real ROM checks.
const Rig = preload('res://addons/ainative/rigging.gd')
const KIND = 'humanoid_rig'
const MAX_ATTEMPTS = 3

static func default_parameters() -> Dictionary:
	return {'height_m':1.8}

static func _sagittal_leg_corrections(scene: Node3D) -> Dictionary:
	var corrections: Dictionary = {}
	var skeleton = scene.get_node_or_null('Skeleton3D') as Skeleton3D
	if skeleton == null: return corrections
	for side in ['l','r']:
		var hip = skeleton.get_bone_global_rest(skeleton.find_bone('thigh_'+side)).origin
		for bone_name in ['shin_'+side,'foot_'+side]:
			var point = skeleton.get_bone_global_rest(skeleton.find_bone(bone_name)).origin
			point.x = hip.x
			point.z = hip.z
			corrections[bone_name] = [point.x,point.y,point.z]
	return corrections

static func _failure(code: String, message: String, attempts: Array = []) -> Dictionary:
	return {'error':message,'code':code,'attempts':attempts}

static func run(source_path: String, options: Dictionary, validation_parent: Node, output_path: String) -> Dictionary:
	if source_path.is_empty() or not FileAccess.file_exists(source_path): return _failure('source_missing','源 GLB 已不存在，请重新选择项目中的模型资源。')
	if source_path.get_extension().to_lower() not in ['glb','gltf']: return _failure('source_not_mesh','创建人形17根骨骼只接受 GLB 或内嵌资源的 glTF 模型。')
	if validation_parent == null or not validation_parent.is_inside_tree(): return _failure('validation_parent_missing','当前编辑器无法建立骨骼验收场景。')
	var height = options.get('height_m',1.8)
	if not (height is float or height is int) or not is_finite(float(height)) or float(height)<.2 or float(height)>4.0: return _failure('invalid_height','目标身高必须是 0.2–4 米之间的有限数值。')
	if output_path.get_extension().to_lower()!='tscn' or FileAccess.file_exists(output_path): return _failure('output_exists','角色输出必须是新的 .tscn 文件。')
	var base = Rig.defaults(source_path)
	if options.get('head_review') is Dictionary: base.head_review = options.head_review.duplicate(true)
	base.height_m = float(height)
	base.one_click = true
	base.confirmed_humanoid = false
	base.route = 'standard'
	base.reference_pose = 'T'
	var source_sha = str(base.source_sha256)
	var attempts: Array = []
	var candidate: Node3D = null
	var candidate_report: Dictionary = {}
	for attempt in MAX_ATTEMPTS:
		var parameters = base.duplicate(true)
		if attempt>=1:
			if candidate == null: break
			parameters.joints = _sagittal_leg_corrections(candidate)
		if attempt>=2: parameters.clean_faces = true
		var repair = ['原始模板拟合','校正腿部矢状面后重拟合','清理重复／退化面后重拟合'][attempt]
		var built = Rig.build(source_path,parameters)
		if built.has('error'):
			if candidate == null: return _failure('fit_failed',str(built.error),attempts)
			attempts.append({'attempt':attempt+1,'repair':repair,'error':str(built.error)})
			break
		var scene = built.scene as Node3D
		if not built.get('diagnostics',{}).get('humanoid_front_passed',false):
			scene.free()
			var problems = built.get('diagnostics',{}).get('humanoid_errors',[])
			if candidate == null: return _failure('humanoid_front_required','正视角人形检查未通过，已停止绑骨。\n'+'\n'.join(problems),attempts)
			attempts.append({'attempt':attempt+1,'repair':repair,'error':'修复后的人形门禁未通过，保留上一候选。'})
			break
		validation_parent.add_child(scene)
		var report = Rig.validate_scene(scene)
		attempts.append({'attempt':attempt+1,'repair':repair,'parameters':parameters.duplicate(true),'validation':report.duplicate(true)})
		if candidate != null: candidate.free()
		candidate = scene
		candidate_report = report
		if report.get('passed',false): break
	if candidate == null or not candidate_report.get('scene_valid',false):
		if candidate != null: candidate.free()
		return _failure('invalid_character','骨骼或蒙皮结构无效，无法形成可编辑角色。',attempts)
	if FileAccess.get_sha256(source_path)!=source_sha:
		candidate.free()
		return _failure('source_changed','源模型在绑骨过程中发生变化，请重新运行。',attempts)
	var limited = not candidate_report.get('passed',false)
	var metadata: Dictionary = candidate.get_meta('rigging',{}).duplicate(true)
	metadata.status = 'capability_limited' if limited else 'reviewed_template'
	metadata.quality = 'rom_validation_not_passed' if limited else 'rom_validated'
	metadata.validation = candidate_report.duplicate(true)
	metadata.anatomical_bone_count = 17
	metadata.independent_root = true
	candidate.set_meta('rigging',metadata)
	var stage_error = Rig.stage(candidate,output_path,true)
	candidate.free()
	if not stage_error.is_empty(): return _failure('stage_failed',stage_error,attempts)
	var packed = ResourceLoader.load(output_path,'PackedScene',ResourceLoader.CACHE_MODE_IGNORE)
	var final_scene = packed.instantiate() as Node3D if packed is PackedScene else null
	if final_scene == null: return _failure('reload_failed','无法重新打开最终角色文件。',attempts)
	validation_parent.add_child(final_scene)
	var final_report = Rig.validate_scene(final_scene)
	if not final_report.get('scene_valid',false):
		final_scene.free()
		return _failure('reload_failed','最终角色重载后的骨骼或蒙皮结构无效。',attempts)
	if final_report.get('passed',false)!=candidate_report.get('passed',false):
		final_scene.free()
		return _failure('reload_changed','保存重载前后的 ROM 验收结论不一致，请检查产物后再试。',attempts)
	limited = limited or not final_report.get('passed',false)
	return {
		'scene':final_scene,
		'path':output_path,
		'sha256':FileAccess.get_sha256(output_path),
		'source_sha256':source_sha,
		'capability_limited':limited,
		'passed':final_report.get('passed',false) and not limited,
		'validation':final_report,
		'attempts':attempts,
		'parameters':final_scene.get_meta('rigging',{}).get('parameters',{}).duplicate(true)
	}
