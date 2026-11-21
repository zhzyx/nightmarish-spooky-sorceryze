@tool
extends SceneTree

var panel
var save_button: Button
var selections: Array[String] = []
var cancellations := 0
var evidence: Array[Dictionary] = []
var base := OS.get_environment("SAVE_PANEL_ROOT")


func _initialize():
	run.call_deferred()


func record(name: String, data: Variant):
	var file := FileAccess.open(base.path_join(name + ".tmp"), FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "  "))
	file.close()
	DirAccess.rename_absolute(base.path_join(name + ".tmp"), base.path_join(name))


func require(ok: bool, message: String) -> bool:
	if not ok:
		push_error(message)
		record("failure.json", {"error": message, "steps": evidence})
		quit(1)
	return ok


func run():
	var deadline := Time.get_ticks_msec() + 30000
	var dock := root.find_child("AINative", true, false)
	while dock == null and Time.get_ticks_msec() < deadline:
		await process_frame
		dock = root.find_child("AINative", true, false)
	if not require(dock != null, "Bundled Maliang dock missing"):
		return
	var tabs: TabContainer = dock.get_parent()
	tabs.current_tab = tabs.get_tab_idx_from_control(dock)
	while panel == null and Time.get_ticks_msec() < deadline:
		await process_frame
		panel = dock.find_child("AINativeWorkbench", true, false)
	if not require(panel != null and panel.get_meta("ainative_builtin", false), "Bundled workbench missing"):
		return
	for button in panel.find_children("*", "Button", true, false):
		if button.text == "保存生成物…":
			save_button = button
			break
	if not require(save_button != null and save_button.is_visible_in_tree(), "Save Artifact button missing"):
		return
	var picker: FileDialog = panel.save_picker
	if not require(picker.use_native_dialog and picker.file_mode == FileDialog.FILE_MODE_SAVE_FILE and picker.access == FileDialog.ACCESS_FILESYSTEM and DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG_FILE), "Native filesystem save dialog unavailable"):
		return
	picker.file_selected.connect(func(path: String): selections.append(path))
	picker.canceled.connect(func(): cancellations += 1)
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = str(panel.get_meta("ainative_tools_dir")).path_join("editor_host.py")
	for step in ["image", "mesh", "cancel"]:
		if not await exercise(step):
			return
	record("callbacks.json", evidence)
	# XCTest owns the app lifetime, including teardown after UI failures.


func exercise(step: String) -> bool:
	var ext := "glb" if step == "mesh" else "png"
	var fixture := ProjectSettings.globalize_path("res://fixtures/sample." + ext)
	var node_id := str(panel.nodes[0].id)
	panel.select_node(node_id)
	panel._set_node_file("source", fixture)
	panel.params_edit.text = '{"delay":0,"fail":false}'
	panel.apply_fields()
	panel.run_node_preview(node_id)
	var deadline := Time.get_ticks_msec() + 45000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec() < deadline:
		await process_frame
	var source := str(panel.preview_source_path)
	var decoded: bool = panel.preview_scene != null if step == "mesh" else panel.preview_resource != null
	if not require(panel.current.get("state") == "succeeded" and decoded and source != fixture and FileAccess.file_exists(source) and FileAccess.get_file_as_bytes(source) == FileAccess.get_file_as_bytes(fixture), step + " preview generation failed"):
		return false
	var before := selections.size()
	var before_cancel := cancellations
	save_button.pressed.emit()
	record(step + ".json", {"suggested_name": panel.save_picker.current_file})
	deadline = Time.get_ticks_msec() + 120000
	while selections.size() == before and cancellations == before_cancel and Time.get_ticks_msec() < deadline:
		await create_timer(0.1).timeout
	var paths := selections.slice(before)
	var cancel_count := cancellations - before_cancel
	evidence.append({"step": step, "file_selected": paths, "canceled": cancel_count, "source": source, "source_sha256": FileAccess.get_sha256(source)})
	return require((paths.is_empty() and cancel_count == 1) if step == "cancel" else (paths.size() == 1 and cancel_count == 0), step + " callback mismatch")
