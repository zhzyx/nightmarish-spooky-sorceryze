@tool
extends Node
## The two Views observe this controller. Page/cache state survives dock reparenting.

signal changed(topic: String)
signal navigation_requested(page: String, object_id: String)

var session: Node
var language := "zh"
var documents: Node
var editor_context: Node
var issues: Node
var repositories: Node
var repository_collaboration: Node
var game_config: Node
var migration: Node
var accounts: Node
var execution: Node
var local_chat: Node
var editor_module := ""
var storage_root := ""
var cache := {}
var errors := {}
var active_conversation := ""
var _pending := {}
var _serial := 0
var _drafts := {}
var _generation := 0
const CONVERSATIONS := "/api/v1/workspace/conversations"
const DESIGN_STAGES := ["direction", "plan", "design"]


func _ready() -> void:
	session = get_meta("session_controller")
	set_translation_domain(&"tianxuan-native")
	session.set_translation_domain(&"tianxuan-native")
	if has_meta("locale_script"):
		get_meta("locale_script").install()
		var settings := EditorInterface.get_editor_settings()
		var selected := str(settings.get_setting("interface/tianxuan/language")) if settings.has_setting("interface/tianxuan/language") else "zh"
		set_language(selected, false)
	session.identity_resetting.connect(_before_identity_change)
	session.identity_changed.connect(_identity_changed)
	if has_meta("local_conversation_script"):
		local_chat = get_meta("local_conversation_script").new()
		local_chat.set_meta("workspace", self)
		add_child(local_chat)
	_identity_changed()
	if has_meta("document_script"):
		documents = get_meta("document_script").new()
		documents.set_meta("workspace", self)
		add_child(documents)
	if has_meta("editor_script"):
		editor_context = get_meta("editor_script").new()
		editor_context.set_meta("workspace", self)
		add_child(editor_context)
	if has_meta("issue_script"):
		issues = get_meta("issue_script").new()
		issues.set_meta("workspace", self)
		add_child(issues)
	if has_meta("repository_script"):
		repositories = get_meta("repository_script").new()
		repositories.set_meta("workspace", self)
		add_child(repositories)
	if has_meta("repository_collaboration_script"):
		repository_collaboration = get_meta("repository_collaboration_script").new()
		repository_collaboration.set_meta("workspace", self)
		add_child(repository_collaboration)
	if has_meta("game_config_script"):
		game_config = get_meta("game_config_script").new()
		game_config.set_meta("workspace", self)
		add_child(game_config)
	if has_meta("migration_script"):
		migration = get_meta("migration_script").new()
		migration.set_meta("workspace", self)
		add_child(migration)
	if has_meta("accounts_script"):
		accounts = get_meta("accounts_script").new()
		accounts.set_meta("workspace", self)
		add_child(accounts)
	if has_meta("execution_script"):
		execution = get_meta("execution_script").new()
		execution.set_meta("workspace", self)
		add_child(execution)


func set_language(value: String, persist := true) -> void:
	if value not in ["zh", "en"]:
		return
	language = value
	if has_meta("locale_script"):
		get_meta("locale_script").configure(language)
	if persist and Engine.is_editor_hint():
		EditorInterface.get_editor_settings().set_setting("interface/tianxuan/language", language)
	changed.emit("language")


func _before_identity_change() -> void:
	# Views save edits synchronously while the old identity is still available.
	changed.emit("identity_resetting")
	if local_chat:
		local_chat.reset()


func _identity_changed() -> void:
	_generation += 1
	cache.clear()
	errors.clear()
	_pending.clear()
	_drafts.clear()
	active_conversation = ""
	editor_module = ""
	changed.emit("identity")


func identity() -> Dictionary:
	return session.get_identity()


func can_edit() -> bool:
	return identity().get("role", "viewer") != "viewer"


func busy(key: String) -> bool:
	return _pending.has(key)


func read(key: String, route: String) -> Dictionary:
	if busy(key):
		return {"status": 0, "data": {}, "pending": true}
	return await _request(key, HTTPClient.METHOD_GET, route, {})


func write(key: String, method: int, route: String, payload: Dictionary) -> Dictionary:
	if busy(key):
		return {"status": 0, "data": {}, "pending": true}
	return await _request(key, method, route, payload)


func _request(key: String, method: int, route: String, payload: Dictionary) -> Dictionary:
	_serial += 1
	var serial := _serial
	var attempt := _generation
	_pending[key] = serial
	errors.erase(key)
	changed.emit(key)
	var result: Dictionary = await session.api_request(method, route, payload)
	if attempt != _generation:
		return {"status": 0, "data": {}, "stale": true}
	if _pending.get(key) != serial:
		return {"status": 0, "data": {}, "stale": true}
	_pending.erase(key)
	if result.status >= 200 and result.status < 300:
		cache[key] = result.data.duplicate(true)
	else:
		errors[key] = error_message(result.status, method != HTTPClient.METHOD_GET)
	changed.emit(key)
	return result


static func error_message(status: int, writing := false) -> String:
	match status:
		0:
			return "连接中断，写入结果待核对。请先刷新确认，草稿已保留。" if writing else "暂时无法连接服务，请检查网络后重试。"
		401:
			return "登录已失效，请重新登录。"
		403:
			return "当前账号没有此操作的权限。"
		404:
			return "内容不存在，或此服务未启用该能力。"
		409, 412:
			return "服务器内容已更新，请比较最新版本后保存。"
		400, 422:
			return "内容未通过校验，请检查必填字段及输入格式。"
		413:
			return "提交内容超过服务允许的大小，请缩小文件或内容后重试。"
		429:
			return "请求过于频繁，请稍后重试。"
		_:
			return TranslationServer.get_or_add_domain(&"tianxuan-native").translate("服务暂时无法完成操作（%d），草稿已保留。") % status


func navigate(page: String, object_id := "") -> void:
	if page == "documents" and documents and not object_id.is_empty():
		documents.open(object_id)
	if page == "issues" and issues and not object_id.is_empty():
		issues.open(object_id)
	if page == "repos" and repositories and not object_id.is_empty():
		repositories.select("git", object_id)
	if page == "execution" and execution and not object_id.is_empty():
		execution.select(object_id)
	if page == "repository_collaboration" and repository_collaboration and object_id.count("/") == 1:
		repository_collaboration.select(object_id.get_slice("/", 0), object_id.get_slice("/", 1))
	navigation_requested.emit(page, object_id)


func _draft_path(key: String) -> String:
	var scope: String = session.scope_key()
	if scope.is_empty() or storage_root.is_empty():
		return ""
	return storage_root.path_join(scope).path_join(key.sha256_text() + ".json")


func save_draft(key: String, value: Dictionary) -> bool:
	var path := _draft_path(key)
	if path.is_empty():
		return false
	_drafts[key] = value.duplicate(true)
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK:
		return false
	var temporary := path + "." + Crypto.new().generate_random_bytes(8).hex_encode() + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if not file:
		return false
	var stored := file.store_string(JSON.stringify(value))
	file.flush()
	var error := file.get_error()
	file.close()
	if stored and error == OK and DirAccess.rename_absolute(temporary, path) == OK:
		changed.emit("draft:" + key)
		return true
	DirAccess.remove_absolute(temporary)
	return false


func load_draft(key: String) -> Dictionary:
	if _drafts.has(key):
		return _drafts[key].duplicate(true)
	var path := _draft_path(key)
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if value is Dictionary:
		_drafts[key] = value
		return value.duplicate(true)
	return {}


func clear_draft(key: String) -> bool:
	var path := _draft_path(key)
	if not path.is_empty() and FileAccess.file_exists(path) and DirAccess.remove_absolute(path) != OK:
		return false
	_drafts.erase(key)
	changed.emit("draft:" + key)
	return true


static func new_id() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var value := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [value.substr(0, 8), value.substr(8, 4), value.substr(12, 4), value.substr(16, 4), value.substr(20, 12)]


func conversation() -> Dictionary:
	var remote: Dictionary = cache.get("conversation:" + active_conversation, {}).duplicate(true)
	return local_chat.overlay(active_conversation, remote) if local_chat else remote


func chat_draft_key(id: String) -> String:
	return "chat:" + ("new" if id.is_empty() else id)


func chat_busy() -> bool:
	return (local_chat and local_chat.busy()) or busy("conversation:create") or busy("conversation:" + active_conversation)


func refresh_conversations(more := false) -> void:
	var previous: Dictionary = cache.get("conversations", {})
	var route := CONVERSATIONS
	if more:
		if not previous.get("next") is String or previous.next.is_empty():
			return
		route += "?before=" + str(previous.next).uri_encode()
	var result := await read("conversations", route)
	if more and result.status == 200:
		var combined: Array = previous.get("conversations", []).duplicate(true)
		var known := {}
		for item in combined:
			known[item.id] = true
		for item in result.data.get("conversations", []):
			if not known.has(item.id):
				combined.append(item)
		cache.conversations.conversations = combined
		changed.emit("conversations")

	if local_chat:
		var listing: Dictionary = cache.get("conversations", {"conversations": [], "next": null})
		listing.conversations = local_chat.summaries(listing.get("conversations", []))
		cache.conversations = listing
		changed.emit("conversations")


func select_conversation(id: String) -> void:
	if chat_busy():
		return
	active_conversation = id
	if local_chat:
		local_chat._publish(id)
	changed.emit("conversation_selection")
	if not id.is_empty():
		await refresh_conversation(id)


func refresh_conversation(id: String) -> void:
	var result := await read("conversation:" + id, CONVERSATIONS + "/" + id.uri_encode())
	if result.status == 200:
		var draft := load_draft(chat_draft_key(id))
		var pending_id: String = draft.get("pending_id", "")
		if not pending_id.is_empty():
			for turn in result.data.get("turns", []):
				if turn.id == pending_id:
					clear_draft(chat_draft_key(id))
					break

	if local_chat:
		if result.status == 200:
			local_chat.observe(id, result.data)
		local_chat._publish(id)
		local_chat.sync(id)


func send_message(text: String, references: Dictionary = {}, _source_text := "") -> void:
	if not can_edit() or chat_busy() or text.strip_edges().is_empty():
		return
	if text.length() > 8000:
		errors.chat = "消息最多 8000 个字符，请缩短内容后发送。"
		changed.emit("chat")
		return
	if not local_chat:
		errors.chat = "本机模型入口尚未准备完成。"
		changed.emit("chat")
		return
	local_chat.send(text, references)


func retry_pending_message() -> void:
	# Reconcile historical cloud requests; never submit them for remote inference.
	var id := active_conversation
	if id.is_empty() or chat_busy():
		return
	var epoch := _generation
	var result := await read("conversation:" + id, CONVERSATIONS + "/" + id.uri_encode())
	if epoch != _generation or result.status not in [200, 404]:
		return
	var draft := load_draft(chat_draft_key(id))
	var pending_id: String = draft.get("pending_id", "")
	if pending_id.is_empty():
		return
	for turn in result.data.get("turns", []):
		if turn.id == pending_id:
			clear_draft(chat_draft_key(id))
			changed.emit("chat")
			return
	# A definitive read found no old submission. Preserve the text for an explicit
	# local send; neither polling nor retry reissues a cloud model request.
	draft.erase("pending_id")
	draft.erase("pending_payload")
	save_draft(chat_draft_key(id), draft)
	changed.emit("chat")


func stop_waiting() -> void:
	if local_chat and local_chat.busy():
		local_chat.cancel()
		return
	var current := conversation()
	if current.is_empty() or chat_busy():
		return
	for turn in current.get("turns", []):
		if turn.get("state") == "pending":
			await write("conversation:" + current.id, HTTPClient.METHOD_POST, CONVERSATIONS + "/" + str(current.id).uri_encode() + "/turns/" + str(turn.id).uri_encode() + "/stop-waiting", {"expected_version": current.version})
			return


func design_revision(stage: String) -> Dictionary:
	var current := conversation()
	var number: int = current.get("current", {}).get(stage, -1)
	for revision in current.get("revisions", []):
		if int(revision.revision) == number:
			return revision.duplicate(true)
	return {}


func design_key(stage: String) -> String:
	return "design:" + active_conversation + ":" + stage


func design_open(stage: String) -> bool:
	var current := conversation()
	if not can_edit() or current.is_empty() or current.get("requirement_id") != null or stage not in DESIGN_STAGES:
		return false
	for previous in DESIGN_STAGES.slice(0, DESIGN_STAGES.find(stage)):
		if design_revision(previous).get("confirmed_at") == null:
			return false
	return true


func update_design_draft(stage: String, body: String, title: String, acceptance: String) -> void:
	if not design_open(stage) or chat_busy():
		return
	var local := load_draft(design_key(stage))
	if local.is_empty():
		local.based_on = design_revision(stage).get("revision", 0)
	local.body = body
	local.title = title
	local.acceptance = acceptance
	if not save_draft(design_key(stage), local):
		errors.design = "无法保存本机设计草稿，请先复制内容。"
		changed.emit("design")


func save_design(stage: String) -> void:
	var local := load_draft(design_key(stage))
	if not design_open(stage) or local.is_empty():
		return
	if local.get("based_on", 0) != design_revision(stage).get("revision", 0):
		errors.design = "该阶段已有新修订。请先比较并采用已保存版本，草稿仍保留。"
		changed.emit("design")
		return
	var payload := {"body": local.get("body", "")}
	if stage == "design":
		payload.title = local.get("title", "")
		payload.acceptance = local.get("acceptance", "")
	var key := design_key(stage)
	var attempt := _generation
	var result := await change_conversation("/design/" + stage + "/drafts", payload)
	if attempt == _generation and result.status == 200:
		clear_draft(key)


func change_conversation(suffix: String, fields: Dictionary) -> Dictionary:
	var current := conversation()
	if current.is_empty() or chat_busy() or not can_edit():
		return {"status": 0, "data": {}}
	var attempt := _generation
	var id: String = current.id
	var payload := fields.duplicate(true)
	payload.expected_version = current.version
	var result := await write("conversation:" + id, HTTPClient.METHOD_POST, CONVERSATIONS + "/" + id.uri_encode() + suffix, payload)
	if attempt == _generation and result.status != 200:
		var failure := error_message(result.status, true)
		await refresh_conversation(id)
		if attempt == _generation:
			errors.design = failure
			changed.emit("design")
	elif attempt == _generation:
		errors.erase("design")
		changed.emit("design")
	return result


func suggest_design(stage: String) -> void:
	if not design_open(stage) or chat_busy():
		return
	if local_chat:
		local_chat.suggest(stage)
	else:
		errors.design = "本机模型入口尚未准备完成。"
		changed.emit("design")


func load_execution() -> void:
	var current := conversation()
	if current.get("requirement_id") == null:
		return
	var id: String = current.id
	read("requirement-review:" + id, CONVERSATIONS + "/" + id.uri_encode() + "/requirement-review")
	var execution: Variant = current.get("execution")
	if execution is Dictionary:
		read("execution:" + str(execution.entry), "/api/v1/native/entry/" + str(execution.entry).uri_encode())
	else:
		read("execution-capabilities", "/api/v1/native/entry/capabilities")


func load_library(kind: String, more := false, query := "", filter := "all") -> void:
	if kind not in ["requirements", "runs", "search"] or busy("library:" + kind):
		return
	var attempt := _generation
	var key := "library:" + kind
	_pending[key] = true
	errors.erase(key)
	changed.emit(key)
	if kind == "search":
		var rows := []
		var failures := PackedStringArray()
		for scope in ["docs", "requirements", "issues", "repos"]:
			if filter != "all" and filter != scope:
				continue
			var route: String = {"docs": "/api/v1/search?q=" + query.uri_encode() + "&limit=100", "requirements": "/api/v1/docs?kind=requirement", "issues": "/api/v1/issues", "repos": "/api/v1/repos"}[scope]
			var response: Dictionary = await read("library-source:" + scope, route)
			if attempt != _generation:
				return
			if response.status == 404 and scope == "repos":
				continue
			if response.status != 200:
				failures.append({"docs": "文档", "requirements": "需求", "issues": "工单", "repos": "仓库"}[scope])
				continue
			var list: Array = response.data.get({"docs": "results", "requirements": "docs", "issues": "issues", "repos": "repos"}[scope], [])
			for item in list:
				var title := str(item.get("title", item.get("full_name", item.get("id", ""))))
				var searchable := title + " " + str(item.get("number", "")) + " " + str(item.get("status", ""))
				if scope != "docs" and not searchable.to_lower().contains(query.to_lower()):
					continue
				rows.append({"id": title if scope == "repos" else item.get("id", title), "title": title, "kind": {"docs": "文档", "requirements": "需求", "issues": "工单", "repos": "仓库"}[scope], "subtitle": item.get("snippet", item.get("status", item.get("default_branch", ""))), "target": "documents" if scope in ["docs", "requirements"] else "repository_collaboration" if scope == "repos" else scope})
		cache[key] = {"items": rows, "query": query, "filter": filter}
		if not failures.is_empty():
			errors[key] = tr("以下范围暂时无法读取：") + "、".join(failures)
	else:
		var previous: Dictionary = cache.get(key, {})
		var route := "/api/v1/docs?kind=requirement" if kind == "requirements" else "/api/v1/workspace/runs"
		if more and previous.get("next_cursor") is String:
			route += "/after/" + str(previous.next_cursor).uri_encode()
		var response: Dictionary = await read("library-source:" + kind, route)
		if attempt != _generation:
			return
		if response.status == 200:
			var items: Array = response.data.get("docs" if kind == "requirements" else "runs", []).duplicate(true)
			if kind == "requirements":
				for item in items:
					var detail: Dictionary = await read("library-requirement:" + str(item.id), "/api/v1/docs/" + str(item.id).uri_encode())
					if attempt != _generation:
						return
					if detail.status == 200:
						item.progress = detail.data.get("progress")
						item.request_id = detail.data.get("request_id")
					else:
						item.progress_error = error_message(detail.status)
			if more:
				items = previous.get("items", []) + items
			cache[key] = {"items": items, "available": response.data.get("available", true), "next_cursor": response.data.get("next_cursor")}
		else:
			errors[key] = error_message(response.status)
	_pending.erase(key)
	changed.emit(key)
