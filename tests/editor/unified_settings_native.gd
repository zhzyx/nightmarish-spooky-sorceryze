@tool
extends Node
# All model, workspace and runtime fixtures are private and synthetic.

var failures: Array = []
var checks: Array = []
var details: Dictionary = {}
var chat
var workbench
var workspace
var settings_dock
var categories: TabContainer
var ai: Control
var environment: Control
var original_environment: Array = []
var callback_values: Array = []
var watchdog: Timer
var finishing := false

var root: Window:
	get: return get_tree().root

func _ready():
	print('UNIFIED_SETTINGS_FIXTURE_INITIALIZED')
	run.call_deferred()

func check(condition: bool, label: String) -> bool:
	print(('PASS ' if condition else 'FAIL ') + label)
	if condition: checks.append(label)
	else: failures.append(label)
	return condition

func field(name: String) -> Node:
	var value = ai.find_child(name, true, false)
	return value if value != null else environment.find_child(name, true, false)

func edit_field(name: String, value: String):
	var control = field(name)
	control.text = value
	control.text_changed.emit(value)

func current_environment() -> Array:
	var settings = EditorInterface.get_editor_settings()
	var runtime: Dictionary = chat.get_runtime_configuration()
	return [str(settings.get_setting('gonggong/workspace')), str(runtime.paths.get('workflow_python', '')), str(settings.get_setting('gonggong/tenant'))]

func finish():
	if finishing: return
	finishing = true
	if is_instance_valid(watchdog):
		watchdog.stop()
		watchdog.queue_free()
		watchdog = null
		await get_tree().process_frame
	var output = FileAccess.open(OS.get_environment('UNIFIED_SETTINGS_RECEIPT'), FileAccess.WRITE)
	if output:
		output.store_string(JSON.stringify({'ok':failures.is_empty(),'checks':checks,'failures':failures,'details':details}, '  '))
		output.close()
	print('UNIFIED_SETTINGS_NATIVE_OK' if failures.is_empty() else 'UNIFIED_SETTINGS_NATIVE_FAILED')
	if failures.is_empty():
		root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	else:
		get_tree().quit(1)

func wait_idle() -> bool:
	var deadline = Time.get_ticks_msec() + 15000
	while (not chat.find_child('Stop', true, false).disabled or not field('APIEndpoint').editable) and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.025).timeout
	return check(chat.find_child('Stop', true, false).disabled and field('APIEndpoint').editable, 'native chat returns to idle')

func open_section(section: String):
	settings_dock.get_meta('settings_navigator').call(section)
	await get_tree().process_frame

func environment_will_change():
	callback_values = current_environment()
	workspace.prepare_environment_change()

func run():
	print('UNIFIED_SETTINGS_FIXTURE_RUNNING')
	watchdog = Timer.new()
	watchdog.name = 'UnifiedFixtureWatchdog'
	watchdog.wait_time = 40.0
	watchdog.one_shot = true
	root.add_child(watchdog)
	watchdog.timeout.connect(func():
		check(false, 'fixture watchdog: a script error or operation did not reach completion')
		finish())
	watchdog.start()
	root.size = Vector2i(1440, 1000)
	await get_tree().create_timer(1.0).timeout
	settings_dock = root.find_child('UnifiedSettings', true, false)
	chat = root.find_child('AI Chat', true, false)
	if not check(settings_dock != null and chat != null and ClassDB.class_exists('UnifiedSettingsEditorPlugin'), 'native settings plugin and chat are registered'):
		finish(); return
	if not check(settings_dock.get_parent() is TabContainer, 'settings is a native main-screen tab'):
		finish(); return
	check(settings_dock.title == '设置', 'main-screen settings title is Chinese')
	check(not DirAccess.dir_exists_absolute('res://addons'), 'project contains no addons')
	var tabs: TabContainer = settings_dock.get_parent()
	var artist = root.find_child('AINative', true, false)
	var mode = OS.get_environment('UNIFIED_SETTINGS_MODE')
	if mode != 'reopen':
		check(artist.find_child('AINativeWorkbench', true, false) == null, 'artist controls start lazy before settings is opened')
	await open_section('ai')
	categories = settings_dock.find_child('UnifiedSettingsCategories', true, false)
	check(categories.get_tab_count() == 2 and categories.get_tab_title(0) == 'AI' and categories.get_tab_title(1) == '环境', 'settings has exactly AI and environment categories')
	check(tabs.current_tab == tabs.get_tab_idx_from_control(settings_dock) and categories.current_tab == 0, 'opening settings initializes artist without selecting its business tab')
	ai = chat.get_ai_settings_control()
	environment = chat.get_environment_settings_control()
	workbench = artist.find_child('AINativeWorkbench', true, false)
	var planner = root.find_child('Daqian', true, false)
	workspace = planner.find_child('DaqianWorkspace', true, false)
	if not check(ai != null and environment != null and workbench != null and workspace != null, 'all three live settings sources are initialized'):
		finish(); return
	check(ai.get_parent().name == 'ChatAISettingsSlot' and environment.get_parent().name == 'ChatEnvironmentSettingsSlot', 'chat getters refer to the actual centralized controls')
	var art_sections = workbench.get_settings_sections()
	check(art_sections.ai.get_parent().name == 'ArtAISettingsSlot' and art_sections.environment.get_parent().name == 'ArtEnvironmentSettingsSlot', 'artist getters refer to the actual centralized controls')
	check(workspace.get_model_settings_control().get_parent().name == 'ModelCatalogSettingsSlot', 'personal model catalog shares the central AI page')
	for name in ['AIBackend','ModelPicker','APIEndpoint','APIModel','APIKey','CLIModel','CodexModel','AllowTools','AutoExecuteCommands']:
		check(ai.find_children(name, '', true, false).size() == 1 and chat.find_child(name, true, false) == null, 'single centralized chat AI control: ' + name)
	for name in ['CLINode','CLIBridge','CLIEntry','CodexEntry','EngineBuildPython','EngineBuildArguments','GongGongWorkspace','GongGongPython','GongGongTenant']:
		check(environment.find_children(name, '', true, false).size() == 1 and chat.find_child(name, true, false) == null, 'single centralized environment control: ' + name)
	check(chat.find_child('ChatSettingsDialog', true, false) == null and chat.find_child('AdvancedSettingsScroll', true, false) == null, 'business chat no longer owns a settings popup')
	check(not workspace.workspace_path.editable and not workspace.python_path.editable and not workspace.connection_panel.visible, 'legacy planner environment mirror is hidden and readonly')
	check(workbench.python_edit.is_ancestor_of(workbench) == false and art_sections.environment.is_ancestor_of(workbench.python_edit), 'artist runtime fields belong to central environment')
	if mode == 'reopen':
		await verify_reopen()
		finish(); return
	verify_existing_values()
	await verify_navigation(tabs, artist, planner)
	verify_registry()
	await verify_model_catalog()
	await verify_busy_lock()
	await verify_scope_change()
	await verify_cross_window_environment()
	await verify_persistence()
	if OS.get_environment('UNIFIED_SETTINGS_DIAGNOSTIC_SKIP_LIFETIME') == '1':
		details.diagnostic_only = 'lifetime intentionally omitted for same-candidate shutdown comparison'
		print('UNIFIED_SETTINGS_DIAGNOSTIC_SKIP_LIFETIME')
	else:
		await verify_lifetime(tabs, artist)
	finish()

func verify_existing_values():
	check(field('EngineBuildPython').text == OS.get_environment('UNIFIED_BUILD_PYTHON'), 'existing build Python is retained')
	check(workbench.python_edit.text == OS.get_environment('UNIFIED_ART_PYTHON'), 'existing distinct artist Python is retained')
	check(field('CodexEntry').text == OS.get_environment('UNIFIED_CHAT_CLI') and workbench.cli_path_edit.text == OS.get_environment('UNIFIED_ART_CLI'), 'existing distinct chat and image CLI paths are retained')
	check(field('GongGongPython').text == OS.get_environment('UNIFIED_FRAMEWORK_PYTHON'), 'existing framework Python is retained independently')
	check(workbench._service_mode() == 'offline' and not workbench.managed_comfy_panel.autostart.button_pressed, 'settings navigation never starts generation or local model autostart')

func verify_navigation(tabs: TabContainer, artist: Control, planner: Control):
	for item in [['AdvancedToggle','ai'], ['EnvironmentSettings','environment'], ['GongGongEnvironmentSettingsButton','environment']]:
		tabs.current_tab = tabs.get_tab_idx_from_control(chat)
		chat.find_child(item[0], true, false).pressed.emit()
		await get_tree().process_frame
		check(settings_dock.is_visible_in_tree() and categories.current_tab == (1 if item[1] == 'environment' else 0), 'chat navigation opens central ' + item[1] + ': ' + item[0])
	tabs.current_tab = tabs.get_tab_idx_from_control(artist)
	workbench.native_buttons.settings.pressed.emit()
	await get_tree().process_frame
	check(settings_dock.is_visible_in_tree() and categories.current_tab == 1, 'artist settings button opens central environment')
	tabs.current_tab = tabs.get_tab_idx_from_control(planner)
	workspace._open_connection()
	await get_tree().process_frame
	check(settings_dock.is_visible_in_tree() and categories.current_tab == 1 and not workspace.connection_panel.visible, 'planner environment button opens central environment')
	await open_section('ai')
	var catalog = workspace.models_dialog
	catalog.key.text = 'synthetic-catalog-key'
	await open_section('environment')
	check(catalog.key.text.is_empty(), 'changing settings category clears catalog session key')
	await open_section('ai')
	catalog.key.text = 'synthetic-catalog-key'
	tabs.current_tab = tabs.get_tab_idx_from_control(chat)
	await get_tree().process_frame
	check(catalog.key.text.is_empty(), 'leaving settings clears catalog session key')
	await open_section('ai')

func verify_registry():
	var registry = AIChatEditorControl.get_singleton()
	check(settings_dock.get_meta('ai_control_page_only', false) and ai.get_meta('ai_control_page_only', false) and environment.get_meta('ai_control_page_only', false), 'central settings and borrowed native sections retain authority protection')
	for query in ['APIKey','AutoExecuteCommands','AllowTools','GongGongPython','EngineBuildPython','AINativeAISettings','SavePersonalModel']:
		check(registry.find_targets(query, 20).is_empty(), 'generic UI registry cannot expose settings authority: ' + query)
	var targets = registry.find_targets('设置', 20)
	check(not targets.is_empty(), 'generic UI registry can discover settings navigation page')

func verify_model_catalog():
	var catalog = workspace.models_dialog
	check(catalog.connect_local.disabled and catalog.embedded_save.disabled and not catalog.key.editable, 'personal catalog starts gated by workspace identity')
	# The helper is a private synthetic executable; it records input and never contacts a provider.
	catalog.user_id = 'fixture-user'
	catalog.chat = chat
	catalog.authorize_embedded(str(EditorInterface.get_editor_settings().get_setting('gonggong/workspace')))
	field('APIKey').text = 'synthetic-session-only-key'
	field('APIEndpoint').text = OS.get_environment('UNIFIED_ENDPOINT')
	field('APIModel').text = 'live-unsaved-model'
	edit_field('CLINode', OS.get_environment('UNIFIED_ALT_NODE'))
	field('CLIEntry').text = 'live-unsaved-buddy'
	edit_field('CodexEntry', OS.get_environment('UNIFIED_CHAT_CLI'))
	field('CodexModel').text = 'live-unsaved-codex'
	catalog._connect_local()
	var deadline = Time.get_ticks_msec() + 12000
	while catalog.pending and Time.get_ticks_msec() < deadline:
		await get_tree().create_timer(0.025).timeout
	var capture = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment('UNIFIED_MODEL_CAPTURE')))
	check(capture is Dictionary and capture.get('endpoint') == field('APIEndpoint').text and capture.get('editor_key') == field('APIKey').text and capture.get('model') == 'live-unsaved-model', 'catalog identifies current unsaved endpoint model and session key consistently')
	var runtime: Dictionary = chat.get_runtime_configuration()
	check(capture is Dictionary and capture.get('cli_node') == runtime.executables.node and capture.get('codex_entry') == runtime.executables.codex and capture.get('cli_entry') == 'live-unsaved-buddy' and capture.get('codex_model') == 'live-unsaved-codex', 'catalog combines current authoritative runtime snapshot with unsaved model controls consistently')
	catalog.clear_embedded_access()
	edit_field('CLINode', OS.get_environment('UNIFIED_NODE'))
	field('CLIEntry').text = OS.get_environment('UNIFIED_BUDDY')
	field('APIModel').text = 'fixture-model'

func verify_busy_lock():
	field('AllowTools').button_pressed = false
	field('AutoExecuteCommands').button_pressed = false
	chat.find_child('ConsultationOnly', true, false).button_pressed = true
	field('APIKey').text = 'synthetic-session-only-key'
	field('APIKey').text_changed.emit(field('APIKey').text)
	if not await wait_idle(): return
	chat.find_child('ChatInput', true, false).text = 'unified-settings-offline-lock-fixture'
	chat.find_child('Send', true, false).pressed.emit()
	await get_tree().create_timer(0.2).timeout
	check(not chat.find_child('Stop', true, false).disabled and field('AIBackend').disabled and not field('APIEndpoint').editable, 'active synthetic chat locks centralized AI controls')
	check(not field('GongGongWorkspace').editable and not field('GongGongPython').editable and field('SaveGongGongEnvironment').disabled, 'active synthetic chat locks shared environment and save')
	var runtime_before: Dictionary = chat.get_runtime_configuration()
	edit_field('GongGongPython', OS.get_environment('UNIFIED_SECOND_FRAMEWORK_PYTHON'))
	check(chat.get_runtime_configuration().configured == runtime_before.configured, 'even synthetic runtime edit emission cannot change the active task configuration')
	field('GongGongPython').text = runtime_before.paths.workflow_python
	var settings = EditorInterface.get_editor_settings()
	var previous = str(settings.get_setting('gonggong/tenant'))
	field('GongGongTenant').text = 'must-not-save-while-busy'
	field('SaveGongGongEnvironment').pressed.emit()
	check(str(settings.get_setting('gonggong/tenant')) == previous, 'even synthetic save emission cannot change busy task scope')
	field('GongGongTenant').text = previous
	await wait_idle()
	check(field('GongGongPython').editable and not field('SaveGongGongEnvironment').disabled, 'environment unlocks after the active synthetic chat finishes')

func verify_scope_change():
	var settings = EditorInterface.get_editor_settings()
	original_environment = current_environment()
	workspace.actor = {'user_id':'fixture-user', 'repo_id':'fixture-repo'}
	workspace.picker_scope = original_environment[0]
	workspace.watcher = {'pid':99999999}
	workspace.watcher_buffer = 'old synthetic watch'
	workspace.chat_work = {'old':{}}
	workspace.debug_process = {'pid':99999999}
	workspace.debug_sessions = {}
	workspace.models_dialog.user_id = 'fixture-user'
	workspace.models_dialog.authorize_embedded(original_environment[0])
	chat.set_environment_changing_handler(environment_will_change)
	field('GongGongWorkspace').text = OS.get_environment('UNIFIED_SECOND_WORKSPACE')
	field('GongGongPython').text = OS.get_environment('UNIFIED_FRAMEWORK_PYTHON')
	field('GongGongTenant').text = 'unified-synthetic-tenant'
	var epoch = workspace.scope_epoch
	field('SaveGongGongEnvironment').pressed.emit()
	check(callback_values == original_environment, 'environment callback observes old scope before all shared writes')
	check(workspace.actor.is_empty() and workspace.watcher.is_empty() and workspace.chat_work.is_empty() and workspace.debug_process.is_empty(), 'scope change releases old actor watch chat and debug state')
	check(workspace.models_dialog.authorized_root.is_empty() and workspace.models_dialog.user_id.is_empty(), 'scope change invalidates model catalog authorization')
	await get_tree().process_frame
	await get_tree().process_frame
	check(workspace.scope_epoch == epoch + 1 and not workspace.environment_reset_pending, 'workspace Python tenant writes coalesce to one scope reset')
	check(settings_dock.is_visible_in_tree(), 'saving new environment keeps the settings page selected')
	original_environment = current_environment()
	callback_values = []
	workspace.actor = {'user_id':'fixture-user', 'repo_id':'fixture-repo'}
	workspace.models_dialog.user_id = 'fixture-user'
	workspace.models_dialog.authorize_embedded(original_environment[0])
	epoch = workspace.scope_epoch
	edit_field('GongGongPython', OS.get_environment('UNIFIED_SECOND_FRAMEWORK_PYTHON'))
	check(callback_values == original_environment, 'workflow Python callback observes the old effective path before the canonical field write')
	check(chat.get_runtime_configuration().configured.workflow_python == OS.get_environment('UNIFIED_SECOND_FRAMEWORK_PYTHON'), 'workflow Python edit atomically persists its canonical field')
	await get_tree().process_frame
	await get_tree().process_frame
	check(workspace.actor.is_empty() and workspace.models_dialog.authorized_root.is_empty() and workspace.scope_epoch == epoch + 1 and not workspace.environment_reset_pending, 'runtime JSON notification resets scope once and revokes old model authorization')
	edit_field('GongGongPython', OS.get_environment('UNIFIED_FRAMEWORK_PYTHON'))
	await get_tree().process_frame
	await get_tree().process_frame
	chat.set_environment_changing_handler(Callable(workspace, 'prepare_environment_change'))

func write_external_workflow(configuration_path: String, value: String) -> bool:
	var configuration = JSON.parse_string(FileAccess.get_file_as_string(configuration_path))
	if not configuration is Dictionary or not configuration.get('runtimes') is Dictionary:
		return false
	configuration.runtimes.workflow_python = value
	var output := FileAccess.open(configuration_path, FileAccess.WRITE)
	if output == null: return false
	output.store_string(JSON.stringify(configuration, '  '))
	output.close()
	return true

func seed_cross_window_context() -> Dictionary:
	workspace.actor = {'user_id':'fixture-user', 'repo_id':'fixture-repo'}
	workspace.picker_scope = workspace._repo()
	workspace.watcher = {'pid':99999999}
	workspace.watcher_buffer = 'cross-window synthetic watch'
	workspace.chat_work = {'old':{}}
	workspace.debug_process = {'pid':99999999}
	workspace.debug_sessions = {}
	workspace.models_dialog.user_id = 'fixture-user'
	workspace.models_dialog.authorize_embedded(workspace._repo())
	return {'scope':workspace._canvas_scope(), 'root':workspace._repo(), 'actor':workspace.actor.duplicate(), 'generation':workspace.canvas_panel.canvas_generation, 'epoch':workspace.selection_epoch, 'board_epoch':workspace.scope_epoch}

func verify_cross_window_environment():
	var runtime: Dictionary = chat.get_runtime_configuration()
	var configuration_path: String = runtime.config_path
	var original_python: String = runtime.configured.workflow_python
	var original_display: String = runtime.paths.workflow_python
	# This existing +x file belongs to the runner's system-temp directory. It is
	# deliberately not an executable program: neither guarded entry may run it.
	var alternate_python := OS.get_environment('UNIFIED_BUILD_PYTHON')
	if not check(FileAccess.file_exists(alternate_python) and alternate_python != original_python, 'cross-window runtime uses an existing private Python stub'):
		return
	var marker := ProjectSettings.globalize_path('res://unexpected-cross-window-request')
	var bridge: String = workspace._repo().path_join('customizations/components/godot-host/daqian/board.py')
	DirAccess.make_dir_recursive_absolute(bridge.get_base_dir())
	var script := FileAccess.open(bridge, FileAccess.WRITE)
	if not check(script != null, 'cross-window request sentinel belongs to the private workspace'):
		return
	script.store_string('from pathlib import Path\nPath(' + JSON.stringify(marker) + ').write_text("unexpected old request", encoding="utf-8")\n')
	script.close()
	var runtime_notifications := []
	var edit_notifications := []
	var runtime_observer := func(): runtime_notifications.append(true)
	var edit_observer := func(_value): edit_notifications.append(true)
	chat.connect('runtime_configuration_changed', runtime_observer)
	field('GongGongPython').text_changed.connect(edit_observer)
	for entry in ['fresh_access', 'host_command']:
		# Re-establish the restored environment before authorizing this case.
		workspace._check_environment_changed()
		var old_context := seed_cross_window_context()
		var epoch: int = workspace.scope_epoch
		var selection_epoch: int = workspace.selection_epoch
		check(workspace._canvas_matches(old_context) and not workspace.models_dialog.authorized_root.is_empty(), entry + ': old workspace context and catalog authorization start valid')
		var wrote := write_external_workflow(configuration_path, alternate_python)
		check(wrote and chat.get_runtime_configuration().configured.workflow_python == alternate_python and field('GongGongPython').text == original_display and runtime_notifications.is_empty() and edit_notifications.is_empty(), entry + ': another window changes canonical Python without a local edit or signal')
		var args := PackedStringArray([bridge, '--synthetic-cross-window'])
		if entry == 'fresh_access':
			check(not await workspace._fresh_access(), entry + ': changed environment refuses the previous identity before starting a request')
		else:
			var response: Dictionary = await workspace._host_command(args, '--result', {'synthetic':'old scoped request'})
			check(response.get('environment_changed', false) and args == PackedStringArray([bridge, '--synthetic-cross-window']), entry + ': changed environment returns its guard before preparing a host request')
		check(workspace.actor.is_empty() and workspace.watcher.is_empty() and workspace.watcher_buffer.is_empty() and workspace.chat_work.is_empty() and workspace.debug_process.is_empty(), entry + ': cross-window detection releases old actor watch chat and debug state')
		check(workspace.models_dialog.authorized_root.is_empty() and workspace.models_dialog.user_id.is_empty() and not workspace._canvas_matches(old_context), entry + ': cross-window detection revokes the catalog and rejects the old context')
		check(workspace.scope_epoch == epoch + 1 and workspace.selection_epoch == selection_epoch + 1, entry + ': synchronous invalidation advances each old context epoch exactly once')
		check(not FileAccess.file_exists(marker), entry + ': no stale workspace request reaches the private sentinel')
		await get_tree().process_frame
		await get_tree().process_frame
		check(workspace.scope_epoch == epoch + 1 and workspace.selection_epoch == selection_epoch + 1 and not workspace.environment_reset_pending, entry + ': deferred observation does not invalidate the same context again')
		var restored := write_external_workflow(configuration_path, original_python)
		var before_refresh := FileAccess.get_file_as_string(configuration_path)
		chat.refresh_runtime_controls()
		check(restored and field('GongGongPython').text == original_display and FileAccess.get_file_as_string(configuration_path) == before_refresh and runtime_notifications.is_empty() and edit_notifications.is_empty(), entry + ': restoring external Python and refreshing only reads canonical settings')
	chat.disconnect('runtime_configuration_changed', runtime_observer)
	field('GongGongPython').text_changed.disconnect(edit_observer)
	workspace._check_environment_changed()

func verify_persistence():
	field('APIKey').text = 'synthetic-session-only-key'
	field('APIModel').text = 'persisted-unified-model'
	field('EngineBuildArguments').text = 'debug_symbols=yes'
	ai.find_child('SaveChatSettings', true, false).pressed.emit()
	workbench.python_edit.text = OS.get_environment('UNIFIED_ART_PYTHON')
	workbench.cli_path_edit.text = OS.get_environment('UNIFIED_ART_CLI')
	workbench.save_settings()
	workbench.managed_comfy_panel.runtime_path.text = OS.get_environment('UNIFIED_MESH_RUNTIME')
	workbench.managed_comfy_panel.save_local()
	var settings = EditorInterface.get_editor_settings()
	check(settings.get_setting('ai_chat/model') == 'persisted-unified-model' and settings.get_setting('ai_chat/build_arguments') == 'debug_symbols=yes', 'central chat save persists existing nonsecret settings keys')
	check(not settings.has_setting('ai_chat/api_key'), 'central chat save never creates a persisted API key')
	# A different writer may have updated the JSON while this form still holds
	# older text. Neither Save action may publish a stale group of runtime values.
	check(chat.set_runtime_field('node', OS.get_environment('UNIFIED_ALT_NODE')).is_empty(), 'authoritative runtime writer accepts a concurrent Node update')
	field('CLINode').text = OS.get_environment('UNIFIED_NODE')
	ai.find_child('SaveChatSettings', true, false).pressed.emit()
	field('SaveGongGongEnvironment').pressed.emit()
	check(chat.get_runtime_configuration().configured.node == OS.get_environment('UNIFIED_ALT_NODE'), 'chat and workspace saves preserve another runtime field despite stale displayed text')
	var configuration_path: String = chat.get_runtime_configuration().config_path
	var before_refresh := FileAccess.get_file_as_string(configuration_path)
	var refresh_notifications := []
	var observer := func(_value): refresh_notifications.append(true)
	field('CLINode').text_changed.connect(observer)
	chat.refresh_runtime_controls()
	field('CLINode').text_changed.disconnect(observer)
	check(field('CLINode').text == OS.get_environment('UNIFIED_ALT_NODE') and refresh_notifications.is_empty() and FileAccess.get_file_as_string(configuration_path) == before_refresh, 'explicit settings refresh rereads effective paths without emitting edits or writing stale values')
	edit_field('CLINode', OS.get_environment('UNIFIED_NODE'))
	var runtime: Dictionary = chat.get_runtime_configuration()
	var canonical = JSON.parse_string(FileAccess.get_file_as_string(runtime.config_path))
	check(canonical is Dictionary and canonical.get('runtimes', {}).get('node') == OS.get_environment('UNIFIED_NODE') and canonical.runtimes.workflow_python == OS.get_environment('UNIFIED_FRAMEWORK_PYTHON') and canonical.runtimes.build_python == OS.get_environment('UNIFIED_BUILD_PYTHON') and canonical.runtimes.codex == OS.get_environment('UNIFIED_CHAT_CLI'), 'central runtime controls persist through the single canonical configuration')
	check(not FileAccess.get_file_as_string(runtime.config_path).contains('synthetic-session-only-key'), 'canonical runtime configuration contains no session credential')
	var local = ConfigFile.new()
	check(local.load(workbench.state_dir.path_join('local.cfg')) == OK and local.get_value('host','python','') == OS.get_environment('UNIFIED_ART_PYTHON') and local.get_value('managed_comfy','runtime_root','') == OS.get_environment('UNIFIED_MESH_RUNTIME'), 'central artist environment saves into existing local machine config')
	details.artist_state_dir = workbench.state_dir
	details.chat_form_instance = ai.get_instance_id()
	details.artist_form_instance = workbench.get_settings_sections().ai.get_instance_id()

func verify_reopen():
	check(field('APIModel').text == 'persisted-unified-model' and field('EngineBuildArguments').text == 'debug_symbols=yes', 'reopening editor restores saved unified AI and build values')
	check(field('APIKey').text.is_empty(), 'reopening editor starts with no session-only key')
	check(field('GongGongWorkspace').text == OS.get_environment('UNIFIED_SECOND_WORKSPACE') and field('GongGongTenant').text == 'unified-synthetic-tenant', 'reopening editor restores saved shared environment')
	verify_existing_values()
	check(workbench.managed_comfy_panel.runtime_path.text == OS.get_environment('UNIFIED_MESH_RUNTIME'), 'reopening restores local model runtime choice')
	check(workspace.models_dialog.authorized_root.is_empty(), 'reopening requires new model catalog identity verification')

func verify_lifetime(tabs: TabContainer, artist: Control):
	var central = settings_dock
	var ai_id = ai.get_instance_id()
	var art_ai = workbench.get_settings_sections().ai
	var art_ai_id = art_ai.get_instance_id()
	var lease = ProjectSettings.globalize_path('res://synthetic-owned-lease')
	var lease_file = FileAccess.open(lease, FileAccess.WRITE)
	lease_file.store_string('fixture lease, no runtime process')
	lease_file.close()
	for index in workbench.service_choice.item_count:
		if workbench.service_choice.get_item_metadata(index) == 'codex': workbench.service_choice.select(index)
	workbench.managed_comfy_panel.lease_path = lease
	var old_parent = central.get_parent()
	old_parent.remove_child(central)
	check(is_instance_id_valid(ai_id) and ai.get_parent() == chat and not ai.visible, 'temporarily removing settings restores native controls to live source')
	check(is_instance_id_valid(art_ai_id) and workbench.is_ancestor_of(art_ai) and not central.is_ancestor_of(art_ai) and not art_ai.visible, 'temporarily removing settings restores artist controls to live source')
	check(FileAccess.file_exists(lease) and workbench.managed_comfy_panel.lease_path == lease, 'settings reparenting preserves the active local model lease')
	old_parent.add_child(central)
	await get_tree().process_frame
	await get_tree().process_frame
	await open_section('ai')
	check(ai.get_instance_id() == ai_id and ai.get_parent().name == 'ChatAISettingsSlot' and art_ai.get_parent().name == 'ArtAISettingsSlot', 'reentering settings rebinds the same controls exactly once')
	var panel = workbench
	var art_environment = panel.get_settings_sections().environment
	var art_environment_id = art_environment.get_instance_id()
	artist.remove_child(panel)
	check(panel.is_ancestor_of(art_ai) and panel.is_ancestor_of(art_environment) and not central.is_ancestor_of(art_ai) and not art_ai.visible, 'removing artist source reclaims borrowed controls before teardown')
	check(not FileAccess.file_exists(lease) and panel.managed_comfy_panel.lease_path.is_empty(), 'removing artist source releases its owned local model lease')
	panel.free()
	check(not is_instance_id_valid(art_ai_id) and not is_instance_id_valid(art_environment_id), 'destroying artist source frees both reclaimed forms without dangling controls')
	# The dock manager keeps its own reference, so final dock destruction is tested
	# through remove/reenter rather than freeing a manager-owned dock behind its back.
	check(is_instance_id_valid(ai_id) and ai.is_inside_tree(), 'other settings sources remain valid after artist teardown')
