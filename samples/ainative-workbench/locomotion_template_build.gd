extends SceneTree
const Templates = preload('res://addons/ainative/locomotion_templates.gd')

func _initialize():
	run.call_deferred()

func run():
	var args = OS.get_cmdline_user_args()
	var output = args[0] if not args.is_empty() else 'res://generated/locomotion'
	var error = DirAccess.make_dir_recursive_absolute(output)
	if error!=OK:
		push_error('Cannot create output directory: '+str(error))
		quit(1)
		return
	var scene = Templates.make_scene()
	var player = scene.get_node('AnimationPlayer') as AnimationPlayer
	var library = player.get_animation_library('')
	for clip in Templates.CLIPS:
		var animation = library.get_animation(clip)
		error = ResourceSaver.save(animation,output.path_join(clip+'.tres'))
		if error!=OK:
			push_error('Cannot save '+clip+': '+str(error))
			scene.free()
			quit(1)
			return
	error = ResourceSaver.save(library,output.path_join('ainative_locomotion_library.tres'))
	if error==OK:
		var packed = PackedScene.new()
		error = packed.pack(scene)
		if error==OK: error = ResourceSaver.save(packed,output.path_join('ainative_locomotion_templates.tscn'))
	if error!=OK:
		push_error('Cannot save template scene/library: '+str(error))
		scene.free()
		quit(1)
		return
	var manifest = {
		'schema_version':1,
		'generator':'analytic-foot-trajectory-two-bone-ik-v1',
		'ai_inference':false,
		'third_party_motion_assets':[],
		'bone_count':18,
		'anatomical_bone_count':17,
		'root_bone':'root',
		'coordinate_system':{'up':'+Y','forward':'+Z','units':'metres'},
		'reference_height_m':1.8,
		'fps':Templates.FPS,
		'clips':{
			'walk_in_place':{'duration_s':Templates.duration_for('walk_in_place'),'loop':true},
			'run_in_place':{'duration_s':Templates.duration_for('run_in_place'),'loop':true},
			'jump':{'duration_s':Templates.duration_for('jump'),'loop':false}
		},
		'files':['ainative_locomotion_library.tres','ainative_locomotion_templates.tscn','walk_in_place.tres','run_in_place.tres','jump.tres']
	}
	var file = FileAccess.open(output.path_join('manifest.json'),FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest,'  ',true,true))
	file.close()
	print('AINATIVE_LOCOMOTION_BUILD '+output)
	scene.free()
	quit()
