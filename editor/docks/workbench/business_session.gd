@tool
extends VBoxContainer

signal identity_changed

var _origin: String
var _token := ""
var _owned_session := false
var _identity := {}
var _generation := 0
var _status := Label.new()
var _form := VBoxContainer.new()
var _email := LineEdit.new()
var _secret := LineEdit.new()
var _project := LineEdit.new()
var _sign_out := Button.new()


func _ready() -> void:
	_origin = OS.get_environment("TIANXUAN_API").strip_edges().trim_suffix("/")
	if _origin.is_empty():
		_origin = "http://127.0.0.1:8000"
	_status.name = "SessionStatus"
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	var actions := HBoxContainer.new()
	add_child(actions)
	var choose := Button.new()
	choose.name = "ChooseAccount"
	choose.text = "天璇账号"
	choose.pressed.connect(_toggle_form)
	actions.add_child(choose)
	_sign_out.name = "SignOut"
	_sign_out.text = "退出"
	_sign_out.pressed.connect(_sign_out_pressed)
	actions.add_child(_sign_out)
	add_child(_form)
	var service := Label.new()
	service.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	service.text = "服务地址 " + _origin
	_form.add_child(service)
	_email.name = "AccountEmail"
	_email.placeholder_text = "账号邮箱（使用个人密钥时留空）"
	_form.add_child(_email)
	_secret.name = "AccountSecret"
	_secret.placeholder_text = "密码或个人访问密钥"
	_secret.secret = true
	_form.add_child(_secret)
	_project.name = "BusinessProject"
	_project.placeholder_text = "业务项目"
	_project.text = OS.get_environment("TIANXUAN_PROJECT").strip_edges()
	if _project.text.is_empty():
		_project.text = "workspace"
	_form.add_child(_project)
	var submit := Button.new()
	submit.name = "Authenticate"
	submit.text = "登录此项目"
	submit.pressed.connect(_submit)
	_form.add_child(submit)
	_form.hide()
	_reset("尚未登录天璇")
	var supplied := OS.get_environment("TIANXUAN_TOKEN")
	if not supplied.is_empty():
		_authenticate("", supplied, _project.text)


func get_identity() -> Dictionary:
	return _identity.duplicate()


func _toggle_form() -> void:
	_form.visible = not _form.visible
	if _form.visible:
		_email.grab_focus()
	else:
		_secret.clear()


func _submit() -> void:
	var secret := _secret.text
	_secret.clear()
	_authenticate(_email.text.strip_edges(), secret, _project.text.strip_edges())


func _sign_out_pressed() -> void:
	_reset("已退出天璇")
	_secret.clear()
	_email.clear()
	_form.hide()


func _reset(message: String) -> void:
	_generation += 1
	var old_token := _token
	var revoke := _owned_session
	_token = ""
	_owned_session = false
	_identity.clear()
	_sign_out.hide()
	_status.text = message
	identity_changed.emit()
	if revoke:
		_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", old_token, {})


func _matches(value: String, pattern: String) -> bool:
	var expression := RegEx.new()
	return expression.compile(pattern) == OK and expression.search(value) != null


func _authenticate(email: String, secret: String, project: String) -> void:
	_reset("正在验证天璇账号…")
	var attempt := _generation
	var secure_origin := _matches(_origin, "^https://([A-Za-z0-9.-]+|\\[[0-9A-Fa-f:]+\\])(:[0-9]{1,5})?$")
	var loopback := _matches(_origin, "^http://(127\\.0\\.0\\.1|localhost|\\[::1\\])(:[0-9]{1,5})?$")
	if not (secure_origin or loopback):
		_status.text = "天璇服务需要 HTTPS 或本机回环地址"
		return
	if not _matches(project, "^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}(/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})?$"):
		_status.text = "请输入有效的业务项目"
		return
	if secret.is_empty() or (email.is_empty() and ("\r" in secret or "\n" in secret)):
		_status.text = "请输入有效凭据以重新认证"
		return
	var credential := secret
	if not email.is_empty():
		var login := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/session", "", {"email": email, "password": secret})
		credential = str(login.data.get("token", ""))
		if attempt != _generation:
			if not credential.is_empty():
				_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", credential, {})
			return
		if login.status != 200 or credential.is_empty():
			_status.text = "登录失败，请重新认证" if login.status in [401, 403] else "无法登录天璇，请检查服务后重试"
			return
	_token = credential
	_owned_session = not email.is_empty()
	var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", credential, {})
	if attempt != _generation:
		return
	if me.status != 200 or str(me.data.get("id", "")).is_empty() or str(me.data.get("role", "")).is_empty():
		_reset("凭据失效，请重新认证" if me.status in [401, 403] else "无法核实天璇身份，请重试")
		_form.show()
		return
	_identity = {"id": me.data.id, "name": me.data.get("name", ""), "role": me.data.role, "project": project}
	_status.text = "%s · %s · %s" % [_identity.name, _identity.role, project]
	_sign_out.show()
	_email.clear()
	_form.hide()
	identity_changed.emit()


# Routes belong to the configured deployment. Each request captures its verified session.
func api_request(method: int, route: String, payload: Dictionary = {}) -> Dictionary:
	if _identity.is_empty():
		return {"status": 401, "data": {}}
	if not route.begins_with("/api/v1/") or "#" in route or "\\" in route or "\n" in route or "\r" in route:
		return {"status": 0, "data": {}}
	for parameter in route.get_slice("?", 1).split("&", false):
		if parameter.get_slice("=", 0).uri_decode() == "project":
			return {"status": 0, "data": {}}
	var scoped_route := route + ("&" if "?" in route else "?") + "project=" + str(_identity.project).uri_encode()
	var attempt := _generation
	var reply := await _exchange(method, scoped_route, _token, payload)
	if attempt != _generation:
		return {"status": 0, "data": {}}
	if reply.status == 401:
		_reset("凭据失效，请重新认证")
		_form.show()
	return reply


func _exchange(method: int, route: String, credential: String, payload: Dictionary) -> Dictionary:
	var http := HTTPRequest.new()
	http.max_redirects = 0
	http.timeout = 12.0
	http.body_size_limit = 8 * 1024 * 1024
	add_child(http)
	var headers := PackedStringArray(["Accept: application/json"])
	if not credential.is_empty():
		headers.append("Authorization: Bearer " + credential)
	var body := ""
	if method not in [HTTPClient.METHOD_GET, HTTPClient.METHOD_HEAD]:
		headers.append("Content-Type: application/json")
		body = JSON.stringify(payload)
	var reply := {"status": 0, "data": {}}
	if http.request(_origin + route, headers, method, body) == OK:
		var response: Array = await http.request_completed
		if response[0] == HTTPRequest.RESULT_SUCCESS:
			reply.status = int(response[1])
			var bytes: PackedByteArray = response[3]
			if not bytes.is_empty():
				var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
				if parsed is Dictionary:
					reply.data = parsed
	http.queue_free()
	return reply
