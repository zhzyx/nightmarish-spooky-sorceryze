@tool
extends RefCounted
## Local node adapter for the existing anatomical template and real ROM checks.
const Rig = preload('res://addons/ainative/rigging.gd')
const KIND = 'humanoid_rig'
const DEFAULT_MAX_ATTEMPTS = 3
const MAX_ATTEMPTS = 12

static func default_parameters() -> Dictionary:
	return {'height_m':1.8,'max_repair_attempts':DEFAULT_MAX_ATTEMPTS}

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

static func _attempt_count(value) -> int:
	if not (value is float or value is int) or value is bool or not is_finite(float(value)): return -1
	if float(value)!=floor(float(value)): return -1
	var count = int(value)
	return count if count>=1 and count<=MAX_ATTEMPTS else -1

static func _has_chest_issue(report: Dictionary, height: float) -> bool:
	return float(report.get('raise_chest_outward_m',0.0))>height*.025

static func _has_leg_issue(report: Dictionary) -> bool:
	for issue in report.get('issues',[]):
		var text = str(issue)
		if text.contains('腿') or text.contains('踝') or text.contains('足底') or text.contains('foot_') or text.contains('shin_') or text.contains('thigh_'):
			return true
	return false

static func _failure(code: String, message: String, attempts: Array = []) -> Dictionary:
	return {'error':message,'code':code,'attempts':attempts}

static func run(source_path: String, options: Dictionary, validation_parent: Node, output_path: String) -> Dictionary:
	if source_path.is_empty() or not FileAccess.file_exists(source_path): return _failure('source_missing','源 GLB 已不存在，请重新选择项目中的模型资源。')
	if source_path.get_extension().to_lower() not in ['glb','gltf']: return _failure('source_not_mesh','创建人形17根骨骼只接受 GLB 或内嵌资源的 glTF 模型。')
	if validation_parent == null or not validation_parent.is_inside_tree(): return _failure('validation_parent_missing','当前编辑器无法建立骨骼验收场景。')
	var height = options.get('height_m',1.8)
	if not (height is float or height is int) or not is_finite(float(height)) or float(height)<.2 or float(height)>4.0: return _failure('invalid_height','目标身高必须是 0.2–4 米之间的有限数值。')
	var max_attempts = _attempt_count(options.get('max_repair_attempts',DEFAULT_MAX_ATTEMPTS))
	if max_attempts<0: return _failure('invalid_repair_attempts','最大拟合／纠错轮次必须是 1–12 的整数，且包含首次拟合。')
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
	var repair_state = {'joints':{},'clean_faces':false,'shoulder_gate_strength':0.0}
	for attempt in max_attempts:
		var parameters = base.duplicate(true)
		var actions: Array = []
		if attempt>=1:
			if candidate == null: break
			if _has_leg_issue(candidate_report) and repair_state.joints.is_empty():
				repair_state.joints = _sagittal_leg_corrections(candidate)
				actions.append('校正腿部矢状面')
			if _has_chest_issue(candidate_report,float(height)) and float(repair_state.shoulder_gate_strength)<1.0:
				var step = 1.0/float(maxi(1,max_attempts-1))
				repair_state.shoulder_gate_strength = minf(1.0,float(repair_state.shoulder_gate_strength)+step)
				actions.append('收紧肩胸权重边界至 %.2f' % repair_state.shoulder_gate_strength)
			if actions.is_empty() and not repair_state.clean_faces:
				repair_state.clean_faces = true
				actions.append('清理重复／退化面')
			if actions.is_empty(): break
		parameters.joints = repair_state.joints.duplicate(true)
		parameters.clean_faces = repair_state.clean_faces
		parameters.shoulder_gate_strength = repair_state.shoulder_gate_strength
		var repair = '原始模板拟合' if attempt==0 else '；'.join(actions)
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
	var metadata: Dictionary = candidate.get_meta('rigging',{}).duplicate(true)
	metadata.validation = candidate_report.duplicate(true)
	metadata.anatomical_bone_count = 17
	metadata.independent_root = true
	if not candidate_report.get('passed',false):
		metadata.status = 'capability_limited'
		metadata.quality = 'rom_validation_not_passed'
		candidate.set_meta('rigging',metadata)
		var draft_path = output_path.get_basename()+'.failed-draft.tscn'
		var draft_error = Rig.stage(candidate,draft_path,true)
		candidate.free()
		if not draft_error.is_empty(): return _failure('draft_stage_failed','未通过候选的草稿保存失败：'+draft_error,attempts)
		var problems: Array = candidate_report.get('issues',[])+candidate_report.get('unsupported',[])
		var message = '经过 %d 轮有针对性的拟合与修复，候选仍未通过本地实测，已阻断正常角色交付。\n未解决问题：\n%s\n失败草稿仅供手动检查，不是角色输出：%s' % [attempts.size(),'\n'.join(problems),draft_path]
		var failed = _failure('rom_validation_failed',message,attempts)
		failed['draft_path'] = draft_path
		failed['validation'] = candidate_report.duplicate(true)
		failed['max_repair_attempts'] = max_attempts
		return failed
	metadata.status = 'reviewed_template'
	metadata.quality = 'rom_validated'
	candidate.set_meta('rigging',metadata)
	var stage_error = Rig.stage(candidate,output_path)
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
	if not final_report.get('passed',false):
		final_scene.free()
		return _failure('reload_validation_failed','最终角色重载后未通过 ROM 验收，已阻断正常角色交付。',attempts)
	return {
		'scene':final_scene,
		'path':output_path,
		'sha256':FileAccess.get_sha256(output_path),
		'source_sha256':source_sha,
		'capability_limited':false,
		'passed':true,
		'validation':final_report,
		'attempts':attempts,
		'max_repair_attempts':max_attempts,
		'parameters':final_scene.get_meta('rigging',{}).get('parameters',{}).duplicate(true)
	}
