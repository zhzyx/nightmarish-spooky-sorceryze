@tool
extends AcceptDialog

var execute: Callable
var repository := LineEdit.new()
var files := Tree.new()
var preview := TextEdit.new()
var message := LineEdit.new()
var status := Label.new()
var send := Button.new()
var inspect := Button.new()
var displayed_module := ""
var displayed_revision := ""
var reload := Button.new()
var snapshot: Dictionary = {}
var busy := false


func _ready() -> void:
	title = "多宝提交"
	get_ok_button().text = "关闭"
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = 520
	add_child(box)
	repository.placeholder_text = "多宝仓库"
	repository.text = OS.get_environment("TIANXUAN_GIT_REPO")
	box.add_child(repository)
	files.hide_root = true
	files.custom_minimum_size.y = 120
	files.item_selected.connect(_preview)
	box.add_child(files)
	preview.editable = false
	preview.custom_minimum_size.y = 115
	box.add_child(preview)
	message.placeholder_text = "提交说明"
	box.add_child(message)
	var actions := HBoxContainer.new()
	box.add_child(actions)
	reload.text = "刷新差异"
	reload.pressed.connect(refresh)
	actions.add_child(reload)
	send.text = "提交所选文件"
	send.pressed.connect(submit)
	actions.add_child(send)
	inspect.name = "InspectNativeRevision"
	inspect.text = "打开提交详情"
	inspect.pressed.connect(_inspect_revision)
	actions.add_child(inspect)
	inspect.hide()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)


func _working(value: bool) -> void:
	busy = value
	send.disabled = value
	reload.disabled = value
	inspect.disabled = value
	message.editable = not value
	repository.editable = not value


func _show(data: Dictionary) -> void:
	snapshot = data
	_set_revision(str(data.branch), str(data.base) if data.get("mode") == "native" else "")
	repository.visible = data.get("mode") != "native"
	files.clear()
	preview.text = ""
	var root := files.create_item()
	for entry in data.files:
		var item := files.create_item(root)
		item.set_cell_mode(0, TreeItem.CELL_MODE_CHECK)
		item.set_editable(0, true)
		item.set_text(0, "%s  %s" % [entry.status, entry.path])
		item.set_metadata(0, entry.path)
		item.set_meta("digest", entry.get("digest", ""))
	var kind := "模块" if data.get("mode") == "native" else "分支"
	status.text = "%s %s @ %s · %d 项磁盘改动" % [kind, data.branch, data.base, data.files.size()]


func refresh() -> void:
	if busy:
		return
	_working(true)
	var result: Dictionary = await execute.call(["workcopy-diff"], {})
	if result.get("ok", false):
		_show(result.data)
	else:
		_set_revision("", "")
		snapshot = {}
		files.clear()
		preview.text = ""
		status.text = str(result.get("error", "读取工作区失败"))
	_working(false)


func _preview() -> void:
	var item := files.get_selected()
	if not item or snapshot.is_empty():
		return
	var path: String = item.get_metadata(0)
	var tree: String = snapshot.tree
	var result: Dictionary = await execute.call(["workcopy-preview"], {"base":snapshot.base, "tree":tree, "path":path, "mode":snapshot.get("mode","git"), "digest":item.get_meta("digest")})
	if snapshot.get("tree") == tree and files.get_selected() and files.get_selected().get_metadata(0) == path:
		preview.text = str(result.data.diff) if result.get("ok", false) else str(result.get("error", "读取差异失败"))


func submit() -> void:
	if busy or snapshot.is_empty():
		return
	var selected := []
	var digests := {}
	for item in files.get_root().get_children():
		if item.is_checked(0):
			selected.append(item.get_metadata(0))
			digests[item.get_metadata(0)] = item.get_meta("digest")
	if selected.is_empty() or message.text.strip_edges().is_empty() or (repository.visible and repository.text.strip_edges().is_empty()):
		status.text = "请选择改动文件并填写提交说明" if not repository.visible else "请选择改动文件并填写仓库和提交说明"
		return
	_working(true)
	var request := {"base":snapshot.base, "tree":snapshot.tree, "branch":snapshot.branch,
			"paths":selected, "digests":digests, "mode":snapshot.get("mode","git"), "message":message.text, "repo":repository.text.strip_edges()}
	var result: Dictionary = await execute.call(["workcopy-submit"], request)
	if result.get("ok", false):
		var receipt: String = result.data.sha
		message.clear()
		var updated: Dictionary = await execute.call(["workcopy-diff"], {})
		if updated.get("ok", false):
			_show(updated.data)
		else:
			snapshot = {}
			files.clear()
			preview.text = ""
		if request.mode == "native":
			_set_revision(str(request.branch), receipt)
		status.text = "多宝已接收 %s @ %s" % [request.branch, receipt]
	else:
		status.text = str(result.get("error", "提交失败"))
	_working(false)


func _set_revision(source: String, revision: String) -> void:
	displayed_module = source
	displayed_revision = revision
	inspect.visible = not revision.is_empty()
	inspect.tooltip_text = revision


func _inspect_revision() -> void:
	var sidebar := EditorInterface.get_base_control().find_child("AIWorkbenchSidebar", true, false)
	var target: Node = sidebar.find_child("issue_revisions", true, false) if sidebar else null
	if not target:
		status.text = "工单版本关联控件不可用"
		return
	hide()
	target.open_revision(displayed_module, displayed_revision)
