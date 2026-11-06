@tool
extends SceneTree

# Run with the macOS candidate: --headless --editor --path <scratch-project> --script <this-file>.
func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	await process_frame
	var preset = root.find_child("GongGongStartupValidation", true, false)
	if not preset or preset.pid > 0 or preset.temporary != null:
		push_error("Headless editor unexpectedly launched or omitted the validation component")
		quit(1)
		return
	# A child exiting successfully without the AI Chat marker must produce a failure.
	preset.probe_source = "extends SceneTree\nfunc _initialize():\n\tquit(0)\n"
	preset._start()
	var scratch: String = preset.temporary.get_current_dir()
	while preset.temporary != null:
		await process_frame
	if preset.pid > 0 or DirAccess.dir_exists_absolute(scratch):
		push_error("Validation process or temporary project survived completion")
		quit(1)
		return
	print("GONGGONG_VALIDATION_CLEANUP_OK")
	quit(0)
