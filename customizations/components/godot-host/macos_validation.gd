@tool
extends Node

const TIMEOUT_MS := 60_000
const PREFIX := "GongGong macOS startup validation"
var probe_source: String
var temporary: DirAccess
var pid := -1


func _write(path: String, content: String) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	return file != null and file.store_string(content)


func verify_entry() -> bool:
	if not is_inside_tree():
		return false
	temporary = DirAccess.create_temp("gonggong-validation")
	if not temporary:
		_finish("cannot create temporary directory")
		return false
	var root := temporary.get_current_dir()
	var project := root.path_join("project")
	var editor := root.path_join("Godot")
	# Separate both the project and self-contained editor settings on every run.
	if temporary.make_dir("project") != OK or not _write(root.path_join("._sc_"), ""):
		_finish("cannot isolate editor settings")
		return false
	if not _write(project.path_join("project.godot"), 'config_version=5\n[application]\nconfig/name="GongGong validation"\n') or not _write(project.path_join("entry.gd"), probe_source):
		_finish("cannot prepare validation project")
		return false
	# Keep file copying off the editor thread, including on non-APFS volumes.
	var code := await _run("/bin/cp", ["-c", OS.get_executable_path(), editor])
	if code != 0 and temporary:
		code = await _run("/bin/cp", [OS.get_executable_path(), editor])
	if not temporary:
		return false
	if code != 0:
		_finish("cannot prepare isolated editor executable (exit %d)" % code)
		return false
	var log_path := root.path_join("probe.log")
	code = await _run("/usr/bin/env", ["-i", "PATH=/usr/bin:/bin", "TMPDIR=" + root, "HOME=" + root,
			"__GODOT_SHELL_ENV_SET=1", editor, "--headless", "--editor", "--path", project,
			"--log-file", log_path, "--script", "res://entry.gd"])
	if not temporary:
		return false
	var log_text := FileAccess.get_file_as_string(log_path) if FileAccess.file_exists(log_path) else ""
	if code != 0 or not log_text.contains("DAQIAN_AI_ENTRY_OK") or log_text.contains("SCRIPT ERROR"):
		_finish("AI Chat entry probe failed (exit %d)" % code)
	else:
		_finish("")
		return true
	return false


func _run(executable: String, args: PackedStringArray) -> int:
	pid = OS.create_process(executable, args)
	if pid <= 0:
		return -1
	var deadline := Time.get_ticks_msec() + TIMEOUT_MS
	while OS.is_process_running(pid):
		if Time.get_ticks_msec() >= deadline:
			OS.kill(pid)
			pid = -1
			return ERR_TIMEOUT
		await get_tree().create_timer(0.25).timeout
		if pid <= 0:
			return ERR_SKIP
	var code := OS.get_process_exit_code(pid)
	pid = -1
	return code


func _finish(error: String) -> void:
	temporary = null
	if error.is_empty():
		print(PREFIX + " passed")
	else:
		push_warning(PREFIX + ": " + error)


func _exit_tree() -> void:
	if pid > 0 and OS.is_process_running(pid):
		OS.kill(pid)
	pid = -1
	temporary = null
