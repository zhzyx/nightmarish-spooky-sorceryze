@tool
extends VBoxContainer

signal save_requested
signal reload_requested

var heading := Label.new()
var summary := Label.new()
var issue_link := LinkButton.new()
var overview := VBoxContainer.new()
var card_text := RichTextLabel.new()
var back := Button.new()
var relations := RichTextLabel.new()
var location := Label.new()
var field := TextEdit.new()
var feedback := Label.new()
var save := Button.new()
var revert := Button.new()
var reload := Button.new()
var document := {}
var busy := false
var node_id := ""

func _ready() -> void:
	name = "IssueDetails"
	set_meta("ai_control_exclude", true)
	size_flags_vertical = SIZE_EXPAND_FILL
	var header := HBoxContainer.new()
	add_child(header)
	heading.size_flags_horizontal = SIZE_EXPAND_FILL
	heading.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	header.add_child(heading)
	header.add_child(issue_link)
	back.text = "工单详情"
	back.pressed.connect(show_overview)
	header.add_child(back)
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)
	overview.size_flags_vertical = SIZE_EXPAND_FILL
	add_child(overview)
	location.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	overview.add_child(location)
	field.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	field.placeholder_text = "此工单暂无偃师设计文档"
	field.size_flags_vertical = SIZE_EXPAND_FILL
	field.size_flags_stretch_ratio = 2.5
	field.text_changed.connect(_buttons)
	overview.add_child(field)
	var actions := HFlowContainer.new()
	overview.add_child(actions)
	save.text = "保存"
	save.pressed.connect(func(): save_requested.emit())
	actions.add_child(save)
	revert.text = "撤销修改"
	revert.pressed.connect(func(): set_document(document))
	actions.add_child(revert)
	reload.text = "刷新详情"
	reload.pressed.connect(func(): reload_requested.emit())
	actions.add_child(reload)
	feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	overview.add_child(feedback)
	var title := Label.new()
	title.text = "关联工单"
	overview.add_child(title)
	relations.size_flags_vertical = SIZE_EXPAND_FILL
	relations.selection_enabled = true
	relations.meta_clicked.connect(func(url): OS.shell_open(str(url)))
	overview.add_child(relations)
	card_text.size_flags_vertical = SIZE_EXPAND_FILL
	card_text.selection_enabled = true
	add_child(card_text)
	show_overview()

func show_overview() -> void:
	node_id = ""
	heading.text = "工单详情"
	back.hide()
	card_text.hide()
	overview.show()

func show_card(id: String, node: Dictionary, state: String, connected: PackedStringArray) -> void:
	node_id = id
	heading.text = str(node.get("title", id))
	back.show()
	overview.hide()
	card_text.show()
	card_text.text = "状态 · " + state + "\n\n" + str(node.get("value", ""))
	if not connected.is_empty():
		card_text.text += "\n\n关联板块\n" + "\n".join(connected)

func set_document(value: Dictionary, draft: Variant = null) -> void:
	document = value
	field.text = str(value.get("markdown", "")) if draft == null else str(draft)
	location.text = "偃师设计文档"
	if value.get("path", "") != "":
		location.text += " · " + str(value.path)
	if value.get("source", "") != "":
		location.text += "（%s）" % value.source
	_buttons()

func dirty() -> bool:
	return field.text != str(document.get("markdown", ""))

func _buttons() -> void:
	field.editable = document.get("editable", false) and not busy
	save.disabled = not field.editable or not dirty()
	revert.disabled = busy or not dirty()
	reload.disabled = busy
	if dirty() and not busy:
		feedback.text = "有未保存的修改"
	elif feedback.text == "有未保存的修改":
		feedback.text = ""

func set_related(rows: Array, empty_text: String, format_state: Callable) -> void:
	relations.clear()
	for row in rows:
		var url := str(row.get("url", ""))
		if not url.begins_with("https://github.com/") or not url.get_file().is_valid_int():
			continue
		relations.push_meta(url)
		relations.add_text("#%s %s" % [url.get_file(), row.get("title", "")])
		relations.pop()
		relations.add_text(" · %s · %s\n" % [row.get("relation", "关联"), format_state.call(row.get("status", "unknown"))])
	if rows.is_empty():
		relations.add_text(empty_text)
