extends SceneTree
## Query the compiled host while real HTTP requests are pending, cancelled and completed.

const ModelFixture = preload("res://tianxuan_local_model_fixture.gd")
const IDLE := {"active": false, "phase": "idle"}
const WAITING := {"active": true, "phase": "waiting"}
var results := {}
var completions := {}
var checks: Array[String] = []


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, description: String) -> bool:
	if not ok:
		push_error(description)
		quit(1)
		return false
	checks.append(description)
	return true


func receive(id: String, result: Dictionary) -> void:
	results[id] = result.duplicate(true)
	completions[id] = int(completions.get(id, 0)) + 1


func wait_until(predicate: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + 10000
	while Time.get_ticks_msec() < deadline:
		if predicate.call():
			return true
		await create_timer(0.02).timeout
	return false


func start(host: Node, scope: String, id: String) -> bool:
	var accepted: Dictionary = host.start(scope, id, [{"role": "user", "content": id}])
	return check(accepted.get("ok", false), "start isolated request " + id)


func run() -> void:
	await process_frame
	await process_frame
	var before: Dictionary = await ModelFixture.configure(self)
	if not check(not before.is_empty(), "configure only the private editor's existing model controls"):
		return
	var controller := EditorInterface.get_base_control().get_node("TianxuanWorkspaceController")
	var host: Node = controller.get_meta("model_host")
	if not check(host.has_method("progress"), "compiled model host exposes the request-scoped progress API"):
		return
	host.finished.connect(receive)
	if not check(host.progress("unknown") == IDLE and host.progress("") == IDLE, "unknown and empty IDs disclose only inactive status"):
		return
	if not start(host, "scope-a-private", "progress-cancel") or not start(host, "scope-b-private", "progress-complete"):
		return
	if not check(host.progress("progress-cancel") == WAITING and host.progress("progress-complete") == WAITING, "each live request exposes only truthful waiting status"):
		return
	var detached: Dictionary = host.progress("progress-complete")
	detached.phase = "forged"
	detached.active = false
	if not check(host.progress("progress-complete") == WAITING and host.progress("wrong-scope-id") == IDLE, "query results are detached and do not fall back to another active request"):
		return
	if not check(await wait_until(func(): return FileAccess.file_exists(OS.get_environment("TX_PROGRESS_MARKERS").path_join("progress-cancel"))), "cancelled request actually reached its isolated provider"):
		return
	if not check(host.cancel("progress-cancel") and host.progress("progress-cancel") == IDLE and host.progress("progress-complete") == WAITING, "canceling one request immediately clears only its status"):
		return
	if not check(await wait_until(func(): return results.has("progress-complete")), "second request completes normally"):
		return
	if not check(results["progress-complete"].get("ok", false) and host.progress("progress-complete") == IDLE, "successful terminal result removes progress without leaking the answer"):
		return
	await create_timer(0.25).timeout
	if not check(completions.get("progress-cancel") == 1 and not results["progress-cancel"].get("ok", true) and host.progress("progress-cancel") == IDLE, "late cancelled provider output cannot revive or duplicate progress"):
		return
	if not start(host, "scope-c-private", "progress-fail"):
		return
	if not check(host.progress("progress-fail") == WAITING and await wait_until(func(): return results.has("progress-fail")), "failed provider request remains visible while actually pending"):
		return
	if not check(not results["progress-fail"].get("ok", true) and host.progress("progress-fail") == IDLE, "failed terminal status exposes no provider diagnostics"):
		return
	if not check(ModelFixture.unchanged(before), "status polling does not alter the ordinary AIChat session, transcript or draft"):
		return
	FileAccess.open(OS.get_environment("TX_REPORT"), FileAccess.WRITE).store_string(JSON.stringify({"ok": true, "checks": checks}, "  "))
	quit(0)
