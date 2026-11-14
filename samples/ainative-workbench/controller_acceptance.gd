extends SceneTree
## Exercises the real controller, native AICore and Python Executor without a View.

const Controller = preload("res://addons/ainative/workbench_controller.gd")
var controller: RefCounted
var failures := 0
var checks: Array = []
var events: Array = []
var previews: Array = []

func check(passed: bool, label: String):
	print(("PASS " if passed else "FAIL ") + label)
	checks.append({"passed": passed, "label": label})
	if not passed: failures += 1

func _initialize():
	call_deferred("run")

func wait_idle(subject = null):
	if subject == null:
		subject = controller
	var deadline = Time.get_ticks_msec() + 30000
	while subject.is_busy() and Time.get_ticks_msec() < deadline:
		subject.tick()
		await create_timer(0.01).timeout
	check(not subject.is_busy(), "controller reaches an idle state")

func copy_model(source: String, fail: bool = false) -> Dictionary:
	return {"format": 1, "nodes": [{"id": "copy", "type": "copy", "version": "1", "provider": "local-copy", "model": "frozen-model", "source": source, "image_context": "", "text": "controller regression", "parameters": {"delay": 0.15, "fail": fail}, "x": 0, "y": 0}], "edges": []}

func completed(command: String, data: Dictionary, _request: Dictionary):
	if command == "preview": previews.append(data)

func run():
	check(ClassDB.class_exists("AIWorkflowRuntime"), "candidate provides the native AIWorkflowRuntime")
	if failures:
		finish()
		return
	controller = Controller.new()
	controller.runtime_event.connect(func(event): events.append(event))
	controller.command_completed.connect(completed)
	controller.command_failed.connect(func(command, failure):
		print("COMMAND_FAILED ", command, " ", JSON.stringify(failure)))
	check(not controller.is_class("Node"), "controller has no scene-tree or View dependency")
	var directory = ProjectSettings.globalize_path("user://controller-test-" + str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(directory)
	var settings = {"python": OS.get_environment("AINATIVE_PYTHON"), "script": ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py"), "database": directory.path_join("executor.sqlite"), "factory": "editor_demo:factory", "state_dir": directory, "use_service": false}
	controller.configure(settings)
	var model = copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png"))
	var mutate_on_start = func(event):
		if event.kind == "run_started":
			model.nodes[0].model = "listener-model"
			model.nodes[0].source = directory.path_join("missing-source.png")
			var changed_settings = settings.duplicate(true)
			changed_settings.database = directory.path_join("listener-database.sqlite")
			changed_settings.factory = "missing_plugin:factory"
			controller.configure(changed_settings)
	controller.runtime_event.connect(mutate_on_start)
	var reentrant_starts: Array = []
	var start_on_artifact = func(event):
		if event.kind == "artifact_ready":
			var previous_run = controller.run_id
			var previous_serial = controller.serial
			reentrant_starts.append({"accepted": controller.start(model), "same_run": controller.run_id == previous_run, "same_serial": controller.serial == previous_serial})
	controller.runtime_event.connect(start_on_artifact)
	var started = controller.start(model, "copy")
	check(started, "controller starts through its public data-only API")
	if not started:
		controller.shutdown()
		finish()
		return
	controller.runtime_event.disconnect(mutate_on_start)
	controller.configure(settings)
	model.nodes[0].model = "changed-after-start"
	check(controller.runtime_snapshot().model.copy.model == "frozen-model", "native run freezes the selected node model")
	var first_generation = int(controller.runtime_snapshot().generation)
	check(not controller.start(model), "a concurrent start cannot replace the active run")
	await wait_idle()
	check(controller.current.get("state") == "succeeded" and previews.size() == 1, "real Executor output reaches the preview event")
	if controller.current.get("state") != "succeeded":
		controller.shutdown()
		finish()
		return
	check(controller.runtime_snapshot().binding.database == settings.database and FileAccess.file_exists(settings.database) and not FileAccess.file_exists(directory.path_join("listener-database.sqlite")), "run_started listener cannot change the submitted model or execution settings")
	check(controller.runtime_snapshot().state == "succeeded", "Executor success becomes a native completed event")
	controller.runtime_event.disconnect(start_on_artifact)
	check(reentrant_starts.size() == 1 and not reentrant_starts[0].accepted and reentrant_starts[0].same_run and reentrant_starts[0].same_serial, "artifact callbacks cannot replace the run while its result is being committed")
	var next_sequence := 1
	for event in events:
		check(int(event.sequence) == next_sequence, "native events keep a monotonic sequence")
		next_sequence += 1
	var restored = Controller.new()
	restored.configure(settings)
	var persisted_id = FileAccess.get_file_as_string(directory.path_join("last_run.txt"))
	check(restored.restore_run(persisted_id), "a new controller reads the persisted execution through its restore entry")
	await wait_idle(restored)
	var restored_snapshot = restored.runtime_snapshot()
	check(restored_snapshot.get("state") == "succeeded" and restored_snapshot.get("binding", {}).get("executor_run_id") == persisted_id, "restored execution is attached to the shared runtime")
	check(restored_snapshot.get("binding", {}).get("model_source") == "persisted_executor" and restored_snapshot.get("model", {}).get("copy") == controller.current.nodes.copy.provider_manifest, "restoration freezes the actual persisted provider identity")
	restored.shutdown()
	var compatible = Controller.new()
	compatible.configure(settings)
	compatible.run_id = persisted_id
	compatible.submit("status", {"run": persisted_id})
	await wait_idle(compatible)
	check(compatible.runtime_snapshot().get("binding", {}).get("executor_run_id") == persisted_id, "legacy run_id plus status also attaches to the shared runtime")
	compatible.shutdown()
	var previews_before_cancel = previews.size()
	controller.submit("preview", {"run": controller.run_id, "node": "copy"})
	check(controller.has_command("preview"), "preview request is in flight before cancellation")
	controller.cancel()
	await wait_idle()
	check(previews.size() == previews_before_cancel and controller.current.get("state") == "cancelled", "cancel discards an in-flight preview while accepting the backend cancellation receipt")

	var serial_before_cancel = controller.serial
	var cancel_on_start = func(event):
		if event.kind == "run_started": controller.cancel()
	controller.runtime_event.connect(cancel_on_start)
	var accepted = controller.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png")))
	controller.runtime_event.disconnect(cancel_on_start)
	check(not accepted and controller.jobs.is_empty() and controller.serial == serial_before_cancel, "synchronous cancellation of run_started prevents process submission")
	check(controller.runtime_snapshot().state == "cancelled", "reentrant cancellation preserves the native terminal state")
	var native_runtime = ClassDB.instantiate("AIWorkflowRuntime")
	var native_subject = Controller.new(native_runtime)
	native_subject.configure(settings)
	var native_cancel_handler = func(event):
		if event.kind == "run_started": native_runtime.cancel(event.run_id)
	native_runtime.event_received.connect(native_cancel_handler)
	check(not native_subject.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png"))) and native_subject.serial == 0, "native synchronous cancellation also prevents dispatch before begin returns")
	native_runtime.event_received.disconnect(native_cancel_handler)
	native_subject.shutdown()

	controller.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png")), "copy")
	controller.cancel()
	check(controller.runtime_snapshot().state == "cancelled", "canceling during create immediately cancels the native run")
	await wait_idle()
	check(controller.current.get("state") == "cancelled" and previews.size() == 1, "cancel reaches the durable Executor and suppresses late preview")
	check(int(controller.runtime_snapshot().generation) > first_generation, "a subsequent run advances the native generation")

	controller.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png"), true))
	await wait_idle()
	check(controller.current.get("state") == "failed", "confirmed provider failure reaches the controller")
	var failed_generation = int(controller.runtime_snapshot().generation)
	controller.retry("copy")
	await wait_idle()
	check(controller.current.nodes.copy.attempt == 1 and controller.current.state == "failed", "retry uses the original durable run and increments its attempt")
	check(int(controller.runtime_snapshot().generation) > failed_generation, "retry opens a fresh native run generation")

	var marker = directory.path_join("lookup.txt")
	OS.set_environment("AINATIVE_LOOKUP_MARKER", marker)
	settings.factory = "test_editor_host:reconcile_factory"
	controller.configure(settings)
	var reconciliation_model = copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png"))
	reconciliation_model.nodes[0].text = "controller reconciliation fixture"
	controller.start(reconciliation_model)
	await wait_idle()
	check(controller.current.state == "reconcile" and controller.runtime_snapshot().state == "reconciling", "unknown submission preserves the reconciliation state")
	var resumed = Controller.new()
	resumed.configure(settings)
	resumed.run_id = controller.run_id
	resumed.resume()
	await wait_idle(resumed)
	check(FileAccess.get_file_as_string(marker).replace("\r", "") == "submit\nlookup\n", "resume queries the original submission without replaying it")
	check(resumed.runtime_snapshot().get("state") == "reconciling" and resumed.runtime_snapshot().get("binding", {}).get("model_source") == "persisted_executor", "cold resume restores model identity before polling the provider")
	resumed.shutdown()
	controller.reset()
	check(controller.run_id.is_empty() and controller.current.is_empty(), "reset releases execution identity after a workflow replacement")
	controller.shutdown()
	var parallel_settings = settings.duplicate(true)
	parallel_settings.state_dir = directory.path_join("parallel")
	parallel_settings.database = parallel_settings.state_dir.path_join("executor.sqlite")
	parallel_settings.factory = "editor_demo:factory"
	DirAccess.make_dir_recursive_absolute(parallel_settings.state_dir)
	var first = Controller.new()
	var second = Controller.new()
	first.configure(parallel_settings)
	second.configure(parallel_settings)
	check(first.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.png"))), "first parallel controller starts")
	check(second.start(copy_model(ProjectSettings.globalize_path("res://fixtures/sample.glb"))), "second parallel controller starts")
	check(first.serial == second.serial and first.jobs.values()[0].prefix != second.jobs.values()[0].prefix, "same-process controllers with equal serials have distinct transport files")
	var deadline = Time.get_ticks_msec() + 30000
	while (first.is_busy() or second.is_busy()) and Time.get_ticks_msec() < deadline:
		first.tick()
		second.tick()
		await create_timer(0.01).timeout
	check(not first.is_busy() and not second.is_busy() and first.current.get("state") == "succeeded" and second.current.get("state") == "succeeded", "two controllers complete against the same state directory and database")
	check(not first.run_id.is_empty() and not second.run_id.is_empty() and first.run_id != second.run_id, "parallel controllers retain independent durable run identities")
	var first_artifacts: Array = first.current.get("manifest", {}).get("artifacts", [])
	var second_artifacts: Array = second.current.get("manifest", {}).get("artifacts", [])
	check(first_artifacts.any(func(artifact): return artifact.type == "image") and not first_artifacts.any(func(artifact): return artifact.type == "mesh"), "first controller retains its image result")
	check(second_artifacts.any(func(artifact): return artifact.type == "mesh") and not second_artifacts.any(func(artifact): return artifact.type == "image"), "second controller retains its mesh result")
	first.shutdown()
	second.shutdown()
	finish()

func finish():
	if controller != null:
		controller.shutdown()
		for signal_name in ["runtime_event", "command_completed", "command_failed"]:
			for connection in controller.get_signal_connection_list(signal_name):
				controller.disconnect(signal_name, connection.callable)
		controller = null
	if OS.has_environment("AINATIVE_CONTROLLER_REPORT"):
		var output = FileAccess.open(OS.get_environment("AINATIVE_CONTROLLER_REPORT"), FileAccess.WRITE)
		output.store_string(JSON.stringify({"passed": failures == 0, "failures": failures, "checks": checks}, "  "))
	print("AINATIVE_CONTROLLER failures=" + str(failures))
	quit(1 if failures else 0)
