extends RefCounted
## Configure only the private editor's existing model controls; never real credentials.


static func transcript(dock: Node) -> Array:
	var result := []
	for messages in dock.find_children("Messages", "", true, false):
		for label in messages.find_children("*", "RichTextLabel", true, false):
			result.append(label.get_parsed_text())
	return result


static func configure(tree: SceneTree) -> Dictionary:
	var dock := tree.root.find_child("AI Chat", true, false)
	if dock == null:
		return {}
	var backend = dock.find_child("AIBackend", true, false)
	backend.select(0)
	backend.item_selected.emit(0)
	var endpoint = dock.get_ai_settings_control().find_child("APIEndpoint", true, false)
	endpoint.text = OS.get_environment("TX_LOCAL_MODEL_ENDPOINT")
	endpoint.text_changed.emit(endpoint.text)
	var model = dock.find_child("APIModel", true, false)
	model.text = "native-local-fixture"
	model.text_changed.emit(model.text)
	if not dock.restore_ai_credential(OS.get_environment("TX_LOCAL_MODEL_KEY"), endpoint.text):
		return {}
	dock.refresh_model_catalog()
	var deadline := Time.get_ticks_msec() + 10000
	while Time.get_ticks_msec() < deadline and dock.get_model_catalog_snapshot().get("state") != "ready":
		await tree.create_timer(0.025).timeout
	if dock.get_model_catalog_snapshot().get("state") != "ready":
		return {}
	var input = dock.find_child("ChatInput", true, false)
	input.text = "普通 AIChat 的未发送中文草稿，天璇调用不得改动。"
	input.text_changed.emit()
	await tree.process_frame
	return {"dock": dock, "session": dock.get_ai_session_snapshot().duplicate(true), "transcript": transcript(dock), "draft": input.text}


static func unchanged(before: Dictionary) -> bool:
	var dock: Node = before.dock
	return dock.get_ai_session_snapshot() == before.session and transcript(dock) == before.transcript and dock.find_child("ChatInput", true, false).text == before.draft
