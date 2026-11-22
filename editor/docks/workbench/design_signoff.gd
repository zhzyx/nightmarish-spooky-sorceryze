@tool
extends VBoxContainer

var view: AcceptDialog
var dialog := ConfirmationDialog.new()
var criteria := TextEdit.new()
var status := Label.new()
var document_id := ""
var version := 0
var generation := 0


func _ready() -> void:
	hide()
	var session := get_parent()
	if not session.is_node_ready():
		await session.ready
	view = session.get_node("WorkbenchDocuments")
	view.signoff.pressed.connect(_open)
	view.revision_cleared.connect(dialog.hide)
	view.visibility_changed.connect(_view_visibility_changed)
	view.add_child(dialog)
	dialog.dialog_hide_on_ok = false
	dialog.confirmed.connect(_confirm)
	dialog.visibility_changed.connect(_dialog_visibility_changed)
	dialog.get_cancel_button().text = "关闭"
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(480, 200) * EditorInterface.get_editor_scale()
	dialog.add_child(box)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(status)
	criteria.placeholder_text = "填写本修订的验收条件"
	criteria.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	criteria.size_flags_vertical = Control.SIZE_EXPAND_FILL
	criteria.text_changed.connect(_criteria_changed)
	box.add_child(criteria)


func _view_visibility_changed() -> void:
	if not view.visible:
		dialog.hide()


func _dialog_visibility_changed() -> void:
	if not dialog.visible:
		generation += 1
		document_id = ""
		version = 0
		criteria.clear()
		status.text = ""


func _route() -> String:
	return "/api/v1/docs/%s/versions/%d/signoff" % [document_id.uri_encode(), version]


func _open() -> void:
	if view.reference.is_empty() or dialog.visible:
		return
	document_id = view.reference.document_id
	version = int(view.reference.version)
	var attempt := generation
	dialog.title = "设计签认 · %s · v%d" % [document_id, version]
	criteria.editable = false
	dialog.get_ok_button().text = "确认 v%d" % version
	dialog.get_ok_button().disabled = true
	status.text = "正在读取此修订的签认回执…"
	dialog.popup_centered()
	var reply: Dictionary = await view.session.api_request(HTTPClient.METHOD_GET, _route())
	if attempt != generation:
		return
	if reply.status == 200 and reply.data.has("signoff"):
		if reply.data.signoff == null:
			status.text = "v%d 尚未签认。请核对正文并填写验收条件。" % version
			criteria.editable = true
			return
		if _show_receipt(reply.data.signoff):
			return
	status.text = "无法读取签认回执，请关闭并重开。"


func _show_receipt(receipt: Variant) -> bool:
	if not receipt is Dictionary or receipt.get("document_id") != document_id or int(receipt.get("version", 0)) != version:
		return false
	for key in ["confirmed_by", "confirmed_at", "acceptance"]:
		if not receipt.get(key) is String or receipt[key].is_empty():
			return false
	criteria.editable = false
	dialog.get_ok_button().disabled = true
	status.text = "v%d 已签认 · 确认人 %s · %s" % [version, receipt.confirmed_by, receipt.confirmed_at]
	criteria.text = receipt.acceptance
	return true


func _criteria_changed() -> void:
	if criteria.editable:
		var value := criteria.text.strip_edges()
		dialog.get_ok_button().disabled = value.is_empty() or value.length() > 8000


func _confirm() -> void:
	if not dialog.visible or dialog.get_ok_button().disabled:
		return
	var attempt := generation
	dialog.get_ok_button().disabled = true
	criteria.editable = false
	status.text = "正在确认 v%d…" % version
	var payload := {"acceptance": criteria.text.strip_edges()}
	var reply: Dictionary = await view.session.api_request(HTTPClient.METHOD_POST, _route(), payload)
	if attempt != generation:
		return
	var receipt: Variant = reply.data.get("signoff")
	if reply.status == 200 and receipt is Dictionary and receipt.get("confirmed_by") == view.session.get_identity().get("id") and receipt.get("acceptance") == payload.acceptance:
		if _show_receipt(receipt):
			return
	if reply.status in [0, 200] or reply.status >= 500:
		status.text = "回执待核对，请重试此次签认。"
		dialog.get_ok_button().text = "重试 v%d 签认" % version
		dialog.get_ok_button().disabled = false
	elif reply.status == 409:
		status.text = "此修订已有签认。请关闭并重开，核对确认人与验收条件。"
	else:
		status.text = "签认失败（%d），请核对账号权限和验收条件。" % reply.status
