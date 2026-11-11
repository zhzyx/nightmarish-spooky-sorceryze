@tool
extends RefCounted
# Await run(host) from an isolated --headless --editor fixture.
# It only exercises editor layout; no model, project run or desktop input is used.

var host
var failures: Array = []
var checks: Array = []
var details: Dictionary = {}

func check(condition: bool, label: String) -> bool:
	host.check(condition, 'shell: ' + label)
	(checks if condition else failures).append(label)
	return condition

func settle():
	for i in range(4):
		await get_tree().process_frame

func get_tree() -> SceneTree:
	return host.get_tree()

func run(p_host):
	host = p_host
	await get_tree().create_timer(1.0).timeout
	var root: Window = get_tree().root
	var chat = root.find_child('AI Chat', true, false)
	var navigation = root.find_child('WorkspaceNavigation', true, false)
	var focus = root.find_child('WorkspaceFocus', true, false)
	var chooser = root.find_child('WorkspaceMenu', true, false)
	if not check(chat != null and navigation != null and focus != null and chooser != null, 'native shell navigation exists'):
		finish(); return
	var tabs: TabContainer = chat.get_parent()
	var bar: TabBar = tabs.get_tab_bar()
	var old_tab = tabs.current_tab
	var old_size = root.size
	var old_focus = EditorInterface.is_distraction_free_mode_enabled()
	var settings = EditorInterface.get_editor_settings()
	var old_separate = settings.get_setting('interface/editor/behavior/separate_distraction_mode')
	settings.set_setting('interface/editor/behavior/separate_distraction_mode', false)
	var scene_tab = -1
	var full_tabs: Array = []
	for i in range(tabs.get_tab_count()):
		if tabs.get_tab_title(i) == '2D': scene_tab = i
		if tabs.get_tab_control(i).name in ['AI Chat', 'Daqian', 'AINative', 'UnifiedSettings']:
			full_tabs.append(i)
	if not check(scene_tab >= 0 and not full_tabs.is_empty(), 'scene and full-workspace tabs available'):
		settings.set_setting('interface/editor/behavior/separate_distraction_mode', old_separate)
		finish(); return
	check(focus.shortcut == null, 'focus action does not register a duplicate shortcut')
	check(bar.tab_alignment == TabBar.ALIGNMENT_LEFT and bar.clip_tabs, 'tabs align left and allow native overflow')
	var title_bars = root.find_children('*', 'EditorTitleBar', true, false)
	var run_bars = root.find_children('*', 'EditorRunBar', true, false)
	check(title_bars.size() == 1 and run_bars.size() == 1, 'global toolbar and run controls remain present')
	for width in [1440, 850]:
		root.size = Vector2i(width, 1000)
		tabs.current_tab = scene_tab
		await settle()
		details['actual_width_' + str(width)] = root.size.x
		var rect: Rect2 = navigation.get_global_rect()
		check(rect.end.x <= root.size.x + 1, 'navigation fits viewport at ' + str(width))
		check(chooser.get_global_rect().end.x <= rect.end.x + 1 and focus.get_global_rect().end.x <= rect.end.x + 1, 'overflow and focus fit row at ' + str(width))
		check(bar.get_global_rect().end.x <= chooser.get_global_rect().position.x + 1, 'tabs never overlap overflow at ' + str(width))
		if not title_bars.is_empty() and not run_bars.is_empty():
			check(title_bars[0].get_global_rect().end.y <= rect.position.y + 1, 'workspace row is below global toolbar at ' + str(width))
			check(run_bars[0].get_global_rect().end.x <= root.size.x + 1, 'run controls fit viewport at ' + str(width))
		chooser.about_to_popup.emit()
		var popup: PopupMenu = chooser.get_popup()
		check(popup.item_count == tabs.get_tab_count(), 'all workspaces listed at ' + str(width))
		for item in range(popup.item_count):
			var target = popup.get_item_id(item)
			popup.id_pressed.emit(target)
			await settle()
			check(tabs.current_tab == target and tabs.get_tab_control(target).is_visible_in_tree(), 'overflow opens workspace ' + str(target) + ' at ' + str(width))
	# Exercise the same click path as a real toggle, with both existing preference modes.
	for separate in [false, true]:
		settings.set_setting('interface/editor/behavior/separate_distraction_mode', separate)
		tabs.current_tab = scene_tab
		await settle()
		if focus.button_pressed:
			focus.button_pressed = false
			focus.pressed.emit()
		focus.button_pressed = true
		focus.pressed.emit()
		check(EditorInterface.is_distraction_free_mode_enabled() and focus.text == 'Restore Layout', 'focus action enters and describes restore; separate=' + str(separate))
		for target in full_tabs:
			tabs.current_tab = target
			await settle()
			check(not focus.visible, 'full workspace hides scene focus action ' + str(target))
		tabs.current_tab = scene_tab
		await settle()
		check(focus.button_pressed and EditorInterface.is_distraction_free_mode_enabled(), 'scene focus survives full-workspace switching; separate=' + str(separate))
		focus.button_pressed = false
		focus.pressed.emit()
		check(not EditorInterface.is_distraction_free_mode_enabled(), 'restore action exits focus; separate=' + str(separate))
	var bottoms = root.find_children('*', 'EditorBottomPanel', true, false)
	if check(bottoms.size() == 1, 'bottom panel available for state roundtrip'):
		var bottom: TabContainer = bottoms[0]
		var old_bottom = bottom.current_tab
		var expand: Button
		for button in bottom.get_tab_bar().get_parent().find_children('*', 'Button', true, false):
			if button.shortcut and button.shortcut.get_name() == 'Expand Bottom Panel': expand = button
		if check(expand != null and bottom.get_tab_count() > 0, 'bottom expand action exists'):
			bottom.current_tab = 0
			await settle()
			expand.button_pressed = true
			await settle()
			for target in full_tabs:
				tabs.current_tab = target
				await settle()
				check(not bottom.visible and tabs.is_visible_in_tree(), 'full workspace temporarily hides expanded bottom panel ' + str(target))
			tabs.current_tab = scene_tab
			await settle()
			check(bottom.visible and bottom.current_tab == 0 and expand.button_pressed, 'scene restores bottom tab and expansion')
			expand.button_pressed = false
			bottom.current_tab = -1
			await settle()
			var side_slots = root.find_children('*', 'SideDockTabContainer', true, false)
			var side_visibility: Array = []
			for slot in side_slots: side_visibility.append(slot.visible)
			for target in full_tabs:
				tabs.current_tab = target
				await settle()
			tabs.current_tab = scene_tab
			await settle()
			check(bottom.visible and bottom.current_tab == -1 and not expand.button_pressed, 'collapsed bottom panel remains collapsed after workspace roundtrip')
			for i in range(side_slots.size()):
				check(side_slots[i].visible == side_visibility[i], 'side dock visibility restored ' + str(i))
			bottom.current_tab = old_bottom
	settings.set_setting('interface/editor/behavior/separate_distraction_mode', old_separate)
	EditorInterface.set_distraction_free_mode(old_focus)
	tabs.current_tab = old_tab
	root.size = old_size
	await settle()
	details['tested_widths'] = [1440, 850]
	details['display_boundary'] = 'Headless geometry and signals only; no pixel or native desktop focus assertion.'
	finish()

func finish():
	host.details['shell_layout'] = details
	var path = OS.get_environment('EDITOR_SHELL_RECEIPT')
	if not path.is_empty():
		var file = FileAccess.open(path, FileAccess.WRITE)
		file.store_string(JSON.stringify({'ok': failures.is_empty(), 'checks': checks, 'failures': failures, 'details': details}, '  '))
	print('EDITOR_SHELL_LAYOUT_OK' if failures.is_empty() else 'EDITOR_SHELL_LAYOUT_FAILED')
