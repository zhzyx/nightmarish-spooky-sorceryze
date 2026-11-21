@tool
extends VBoxContainer

var consult := Button.new()


func _ready() -> void:
	var detail := get_parent()
	consult.name = "ConsultIssueDetail"
	consult.text = "咨询此工单"
	add_child(consult)
	detail.detail_changed.connect(func(): visible = not detail.get_detail().is_empty())
	visible = not detail.get_detail().is_empty()
	consult.pressed.connect(func():
		var panel := get_tree().root.find_child("WorkbenchBusinessModules", true, false)
		if panel:
			panel.open_issue_consultation(detail)
	)
