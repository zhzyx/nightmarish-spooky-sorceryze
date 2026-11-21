extends SceneTree

var view: Node
var lifecycle: Node
var accept: Button
var close: Button
var reopen: Button
var feedback: Label
var history: Label


func _initialize() -> void:
	run.call_deferred()


func check(ok: bool, reason: String) -> bool:
	if not ok:
		printerr("I15: " + reason)
		quit(1)
	return ok


func wait_for(condition: Callable, reason: String) -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return check(condition.call(), reason + (" / " + feedback.text if feedback else ""))


func run() -> void:
	await create_timer(1).timeout
	var palette := EditorInterface.get_command_palette()
	var key := InputEventShortcut.new()
	key.shortcut = EditorInterface.get_editor_settings().get_shortcut("editor/command_palette")
	root.push_input(key)
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	if not check(results.get_selected().get_metadata(0) == search.text, "palette action"):
		return
	results.item_activated.emit()
	await process_frame
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	lifecycle = view.get_node_or_null("issue_lifecycle")
	if not check(lifecycle != null, "compiled lifecycle control"):
		return
	if not await wait_for(func(): return not session.get_identity().is_empty(), "account"):
		return
	accept = lifecycle.find_child("AcceptIssueEvidence", true, false)
	close = lifecycle.find_child("CloseAcceptedIssue", true, false)
	reopen = lifecycle.find_child("ReopenIssue", true, false)
	feedback = lifecycle.find_child("IssueLifecycleFeedback", true, false)
	history = lifecycle.find_child("IssueLifecycleHistory", true, false)
	var phase := OS.get_environment("I15_PHASE")
	var number := int(OS.get_environment("I15_NUMBER"))
	await view.open_issue(number)
	if not await wait_for(func(): return lifecycle.is_visible_in_tree() and not feedback.text.is_empty(), "lifecycle read"):
		return
	if phase == "close":
		var assignment := view.get_node("issue_assignment")
		assignment.find_child("EditIssueProperties", true, false).pressed.emit()
		var stages := assignment.find_child("IssueStageChoice", true, false) as OptionButton
		if not await wait_for(func(): return not stages.disabled, "existing I06 form"):
			return
		for i in stages.item_count:
			if not check(stages.get_item_text(i) != "done", "unguarded completion in status editor"):
				return
		close.pressed.emit()
		if not await wait_for(func(): return feedback.text.contains("缺少本版验收证据"), "missing evidence denied"):
			return
		var comments := view.get_node("issue_comments")
		var thread := comments.find_child("IssueCommentThread", true, false) as ItemList
		if not await wait_for(func(): return thread.item_count == 1, "evidence comment"):
			return
		thread.select(0)
		thread.item_selected.emit(0)
		var body := comments.find_child("SelectedCommentBody", true, false) as RichTextLabel
		if not check(body.text == OS.get_environment("I15_EVIDENCE"), "actual inspected evidence"):
			return
		accept.pressed.emit()
		if not await wait_for(func(): return history.text.contains("确认验收") and not close.disabled, "recorded decision"):
			return
		close.pressed.emit()
		if not await wait_for(func(): return view.get_detail().get("status") == "done" and history.text.contains("关闭"), "lost close response reconciled"):
			return
	elif phase == "reopen":
		if not check(not reopen.disabled, "reopen enabled"):
			return
		reopen.pressed.emit()
		if not await wait_for(func(): return feedback.text.contains("可重试同一操作") and not reopen.disabled, "pre-commit 503 and readback"):
			return
		reopen.pressed.emit()
		if not await wait_for(func(): return view.get_detail().get("status") == "in-review" and history.text.contains("重开"), "reopened history"):
			return
		close.pressed.emit()
		if not await wait_for(func(): return feedback.text.contains("缺少本版验收证据"), "prior acceptance expired"):
			return
	else:
		if not check(accept.disabled and close.disabled and reopen.disabled and feedback.text.contains("仅可查看"), "viewer controls"):
			return
	var observation := {"id": view.get_detail().id, "number": int(view.get_detail().number),
			"status": view.get_detail().status, "revision": view.get_detail().revision, "history": history.text}
	session.find_child("SignOut", true, false).pressed.emit()
	if not check(not lifecycle.visible and history.text.is_empty(), "cleared on signout"):
		return
	print("I15_REPORT=" + JSON.stringify(observation))
	quit()
