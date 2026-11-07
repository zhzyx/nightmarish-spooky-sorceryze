@tool
extends SceneTree
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

func _initialize():
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

func finish():
	if finishing: return
	finishing = true
	if is_instance_valid(watchdog):
		watchdog.stop()
		watchdog.queue_free()
		watchdog = null
		await process_frame
	var output = FileAccess.open(OS.get_environment('UNIFIED_SETTINGS_RECEIPT'), FileAccess.WRITE)
	if output:
		output.store_string(JSON.stringify({'ok':failures.is_empty(),'checks':checks,'failures':failures,'details':details}, '  '))
		output.close()
	print('UNIFIED_SETTINGS_NATIVE_OK' if failures.is_empty() else 'UNIFIED_SETTINGS_NATIVE_FAILED')
	quit(0 if failures.is_empty() else 1)

func wait_idle() -> bool:
	var deadline = Time.get_ticks_msec() + 15000
	while (not chat.find_child('Stop', true, false).disabled or not field('APIEndpoint').editable) and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	return check(chat.find_child('Stop', true, false).disabled and field('APIEndpoint').editable, 'native chat returns to idle')

func open_section(section: String):
	settings_dock.get_meta('settings_navigator').call(section)
	await process_frame

func environment_will_change():
	var settings = EditorInterface.get_editor_settings()
	callback_values = [str(settings.get_setting('gonggong/workspace')), str(settings.get_setting('gonggong/python')), str(settings.get_setting('gonggong/tenant'))]
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
	await create_timer(1.0).timeout
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
		await process_frame
		check(settings_dock.is_visible_in_tree() and categories.current_tab == (1 if item[1] == 'environment' else 0), 'chat navigation opens central ' + item[1] + ': ' + item[0])
	tabs.current_tab = tabs.get_tab_idx_from_control(artist)
	workbench.native_buttons.settings.pressed.emit()
	await process_frame
	check(settings_dock.is_visible_in_tree() and categories.current_tab == 1, 'artist settings button opens central environment')
	tabs.current_tab = tabs.get_tab_idx_from_control(planner)
	workspace._open_connection()
	await process_frame
	check(settings_dock.is_visible_in_tree() and categories.current_tab == 1 and not workspace.connection_panel.visible, 'planner environment button opens central environment')
	await open_section('ai')
	var catalog = workspace.models_dialog
	catalog.key.text = 'synthetic-catalog-key'
	await open_section('environment')
	check(catalog.key.text.is_empty(), 'changing settings category clears catalog session key')
	await open_section('ai')
	catalog.key.text = 'synthetic-catalog-key'
	tabs.current_tab = tabs.get_tab_idx_from_control(chat)
	await process_frame
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
	field('CLINode').text = 'live-unsaved-node'
	field('CLIEntry').text = 'live-unsaved-buddy'
	field('CodexEntry').text = OS.get_environment('UNIFIED_CHAT_CLI')
	field('CodexModel').text = 'live-unsaved-codex'
	catalog._connect_local()
	var deadline = Time.get_ticks_msec() + 12000
	while catalog.pending and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	var capture = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment('UNIFIED_MODEL_CAPTURE')))
	check(capture is Dictionary and capture.get('endpoint') == field('APIEndpoint').text and capture.get('editor_key') == field('APIKey').text and capture.get('model') == 'live-unsaved-model', 'catalog identifies current unsaved endpoint model and session key consistently')
	check(capture is Dictionary and capture.get('cli_node') == 'live-unsaved-node' and capture.get('cli_entry') == 'live-unsaved-buddy' and capture.get('codex_model') == 'live-unsaved-codex', 'catalog identifies current unsaved CLI controls consistently')
	catalog.clear_embedded_access()
	field('CLINode').text = OS.get_environment('UNIFIED_NODE')
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
	await create_timer(0.2).timeout
	check(not chat.find_child('Stop', true, false).disabled and field('AIBackend').disabled and not field('APIEndpoint').editable, 'active synthetic chat locks centralized AI controls')
	check(not field('GongGongWorkspace').editable and not field('GongGongPython').editable and field('SaveGongGongEnvironment').disabled, 'active synthetic chat locks shared environment and save')
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
	original_environment = [str(settings.get_setting('gonggong/workspace')), str(settings.get_setting('gonggong/python')), str(settings.get_setting('gonggong/tenant'))]
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
	await process_frame
	await process_frame
	check(workspace.scope_epoch == epoch + 1 and not workspace.environment_reset_pending, 'workspace Python tenant writes coalesce to one scope reset')
	check(settings_dock.is_visible_in_tree(), 'saving new environment keeps the settings page selected')
	chat.set_environment_changing_handler(Callable(workspace, 'prepare_environment_change'))

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
	await process_frame
	await process_frame
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
