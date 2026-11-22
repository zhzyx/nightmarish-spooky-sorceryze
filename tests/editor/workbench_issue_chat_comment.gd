extends "res://issue_consultation.gd"


func _run() -> void:
	await create_timer(1).timeout
	var palette := EditorInterface.get_command_palette()
	palette.popup_centered()
	await process_frame
	var search := palette.find_children("*", "LineEdit", true, false).front() as LineEdit
	var results := palette.find_children("*", "Tree", true, false).front() as Tree
	search.text = "editor/open_ai_workbench"
	search.text_changed.emit(search.text)
	results.item_activated.emit()
	await process_frame
	var dock := root.find_child("AIWorkbenchSidebar", true, false)
	view = dock.find_child("WorkbenchIssueDetail", true, false)
	panel = dock.find_child("WorkbenchBusinessModules", true, false)
	if not check(await wait_for(func(): return panel.managed_identity and not panel.session.get_identity().is_empty()), "login"):
		return
	if not view.find_child("IssueDetailNumber", true, false).is_visible_in_tree():
		view.find_child("OpenIssueDetail", true, false).pressed.emit()
	var numbers: Array = JSON.parse_string(OS.get_environment("U11_NUMBERS"))
	var review := panel.find_child("ReviewIssueChatComment", true, false) as Button
	var dialog := panel.find_child("AuthorizeIssueChatComment", true, false) as ConfirmationDialog
	var widget := view.get_node("issue_comments")
	var thread := widget.get_node("IssueCommentThread") as ItemList
	if not await open_detail(int(numbers[0])):
		return
	if not check(review.is_visible_in_tree(), "review missing for first item"):
		return
	review.pressed.emit()
	if not check(dialog.visible, "preview missing"):
		return
	dialog.get_cancel_button().pressed.emit()
	if not check(await wait_for(func(): return not dialog.visible), "cancel did not dismiss preview"):
		return
	dialog.confirmed.emit()
	if not check(not dialog.visible and not panel.busy, "cancel retained authorization"):
		return
	review.pressed.emit()
	# A second detail with the same title invalidates the first open authorization.
	if not await open_detail(int(numbers[1])):
		return
	if not check(not dialog.visible and not review.visible and thread.item_count == 0, "sibling reused authority"):
		return
	dialog.confirmed.emit()
	if not await open_detail(int(numbers[0])):
		return
	if not check(await wait_for(func(): return not widget._busy) and thread.item_count == 0, "consultation wrote a comment"):
		return
	var draft := widget.get_node("IssueCommentDraft") as TextEdit
	draft.text = "正在编辑的手写草稿"
	draft.text_changed.emit()
	review.pressed.emit()
	var preview := dialog.find_children("*", "TextEdit", true, false).front() as TextEdit
	if not check(dialog.visible and dialog.title.contains("#%d" % int(numbers[0])) and preview.text == panel.conversation.turns.back().answer, "preview target or body"):
		return
	var body := preview.text
	dialog.get_ok_button().pressed.emit()
	if not check(await wait_for(func(): return not panel.busy) and thread.item_count == 1 and not review.visible, "comment readback: " + panel.feedback.text):
		return
	var receipt: Dictionary = thread.get_item_metadata(0)
	if not check(widget.get_selected_comment_id() == receipt.id and widget.get_node("SelectedCommentBody").text == body and receipt.body == body and draft.text == "正在编辑的手写草稿", "selected comment/draft"):
		return
	if not await open_detail(int(numbers[1])):
		return
	if not check(await wait_for(func(): return not widget._busy) and thread.item_count == 0, "second detail changed"):
		return
	if not await open_detail(int(numbers[0])):
		return
	if not check(await wait_for(func(): return not widget._busy) and thread.item_count == 1 and thread.get_item_metadata(0) == receipt and not review.visible, "reopened first detail"):
		return
	print("I16_NATIVE=", JSON.stringify({"preview": body, "selected_comment": receipt, "sibling_rows": 0, "manual_draft_preserved": true, "reopened": true}))
	quit()
