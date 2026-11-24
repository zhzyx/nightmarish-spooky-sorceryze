extends SceneTree


func _initialize() -> void:
	observe.call_deferred()


func observe() -> void:
	# The headless display driver can start an editor script at 64 x 64.
	root.size = Vector2i(1440, 960)
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("R08_FIXTURE"))
	var deadline := Time.get_ticks_msec() + 25000
	var observed := {}
	var filesystem := EditorInterface.get_resource_filesystem()
	var held := bool(fixture.get("hold_first_scan", false))
	var bound_before_layout := false
	var original_process_mode := filesystem.process_mode
	if fixture.get("phase") != "save":
		var path := "res://.godot/editor/editor_layout.cfg"
		if FileAccess.get_sha256(path) != fixture.layout_sha256:
			printerr("Reopened editor did not read the expected saved project layout")
			quit(1)
			return
	if held:
		# Keep the completed background scan from notifying EditorNode until the real
		# HTTP response has bound the first row. The editor and worker keep processing.
		if not filesystem.is_scanning():
			printerr("First scan already finished before the ordering probe started")
			quit(1)
			return
		filesystem.process_mode = Node.PROCESS_MODE_DISABLED
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var dock := root.find_child("AIWorkbenchSidebar", true, false) as Control
		if not dock:
			continue
		var session := dock.find_child("WorkbenchBusinessSession", true, false)
		if not session or session.get_identity().get("id") != fixture.actor:
			continue
		var chat := root.find_child("AI Chat", true, false) as Control
		var tabs := chat.get_parent() as TabContainer
		var selected := tabs.get_current_tab_control()
		if fixture.get("phase") == "save":
			if filesystem.is_scanning() or not FileAccess.file_exists(fixture.response):
				continue
			if not fixture.supplied and selected != chat:
				EditorInterface.set_main_screen_editor("AI Chat")
				continue
			if not dock.is_visible_in_tree():
				finish({"selected": str(selected.name), "sidebar_visible": false})
				return
			continue
		var rows := dock.find_child("PendingJudgmentRows", true, false)
		var scroll := dock.find_child("WorkbenchSidebarScroll", true, false) as ScrollContainer
		if held and rows.get_child_count() == 1:
			bound_before_layout = filesystem.is_scanning()
			filesystem.process_mode = original_process_mode
			held = false
		if filesystem.is_scanning():
			continue
		var recovered := FileAccess.file_exists(fixture.response)
		if fixture.revision.is_empty():
			if recovered and str(selected.name) == fixture.saved_main_screen and not dock.is_visible_in_tree() and rows.get_child_count() == 0:
				finish({"sidebar_visible": false, "rows": 0, "selected": str(selected.name)})
				return
			continue
		if not dock.is_visible_in_tree() or rows.get_child_count() != 1:
			continue
		var row := rows.get_child(0) as Button
		if not row.has_focus() or not row.is_visible_in_tree() or row.tooltip_text != "b @ " + str(fixture.revision):
			continue
		var bounds := row.get_global_rect()
		var editor_bounds := EditorInterface.get_base_control().get_global_rect()
		if not bounds.has_area() or not scroll.get_global_rect().encloses(bounds) or not editor_bounds.encloses(bounds):
			continue
		if observed.is_empty() and FileAccess.file_exists(fixture.worker_started) and not recovered:
			observed = {"row": row.text, "revision": row.tooltip_text, "row_bounds": str(bounds),
					"scroll_bounds": str(scroll.get_global_rect()), "editor_bounds": str(editor_bounds), "visible_focused_with_worker_ms": Time.get_ticks_msec(),
					"worker_started_while_focused": true, "sidebar_visible": true, "row_visible": true,
					"selected": str(selected.name), "focus": str(row.get_path()), "bound_before_layout": bound_before_layout}
			var marker := FileAccess.open(fixture.queue_visible, FileAccess.WRITE)
			marker.close()
		if not observed.is_empty() and recovered:
			observed["still_focused_after_recovery"] = true
			finish(observed)
			return
	var dock := root.find_child("AIWorkbenchSidebar", true, false) as Control
	if held:
		filesystem.process_mode = original_process_mode
	if dock:
		var rows := dock.find_child("PendingJudgmentRows", true, false)
		var scroll := dock.find_child("WorkbenchSidebarScroll", true, false) as ScrollContainer
		printerr("Sidebar visible=", dock.is_visible_in_tree(), ", rows=", rows.get_child_count(),
				", scroll=", scroll.get_global_rect(), ", focus=", root.gui_get_focus_owner())
		if rows.get_child_count() > 0:
			printerr("First row ", rows.get_child(0).tooltip_text, " at ", rows.get_child(0).get_global_rect(), ", focused=", rows.get_child(0).has_focus())
	if fixture.get("phase") == "save":
		printerr("AI Chat project did not reach its pre-close layout")
		quit(1)
		return
	printerr("Worker started=", FileAccess.file_exists(fixture.worker_started), ", queue marker=",
			FileAccess.file_exists(fixture.queue_visible), ", recovery finished=", FileAccess.file_exists(fixture.response),
			", editor=", EditorInterface.get_base_control().get_global_rect())
	printerr("Startup queue and recovery did not reach the expected visible state")
	quit(1)


func finish(result: Dictionary) -> void:
	result["pid"] = OS.get_process_id()
	result["elapsed_ms"] = Time.get_ticks_msec()
	result["display_driver"] = DisplayServer.get_name()
	print("R08_NATIVE=" + JSON.stringify(result))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
