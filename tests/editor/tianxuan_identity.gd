extends SceneTree

var checks: Array[String] = []
var late := {}
var login_result := {}
var session: Node


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, label: String) -> bool:
	if not ok:
		push_error("Identity check failed: " + label)
		quit(1)
		return false
	checks.append(label)
	return true


func settled() -> void:
	while session._restore_running or session._store_issued != session._store_next or not session._requests.is_empty():
		await process_frame


func set_mode(mode: String) -> void:
	var file := FileAccess.open(OS.get_environment("TX_STATE"), FileAccess.WRITE)
	file.store_string(mode)
	file.close()


func slow_request() -> void:
	late = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues/slow")


func pending_login(token: String) -> void:
	login_result = {"passed": await session.authenticate("", token, "project-b")}


func update_project(token: String) -> void:
	late = {"accepted": await session.authenticate("", token, "new-project")}


func run() -> void:
	await process_frame
	var mounted := EditorInterface.get_base_control().find_child("TianxuanSessionController", true, false)
	if not check(mounted != null, "editor mounted its shared session"):
		return
	var source_loaded := OS.get_environment("TX_SOURCE_LOADED") == "1"
	var script: Script = load("res://session_controller.gd") if source_loaded else mounted.get_script()
	session = script.new()
	session.credential_transport = load("res://session_memory.gd") if source_loaded else mounted.credential_transport
	var helper: String = FileAccess.get_file_as_string("res://session_credentials.py") if source_loaded else mounted.helper_source
	var phase := OS.get_environment("TX_PHASE")
	# Use the real OS backend under a fresh service name, never the production vault.
	session.test_helper_source = helper.replace("Godot.Tianxuan.Editor", OS.get_environment("TX_TEST_SERVICE"))
	# Security.framework chooses its Keychain search scope from HOME. Only the
	# helper shares the runner's OS scope; the editor itself stays fully isolated.
	if OS.has_environment("TX_VAULT_HOME"):
		session.test_helper_source = session.test_helper_source.replace("import os\n", "import os\nos.environ['HOME'] = os.environ['TX_VAULT_HOME']\n")
	if phase == "migrate_logout_during_save":
		session.test_helper_source = session.test_helper_source.replace("response = dispatch(request)", "response = dispatch(request)\n            if request.get('action') == 'save' and response.get('status') == 'saved':\n                import os,time\n                open(os.environ['TX_SAVED'],'w').close()\n                time.sleep(0.5)")
	if not check(session.test_helper_source != helper and session.credential_transport != null, "isolated native helper embedded"):
		return
	session.test_python = OS.get_environment("TX_PYTHON")
	var persistence_states: Array[String] = []
	session.status_changed.connect(func(): persistence_states.append(session.get_login_persistence()))
	root.add_child(session)
	if phase == "authenticate_migrate":
		session._cancel_login()
	if phase == "early_logout":
		await session.reset()
	if phase in ["migrate_cancel", "migrate_echo_cancel"]:
		while not FileAccess.file_exists(OS.get_environment("TX_ENROLLED")):
			await process_frame
		session._cancel_login()
	if phase == "migrate_logout_during_save":
		while not FileAccess.file_exists(OS.get_environment("TX_SAVED")):
			await process_frame
		await session.reset()
	await process_frame
	await settled()
	var token := OS.get_environment("TX_FIXTURE_KEY")
	var password := OS.get_environment("TX_FIXTURE_PASSWORD")
	if phase == "login":
		if not check(persistence_states.has("restore_pending") and persistence_states.back() == "signed_out", "empty vault startup notifies views when the persistence check finishes"):
			return
		var memory := root.find_child("AIConnectionMemory", true, false)
		if not check(memory != null, "existing AI credential consumer is mounted"):
			return
		memory.test_helper_source = "import json,sys\nrequest=json.loads(sys.stdin.buffer.readline())\nprint(json.dumps({'status':'loaded','secret':request['secret']}))"
		var returned: Dictionary = await memory._request({"secret": token})
		if not check(returned.get("secret") == token, "existing AI connection memory uses the shared bounded pipe"):
			return
	if phase in ["login", "legacy"]:
		if not check(session.get_identity().is_empty(), "fresh editor is signed out"):
			return
		if not check(await session.authenticate("user@example.test", password, "project-a"), "ordinary password login"):
			return
		if not check(session.get_identity().id == "alice" and not session._stored_digest.is_empty(), "verified device grant saved"):
			return
		if not check(session.get_login_persistence() == "saved_device", "login presentation reports the device grant actually saved by the OS vault"):
			return
	elif phase == "authenticate_migrate":
		if not check(session.get_identity().is_empty(), "explicit login begins before legacy restore"):
			return
		if not check(await session.authenticate("", token, "project-b"), "explicit login upgrades same-account legacy shared record"):
			return
		var saved: Dictionary = await session._store("load", session.origin)
		var record: Dictionary = JSON.parse_string(saved.get("secret", "{}"))
		if not check(record.get("owned") == true and record.get("token") == session._token and session._token != token, "same-account retention cannot preserve the shared root key"):
			return
		await session.reset()
	elif phase == "same_account":
		var original: String = session._stored_digest
		var personal := OS.get_environment("TX_SAME_ACCOUNT_KEY")
		if not check(await session.authenticate("", personal, "project-a") and session._stored_digest == original, "same account and project retain exact original binding"):
			return
		set_mode("saved_offline")
		if not check(not await session.authenticate("", personal, "project-b") and session._stored_digest == original, "saved grant verification outage preserves actor, project and original credential"):
			return
		set_mode("online")
		if not check(await session.authenticate("user@example.test", password, "project-a") and session._stored_digest == original, "same-account password confirmation retains prior device authorization"):
			return
		if not check(await session.authenticate("", personal, "project-b") and session.get_identity().project == "project-b", "same user can update project on the retained binding"):
			return
		var audited: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/measure")
		if not check(audited.data.get("actor") == "alice", "server audits original account after project change"):
			return
		var scoped_assets := [
			"/api/v1/native/asset-context/source/revision/models/pig.tres",
			"/api/v1/native/business-modules/module/assets",
			"/api/v1/native/business-modules/module/assets/object",
			"/api/v1/native/assets/object/business-modules",
		]
		for route: String in scoped_assets:
			var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route + "?limit=2")
			if not check(reply.status == 200 and reply.data.query == {"limit": ["2"], "project": ["project-b"]}, "native asset route preserves its query and carries the verified project: " + route):
				return
		for operation in [[HTTPClient.METHOD_POST, scoped_assets[1]], [HTTPClient.METHOD_DELETE, scoped_assets[2]]]:
			var reply: Dictionary = await session.api_request(operation[0], operation[1])
			if not check(reply.status == 200 and reply.data.query == {"project": ["project-b"]}, "asset link writes use the same verified project scope: " + operation[1]):
				return
		for route: String in ["/api/v1/native/modules/source/branches", "/api/v1/native/workflow/status", "/api/v1/native/business-modules/module/assets-extra", "/api/v1/native/business-modules/module/assets/object/extra", "/api/v1/native/assets/object/business-modules/extra", "/api/v1/native/asset-context/source/revision"]:
			var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, route)
			if not check(reply.status == 200 and reply.data.query.is_empty(), "unrelated or incomplete native routes retain the query-free contract: " + route):
				return
		for action in ["pause", "resume", "cancel", "recover-project"]:
			var reply: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/workflow/" + action)
			if not check(reply.status == 200 and reply.data.query == {"project": ["project-b"]}, "existing workflow project scope remains intact: " + action):
				return
		for query in ["project=another", "%70roject=another", "limit=2&project=another"]:
			var reply: Dictionary = await session.api_request(HTTPClient.METHOD_GET, scoped_assets[0] + "?" + query)
			if not check(reply.status == 0, "callers cannot override asset ownership project: " + query):
				return
	elif phase == "rebind":
		var short_key := OS.get_environment("TX_SAME_ACCOUNT_KEY")
		if not check(await session.authenticate("", short_key, "project-a"), "initial finite personal key enrolls an independent device"):
			return
		set_mode("prior_revoked")
		if not check(await session.authenticate("", OS.get_environment("TX_SECOND_KEY"), "project-a"), "confirmed revoked saved device is replaced by a newly verified device"):
			return
	elif phase == "concurrent":
		set_mode("replace_during_check")
		if not check(not await session.authenticate("", OS.get_environment("TX_SAME_ACCOUNT_KEY"), "project-b"), "concurrent account switch wins over stale saved binding"):
			return
	elif phase == "logout_during_update":
		if not check(session.get_identity().get("id") == "bob", "competing editor's saved login restored"):
			return
		# Delay the test-only helper so the explicit logout lands while the CAS is pending.
		session.test_helper_source = "import time\ntime.sleep(0.3)\n" + session.test_helper_source
		var pending_save: int = session._store_issued + 2
		update_project(token)
		var until := Time.get_ticks_msec() + 8000
		while session._store_issued < pending_save and Time.get_ticks_msec() < until:
			await process_frame
		if not check(session._store_issued == pending_save and session._store_next < pending_save, "project save is in flight before explicit logout"):
			return
		await session.reset()
		while late.is_empty():
			await process_frame
		await settled()
		if not check(not late.accepted and session.get_identity().is_empty(), "explicit logout supersedes unfinished project change"):
			return
	elif phase == "restart":
		if not check(session.get_identity().id == "alice" and session.get_identity().project == "project-b", "new process restored verified actor and updated project"):
			return
		if not check(session.get_login_persistence() == "saved_device", "restarted editor reports verified saved device identity"):
			return
		var denied: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/denied")
		if not check(denied.status == 403 and session.get_identity().id == "alice", "business permission refusal keeps login"):
			return
		if not check(not await session.authenticate("", "invalid", "project-b") and session.get_identity().id == "alice", "failed account switch retains actor"):
			return
		if not check(session.get_login_persistence() == "saved_device", "failed authentication preserves the existing persisted-login presentation"):
			return
		var original: Dictionary = await session._store("load", session.origin)
		for failure in ["invalid_me", "failed_enrollment"]:
			set_mode(failure)
			if not check(not await session.authenticate("", token, "project-b"), failure + " rejects new device session"):
				return
			var retained: Dictionary = await session._store("load", session.origin)
			if not check(session.get_identity().id == "alice" and retained == original, failure + " retains prior actor and stored grant"):
				return
		set_mode("cancel_enrollment")
		pending_login(token)
		while not FileAccess.file_exists(OS.get_environment("TX_ENROLLED")):
			await process_frame
		if not check(not await session.authenticate("", "", "project-b"), "new login cancels pending enrollment"):
			return
		while login_result.is_empty():
			await process_frame
		var retained: Dictionary = await session._store("load", session.origin)
		if not check(not login_result.passed and session.get_identity().id == "alice" and retained == original, "late enrollment cannot replace actor or persisted grant"):
			return
		set_mode("online")
		var initial: String = session.origin
		session.set_origin(OS.get_environment("TX_OTHER_ORIGIN"))
		await process_frame
		await settled()
		if not check(session.get_identity().is_empty(), "different origin cannot restore first grant"):
			return
		session.set_origin(initial)
		await process_frame
		await settled()
		if not check(session.get_identity().id == "alice", "returning to bound origin restores actor"):
			return
		slow_request()
		if not check(await session.authenticate("", token, "project-b"), "verified personal key switched account"):
			return
		if not check(session._owned_session and session._token != token and not session._stored_digest.is_empty(), "personal key persists only its independently revocable device session"):
			return
		while late.is_empty():
			await process_frame
		if not check(late.get("stale") == true and session.get_identity().id == "bob", "late old response cannot reset new actor"):
			return
		var result: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/measure")
		if not check(result.data.get("actor") == "bob", "server recorded current account on operation"):
			return
	elif phase == "precedence":
		if not check(session.get_identity().get("id") == "bob", "desktop with inherited launcher credential restores the account selected by the user"):
			return
		if source_loaded:
			mounted = script.new()
			root.add_child(mounted)
		var timeout := Time.get_ticks_msec() + 5000
		while mounted.get_identity().is_empty() and Time.get_ticks_msec() < timeout:
			await process_frame
		if not check(mounted.get_identity().get("id") == "alice" and mounted._stored_digest.is_empty(), "headless launch uses its own grant without replacing desktop identity"):
			return
	elif phase == "offline":
		if not check(session.get_identity().is_empty() and session._restore_pending, "unavailable server retains pending grant without asserting identity"):
			return
		set_mode("online")
		await session.auth_config()
		await process_frame
		await settled()
		if not check(session.get_identity().id == "bob", "reconnect restored without credential entry"):
			return
		set_mode("revoked")
		var blocked: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/issues/denied")
		await settled()
		if not check(blocked.status == 403 and session.get_identity().is_empty(), "authenticated endpoint confirms revoked identity"):
			return
	elif phase == "logout":
		if not check(session.get_identity().is_empty(), "revoked grant absent after restart"):
			return
		if not check(await session.authenticate("", token, "project-b"), "user supplied reauthorized personal key"):
			return
		await session.reset()
		if not check(session.get_identity().is_empty(), "logout forgets and revokes only the device session"):
			return
	elif phase == "early_logout":
		if not check(session.get_identity().is_empty() and not session._restore_pending, "cold-start logout cancels pending identity restore"):
			return
	elif phase in ["migrate", "migration_restart"]:
		if not check(session.get_identity().get("id") == "bob" and session.get_identity().project == "legacy-project", "legacy personal-key identity restores with its original actor and project"):
			return
		if not check(session._owned_session and session._token != token and not session._stored_digest.is_empty(), "legacy shared key is upgraded to a persisted owned device grant"):
			return
	elif phase in ["migrate_failure", "migrate_cancel", "migrate_cas", "migrate_denied", "migrate_echo", "migrate_echo_cancel"]:
		if not check(session.get_identity().is_empty(), "failed or superseded legacy migration never activates shared credentials"):
			return
	elif phase == "migrate_logout_during_save":
		if not check(session.get_identity().is_empty(), "logout during committed migration cannot restore either identity"):
			return
	elif phase == "migration_logout":
		if not check(session.get_identity().get("id") == "bob", "upgraded device survives process restart"):
			return
		await session.reset()
		if not check(session.get_identity().is_empty(), "upgraded device logs out independently of shared key"):
			return
	await settled()
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
