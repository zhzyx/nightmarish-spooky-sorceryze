extends SceneTree
# Fresh bundled-runtime startup uses a fake interpreter only; no model inference.
var panel
var failures = 0

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func write_text(path: String, value: String):
	var file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(value)
	file.close()

func run():
	var state = OS.get_environment("AINATIVE_FRESH_TEST_DIR")
	if state.is_empty(): state = ProjectSettings.globalize_path("user://managed-comfy-fresh-test").path_join(str(Time.get_ticks_usec()))
	var runtime = state.path_join("maliang-hunyuan")
	var interpreter = runtime.path_join("python/python.exe")
	DirAccess.make_dir_recursive_absolute(interpreter.get_base_dir())
	write_text(runtime.path_join("config.json"), JSON.stringify({"distribution": "maliang-hunyuan3d-2mini-v1"}))
	write_text(interpreter, "fake executable; connection is expected to fail before any model starts")
	var tools = state.path_join("bundled-tools")
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.state_dir = state.path_join("editor-state")
	panel.set_meta("ainative_builtin", true)
	panel.set_meta("ainative_tools_dir", tools)
	root.add_child(panel)
	panel.bundled_runtime = {"root": runtime, "python": interpreter}
	panel.python_edit.text = interpreter
	panel.managed_comfy_panel.runtime_path.text = runtime
	panel.managed_comfy_panel.initialize(panel, ConfigFile.new())
	for i in 8: await process_frame
	check(panel.managed_comfy_panel.autostart.button_pressed, "fresh bundled installation enables connection recovery")
	check(panel._service_mode() == "local_mesh", "fresh bundled installation selects the shipped local Mesh service")
	check(panel.managed_comfy_panel.requested_python == interpreter, "fresh startup attempts the bundled interpreter connection")
	check(panel.managed_comfy_panel.requested_host == tools.path_join("editor_host.py"), "fresh startup keeps the native bundled host boundary")
	check(panel.managed_comfy_panel.requested_service.get("mode", "") == "local_mesh", "fresh connection request carries the selected local Mesh mode")
	print("FRESH_STARTUP_EVIDENCE " + JSON.stringify({"notice": panel.managed_comfy_panel.notice.text, "status": panel.status.text, "interpreter": interpreter, "factory": panel.factory_edit.text, "host": panel.host_edit.text, "runtime": panel.bundled_runtime, "using_bundle": panel.managed_comfy_panel.using_bundle(), "native_host": panel.managed_comfy_panel._uses_native_host(), "config_exists": FileAccess.file_exists(panel.service_config_path), "autostart": panel.managed_comfy_panel.autostart.button_pressed}))
	panel.queue_free()
	await process_frame
	print("AINATIVE_FRESH_STARTUP failures=" + str(failures))
	quit(0 if failures == 0 else 1)
