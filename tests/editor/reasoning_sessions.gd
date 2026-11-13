@tool
extends SceneTree
var dock: Node
var report := {"ok": false, "error": "", "checks": []}
func finish(ok: bool, reason := ""):
	report.ok = ok
	report.error = reason
	var f = FileAccess.open(OS.get_environment("WIRE_RESULT"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report))
	f.close()
	quit(0 if ok else 1)
func wait_catalog() -> bool:
	var deadline := Time.get_ticks_msec() + 40000
	while dock.get_model_catalog_snapshot().loading and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	return not dock.get_model_catalog_snapshot().loading
func select_model(id: String) -> bool:
	var picker = dock.find_child("ModelPicker", true, false)
	for i in range(picker.item_count):
		if str(picker.get_item_metadata(i)) == id:
			picker.select(i)
			picker.item_selected.emit(i)
			return true
	return false
func send_expected(text: String) -> bool:
	var send = dock.find_child("Send", true, false)
	if send.disabled:
		return false
	dock.find_child("ChatInput", true, false).text = "Fixture transport verification."
	send.pressed.emit()
	var stop = dock.find_child("Stop", true, false)
	var deadline := Time.get_ticks_msec() + 20000
	while not stop.disabled and Time.get_ticks_msec() < deadline:
		await create_timer(0.05).timeout
	if not stop.disabled:
		stop.pressed.emit()
		return false
	var matched := false
	for label in dock.find_child("Messages", true, false).find_children("*", "RichTextLabel", true, false):
		matched = matched or label.get_parsed_text().strip_edges() == text
	return matched
func _initialize():
	_run.call_deferred()
func _run():
	await create_timer(1).timeout
	dock = root.find_child("AI Chat", true, false)
	if dock == null:
		finish(false, "missing dock")
		return
	if not await wait_catalog():
		finish(false, "startup timeout")
		return
	var phase := OS.get_environment("WIRE_PHASE")
	if phase != "full":
		var tabs = dock.find_child("AgentTabs", true, false)
		var effort = dock.find_child("ReasoningEffort", true, false)
		if tabs.tab_count != 2:
			finish(false, "two saved sessions did not reopen")
			return
		for i in range(2):
			tabs.current_tab = i
			tabs.tab_changed.emit(i)
			if not await wait_catalog():
				finish(false, "restored catalog timeout")
				return
			var expected := 2 if phase == "legacy" or i == 0 else 0
			if effort.selected != expected or dock.get_model_catalog_snapshot().current != "fixture-full":
				finish(false, "restored reasoning mismatch: " + phase + ":" + str(i))
				return
		report.checks.append("both sessions restore their expected reasoning: " + phase)
		if phase == "legacy":
			effort.select(0)
			effort.item_selected.emit(0)
			tabs.current_tab = 0
			tabs.tab_changed.emit(0)
			if not await wait_catalog() or effort.selected != 2:
				finish(false, "migrated legacy preferences share mutable state")
				return
			report.checks.append("legacy per-model preference migrates separately into each old session")
		else:
			# Close inactive A; active B must remain default after tab indices shift.
			tabs.tab_close_pressed.emit(0)
			var confirm = dock.find_child("AgentCloseConfirmation", true, false)
			if confirm.visible:
				confirm.confirmed.emit()
			if tabs.tab_count != 1 or not await wait_catalog() or effort.selected != 0:
				finish(false, "closing other session changed active reasoning")
				return
			report.checks.append("closing another session preserves current default choice")
		await create_timer(0.5).timeout
		finish(true)
		return
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(2)
	backend.item_selected.emit(2)
	dock.refresh_model_catalog()
	if not await wait_catalog() or not select_model("fixture-full"):
		finish(false, "initial controlled catalog unavailable")
		return
	var effort = dock.find_child("ReasoningEffort", true, false)
	var tools = dock.get_ai_settings_control().find_child("AllowTools", true, false)
	tools.button_pressed = false
	tools.toggled.emit(false)
	var consultation = dock.find_child("ConsultationOnly", true, false)
	consultation.button_pressed = true
	consultation.toggled.emit(true)
	var ids := ["", "low", "medium", "high", "xhigh", "max", "ultra"]
	for i in range(2, 7):
		if effort.is_item_disabled(i) or str(effort.get_item_metadata(i)) != ids[i]:
			finish(false, "mapped effort unavailable")
			return
		effort.select(i)
		effort.item_selected.emit(i)
		if not await send_expected("wire-fixture-full-" + ids[i]):
			finish(false, "native send failed for " + ids[i])
			return
	report.checks.append("five native choices reached controlled CLI and returned distinct replies")
	if not select_model("fixture-none") or effort.selected != 0 or not effort.disabled:
		finish(false, "model without efforts did not default")
		return
	if not await send_expected("wire-fixture-none-default"):
		finish(false, "model without capability default send failed")
		return
	report.checks.append("unknown/empty capability model automatically defaults before native send")
	if not select_model("fixture-full") or effort.selected != 6:
		finish(false, "prior model preference did not restore before shrink")
		return
	var mode = FileAccess.open(OS.get_environment("WIRE_MODE"), FileAccess.WRITE)
	mode.store_string("reduced")
	mode.close()
	dock.refresh_model_catalog()
	if not await wait_catalog() or effort.selected != 0 or not effort.is_item_disabled(6) or effort.is_item_disabled(2):
		finish(false, "same-model capability shrink did not default stale ultra")
		return
	if not await send_expected("wire-fixture-full-default"):
		finish(false, "same-model capability shrink default send failed")
		return
	report.checks.append("same selected model lost ultra; refresh defaulted automatically and actual native send omitted effort")
	effort.select(2)
	effort.item_selected.emit(2)
	var tabs = dock.find_child("AgentTabs", true, false)
	dock.find_child("AddAgent", true, false).pressed.emit()
	if not await wait_catalog() or not select_model("fixture-full"):
		finish(false, "new session catalog unavailable")
		return
	effort.select(0)
	effort.item_selected.emit(0)
	tabs.current_tab = 0
	tabs.tab_changed.emit(0)
	if not await wait_catalog() or effort.selected != 2 or dock.get_model_catalog_snapshot().current != "fixture-full":
		finish(false, "session B default overwrote session A medium")
		return
	tabs.current_tab = 1
	tabs.tab_changed.emit(1)
	if not await wait_catalog() or effort.selected != 0 or dock.get_model_catalog_snapshot().current != "fixture-full":
		finish(false, "session A medium overwrote session B default")
		return
	report.checks.append("same model preserves distinct per-session medium and default selections")
	var settings = EditorInterface.get_editor_settings()
	if not Dictionary(settings.get_project_metadata("ai_chat", "reasoning_preferences", {})).is_empty():
		finish(false, "session preference leaked into project metadata")
		return
	settings.set_project_metadata("ai_chat", "reasoning_preferences", {"2:fixture-full": "medium"})
	report.checks.append("session edits left legacy project preference untouched")
	await create_timer(0.5).timeout
	finish(true)
