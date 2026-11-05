@tool
extends SceneTree

func _initialize():
	_run.call_deferred()

func _run():
	await create_timer(1.0).timeout
	var dock = root.find_child("AI Chat", true, false)
	if dock == null or dock.find_child("SpawnWorkOrderAgents", true, false) == null:
		push_error("Parallel work-order UI missing from candidate editor")
		quit(1)
		return
	var settings = EditorInterface.get_editor_settings()
	if not settings.has_setting("ai_chat/parallel_work_orders_config"):
		push_error("Parallel host setting was not registered")
		quit(1)
		return
	print("ISSUE72_EDITOR_PARALLEL_UI_OK")
	quit(0)
