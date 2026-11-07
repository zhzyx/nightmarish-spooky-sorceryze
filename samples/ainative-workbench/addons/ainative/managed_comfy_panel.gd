@tool
extends VBoxContainer

var host
var runtime_path: LineEdit
var notice: Label
var autostart: CheckButton
var chooser: FileDialog
var session_id = ""
var lease_path = ""
var heartbeat_elapsed = 0.0
var manager_root = ""
var last_report: Dictionary = {}

func initialize(workbench, settings: ConfigFile):
	host = workbench
	name = 'ManagedLocalMesh'
	session_id = str(OS.get_process_id()) + '-' + Crypto.new().generate_random_bytes(12).hex_encode()
	if manager_root.is_empty(): manager_root = OS.get_cache_dir().path_join('godot/ainative-managed-comfy')
	var heading = Label.new()
	heading.text = '本机网格模型 · 由引擎管理'
	add_child(heading)
	runtime_path = host.line(self, '选择已有 ComfyUI 本机运行库', str(settings.get_value('managed_comfy', 'runtime_root', '')))
	var actions = HFlowContainer.new()
	add_child(actions)
	host.button(actions, '选择本机运行库…', func(): chooser.popup_centered_ratio(0.7))
	host.button(actions, '检测运行库', operate.bind('inspect'))
	host.button(actions, '启动并连接', operate.bind('start'))
	host.button(actions, '停止本机模型', operate.bind('stop'))
	chooser = FileDialog.new()
	chooser.access = FileDialog.ACCESS_FILESYSTEM
	chooser.file_mode = FileDialog.FILE_MODE_OPEN_DIR
	chooser.title = '选择已有 ComfyUI 本机运行库'
	chooser.dir_selected.connect(func(path): runtime_path.text = path)
	add_child(chooser)
	autostart = CheckButton.new()
	autostart.text = '重开引擎时恢复本机模型连接'
	autostart.button_pressed = bool(settings.get_value('managed_comfy', 'autostart', false))
	add_child(autostart)
	autostart.toggled.connect(func(_enabled): save_local())
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.text = '图片使用已登录的 Codex CLI；网格在本机执行，无需额外充值。本机模型不会自动下载。'
	add_child(notice)
	if autostart.button_pressed and host._service_mode() == 'codex' and not runtime_path.text.is_empty(): operate.call_deferred('start')

func save_local():
	var settings = ConfigFile.new()
	settings.load(host.state_dir.path_join('local.cfg'))
	settings.set_value('managed_comfy', 'runtime_root', runtime_path.text.strip_edges())
	settings.set_value('managed_comfy', 'autostart', autostart.button_pressed)
	if settings.save(host.state_dir.path_join('local.cfg')) != OK:
		notice.text = '无法保存本机模型设置，请检查用户目录是否可写。'

func operate(action: String):
	if host.is_graph_busy():
		notice.text = '请等待当前操作完成或取消后，再管理本机模型。'
		return
	if runtime_path.text.strip_edges().is_empty():
		notice.text = '请先选择已有的本机运行库。'
		return
	# Bootstrap the bundled Python tools from the selected trusted runtime.
	for candidate in ['venv/Scripts/python.exe', 'venv/bin/python']:
		var python = runtime_path.text.path_join(candidate)
		if FileAccess.file_exists(python):
			host.python_edit.text = python
			break
	notice.text = {'inspect':'正在检查本机运行库…', 'start':'正在启动本机模型，首次启动可能需要一些时间…', 'stop':'正在释放当前连接；有任务运行时会等待任务结束。'}.get(action, '正在查询本机模型…')
	var request = {'action':action, 'runtime_root':runtime_path.text.strip_edges(), 'state_dir':manager_root, 'session_id':session_id}
	host.launch('managed-comfy', request)

func completed(data: Dictionary, request: Dictionary):
	if request.get('runtime_root', '') != runtime_path.text.strip_edges() or (request.get('action') in ['start', 'inspect'] and host._service_mode() != 'codex'):
		if data.get('owned', false) and not str(data.get('lease_path', '')).is_empty():
			DirAccess.remove_absolute(str(data.lease_path).replace('\\', '/'))
		notice.text = '设置已改变，已释放迟到的本机模型连接。'
		return
	last_report = data.duplicate(true)
	notice.text = str(data.get('message', '已读取本机模型状态。'))
	if not data.get('ok', false): return
	if not str(data.get('python', '')).is_empty(): host.python_edit.text = str(data.python)
	if data.get('owned', false) and not str(data.get('lease_path', '')).is_empty():
		lease_path = str(data.lease_path).replace('\\', '/')
		heartbeat_elapsed = 2.0
	if data.get('action') in ['stop', 'release']:
		lease_path = ''
		return
	if data.get('action') == 'start' and data.get('connected', false):
		host.endpoint_edit.text = str(data.endpoint)
		host._set_model_options(host.mesh_model_choice, [str(data.mesh_model)], str(data.mesh_model), true)
		host._service_settings_changed()
		save_local()
		host.save_service_settings()
		host.check_service()

func failed(message: String):
	notice.text = message

func _process(delta):
	if lease_path.is_empty(): return
	if host._service_mode() != 'codex':
		DirAccess.remove_absolute(lease_path)
		lease_path = ''
		return
	heartbeat_elapsed += delta
	if heartbeat_elapsed < 2.0: return
	heartbeat_elapsed = 0.0
	# Only refresh the lease returned for this exact UI session.
	if not FileAccess.file_exists(lease_path):
		lease_path = ''
		notice.text = '本机模型连接已释放，请重新启动并连接。'
		return
	var output = FileAccess.open(lease_path, FileAccess.READ_WRITE)
	if output != null:
		output.seek(0)
		output.store_8(49)
		output.flush()
		output.close()

func _exit_tree():
	if not lease_path.is_empty(): DirAccess.remove_absolute(lease_path)
