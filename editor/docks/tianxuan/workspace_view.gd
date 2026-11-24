@tool
extends PanelContainer

signal companion_requested

var controller: Node
var session: Node
var ui_scale := 1.0
var compact := false
var _theme_script: Script
var _scripts := {}
var _body := VBoxContainer.new()
var _pages := VBoxContainer.new()
var _login := VBoxContainer.new()
var _status := Label.new()
var _address := LineEdit.new()
var _project := LineEdit.new()
var _email := LineEdit.new()
var _secret := LineEdit.new()
var _workspace_name := LineEdit.new()
var _mode := OptionButton.new()
var _submit := Button.new()
var _registration := CheckBox.new()
var _auth_mode := ""
var _page_instances := {}
var _page_picker := OptionButton.new()
var _connection := Label.new()
var _theme_choice := OptionButton.new()
var _language_choice := OptionButton.new()
var _nav := VBoxContainer.new()
var _navigation_scroll := ScrollContainer.new()
var _columns := HBoxContainer.new()
var _current_page := "home"
var _config_serial := 0
var _config_message := ""
var _layout_pending := false


func _ready() -> void:
	set_translation_domain(&"tianxuan-native")
	controller = get_meta("controller")
	if not controller.is_node_ready():
		await controller.ready
	session = controller.session
	_scripts = get_meta("scripts")
	_theme_script = _scripts.theme
	ui_scale = EditorInterface.get_editor_scale()
	compact = bool(get_meta("compact", false))
	name = "TianxuanSidebarView" if compact else "TianxuanWorkspaceView"
	theme_type_variation = "TianxuanCanvas"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	custom_minimum_size = Vector2(280 if compact else 430, 240) * ui_scale
	add_child(_body)
	_build_header()
	_body.add_child(_columns)
	_columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_build_navigation()
	_columns.add_child(_pages)
	_pages.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_pages.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_build_login()
	controller.changed.connect(_changed)
	controller.navigation_requested.connect(_navigate)
	session.status_changed.connect(func():
		_config_message = ""
		_update_session_status()
	)
	session.connection_changed.connect(_update_session_status)
	session.origin_changed.connect(func():
		_address.text = session.origin
		_load_auth_config()
	)
	resized.connect(_responsive)
	EditorInterface.get_editor_settings().settings_changed.connect(_apply_theme)
	_apply_theme()
	_changed("language")
	_changed("identity")
	_responsive()


func _build_header() -> void:
	var row := HBoxContainer.new()
	_body.add_child(row)
	var brand := Label.new()
	brand.text = "天璇"
	brand.theme_type_variation = "TianxuanHeading"
	brand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(brand)
	_language_choice.name = "TianxuanLanguage"
	_language_choice.tooltip_text = "语言"
	_language_choice.add_item("中文")
	_language_choice.add_item("English")
	_language_choice.item_selected.connect(func(index: int): controller.set_language("zh" if index == 0 else "en"))
	row.add_child(_language_choice)
	var companion := Button.new()
	companion.name = "ExpandTianxuan" if compact else "OpenTianxuanSidebar"
	companion.text = "展开" if compact else "打开侧栏"
	companion.pressed.connect(func(): companion_requested.emit())
	row.add_child(companion)
	_connection.theme_type_variation = "TianxuanCaption"
	_connection.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.add_child(_connection)
	_page_picker.name = "TianxuanPagePicker"
	_page_picker.item_selected.connect(func(index: int): _navigate(str(_page_picker.get_item_metadata(index)), ""))
	_body.add_child(_page_picker)
	var divider := HSeparator.new()
	_body.add_child(divider)


func _build_navigation() -> void:
	_nav.custom_minimum_size.x = 160 * ui_scale
	_navigation_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_navigation_scroll.follow_focus = true
	_navigation_scroll.custom_minimum_size.x = 180 * ui_scale
	_navigation_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_nav.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_columns.add_child(_navigation_scroll)
	_navigation_scroll.add_child(_nav)
	var group := ButtonGroup.new()
	for entry in [["home", "工作台", "AIChatWave"], ["documents", "文曲 · 文档", "TextFile"], ["design", "需求与执行", "Play"], ["requirements", "需求库", "FileList"], ["issues", "工单", "FileList"], ["repos", "多宝 · 仓库", "Filesystem"], ["repository_collaboration", "审查与发布", "VcsBranches"], ["game_config", "游戏配置", "Tools"], ["runs", "运行记录", "History"], ["execution", "执行与发布", "Play"], ["search", "搜索", "Search"], ["migration", "迁移与历史", "History"], ["accounts", "账号与权限", "Key"], ["account", "连接与外观", "Tools"]]:
		var button := Button.new()
		button.text = entry[1]
		button.name = "TianxuanPage_" + entry[0]
		button.theme_type_variation = "TianxuanNavigationButton"
		button.icon = EditorInterface.get_editor_theme().get_icon(entry[2], "EditorIcons")
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.toggle_mode = true
		button.button_group = group
		button.button_pressed = entry[0] == _current_page
		button.pressed.connect(_navigate.bind(entry[0], ""))
		_nav.add_child(button)
		_page_picker.add_item(entry[1])
		_page_picker.set_item_metadata(_page_picker.item_count - 1, entry[0])
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_nav.add_child(spacer)
	_theme_choice.name = "TianxuanAppearance"
	for text in ["跟随编辑器", "深色", "浅色"]:
		_theme_choice.add_item(text)
	_theme_choice.item_selected.connect(_choose_theme)
	var web := Button.new()
	web.text = "在浏览器中打开"
	web.pressed.connect(func():
		if session.valid_origin(session.origin):
			OS.shell_open(session.origin)
	)
	_nav.add_child(web)


func _field(label: String, control: Control) -> void:
	var title := Label.new()
	title.text = label
	title.theme_type_variation = "TianxuanCaption"
	_login.add_child(title)
	_login.add_child(control)


func _build_login() -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "TianxuanAccountPage"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_pages.add_child(scroll)
	_page_instances.account = scroll
	_login.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_login)
	var title := Label.new()
	title.text = "连接你的工作区"
	title.theme_type_variation = "TianxuanHeading" if compact else "TianxuanTitle"
	_login.add_child(title)
	var description := Label.new()
	description.text = "使用同一账号，在原生工作台与 Web 之间继续工作。"
	description.theme_type_variation = "TianxuanMuted"
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_login.add_child(description)
	_field("外观", _theme_choice)
	_address.name = "TianxuanServiceAddress"
	_address.text = session.origin
	_address.placeholder_text = "https://workspace.example.com"
	_field("工作区服务", _address)
	var connect_button := Button.new()
	connect_button.text = "连接服务"
	connect_button.pressed.connect(_connect_service)
	_login.add_child(connect_button)
	_project.name = "TianxuanProjectBinding"
	_project.text = str(session.get_identity().get("project", EditorInterface.get_editor_settings().get_project_metadata("tianxuan", "business_project", OS.get_environment("TIANXUAN_PROJECT"))))
	if _project.text.is_empty():
		_project.text = "workspace"
	_field("业务项目", _project)
	_mode.name = "TianxuanAuthenticationMode"
	_mode.add_item("个人访问密钥")
	_mode.item_selected.connect(func(_index: int): _update_auth_fields())
	_field("登录方式", _mode)
	_email.name = "TianxuanEmail"
	_email.placeholder_text = "账号邮箱"
	_login.add_child(_email)
	_secret.name = "TianxuanCredential"
	_secret.secret = true
	_field("凭据", _secret)
	_registration.text = "注册新账号"
	_registration.toggled.connect(func(_enabled: bool): _update_auth_fields())
	_login.add_child(_registration)
	_workspace_name.placeholder_text = "新工作空间名称"
	_login.add_child(_workspace_name)
	_submit.name = "AuthenticateTianxuan"
	_submit.text = "登录工作区"
	_submit.theme_type_variation = "TianxuanPrimaryButton"
	_submit.pressed.connect(_authenticate)
	_login.add_child(_submit)
	var logout := Button.new()
	logout.text = "退出当前账号"
	logout.pressed.connect(func(): session.reset())
	_login.add_child(logout)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.theme_type_variation = "TianxuanMuted"
	_login.add_child(_status)
	_update_auth_fields()
	_connect_service()


func _connect_service() -> void:
	var previous_origin: String = session.origin
	_config_message = ""
	if not session.set_origin(_address.text):
		_config_serial += 1
		_submit.disabled = true
		_update_session_status()
		return
	if previous_origin == session.origin:
		_load_auth_config()


func _load_auth_config() -> void:
	_config_serial += 1
	var serial := _config_serial
	_submit.disabled = true
	_config_message = "正在连接服务…"
	_update_session_status()
	var response: Dictionary = await session.auth_config()
	if serial != _config_serial:
		return
	if response.status != 200 or str(response.data.get("mode", "")) not in ["accounts", "keys", "legacy"]:
		_config_message = "无法读取服务登录配置，请检查地址和编辑器代理后重试。"
		_update_session_status()
		return
	_auth_mode = str(response.data.get("mode", ""))
	EditorInterface.get_editor_settings().set_setting("network/web_platform/url", session.origin)
	_mode.clear()
	if _auth_mode == "accounts":
		_mode.add_item("账号与密码")
	_mode.add_item("个人访问密钥")
	_submit.disabled = false
	_update_auth_fields()
	_config_message = "服务已连接，请登录工作区。" if session.get_identity().is_empty() else "服务已连接。"
	_update_session_status()


func _update_auth_fields() -> void:
	var accounts := _auth_mode == "accounts" and _mode.selected == 0
	_email.visible = accounts
	_registration.visible = accounts
	_workspace_name.visible = accounts and _registration.button_pressed
	_secret.placeholder_text = "账号密码" if accounts else "个人访问密钥"
	_submit.text = "注册并登录" if _workspace_name.visible else "登录工作区"


func _authenticate() -> void:
	if _submit.disabled:
		return
	_config_message = ""
	var secret := _secret.text
	_secret.clear()
	_submit.disabled = true
	var accounts := _auth_mode == "accounts" and _mode.selected == 0
	if accounts and _registration.button_pressed:
		var result: Dictionary = await session.register_account(_workspace_name.text.strip_edges(), _email.text.strip_edges(), secret)
		if result.status < 200 or result.status >= 300:
			_status.text = controller.error_message(result.status, true)
			_submit.disabled = false
			return
	var success: bool = await session.authenticate(_email.text.strip_edges() if accounts else "", secret, _project.text.strip_edges())
	_submit.disabled = false
	_status.text = session.status_text
	if success:
		EditorInterface.get_editor_settings().set_project_metadata("tianxuan", "business_project", _project.text.strip_edges())
		_navigate("home", "")


func _update_session_status() -> void:
	var identity: Dictionary = session.get_identity()
	_status.text = session.status_text if _config_message.is_empty() else tr(_config_message)
	_connection.text = tr("尚未登录") if identity.is_empty() else "%s · %s%s" % [identity.get("name", identity.id), identity.project, "" if session.online else tr(" · 离线")]


func _changed(topic: String) -> void:
	_queue_layout()
	if topic == "language":
		_language_choice.select(0 if controller.language == "zh" else 1)
		propagate_notification(NOTIFICATION_TRANSLATION_CHANGED)
		_update_session_status()
	elif topic == "identity":
		_update_session_status()
		if session.get_identity().is_empty():
			_secret.clear()
			_navigate("account", "")
		else:
			_project.text = str(session.get_identity().project)
			_navigate(_current_page, "")


func _navigate(page: String, _object_id: String) -> void:
	if session.get_identity().is_empty():
		page = "account"
	if page in ["home", "documents", "design", "requirements", "issues", "repos", "repository_collaboration", "game_config", "runs", "search", "migration", "accounts", "execution"] and not _page_instances.has(page):
		var view: Control = _scripts[page].new()
		view.set_meta("controller", controller)
		view.set_meta("compact", compact)
		view.set_meta("ui_scale", ui_scale)
		view.set_meta("markdown_script", _scripts.markdown)
		view.set_meta("asset_script", _scripts.issue_assets)
		view.set_meta("flow_script", _scripts.issue_flow)
		view.set_meta("page_kind", page)
		_pages.add_child(view)
		_page_instances[page] = view
	if not _page_instances.has(page):
		return
	_current_page = page
	for key in _page_instances:
		_page_instances[key].visible = key == page
	for child in _nav.get_children():
		if child is Button and child.toggle_mode:
			child.set_pressed_no_signal(child.name == "TianxuanPage_" + page)
	for index in _page_picker.item_count:
		if _page_picker.get_item_metadata(index) == page:
			_page_picker.select(index)
	_queue_layout()


func _queue_layout() -> void:
	if not _layout_pending:
		_layout_pending = true
		_prepare_layout.call_deferred()


func _prepare_layout() -> void:
	_layout_pending = false
	_theme_script.prepare_layout(self)


func _responsive() -> void:
	var narrow := compact or size.x < 760 * ui_scale
	_nav.visible = not narrow
	_navigation_scroll.visible = not narrow
	_page_picker.visible = narrow


func _choose_theme(index: int) -> void:
	var settings := EditorInterface.get_editor_settings()
	settings.set_setting("interface/tianxuan/appearance", index)
	_apply_theme()


func _apply_theme() -> void:
	var settings := EditorInterface.get_editor_settings()
	var mode := int(settings.get_setting("interface/tianxuan/appearance")) if settings.has_setting("interface/tianxuan/appearance") else 0
	var base := EditorInterface.get_editor_theme()
	var dark := base.get_color("base_color", "Editor").get_luminance() < 0.5
	if mode > 0:
		dark = mode == 1
	theme = _theme_script.build(base, ui_scale, dark)
	_theme_choice.select(mode)
