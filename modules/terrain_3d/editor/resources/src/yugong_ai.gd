@tool
extends Node

signal finished(recipe: Dictionary, error: String)

const Landform = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_landform.gd")
const Layout = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_layout.gd")
const LIMIT_MS := 180000
var planning_layout := false
var process_id := -1
var job_dir := ""
var started_at := 0

func _ready() -> void:
	set_process(false)

func start(description: String, reference: Image, width_m: float, height_m: float, playable := false) -> void:
	if process_id >= 0:
		return
	planning_layout = playable
	var program := "codex.exe" if OS.get_name() == "Windows" else "codex"
	var settings := EditorInterface.get_editor_settings()
	var configured: String = settings.get_setting("yugong/codex_executable") if settings.has_setting("yugong/codex_executable") else ""
	if not configured.is_empty():
		program = configured
	job_dir = EditorInterface.get_editor_paths().get_cache_dir().path_join("yugong").path_join(ResourceUID.id_to_text(ResourceUID.create_id()).trim_prefix("uid://"))
	if DirAccess.make_dir_recursive_absolute(job_dir) != OK:
		_fail("无法创建本地 AI 任务目录。")
		return
	var number := {"type": "number"}
	var point := {"type": "object", "properties": {"x": number, "z": number, "radius": number, "amount": number},
		"required": ["x", "z", "radius", "amount"], "additionalProperties": false}
	var schema := {"type": "object", "additionalProperties": false, "required": ["shape", "width", "roughness", "angle", "features"],
		"properties": {"shape": {"type": "string", "enum": Landform.SHAPES}, "width": number, "roughness": number, "angle": number,
		"features": {"type": "array", "items": point}}}
	if playable:
		schema = Layout.schema()
	var file := FileAccess.open(job_dir.path_join("schema.json"), FileAccess.WRITE)
	if not file:
		_fail("无法写入地形参数格式。")
		return
	file.store_string(JSON.stringify(schema))
	file.close()
	var args := PackedStringArray(["--no-daemon", "--ask-for-approval", "never", "exec", "--ignore-user-config", "--ignore-rules",
		"--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", "--color", "never", "--cd", job_dir,
		"--output-schema", job_dir.path_join("schema.json"), "--output-last-message", job_dir.path_join("result.json")])
	for feature in ["shell_tool", "unified_exec", "apps", "plugins", "multi_agent", "code_mode", "hooks"]:
		args.append_array(["-c", "features.%s=false" % feature])
	args.append_array(["-c", "web_search=\"disabled\""])
	if playable:
		args.append_array(["--model","gpt-6.2-astra","-c","model_reasoning_effort=\"high\""])
	else:
		args.append_array(["-c","model_reasoning_effort=\"low\""])
	if reference != null:
		var small: Image = reference.duplicate()
		var factor := minf(1.0, 1024.0 / maxi(small.get_width(), small.get_height()))
		small.resize(maxi(1, roundi(small.get_width() * factor)), maxi(1, roundi(small.get_height() * factor)), Image.INTERPOLATE_BILINEAR)
		small.convert(Image.FORMAT_RGB8)
		if small.save_png(job_dir.path_join("reference.png")) != OK:
			_fail("无法准备参考图。")
			return
		args.append_array(["--image", job_dir.path_join("reference.png")])
	args.append("--")
	if playable:
		args.append("Design an original navigable terrain as JSON only. World width %s m, relief %s m. Coordinates x,z are normalized fractions of half width in [-0.95,0.95]; north is negative z. spawn and arithmetic center of plateau are the shared road endpoints, at least 0.40 apart, dry and at least 0.10 from river. Plateau is a simple convex 4-7 vertex outline around a landmark named ruin, tree or cairn. River is an ordered 5-10 point polyline traversing the map. Both roads contain 3-9 distinct INTERMEDIATE waypoints only. Make two distinct scenic routes between the common endpoints. Where a bridge is wanted, cross the channel at a clear angle. Avoid roads coinciding with the channel. Ridges: 3-8 distinct {x,z,radius,height}; radius .06 to .55, height .1 to .9. Reflect the user's directions and any image composition. User: %s" % [width_m,height_m,description.left(2400)])
	else:
		args.append("Design a heightfield recipe only. No tools or code. Translate the user's terrain or image composition into the given schema. World width %s m, relief %s m. width is valley floor/ridge width in 0.05..0.85; roughness 0..1; angle degrees, zero runs north-south. Up to eight Gaussian-like features, x,z in -1..1 (west/east, north/south), radius 0.08..1.5, signed amount -1..1 raises or lowers. Preserve significant spatial relations. User: %s" % [width_m, height_m, description.left(2400)])
	if OS.get_name() == "Windows":
		var proxy_host: String = settings.get_setting("network/http_proxy/host")
		var proxy := "http://%s:%s" % [proxy_host, settings.get_setting("network/http_proxy/port")] if not proxy_host.is_empty() else ""
		file = FileAccess.open(job_dir.path_join("launch.json"), FileAccess.WRITE)
		if not file:
			_fail("无法写入本地 AI 启动参数。")
			return
		file.store_string(JSON.stringify({"program": program, "arguments": args, "proxy": proxy}))
		file.close()
		var runner := ProjectSettings.globalize_path("@TERRAIN3D_EDITOR_ROOT@/src/yugong_codex.ps1")
		var shell := OS.get_environment("SystemRoot").path_join("System32/WindowsPowerShell/v1.0/powershell.exe")
		process_id = OS.create_process(shell, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", runner, job_dir, str(OS.get_process_id())])
	else:
		process_id = OS.create_process(program, args)
	if process_id < 0:
		_fail("无法启动 Codex CLI。可继续使用本地草案，或在编辑器设置中指定可执行文件。")
		return
	started_at = Time.get_ticks_msec()
	set_process(true)

func _process(_delta: float) -> void:
	if OS.is_process_running(process_id):
		if Time.get_ticks_msec() - started_at > LIMIT_MS:
			cancel()
			finished.emit({}, "AI 解读超时，可重试或生成本地草案。")
		return
	var exit_code := OS.get_process_exit_code(process_id)
	process_id = -1
	set_process(false)
	var path := job_dir.path_join("result.json")
	var parsed: Variant = null
	if exit_code == 0 and FileAccess.file_exists(path):
		parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	if planning_layout:
		var problem := Layout.error(parsed)
		if not problem.is_empty():
			_fail("AI 布局未通过校验：" + problem)
			return
	elif not Landform.validate_recipe(parsed):
		_fail("AI 未返回有效地形参数。请检查 Codex CLI 登录与连接，或使用本地草案。")
		return
	_cleanup()
	finished.emit(parsed, "")

func cancel() -> void:
	if process_id >= 0 and OS.is_process_running(process_id):
		if OS.get_name() == "Windows":
			var flag := FileAccess.open(job_dir.path_join("cancel"), FileAccess.WRITE)
			if flag:
				flag.close()
				# The owned worker terminates its request and removes the private inputs.
				job_dir = ""
		else:
			OS.kill(process_id)
	process_id = -1
	set_process(false)
	_cleanup()

func _exit_tree() -> void:
	cancel()

func _fail(message: String) -> void:
	_cleanup()
	finished.emit({}, message)

func _cleanup() -> void:
	if job_dir.is_empty():
		return
	for file in ["schema.json", "result.json", "reference.png", "launch.json"]:
		var path := job_dir.path_join(file)
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
	DirAccess.remove_absolute(job_dir)
	job_dir = ""
