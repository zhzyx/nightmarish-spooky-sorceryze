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
# Retain this marker after sign-out so repeated logout cannot delete a different
# process's saved authorization while this editor only used a temporary key.
var _memory_only_login := false
var _identity := {}
var _requests: Array[HTTPRequest] = []
var credential_transport: Script
var helper_source := ""
var credential_python: Callable
# Headless editors only access a helper explicitly injected by their isolated test.
var test_helper_source := ""
var test_python := ""
var _process := {}
var _store_issued := 0
var _store_next := 0
var _login_serial := 0
var _logout_serial := -1
var _origin_serial := 0
var _stored_digest := ""
var _restore_pending := false
var _restore_running := false


func _automated_launch() -> bool:
	if DisplayServer.get_name() == "headless":
		return true
	for argument in OS.get_cmdline_args():
		if argument in ["-s", "--script", "--import", "--export-release", "--export-debug", "--export-pack", "--export-patch"]:
			return true
	return false


func _ready() -> void:
	set_translation_domain(&"tianxuan-native")
	# An automated editor uses its launcher's grant. A desktop login belongs
	# to the person who chose it, including when the launcher exports a token.
	if _automated_launch() and test_helper_source.is_empty():
		_login_from_launcher.call_deferred(_login_serial)
	else:
		_restore_pending = true
		_restore.call_deferred(_login_serial)


func _login_from_launcher(serial: int) -> void:
	var supplied := OS.get_environment("TIANXUAN_TOKEN")
	if serial == _login_serial and not supplied.is_empty():
		var project := OS.get_environment("TIANXUAN_PROJECT").strip_edges()
		await authenticate("", supplied, "workspace" if project.is_empty() else project)


func _exit_tree() -> void:
	if not _process.is_empty():
		OS.kill(_process.pid)
		_process.stdio.close()
		_process.stderr.close()
		_process.clear()


func _store(action: String, target: String, secret := "", expected_digest := "") -> Dictionary:
	var automated := _automated_launch()
	var source := test_helper_source if automated else helper_source
	if not credential_transport or source.is_empty():
		return {"status": "disabled"}
	var python := test_python if automated else ""
	if not automated and credential_python.is_valid():
		python = str(credential_python.call())
	if python.is_empty():
		return {"status": "unavailable"}
	var ticket := _store_issued
	_store_issued += 1
	while ticket != _store_next:
		await get_tree().process_frame
	var request := {"service": "tianxuan-editor", "action": action, "account": target.sha256_text()}
	if action == "save":
		request.secret = secret
	if not expected_digest.is_empty():
		request.expected = expected_digest
	var result: Dictionary = await credential_transport.exchange(self, _process, python, source, request)
	_store_next += 1
	return result


func _read_record(reply: Dictionary, target: String) -> Dictionary:
	var parser := JSON.new()
	if reply.get("status") != "loaded" or parser.parse(str(reply.get("secret", ""))) != OK or not parser.data is Dictionary:
		return {}
	var record: Dictionary = parser.data
	if record.get("version") != 1 or record.get("origin") != target or not valid_project(str(record.get("project", ""))):
		return {}
	if not record.get("token") is String or not _valid_token(record.token) or not record.get("owned") is bool or str(record.get("user_id", "")).is_empty():
		return {}
	return record


static func _valid_token(value: String) -> bool:
	return not value.is_empty() and not _matches(value, "[[:cntrl:]]")


func _restore(serial: int) -> void:
	if serial != _login_serial or not _restore_pending or _restore_running or not valid_origin(origin):
		return
	_restore_running = true
	status_changed.emit()
	var target := origin
	var reply := await _store("load", target)
	if serial != _login_serial:
		return
	var record := _read_record(reply, target)
	if record.is_empty():
		_restore_running = false
		_restore_pending = reply.get("status") == "unavailable"
		if _restore_pending:
			_set_status("无法访问系统凭据库，请检查后重新连接服务。")
		else:
			status_changed.emit()
		return
	_stored_digest = str(reply.secret).sha256_text()
	var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", record.token, {}, 12.0, "", target)
	if serial != _login_serial:
		return
	_restore_running = false
	if me.status in [401, 403] or (me.status == 200 and str(me.data.get("id", "")) != str(record.user_id)):
		reset("凭据失效，请重新认证")
		return
	if me.status != 200 or str(me.data.get("role", "")).is_empty():
		_set_status("暂时无法核实保存的身份，重新连接服务后将重试")
		return
	if not record.owned:
		# Older editors saved the shared key itself. Upgrade it using the exact
		# record read above so another process's newer login always wins.
		_restore_running = true
		var enrollment := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/device-session", record.token, {}, 12.0, "", target)
		var credential := str(enrollment.data.get("token", ""))
		var echoes_shared_key := credential.strip_edges() == str(record.token).strip_edges()
		if serial != _login_serial:
			if not echoes_shared_key:
				await _revoke(credential, target)
			return
		if enrollment.status != 200 or not _valid_token(credential) or echoes_shared_key:
			_restore_running = false
			_set_status("无法升级保存的设备身份，请重新认证或连接服务后重试")
			if not echoes_shared_key:
				await _revoke(credential, target)
			return
		var verified := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", credential, {}, 12.0, "", target)
		if serial != _login_serial or verified.status != 200 or str(verified.data.get("id", "")) != str(record.user_id) or str(verified.data.get("role", "")).is_empty():
			if serial == _login_serial:
				_restore_running = false
				_set_status("无法核实升级后的设备身份，请重新认证")
			await _revoke(credential, target)
			return
		var upgraded := record.duplicate(true)
		upgraded.token = credential
		upgraded.owned = true
		upgraded.binding_id = Crypto.new().generate_random_bytes(16).hex_encode()
		var serialized := JSON.stringify(upgraded)
		var saved := await _store("save", target, serialized, str(reply.secret).sha256_text())
		if serial != _login_serial:
			if saved.get("status") == "saved":
				# A concurrent logout must never resurrect the old shared identity.
				await _store("delete", target, "", serialized.sha256_text())
			await _revoke(credential, target)
			return
		_restore_running = false
		if saved.get("status") != "saved":
			_set_status("保存的身份已变化或凭据库不可用，请重新连接后重试")
			await _revoke(credential, target)
			return
		record = upgraded
		_stored_digest = serialized.sha256_text()
		me = verified
	_restore_pending = false
	_activate(me.data, record.project, record.token, record.owned, _stored_digest)


func _cancel_login() -> void:
	_login_serial += 1
	_restore_pending = false
	_restore_running = false


func _init() -> void:
	if origin.is_empty():
		origin = OS.get_environment("TIANXUAN_API").strip_edges().trim_suffix("/")
	if origin.is_empty():
		origin = "https://167-172-70-41.sslip.io"


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
		_origin_serial += 1
		_cancel_login()
		_memory_only_login = false
		_clear_active("服务已切换，请登录天璇")
		origin = target
		_set_online(false)
		origin_changed.emit()
		if is_inside_tree():
			_restore_pending = true
			_restore.call_deferred(_login_serial)
	return true


func get_identity() -> Dictionary:
	return _identity.duplicate(true)


func get_login_persistence() -> String:
	# Public presentation state only: never expose the credential or vault digest.
	if _identity.is_empty():
		return "restore_pending" if _restore_running else "signed_out"
	if _memory_only_login:
		return "temporary_legacy"
	if _owned_session and not _stored_digest.is_empty():
		return "saved_device"
	return "temporary_session"


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
	_cancel_login()
	_logout_serial = _login_serial
	var target := origin
	var digest := _stored_digest
	var token := _token
	var owned := _owned_session
	var memory_only := _memory_only_login
	var serial := _login_serial
	_clear_active(message)
	# The user can sign out during cold start, before /me establishes an actor.
	if token.is_empty() and valid_origin(target) and not memory_only:
		var prior := await _store("load", target)
		if serial != _login_serial:
			return
		if prior.get("status") == "loaded" and (digest.is_empty() or digest == str(prior.secret).sha256_text()):
			digest = str(prior.secret).sha256_text()
			var record := _read_record(prior, target)
			token = str(record.get("token", ""))
			owned = bool(record.get("owned", false))
		elif prior.get("status") == "unavailable":
			_set_status("已停止使用当前身份；系统凭据库清除失败，请再次退出")
	if not digest.is_empty():
		var deleted := await _store("delete", target, "", digest)
		if serial == _login_serial and deleted.get("status") not in ["deleted", "missing", "changed"]:
			_stored_digest = digest
			_set_status("已停止使用当前身份；系统凭据库清除失败，请再次退出")
	if owned:
		await _revoke(token, target)


func _clear_active(message: String) -> void:
	if not _identity.is_empty():
		identity_resetting.emit()
	generation += 1
	_token = ""
	_owned_session = false
	_stored_digest = ""
	_identity.clear()
	_set_status(message)
	identity_changed.emit()


func _revoke(credential: String, target: String) -> void:
	if _valid_token(credential):
		await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/logout", credential, {}, 12.0, "", target)


func authenticate(email: String, secret: String, project: String) -> bool:
	_cancel_login()
	var serial := _login_serial
	var target := origin
	if not valid_origin(target):
		_set_status("天璇服务需要 HTTPS 或本机回环地址")
		return false
	if not valid_project(project):
		_set_status("请输入有效的业务项目")
		return false
	if secret.is_empty() or (email.is_empty() and (not _valid_token(secret) or secret.strip_edges().is_empty())):
		_set_status("请输入有效凭据以重新认证")
		return false
	if email.is_empty():
		secret = secret.strip_edges()
	_set_status("正在验证天璇账号…")
	var credential := secret
	var owned := not email.is_empty()
	var memory_only := false
	if owned:
		var payload := {"email": email, "password": secret}
		var login := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/editor-session", "", payload, 12.0, "", target)
		if serial == _login_serial and login.status in [404, 405]:
			# Older deployments retain their original server-side session lifetime.
			login = await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/session", "", payload, 12.0, "", target)
		credential = str(login.data.get("token", ""))
		if serial != _login_serial:
			_revoke(credential, target)
			return false
		if login.status != 200 or not _valid_token(credential):
			_revoke(credential, target)
			_set_status("登录失败，请重新认证" if login.status in [401, 403] else "无法登录天璇，请检查服务后重试")
			return false
	else:
		# A shared personal key authorizes enrollment, each device uses its own session.
		var enrollment := await _exchange(HTTPClient.METHOD_POST, "/api/v1/auth/device-session", credential, {}, 12.0, "", target)
		credential = str(enrollment.data.get("token", ""))
		var echoes_shared_key := credential.strip_edges() == secret
		if serial != _login_serial:
			if enrollment.status not in [404, 405] and not echoes_shared_key:
				_revoke(credential, target)
			return false
		if enrollment.status in [404, 405]:
			# Only a definite absent endpoint permits the old /me contract. Never
			# persist, revoke, or infer ownership of the shared personal key.
			credential = secret
			memory_only = true
		elif enrollment.status != 200 or not _valid_token(credential) or echoes_shared_key:
			if not echoes_shared_key:
				_revoke(credential, target)
			var detail := tr("连接失败") if enrollment.status == 0 else "HTTP %d" % enrollment.status
			if enrollment.status in [401, 403]:
				_set_status(tr("设备登录被拒绝，请检查个人密钥与权限（%s）") % detail)
			elif enrollment.status == 200:
				_set_status(tr("设备登录未返回独立设备凭据，个人密钥未保存（%s）") % detail)
			else:
				_set_status(tr("设备登录服务暂时不可用，请检查网络或稍后重试（%s）") % detail)
			return false
		else:
			owned = true
	var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", credential, {}, 12.0, "", target)
	var invalid_legacy_identity: bool = memory_only and (not me.data.get("id") is String or str(me.data.get("id", "")).strip_edges().is_empty() or me.data.get("role") not in ["admin", "editor", "viewer"])
	if serial != _login_serial or me.status != 200 or str(me.data.get("id", "")).is_empty() or str(me.data.get("role", "")).is_empty() or invalid_legacy_identity:
		if owned:
			_revoke(credential, target)
		if serial == _login_serial:
			if memory_only:
				var detail := tr("连接失败") if me.status == 0 else "HTTP %d" % me.status
				_set_status(tr("旧服务身份核实失败，请检查个人密钥、权限或服务状态（%s）") % detail)
			else:
				_set_status("凭据失效，请重新认证" if me.status in [401, 403] else "无法核实天璇身份，请重试")
		return false
	if memory_only:
		# This path intentionally performs no vault read, replacement, cleanup,
		# or revocation of an existing device grant belonging to another process.
		_activate(me.data, project, credential, false, "", true)
		_set_status(status_text + tr(" · 当前服务不支持设备登录，仅本次登录有效；已保存登录保持不变"))
		return true
	var prior := await _store("load", target)
	if serial != _login_serial:
		if owned:
			_revoke(credential, target)
		return false
	var previous := _read_record(prior, target)
	var retain := false
	# Shared keys from older editors must become independent device grants.
	# Only an owned device authorization can survive same-account confirmation.
	if previous.get("owned") == true and previous.get("user_id") == me.data.id:
		var saved_me := me
		if previous.token != credential:
			saved_me = await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", previous.token, {}, 12.0, "", target)
		var verified: bool = saved_me.status == 200 and not str(saved_me.data.get("id", "")).is_empty() and not str(saved_me.data.get("role", "")).is_empty()
		if serial != _login_serial or (not verified and saved_me.status not in [401, 403]):
			if owned and credential != previous.token:
				await _revoke(credential, target)
			if serial == _login_serial:
				_set_status("暂时无法核实保存的身份，请重新连接后重试")
			return false
		retain = verified and saved_me.data.id == me.data.id and saved_me.data.get("tenant_id") == me.data.get("tenant_id")
		if retain:
			me = saved_me
	var selected := str(previous.token) if retain else credential
	var selected_owned := bool(previous.owned) if retain else owned
	if retain and owned and credential != selected:
		await _revoke(credential, target)
		if serial != _login_serial:
			return false
	var record: String
	if retain:
		record = str(prior.secret)
		if previous.project != project:
			previous.project = project
			record = JSON.stringify(previous)
	else:
		record = JSON.stringify({"version": 1, "origin": target, "project": project, "user_id": str(me.data.id), "owned": owned, "token": credential, "binding_id": Crypto.new().generate_random_bytes(16).hex_encode()})
	var expected := str(prior.secret).sha256_text() if prior.get("status") == "loaded" else "missing"
	var saved := await _store("save", target, record, expected)
	var digest := record.sha256_text() if saved.get("status") == "saved" else ""
	if serial != _login_serial:
		# Logout may already have captured the digest from before our project update.
		# Only delete the exact bytes this save wrote, and leave a later login intact.
		if not digest.is_empty() and (not retain or (_logout_serial == _login_serial and digest != expected)):
			await _store("delete", target, "", digest)
		if owned and not retain:
			_revoke(credential, target)
		return false
	if digest.is_empty() and (saved.get("status") == "changed" or not previous.is_empty() or not _stored_digest.is_empty()):
		if owned and not retain:
			_revoke(credential, target)
		_set_status("无法替换已保存的身份，请检查系统凭据库后重试")
		return false
	if _owned_session and _token != selected:
		_revoke(_token, target)
	if previous.get("owned") == true and previous.token != selected and previous.token != _token:
		_revoke(previous.token, target)
	_activate(me.data, project, selected, selected_owned, digest)
	if digest.is_empty() and saved.get("status") != "disabled":
		_set_status(status_text + " · 系统凭据库不可用，仅本次登录有效")
	return true


func _activate(identity: Dictionary, project: String, credential: String, owned: bool, digest: String, memory_only := false) -> void:
	if not _identity.is_empty():
		identity_resetting.emit()
	generation += 1
	_identity = identity.duplicate(true)
	_identity.project = project
	_token = credential
	_owned_session = owned
	_memory_only_login = memory_only
	_stored_digest = digest
	_set_status("%s · %s · %s" % [_identity.get("name", ""), _identity.role, project])
	identity_changed.emit()
	authenticated.emit()
	if not _identity.is_empty() and _identity.role != "viewer":
		_recover_project(generation)


func auth_config() -> Dictionary:
	if not valid_origin(origin):
		return {"status": 0, "data": {}}
	var serial := _origin_serial
	var result := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/config", "", {})
	if serial == _origin_serial and result.status == 200 and _restore_pending:
		_restore.call_deferred(_login_serial)
	return result if serial == _origin_serial else {"status": 0, "data": {}}


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
	# Business asset ownership belongs to the verified project. Other native
	# endpoints deliberately retain their query-free protocol.
	if _matches(path, "^/api/v1/native/asset-context/[^/]+/[^/]+/.+$") or _matches(path, "^/api/v1/native/business-modules/[^/]+/assets(/[^/]+)?$") or _matches(path, "^/api/v1/native/assets/[^/]+/business-modules$"):
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
	elif reply.status == 403:
		# Business authorization may fail while this identity remains valid.
		var me := await _exchange(HTTPClient.METHOD_GET, "/api/v1/auth/me", _token, {})
		if attempt != generation:
			return {"status": 0, "data": {}, "stale": true}
		if me.status in [401, 403] or (me.status == 200 and str(me.data.get("id", "")) != str(_identity.id)):
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
	# Local workers stay on the machine even when the editor uses a proxy.
	if Engine.is_editor_hint() and not _matches(target.to_lower(), "^https?://(localhost\\.?|127(\\.[0-9]{1,3}){3}|\\[::1\\])(:[0-9]+)?$"):
		var settings := EditorInterface.get_editor_settings()
		var host := str(settings.get_setting("network/http_proxy/host")).strip_edges()
		var port := int(settings.get_setting("network/http_proxy/port"))
		if not host.is_empty() and port > 0 and port <= 65535:
			http.set_http_proxy(host, port)
			http.set_https_proxy(host, port)
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
