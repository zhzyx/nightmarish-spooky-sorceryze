extends SceneTree


func _initialize() -> void:
	observe.call_deferred()


func observe() -> void:
	# The headless display driver can start an editor script at 64 x 64.
	root.size = Vector2i(1440, 960)
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("R08_FIXTURE"))
	var deadline := Time.get_ticks_msec() + 25000
	var observed := {}
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var dock := root.find_child("AIWorkbenchSidebar", true, false) as Control
		if not dock:
			continue
		var session := dock.find_child("WorkbenchBusinessSession", true, false)
		if not session or session.get_identity().get("id") != fixture.actor:
			continue
		var rows := dock.find_child("PendingJudgmentRows", true, false)
		var scroll := dock.find_child("WorkbenchSidebarScroll", true, false) as ScrollContainer
		var recovered := FileAccess.file_exists(fixture.response)
		if fixture.revision.is_empty():
			if recovered and not dock.is_visible_in_tree() and rows.get_child_count() == 0:
				finish({"sidebar_visible": false, "rows": 0})
				return
			continue
		if not dock.is_visible_in_tree() or rows.get_child_count() != 1:
			continue
		var row := rows.get_child(0) as Button
		if not row.has_focus() or not row.is_visible_in_tree() or row.tooltip_text != "b @ " + str(fixture.revision):
			continue
		var bounds := row.get_global_rect()
		if not scroll.get_global_rect().encloses(bounds) or not EditorInterface.get_base_control().get_global_rect().encloses(bounds):
			continue
		if observed.is_empty() and FileAccess.file_exists(fixture.worker_started) and not recovered:
			observed = {"row": row.text, "revision": row.tooltip_text, "row_bounds": str(bounds),
					"scroll_bounds": str(scroll.get_global_rect()), "editor_bounds": str(EditorInterface.get_base_control().get_global_rect()),
					"worker_started_while_focused": true}
			var marker := FileAccess.open(fixture.queue_visible, FileAccess.WRITE)
			marker.close()
		if not observed.is_empty() and recovered:
			observed["still_focused_after_recovery"] = true
			finish(observed)
			return
	var dock := root.find_child("AIWorkbenchSidebar", true, false) as Control
	if dock:
		var rows := dock.find_child("PendingJudgmentRows", true, false)
		var scroll := dock.find_child("WorkbenchSidebarScroll", true, false) as ScrollContainer
		printerr("Sidebar visible=", dock.is_visible_in_tree(), ", rows=", rows.get_child_count(),
				", scroll=", scroll.get_global_rect(), ", focus=", root.gui_get_focus_owner())
		if rows.get_child_count() > 0:
			printerr("First row ", rows.get_child(0).tooltip_text, " at ", rows.get_child(0).get_global_rect(), ", focused=", rows.get_child(0).has_focus())
	printerr("Worker started=", FileAccess.file_exists(fixture.worker_started), ", queue marker=",
			FileAccess.file_exists(fixture.queue_visible), ", recovery finished=", FileAccess.file_exists(fixture.response),
			", editor=", EditorInterface.get_base_control().get_global_rect())
	printerr("Startup queue and recovery did not reach the expected visible state")
	quit(1)


func finish(result: Dictionary) -> void:
	result["pid"] = OS.get_process_id()
	print("R08_NATIVE=" + JSON.stringify(result))
	root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
