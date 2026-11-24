@tool
extends VBoxContainer

const ROLES := [["viewer", "只读"], ["editor", "编辑"], ["admin", "管理员"]]
var controller: Node
var model: Node
var _status := Label.new()
var _identity := Label.new()
var _system := Label.new()
var _secret_panel := VBoxContainer.new()
var _secret := LineEdit.new()
var _recipient := Label.new()
var _ack := Button.new()
var _tabs := TabContainer.new()
var _users := VBoxContainer.new()
var _keys := VBoxContainer.new()
var _links := VBoxContainer.new()
var _events := VBoxContainer.new()
var _forms := {}
var _defaults := {}
var _submit := {}
var _filter := OptionButton.new()
var _dialog := ConfirmationDialog.new()
var _intent := {}
var _scope := ""
var _signatures := {}
var _syncing := false


func _ready() -> void:
	controller = get_meta("controller")
	model = controller.accounts
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	label(self, "账号与权限", "TianxuanHeading" if get_meta("compact", false) else "TianxuanTitle")
	_identity.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_identity)
	button(self, "刷新账号与服务状态", "NativeAccountsRefresh", func(): model.refresh())
	_system.theme_type_variation = "TianxuanCaption"
	_system.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_system)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_ack = button(self, "已刷新并核对记录，恢复编辑", "NativeAccountsAcknowledge", func(): model.acknowledge_unknown())
	add_child(_secret_panel)
	label(_secret_panel, "本次签发", "TianxuanHeading")
	_recipient.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_secret_panel.add_child(_recipient)
	_secret.editable = false
	_secret.name = "NativeAccountsIssuedSecret"
	_secret_panel.add_child(_secret)
	button(_secret_panel, "复制", "NativeAccountsCopySecret", func():
		if not model.issued_secret.is_empty():
			DisplayServer.clipboard_set(model.issued_secret)
	)
	button(_secret_panel, "已保存，隐藏", "NativeAccountsHideSecret", func(): model.hide_secret())
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	var people := tab("账号")
	people.add_child(_users)
	form(people, "create_account", "创建账号并签发初始密钥", [["email", "邮箱", "line", ""], ["name", "姓名", "line", ""], ["role", "权限", "choice", ROLES]], "创建并签发")
	form(people, "invite", "创建邀请", [["email", "受邀者邮箱", "line", ""], ["role", "权限", "choice", ROLES]], "生成邀请码")
	var access := tab("访问密钥")
	access.add_child(_keys)
	form(access, "issue_key", "签发访问密钥", [["user_id", "账号", "user", ""], ["name", "用途", "line", "新增访问"], ["days", "有效天数", "number", 90]], "签发密钥")
	form(access, "issue_admin_key", "分配管理员密钥", [["user_id", "管理员账号", "admin", ""], ["name", "用途", "line", ""], ["days", "有效天数", "number", 90]], "签发管理员密钥")
	var identities := tab("身份绑定")
	identities.add_child(_links)
	form(identities, "bind_identity", "绑定外部身份", [["provider", "来源", "choice", [["tianshu", "天枢"], ["github", "GitHub"], ["oidc", "OIDC"], ["static", "静态适配器"]]], ["subject", "外部身份标识", "line", ""], ["user_id", "对应账号", "user", ""]], "绑定身份")
	var events := tab("身份记录")
	for choice in [["", "全部事件"], ["identity.linked", "绑定"], ["identity.rebound", "改绑"], ["identity.unlinked", "解绑"]]:
		_filter.add_item(choice[1])
		_filter.set_item_metadata(_filter.item_count - 1, choice[0])
	_filter.item_selected.connect(func(index: int): model.event_filter = _filter.get_item_metadata(index); model.events())
	events.add_child(_filter)
	events.add_child(_events)
	_dialog.confirmed.connect(func():
		if not _intent.is_empty():
			model.execute(_intent.operation, _intent.values, _intent.expected)
	)
	add_child(_dialog)
	model.changed.connect(_render)
	_render()
	model.refresh()


func label(parent: Node, text: String, variation := "TianxuanCaption") -> Label:
	var node := Label.new()
	node.text = text
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.theme_type_variation = variation
	parent.add_child(node)
	return node


func button(parent: Node, text: String, node_name: String, action: Callable) -> Button:
	var node := Button.new()
	node.text = text
	node.name = node_name
	node.pressed.connect(action)
	parent.add_child(node)
	return node


func tab(title: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	_tabs.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(box)
	return box


func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func _user_options(select: OptionButton, admin: bool) -> void:
	select.clear()
	select.add_item("选择账号")
	select.set_item_metadata(0, "")
	for user in model.data.get("users", {}).get("users", []):
		if not admin or user.role == "admin":
			select.add_item(str(user.email))
			select.set_item_metadata(select.item_count - 1, user.id)


func form(parent: Node, operation: String, title: String, fields: Array, action: String) -> void:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "TianxuanCard"
	parent.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	label(box, title, "TianxuanHeading")
	_forms[operation] = {}
	_defaults[operation] = {}
	for field in fields:
		label(box, field[1])
		var input: Control
		var initial: Variant = field[3]
		if field[2] in ["choice", "user", "admin"]:
			var select := OptionButton.new()
			if field[2] == "choice":
				for option in field[3]:
					select.add_item(option[1])
					select.set_item_metadata(select.item_count - 1, option[0])
				initial = field[3][0][0]
			select.item_selected.connect(func(_index: int): _edited(operation))
			input = select
		elif field[2] == "number":
			var number := SpinBox.new()
			number.min_value = 1
			number.max_value = 365
			number.value_changed.connect(func(_value: float): _edited(operation))
			input = number
		else:
			var line := LineEdit.new()
			line.max_length = 200
			line.text_changed.connect(func(_text: String): _edited(operation))
			input = line
		input.name = "NativeAccounts_" + operation + "_" + field[0]
		input.set_meta("kind", field[2])
		_forms[operation][field[0]] = input
		_defaults[operation][field[0]] = initial
		box.add_child(input)
	_submit[operation] = button(box, action, "NativeAccountsSubmit_" + operation, func(): _ask(operation, _values(operation), title))
	_submit[operation].theme_type_variation = "TianxuanPrimaryButton"


func _values(operation: String) -> Dictionary:
	var values := {}
	for name in _forms[operation]:
		var input: Control = _forms[operation][name]
		values[name] = input.get_selected_metadata() if input is OptionButton else int(input.value) if input is SpinBox else input.text
	return values


func _edited(operation: String) -> void:
	if not _syncing:
		model.edit(operation, _values(operation))


func _ask(operation: String, values: Dictionary, title: String) -> void:
	_intent = {"operation": operation, "values": values.duplicate(true), "expected": model.snapshot()}
	_dialog.title = title
	var subject := str(values.get("email", model.user_name(str(values.get("user_id", values.get("id", ""))))))
	_dialog.dialog_text = subject + "\n" + title + "。"
	_dialog.popup_centered()


func _new(topic: String, value: Variant) -> bool:
	var signature := JSON.stringify([_scope, value])
	if _signatures.get(topic) == signature:
		return false
	_signatures[topic] = signature
	return true


func _render() -> void:
	_syncing = true
	var scope: String = controller.session.scope_key()
	var switched := scope != _scope
	if switched:
		_scope = scope
		_dialog.hide()
		_intent.clear()
	var identity: Dictionary = controller.identity()
	_identity.text = "%s · %s" % [identity.get("email", ""), str({"viewer": tr("只读"), "editor": tr("编辑"), "admin": tr("管理员")}.get(identity.get("role", ""), ""))]
	_status.text = tr(model.status)
	for topic in model.errors:
		_status.text += "\n" + str(model.errors[topic])
	_system.text = tr("业务服务：%s · 仓库托管：%s") % [tr("已连接") if model.data.has("health") else tr("未取得状态"), tr("已配置") if model.data.get("hosting", {}).get("configured", false) else tr("未配置")]
	_ack.visible = not model.draft("pending").is_empty()
	_ack.disabled = model.saving
	_secret_panel.visible = not model.issued_secret.is_empty()
	_secret.text = model.issued_secret
	_recipient.text = "%s · %s" % [tr(model.issued_kind), model.issued_recipient]
	var writable: bool = model.editable()
	for operation in _forms:
		var values: Dictionary = model.draft(operation)
		if values.is_empty():
			values = _defaults[operation]
		var enabled: bool = writable and (operation != "issue_admin_key" or identity.get("can_issue_admin_keys", false))
		for name in _forms[operation]:
			var input: Control = _forms[operation][name]
			var value: Variant = values.get(name)
			if input is OptionButton:
				if input.get_meta("kind") in ["user", "admin"]:
					_user_options(input, input.get_meta("kind") == "admin")
				input.disabled = not enabled
				for index in input.item_count:
					if input.get_item_metadata(index) == value:
						input.select(index)
			elif input is SpinBox:
				input.editable = enabled
				if switched or not input.get_line_edit().has_focus():
					input.value = int(value)
			else:
				input.editable = enabled
				if switched or not input.has_focus():
					input.text = str(value)
		_submit[operation].disabled = not enabled
	if _new("users", [model.data.get("users", {}), writable]):
		clear(_users)
		for user in model.data.get("users", {}).get("users", []):
			label(_users, "%s · %s" % [user.get("name", ""), user.email], "TianxuanHeading")
			var role := OptionButton.new()
			for item in ROLES:
				role.add_item(item[1])
				role.set_item_metadata(role.item_count - 1, item[0])
				if user.role == item[0]:
					role.select(role.item_count - 1)
			role.disabled = not writable or user.id == identity.get("id")
			role.item_selected.connect(func(index: int):
				var requested: String = role.get_item_metadata(index)
				for original in role.item_count:
					if role.get_item_metadata(original) == user.role:
						role.select(original)
				_ask("set_role", {"id": user.id, "role": requested}, "修改账号权限")
			)
			_users.add_child(role)
	if _new("keys", [model.data.get("keys", {}), model.data.get("users", {}), writable]):
		clear(_keys)
		for access in model.data.get("keys", {}).get("keys", []):
			label(_keys, "%s · %s" % [model.user_name(access.user_id), access.name], "TianxuanHeading")
			label(_keys, tr("有效期：%s · %s") % [str(access.get("expires_at", "—")), tr("已撤销") if access.get("revoked_at") != null else tr("有效")])
			if access.get("revoked_at") == null:
				button(_keys, "撤销此密钥", "NativeAccountsRevoke", _ask.bind("revoke_key", {"id": access.id, "user_id": access.user_id}, "撤销所选访问密钥")).disabled = not writable
	if _new("links", [model.data.get("links", {}), model.data.get("users", {}), writable]):
		clear(_links)
		for link in model.data.get("links", {}).get("links", []):
			label(_links, "%s · %s\n%s" % [link.provider, link.subject, model.user_name(link.user_id)], "TianxuanHeading")
			var target := OptionButton.new()
			_user_options(target, false)
			for index in target.item_count:
				if target.get_item_metadata(index) == link.user_id:
					target.select(index)
			target.disabled = not writable
			_links.add_child(target)
			button(_links, "改绑到所选账号", "NativeAccountsRebind", func(): _ask("rebind_identity", {"id": link.id, "user_id": target.get_selected_metadata()}, "改绑外部身份")).disabled = not writable
			button(_links, "解除绑定", "NativeAccountsUnbind", _ask.bind("unbind_identity", {"id": link.id}, "解除此外部身份绑定")).disabled = not writable
	if _new("events", model.data.get("events", {})):
		clear(_events)
		for event in model.data.get("events", {}).get("events", []):
			label(_events, "%s · %s\n%s" % [event.type, event.get("created_at", ""), str(event.get("payload", {}).get("subject", ""))])
	_syncing = false


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_signatures.clear()
		_render()
