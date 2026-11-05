@tool
extends SceneTree


func _initialize() -> void:
	check_restore.call_deferred()


func check_restore() -> void:
	await create_timer(0.5).timeout
	var control := AIChatEditorControl.get_singleton()
	if control == null:
		quit(1)
		return
	var state := control.guidance_status()
	var ok: bool = state.get("status") == "preview" and state.get("restored") == true and not state.get("highlight_visible", true) and not control.describe_target("project_settings").get("visible", true)
	if ok:
		print("EDITOR_GUIDED_WORKFLOWS_RESTORE_OK")
	else:
		push_error("Guidance did not restore as an inert preview: %s" % state)
	quit(0 if ok else 1)
