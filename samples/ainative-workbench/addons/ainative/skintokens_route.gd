@tool
extends RefCounted
# Independent SkinTokens local auto-rig route: learned skeleton + skinning weights.
# No cloud service, no Blender. This file plus the explicit SkinTokens branches in
# rigging_panel.gd are the entire integration; delete both to roll back without
# touching the existing anatomical template routes.
const Rig = preload('res://addons/ainative/rigging.gd')
const RuntimeMesh = preload('res://addons/ainative/runtime_mesh.gd')

static func run(host: Control, source: String) -> Dictionary:
	var config = OS.get_environment('AINATIVE_SKINTOKENS_CONFIG')
	if config.is_empty():
		return {'error':'未配置 SkinTokens 独立管线。请在本机 JSON 配置中指定 skintokens-cli 与权重目录，并带 AINATIVE_SKINTOKENS_CONFIG 环境变量启动编辑器；详见 tools/ainative/SKINTOKENS.md。'}
	var script = host.host_edit.text.get_base_dir().path_join('skintokens_rig.py')
	var stamp = str(Time.get_ticks_usec())
	var output = host.state_dir.path_join('skintokens-' + stamp + '.glb')
	var report_path = host.state_dir.path_join('skintokens-' + stamp + '.json')
	var lines = []
	var code = OS.execute(host.python_edit.text,[script,'--config',config,'--source',source,'--output',output,'--report',report_path],lines,true)
	if code != 0:
		return {'error':'SkinTokens 本地绑骨失败：\n' + '\n'.join(lines)}
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	if document.append_from_file(output,state) != OK:
		return {'error':'无法解析 SkinTokens 输出 GLB。'}
	var scene = RuntimeMesh.generate(document,state)
	if scene == null:
		return {'error':'SkinTokens 输出不含场景。'}
	var skeletons = scene.find_children('*','Skeleton3D',true,false)
	if skeletons.is_empty():
		scene.free()
		return {'error':'SkinTokens 输出不含 Skeleton3D，绑定无效。'}
	var report = {}
	if FileAccess.file_exists(report_path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(report_path))
		if parsed is Dictionary: report = parsed.get('report',{})
	scene.name = 'Character'
	scene.set_meta('rigging',{
		'source_sha256':FileAccess.get_sha256(source),
		'parameters':{'route':'skintokens','output':output,'output_sha256':FileAccess.get_sha256(output),'report':report_path},
		'algorithm':'skintokens-local',
		'status':'reviewed_skintokens',
		'diagnostics':report,
		'compatibility':'target_bound',
		'quality':'learned_auto_rig_not_reviewed',
	})
	return {'scene':scene,'report':report}

static func stage(scene: Node3D, target: String) -> String:
	if FileAccess.file_exists(target) or target.get_extension()!='tscn':
		return '请选择新的 .tscn 版本；现有文件不可覆盖。'
	if scene.get_meta('rigging',{}).get('algorithm','') != 'skintokens-local':
		return '不是 SkinTokens 绑定结果。'
	var snapshot = scene.duplicate()
	var player = snapshot.get_node_or_null('AnimationPlayer')
	if player != null: player.stop()
	var skeleton = snapshot.get_node_or_null('Skeleton3D')
	if skeleton != null: skeleton.reset_bone_poses()
	Rig.owners(snapshot,snapshot)
	var packed = PackedScene.new()
	var error = packed.pack(snapshot)
	snapshot.free()
	if error != OK or ResourceSaver.save(packed,target) != OK: return '无法保存场景'
	return ''
