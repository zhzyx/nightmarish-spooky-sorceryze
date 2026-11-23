@tool
extends Node
## Shared transport and identity, owned by the editor rather than a dock or page.
## Every coroutine captures its origin and identity generation before yielding.

signal identity_resetting
signal identity_changed
signal authenticated
signal status_changed
signal connection_changed
signal origin_changed

var origin := ""
var status_text := "尚未登录天璇"
var generation := 0
var online := false
var _token := ""
var _owned_session := false
var _identity := {}
var _requests: Array[HTTPRequest] = []


func _init() -> void:
	if origin.is_empty():
		origin = OS.get_environment("TIANXUAN_API").strip_edges().trim_suffix("/")
	if origin.is_empty():
		origin = "http://127.0.0.1:8000"


static func _matches(value: String, pattern: String) -> bool:
	var expression := RegEx.new()
	return expression.compile(pattern) == OK and expression.search(value) != null


static func valid_origin(value: String) -> bool:
	return _matches(value, "^https://([A-Za-z0-9.-]+|\\[[0-9A-Fa-f:]+\\])(:[0-9]{1,5})?$") or _matches(value, "^http://(127\\.0\\.0\\.1|localhost|\\[::1\\])(:[0-9]{1,5})?$")


static func valid_project(value: String) -> bool:
	return _matches(value, "^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}(/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})?$")


func set_origin(value: String) -> bool:
	var target := value.strip_edges().trim_suffix("/")
	if not valid_origin(target):
		_set_status("请输入 HTTPS 服务地址或本机回环地址")
		return false
	if target != origin:
		reset("服务已切换，请登录天璇")
		origin = target
		_set_online(false)
		origin_changed.emit()
	return true


func get_identity() -> Dictionary:
	return _identity.duplicate(true)


func scope_key() -> String:
	if _identity.is_empty():
		return ""
	return JSON.stringify([origin, _identity.id, _identity.project]).sha256_text()


func redact_credentials(text: String) -> String:
	return text if _token.is_empty() else text.replace(_token, "[REDACTED]")


func _set_status(message: String) -> void:
	status_text = message
	status_changed.emit()


func _set_online(value: bool) -> void:
	if online != value:
		online = value
		connection_changed.emit()


func reset(message := "已退出天璇") -> void:
	if not _identity.is_empty():
		identity_resetting.emit()
	var previous_origin := origin
	var previous_token := _token
	var revoke := _owned_session
	generation += 1
	_token = ""
	_owned_session = false
	_identity.clear()
	_set_status(message)
	identity_changed.emit()
	if revoke:
		# The captured old origin prevents logout credentials crossing deployments.
		_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", previous_token, {}, 12.0, "", previous_origin)


func authenticate(email: String, secret: String, project: String) -> bool:
	reset("正在验证天璇账号…")
	var attempt := generation
	var target := origin
	if not valid_origin(target):
		_set_status("天璇服务需要 HTTPS 或本机回环地址")
		return false
	if not valid_project(project):
		_set_status("请输入有效的业务项目")
		return false
	if secret.is_empty() or (email.is_empty() and ("\r" in secret or "\n" in secret)):
		_set_status("请输入有效凭据以重新认证")
		return false
	var credential := secret
	if not email.is_empty():
		var login := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/session", "", {"email": email, "password": secret}, 12.0, "", target)
		credential = str(login.data.get("token", ""))
		if attempt != generation:
			if not credential.is_empty():
				_exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", credential, {}, 12.0, "", target)
			return false
		if login.status != 200 or credential.is_empty():
			_set_status("登录失败，请重新认证" if login.status in [401, 403] else "无法登录天璇，请检查服务后重试")
			return false
	_token = credential
	_owned_session = not email.is_empty()
	var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", credential, {}, 12.0, "", target)
	if attempt != generation:
		return false
	if me.status != 200 or str(me.data.get("id", "")).is_empty() or str(me.data.get("role", "")).is_empty():
		reset("凭据失效，请重新认证" if me.status in [401, 403] else "无法核实天璇身份，请重试")
		return false
	_identity = me.data.duplicate(true)
	_identity.project = project
	_set_status("%s · %s · %s" % [_identity.get("name", ""), _identity.role, project])
	identity_changed.emit()
	authenticated.emit()
	if attempt == generation and not _identity.is_empty() and _identity.role != "viewer":
		_recover_project(attempt)
	return attempt == generation and not _identity.is_empty()


func auth_config() -> Dictionary:
	if not valid_origin(origin):
		return {"status": 0, "data": {}}
	var attempt := generation
	var result := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/config", "", {})
	return result if attempt == generation else {"status": 0, "data": {}}


func register_account(workspace: String, email: String, password: String) -> Dictionary:
	if not valid_origin(origin):
		return {"status": 0, "data": {}}
	var attempt := generation
	var result := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/register", "", {"tenant_name": workspace, "email": email, "password": password})
	return result if attempt == generation else {"status": 0, "data": {}}


func _recover_project(attempt: int) -> void:
	await api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/recover-occupancy", {"project": _identity.project})
	if attempt != generation:
		return
	var response := await api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/recover-project", {}, 86400.0)
	if attempt == generation and response.status != 404 and (response.status != 200 or int(response.data.get("errors", 0)) > 0):
		_set_status(status_text + tr(" · 部分任务恢复回执待核对"))


func api_request(method: int, route: String, payload: Dictionary = {}, timeout_seconds := 12.0, download_path := "", download_limit := -1) -> Dictionary:
	if _identity.is_empty():
		return {"status": 401, "data": {}}
	if not route.begins_with("/api/v1/") or "#" in route or "\\" in route or "\n" in route or "\r" in route:
		return {"status": 0, "data": {}}
	for parameter in route.get_slice("?", 1).split("&", false):
		if parameter.get_slice("=", 0).uri_decode() == "project":
			return {"status": 0, "data": {}}
	var scoped_route := route
	var path := route.get_slice("?", 0)
	var project_scoped := not path.begins_with("/api/v1/native/") and not path.begins_with("/api/v1/workspace/runs") and not path.begins_with("/api/v1/workspace/modules")
	if path in ["/api/v1/native/workflow/pause", "/api/v1/native/workflow/resume", "/api/v1/native/workflow/cancel", "/api/v1/native/workflow/recover-project"]:
		project_scoped = true
	if path.begins_with("/api/v1/issues/") and path.ends_with("/work/godot-inputs"):
		project_scoped = false
	if project_scoped:
		scoped_route += ("&" if "?" in route else "?") + "project=" + str(_identity.project).uri_encode()
	var attempt := generation
	var reply := await _exchange(method, scoped_route, _token, payload, timeout_seconds, download_path, "", download_limit)
	if attempt != generation:
		return {"status": 0, "data": {}, "stale": true}
	if reply.status == 401:
		reset("凭据失效，请重新认证")
	return reply


func join_room(route: String) -> WebSocketPeer:
	if _identity.is_empty() or not route.begins_with("/api/v1/ws/") or "?" in route or "#" in route or "\\" in route or "\n" in route or "\r" in route:
		return null
	var peer := WebSocketPeer.new()
	peer.inbound_buffer_size = 8 * 1024 * 1024
	peer.handshake_headers = PackedStringArray(["Authorization: Bearer " + _token])
	var url := "ws" + origin.trim_prefix("http") + route + "?project=" + str(_identity.project).uri_encode()
	return peer if peer.connect_to_url(url) == OK else null


func join_document_room(id: String) -> WebSocketPeer:
	return null if id.is_empty() else join_room("/api/v1/ws/docs/" + id.uri_encode())


static func wire_value(value: Variant) -> Variant:
	# Godot's JSON parser returns floats for integer fields. Match the Web client's
	# JSON number encoding when replaying persisted versions, counts and indexes.
	if value is float and is_finite(value) and absf(value) <= 9007199254740991.0 and value == floor(value):
		return int(value)
	if value is Dictionary:
		var result := {}
		for key in value:
			result[key] = wire_value(value[key])
		return result
	if value is Array:
		return value.map(wire_value)
	return value


func _exchange(method: int, route: String, credential: String, payload: Dictionary, timeout_seconds := 12.0, download_path := "", target_origin := "", download_limit := -1) -> Dictionary:
	var target := origin if target_origin.is_empty() else target_origin
	var attempt := generation
	var http := HTTPRequest.new()
	http.max_redirects = 0
	http.timeout = timeout_seconds
	http.body_size_limit = 8 * 1024 * 1024 if download_path.is_empty() else download_limit
	http.download_file = download_path
	_requests.append(http)
	# This node stays in the editor tree when either View is moved, closed or rebuilt.
	add_child(http)
	var headers := PackedStringArray(["Accept: application/json" if download_path.is_empty() else "Accept: application/octet-stream"])
	if not credential.is_empty():
		headers.append("Authorization: Bearer " + credential)
	if route.get_slice("?", 0) == "/api/v1/native/workflow/recover-project" and _matches(target, "^https?://(127\\.0\\.0\\.1|localhost|\\[::1\\])(:[0-9]{1,5})?$"):
		headers.append("X-Native-Worker-Lifetime: editor-connection")
	var body := ""
	if method not in [HTTPClient.METHOD_GET, HTTPClient.METHOD_HEAD]:
		headers.append("Content-Type: application/json")
		body = JSON.stringify(wire_value(payload))
	var reply := {"status": 0, "data": {}}
	if http.request(target + route, headers, method, body) == OK:
		var response: Array = await http.request_completed
		if response[0] in [HTTPRequest.RESULT_DOWNLOAD_FILE_CANT_OPEN, HTTPRequest.RESULT_DOWNLOAD_FILE_WRITE_ERROR]:
			reply.write_failed = true
		if response[0] == HTTPRequest.RESULT_SUCCESS:
			reply.status = int(response[1])
			var bytes: PackedByteArray = response[3]
			if not bytes.is_empty() and download_path.is_empty():
				var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
				if parsed is Dictionary:
					reply.data = parsed
	_requests.erase(http)
	http.queue_free()
	if attempt == generation and target == origin and route != "/api/v1/auth/logout":
		_set_online(reply.status > 0)
	return reply
