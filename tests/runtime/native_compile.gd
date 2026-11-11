extends SceneTree

var failures: Array[String] = []

func check(condition: bool, message: String = "native compilation check failed") -> void:
	if not condition:
		failures.append(message)
		push_error(message)

func _initialize() -> void:
	var compiler := OS.get_environment("RUNTIME_NATIVE_COMPILER")
	var source := OS.get_environment("RUNTIME_NATIVE_SOURCE")
	var include := OS.get_environment("RUNTIME_NATIVE_INCLUDE")
	check(not compiler.is_empty() and not source.is_empty() and not include.is_empty())
	var root := "res://native builds " + str(OS.get_process_id()) + " " + str(Time.get_ticks_usec())
	check(DirAccess.make_dir_absolute(root) == OK)
	for language in ["c", "c++"]:
		var args := PackedStringArray(["-x", language, source, "-I", include])
		var previous_path := ""
		for version in [42, 73]:
			var directory := root.path_join(language.replace("+", "p") + str(version))
			var options := args.duplicate()
			options.append("-DFIXTURE_VALUE=" + str(version))
			var result: Dictionary = GDExtensionManager.compile_extension(compiler, options, directory, "runtime_native_init")
			check(result.error == OK, str(result))
			check(result.exit_code == 0 and FileAccess.file_exists(result.library_path))
			check(not GDExtensionManager.is_extension_loaded(result.path))
			check(result.path != previous_path)
			previous_path = result.path
			check(GDExtensionManager.load_extension(result.path) == GDExtensionManager.LOAD_STATUS_OK)
			check(ClassDB.class_call_static("RuntimeNativeFixture", "answer") == version)
			var collision: Dictionary = GDExtensionManager.compile_extension(compiler, options, directory, "runtime_native_init")
			check(collision.error != OK and collision.exit_code == -1 and collision.path.is_empty())
			check(ClassDB.class_call_static("RuntimeNativeFixture", "answer") == version)
			check(GDExtensionManager.unload_extension(result.path) == GDExtensionManager.LOAD_STATUS_OK)
	var print_errors := Engine.print_error_messages
	Engine.print_error_messages = false
	var missing: Dictionary = GDExtensionManager.compile_extension(root.path_join("missing-compiler"), PackedStringArray(), root.path_join("missing"), "runtime_native_init")
	var failed: Dictionary = GDExtensionManager.compile_extension(compiler, PackedStringArray(["-x", "c", source + ".missing"]), root.path_join("failure"), "runtime_native_init")
	Engine.print_error_messages = print_errors
	check(missing.error != OK and missing.path.is_empty())
	check(failed.error != OK and failed.exit_code != 0 and not failed.output.is_empty() and failed.path.is_empty())
	check(not FileAccess.file_exists(root.path_join("failure/extension.gdextension")))
	print(JSON.stringify({"test": "native_compile", "passed": failures.is_empty(), "failures": failures}))
	if failures.is_empty():
		print("RUNTIME_NATIVE_COMPILE_OK")
	quit(0 if failures.is_empty() else 1)
