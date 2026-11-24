extends SceneTree
## The hosting service is an actual disposable Gitea instance, not a fake client.

var checks: Array[String] = []
var main: Control
var controller: Node
var model: Node
var view: Control


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Native hosting: " + description)
		if model:
			print(JSON.stringify({"status": model.status, "errors": model.errors}))
		quit(1)
		return false
	checks.append(description)
	return true


func wait_until(predicate: Callable) -> bool:
	for attempt in 600:
		if predicate.call():
			return true
		await create_timer(0.025).timeout
	return false


func idle() -> bool:
	return not model.saving and model._pending.is_empty()


func submit(operation: String, accepted := true) -> bool:
	if not check(await wait_until(idle) and not view._submit[operation].disabled, "native hosting form is ready: " + operation):
		return false
	view._submit[operation].pressed.emit()
	if not check(view._dialog.visible and not model.saving, "hosting write waits for explicit confirmation: " + operation):
		return false
	view._dialog.confirmed.emit()
	view._dialog.hide()
	if not check(await wait_until(func(): return idle() and model.draft("pending").is_empty()), "hosting request has a determinate result: " + operation):
		return false
	return check(model.status.begins_with("操作已接收") == accepted, ("hosting service accepts " if accepted else "hosting service rejects ") + operation)


func open_repository() -> bool:
	controller.navigate("repository_collaboration")
	view = main._page_instances.repository_collaboration
	view._owner.text = "native-author"
	view._repository.text = "shared-fixture"
	view.find_child("NativeCollaborationOpen", true, false).pressed.emit()
	return check(await wait_until(func(): return idle() and model.data.get("branches", {}).get("branches", []).size() == 3), "native branch list reads the real hosted repository")


func select_pull() -> bool:
	var row: TreeItem = view._pulls.get_root().get_first_child()
	if not check(row != null, "native pull request tree contains the created request"):
		return false
	row.select(0)
	view._pulls.item_selected.emit()
	return check(await wait_until(func(): return model.pull_number > 0 and idle()), "native pull request selection loads the hosted reviews")


func discard_form(operation: String) -> bool:
	view.find_child("NativeCollaborationDiscard_" + operation, true, false).pressed.emit()
	view._dialog.confirmed.emit()
	view._dialog.hide()
	return check(model.draft(operation).is_empty(), "explicit discard loads the current record: " + operation)


func stale_confirmation(operation: String, action: String) -> bool:
	view._submit[operation].pressed.emit()
	var expected: Dictionary = view._intent.expected.duplicate(true)
	var changed: Dictionary = await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/native-test/hosting/" + action, {})
	if not check(changed.status == 200 and view._intent.expected == expected, "remote change occurs after the native confirmation snapshot: " + operation):
		return false
	view._dialog.confirmed.emit()
	view._dialog.hide()
	if not check(await wait_until(func(): return idle() and model.draft("pending").is_empty()), "stale hosting request returns a determinate conflict: " + operation):
		return false
	return check(not model.status.begins_with("操作已接收") and model.snapshot() != expected, "old confirmation cannot mutate the changed hosted record: " + operation)


func run() -> void:
	root.size = Vector2i(1600, 1000)
	await process_frame
	await process_frame
	main = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
	if not check(main != null, "compiled native hosting page is available"):
		return
	controller = main.get_meta("controller")
	model = controller.repository_collaboration
	await controller.session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await open_repository():
		return
	var identity: Dictionary = controller.session.get_identity().duplicate(true)
	await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/native-test/hosting/auth_expired", {})
	await model.load_catalog()
	if not check(controller.session.get_identity() == identity and model.errors.has("repositories"), "upstream authentication failure does not log out a valid Tianxuan session"):
		return
	await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/native-test/hosting/auth_restored", {})
	await model.load_catalog()
	if not check(not model.errors.has("repositories") and controller.session.get_identity() == identity, "restored hosting authentication resumes the same native session"):
		return
	view._forms.create_repository.name.text = "native-created"
	if not await submit("create_repository"):
		return
	if not check(model.data.repositories.repos.any(func(item: Dictionary): return item.full_name == "native-author/native-created"), "native-created private repository appears in the real hosting catalog"):
		return
	view._forms.create_repository.name.text = "native-unknown"
	view._submit.create_repository.pressed.emit()
	view._dialog.confirmed.emit()
	view._dialog.hide()
	if not check(await wait_until(func(): return not model.saving and not model.draft("pending").is_empty()), "lost upstream acknowledgement retains the exact pending request despite a legacy HTTP 400"):
		return
	await model.load_catalog()
	if not check(model.data.repositories.repos.any(func(item: Dictionary): return item.full_name == "native-author/native-unknown") and not model.writable(), "readback finds the real created repository while duplicate submission remains blocked"):
		return
	view._ack.pressed.emit()
	if not check(model.draft("pending").is_empty(), "explicit checked-record acknowledgement restores editing"):
		return
	view._forms.create_pull.title.text = "原生审查与合并"
	view._forms.create_pull.head.text = "feature"
	view._forms.create_pull.body.text = "通过原生界面提出的实际托管仓库变更。"
	if not await submit("create_pull") or not await select_pull():
		return
	if not await submit("merge_pull", false):
		return
	if not check(model.data.pulls.pulls[0].state == "open", "required approval blocks merging and preserves the open request"):
		return
	await controller.session.authenticate("reviewer@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await open_repository() or not await select_pull():
		return
	view._forms.review_pull.event.select(1)
	view._forms.review_pull.event.item_selected.emit(1)
	view._forms.review_pull.body.text = "已核对实际来源分支的文本变更。"
	if not await stale_confirmation("review_pull", "advance"):
		return
	if not check(model.data.reviews.reviews.is_empty() and not model.draft("review_pull").is_empty(), "stale review creates no approval and retains the original review draft"):
		return
	if not await submit("review_pull", false) or not await discard_form("review_pull"):
		return
	view._forms.review_pull.event.select(1)
	view._forms.review_pull.event.item_selected.emit(1)
	view._forms.review_pull.body.text = "Reviewed the refreshed commit."
	if not await submit("review_pull"):
		return
	if not check(model.data.reviews.reviews.any(func(item: Dictionary): return item.state == "APPROVED" and item.user == "native-reviewer"), "hosted approval is attributed to the separate bound reviewer account"):
		return
	await controller.session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await open_repository() or not await select_pull():
		return
	if not await stale_confirmation("merge_pull", "advance"):
		return
	if not await submit("merge_pull", false):
		return
	await controller.session.authenticate("reviewer@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await open_repository() or not await select_pull():
		return
	view._forms.review_pull.event.select(1)
	view._forms.review_pull.event.item_selected.emit(1)
	view._forms.review_pull.body.text = "Reviewed the newest commit after the merge conflict."
	if not await submit("review_pull"):
		return
	await controller.session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	if not await open_repository() or not await select_pull():
		return
	var original_head: String = model.revision("merge_pull").head_sha
	if not await stale_confirmation("merge_pull", "retarget"):
		return
	if not check(model.revision("merge_pull").head_sha == original_head and model.revision("merge_pull").base == "staging", "retargeting is rejected even when the approved HEAD is unchanged"):
		return
	await controller.session.api_request(HTTPClient.METHOD_POST, "/api/v1/native-test/hosting/restore_target", {})
	await model.refresh_repository()
	if not await submit("merge_pull"):
		return
	view._filter.select(1)
	view._filter.item_selected.emit(1)
	if not check(await wait_until(func(): return idle() and model.data.get("pulls", {}).get("pulls", []).size() == 1 and model.data.pulls.pulls[0].state == "closed"), "native closed-request filter reads back the actual merged request"):
		return
	view._forms.create_release.tag_name.text = "v-native-1"
	view._forms.create_release.name.text = "原生发布草稿"
	view._forms.create_release.body.text = "对应刚刚合入的实际提交。"
	if not await submit("create_release"):
		return
	if not check(model.data.releases.releases.size() == 1 and model.data.releases.releases[0].draft, "native release creation retains the explicit draft state"):
		return
	var row: TreeItem = view._releases.get_root().get_first_child()
	row.select(0)
	view._releases.item_selected.emit()
	await process_frame
	view._forms.update_release.name.text = "原生正式发布"
	view._forms.update_release.name.text_changed.emit(view._forms.update_release.name.text)
	if not await stale_confirmation("update_release", "release"):
		return
	if not check(model.data.releases.releases[0].body == "Collaborator release notes" and model.draft("update_release").name == "原生正式发布", "conflicting release preserves collaborator content and the original local form"):
		return
	if not await submit("update_release", false) or not await discard_form("update_release"):
		return
	view._forms.update_release.name.text = "原生正式发布"
	view._forms.update_release.name.text_changed.emit(view._forms.update_release.name.text)
	view._forms.update_release.draft.button_pressed = false
	if not await submit("update_release"):
		return
	if not check(not model.data.releases.releases[0].draft and model.data.releases.releases[0].name == "原生正式发布", "native release edit publishes the selected real hosting release"):
		return
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
