@tool
extends SceneTree

var outcome: Variant

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
	var sources: Dictionary = preset.package_sources()
	if sources.is_empty():
		push_error("Test editor must have both installed packages")
		quit(1)
		return
	# A zero exit with the entry marker and just one valid package receipt must fail.
	for name: String in ["ui", "board"]:
		var marker := "TIANSHU_%s_LOADED %s" % [name.to_upper(), sources[name].sha256]
		preset.probe_source = 'extends SceneTree\nfunc _initialize():\n\tprint("DAQIAN_AI_ENTRY_OK")\n\tprint("%s")\n\tquit(0)\n' % marker
		outcome = null
		_verify(preset, sources)
		if not preset.temporary:
			push_error("Isolated child did not start")
			quit(1)
			return
		var scratch: String = preset.temporary.get_current_dir()
		while outcome == null:
			await process_frame
		if outcome or preset.pid > 0 or DirAccess.dir_exists_absolute(scratch):
			push_error("Incomplete child package receipts passed or survived completion")
			quit(1)
			return
	print("GONGGONG_VALIDATION_CLEANUP_OK")
	quit(0)


func _verify(preset: Node, sources: Dictionary) -> void:
	outcome = await preset.verify_entry(sources)
