extends CharacterBody3D

@export var spawn_position := Vector3.ZERO
@export var destination := Vector3.ZERO
@export var initial_heading := 0.0
@export var initial_pitch := .035
@export var landmark_name := "台地地标"
@export var speed := 6.0
var exploring := true
var yaw := 0.0
var pitch := 0.0

func _ready() -> void:
	floor_snap_length=.65
	floor_max_angle=deg_to_rad(43)
	restart()

func restart() -> void:
	position=spawn_position
	velocity=Vector3.ZERO
	yaw=initial_heading
	pitch=initial_pitch
	rotation.y=yaw
	$Eye.rotation.x=pitch
	exploring=true
	$Eye.current=true
	update_hint()

func update_hint() -> void:
	$Guide/Hint.text=("目标 · "+landmark_name+"\nWASD 行走  ·  Shift 加速  ·  点击捕获鼠标  ·  Tab 鸟瞰  ·  R 回到出生点") if exploring else "鸟瞰  ·  Tab 回到步行"

	if has_node("../GateView"):
		$Guide/Hint.text+="  ·  1 出生点  /  2 旧渡  /  3 堡门" if has_node("../CrossingView") else "  ·  1 出生点  /  3 堡门"

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_TAB:
				exploring=not exploring
				if exploring: $Eye.current=true
				else: get_node("../Overview").current=true
				Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
				update_hint()
			KEY_1,KEY_R: restart()
			KEY_2,KEY_3:
				var camera:=get_node_or_null("../CrossingView" if event.keycode==KEY_2 else "../GateView") as Camera3D
				if camera:
					exploring=false
					camera.current=true
					Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
					update_hint()
					$Guide/Hint.text=("旧渡" if event.keycode==KEY_2 else "堡门")+"  ·  Tab 回到步行  /  1 回到出生点"
			KEY_ESCAPE: Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
	if exploring and event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT and event.pressed:
		Input.mouse_mode=Input.MOUSE_MODE_CAPTURED
	if exploring and event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
		yaw-=event.relative.x*.0023
		pitch=clampf(pitch-event.relative.y*.0023,-1.4,1.4)
		rotation.y=yaw
		$Eye.rotation.x=pitch

func _physics_process(delta: float) -> void:
	var input:=Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),0,float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W)))
	var wish:=basis*(input.normalized() if exploring else Vector3.ZERO)*speed*(2.5 if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
	travel(wish,delta)

func travel(wish:Vector3, delta:float) -> void:
	velocity.x=wish.x
	velocity.z=wish.z
	velocity.y-=22.0*delta
	move_and_slide()
	if position.y < -35: restart()
