extends SceneTree
const P = preload('res://addons/ainative/cloth_panel.gd')
const I = preload('res://addons/ainative/interop.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var built = P.assemble(config)
	if built.has('error'): printerr(built); quit(1); return
	root.add_child(built.scene); built.runner.playing = false
	var error = built.cloth.initialize()
	if error: printerr(error); quit(1); return
	print('hip_rest_y=',I.decode(built.cloth.profile.bones[int(built.cloth.profile.mapping.hips)].global_rest).origin.y)
	var worst = 0.0
	for frame in 180:
		built.runner.sample(frame/60.0)
		if built.cloth.result.has('error'): printerr(built.cloth.result); quit(1); return
		for p in built.cloth.points:
			if not p.is_finite(): printerr('Nonfinite particle'); quit(1); return
		worst = maxf(worst,float(built.cloth.result.get('total_us',0)))
	print(JSON.stringify({'last':built.cloth.result,'worst_us':worst,'frames':built.cloth.frame}))
	quit()
