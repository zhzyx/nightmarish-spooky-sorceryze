extends SceneTree

var checks: Array[String] = []
var delayed_result := {}


func _initialize() -> void:
	run.call_deferred()


func check(value: bool, description: String) -> bool:
	if not value:
		push_error("Tianxuan controller: " + description)
		quit(1)
		return false
	checks.append(description)
	return true


func load_source(relative: String) -> GDScript:
	var script := GDScript.new()
	script.source_code = FileAccess.get_file_as_string(OS.get_environment("TX_SOURCE").path_join(relative))
	if script.reload() != OK:
		return null
	return script


func delayed_read(session: Node) -> void:
	delayed_result = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/native-test/delayed")


func wait_until(predicate: Callable, seconds := 6.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	return predicate.call()


func run() -> void:
	var script := load_source("editor/docks/tianxuan/session_controller.gd")
	if not check(script != null, "shared session source compiles"):
		return
	var workspace_script := load_source("editor/docks/tianxuan/workspace_controller.gd")
	var theme_script := load_source("editor/docks/tianxuan/native_theme.gd")
	var legacy_script := load_source("editor/docks/workbench/business_session.gd")
	if not check(workspace_script != null and theme_script != null and legacy_script != null, "native controller, visual tokens and compatibility View compile"):
		return
	for source in ["workspace_view.gd", "home_page.gd", "markdown_view.gd", "document_controller.gd", "documents_page.gd", "design_page.gd", "editor_controller.gd", "library_page.gd", "issue_controller.gd", "issues_page.gd", "issue_assets.gd", "issue_flow.gd", "asset_decoder.gd", "repositories_controller.gd", "repositories_page.gd", "repository_collaboration_controller.gd", "repository_collaboration_page.gd", "game_config_controller.gd", "game_config_page.gd", "migration_controller.gd", "migration_page.gd", "accounts_controller.gd", "accounts_page.gd", "execution_controller.gd", "execution_page.gd"]:
		if not check(load_source("editor/docks/tianxuan/" + source) != null, "compile native View " + source):
			return
	var markdown = load_source("editor/docks/tianxuan/markdown_view.gd").new()
	root.add_child(markdown)
	markdown.set_markdown("# 原生标题\n\n| 名称 | 数量 |\n| :--- | ---: |\n| **资源** | 2 |\n\n1. 首项\n  - [X] 嵌套完成\n\n> 引用\n\n```gdscript\n[url=javascript:bad]原样代码[/url]\n```\n\n*斜体* 与 ~~删除~~")
	var rendered: String = markdown.get_parsed_text()
	if not check("资源" in rendered and "2" in rendered and not "| :---" in rendered and not "**资源**" in rendered and "☑" in rendered, "native Markdown renders tables, ordered lists and nested completed tasks"):
		return
	if not check("[url=javascript:bad]原样代码[/url]" in rendered and not "~~删除~~" in rendered and not "*斜体*" in rendered, "native Markdown preserves literal code without interpreting BBCode while rendering emphasis"):
		return
	markdown.select_all()
	var selected_markdown: String = markdown.get_selected_text()
	markdown.set_markdown(markdown._markdown)
	if not check(markdown.get_selected_text() == selected_markdown, "unchanged native Markdown refresh preserves the reader's text selection"):
		return
	markdown.free()
	var session = script.new()
	session.origin = OS.get_environment("TX_API")
	root.add_child(session)
	if not check(not session.valid_origin("http://example.com") and not session.valid_origin("https://user:secret@example.com") and not session.valid_origin("https://example.com/other"), "reject cleartext remote, URL credentials and non-origin addresses"):
		return
	var config: Dictionary = await session.auth_config()
	if not check(config.status == 200 and config.data.mode == "accounts", "read actual deployment login mode"):
		return
	var workspace = workspace_script.new()
	workspace.set_meta("session_controller", session)
	workspace.set_meta("asset_decoder_script", load_source("editor/docks/tianxuan/asset_decoder.gd"))
	workspace.storage_root = OS.get_environment("TX_DRAFTS")
	root.add_child(workspace)
	var signed_in: bool = await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "studio/game")
	if not check(signed_in and session.get_identity().role == "admin", "real account authentication and role"):
		return
	var actor_a: String = session.get_identity().id
	var inventory: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/workspace/runs")
	if not check(inventory.status == 200 and inventory.data.available == false, "native inventory receives its exact query-free contract"):
		return
	var substituted: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/docs?project=another")
	if not check(substituted.status == 0, "callers cannot substitute the verified project query"):
		return
	var identity: Dictionary = session.get_identity()
	identity.role = "viewer"
	if not check(session.get_identity().role == "admin", "View receives a detached identity snapshot"):
		return
	if not check(workspace.save_draft("document:one", {"base_version": 1, "body": "离线草稿与选区"}), "atomic private draft persistence"):
		return
	var main_view := VBoxContainer.new()
	var sidebar_view := VBoxContainer.new()
	root.add_child(main_view)
	root.add_child(sidebar_view)
	delayed_read(session)
	main_view.free()
	await create_timer(0.3).timeout
	if not check(delayed_result.get("status") == 200 and delayed_result.data.actor == actor_a, "closing a View leaves in-flight transport alive"):
		return
	delayed_result.clear()
	delayed_read(session)
	var as_viewer: bool = await session.authenticate("", OS.get_environment("TX_VIEWER_KEY"), "studio/game")
	if not check(as_viewer and session.get_identity().role == "viewer", "personal key uses verified server identity"):
		return
	var second_device = script.new()
	second_device.origin = session.origin
	root.add_child(second_device)
	if not check(await second_device.authenticate("", OS.get_environment("TX_VIEWER_KEY"), "studio/game"), "same account key signs in on a second device"):
		return
	if not check(second_device.get_identity().id == session.get_identity().id and second_device.get_identity().device_id != session.get_identity().device_id and second_device.get_identity().credential_id != session.get_identity().credential_id, "server separates device and authorization identifiers for the same account"):
		return
	second_device.reset()
	var still_signed_in: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/auth/me")
	if not check(still_signed_in.status == 200, "logging out another device preserves the first device session"):
		return
	second_device.queue_free()
	await create_timer(0.3).timeout
	if not check(delayed_result.get("stale", false) and delayed_result.data.is_empty(), "old identity response cannot cross account switch"):
		return
	if not check(workspace.load_draft("document:one").is_empty() and workspace.cache.is_empty(), "different accounts cannot read each other's private draft or cache"):
		return
	var denied: Dictionary = await workspace.write("create", HTTPClient.METHOD_POST, "/api/v1/docs", {"title": "Forbidden", "body_md": "blocked"})
	if not check(denied.status == 403 and not session.get_identity().is_empty(), "viewer write is denied by existing service permissions"):
		return
	await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "studio/game")
	if not check(workspace.load_draft("document:one").get("body") == "离线草稿与选区", "returning account restores exact draft"):
		return
	var doc_script := load_source("editor/docks/tianxuan/document_controller.gd")
	var docs = doc_script.new()
	docs.set_meta("workspace", workspace)
	workspace.add_child(docs)
	docs.update_draft("原生设计", "第一段\n\n第二段")
	await docs.save()
	if not check(not docs.active_id.is_empty() and docs.document.version == 1 and docs.draft().is_empty(), "native document creates through the existing service and clears only acknowledged draft"):
		return
	docs.update_draft("原生设计", "本机修改第一段\n\n第二段")
	var remote: Dictionary = await session.api_request(HTTPClient.METHOD_PATCH, docs.route(), {"body_md": "他人修改第一段\n\n第二段", "expected_version": 1})
	if not check(remote.status == 200, "collaborator advances the actual document"):
		return
	await docs.save()
	if not check(not docs.conflict.is_empty() and docs.draft().body_md.begins_with("本机"), "conflicting collaborator edits retain both native draft and remote revision"):
		return
	docs.resolve_conflict()
	await docs.save()
	if not check(docs.document.version == 3 and docs.document.body_md.begins_with("本机"), "explicit conflict resolution saves against the reviewed remote version"):
		return
	docs.update_draft("原生设计", "本机修改第一段\n\n本机修改第二段")
	await session.api_request(HTTPClient.METHOD_PATCH, docs.route(), {"body_md": "他人再次修改第一段\n\n第二段", "expected_version": 3})
	await docs.save()
	if not check(docs.conflict.is_empty() and "他人再次修改第一段" in docs.draft().body_md and "本机修改第二段" in docs.draft().body_md, "disjoint edits merge into a reviewable draft without losing either contributor"):
		return
	await docs.save()
	if not check(docs.document.version == 5, "reviewed merged document is saved once"):
		return
	docs.set_process(false)
	var replay := {"title": "原生设计", "body_md": "回执重放校验", "expected_version": 5, "call_id": workspace.new_id()}
	await session.api_request(HTTPClient.METHOD_PATCH, docs.route(), replay)
	workspace.save_draft(docs.draft_key(), {"title": replay.title, "body_md": replay.body_md, "base_version": 5, "base_title": replay.title, "base_md": docs.document.body_md, "submission": replay})
	await docs._sync_submission()
	if not check(docs.document.version == 6 and docs.draft().is_empty(), "lost save acknowledgement replays the original receipt without adding another revision"):
		return
	await docs.load_details("versions")
	await docs.compare_versions(1, 6)
	if not check(docs.detail.versions.versions.size() == 6 and "回执重放校验" in docs.detail.diff, "native history and diff read the same six server revisions"):
		return
	var comment: Dictionary = await docs.action(HTTPClient.METHOD_POST, "/comments", {"body": "请检查边界条件"})
	if not check(comment.status == 200, "native comment uses shared document permissions"):
		return
	await docs.resolve_comment(comment.data.id, true)
	await docs.export_file("md", OS.get_environment("TX_DRAFTS").path_join("export.md"))
	if not check(FileAccess.get_file_as_string(OS.get_environment("TX_DRAFTS").path_join("export.md")) == "回执重放校验", "authenticated native export matches the saved document"):
		return
	var native_theme: Theme = theme_script.build(Theme.new(), 1.5, true)
	if not check(native_theme.get_font_size("font_size", "TianxuanTitle") == 41 and native_theme.get_stylebox("panel", "TianxuanCard") is StyleBoxFlat, "native typography and surfaces scale together"):
		return
	await session.authenticate("first@example.invalid", OS.get_environment("TX_PASSWORD"), "workspace")
	var issue_script := load_source("editor/docks/tianxuan/issue_controller.gd")
	var issues = issue_script.new()
	issues.set_meta("workspace", workspace)
	workspace.add_child(issues)
	await issues.load_catalog()
	issues.edit("create", {"title": "原生工单契约", "module_id": OS.get_environment("TX_MODULE"), "type": "task", "body_md": "明确实现", "acceptance": "提供证据"})
	await issues.create()
	if not check(not issues.selected.is_empty() and issues.detail.title == "原生工单契约" and issues.detail.project == "workspace", "native issue creation persists in the selected project and reads its authoritative detail"):
		return
	issues.edit("classification", {"type": "feature", "labels": ["native-ui", "验收"]})
	await issues.submit("classification")
	if not check(issues.detail.type == "feature" and "native-ui" in issues.detail.labels, "native issue classification round trips existing labels and optimistic expectations"):
		return
	issues.edit("definition", {"key": "release", "label": "发布批次"})
	await issues.define_field()
	await issues.load_catalog()
	issues.edit("field", {"key": "release", "value": "原生界面首轮"})
	await issues.submit("field")
	if not check(issues.sections.work.plan.custom_fields.release == "原生界面首轮", "native custom field preserves its server-defined key and text value"):
		return
	issues.edit("plan", {"iteration": "第一迭代", "milestone": "原生界面", "estimated_minutes": 90})
	var concurrent: Dictionary = await session.api_request(HTTPClient.METHOD_POST, issues.route("/work/plan"), {"expected_version": int(issues.sections.work.version), "plan": {"milestone": "服务器里程碑"}, "call_id": workspace.new_id()})
	await issues.submit("plan")
	if not check(concurrent.status == 200 and issues.draft_outdated("plan") and issues.draft("plan").values.milestone == "原生界面" and issues.sections.work.plan.milestone == "服务器里程碑", "concurrent issue plan changes retain local and remote values for comparison"):
		return
	issues.review_draft("plan")
	await issues.submit("plan")
	if not check(issues.sections.work.plan.estimated_minutes == 90 and issues.draft("plan").is_empty(), "explicitly reviewed issue plan saves against the new server version"):
		return
	var log_payload := {"expected_version": int(issues.sections.work.version), "minutes": 25, "note": "实现原生工单", "call_id": workspace.new_id()}
	await session.api_request(HTTPClient.METHOD_POST, issues.route("/work/log"), log_payload)
	workspace.save_draft(issues.draft_key("pending"), {"section": "log", "method": HTTPClient.METHOD_POST, "url": issues.route("/work/log"), "payload": log_payload, "replayable": true})
	workspace._drafts.erase(issues.draft_key("pending"))
	await issues.retry()
	if not check(issues.sections.work.logged_minutes == 25 and issues.sections.work.logs.size() == 1 and issues.pending().is_empty(), "lost issue time acknowledgement replays its exact request without duplicate work logs"):
		return
	var flow_values: Dictionary = issues.flow_values()
	flow_values.stages.append({"id": "native-review", "progress": 80, "human": true})
	flow_values.edges.append({"from": "native-review", "to": "in-review"})
	flow_values.edges.append({"from": "in-progress", "to": "native-review"})
	issues.edit("flow", flow_values)
	var remote_flow: Dictionary = issues.sections.flow.duplicate(true)
	remote_flow.stages[0].progress = 1
	var flow_changed: Dictionary = await session.api_request(HTTPClient.METHOD_POST, issues.route("/work/flow/configure"), {"stages": remote_flow.stages, "edges": remote_flow.edges, "expected_version": int(remote_flow.version), "call_id": workspace.new_id()})
	await issues.submit("flow")
	if not check(flow_changed.status == 200 and issues.draft_outdated("flow") and issues.flow_values().stages.size() > issues.sections.flow.stages.size(), "concurrent flow edits retain the local stages and the latest server configuration"):
		return
	issues.review_draft("flow")
	await issues.submit("flow")
	if not check(issues.sections.flow.configured and issues.draft("flow").is_empty() and issues.sections.flow.stages.any(func(stage: Dictionary): return stage.id == "native-review" and stage.human), "reviewed native flow saves typed stages, human decisions and routes against the current version"):
		return
	flow_values = issues.flow_values()
	flow_values.edges.append(flow_values.edges[0])
	if not check(not issues.flow_error(flow_values).is_empty(), "native flow validation rejects duplicate routes before submission"):
		return
	issues.edit("comment", {"body": "原生实现与回归证据已核对", "parent_id": null})
	await issues.submit("comment")
	if not check(issues.sections.comments.comments.size() == 1, "native issue comment creates a durable evidence record"):
		return
	for stage in ["planned", "in-progress", "in-review"]:
		await issues.action("advance", {"to_status": stage}, issues.action_snapshot())
		if not check(issues.detail.status == stage, "native issue follows the server workflow transition to " + stage):
			return
	var evidence: String = issues.sections.comments.comments[0].id
	await issues.action("accept", {"comment": evidence}, issues.action_snapshot())
	if not check(issues.sections.lifecycle.accepted == evidence, "native acceptance binds the current issue revision to its existing evidence comment"):
		return
	await issues.action("close", {}, issues.action_snapshot())
	if not check(issues.detail.status == "done", "native close uses the acknowledged lifecycle revision"):
		return
	await issues.action("reopen", {}, issues.action_snapshot())
	if not check(issues.detail.status != "done", "native reopen follows the authority's recorded previous stage"):
		return
	await issues.upload_artifact(OS.get_environment("TX_IMPORT_SOURCE"))
	if not check(issues.sections.artifacts.artifacts.size() == 1, "native attachment uploads into immutable native storage and binds to the real issue"):
		return
	await issues.upload_artifact(OS.get_environment("TX_IMPORT_SOURCE"))
	if not check(issues.sections.artifacts.artifacts.size() == 1, "repeating the same native attachment preserves one immutable issue binding"):
		return
	await issues.inspect_artifact(issues.sections.artifacts.artifacts[0])
	var artifact_version := str(issues.sections.artifacts.artifacts[0].version)
	if not check(issues.previews[artifact_version].get("text", "") == FileAccess.get_file_as_string(OS.get_environment("TX_IMPORT_SOURCE")), "native attachment preview verifies the digest and preserves exact UTF-8 content"):
		return
	var candidate_module := "native-issue-concept-fixture"
	var candidate: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches", {"request_key": workspace.new_id(), "changes": [{"module": candidate_module, "base": null, "reads": null, "edits": {"concept.txt": Marshalls.raw_to_base64("第一版创意原件".to_utf8_buffer())}}]})
	if not check(candidate.status == 200, "creative fixture is a real immutable native revision"):
		return
	var submitted_asset: Dictionary = await session.api_request(HTTPClient.METHOD_POST, issues.route("/work/submit_asset"), {"kind": "concept", "module": candidate_module, "revision": candidate.data.revisions[candidate_module], "path": "concept.txt", "expected_version": int(issues.sections.work.version), "call_id": workspace.new_id()})
	await issues.refresh()
	if not check(submitted_asset.status == 200 and issues.sections.work.creative_judgments.size() == 1, "creative source is bound to its actual issue submission and responsible user"):
		return
	var original: Dictionary = issues.sections.artifacts.artifacts[0]
	await issues.inspect_artifact(original)
	await issues.edit_artifact(original, "第二版创意原件", issues.action_snapshot())
	if not check(issues.sections.work.creative_judgments.size() == 2 and issues.sections.work.creative_judgments[0].decision == "superseded", "editing a creative original preserves the old submission and creates a new pending candidate"):
		return
	var revised: Dictionary = issues.sections.artifacts.artifacts[0]
	await issues.inspect_artifact(revised)
	if not check(issues.previews[str(revised.version)].text == "第二版创意原件", "revised native candidate reads back the exact edited original"):
		return
	await issues.judge_artifact(original, "approved", "不能采纳已替代候选", "", issues.action_snapshot())
	if not check(issues.sections.work.creative_judgments[1].decision == "pending", "superseded candidate cannot accidentally approve the latest revision"):
		return
	await issues.judge_artifact(revised, "approved", "已核对当前原件", "", issues.action_snapshot())
	if not check(issues.sections.work.creative_judgments[1].decision == "approved", "explicit native judgment applies only to the selected current submission"):
		return
	var model_source: PackedByteArray = FileAccess.get_file_as_bytes(OS.get_environment("TX_MODEL_SOURCE"))
	var decoder = workspace.get_meta("asset_decoder_script")
	var model_candidate: Dictionary = await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches", {"request_key": workspace.new_id(), "changes": [{"module": "native-model-fixture", "base": null, "reads": null, "edits": {"triangle.glb": Marshalls.raw_to_base64(model_source)}}]})
	issues.edit("asset", {"kind": "model", "module": "native-model-fixture", "revision": model_candidate.data.revisions["native-model-fixture"], "path": "triangle.glb"})
	await issues.submit("asset")
	var model_asset: Dictionary = issues.sections.artifacts.artifacts.filter(func(item: Dictionary): return item.kind == "model")[0]
	await issues.inspect_artifact(model_asset)
	var model_preview: Dictionary = issues.previews[str(model_asset.version)]
	if not check(model_preview.get("scene") is PackedScene and model_preview.meshes == 1 and model_preview.bounds.size.x == 2, "native candidate submission reads the exact digest-verified GLB into real Godot mesh geometry"):
		return
	var source_directory: String = OS.get_environment("TX_MODEL_SOURCE").get_base_dir()
	if not check(not decoder.validate_glb(FileAccess.get_file_as_bytes(source_directory.path_join("external-model.glb"))).is_empty() and not decoder.validate_glb(FileAccess.get_file_as_bytes(source_directory.path_join("cyclic-model.glb"))).is_empty(), "native model preview rejects external dependencies and cyclic node graphs before import"):
		return
	var unlit: Dictionary = decoder.decode_glb(FileAccess.get_file_as_bytes(source_directory.path_join("unlit-model.glb")))
	if not check(unlit.get("scene") is PackedScene and unlit.meshes == 1, "native model preview supports standard unlit material extensions"):
		return
	var repositories = load_source("editor/docks/tianxuan/repositories_controller.gd").new()
	repositories.set_meta("workspace", workspace)
	workspace.add_child(repositories)
	await repositories.load_catalog("native")
	await repositories.select("native", candidate_module)
	await repositories.open_file("concept.txt")
	if not check(repositories.file.content == "第二版创意原件", "native repository reads the exact module head and digest-verified object"):
		return
	repositories.update_draft("仓库编辑产生的新修订", "")
	await repositories.save()
	if not check(repositories.file.content == "仓库编辑产生的新修订" and repositories.draft().is_empty(), "native repository edit creates and reads back a new immutable revision"):
		return
	repositories.update_draft("本地未提交修改", "")
	await session.api_request(HTTPClient.METHOD_POST, "/api/v1/native/batches", {"request_key": workspace.new_id(), "changes": [{"module": candidate_module, "base": repositories.revision, "reads": null, "edits": {"concept.txt": Marshalls.raw_to_base64("协作者的新修订".to_utf8_buffer())}}]})
	await repositories.save()
	if not check(repositories.draft().content == "本地未提交修改" and not repositories.draft().has("submission"), "native repository conflict preserves local content without replaying a new write"):
		return
	await repositories.select("native", candidate_module)
	await repositories.open_file("concept.txt")
	if not check(repositories.file.content == "协作者的新修订" and repositories.draft().content == "本地未提交修改", "native repository exposes the current remote object beside the preserved draft"):
		return
	repositories.review_draft()
	await repositories.save()
	if not check(repositories.file.content == "本地未提交修改", "reviewed repository draft saves against the explicitly compared revision"):
		return
	await repositories.load_catalog("git")
	await repositories.select("git", "fixture.git", "main")
	await repositories.open_file("README.md")
	if not check(repositories.file.content == "原生仓库测试\n" and repositories.state.tree.entries.size() == 2, "native Git browser reads the isolated repository tree and tracked file"):
		return
	repositories.update_draft("原生 Git 文件编辑\n", "Native edit fixture")
	await repositories.save()
	var edited_branch: String = repositories.branch
	if not check(edited_branch != "main" and repositories.file.content == "原生 Git 文件编辑\n" and repositories.draft().is_empty(), "native Git edit saves to a fresh branch and verifies its acknowledged file"):
		return
	await repositories.inspect("diff", "main", edited_branch)
	await repositories.inspect("search", "原生")
	await repositories.inspect("blame")
	if not check("原生 Git 文件编辑" in repositories.state.diff.diff and repositories.state.search.results.size() == 1 and not repositories.state.blame.lines.is_empty(), "native Git diff, search and line history return real commit evidence"):
		return
	await repositories.select("git", "fixture.git", "main")
	await repositories.open_file("README.md")
	if not check(repositories.file.content == "原生仓库测试\n", "native file editing preserves the original deployment branch"):
		return
	await repositories.manage_git("create_branch", {"name": "native-review", "ref": "main"}, repositories.git_snapshot())
	await repositories.manage_git("create_tag", {"name": "native-v1", "ref": "main", "message": "原生标签"}, repositories.git_snapshot())
	if not check("native-review" in repositories.state.branches and repositories.state.tags.size() == 1 and repositories.state.tags[0].name == "native-v1", "native branch and tag management reads back the actual Git references"):
		return
	await repositories.manage_git("delete_branch", {"name": "native-review"}, repositories.git_snapshot())
	await repositories.manage_git("delete_tag", {"name": "native-v1"}, repositories.git_snapshot())
	if not check(not "native-review" in repositories.state.branches and repositories.state.tags.is_empty() and "main" in repositories.state.branches, "native reference removal affects only the explicitly selected branch and tag"):
		return
	var configuration = load_source("editor/docks/tianxuan/game_config_controller.gd").new()
	configuration.set_meta("workspace", workspace)
	workspace.add_child(configuration)
	configuration.edit({"title": "原生配置测试", "features": []})
	configuration.add_item("", "combat", "战斗")
	configuration.add_item("combat", "health", "生命值")
	configuration.field("combat", "health", "type", "integer")
	configuration.field("combat", "health", "value", "100")
	configuration.field("combat", "health", "default", "100")
	configuration.field("combat", "health", "min", "0")
	await configuration.save()
	if not check(not configuration.selected.is_empty() and configuration.project.version == 1 and configuration.project.features[0].entries[0].value == 100, "native game configuration creates a real versioned project with typed integer data"):
		return
	configuration.field("combat", "health", "value", "-")
	await configuration.save()
	if not check(configuration.project.version == 1 and not configuration.validation.is_empty() and configuration.values().features[0].entries[0].value == "-", "incomplete numeric edits remain private drafts and never replace the persisted configuration"):
		return
	configuration.field("combat", "health", "value", "120")
	configuration.field("", "", "title", "本机配置标题")
	var config_payload := {"title": configuration.project.title, "features": configuration.project.features.duplicate(true), "expected_version": int(configuration.project.version)}
	config_payload.features[0].description = "协作者添加的说明"
	config_payload.features[0].entries[0].value = 100
	config_payload.features[0].entries[0].default = 100
	await session.api_request(HTTPClient.METHOD_PUT, "/api/v1/game-config/projects/" + configuration.selected, config_payload)
	await configuration.refresh()
	configuration.compare({}, true)
	await configuration.save()
	if configuration.project.version != 3 or configuration.project.title != "本机配置标题" or configuration.project.features[0].description != "协作者添加的说明" or configuration.project.features[0].entries[0].value != 120:
		print(JSON.stringify({"config": configuration.project, "draft": configuration.draft(), "status": configuration.status, "validation": configuration.validation, "conflicts": configuration.conflicts}))
	if not check(configuration.project.version == 3 and configuration.project.title == "本机配置标题" and configuration.project.features[0].description == "协作者添加的说明" and configuration.project.features[0].entries[0].value == 120, "configuration three-way merge preserves independent local and remote field changes"):
		return
	configuration.field("combat", "health", "value", "130")
	config_payload = {"title": configuration.project.title, "features": configuration.project.features.duplicate(true), "expected_version": int(configuration.project.version)}
	config_payload.features[0].entries[0].value = 140
	config_payload.features[0].entries[0].default = 100
	await session.api_request(HTTPClient.METHOD_PUT, "/api/v1/game-config/projects/" + configuration.selected, config_payload)
	await configuration.refresh()
	configuration.compare({}, true)
	if not check(configuration.outdated() and configuration.conflicts.size() == 1 and configuration.conflicts[0].path == "features/combat/entries/health/value", "concurrent changes to the same configuration field require one explicit conflict choice"):
		return
	configuration.compare({"features/combat/entries/health/value": "remote"}, true)
	await configuration.save()
	if not check(configuration.project.features[0].entries[0].value == 140 and configuration.draft().is_empty(), "the explicit remote conflict choice is saved and read back without retaining the discarded local value"):
		return
	var config_version := int(configuration.project.version)
	await configuration.history()
	await configuration.restore(1, configuration.snapshot())
	if not check(configuration.project.version == config_version + 1 and configuration.project.features[0].entries[0].value == 100, "native configuration history restore creates a new version using the confirmed current version"):
		return
	configuration.field("combat", "health", "value", "200")
	var pending_config: Dictionary = configuration.draft()
	var pending_payload: Dictionary = configuration.parse()
	pending_payload.expected_version = int(configuration.project.version)
	var config_route := "/api/v1/game-config/projects/" + str(configuration.selected)
	await session.api_request(HTTPClient.METHOD_PUT, config_route, pending_payload)
	pending_config.submission = {"kind": "save", "method": HTTPClient.METHOD_PUT, "route": config_route, "payload": pending_payload}
	workspace.save_draft(configuration.key(), pending_config)
	await configuration.refresh()
	if configuration.project.version != config_version + 2 or not configuration.draft().is_empty():
		print(JSON.stringify({"pending_config_project": configuration.project, "pending_config_draft": configuration.draft(), "status": configuration.status, "expected_version": config_version + 2}))
	if not check(configuration.project.version == config_version + 2 and configuration.draft().is_empty(), "lost configuration acknowledgement reads the matching saved version without creating a duplicate revision"):
		return
	var runtime := WebSocketPeer.new()
	runtime.handshake_headers = PackedStringArray(["Authorization: Bearer " + str(session._token)])
	runtime.connect_to_url("ws" + session.origin.trim_prefix("http") + "/api/v1/ws/game-config/" + configuration.selected + "?kind=runtime")
	if not check(await wait_until(func(): runtime.poll(); return runtime.get_ready_state() == WebSocketPeer.STATE_OPEN), "isolated real game consumer authenticates over the existing websocket protocol"):
		return
	runtime.send_text(JSON.stringify({"type": "subscribe", "name": "隔离游戏客户端"}))
	if not check(await wait_until(func(): runtime.poll(); return runtime.get_available_packet_count() > 0), "game consumer receives the saved configuration snapshot"):
		return
	var runtime_snapshot: Variant = JSON.parse_string(runtime.get_packet().get_string_from_utf8())
	runtime.send_text(JSON.stringify({"type": "applied", "version": int(runtime_snapshot.project.version)}))
	if not check(await wait_until(func(): runtime.poll(); return configuration.clients.size() == 1 and configuration.clients[0].status == "applied" and configuration.clients[0].version == configuration.project.version), "native configuration displays applied only after a real runtime acknowledges the exact current version"):
		return
	runtime.close()
	repositories.edit_import("native-import.git", "https://user:private@example.invalid/repo.git")
	if not check(not repositories.import_error().is_empty() and repositories.import_draft().is_empty(), "credential-bearing repository URLs never enter durable import drafts"):
		return
	repositories.edit_import("native-import.git", OS.get_environment("TX_IMPORT_REPOSITORY"))
	repositories.observe_imports(repositories, true)
	await repositories.start_import(repositories.import_draft(), session.scope_key())
	if not check(await wait_until(func(): return repositories.import_jobs.any(func(job: Dictionary): return job.name == "native-import.git" and job.status == "succeeded")), "native import follows an actual background Git mirror job to its completed server receipt"):
		return
	var imported_file: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/git/repos/native-import.git/file?branch=main&path=README.md")
	if not check(imported_file.status == 200 and imported_file.data.content == "原生仓库测试\n", "imported Git repository contains the exact source commit content"):
		return
	repositories.edit_import("native-import.git", OS.get_environment("TX_IMPORT_REPOSITORY"))
	await repositories.start_import(repositories.import_draft(), session.scope_key())
	if not check(await wait_until(func(): return repositories.import_jobs.any(func(job: Dictionary): return job.name == "native-import.git" and job.status == "failed")), "duplicate repository import reports the real failure and retains the existing repository"):
		return
	repositories.observe_imports(repositories, false)
	var collaboration = load_source("editor/docks/tianxuan/repository_collaboration_controller.gd").new()
	collaboration.set_meta("workspace", workspace)
	workspace.add_child(collaboration)
	await collaboration.load_catalog()
	await collaboration.execute("link_repository", {"provider": "github", "owner": "fixture", "name": "native-ui"}, collaboration.snapshot())
	if not check(collaboration.data.configuration.configured == false and collaboration.data.links.links.size() == 1, "native repository bindings work without pretending external hosting is configured"):
		return
	await collaboration.execute("unlink_repository", {"id": collaboration.data.links.links[0].id}, collaboration.snapshot())
	await collaboration.execute("enqueue", {"repo": "fixture.git", "source": edited_branch, "target": "main", "title": "原生合入验证"}, collaboration.snapshot())
	if not check(collaboration.data.links.links.is_empty() and collaboration.data.queue.items.size() == 1 and collaboration.data.queue.items[0].status == "queued", "native queue durably records the exact source and target of the isolated Git candidate"):
		return
	collaboration.queue_id = collaboration.data.queue.items[0].id
	await collaboration.execute("cancel_queue", {}, collaboration.snapshot())
	if not check(collaboration.data.queue.items[0].status == "cancelled", "native queue cancellation reads back the selected candidate's actual state"):
		return
	await collaboration.execute("enqueue", {"repo": "fixture.git", "source": edited_branch, "target": "main", "title": "原生合入执行"}, collaboration.snapshot())
	await collaboration.execute("process_queue", {}, collaboration.snapshot())
	await repositories.open_file("README.md")
	if not check(collaboration.data.queue.items.filter(func(item: Dictionary): return item.status == "merged").size() == 1 and repositories.file.content == "原生 Git 文件编辑\n", "native queue processing verifies the actual merged file on the target branch"):
		return
	var migration = load_source("editor/docks/tianxuan/migration_controller.gd").new()
	migration.set_meta("workspace", workspace)
	workspace.add_child(migration)
	await migration.refresh()
	await migration.read("search", {"query": "原生归档", "limit": 10})
	await migration.read("detail", {"source_id": "github:fixture/repo/issue/14"})
	if not check(migration.publication.available and migration.data.search.total == 1 and migration.data.detail.record.content.body == "只读历史，不触发任务执行。" and migration.data.detail.comments.total == 1, "native migration browser reads the published catalog and its linked archived comments"):
		return
	await migration.read("commits", {"path": "README.md", "limit": 10})
	await migration.read("file", {"path": "README.md", "commit": migration.publication.revision})
	if not check(migration.data.commits.items.size() == 1 and migration.data.file.text == "原生仓库测试\n", "native archive code history reads the immutable imported Git bundle despite later active repository changes"):
		return
	var live_issues: Dictionary = await session.api_request(HTTPClient.METHOD_GET, "/api/v1/issues")
	if not check(live_issues.data.issues.filter(func(item: Dictionary): return item.title == "原生归档工单").is_empty(), "reading archived work orders never creates executable live issues"):
		return
	await migration.set_entry("tianxuan", migration.snapshot())
	if not check(migration.entry == "tianxuan", "native migration settings persist and read back the explicit administrator entry choice"):
		return
	migration.edit("来自原生迁移入口的新任务")
	await migration.start(migration.snapshot())
	if not check(migration.data.get("task", {}).has("issue_id") and migration.draft().is_empty(), "explicit migration new-task intent creates a new live issue separate from archived history"):
		return
	var accounts = load_source("editor/docks/tianxuan/accounts_controller.gd").new()
	accounts.set_meta("workspace", workspace)
	workspace.add_child(accounts)
	await accounts.refresh()
	await accounts.execute("create_account", {"email": "native-member@example.invalid", "name": "原生成员", "role": "editor"}, accounts.snapshot())
	var new_members: Array = accounts.data.users.users.filter(func(item: Dictionary): return item.email == "native-member@example.invalid")
	if not check(new_members.size() == 1 and not accounts.issued_secret.is_empty() and accounts.data.keys.keys.size() == 2, "native account creation separately verifies the new member and the issued initial key"):
		return
	var member_id := str(new_members[0].id)
	var issued_secret: String = accounts.issued_secret
	var private_safe := true
	var private_directory: String = workspace.storage_root.path_join(session.scope_key())
	for filename in DirAccess.get_files_at(private_directory):
		if issued_secret in FileAccess.get_file_as_string(private_directory.path_join(filename)):
			private_safe = false
	if not check(private_safe and not issued_secret in JSON.stringify(accounts.data), "new credential plaintext is never placed in private drafts or cached account records"):
		return
	accounts.hide_secret()
	await accounts.execute("set_role", {"id": member_id, "role": "viewer"}, accounts.snapshot())
	await accounts.execute("bind_identity", {"provider": "github", "subject": "native-fixture", "user_id": member_id}, accounts.snapshot())
	if not check(accounts.data.users.users.filter(func(item: Dictionary): return item.id == member_id)[0].role == "viewer" and accounts.data.links.links.size() == 1, "native account role and external identity binding changes use the existing administration permissions"):
		return
	var binding_id := str(accounts.data.links.links[0].id)
	await accounts.execute("rebind_identity", {"id": binding_id, "user_id": actor_a}, accounts.snapshot())
	await accounts.execute("unbind_identity", {"id": binding_id}, accounts.snapshot())
	if not check(accounts.data.links.links.is_empty() and accounts.data.events.events.size() >= 3, "native identity rebind and removal retain the server's auditable event history"):
		return
	await accounts.execute("issue_admin_key", {"user_id": actor_a, "name": "原生管理员验收", "days": 1}, accounts.snapshot())
	if not check(not accounts.issued_secret.is_empty(), "native administrator-key allocation follows the deployment capability and administrator recipient check"):
		return
	accounts.hide_secret()
	var issued_key: Dictionary = accounts.data.keys.keys.filter(func(item: Dictionary): return item.name == "原生管理员验收")[0]
	await accounts.execute("revoke_key", {"id": issued_key.id}, accounts.snapshot())
	if not check(accounts.data.keys.keys.filter(func(item: Dictionary): return item.id == issued_key.id)[0].revoked_at != null, "native key revocation reads back the authoritative revoked state"):
		return
	var owner_issue: String = issues.selected
	issues.edit("comment", {"body": "只属于当前账号的工单草稿"})
	await session.authenticate("", OS.get_environment("TX_VIEWER_KEY"), "workspace")
	await issues.open(owner_issue)
	await collaboration.load_queue()
	await collaboration.execute("enqueue", {"repo": "fixture.git", "source": edited_branch, "target": "main"}, collaboration.snapshot())
	if not check(not collaboration.writable() and collaboration.data.queue.items.size() == 2 and collaboration.draft("pending").is_empty(), "read-only identities cannot submit native merge candidates"):
		return
	if not check(not issues.editable() and issues.draft("comment").is_empty(), "viewer identity cannot edit or inherit another account's issue draft"):
		return
	if not check(session.set_origin("http://127.0.0.1:1") and session.get_identity().is_empty(), "service change immediately clears authentication"):
		return
	sidebar_view.free()
	workspace.free()
	await create_timer(0.2).timeout
	session.free()
	print(JSON.stringify({"passed": true, "checks": checks}))
	quit(0)
