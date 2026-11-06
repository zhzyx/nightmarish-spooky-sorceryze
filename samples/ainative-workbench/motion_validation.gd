extends SceneTree
const Motion = preload('res://addons/ainative/motion.gd')

func _initialize(): run.call_deferred()

func run():
	var args = OS.get_cmdline_user_args()
	var document = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var before = JSON.stringify(document)
	var normal = Motion.build(document,FileAccess.get_sha256(args[0]))
	var processed = Motion.build(document,FileAccess.get_sha256(args[0]),true,true,.2)
	assert(normal.has('scene') and processed.has('scene'))
	var a = normal.scene.get_meta('motion_processing')
	var b = processed.scene.get_meta('motion_processing')
	assert(a.raw_root_displacement_m==b.raw_root_displacement_m,'Raw root metric changed under processing')
	assert(a.processed_root_horizontal_displacement_m>.1)
	assert(b.processed_root_horizontal_displacement_m<.00001)
	assert(processed.animation.loop_mode==Animation.LOOP_LINEAR)
	assert(b.loop_max_joint_seam_radians>.01) # loop flag does not hide the real seam
	assert(b.smoothing_max_displacement_m>0)
	assert(JSON.stringify(document)==before,'Processing modified immutable source')
	var file = FileAccess.open(args[1],FileAccess.WRITE)
	file.store_string(JSON.stringify({'raw':a,'processed':b,'source_preserved':true,'loop_mode':processed.animation.loop_mode},'  ',true,true))
	file.close()
	print('MOTION_VALIDATION passed real source: root policy, smoothing, loop seam, source immutability')
	normal.scene.free()
	processed.scene.free()
	quit()
