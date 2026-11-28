extends SceneTree
## Run with the custom Vulkan Forward+ editor. Exercises world-space PBR page feedback.

var surface: RID
var failures := 0
var camera: Camera3D

func _initialize() -> void:
	run.call_deferred()

func frames(count: int) -> void:
	for frame in count:
		await RenderingServer.frame_post_draw

func measured(limits: Vector4) -> int:
	RenderingServer.runtime_virtual_texture_set_material_feedback_limits(surface,limits)
	var initial := int(RenderingServer.runtime_virtual_texture_get_stats(surface).gpu_feedback_batches)
	for frame in 60:
		await RenderingServer.frame_post_draw
		if int(RenderingServer.runtime_virtual_texture_get_stats(surface).gpu_feedback_batches) >= initial+3:
			break
	return int(RenderingServer.runtime_virtual_texture_get_stats(surface).gpu_feedback_pages)

func check(ok: bool, label: String) -> void:
	if not ok:
		failures += 1
		push_error(label)

func run() -> void:
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(32,32)
	ground.mesh = plane
	root.add_child(ground)
	ground.position = Vector3(-234,-5,-107)
	camera = Camera3D.new()
	root.add_child(camera)
	camera.position = ground.position + Vector3.UP*30.0
	camera.look_at(ground.position,Vector3.FORWARD)
	camera.make_current()
	root.scaling_3d_scale = 1.0
	surface = RenderingServer.runtime_virtual_texture_create()
	RenderingServer.runtime_virtual_texture_configure(surface,RenderingServer.RVT_MATERIAL_TERRAIN_PBR,4,16,2,8)
	RenderingServer.runtime_virtual_texture_set_scenario(surface,ground.get_world_3d().scenario)
	RenderingServer.runtime_virtual_texture_set_material_writer(surface,ground.get_instance(),4)
	# Rotate the local XZ axes relative to world XZ and use negative world coordinates.
	var axes := Basis(Vector3.UP,0.43)*Basis.from_scale(Vector3(32,12,32))
	RenderingServer.runtime_virtual_texture_set_transform(surface,Transform3D(axes,ground.position))
	for msaa in [Viewport.MSAA_DISABLED,Viewport.MSAA_2X]:
		root.msaa_3d = msaa
		for projection in [Camera3D.PROJECTION_ORTHOGONAL,Camera3D.PROJECTION_PERSPECTIVE]:
			camera.projection = projection
			camera.size = 22
			camera.fov = 38
			await frames(24)
			var unfiltered := await measured(Vector4.ZERO)
			check(unfiltered>10,"Unfiltered plane yielded too few feedback pages")
			check((await measured(Vector4(70,0,0,0))) == 0,"Minimum 3D camera distance was ignored")
			check((await measured(Vector4(0,15,0,0))) == 0,"Maximum 3D camera distance was ignored")
			var near_axis := await measured(Vector4(22,60,2,0))
			check(near_axis>0 and near_axis<unfiltered,"World-axis range failed to isolate the middle of the plane")
			var center := root.get_visible_rect().size * 0.5
			var footprint := camera.project_position(center,30).distance_to(camera.project_position(center+Vector2.RIGHT,30))
			RenderingServer.runtime_virtual_texture_set_lod_bias(surface,1.0)
			check((await measured(Vector4(0,0,0,footprint*0.55))) == 0,"The sub-pixel footprint limit was ignored")
			check((await measured(Vector4(0,0,0,footprint*1.5))) > 0,"Mip bias was applied to the footprint filter")
			RenderingServer.runtime_virtual_texture_set_lod_bias(surface,0.0)
			check((await measured(Vector4.ZERO)) == unfiltered,"Clearing limits failed to restore the original footprint")
			print("Material feedback projection=",projection," msaa=",msaa," pages=",unfiltered," chebyshev=",near_axis," footprint_m=",footprint)
	RenderingServer.free_rid(surface)
	print("Material feedback limits failures=",failures)
	quit(int(failures>0))
