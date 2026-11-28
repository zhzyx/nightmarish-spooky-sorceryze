@tool
extends SubViewportContainer

var viewport_3d := SubViewport.new()
var surface := MeshInstance3D.new()
var camera := Camera3D.new()
var heading := 0.65
var elevation := 0.56
var zoom := 1.0
var span := 512.0
var midpoint := 0.0
var extent := 0.0

func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	viewport_3d.own_world_3d = true
	viewport_3d.render_target_update_mode = SubViewport.UPDATE_ONCE
	viewport_3d.msaa_3d = Viewport.MSAA_2X
	add_child(viewport_3d)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("#253642")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.65
	camera.environment = environment
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	viewport_3d.add_child(camera)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_energy = 1.0
	viewport_3d.add_child(sun)
	viewport_3d.add_child(surface)
	var material := StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.vertex_color_is_srgb = true
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	surface.material_override = material
	resized.connect(_view)

func display_height(height: Image, world_span: float, relief: float, control: Image = null) -> void:
	var paint := control.get_data() if control else PackedByteArray()
	span = world_span
	var step := maxi(3,height.get_width()/100)
	var last := height.get_width() - 1
	var count := ceili(float(last) / step) + 1
	var points := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	var normals := PackedVector3Array()
	points.resize(count * count)
	colors.resize(points.size())
	normals.resize(points.size())
	var low := INF
	var high := -INF
	for z in count:
		for x in count:
			var u := mini(last, x * step)
			var v := mini(last, z * step)
			var h := height.get_pixel(u, v).r
			var i := z * count + x
			points[i] = Vector3((float(u) / last - 0.5) * span, h, (float(v) / last - 0.5) * span)
			var grade := Vector2(height.get_pixel(mini(u + 1, last), v).r - height.get_pixel(maxi(u - 1, 0), v).r,
					height.get_pixel(u, mini(v + 1, last)).r - height.get_pixel(u, maxi(v - 1, 0)).r) / (2.0 * span / last)
			normals[i] = Vector3(-grade.x, 1.0, -grade.y).normalized()
			colors[i] = Color("#557854").lerp(Color("#adad88"), smoothstep(0.12, 0.72, h / relief)).lerp(Color("#807966"), smoothstep(0.30, 0.85, grade.length()))
			if control:
				var layer := paint.decode_u32((v * height.get_width() + u) * 4)
				if ((layer >> 22) & 31) == 2:
					colors[i] = colors[i].lerp(Color("#ba9e6c"), float((layer >> 14) & 255) / 255.0)
			low = minf(low, h)
			high = maxf(high, h)
			if x + 1 < count and z + 1 < count:
				indices.append_array(PackedInt32Array([i, i + 1, i + count, i + 1, i + count + 1, i + count]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = points
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	surface.mesh = mesh
	midpoint = (low + high) * 0.5
	extent = high - low
	_view()

func _view() -> void:
	if not camera.is_inside_tree() or not surface.mesh:
		return
	var distance := maxf(span, extent) * 2.5
	var target := Vector3(0, midpoint, 0)
	camera.position = target + Vector3(sin(heading) * cos(elevation), sin(elevation), cos(heading) * cos(elevation)) * distance
	camera.look_at(target)
	camera.size = maxf(span * 1.42, extent * 1.45) * maxf(1.0, size.y / maxf(size.x, 1.0)) / zoom
	camera.far = distance * 3
	viewport_3d.render_target_update_mode = SubViewport.UPDATE_ONCE

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_LEFT:
		heading -= event.relative.x * 0.008
		elevation = clampf(elevation + event.relative.y * 0.008, 0.10, 1.5)
	elif event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		zoom = clampf(zoom * (1.12 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.12), 0.5, 4.0)
	else:
		return
	_view()
	accept_event()
