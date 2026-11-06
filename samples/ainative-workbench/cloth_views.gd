extends SceneTree
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var config = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var host = load('res://addons/ainative/workbench.gd').new(); root.add_child(host)
	await process_frame
	host.mesh_container.stretch = false; host.viewport.size = Vector2i(1024,1024); host.viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var panel = host.find_child('ClothPanel',true,false)
	panel.configuration.text = args[0]; panel.build()
	if not is_instance_valid(panel.built): printerr(panel.message.text); quit(1); return
	panel.runner.playing = false; panel.runner.sample(119.0/60)
	if panel.cloth.result.has('error'): printerr(panel.cloth.result); quit(1); return
	var bounds = AABB(); var first = true
	for mesh in panel.built.find_children('*','MeshInstance3D',true,false):
		var box = mesh.global_transform*mesh.get_aabb(); bounds = box if first else bounds.merge(box); first = false
	var center = bounds.get_center(); var camera = host.preview_root.get_child(0) as Camera3D
	var fill = OmniLight3D.new(); fill.light_energy = 2; fill.omni_range = 10; host.preview_root.add_child(fill)
	var distance = bounds.size.length()*.5/sin(deg_to_rad(camera.fov*.5))*1.15
	for entry in [['back',Vector3(0,.15,-1)],['side',Vector3(1,.15,0)]]:
		camera.position = center+entry[1].normalized()*distance; camera.look_at(center)
		fill.position = camera.position
		await process_frame; await RenderingServer.frame_post_draw
		host.viewport.get_texture().get_image().save_png(config.output+'-'+entry[0]+'119.png')
	FileAccess.open(config.output+'-views.json',FileAccess.WRITE).store_string(JSON.stringify({'source_scene_sha256':FileAccess.get_sha256(config.scene),'time_seconds':119.0/60,'cache_key':panel.cloth.cache.key,'views':['back','side'],'same_instance':true},'\t'))
	quit()
