@tool
extends AcceptDialog

var remote_command: Callable
var local_command: Callable
var repository := LineEdit.new()
var branch_name := LineEdit.new()
var baseline := LineEdit.new()
var preserve := CheckBox.new()
var status := Label.new()
var actions: Array[Button] = []
var snapshot: Dictionary = {}
var busy := false


func _ready() -> void:
	title = "多宝分支"
	exclusive = true
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = 490
	add_child(box)
	for field in [[repository,"多宝仓库"], [branch_name,"分支名称"], [baseline,"创建起点（完整提交）"]]:
		var label := Label.new()
		label.text = field[1]
		box.add_child(label)
		box.add_child(field[0])
	repository.text = OS.get_environment("TIANXUAN_GIT_REPO")
	preserve.text = "切换前保存编辑，并用 Git stash 保全工作副本（含未跟踪文件）"
	box.add_child(preserve)
	var row := HBoxContainer.new()
	box.add_child(row)
	for action in [["刷新",refresh],["创建分支",create_branch],["切换",switch_branch],["恢复本分支修改",restore_edits]]:
		var button := Button.new()
		button.text = action[0]
		button.pressed.connect(action[1])
		row.add_child(button)
		actions.append(button)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)
	get_ok_button().text = "关闭"


func _working(value: bool) -> void:
	busy = value
	for button in actions:
		button.disabled = value
	repository.editable = not value
	branch_name.editable = not value
	baseline.editable = not value
	preserve.disabled = value


func _show_state(data: Dictionary) -> void:
	snapshot = data
	status.text = "%s\n当前 %s @ %s" % [data.root, data.branch, data.head]
	if data.dirty:
		status.text += " · 有未提交修改"
	if not str(data.recovery).is_empty():
		status.text += "\n可恢复的保全记录 " + str(data.recovery)


func refresh() -> void:
	if busy:
		return
	_working(true)
	var r: Dictionary = await local_command.call(["status"])
	if r.get("ok", false):
		_show_state(r.data)
		if baseline.text.is_empty():
			baseline.text = str(r.data.head)
	else:
		snapshot = {}
		status.text = str(r.get("error", "当前项目没有可读取的 Git 工作副本"))
	_working(false)


func _target() -> Array:
	return ["--repo-name", repository.text.strip_edges(), "--branch", branch_name.text.strip_edges()]


func create_branch() -> void:
	if busy:
		return
	_working(true)
	var r: Dictionary = await remote_command.call(["branch-create"] + _target() + ["--start", baseline.text.strip_edges()])
	if r.get("ok",false):
		status.text = "多宝已接收 %s @ %s" % [r.data.branch, r.data.sha]
	else:
		status.text = str(r.get("error", "创建失败"))
	_working(false)


func switch_branch() -> void:
	if busy or snapshot.is_empty():
		return
	_working(true)
	var target := branch_name.text.strip_edges()
	var r: Dictionary = await remote_command.call(["branch-tip"] + _target())
	if not r.get("ok",false):
		status.text = str(r.get("error", "无法读取目标分支"))
		_working(false)
		return
	var scripts := EditorInterface.get_script_editor()
	var dirty := not scripts.get_unsaved_files().is_empty() or not EditorInterface.get_unsaved_scenes().is_empty()
	if dirty and preserve.button_pressed:
		scripts.save_all_scripts()
		EditorInterface.save_all_scenes()
		dirty = not scripts.get_unsaved_files().is_empty() or not EditorInterface.get_unsaved_scenes().is_empty()
	if dirty:
		status.text = "有未保存的编辑。请选择保全，或先为未命名场景另存再切换。"
		_working(false)
		return
	var args := ["switch","--branch",target,"--head",str(r.data.sha),"--expected",str(snapshot.branch)+"@"+str(snapshot.head)]
	if preserve.button_pressed:
		args.append("--preserve")
	var switched: Dictionary = await local_command.call(args)
	if switched.get("ok",false):
		_show_state(switched.data)
		EditorInterface.get_resource_filesystem().scan()
	else:
		status.text = str(switched.get("error","切换失败"))
	_working(false)


func restore_edits() -> void:
	if busy or snapshot.is_empty():
		return
	if not EditorInterface.get_script_editor().get_unsaved_files().is_empty() or not EditorInterface.get_unsaved_scenes().is_empty():
		status.text = "请先保存或移开当前未保存的编辑，再恢复保全记录。"
		return
	_working(true)
	var r: Dictionary = await local_command.call(["restore","--expected",str(snapshot.branch)+"@"+str(snapshot.head),"--recovery",str(snapshot.get("recovery",""))])
	if r.get("ok",false):
		_show_state(r.data)
		EditorInterface.get_resource_filesystem().scan()
	else:
		status.text = str(r.get("error","恢复失败"))
	_working(false)
