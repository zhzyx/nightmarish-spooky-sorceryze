extends SceneTree


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	await create_timer(1.0).timeout
	var panel = root.find_child("DaqianWorkspace", true, false)
	var controller = panel._get_workflow_controller()
	panel.actor = {"user_id":"r02-owner", "repo_id":"r02-project"}
	panel.picker_scope = panel._repo()
	var cache: String = panel._private_path()
	var binding := {"number":1802, "request":"r02", "url":"fixture/1802"}
	var opens := []
	var model := {"backend":0, "id":"r02"}
	controller.session_opener = func(_url, _issue, _request, _message, _preview, selection, _embedded, _receipt, _existing, _background):
		opens.append(selection.execution_receipt)
		return ""
	var error: String = controller.submit_execution(binding, "original", model, false, false, false)
	if not error.is_empty() or opens.size() != 1:
		push_error("Original editor operation did not start")
		quit(1)
		return
	var receipt: Dictionary = opens[0]
	# Godot tears down the actual dock through EXIT_TREE on quit. Deliver the
	# already-running worker's receipt at that boundary and try its successor.
	panel.tree_exiting.connect(func():
		controller.finish_execution(receipt, "", true)
		var declined: String = controller.submit_execution(binding, "next", model, false, false, false)
		var file := FileAccess.open(cache, FileAccess.READ)
		var checkpoint: Dictionary = file.get_var(false).get("shutdown_checkpoint", {}) if file else {}
		if not declined.is_empty() and opens.size() == 1 and checkpoint.get("runs", []).size() == 1 and checkpoint.runs[0].issue == binding.url:
			print("DAQIAN_SHUTDOWN_OK ", JSON.stringify({"checkpoint":checkpoint, "dispatches_after_close":opens.size()-1}))
		else:
			push_error("Closing editor admitted work or lost its final checkpoint: " + JSON.stringify(checkpoint))
	, CONNECT_ONE_SHOT)
	quit()
