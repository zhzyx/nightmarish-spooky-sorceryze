@tool
extends Node
## Administrative forms share drafts; issued credentials exist only in memory.

signal changed
var workspace: Node
var data := {}
var errors := {}
var status := ""
var saving := false
var issued_secret := ""
var issued_recipient := ""
var issued_kind := ""
var event_filter := ""
var _generation := 0
var _serial := {}


func _ready() -> void:
	workspace = get_meta("workspace")
	workspace.changed.connect(func(topic: String):
		if topic == "identity":
			_generation += 1
			data.clear()
			errors.clear()
			_serial.clear()
			status = ""
			saving = false
			issued_secret = ""
			issued_recipient = ""
			issued_kind = ""
			event_filter = ""
			changed.emit()
		elif topic.begins_with("draft:accounts:"):
			changed.emit()
	)


func draft(section: String) -> Dictionary:
	return workspace.load_draft("accounts:" + section)


func editable() -> bool:
	return workspace.identity().get("role") == "admin" and not saving and draft("pending").is_empty() and issued_secret.is_empty()


func edit(section: String, values: Dictionary) -> void:
	if editable() and section in ["create_account", "invite", "issue_key", "issue_admin_key", "bind_identity"]:
		workspace.save_draft("accounts:" + section, values)


func read(topic: String, route: String) -> void:
	var generation := _generation
	_serial[topic] = int(_serial.get(topic, 0)) + 1
	var serial: int = _serial[topic]
	var result: Dictionary = await workspace.session.api_request(HTTPClient.METHOD_GET, route)
	if generation != _generation or serial != _serial.get(topic):
		return
	if result.status == 200:
		data[topic] = result.data
		errors.erase(topic)
	else:
		data.erase(topic)
		errors[topic] = workspace.error_message(result.status)
	changed.emit()


func refresh() -> void:
	var generation := _generation
	for pair in [["users", "/api/v1/users"], ["health", "/api/v1/health"], ["hosting", "/api/v1/gitea/status"]]:
		await read(pair[0], pair[1])
		if generation != _generation:
			return
	if workspace.identity().get("role") == "admin":
		for pair in [["keys", "/api/v1/auth/keys"], ["links", "/api/v1/identity/links"]]:
			await read(pair[0], pair[1])
			if generation != _generation:
				return
		await events()


func events() -> void:
	await read("events", "/api/v1/identity/events?limit=100" + ("&event_type=" + event_filter.uri_encode() if not event_filter.is_empty() else ""))


func user_name(id: String) -> String:
	for user in data.get("users", {}).get("users", []):
		if user.id == id:
			return str(user.email)
	return id


func snapshot() -> Dictionary:
	return {"scope": workspace.session.scope_key(), "users": data.get("users", {}), "keys": data.get("keys", {}), "links": data.get("links", {})}.duplicate(true)


func execute(operation: String, values: Dictionary, expected: Dictionary) -> void:
	if expected != snapshot() or not editable():
		return
	var payload := values.duplicate(true)
	var route := ""
	var method := HTTPClient.METHOD_POST
	match operation:
		"create_account":
			route = "/api/v1/users"
			payload.password = Crypto.new().generate_random_bytes(48).hex_encode()
		"invite": route = "/api/v1/invites"
		"set_role":
			if values.get("id") == workspace.identity().get("id"):
				return
			route = "/api/v1/users/" + str(values.get("id", "")).uri_encode() + "/role"
			method = HTTPClient.METHOD_PATCH
			payload = {"role": values.get("role", "viewer")}
		"issue_key", "issue_admin_key":
			if operation == "issue_admin_key" and not workspace.identity().get("can_issue_admin_keys", false):
				return
			route = "/api/v1/auth/keys" + ("/admin" if operation == "issue_admin_key" else "")
		"revoke_key":
			route = "/api/v1/auth/keys/" + str(values.get("id", "")).uri_encode()
			method = HTTPClient.METHOD_DELETE
			payload = {}
		"bind_identity": route = "/api/v1/identity/links"
		"rebind_identity", "unbind_identity":
			route = "/api/v1/identity/links/" + str(values.get("id", "")).uri_encode()
			method = HTTPClient.METHOD_DELETE if operation == "unbind_identity" else HTTPClient.METHOD_PATCH
			payload = {} if operation == "unbind_identity" else {"user_id": values.get("user_id", "")}
		_: return
	# Store non-secret intent only. Passwords, invitation codes and access keys never enter drafts.
	if not workspace.save_draft("accounts:pending", {"operation": operation, "values": values.duplicate(true)}):
		status = "无法保存请求记录，请检查草稿存储。"
		changed.emit()
		return
	var generation := _generation
	saving = true
	changed.emit()
	var result: Dictionary = await workspace.session.api_request(method, route, payload)
	payload.clear()
	if generation != _generation:
		return
	if result.status >= 200 and result.status < 300:
		workspace.clear_draft("accounts:" + operation)
		workspace.clear_draft("accounts:pending")
		if operation == "create_account":
			var created_id := str(result.data.get("user_id", result.data.get("id", "")))
			status = "账号已创建，正在签发初始密钥。"
			var key_payload := {"user_id": created_id, "name": "初始访问", "days": 90}
			if not workspace.save_draft("accounts:pending", {"operation": "issue_key", "values": key_payload}):
				saving = false
				status = "账号已创建，但无法记录密钥签发意图。请刷新后为该账号单独签发。"
				changed.emit()
				return
			result = await workspace.session.api_request(HTTPClient.METHOD_POST, "/api/v1/auth/keys", key_payload)
			if generation != _generation:
				return
			if result.status >= 200 and result.status < 300:
				workspace.clear_draft("accounts:pending")
			elif result.status >= 400 and result.status < 500:
				workspace.clear_draft("accounts:pending")
		if result.status >= 200 and result.status < 300:
			issued_secret = str(result.data.get("key", result.data.get("code", "")))
			issued_recipient = str(values.get("email", user_name(str(values.get("user_id", "")))))
			issued_kind = "邀请码" if operation == "invite" else "访问密钥"
			status = tr("已保存并读取最新记录。") if issued_secret.is_empty() else tr("请保存本次签发的%s；隐藏后无法再次读取明文。") % tr(issued_kind)
		else:
			status = tr("账号已创建，初始密钥签发被拒绝。") + workspace.error_message(result.status, true) if result.status >= 400 and result.status < 500 else tr("账号已创建，初始密钥签发未确认。请先刷新密钥列表核对，再为现有账号签发。")
	elif result.status >= 400 and result.status < 500:
		workspace.clear_draft("accounts:pending")
		status = workspace.error_message(result.status, true)
	else:
		status = "操作结果未确认，请先刷新账号、密钥或绑定记录进行核对。原意图已保留。"
	saving = false
	changed.emit()
	await refresh()


func hide_secret() -> void:
	issued_secret = ""
	issued_recipient = ""
	issued_kind = ""
	changed.emit()


func acknowledge_unknown() -> void:
	if not saving:
		workspace.clear_draft("accounts:pending")
		status = "已保留表单。请依据刚核对的记录决定后续操作。"
		changed.emit()
