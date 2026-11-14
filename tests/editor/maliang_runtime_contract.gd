@tool
extends Node

class Transport extends "res://addons/ainative/workflow_controller.gd":
	var launched := []
	func launch(command: String, spec: Dictionary):
		launched.append({"command":command, "spec":spec.duplicate(true)})

var failures := []
var checks := 0
func check(ok: bool, description: String) -> void:
	checks += 1
	if not ok: failures.append(description)

func _ready() -> void:
	run.call_deferred()

func run() -> void:
	var service = Engine.get_singleton("AIWorkflowRuntime")
	var controller := Transport.new()
	get_tree().root.add_child(controller)
	controller.set_process(false)
	controller.configure({"state_dir":OS.get_user_data_dir(), "db":"isolated-runtime-contract"})
	var model := {"nodes":[{"id":"mesh", "type":"text_to_mesh", "provider":"fixture", "model":"mesh-v1", "image_model":"image-v2"}], "edges":[]}
	controller.start(model)
	check(controller.runtime == service and controller.launched.size() == 1, "actual Controller starts against editor singleton")
	var id: String = controller.public_snapshot.get("run_id", "")
	var frozen: Dictionary = service.snapshot(id).get("snapshot", {})
	check(frozen.get("model", {}).get("nodes", [])[0].image_model == "image-v2", "auxiliary image model accepted by actual metadata boundary")
	model.nodes[0].image_model = "edited"
	check(service.snapshot(id).snapshot.model.nodes[0].image_model == "image-v2", "native model snapshot remains frozen")
	controller._complete({"command":"create", "spec":{}}, {"run_id":"domain-one"})
	check(service.snapshot(id).snapshot.sequence == 2, "creation projection accepted by native event vocabulary")
	controller._complete({"command":"step", "spec":{}}, {"state":"succeeded", "nodes":{}})
	check(service.snapshot(id).snapshot.state == "succeeded", "actual native projection completes with domain result")
	controller.start(model)
	id = controller.public_snapshot.run_id
	controller._complete({"command":"create", "spec":{}}, {"run_id":"domain-two"})
	controller.cancel()
	controller._complete({"command":"cancel", "spec":{}}, {"state":"cancelled", "nodes":{}})
	controller._complete({"command":"step", "spec":{}}, {"state":"succeeded", "nodes":{}})
	check(controller.current.state == "cancelled" and service.snapshot(id).snapshot.state == "cancelled", "late domain result cannot resurrect native cancellation")
	controller.start(model)
	id = controller.public_snapshot.run_id
	controller._complete({"command":"create", "spec":{}}, {"run_id":"domain-three"})
	controller._failure("step", "missing transport receipt", {}, "ai", true)
	check(service.snapshot(id).snapshot.state == "reconciling", "unknown transport outcome is not a native terminal failure")
	controller._complete({"command":"status", "spec":{}}, {"state":"reconcile", "nodes":{}})
	check(service.snapshot(id).snapshot.state == "reconciling", "domain readback keeps original native run reconciling")
	controller.free()
	print(JSON.stringify({"checks":checks, "failures":failures, "native_runtime":true}))
	get_tree().quit(0 if failures.is_empty() else 1)
