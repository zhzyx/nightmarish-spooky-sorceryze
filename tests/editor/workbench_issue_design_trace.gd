extends "res://workbench_issue_detail.gd"

var fixture: Dictionary
var session: Node
var tree: Tree
var trace := {}


func open_from_roadmap(path: Array, issue: Dictionary) -> bool:
	var open := session.find_child("OpenIssueRoadmap", true, false) as Button
	if not require(open.is_visible_in_tree() and not open.disabled, "Roadmap unavailable"):
		return false
	open.pressed.emit()
	if not require(await wait_for(func(): return tree.get_root() != null), "Roadmap read failed"):
		return false
	var item := tree.get_root()
	for caption: String in path:
		var next: TreeItem
		for child in item.get_children():
			if child.get_text(0) == caption:
				next = child
				break
		if not require(next != null, "Roadmap missing " + caption):
			return false
		item.collapsed = false
		item = next
	if not require(item.get_metadata(0) == int(issue.number), "Incorrect roadmap item"):
		return false
	item.select(0)
	tree.item_activated.emit()
	return require(await wait_for(func(): return view.get_detail().get("id") == issue.id), "Wrong issue opened")


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	session = dock.find_child("WorkbenchBusinessSession", true, false)
	view = session.get_node("WorkbenchIssueDetail")
	tree = session.find_child("IssueRoadmapTree", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "Session unavailable"):
		return
	fixture = JSON.parse_string(OS.get_environment("Q13_FIXTURE"))
	var parent_path: Array = fixture.path.slice(0, -1)
	if not await open_from_roadmap(parent_path, fixture.parent):
		return
	var hierarchy := view.find_child("IssueHierarchyCurrent", true, false) as Label
	if not require(await wait_for(func(): return fixture.child.title in hierarchy.text), "Missing child"):
		return
	trace.parent_hierarchy = hierarchy.text
	trace.parent_id = view.get_detail().id
	if not await open_from_roadmap(fixture.path, fixture.child):
		return
	var deps := view.find_child("DependencyList", true, false) as ItemList
	var comments := view.find_child("IssueCommentThread", true, false) as ItemList
	if not require(await wait_for(func(): return deps.item_count == 1 and comments.item_count == 1 and fixture.parent.title in hierarchy.text), "Incomplete child details"):
		return
	trace.detail = view.get_detail()
	trace.fields = view.find_child("IssueDetailFields", true, false).text
	trace.child_hierarchy = hierarchy.text
	trace.dependency = {"id": deps.get_item_metadata(0), "label": deps.get_item_text(0)}
	comments.select(0)
	comments.item_selected.emit(0)
	trace.comment = comments.get_item_metadata(0)
	trace.comment_body = view.find_child("SelectedCommentBody", true, false).text
	var source := view.find_child("OpenIssueDesignSource", true, false) as Button
	if not require(source.is_visible_in_tree(), "Source design unavailable"):
		return
	source.pressed.emit()
	var docs = session.get_node("WorkbenchDocuments")
	if not require(await wait_for(func(): return docs.visible and not docs.reference.is_empty()), "Source did not open"):
		return
	trace.reference = docs.reference.duplicate()
	trace.body = docs.raw_body
	docs.history.pressed.emit()
	var history = session.get_node("WorkbenchDocumentHistory")
	if not require(await wait_for(func(): return history.dialog.visible and not history.diff.text.is_empty()), "History unavailable"):
		return
	trace.history = {"document_id": history.document_id, "from": history.source.get_selected_id(),
			"to": history.comparison.get_selected_id(), "diff": history.diff.text}
	print("WORKBENCH_REPORT=", JSON.stringify(trace))
	quit()
