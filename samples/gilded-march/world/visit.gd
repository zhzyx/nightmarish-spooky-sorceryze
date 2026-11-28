extends Node3D

@onready var camera: Camera3D = $Traveler
@onready var terrain: Terrain3D = $Terrain3D
@onready var info: Label = $Guide/Panel/Margin/Info
var recipe: Dictionary
var mode := 1
var walk := false
var yaw := 0.0
var pitch := 0.0
var capture := false
const TITLES := ["南肩望台","金岬全景","七孔旧渡","风冠残堡"]

func ground(x: float, z: float) -> float:
	var y := terrain.data.get_surface_height(Vector3(x,0,z))
	return y if is_finite(y) else 0.0

func walk_eye_height(at: Vector3) -> float:
	var eye_height := ground(at.x, at.z) + 2.0
	if absf(at.x - 125.53) < 78 and absf(at.z + 65) < 3.75 and at.y > 73.0:
		return maxf(eye_height, 76.8)
	return eye_height

func _ready() -> void:
	recipe = JSON.parse_string(FileAccess.get_file_as_string("res://design/astra-layout.json"))
	preset(1)
	capture = not OS.get_environment("MARCH_CAPTURE").is_empty()
	if capture:
		shoot.call_deferred()

func preset(idx: int) -> void:
	mode=idx
	walk=false
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
	var spawn: Dictionary=recipe.spawn
	var keep: Dictionary=recipe.keep
	var eye:=Vector3.ZERO
	var aim:=Vector3.ZERO
	match idx:
		0:
			eye=Vector3(spawn.x,ground(spawn.x,spawn.z)+2.15,spawn.z)
			aim=Vector3(-56,137,-245)
			camera.fov=58
		1:
			eye=Vector3(367,366,579)
			aim=Vector3(-65,86,-142)
			camera.fov=56
		2:
			eye=Vector3(55,ground(55,42)+6,42)
			aim=Vector3(101,81,-97)
			camera.fov=60
		3:
			eye=Vector3(-166,ground(-166,-166)+4.3,-166)
			aim=Vector3(keep.x,ground(keep.x,keep.z)+32,keep.z)
			camera.fov=69
	camera.position=eye
	camera.look_at(aim)
	yaw=camera.rotation.y
	pitch=camera.rotation.x
	overlay()

func overlay() -> void:
	var hints: String = "WASD 行走     鼠标转向     Shift 加速     Tab 释放鼠标" if walk else "1  南肩     2  鸟瞰     3  旧渡     4  堡门     ·     Tab 步行     H 隐藏提示"
	info.text="金岬荒境    /    "+TITLES[mode]+"\n"+hints

func _unhandled_input(e: InputEvent) -> void:
	if capture:return
	if e is InputEventKey and e.pressed and not e.echo:
		match e.keycode:
			KEY_1,KEY_2,KEY_3,KEY_4:preset(e.keycode-KEY_1)
			KEY_H:$Guide.visible=not $Guide.visible
			KEY_TAB:
				if not walk and mode==1:
					preset(0)
				walk=not walk
				if walk:
					camera.position.y = walk_eye_height(camera.position)
				Input.mouse_mode=Input.MOUSE_MODE_CAPTURED if walk else Input.MOUSE_MODE_VISIBLE
				overlay()
			KEY_ESCAPE:
				if walk:
					walk=false
					Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
					overlay()
				else:get_tree().quit()
	if e is InputEventMouseMotion and walk:
		yaw-=e.relative.x*.0022
		pitch=clampf(pitch-e.relative.y*.0022,-1.28,1.33)
		camera.rotation=Vector3(pitch,yaw,0)

func _process(dt: float) -> void:
	if not walk:return
	var v:=Vector2(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).normalized()
	if v==Vector2.ZERO:return
	var next:=camera.position+Basis(Vector3.UP,yaw)*Vector3(v.x,0,v.y)*dt*(24.0 if Input.is_key_pressed(KEY_SHIFT) else 7.0)
	next.x=clampf(next.x,-750,750)
	next.z=clampf(next.z,-750,750)
	next.y = walk_eye_height(next)
	camera.position=next

func shoot() -> void:
	$Guide.hide()
	for i in 4:
		preset(i)
		for frame in 22:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var im:=get_viewport().get_texture().get_image()
		var err:=im.save_png(OS.get_environment("MARCH_CAPTURE").path_join(["01-south","02-overview","03-crossing","04-keep"][i]+".png"))
		print("CAPTURE ",i," ",err," region_count ",terrain.data.get_region_count()," camera ",camera.position)
		if err!=OK or terrain.data.get_region_count()!=16:
			get_tree().quit(1)
			return
	get_tree().quit()
