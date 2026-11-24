extends SceneTree
## Loopback legacy-service compatibility using only a throwaway credential vault.

var session: Node
var checks: Array[String] = []
var pending := {}
var late := {}


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, label: String) -> bool:
	if not ok:
		push_error("Legacy identity check failed: " + label)
		quit(1)
		return false
	checks.append(label)
	return true


func mode(value: String) -> void:
	FileAccess.open(OS.get_environment("TX_STATE"), FileAccess.WRITE).store_string(value)
	DirAccess.remove_absolute(OS.get_environment("TX_ENTERED"))


func settled() -> void:
	while session._restore_running or session._store_issued != session._store_next or not session._requests.is_empty():
		await process_frame


func restore_original() -> bool:
	mode("online")
	session._restore_pending = true
	await session._restore(session._login_serial)
	await settled()
	return check(session.get_identity().get("id") == "alice" and session._owned_session and not session._memory_only_login and not session._stored_digest.is_empty(), "normal saved device restoration retains its existing ownership and digest")


func login_later(key: String) -> void:
	pending = {"ok": await session.authenticate("", key, "temporary-project")}


func slow_request() -> void:
	late = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/slow")


func wait_entered() -> void:
	while not FileAccess.file_exists(OS.get_environment("TX_ENTERED")):
		await process_frame


func run() -> void:
	await process_frame
	var mounted: Node = EditorInterface.get_base_control().find_child("TianxuanSessionController", true, false)
	var source_loaded := OS.get_environment("TX_SOURCE_LOADED") == "1"
	var script: Script = load("res://session_controller.gd") if source_loaded else mounted.get_script()
	session = script.new()
	session.credential_transport = load("res://session_memory.gd") if source_loaded else mounted.credential_transport
	var helper: String = FileAccess.get_file_as_string("res://session_credentials.py") if source_loaded else mounted.helper_source
	session.test_helper_source = helper.replace("Godot.Tianxuan.Editor", OS.get_environment("TX_TEST_SERVICE"))
	# Keep only the helper's macOS Keychain lookup in the same OS account as the
	# runner; the editor remains in its private HOME and only this random service is queried.
	if OS.has_environment("TX_VAULT_HOME"):
		session.test_helper_source = session.test_helper_source.replace("import os\n", "import os\nos.environ['HOME'] = os.environ['TX_VAULT_HOME']\n")
	session.test_python = OS.get_environment("TX_PYTHON")
	root.add_child(session)
	await process_frame
	await settled()
	if session.get_identity().get("id") != "alice":
		var diagnostic: Dictionary = await session._store("load", session.origin)
		print(JSON.stringify({"fixture_status": session.status_text, "store_status": diagnostic.get("status"), "origin_matches": session.origin == OS.get_environment("TIANXUAN_API"), "valid_record": not session._read_record(diagnostic, session.origin).is_empty()}))
		check(false, "private editor initially restores only its throwaway saved device")
		return
	check(true, "private editor initially restores only its throwaway saved device")
	var key := OS.get_environment("TX_PERSONAL_KEY")
	for status in [404, 405]:
		mode("enrollment_%d" % status)
		var issued: int = session._store_issued
		if not check(await session.authenticate("", key, "temporary-project"), "definite unsupported endpoint %d permits verified temporary identity" % status):
			return
		if not check(session.get_identity().id == "bob" and session.get_identity().role == "viewer" and session._token == key and not session._owned_session and session._memory_only_login and session._stored_digest.is_empty(), "temporary key preserves the exact server identity and viewer permission without ownership"):
			return
		if not check(session.get_login_persistence() == "temporary_legacy", "legacy fallback is explicitly temporary even when another saved device binding exists"):
			return
		if not check(session.status_text.contains("仅本次登录有效") and not session.redact_credentials(key).contains(key), "temporary status is explicit and active personal key is redacted"):
			return
		await session.reset()
		await session.reset()
		if not check(session.get_identity().is_empty() and session._store_issued == issued, "temporary login and repeated logout never read write or delete a persistent login"):
			return
		if not await restore_original():
			return
	for failure in ["enrollment_401", "enrollment_403", "enrollment_500", "enrollment_503", "enrollment_disconnect", "enrollment_empty", "enrollment_echo", "enrollment_echo_spaced", "me_401", "me_403", "me_503", "me_disconnect", "me_missing_id", "me_missing_role", "me_unknown_role", "me_null_id"]:
		mode(failure)
		var issued: int = session._store_issued
		var original_digest: String = session._stored_digest
		var supplied := "  " + key + "  " if failure == "enrollment_echo_spaced" else key
		if not check(not await session.authenticate("", supplied, "temporary-project"), failure + " never silently downgrades authorization"):
			return
		if not check(session.get_identity().id == "alice" and session._stored_digest == original_digest and session._store_issued == issued, failure + " preserves current and persisted identity"):
			return
		if not check(session.status_text.contains("HTTP") or session.status_text.contains("连接失败"), failure + " reports only a safe status indicator"):
			return
	for delay in ["delay_enrollment", "delay_me"]:
		mode(delay)
		pending.clear()
		var issued: int = session._store_issued
		login_later(key)
		await wait_entered()
		await session.authenticate("", "", "temporary-project")
		while pending.is_empty():
			await process_frame
		if not check(not pending.ok and session.get_identity().id == "alice" and session._store_issued == issued, delay + " cannot activate a cancelled or superseded login"):
			return
	mode("delay_me")
	pending.clear()
	login_later(key)
	await wait_entered()
	var initial: String = session.origin
	session.set_origin(OS.get_environment("TX_OTHER_ORIGIN"))
	while pending.is_empty():
		await process_frame
	await settled()
	if not check(not pending.ok and session.get_identity().is_empty(), "late personal-key verification cannot cross a changed service origin"):
		return
	session.set_origin(initial)
	await process_frame
	await settled()
	if not await restore_original():
		return
	mode("enrollment_404")
	slow_request()
	await wait_entered()
	if not check(await session.authenticate("", key, "temporary-project"), "temporary identity can replace current display while preserving the saved device"):
		return
	while late.is_empty():
		await process_frame
	if not check(late.get("stale", false) and session.get_identity().id == "bob", "late old 401 cannot reset the new temporary identity"):
		return
	await session.reset()
	if not await restore_original():
		return
	mode("replace_persisted")
	var issued: int = session._store_issued
	if not check(await session.authenticate("", key, "temporary-project"), "independent persisted-login replacement does not block a verified memory-only login"):
		return
	await session.reset()
	await session.reset()
	if not check(session._store_issued == issued, "temporary login never reads or modifies the concurrently replaced vault record"):
		return
	await settled()
	FileAccess.open(OS.get_environment("TX_REPORT"), FileAccess.WRITE).store_string(JSON.stringify({"passed": true, "checks": checks}, "  "))
	quit(0)
