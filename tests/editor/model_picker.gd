@tool
extends SceneTree
var dock: Node
var checks: Array = []
func finish(ok: bool, reason := ""):
	var f = FileAccess.open(OS.get_environment("MODEL_TEST_RESULT"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"ok": ok, "error": reason, "checks": checks}))
	f.close()
	quit(0 if ok else 1)
func _initialize():
	_run.call_deferred()
func _run():
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		finish(false, "missing dock")
		return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(2)
	backend.item_selected.emit(2)
	dock.find_child("CLINode", true, false).text = OS.get_environment("GONGGONG_NODE")
	dock.find_child("CodexEntry", true, false).text = OS.get_environment("MODEL_TEST_CODEX")
	dock.find_child("RefreshModels", true, false).pressed.emit()
	var picker = dock.find_child("ModelPicker", true, false)
	var status = dock.find_child("ModelStatus", true, false)
	var refresh = dock.find_child("RefreshModels", true, false)
	var until = Time.get_ticks_msec() + 40000
	while refresh.disabled and Time.get_ticks_msec() < until:
		await create_timer(0.05).timeout
	if picker.item_count < 3:
		finish(false, "refresh failed: " + status.text)
		return
	checks.append("live Codex model/list populated picker")
	picker.select(1)
	picker.item_selected.emit(1)
	var effort = dock.find_child("ReasoningEffort", true, false)
	if effort.disabled or effort.is_item_disabled(3):
		finish(false, "high unavailable for live default model")
		return
	effort.select(3)
	effort.item_selected.emit(3)
	checks.append("high effort selectable")
	var tabs = dock.find_child("AgentTabs", true, false)
	dock.find_child("AddAgent", true, false).pressed.emit()
	tabs.current_tab = 0
	tabs.tab_changed.emit(0)
	if effort.selected != 3:
		finish(false, "effort lost across session switch")
		return
	checks.append("session switch preserves model capabilities and high selection")
	for i in range(picker.item_count):
		if "luna" in str(picker.get_item_metadata(i)):
			picker.select(i)
			picker.item_selected.emit(i)
			if not effort.is_item_disabled(6) or effort.selected != 0:
				finish(false, "unsupported ultra remained selectable or stale selection")
				return
			checks.append("unsupported ultra disabled, new model uses default")
			break
	# Bad path must leave refresh retryable and keep chat untouched.
	dock.find_child("CodexEntry", true, false).text = "/nonexistent/codex"
	refresh.pressed.emit()
	if refresh.disabled or not "路径" in status.text:
		finish(false, "invalid path cannot retry")
		return
	checks.append("invalid path reports cause and allows retry")
	for api_backend in [0, 3]:
		backend.select(api_backend)
		backend.item_selected.emit(api_backend)
		dock.find_child("APIEndpoint", true, false).text = OS.get_environment("MODEL_TEST_ENDPOINT") + ("/responses" if api_backend == 3 else "/chat/completions")
		dock.find_child("APIModel", true, false).text = "fixture-reasoner"
		refresh.pressed.emit()
		until = Time.get_ticks_msec() + 5000
		while refresh.disabled and Time.get_ticks_msec() < until:
			await create_timer(0.05).timeout
		if effort.disabled or effort.is_item_disabled(3) or not effort.is_item_disabled(6):
			finish(false, "API advertised capabilities not respected")
			return
		picker.select(1)
		picker.item_selected.emit(1)
		if not effort.disabled or effort.selected != 0:
			finish(false, "unknown API model must keep default")
			return
	checks.append("both API modes honor declared efforts and keep unknown models at default")
	backend.select(1)
	backend.item_selected.emit(1)
	if not effort.disabled or effort.selected != 0:
		finish(false, "unverified CodeBuddy effort must remain default")
		return
	checks.append("CodeBuddy unknown capability uses default with TODO")
	finish(true)
