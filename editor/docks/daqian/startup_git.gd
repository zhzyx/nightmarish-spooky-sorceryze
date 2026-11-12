@tool
extends RefCounted

var helper_source: String = ""
var _process: Dictionary = {}
var _cancelled := false


func cancel() -> void:
	_cancelled = true
	if not _process.is_empty():
		var pipe: FileAccess = _process.stdio
		if pipe != null and pipe.is_open():
			pipe.store_line("cancel")
			pipe.flush()
			# EOF is also cancellation, including when the owner is being freed.
			pipe.close()


func run(owner: Node, project_path: String, python: String) -> Dictionary:
	if not _process.is_empty():
		return {"status": "busy", "message": "Git 启动同步正在运行。"}
	if python.is_empty():
		return {"status": "no_python", "message": "未配置工作流 Python，无法执行 Git 启动同步。"}
	if helper_source.is_empty() or not is_instance_valid(owner) or not owner.is_inside_tree():
		return {"status": "error", "message": "Git 启动同步运行环境不可用。"}
	_cancelled = false
	_process = OS.execute_with_pipe(python, ["-c", helper_source, project_path], false)
	if _process.is_empty():
		return {"status": "no_python", "message": "无法启动工作流 Python。"}
	var process := _process
	var tree := owner.get_tree()
	var started := Time.get_ticks_msec()
	var output := PackedByteArray()
	var overflow := false
	var timed_out := false
	while OS.is_process_running(process.pid):
		if not is_instance_valid(owner) or not owner.is_inside_tree():
			cancel()
		var pipe: FileAccess = process.stdio
		if pipe != null and pipe.is_open():
			var size := mini(pipe.get_length(), 8192)
			if size > 0:
				var chunk := pipe.get_buffer(size)
				if output.size() + chunk.size() <= 8192:
					output.append_array(chunk)
				else:
					overflow = true
		var errors: FileAccess = process.stderr
		if errors != null and errors.is_open():
			var size := mini(errors.get_length(), 8192)
			if size > 0:
				errors.get_buffer(size) # Diagnostics can contain URLs or credentials.
		if Time.get_ticks_msec() - started > 55000 and not timed_out:
			timed_out = true
			cancel()
		if Time.get_ticks_msec() - started > 60000:
			OS.kill(process.pid)
			break
		await tree.create_timer(0.05).timeout
	var final_pipe: FileAccess = process.stdio
	if final_pipe != null and final_pipe.is_open():
		var remaining := final_pipe.get_length()
		if remaining > 0 and remaining + output.size() <= 8192:
			output.append_array(final_pipe.get_buffer(remaining))
		elif remaining > 0:
			overflow = true
		final_pipe.close()
	var final_errors: FileAccess = process.stderr
	if final_errors != null:
		final_errors.close()
	_process = {}
	if timed_out:
		return {"status": "timeout", "message": "Git 启动同步超时，已请求停止后台进程。"}
	if _cancelled:
		return {"status": "cancelled", "message": "Git 启动同步已取消。"}
	var result = JSON.parse_string(output.get_string_from_utf8()) if not overflow else null
	if result is Dictionary and result.get("status") is String and result.get("message") is String:
		return result
	return {"status": "error", "message": "Git 启动同步未返回有效结果。"}
