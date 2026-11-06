extends SceneTree
const Session = preload('res://addons/ainative/character_session.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = Session.read_object(args[0])
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.python_edit.text = args[3]
	var panel = host.find_child('CharacterWorkbench',true,false)
	panel.local_config = config
	panel.destination.text = args[1]
	panel.reopen()
	assert(is_instance_valid(panel.session.live),panel.message.text)
	var result = {'publication_sha256':FileAccess.get_sha256(args[1]),'targets':[]}
	for i in 3:
		panel.export_target.select(i)
		panel.export_path.text = args[2]+'-'+['ue4','manny','mixamo'][i]+'.glb'
		panel.export_character()
		print(panel.message.text)
		assert(FileAccess.file_exists(panel.export_path.text),panel.message.text)
		var loaded = Session.I.load_scene(panel.export_path.text)
		assert(not loaded.has('error'))
		var sk = Session.I.skeleton(loaded.scene)
		var profile = Session.read_object(config.target_profiles[i])
		assert(sk.get_bone_count()==profile.bones.size())
		for bone in sk.get_bone_count(): assert(str(sk.get_bone_name(bone))==profile.bones[bone].name)
		result.targets.append({'target':['ue4','manny','mixamo'][i],'sha256':FileAccess.get_sha256(panel.export_path.text),'bones':sk.get_bone_count(),'animation_players':loaded.scene.find_children('*','AnimationPlayer',true,false).size()})
		loaded.scene.free()
	var report = FileAccess.open(args[2]+'-readback.json',FileAccess.WRITE)
	report.store_string(JSON.stringify(result,'\t'))
	print(JSON.stringify(result))
	host.free()
	quit()
