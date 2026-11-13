@tool
extends VBoxContainer

const DISTRIBUTION = 'maliang-hunyuan3d-2mini-v1'
const BUNDLED_MODEL = 'hunyuan3d-mini.safetensors'

var host
var runtime_path: LineEdit
var notice: Label
var autostart: CheckButton
var chooser: FileDialog
var session_id = ''
var lease_path = ''
var lease_runtime = ''
var heartbeat_elapsed = 0.0
var manager_root = ''
var last_report: Dictionary = {}
var requested_service: Dictionary = {}
var requested_host = ''
var requested_python = ''
var restore_bundle = false
var bundled_endpoint = ''
var bundle_failure = ''

# Only the native workbench calls this. Neither project settings nor manifest
# fields can supply the Python executable, script, or runtime directory.
static func discover_bundle() -> Dictionary:
	var directory = OS.get_executable_path().get_base_dir()
	var root: String
	var interpreter: String
	match OS.get_name():
		'macOS':
			root = directory.path_join('../Resources/maliang-hunyuan').simplify_path()
			interpreter = 'python/bin/python3.12'
		'Windows':
			root = directory.path_join('maliang-hunyuan')
			interpreter = 'python/python.exe'
		_:
			return {}
	if not DirAccess.dir_exists_absolute(root): return {}
	var manifest = FileAccess.open(root.path_join('config.json'), FileAccess.READ)
	var config = JSON.parse_string(manifest.get_as_text()) if manifest != null else null
	if not config is Dictionary or config.get('distribution') != DISTRIBUTION:
		return {'error':'无法识别引擎旁的 Hunyuan3D 发行配置，请检查完整发行包。', 'directory':root}
	return {'root':root, 'python':root.path_join(interpreter)}

func initialize(workbench, settings: ConfigFile):
	host = workbench
	name = 'ManagedLocalMesh'
	session_id = str(OS.get_process_id()) + '-' + Crypto.new().generate_random_bytes(12).hex_encode()
	if manager_root.is_empty():
		var cache = OS.get_cache_dir()
		var directories = DirAccess.get_directories_at(cache)
		var godot_folder = 'Godot' if 'Godot' in directories and 'godot' not in directories else 'godot'
		manager_root = cache.path_join(godot_folder).path_join('ainative-managed-comfy')
	var heading = Label.new()
	heading.text = '本机网格模型 · 引擎已内置 Hunyuan3D' if host.bundled_runtime.has('root') else '本机网格模型 · 由引擎管理'
	add_child(heading)
	restore_bundle = settings.get_value('managed_comfy', 'use_bundled_runtime', false)
	bundled_endpoint = str(settings.get_value('managed_comfy', 'bundled_endpoint', ''))
	var configured_root = '' if restore_bundle else str(settings.get_value('managed_comfy', 'runtime_root', ''))
	runtime_path = host.line(self, '选择已有 ComfyUI 本机运行库', host.bundled_runtime.get('root', '') if configured_root.is_empty() else configured_root)
	var actions = HFlowContainer.new()
	add_child(actions)
	host.button(actions, '更换本机运行库…' if host.bundled_runtime.has('root') else '选择本机运行库…', func(): chooser.popup_centered_ratio(0.7))
	host.button(actions, '检测运行库', operate.bind('inspect'))
	host.button(actions, '启动并连接', operate.bind('start'))
	host.button(actions, '停止本机模型', operate.bind('stop'))
	host.button(actions, '打开模型日志', open_log)
	chooser = FileDialog.new()
	chooser.access = FileDialog.ACCESS_FILESYSTEM
	chooser.file_mode = FileDialog.FILE_MODE_OPEN_DIR
	chooser.title = '选择已有 ComfyUI 本机运行库'
	chooser.dir_selected.connect(func(path): runtime_path.text = path)
	add_child(chooser)
	var fresh = (host._service_mode() == 'offline'
			and not settings.has_section_key('service', 'mode')
			and not FileAccess.file_exists(host.service_config_path)
			and host.factory_edit.text == 'editor_demo:factory')
	var default_bundle = fresh and using_bundle() and _uses_native_host()
	autostart = CheckButton.new()
	autostart.text = '重开引擎时恢复本机模型连接'
	autostart.button_pressed = settings.get_value('managed_comfy', 'autostart', default_bundle)
	add_child(autostart)
	autostart.toggled.connect(func(_enabled): save_local())
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.text = '已有图片可直接生成网格，无需 CLI。生成或重绘图片请另选图像服务。'
	add_child(notice)
	if default_bundle and autostart.button_pressed:
		restore_bundle = true
		host.select_service_mode('local_mesh')
		host._service_settings_changed()
	if runtime_path.text.is_empty() and ((fresh and host.bundled_runtime.has('error')) or _saved_bundle_selected()):
		var reason = host.bundled_runtime.get('error', '当前引擎缺少已选择的 Hunyuan3D 运行库，请恢复完整发行包。')
		failed.call_deferred(host.diagnostic_error(reason, OS.get_executable_path()))
	if using_bundle():
		host.visibility_changed.connect(_resume_on_show)
		if not (default_bundle or _saved_bundle_selected()): return
	if autostart.button_pressed and host._service_mode() in ['codex', 'local_mesh'] and not runtime_path.text.is_empty():
		_restore_connection.call_deferred(host.service_draft(), runtime_path.text)

func using_bundle() -> bool:
	return host.bundled_runtime.has('root') and runtime_path.text.strip_edges() == host.bundled_runtime.root

func _uses_native_host() -> bool:
	var tools = str(host.get_meta('ainative_tools_dir', ''))
	return tools.is_absolute_path() and not tools.contains('://') and host.host_edit.text == tools.path_join('editor_host.py')

func _saved_bundle_selected() -> bool:
	return (restore_bundle and not bundled_endpoint.is_empty()
			and host.service_saved.get('mode') in ['codex', 'local_mesh']
			and host.service_saved.get('mesh_model') == BUNDLED_MODEL
			and host.service_saved.get('endpoint') == bundled_endpoint
			and host.service_saved == host.service_draft())

func _resume_on_show():
	if host.is_visible_in_tree() and using_bundle() and _saved_bundle_selected() and last_report.get('action') != 'stop':
		_restore_connection.call_deferred(host.service_draft(), runtime_path.text)

func _restore_connection(draft: Dictionary, path: String):
	if not autostart.button_pressed or not host.is_inside_tree() or host.is_graph_busy(): return
	if using_bundle() and not _uses_native_host(): return
	if host._service_mode() not in ['codex', 'local_mesh'] or host.service_draft() != draft or runtime_path.text != path: return
	if lease_runtime == path and not lease_path.is_empty() and FileAccess.file_exists(lease_path): return
	operate('start')

func save_local():
	var settings = ConfigFile.new()
	settings.load(host.state_dir.path_join('local.cfg'))
	restore_bundle = using_bundle()
	settings.set_value('managed_comfy', 'use_bundled_runtime', restore_bundle)
	settings.set_value('managed_comfy', 'runtime_root', '' if restore_bundle else runtime_path.text.strip_edges())
	settings.set_value('managed_comfy', 'bundled_endpoint', bundled_endpoint if restore_bundle and not bundled_endpoint.is_empty() else null)
	settings.set_value('managed_comfy', 'autostart', autostart.button_pressed)
	if settings.save(host.state_dir.path_join('local.cfg')) != OK:
		failed('无法保存本机模型设置，请检查用户目录是否可写。')

func operate(action: String):
	if host.is_graph_busy():
		notice.text = '请等待当前操作完成或取消后，再管理本机模型。'
		return
	var root = runtime_path.text.strip_edges()
	if root.is_empty():
		failed('请先选择已有的本机运行库。')
		return
	if using_bundle():
		var interpreter: String = host.bundled_runtime.python
		if not FileAccess.file_exists(interpreter):
			failed(host.diagnostic_error('发行包缺少内置 Python，请恢复完整发行包。', interpreter))
			return
	else:
		for candidate in ['venv/Scripts/python.exe', 'venv/bin/python']:
			var python = root.path_join(candidate)
			if FileAccess.file_exists(python):
				host.python_edit.text = python
				break
	requested_service = host.service_draft()
	requested_host = host.host_edit.text
	requested_python = host.python_edit.text
	notice.text = {'inspect':'正在检查本机运行库…', 'start':'正在启动本机网格模型，首次启动可能需要一些时间…', 'stop':'正在释放当前连接；有任务运行时会等待任务结束。'}.get(action, '正在查询本机模型…')
	if using_bundle() and host.status != null: host.status.text = notice.text
	var request = {'action':action, 'runtime_root':root, 'state_dir':manager_root, 'session_id':session_id}
	if using_bundle() and action == 'start': request['timeout'] = 300
	host.launch('managed-comfy', request)

func completed(data: Dictionary, request: Dictionary):
	var changed = (host._service_mode() not in ['codex', 'local_mesh'] or requested_service != host.service_draft()
			or requested_host != host.host_edit.text or requested_python != host.python_edit.text)
	if request.get('runtime_root', '') != runtime_path.text.strip_edges() or (request.get('action') in ['start', 'inspect'] and changed):
		if data.get('owned', false) and not str(data.get('lease_path', '')).is_empty():
			DirAccess.remove_absolute(str(data.lease_path).replace('\\', '/'))
		notice.text = '设置已改变，已释放迟到的本机模型连接。'
		return
	last_report = data.duplicate(true)
	notice.text = str(data.get('message', '已读取本机模型状态。'))
	if not data.get('ok', false):
		var details = {'code':data.get('code', ''), 'runtime_root':request.runtime_root, 'logs':data.get('log_path', manager_root)}
		failed(host.diagnostic_error(notice.text, details))
		return
	if not using_bundle() and not str(data.get('python', '')).is_empty(): host.python_edit.text = str(data.python)
	if data.get('action') == 'start' and request.runtime_root != lease_runtime: release_connection()
	if data.get('owned', false) and not str(data.get('lease_path', '')).is_empty():
		lease_runtime = request.runtime_root
		lease_path = str(data.lease_path).replace('\\', '/')
		heartbeat_elapsed = 2.0
	if data.get('action') in ['stop', 'release']:
		release_connection()
		return
	if data.get('action') == 'start' and data.get('connected', false):
		bundle_failure = ''
		if using_bundle(): bundled_endpoint = str(data.endpoint)
		host.endpoint_edit.text = str(data.endpoint)
		var selected: String = host._model_name(host.mesh_model_choice)
		host._set_model_options(host.mesh_model_choice, [str(data.mesh_model)], str(data.mesh_model) if selected.is_empty() else selected, true)
		host._service_settings_changed()
		save_local()
		host.save_service_settings()
		host.check_service()

func failed(message: String):
	bundle_failure = message
	notice.text = message
	host.service_status.text = message
	host._show_run_problem(message, 'environment')

func bundled_mesh_blocker() -> String:
	if not restore_bundle or host._service_mode() not in ['codex', 'local_mesh']: return ''
	if not host.service_saved.is_empty() and not _saved_bundle_selected(): return ''
	if host.service_saved.is_empty() and not using_bundle(): return ''
	if host.bundled_runtime.has('root') and lease_runtime == host.bundled_runtime.root and not lease_path.is_empty() and FileAccess.file_exists(lease_path): return ''
	return bundle_failure if not bundle_failure.is_empty() else '内置 Hunyuan3D 尚未连接，请在环境设置中启动本机模型。'

func open_log():
	var path = str(last_report.get('log_path', ''))
	if not path.is_empty() and FileAccess.file_exists(path): OS.shell_open(path)
	else: host.open_diagnostics()

func _process(delta):
	if lease_path.is_empty(): return
	if host._service_mode() not in ['codex', 'local_mesh']:
		release_connection()
		return
	heartbeat_elapsed += delta
	if heartbeat_elapsed < 2.0: return
	heartbeat_elapsed = 0.0
	# Only refresh the lease returned for this exact UI session.
	if not FileAccess.file_exists(lease_path):
		lease_path = ''
		lease_runtime = ''
		failed(host.diagnostic_error('本机模型连接已释放，请重新启动并连接。', last_report.get('log_path', manager_root)))
		return
	var output = FileAccess.open(lease_path, FileAccess.READ_WRITE)
	if output != null:
		output.seek(0)
		output.store_8(49)
		output.flush()
		output.close()

func release_connection():
	if not lease_path.is_empty(): DirAccess.remove_absolute(lease_path)
	lease_path = ''
	lease_runtime = ''

func _notification(what):
	# Moving the settings control between containers must not release its host's
	# lease. The workbench explicitly releases on exit; deletion is a fallback.
	if what == NOTIFICATION_PREDELETE: release_connection()
