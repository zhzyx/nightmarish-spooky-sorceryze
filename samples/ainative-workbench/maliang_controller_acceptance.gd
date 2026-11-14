extends SceneTree

const Controller = preload("res://addons/ainative/workflow_controller.gd")
var failures = 0
var checks: Array = []
var state_dir = OS.get_environment("AINATIVE_UI_STATE")

class RuntimeFixture extends RefCounted:
	var requests: Array = []
	var events: Array = []
	var runs: Dictionary = {}
	func begin_run(request: Dictionary) -> Dictionary:
		requests.append(request.duplicate(true))
		var id = "public-" + str(requests.size())
		var value = {"run_id": id, "generation": requests.size(), "sequence": 1, "state": request.get("initial_state", "running"), "model": request.model.duplicate(true)}
		runs[id] = value
		return {"ok": true, "changed": true, "snapshot": value.duplicate(true)}
	func publish(event: Dictionary) -> Dictionary:
		events.append(event.duplicate(true))
		if event.get("kind") not in ["progress", "text_delta", "artifact_ready", "tool_requested", "completed", "failed", "cancelled"]:
			return {"ok":false, "code":"invalid_kind"}
		var value: Dictionary = runs[event.run_id]
		if value.state in ["cancelled", "failed", "succeeded"]: return {"ok": false, "changed": false, "code":"terminal"}
		if event.generation != value.generation or event.expected_sequence != value.sequence: return {"ok": false}
		value.sequence += 1
		value.state = event.state
		return {"ok": true, "changed": true, "snapshot": value.duplicate(true)}
	func cancel(id: String, generation: int, event_id: String) -> Dictionary:
		return publish({"run_id": id, "generation": generation, "event_id": event_id, "expected_sequence": runs[id].sequence, "kind":"cancelled", "state": "cancelled"})
	func snapshot(id: String) -> Dictionary:
		return {"ok": true, "snapshot": runs[id].duplicate(true)}

class TransportFixture extends Controller:
	var launches: Array = []
	var stopped = 0
	func launch(command: String, spec: Dictionary):
		launches.append({"command": command, "spec": spec.duplicate(true)})
	func shutdown():
		stopped += 1
		super.shutdown()

func check(ok: bool, label: String):
	checks.append({"ok": ok, "label": label})
	print(("PASS " if ok else "FAIL ") + label)
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func fixture() -> TransportFixture:
	var controller = TransportFixture.new()
	controller.runtime = RuntimeFixture.new()
	controller.configure({"state_dir": state_dir, "db": state_dir.path_join("fixture.sqlite"), "python": "fixture", "script": "fixture"})
	root.add_child(controller)
	controller.set_process(false)
	return controller

func run():
	DirAccess.make_dir_recursive_absolute(state_dir)
	var controller = fixture()
	var model = {"nodes": [{"id": "a", "type": "text_to_mesh", "provider": "api-modeling", "model": "model-a"}, {"id": "b", "type": "model_adjust", "provider": "api-sculpt", "model": "model-b", "image_model": "image-b"}], "edges": []}
	controller.start(model, "a")
	model.nodes[0].model = "edited"
	controller.configure({"state_dir": state_dir, "db": "changed", "python": "changed"})
	check(controller.creating and controller.auto_step and controller.launches[0].command == "create", "start is implemented by controller")
	check(controller.model_snapshot.nodes[0].model == "model-a" and controller.run_configuration.python == "fixture", "input and execution configuration freeze at start")
	check(controller.runtime.requests[0].model.nodes[0].model == "model-a" and controller.runtime.requests[0].model.nodes[1].model == "model-b", "independent modeling and sculpt selections reach public snapshot")
	check(controller.runtime.requests[0].model.nodes[1].image_model == "image-b", "auxiliary image selection remains independent")
	controller.cancel()
	controller._complete({"command": "create", "spec": {}}, {"run_id": "domain-original"})
	check(not controller.auto_step and not controller.creating and controller.launches[-1].command == "cancel", "cancel during create cancels returned domain run without auto step")
	controller._complete({"command": "cancel", "spec": {}}, {"state": "cancelled", "nodes": {}})
	controller._complete({"command": "step", "spec": {}}, {"state": "succeeded", "nodes": {}})
	check(controller.current.state == "cancelled" and controller.public_snapshot.state == "cancelled", "late success cannot replace cancellation in controller or runtime")
	var original_id = controller.run_id
	controller.restore()
	check(controller.launches[-1].command == "status" and controller.run_id == original_id, "rebinding queries existing run without create")
	controller._complete({"command": "status", "spec": {}}, {"state": "cancelled", "nodes": {}})
	check(controller.launches[-1].command == "status" and controller.current.state == "cancelled", "status after cancellation is read without repeated cancellation")
	controller.retry("a")
	check(controller.launches[-1].command == "retry" and controller.runtime.requests.size() == 2, "retry creates new public operation for same domain run")
	controller._complete({"command": "retry", "spec": {}}, {"state": "running", "nodes": {}})
	check(controller.auto_step, "retry resumes controller stepping")
	controller._complete({"command": "step", "spec": {}}, {"state": "reconcile", "nodes": {}})
	check(not controller.auto_step and controller.public_snapshot.state == "reconciling", "unknown submission stops automatic stepping")
	controller.resume()
	check(controller.launches[-1].command == "step", "explicit resume delegates lookup to domain executor")
	controller.attach_view()
	controller.attach_view()
	controller.detach_view()
	await process_frame
	check(controller.stopped == 0, "detaching one of two views does not stop shared work")
	controller.detach_view()
	controller.attach_view()
	await process_frame
	check(controller.stopped == 0, "same-frame UI replacement retains controller ownership")
	controller.detach_view()
	await process_frame
	check(controller.stopped == 1, "closing final view stops owned transport")
	var restored = fixture()
	restored.restore()
	check(restored.run_id == "domain-original" and restored.launches.size() == 1 and restored.launches[0].command == "status", "cold restoration only reads persisted domain identity")
	check(restored.runtime.requests[0].initial_state == "reconciling", "cold restoration declares reconciliation to runtime")
	check(restored.runtime.requests[0].model.nodes[0].model == "model-a", "cold restoration preserves frozen node model metadata")
	await view_lifecycle()
	await real_transport()
	controller.queue_free()
	restored.queue_free()
	await process_frame
	var report = FileAccess.open(state_dir.path_join("controller-report.json"), FileAccess.WRITE)
	report.store_string(JSON.stringify({"ok": failures == 0, "checks": checks, "evidence": "GDScript injection fixture plus real local demo Executor; not new native singleton integration"}, "  "))
	report.close()
	quit(0 if failures == 0 else 1)

func real_transport():
	var controller = Controller.new()
	controller.runtime = RuntimeFixture.new()
	controller.failed.connect(func(command, message, details, _section): print("TRANSPORT ", command, " ", message, " ", details))
	var local = state_dir.path_join("real")
	DirAccess.make_dir_recursive_absolute(local)
	controller.configure({"state_dir": local, "db": local.path_join("executor.sqlite"), "python": OS.get_environment("AINATIVE_PYTHON"), "script": OS.get_environment("AINATIVE_UI_TOOLS").path_join("editor_host.py"), "factory": "editor_demo:factory", "uses_service": false})
	root.add_child(controller)
	var model = {"format": 1, "nodes": [{"id": "copy", "type": "copy", "provider": "local-copy", "source": ProjectSettings.globalize_path("res://fixtures/sample.png"), "image_context": "", "text": "", "parameters": {"delay": 0.01, "fail": false}}], "edges": []}
	controller.start(model)
	var deadline = Time.get_ticks_msec() + 20000
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(controller.current.get("state") == "succeeded", "real subprocess request, PID polling and Executor complete without a View")
	check(controller.public_snapshot.get("state") == "succeeded", "real domain completion publishes public event through injected runtime")
	check(not controller.run_id.is_empty() and FileAccess.get_file_as_string(local.path_join("last_run.txt")) == controller.run_id, "real create persists recovery identity")
	var domain_id = controller.run_id
	controller.shutdown()
	controller.restore()
	while not controller.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.run_id == domain_id and controller.current.get("state") == "succeeded", "real restored status reads same Executor run")
	model.nodes[0].parameters.fail = true
	controller.start(model)
	deadline = Time.get_ticks_msec() + 20000
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "failed", "real provider failure reaches controller domain snapshot")
	controller.retry("copy")
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "failed" and controller.current.nodes.copy.attempt == 1, "real retry retains domain run and increments Executor attempt")
	model.nodes[0].parameters.fail = false
	controller.start(model)
	controller.cancel()
	while (not controller.jobs.is_empty() or controller.auto_step or controller.creating) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "cancelled", "real immediate cancellation during create is durable")
	controller.restore()
	while not controller.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "cancelled" and controller.jobs.is_empty(), "real cancelled run restores without reissuing work")
	var marker = local.path_join("lookup.txt")
	OS.set_environment("AINATIVE_LOOKUP_MARKER", marker)
	var lookup_config = controller.configuration.duplicate(true)
	lookup_config.factory = "test_editor_host:reconcile_factory"
	controller.configure(lookup_config)
	model.nodes[0].text = "unique unknown-submission fixture"
	controller.start(model)
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "reconcile" and FileAccess.get_file_as_string(marker) == "submit\n", "real unknown submission pauses after one submission")
	controller.resume()
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "reconcile" and FileAccess.get_file_as_string(marker) == "submit\nlookup\n", "real explicit resume performs lookup without duplicate submission")
	await transport_receipt_regressions(model)
	controller.configure({"state_dir": local, "db": local.path_join("executor.sqlite"), "python": "", "script": "fixture"})
	controller.start(model)
	check(not controller.creating and not controller.auto_step and controller.jobs.is_empty(), "invalid environment clears creating state without starting a process")
	lookup_config.factory = "editor_demo:factory"
	controller.configure(lookup_config)
	model.nodes[0].parameters.delay = 5.0
	model.nodes[0].text = "shutdown ownership fixture"
	controller.start(model)
	while controller.creating and Time.get_ticks_msec() < deadline: await process_frame
	var owned = controller.jobs.keys()
	controller.shutdown()
	var stop_deadline = Time.get_ticks_msec() + 2000
	while owned.any(_process_exists) and Time.get_ticks_msec() < stop_deadline: await process_frame
	check(not owned.is_empty() and not owned.any(_process_exists) and controller.jobs.is_empty(), "explicit shutdown terminates owned real transport processes")
	check(controller.public_snapshot.state == "reconciling", "transport shutdown retains unknown domain outcome for later reconciliation")
	controller.queue_free()

func transport_receipt_regressions(model: Dictionary):
	var local = state_dir.path_join("receipt-regressions")
	DirAccess.make_dir_recursive_absolute(local)
	var host_path = local.path_join("host.py")
	var host_file = FileAccess.open(host_path, FileAccess.WRITE)
	host_file.store_string("""import argparse,json,os,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('command')
for name in ('db','factory','spec','result'):p.add_argument('--'+name,required=True)
a=p.parse_args();a.service_config=None
if a.factory=='delayed-status':
    result={'state':'cancelled' if a.command=='cancel' else 'running','nodes':{}}
    if a.command=='status':time.sleep(.5)
else:
    sys.path.insert(0,os.environ['AINATIVE_UI_TOOLS'])
    import editor_host
    result=editor_host.dispatch(a,json.loads(Path(a.spec).read_text()))
    if a.command=='step':sys.exit(7) # Durable Executor mutation, missing transport receipt.
Path(a.result).write_text(json.dumps({'ok':True,'result':result}))
""")
	host_file.close()
	var controller = Controller.new()
	controller.runtime = RuntimeFixture.new()
	var config = {"state_dir":local,"db":local.path_join("regression.sqlite"),"python":OS.get_environment("AINATIVE_PYTHON"),"script":host_path,"factory":"delayed-status"}
	controller.configure(config)
	root.add_child(controller)
	controller.run_id = "original-domain"
	controller.model_snapshot = model.duplicate(true)
	controller._begin_public("restore", "reconciling")
	controller.restore()
	await create_timer(.1).timeout
	controller.cancel()
	var deadline = Time.get_ticks_msec() + 10000
	while not controller.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "cancelled" and controller.public_snapshot.state == "cancelled", "late real status read cannot overwrite a completed cancel")
	config.factory = "test_editor_host:reconcile_factory"
	controller.configure(config)
	var marker = local.path_join("submit-marker.txt")
	OS.set_environment("AINATIVE_LOOKUP_MARKER", marker)
	model = model.duplicate(true)
	model.nodes[0].text = "lost transport receipt regression"
	controller.start(model)
	while (not controller.jobs.is_empty() or controller.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.public_snapshot.state == "reconciling" and FileAccess.get_file_as_string(marker) == "submit\n", "lost real step receipt preserves unknown submission instead of failing public run")
	var public_id = controller.public_snapshot.run_id
	controller.restore()
	while not controller.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(controller.current.get("state") == "reconcile" and controller.public_snapshot.state == "reconciling" and controller.public_snapshot.run_id == public_id, "restore reconciles same public identity with durable Executor")
	check(FileAccess.get_file_as_string(marker) == "submit\n", "readback after missing receipt never submits again")
	controller.queue_free()

func view_lifecycle():
	var first = load("res://addons/ainative/workbench.gd").new()
	first.state_dir = state_dir.path_join("views")
	root.add_child(first)
	first.workflow_controller.runtime = RuntimeFixture.new()
	var shared = first.workflow_controller
	var second = load("res://addons/ainative/workbench.gd").new()
	second.state_dir = first.state_dir
	root.add_child(second)
	check(first.workflow_controller == second.workflow_controller and shared._views == 2, "two actual Workbench Views bind one Controller")
	check(shared.completed.get_connections().size() == 2, "each View subscribes once")
	first.queue_free()
	await process_frame
	await process_frame
	check(shared._views == 1 and shared.completed.get_connections().size() == 1, "actual View exit unbinds only its subscriptions")
	second.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	second.host_edit.text = OS.get_environment("AINATIVE_UI_TOOLS").path_join("editor_host.py")
	second.factory_edit.text = "editor_demo:factory"
	second._set_node_file("source", ProjectSettings.globalize_path("res://fixtures/sample.png"))
	second.parameter_form.configure("copy", {"delay": 0.01, "fail": false})
	second.start_run()
	var deadline = Time.get_ticks_msec() + 20000
	while (not second.jobs.is_empty() or second.auto_step) and Time.get_ticks_msec() < deadline: await process_frame
	check(second.current.get("state") == "succeeded" and not shared.public_snapshot.is_empty(), "actual Workbench start delegates real Executor and runtime events")
	second.request_preview()
	while not second.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(second.preview_resource != null and not second.preview_token.is_empty(), "preview result signal loads real generated artifact")
	second.target_edit.text = second.state_dir.path_join("published.tres")
	second.review_publish()
	check(not FileAccess.file_exists(second.target_edit.text) and second.jobs.is_empty(), "review stages resource and requires explicit confirmation")
	var reviewed = second.confirmation.duplicate(true)
	second.preview_token = "changed"
	second.confirm_publish()
	check(second.jobs.is_empty() and not FileAccess.file_exists(second.target_edit.text), "changed preview rejects stale publish confirmation")
	second.preview_token = reviewed.confirmation
	second.confirmation = reviewed
	second.confirm_publish()
	second.dialog.hide()
	while not second.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(FileAccess.file_exists(second.target_edit.text), "confirmed publish delegates existing host atomic publication")
	second.run_node_preview(second.selected_id)
	while (not second.jobs.is_empty() or second.auto_step or second.creating) and Time.get_ticks_msec() < deadline: await process_frame
	check(second.preview_resource != null and second.preview_run == second.run_id and not second.preview_token.is_empty(), "actual node preview entry runs controller dependency target and loads result")
	var original_id = second.run_id
	second.queue_free()
	await process_frame
	await process_frame
	var rebuilt = load("res://addons/ainative/workbench.gd").new()
	rebuilt.state_dir = state_dir.path_join("views")
	root.add_child(rebuilt)
	while not rebuilt.jobs.is_empty() and Time.get_ticks_msec() < deadline: await process_frame
	check(rebuilt.workflow_controller == shared and rebuilt.run_id == original_id and rebuilt.current.get("state") == "succeeded", "rebuilt actual View reuses and queries original domain run")
	rebuilt.queue_free()
	await process_frame

func _process_exists(pid: int) -> bool:
	# Godot deliberately drops killed children from its PID table. Querying that
	# table after shutdown logs an invalid-child error, so use OS liveness here.
	var code = "import os,sys\ntry: os.kill(int(sys.argv[1]),0)\nexcept ProcessLookupError: sys.exit(1)"
	return OS.execute(OS.get_environment("AINATIVE_PYTHON"), PackedStringArray(["-c", code, str(pid)])) == 0
