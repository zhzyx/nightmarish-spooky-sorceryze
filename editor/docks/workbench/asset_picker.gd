@tool
extends VBoxContainer

const CONTEXT := "/api/v1/native/asset-context/"
const MODULE_ASSETS := "/api/v1/native/business-modules/"

var host
var dialog: ConfirmationDialog
var form: VBoxContainer
var source: LineEdit
var revision: LineEdit
var path: LineEdit
var lookup: Button
var choices: OptionButton
var issue_assets: OptionButton
var notice: Label
var issue_button: Button
var origin_issue := ""
var origin_module := ""
var selected_asset := {}
var attempt := 0


func _ready() -> void:
	host = get_parent()
	var open := Button.new()
	open.name = "OpenStandaloneAsset"
	open.text = "打开多宝资产…"
	open.pressed.connect(_open.bind(false))
	add_child(open)
	issue_button = Button.new()
	issue_button.name = "OpenIssueAsset"
	issue_button.text = "从此工单打开资产…"
	issue_button.pressed.connect(_open.bind(true))
	host.content.add_child(issue_button)
	host.content.move_child(issue_button, 1)
	update_issue_button()
	dialog = ConfirmationDialog.new()
	dialog.name = "AssetOwnershipDialog"
	dialog.title = "资产归属"
	dialog.ok_button_text = "加入草稿"
	dialog.get_cancel_button().text = "取消"
	dialog.dialog_hide_on_ok = false
	dialog.confirmed.connect(_confirm)
	dialog.canceled.connect(_invalidate)
	dialog.visibility_changed.connect(_on_visibility)
	add_child(dialog)
	form = VBoxContainer.new()
	dialog.add_child(form)
	source = _field("AssetSource", "多宝来源模块")
	revision = _field("AssetRevision", "不可变版本")
	path = _field("AssetPath", "对象路径")
	lookup = Button.new()
	lookup.name = "LookupAsset"
	lookup.text = "查看现有归属"
	lookup.pressed.connect(_lookup)
	form.add_child(lookup)
	issue_assets = OptionButton.new()
	issue_assets.name = "IssueAssets"
	issue_assets.fit_to_longest_item = false
	issue_assets.item_selected.connect(_issue_asset_selected)
	form.add_child(issue_assets)
	choices = OptionButton.new()
	choices.name = "AssetOwner"
	choices.fit_to_longest_item = false
	choices.item_selected.connect(func(i): dialog.get_ok_button().disabled = i == 0)
	form.add_child(choices)
	notice = Label.new()
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	form.add_child(notice)


func _field(id: String, hint: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.name = id
	edit.placeholder_text = hint
	edit.text_changed.connect(func(_value): _invalidate())
	form.add_child(edit)
	return edit


func update_issue_button() -> void:
	issue_button.visible = host.location.get("issue_id") != null


func reset() -> void:
	attempt += 1
	dialog.hide()
	source.clear()
	revision.clear()
	path.clear()
	issue_assets.clear()
	_invalidate()
	update_issue_button()


func _on_visibility() -> void:
	if not dialog.visible:
		attempt += 1
		selected_asset.clear()


func _invalidate() -> void:
	attempt += 1
	selected_asset = {}
	choices.clear()
	choices.hide()
	notice.text = ""
	dialog.get_ok_button().disabled = true


func _open(from_issue: bool) -> void:
	if host.busy:
		return
	if not host._authenticated():
		host._notice("请先登录天璇。")
		return
	origin_issue = str(host.location.issue_id) if from_issue and host.location.get("issue_id") != null else ""
	origin_module = host.module_id if from_issue else ""
	if from_issue and origin_issue.is_empty():
		return
	_invalidate()
	for control in [source, revision, path, lookup]:
		control.visible = not from_issue
	issue_assets.visible = from_issue
	issue_assets.clear()
	issue_assets.add_item("选择工单所属模块的资产…")
	dialog.popup_centered(Vector2i(460, 240) * EditorInterface.get_editor_scale())
	if from_issue:
		var ticket := attempt
		var reply: Dictionary = await host._request(MODULE_ASSETS + origin_module.uri_encode() + "/assets")
		if ticket != attempt:
			return
		if not reply.get("assets") is Array:
			notice.text = "读取工单资产失败，请重新打开。"
			return
		for asset in reply.assets:
			issue_assets.add_item("%s · %s · %s" % [asset.path, asset.source_module, asset.revision.left(12)])
			issue_assets.set_item_metadata(issue_assets.item_count - 1, asset)
		if reply.assets.is_empty():
			notice.text = "此工单所属模块暂无可读资产。"


func _issue_asset_selected(index: int) -> void:
	_invalidate()
	if index > 0:
		await _resolve(issue_assets.get_item_metadata(index))


func _lookup() -> void:
	await open_standalone_asset({"source_module": source.text, "revision": revision.text, "path": path.text})


# A native asset view can forward its already opened immutable C03 object.
func open_standalone_asset(asset: Dictionary) -> void:
	if host.busy or not host._authenticated():
		return
	if not dialog.visible or not origin_issue.is_empty():
		_open(false)
	_invalidate()
	source.text = str(asset.get("source_module", "")).strip_edges()
	revision.text = str(asset.get("revision", "")).strip_edges()
	path.text = str(asset.get("path", ""))
	if source.text.is_empty() or revision.text.is_empty() or path.text.is_empty():
		notice.text = "请填写来源模块、版本和对象路径。"
		return
	await _resolve({"source_module": source.text, "revision": revision.text, "path": path.text})


func _context_url(asset: Dictionary) -> String:
	var segments := str(asset.path).split("/")
	for index in segments.size():
		segments[index] = segments[index].uri_encode()
	return CONTEXT + str(asset.source_module).uri_encode() + "/" + str(asset.revision).uri_encode() + "/" + "/".join(segments)


func _resolve(asset: Dictionary) -> void:
	var ticket := attempt
	var reply: Dictionary = await host._request(_context_url(asset))
	if attempt != ticket:
		return
	if not reply.get("modules") is Array:
		notice.text = "资产不存在或不可读取，请核对版本与权限。"
		return
	selected_asset = reply
	if not origin_issue.is_empty():
		if not reply.modules.any(func(owner): return owner.id == origin_module):
			notice.text = "此资产与工单的业务关系已变化。"
			return
		notice.text = "沿用当前工单及其模块，引用 " + str(reply.path)
		dialog.get_ok_button().disabled = false
		return
	choices.add_item("选择资产归属…")
	choices.add_item("仅作引用，保留当前会话")
	choices.set_item_metadata(1, "")
	for owner in reply.modules:
		choices.add_item("%s · %s" % [owner.name, owner.id])
		choices.set_item_metadata(choices.item_count - 1, owner.id)
	choices.show()
	if reply.modules.is_empty():
		choices.select(1)
		dialog.get_ok_button().disabled = false
		notice.text = "此资产尚无业务归属。"


func _confirm() -> void:
	if host.busy or selected_asset.is_empty() or dialog.get_ok_button().disabled:
		return
	var asset := selected_asset.duplicate(true)
	var target := origin_module
	if origin_issue.is_empty():
		target = str(choices.get_item_metadata(choices.selected))
	var ticket := attempt
	var generation: int = host.identity_generation
	host._lock(true)
	dialog.get_ok_button().disabled = true
	var fresh: Dictionary = await host._request(_context_url(asset))
	if ticket == attempt and generation == host.identity_generation:
		var valid: bool = fresh.get("asset_id") == asset.asset_id and fresh.get("sha256") == asset.sha256
		if valid and not target.is_empty():
			valid = fresh.modules.any(func(owner): return owner.id == target)
		if valid and not origin_issue.is_empty():
			var issue: Dictionary = await host._request("/api/v1/issues/" + origin_issue.uri_encode())
			valid = (
				issue.get("id") == origin_issue and issue.get("project") == host.project
				and issue.get("module_id") == target and host.location.get("issue_id") == origin_issue
			)
		if ticket == attempt and generation == host.identity_generation:
			if valid:
				# Confirmation commits the choice. Earlier dismissal invalidates every outstanding read.
				dialog.hide()
				var located := true
				if not target.is_empty() and origin_issue.is_empty():
					located = await host.select_asset_module(target, fresh.modules)
				if located and generation == host.identity_generation and (target.is_empty() or host.module_id == target):
					host.stage_asset_reference(asset)
			else:
				_invalidate()
				notice.text = "资产或工单归属已变化，请重新选择。"
	if generation == host.identity_generation:
		host._lock(false)
