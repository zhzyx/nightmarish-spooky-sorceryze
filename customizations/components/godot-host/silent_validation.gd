@tool
extends Node

# Run outside the open project so its scenes, autoloads and plugins cannot affect the probe.
const PROBE := """extends SceneTree
func _initialize():
	check.call_deferred()

func check():
	if DisplayServer.get_name() != "headless":
		quit(1)
		return
	var button := Button.new()
	button.toggle_mode = true
	button.set_pressed_no_signal(true)
	root.add_child(button)
	if not button.is_pressed() or not button.is_inside_tree():
		quit(2)
		return
	var receipt := FileAccess.open("res://passed", FileAccess.WRITE)
	if not receipt:
		quit(3)
		return
	receipt.store_line("headless-control-ok")
	receipt.close()
	quit()
"""

var child_pid := -1
var scratch: DirAccess


func _ready() -> void:
	_verify.call_deferred()


func _verify() -> void:
	var binary := OS.get_executable_path()
	var key := ("%s|%s|%s|%s" % [binary, FileAccess.get_modified_time(binary), Engine.get_version_info().hash, PROBE]).sha256_text()
	var cache := EditorInterface.get_editor_paths().get_cache_dir().path_join("godot-silent-" + key + ".ok")
	if FileAccess.file_exists(cache) and FileAccess.get_file_as_string(cache).strip_edges() == key:
		return
	scratch = DirAccess.create_temp("godot-silent")
	if not scratch:
		push_warning("静默验证无法创建临时目录，下次启动将重试。")
		return
	var folder := scratch.get_current_dir()
	var inputs := {"project.godot": "config_version=5\n[debug]\nfile_logging/enable_file_logging=false\n", "probe.gd": PROBE}
	for filename in inputs:
		var file := FileAccess.open(folder.path_join(filename), FileAccess.WRITE)
		if not file:
			push_warning("静默验证无法写入临时文件，下次启动将重试。")
			scratch = null
			return
		file.store_string(inputs[filename])
		file.close()
	child_pid = OS.create_process(binary, ["--headless", "--path", folder, "--script", "res://probe.gd"], false)
	var deadline := Time.get_ticks_msec() + 30000
	while child_pid > 0 and OS.is_process_running(child_pid):
		if Time.get_ticks_msec() >= deadline:
			OS.kill(child_pid)
			child_pid = -1
			break
		await get_tree().create_timer(0.25).timeout
	var marker := folder.path_join("passed")
	var passed := child_pid > 0 and OS.get_process_exit_code(child_pid) == 0 and FileAccess.file_exists(marker) and FileAccess.get_file_as_string(marker).strip_edges() == "headless-control-ok"
	child_pid = -1
	scratch = null
	if not passed:
		push_warning("Godot 无窗口控件验证失败。请检查本机构建的 --headless 和 GDScript 支持，下次打开将重试。")
		return
	var receipt := FileAccess.open(cache, FileAccess.WRITE)
	if receipt:
		receipt.store_line(key)
	else:
		push_warning("静默验证已通过，但无法保存本机回执，下次启动将重试。")


func _exit_tree() -> void:
	if child_pid > 0 and OS.is_process_running(child_pid):
		OS.kill(child_pid)
	child_pid = -1
