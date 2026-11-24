extends SceneTree
const Templates = preload('res://addons/ainative/locomotion_templates.gd')

func _initialize():
	run.call_deferred()

func material(color: Color) -> StandardMaterial3D:
	var result = StandardMaterial3D.new()
	result.albedo_color = color
	result.roughness = .8
	return result

func add_joint(sk: Skeleton3D, bone: int, mat: Material):
	var attachment = BoneAttachment3D.new()
	attachment.bone_name = sk.get_bone_name(bone)
	sk.add_child(attachment)
	var joint = MeshInstance3D.new()
	var sphere = SphereMesh.new()
	sphere.radius = .035
	sphere.height = .07
	sphere.radial_segments = 12
	sphere.rings = 6
	joint.mesh = sphere
	joint.material_override = mat
	attachment.add_child(joint)
	for child in sk.get_bone_count():
		if sk.get_bone_parent(child)!=bone: continue
		var segment = MeshInstance3D.new()
		var offset = sk.get_bone_rest(child).origin
		var cylinder = CylinderMesh.new()
		cylinder.top_radius = .022
		cylinder.bottom_radius = .022
		cylinder.height = offset.length()
		cylinder.radial_segments = 10
		segment.mesh = cylinder
		segment.position = offset*.5
		segment.quaternion = Quaternion(Vector3.UP,offset.normalized())
		segment.material_override = mat
		attachment.add_child(segment)

func run():
	var args = OS.get_cmdline_user_args()
	if args.size()<2:
		push_error('Usage: clip output_directory [template.tscn]')
		quit(2)
		return
	var clip = args[0]
	var output = args[1]
	var scene_path = args[2] if args.size()>2 else 'res://generated/locomotion/ainative_locomotion_templates.tscn'
	DirAccess.make_dir_recursive_absolute(output)
	var scene = load(scene_path).instantiate() as Node3D
	root.add_child(scene)
	var sk = scene.get_node('Skeleton3D') as Skeleton3D
	var center = material(Color('e8edf2'))
	var left = material(Color('62b5ff'))
	var right = material(Color('ff9b68'))
	for bone in sk.get_bone_count()-1:
		add_joint(sk,bone,left if sk.get_bone_name(bone).ends_with('_l') else (right if sk.get_bone_name(bone).ends_with('_r') else center))
	var ground = MeshInstance3D.new()
	var plane = PlaneMesh.new()
	plane.size = Vector2(5,5)
	ground.mesh = plane
	ground.material_override = material(Color('202b36'))
	scene.add_child(ground)
	var world = WorldEnvironment.new()
	var environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color('101820')
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color('b8c9db')
	environment.ambient_light_energy = .8
	world.environment = environment
	scene.add_child(world)
	var light = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-48,-28,0)
	light.light_energy = 1.5
	scene.add_child(light)
	var camera = Camera3D.new()
	camera.position = Vector3(2.8,1.65,4.2)
	camera.fov = 38
	scene.add_child(camera)
	camera.look_at(Vector3(0,.9,0))
	camera.current = true
	root.size = Vector2i(800,600)
	var player = scene.get_node('AnimationPlayer') as AnimationPlayer
	var phases = [0.0,.25,.5,.75] if clip!='jump' else [0.0,.30,.60,.90]
	player.play(clip)
	for i in phases.size():
		player.seek(phases[i]*player.current_animation_length,true)
		await process_frame
		await RenderingServer.frame_post_draw
		var image = root.get_texture().get_image()
		image.save_png(output.path_join(str(i)+'.png'))
	print('AINATIVE_LOCOMOTION_PREVIEW '+clip+' '+output)
	scene.queue_free()
	await process_frame
	quit()
