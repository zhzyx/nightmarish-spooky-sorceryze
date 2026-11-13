
# Appended only to the isolated native acceptance restart fixture.
func _recovery_press_951(button) -> bool:
	if not _check(button != null and not button.disabled, "Recovery fixture attempted a disabled control"):
		return false
	button.pressed.emit()
	return true

func _assert_initial_confirmation_951():
	var disk := ConfigFile.new()
	_check(disk.load("res://.godot/editor/project_metadata.cfg") == OK and disk.has_section("design_confirmations"), "Initial public confirmation was not durable before dispatch")

func _fixture_children_951() -> Dictionary:
	var history: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/editor/ai_chat_history.json"))
	var children := {}
	for agent in history.agents:
		if agent.has("sub_agent"):
			children[str(agent.id)] = agent.sub_agent
	return children

func _restore_design_confirmation_951() -> bool:
	var settings = EditorInterface.get_editor_settings()
	var path := "res://.godot/editor/project_metadata.cfg"
	var disk := ConfigFile.new()
	if not _check(disk.load(path) == OK and disk.has_section("design_confirmations"), "Missing original durable fixture confirmation"):
		return false
	var keys := disk.get_section_keys("design_confirmations")
	if not _check(keys.size() == 1, "Expected one exact parent confirmation"):
		return false
	var key: String = keys[0]
	var original: Dictionary = disk.get_value("design_confirmations", key)
	# A normal tab round-trip persists the host's startup state normalization.
	var tabs = dock.find_child("SubAgentTabs", true, false)
	tabs.current_tab = 1
	tabs.tab_selected.emit(1)
	tabs.current_tab = 0
	tabs.tab_selected.emit(0)
	await create_timer(0.5).timeout
	var before := _fixture_children_951()
	var inert := false
	for child in before.values():
		if child.get("work_order", 0) == 3:
			inert = child.state == "interrupted" and child.get("state_before_restore", "") == "waiting" and not child.has("terminal_receipt")
	if not _check(inert, "Fixture did not reach cold never-started C"):
		return false
	# Fault injection is confined to this fixture's local confirmation store.
	settings.set_project_metadata("design_confirmations", key, null)
	disk.erase_section_key("design_confirmations", key)
	disk.save(path)
	var spawn = dock.find_child("SpawnWorkOrderAgents", true, false)
	var confirmation = dock.find_child("WorkOrderConfirmation", true, false)
	if not _recovery_press_951(spawn):
		return false
	if not confirmation.visible:
		print("CONFIRMATION_RECOVERY_PRECONDITION ", JSON.stringify({"children": before, "approval": original, "actor": OS.get_environment("USERNAME"), "queue_paused": dock.get_meta("queue_paused", false), "queue_count": dock.get_meta("queued_message_count", 0)}))
	if not _check(confirmation.visible and confirmation.title == "重新确认原设计", "Public continuation did not offer exact original-design reconfirmation: " + _text()):
		return false
	if not _recovery_press_951(confirmation.get_cancel_button()):
		return false
	await process_frame # AcceptDialog schedules hide through call_deferred.
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Cancel restored authorization")
	# A conflicting disk record is not treated as missing, even with a NIL cache.
	disk.set_value("design_confirmations", key, {"conflict": true})
	disk.save(path)
	if not _recovery_press_951(spawn):
		return false
	_check(not confirmation.visible, "Conflicting disk confirmation was offered for overwrite")
	disk.erase_section_key("design_confirmations", key)
	disk.save(path)
	settings.set_project_metadata("design_confirmations", key, {"conflict": true})
	if not _recovery_press_951(spawn):
		return false
	_check(not confirmation.visible, "Conflicting cached confirmation was offered for overwrite")
	settings.set_project_metadata("design_confirmations", key, null)
	if not _recovery_press_951(spawn):
		return false
	tabs.current_tab = 1
	tabs.tab_selected.emit(1)
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Switching away from the parent restored authorization")
	tabs.current_tab = 0
	tabs.tab_selected.emit(0)
	await process_frame
	# Identity and version are checked again at the confirmation boundary.
	if not _recovery_press_951(spawn):
		return false
	var actor_key := "USERNAME" if OS.has_environment("USERNAME") else "USER"
	var actor := OS.get_environment(actor_key)
	OS.set_environment(actor_key, actor + "-foreign-fixture")
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	OS.set_environment(actor_key, actor)
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Changed actor restored authorization")
	if not _recovery_press_951(spawn):
		return false
	var design_path: String = original.binding.workspace.path_join("design-docs").path_join(str(original.binding.request_id) + ".md")
	var design_bytes := FileAccess.get_file_as_bytes(design_path)
	FileAccess.open(design_path, FileAccess.WRITE).store_buffer(design_bytes + "\nDrift".to_utf8_buffer())
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	FileAccess.open(design_path, FileAccess.WRITE).store_buffer(design_bytes)
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Changed design restored authorization")
	if not _recovery_press_951(spawn):
		return false
	var tools = dock.get_ai_settings_control().find_child("AllowTools", true, false)
	tools.button_pressed = false
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	tools.button_pressed = true
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Tools-off confirmation restored authorization")
	if not _recovery_press_951(spawn):
		return false
	if not _check(not dock.find_child("Send", true, false).disabled, "Live probe Send is disabled"):
		return false
	_send("RECOVERY_LIVE_PROBE_951")
	var deadline := Time.get_ticks_msec() + 60000
	while not FileAccess.file_exists("res://recovery-live-started") and Time.get_ticks_msec() < deadline:
		await process_frame
	var live_started: bool = FileAccess.file_exists("res://recovery-live-started") and not dock.find_child("Stop", true, false).disabled
	_check(live_started, "Live rejection test never reached an actual pending model request")
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Running parent request restored authorization")
	FileAccess.open("res://recovery-live-release", FileAccess.WRITE).store_string("released after confirmation attempt")
	await _wait_marker("RECOVERY_LIVE_PROBE_FINISHED", 60.0)
	deadline = Time.get_ticks_msec() + 60000
	while (spawn.disabled or dock.get_meta("gonggong_reporting", "") != "recorded_file") and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _check(not spawn.disabled and dock.get_meta("gonggong_reporting", "") == "recorded_file", "Live parent reporting did not finish before recovery retry"):
		return false
	# A readable but unwritable file reaches save_project_metadata's real failure.
	if not _recovery_press_951(spawn):
		return false
	if not _check(confirmation.visible and confirmation.title == "重新确认原设计", "Read-only save test did not reach confirmation"):
		return false
	var made_read_only := FileAccess.set_read_only_attribute(path, true) == OK
	_check(made_read_only, "Cannot create the actual read-only metadata fixture")
	if not _recovery_press_951(confirmation.get_ok_button()):
		FileAccess.set_read_only_attribute(path, false)
		return false
	var no_cached_grant: bool = settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record"
	var no_disk_grant := disk.load(path) == OK and not disk.has_section_key("design_confirmations", key)
	FileAccess.set_read_only_attribute(path, false)
	_check(no_cached_grant and no_disk_grant and _text().contains("未能保存并回读"), "Failed metadata save granted authorization or claimed success")
	# A storage obstruction appearing while the dialog is open cannot grant access.
	if not _recovery_press_951(spawn):
		return false
	DirAccess.remove_absolute(path)
	DirAccess.make_dir_absolute(path)
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	_check(settings.get_project_metadata("design_confirmations", key, "missing-fixture-record") == "missing-fixture-record", "Unreadable metadata restored cached authorization")
	DirAccess.remove_absolute(path)
	disk.save(path)
	if not _recovery_press_951(spawn):
		return false
	if not _check(confirmation.visible and confirmation.title == "重新确认原设计", "Recovery did not remain retryable"):
		return false
	if not _recovery_press_951(confirmation.get_ok_button()):
		return false
	_check(disk.load(path) == OK and disk.has_section_key("design_confirmations", key) and disk.get_value("design_confirmations", key) == original, "Explicit recovery did not durably preserve the exact approval")
	await create_timer(0.4).timeout
	_check(_fixture_children_951() == before, "Confirmation itself changed worker, terminal, review or acceptance history")
	var result := {"ok": failure.is_empty(), "cancel": true, "disk_conflict": true, "cache_conflict": true, "parent_switch": true, "actor_drift": true, "design_drift": true, "tools_off": true, "live_request_started": live_started, "failed_save_no_grant": no_cached_grant and no_disk_grant, "storage_obstruction": true, "same_approval_persisted": true, "children_unchanged": true, "never_started_c_preserved": inert}
	FileAccess.open("res://confirmation-recovery.json", FileAccess.WRITE).store_string(JSON.stringify(result))
	return failure.is_empty()
