@tool
extends SceneTree

var failures: Array = []
var checks: Array = []
var chat
var ai
var dock
var indicator

func _initialize():
	run.call_deferred()

func check(value: bool, message: String):
	checks.append(message)
	if not value: failures.append(message)
	print(('PASS ' if value else 'FAIL ') + message)

func edit(name: String, value: String):
	var control = ai.find_child(name, true, false)
	if control == null:
		control = chat.find_child(name, true, false)
	control.text = value
	control.text_changed.emit(value)

func wait_probe():
	var deadline := Time.get_ticks_msec() + 10000
	while chat.get_ai_connection_status().state == 'checking' and Time.get_ticks_msec() < deadline:
		await create_timer(0.025).timeout
	check(chat.get_ai_connection_status().state != 'checking', 'connection probe completes within deadline')

func run():
	await create_timer(1.0).timeout
	chat = root.find_child('AI Chat', true, false)
	dock = root.find_child('UnifiedSettings', true, false)
	indicator = root.find_child('ProjectAIConnectionStatus', true, false)
	var entry = root.find_child('ProjectAIConfiguration', true, false)
	if chat == null or dock == null or indicator == null or entry == null:
		check(false, 'native project AI entry exists')
		finish(); return
	entry.pressed.emit()
	await process_frame
	check(dock.is_visible_in_tree(), 'top AI entry opens unified settings')
	check(dock.find_child('UnifiedSettingsCategories', true, false).current_tab == 0, 'top entry opens AI category')
	ai = chat.get_ai_settings_control()
	check(ai.get_parent().name == 'ChatAISettingsSlot', 'chat shares live project controls')
	check(root.find_child('DaqianWorkspace', true, false).get_model_settings_control().get_parent().name == 'ModelCatalogSettingsSlot', 'Tianshu model library integrated')
	check(root.find_child('AINativeWorkbench', true, false).get_settings_sections().ai.get_parent().name == 'ArtAISettingsSlot', 'image and Mesh services integrated')
	check(dock.find_child('ConnectProjectAI', true, false) != null and root.find_child('DaqianWorkspace', true, false).has_method('connect_project_models'), 'one-click entry routes to Tianshu')
	var mode := OS.get_environment('PROJECT_AI_MODE')
	var settings = EditorInterface.get_editor_settings()
	if mode in ['child', 'scheduled']:
		check(chat.get_ai_configuration().model == 'execution-override', 'active execution session keeps its model on restart: ' + mode)
		check(settings.get_project_metadata('ai_chat', 'model', '') == '', 'execution override never creates a project model default: ' + mode)
	elif mode == 'reopen':
		check(chat.get_ai_configuration().model == 'project-model', 'active session model persists after restart: ' + str(chat.get_ai_configuration()))
		check(chat.get_ai_configuration().endpoint == OS.get_environment('PROJECT_AI_ENDPOINT') + '/v1/chat/completions', 'project endpoint persists')
		check(ai.find_child('APIKey', true, false).text.is_empty(), 'session credential is not restored')
		check(indicator.get_meta('connection_state') != 'available', 'restart requires fresh availability evidence')
	elif mode == 'other':
		check(chat.get_ai_configuration().model != 'project-model', 'different project does not inherit another session model')
		check(settings.get_setting('ai_chat/model') != 'project-model', 'session model never overwrites editor global default')
	else:
		check(indicator.get_meta('connection_state') != 'available', 'model enumeration alone does not show green')
		edit('APIModel', 'project-model')
		edit('APIKey', 'project-ai-synthetic-secret')
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/v1/chat/completions')
		ai.find_child('SaveChatSettings', true, false).pressed.emit()
		check(settings.get_project_metadata('ai_chat', 'model', '') == '', 'central save does not create a project model default')
		check(chat.get_ai_configuration().scope == 'project', 'configuration API reports project scope')
		check(not JSON.stringify(chat.get_ai_configuration()).contains('project-ai-synthetic-secret'), 'shared configuration API excludes credentials')
		check(chat.get_daqian_models().current == 'project-model', 'Tianshu consumes same project model')
		dock.find_child('VerifyProjectAI', true, false).pressed.emit()
		check(indicator.get_meta('connection_state') == 'checking', 'top state immediately shows checking')
		await wait_probe()
		check(indicator.get_meta('connection_state') == 'available', 'successful text response marks current project available')
		var color: Color = indicator.get_theme_color('font_color')
		check(color.g > color.r and color.g > color.b, 'available circle is green')
		ai.find_child('AllowTools', true, false).button_pressed = false
		chat.find_child('ConsultationOnly', true, false).button_pressed = true
		await create_timer(0.8).timeout
		chat.find_child('ChatInput', true, false).text = 'project-ai-invalid-response'
		chat.find_child('Send', true, false).pressed.emit()
		var deadline := Time.get_ticks_msec() + 10000
		while not chat.find_child('Stop', true, false).disabled and Time.get_ticks_msec() < deadline:
			await create_timer(0.025).timeout
		check(indicator.get_meta('connection_state') == 'unavailable', 'malformed normal chat 200 response revokes previous green')
		chat.verify_ai_connection()
		await wait_probe()
		edit('APIKey', 'project-ai-synthetic-secret-updated')
		check(indicator.get_meta('connection_state') != 'available', 'credential edit invalidates green immediately')
		edit('APIModel', 'changed-model')
		check(indicator.get_meta('connection_state') != 'available', 'changing model immediately invalidates green')
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/fail/chat/completions')
		chat.verify_ai_connection()
		await wait_probe()
		check(indicator.get_meta('connection_state') == 'unavailable', 'provider failure is unavailable')
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/slow/chat/completions')
		chat.verify_ai_connection()
		await create_timer(0.15).timeout
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/fail/chat/completions')
		await create_timer(1.2).timeout
		check(indicator.get_meta('connection_state') != 'available', 'late success from previous configuration cannot turn green')
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/slow/chat/completions')
		chat.verify_ai_connection()
		var owner = chat.get_parent()
		owner.remove_child(chat)
		owner.add_child(chat)
		await process_frame
		check(chat.get_ai_connection_status().state != 'checking' and not dock.find_child('VerifyProjectAI', true, false).disabled, 'cancelled probe can be retried after dock reentry')
		await verify_cli()
		edit('APIModel', 'project-model')
		edit('APIEndpoint', OS.get_environment('PROJECT_AI_ENDPOINT') + '/v1/chat/completions')
		ai.find_child('SaveChatSettings', true, false).pressed.emit()
	finish()

func verify_cli():
	var environment = chat.get_environment_settings_control()
	check(chat.set_runtime_field('node', OS.get_environment('PROJECT_AI_PYTHON')).is_empty(), 'CLI probe uses isolated fixture runtime')
	environment.find_child('CLIBridge', true, false).text = OS.get_environment('PROJECT_AI_CLI_BRIDGE')
	environment.find_child('CLIEntry', true, false).text = OS.get_environment('PROJECT_AI_PYTHON')
	var backend = chat.find_child('AIBackend', true, false)
	backend.select(1)
	backend.item_selected.emit(1)
	await create_timer(0.8).timeout
	edit('CLIModel', 'cli-model')
	chat.verify_ai_connection()
	await wait_probe()
	check(indicator.get_meta('connection_state') == 'available', 'CLI text probe returns actual bounded transport success')
	edit('CLIModel', 'cli-failure')
	chat.verify_ai_connection()
	await wait_probe()
	check(indicator.get_meta('connection_state') == 'unavailable', 'CLI nonzero process exit cannot show green')
	edit('CLIModel', 'cli-slow')
	chat.verify_ai_connection()
	await create_timer(0.15).timeout
	edit('CLIModel', 'cli-model')
	await create_timer(1.1).timeout
	check(indicator.get_meta('connection_state') != 'available', 'changed CLI selection cancels obsolete text probe')
	backend.select(0)
	backend.item_selected.emit(0)
	await create_timer(0.5).timeout

func finish():
	var f := FileAccess.open(OS.get_environment('PROJECT_AI_REPORT'), FileAccess.WRITE)
	f.store_string(JSON.stringify({'passed':failures.is_empty(),'checks':checks,'failures':failures}))
	f.close()
	print('PROJECT_AI_CONFIG_OK' if failures.is_empty() else 'PROJECT_AI_CONFIG_FAILED')
	quit(0 if failures.is_empty() else 1)
