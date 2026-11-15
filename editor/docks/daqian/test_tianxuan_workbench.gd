extends SceneTree

## 天璇入口 UI 冒烟：确认 Issue 详情存在「天璇」按钮并能发出请求信号。
## 运行：godot --headless --path . --script editor/docks/daqian/test_tianxuan_workbench.gd

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var inspector_script: Script = load("res://editor/docks/daqian/issue_inspector.gd")
	if inspector_script == null:
		push_error("tianshu-ui-smoke: issue_inspector.gd not found")
		quit(1)
		return
	var inspector: VBoxContainer = inspector_script.new()
	root.add_child(inspector)
	await process_frame
	if inspector.tianxuan == null:
		push_error("tianshu-ui-smoke: tianxuan button missing")
		quit(1)
		return
	if inspector.tianxuan.text != "天璇":
		push_error("tianshu-ui-smoke: unexpected button label: " + inspector.tianxuan.text)
		quit(1)
		return
	var fired := [false]
	inspector.tianxuan_requested.connect(func(): fired[0] = true)
	inspector.tianxuan.pressed.emit()
	if not fired[0]:
		push_error("tianshu-ui-smoke: tianxuan_requested not emitted")
		quit(1)
		return
	print("tianshu-ui-smoke: ok")
	quit(0)
