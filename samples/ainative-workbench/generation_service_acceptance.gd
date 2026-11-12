extends SceneTree
# UI and HTTP transport infrastructure only. Fixture servers never run models.
var panel
var checks: Array = []
var failures = 0
var state_path = ""
var valid_endpoint = ""
var image_model = "fixture-image.safetensors"
var mesh_model = "fixture-mesh.safetensors"
var settings_requests: Array = []

func check(ok: bool, label: String) -> bool:
	print(("PASS " if ok else "FAIL ") + label)
	checks.append({"passed":ok, "label":label})
	if not ok: failures += 1
	return ok

func _initialize():
	run.call_deferred()

func settle():
	for i in 4: await process_frame

func idle():
	var deadline = Time.get_ticks_msec() + 20000
	while (panel.creating or panel.auto_step or not panel.jobs.is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame
	check(not panel.creating and not panel.auto_step and panel.jobs.is_empty(), "service operation completes while the editor remains responsive")

func mode(value: String):
	for i in panel.service_choice.item_count:
		if panel.service_choice.get_item_metadata(i) == value:
			panel.service_choice.select(i)
			panel.service_choice.item_selected.emit(i)
			return
	check(false, "requested service mode exists: " + value)

func select_model(choice: OptionButton, model: String):
	for i in choice.item_count:
		if choice.get_item_metadata(i) == model:
			choice.select(i)
			choice.item_selected.emit(i)
			return
	check(false, "detected model is selectable: " + model)

func traffic() -> Array:
	var path = OS.get_environment("AINATIVE_SERVICE_TEST_TRAFFIC")
	if path.is_empty() or not FileAccess.file_exists(path): return []
	var value = JSON.parse_string(FileAccess.get_file_as_string(path))
	return value if value is Array else []

func same_settings(left: Dictionary, right: Dictionary) -> bool:
	return JSON.parse_string(JSON.stringify(left)) == JSON.parse_string(JSON.stringify(right))

func new_panel():
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.state_dir = state_path
	panel.set_meta("ainative_builtin", true)
	panel.settings_requested.connect(func(section): settings_requests.append(section))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await settle()
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")

func set_node(kind: String, source: String, prompt: String = ""):
	panel.nodes = [{"id":"fixture", "type":kind, "version":"1", "provider":"local-copy" if kind == "copy" else "comfy", "source":source, "image_context":"", "text":"", "parameters":{"delay":0.0,"fail":false} if kind == "copy" else {"prompt":prompt,"seed":1}, "x":40,"y":60}]
	panel.edges = []
	panel.rebuild()
	panel.select_node("fixture")

func configure_valid():
	mode("comfy")
	panel.endpoint_edit.text = valid_endpoint
	panel.check_service()
	await idle()
	select_model(panel.image_model_choice, image_model)
	select_model(panel.mesh_model_choice, mesh_model)
	panel.save_service_settings()
	panel.check_service()
	await idle()

func run():
	root.size = Vector2i(1440,1000)
	var state_override = OS.get_environment("AINATIVE_SERVICE_TEST_STATE")
	state_path = state_override.path_join(str(Time.get_ticks_usec())) if not state_override.is_empty() else ProjectSettings.globalize_path("user://generation-service-test-" + str(Time.get_ticks_usec()))
	valid_endpoint = OS.get_environment("AINATIVE_SERVICE_TEST_ENDPOINT")
	if not check(not valid_endpoint.is_empty(), "read-only HTTP fixture endpoints are explicitly supplied"):
		await finish()
		return
	await new_panel()
	if not check(panel.get("service_choice") is OptionButton and panel.has_method("check_service"), "built-in settings expose generation service controls"):
		await finish()
		return
	var available_modes: Array = []
	for i in panel.service_choice.item_count: available_modes.append(panel.service_choice.get_item_metadata(i))
	for expected_mode in ["offline", "comfy", "legacy", "codex", "codex_modeling", "codex_sculpt", "kimi_native", "local_mesh", "api_modeling", "api_sculpt"]:
		check(expected_mode in available_modes, "settings expose service mode: " + expected_mode)
	check(panel._service_mode() == "offline" and panel.service_saved.is_empty(), "a fresh project starts without a claimed real generation service")
	check(panel.service_status.text.contains("离线") and panel.service_capability_labels.copy.text.contains("可用"), "fresh settings clearly show offline copying availability")
	set_node("text_to_image", "", "fixture prompt; do not submit")
	var serial = panel.serial
	panel.run_node_preview("fixture")
	check(panel.serial == serial and panel.jobs.is_empty() and panel.status.text.contains("离线"), "direct generation is blocked before subprocess creation in offline mode")
	check(panel.service_config_link.visible, "blocked generation exposes an actionable configuration entry")
	panel.service_config_link.pressed.emit()
	await settle()
	check(settings_requests.back() == 'ai' and not panel.native_sections.machine.visible, "configuration entry navigates to central AI settings without reopening an editable business form")
	check(traffic().is_empty(), "opening settings and rejecting unconfigured generation makes no HTTP calls")
	mode("comfy")
	panel.endpoint_edit.text = valid_endpoint
	panel.check_service()
	await idle()
	print('DISCOVERY_REPORT ',JSON.stringify(panel.service_report),' STATUS ',panel.service_status.text,' DRAFT ',JSON.stringify(panel.service_draft()))
	check(panel.service_report.get("connected", false), "GUI discovery reaches the read-only HTTP fixture through the real Python subprocess")
	check(panel._model_name(panel.image_model_choice).is_empty() and panel._model_name(panel.mesh_model_choice).is_empty(), "discovery lists models without silently selecting one")
	var images: Array = []
	for i in panel.image_model_choice.item_count: images.append(panel.image_model_choice.get_item_metadata(i))
	var meshes: Array = []
	for i in panel.mesh_model_choice.item_count: meshes.append(panel.mesh_model_choice.get_item_metadata(i))
	check(images.has(image_model) and meshes.has(mesh_model), "both model selectors contain names reported by the fixture")
	check(not panel.service_report.capabilities.text_to_image.ready and panel.service_capability_labels.text_to_image.text.contains("不可用"), "detected but unselected models do not claim generation readiness")
	select_model(panel.image_model_choice, image_model)
	select_model(panel.mesh_model_choice, mesh_model)
	panel.save_service_settings()
	check(FileAccess.file_exists(panel.service_config_path), "GUI save creates the private local service configuration")
	var config = JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path))
	var expected_config = {"schema_version":1,"mode":"comfy","endpoint":valid_endpoint,"image_model":image_model,"mesh_model":mesh_model}
	expected_config.merge(panel._image_board_runtime())
	check(same_settings(config, expected_config), "saved configuration exactly records the endpoint, models and trusted board runtime")
	check(expected_config.image_board_godot_path.is_absolute_path() and expected_config.image_board_builder_path.is_absolute_path() and FileAccess.file_exists(expected_config.image_board_godot_path) and FileAccess.file_exists(expected_config.image_board_builder_path), "saved reference-board Godot and builder paths are absolute and executable/readable")
	check(panel.factory_edit.text == "editor_demo:factory" and panel._uses_gui_service(), "explicit GUI settings select the managed adapter without a custom factory or environment variable")
	panel.path_edit.text = state_path.path_join("workflow.json")
	panel.save_graph()
	var graph_text = FileAccess.get_file_as_string(panel.path_edit.text)
	check(not graph_text.contains(valid_endpoint) and not graph_text.contains(image_model) and not graph_text.contains("service_config"), "workflow serialization excludes machine service settings")
	panel.check_service()
	await idle()
	check(panel.service_report.capabilities.text_to_image.ready and panel.service_report.capabilities.image_to_mesh.ready, "selected fixture models enable the corresponding discovered capabilities")
	check(panel.service_capability_labels.text_to_image.text.contains("就绪") and panel.service_capability_labels.image_to_mesh.text.contains("就绪"), "capability readiness is shown separately for image and mesh types")
	var saved_config = config.duplicate(true)
	panel.queue_free()
	await settle()
	await new_panel()
	check(same_settings(panel.service_draft(), saved_config) and same_settings(panel.service_saved, saved_config), "freshly recreated GUI restores saved settings independently of launcher environment")
	check(panel.service_report.is_empty() and panel.service_status.text.contains("待检测"), "restored settings do not reuse a stale connection result")
	check(panel._model_name(panel.image_model_choice) == image_model and panel._model_name(panel.mesh_model_choice) == mesh_model, "saved model choices survive reopening before discovery")
	# Missing node input must win before network checks or provider calls.
	set_node("image_to_mesh", "")
	var traffic_before = traffic().size()
	serial = panel.serial
	panel.run_node_preview("fixture")
	check(panel.serial == serial and traffic().size() == traffic_before and panel.status.text.contains("源文件"), "missing required source is diagnosed before a service check or subprocess")
	# Check replies are bound to the exact draft which initiated them.
	mode("comfy")
	panel.endpoint_edit.text = OS.get_environment("AINATIVE_SERVICE_TEST_SLOW_ENDPOINT")
	panel.check_service()
	check(not panel.jobs.is_empty(), "slow fixture check is actually pending")
	panel.endpoint_edit.text = valid_endpoint
	await idle()
	check(panel.service_report.is_empty() and panel.service_status.text.contains("已改变"), "late discovery for an edited endpoint cannot replace current readiness")
	# Unsafe address saves preserve the prior valid bytes and redact secrets.
	var saved_hash = FileAccess.get_sha256(panel.service_config_path)
	panel.endpoint_edit.text = "http://fixture-user:fixture-secret@127.0.0.1:1234/private?token=fixture-token"
	panel.save_service_settings()
	check(FileAccess.get_sha256(panel.service_config_path) == saved_hash and panel.status.text.contains("地址"), "invalid authenticated or path-bearing address cannot replace the last valid configuration")
	check(not panel.status.text.contains("fixture-secret") and not panel.service_status.text.contains("fixture-token"), "visible validation errors do not echo embedded credentials")
	# Discoverable service failures remain distinguishable and actionable.
	panel.endpoint_edit.text = "http://127.0.0.1:1"
	panel.check_service()
	await idle()
	check(panel.service_report.get("code") == "service_unreachable" and panel.service_status.text.contains("无法连接"), "offline service produces a precise connection failure")
	panel.endpoint_edit.text = OS.get_environment("AINATIVE_SERVICE_TEST_PROTOCOL_ENDPOINT")
	panel.check_service()
	await idle()
	check(panel.service_report.get("code") == "service_protocol_invalid" and panel.service_status.text.contains("兼容"), "wrong server protocol is distinguished from an offline service")
	panel.endpoint_edit.text = OS.get_environment("AINATIVE_SERVICE_TEST_MISSING_ENDPOINT")
	panel.check_service()
	await idle()
	check(panel.service_report.capabilities.text_to_image.code == "image_model_missing" and panel.service_report.capabilities.image_to_mesh.code == "mesh_model_missing", "missing model lists report the specific image and mesh requirements")
	check(panel.service_capability_labels.text_to_image.text.contains("模型") and not panel.service_report.capabilities.text_to_mesh.ready, "missing models leave affected capabilities unavailable with a repair hint")
	await configure_valid()
	check(panel._service_blocker("text_to_image").is_empty() and panel._service_blocker("image_to_mesh").is_empty(), "corrected detected and saved settings recover service eligibility without restarting")
	# A mesh-only configuration is sufficient until an explicit redraw prompt is supplied.
	select_model(panel.image_model_choice, "")
	panel.save_service_settings()
	panel.check_service()
	await idle()
	panel.show_native_section("mesh")
	set_node("image_to_mesh", ProjectSettings.globalize_path("res://fixtures/sample.png"))
	check(panel.node_run_blocker("fixture").is_empty() and panel.service_report.capabilities.image_to_mesh.ready, "mesh-only settings allow image-to-mesh without an optional redraw prompt")
	panel.parameter_form.prompt_edit.text = "redraw this source before mesh generation"
	panel.parameter_form.prompt_edit.text_changed.emit()
	panel.apply_fields()
	check(panel.node_run_blocker("fixture").contains("图像模型"), "an explicit image-to-mesh redraw prompt requires an image model")
	panel.path_edit.text = state_path.path_join("existing-redraw-workflow.json")
	panel.save_graph()
	panel.open_graph()
	panel.select_node("fixture")
	check(panel.nodes[0].parameters.prompt == "redraw this source before mesh generation" and panel.parameter_form.prompt_edit.text == panel.nodes[0].parameters.prompt, "existing saved image-to-mesh prompts remain intact and visible")
	for i in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(i) == "image_to_mesh": panel.generator_choice.select(i)
	panel.add_generator()
	check(panel.nodes.back().parameters.prompt.is_empty(), "new image-to-mesh nodes start without silently requesting image redraw")
	var count_before_context = panel.nodes.size()
	panel.graph.popup_request.emit(panel.graph.size - Vector2(10,10))
	panel.create_context_node("image_to_mesh")
	check(panel.nodes.size() == count_before_context + 1 and panel.nodes.back().parameters.prompt.is_empty(), "context-created image-to-mesh nodes also start with an empty optional prompt")
	panel.context_menu.hide()
	# The original defect swallowed create exceptions. A fixture which becomes
	# unavailable after discovery proves the actual create reply is actionable.
	panel.endpoint_edit.text = OS.get_environment("AINATIVE_SERVICE_TEST_STOPS_ENDPOINT")
	panel.check_service()
	await idle()
	select_model(panel.image_model_choice, image_model)
	select_model(panel.mesh_model_choice, mesh_model)
	panel.save_service_settings()
	panel.check_service()
	await idle()
	check(panel.service_report.capabilities.image_to_mesh.ready, "service fixture is ready before simulating loss between detection and execution")
	set_node("image_to_mesh", ProjectSettings.globalize_path("res://fixtures/sample.png"))
	panel.show_native_section("mesh")
	serial = panel.serial
	panel.run_node_preview("fixture")
	await idle()
	check(panel.serial > serial and panel.status.text.contains("操作失败") and panel.status.text.contains("无法连接"), "a real create-stage service failure reaches the GUI as a precise repairable error")
	check(panel.service_config_link.visible and panel.preview_history.get("fixture", []).is_empty(), "failed create exposes settings and does not invent a generated result")
	await configure_valid()
	# Legacy mode remains explicit and separate from the GUI JSON schema.
	mode("legacy")
	panel.save_service_settings()
	var local = ConfigFile.new()
	local.load(state_path.path_join("local.cfg"))
	check(local.get_value("service","mode","") == "legacy", "legacy compatibility choice persists explicitly in local host settings")
	check(JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path)).mode == "comfy", "legacy selection does not write an unsupported legacy mode into managed service JSON")
	serial = panel.serial
	panel.check_service()
	check(panel.serial == serial and panel.service_status.text.contains("旧配置"), "legacy check points to the configured adapter without sending managed HTTP discovery")
	# Kimi configuration is local-only here; no discovery or inference is submitted.
	mode("kimi_native")
	panel.endpoint_edit.text = "https://api.kimi.com/coding/v1"
	panel.kimi_model_edit.text = "k3-256k"
	var kimi_draft = panel.service_draft()
	check(kimi_draft.endpoint == "https://api.kimi.com/coding/v1" and not kimi_draft.has("cli_path") and not kimi_draft.has("blender_path"), "Kimi Native does not inherit ComfyUI, Codex or Blender configuration")
	check(panel._generator_provider("text_to_mesh") == "kimi_native" and panel._generator_provider("image_to_mesh") == "kimi_native", "Kimi Native routes both Mesh node kinds")
	check(panel._generator_provider("text_to_image") == "kimi_work_image" and panel._generator_provider("image_to_image") == "kimi_work_image", "2D nodes route independently to Kimi Work image generation")
	panel.save_service_settings()
	check(panel._service_blocker("text_to_mesh").is_empty() and panel._service_blocker("text_to_image").contains("Kimi Work") and panel._service_blocker("image_to_image").contains("pythonw"), "missing image tools do not block Mesh and explain the independent 2D configuration")
	panel.kimi_image_tool_edit.text = state_path.path_join("fixture-only/image_generation_tool.py")
	panel.kimi_image_pythonw_edit.text = state_path.path_join("fixture-only/pythonw.exe")
	kimi_draft = panel.service_draft()
	panel.save_service_settings()
	check(panel._service_blocker("text_to_image").is_empty() and panel._service_blocker("image_to_image").is_empty(), "saved composite settings admit 2D nodes for the actual local tool check at run creation")
	var kimi_json = FileAccess.get_file_as_string(panel.service_config_path)
	check(panel.service_saved == kimi_draft and not kimi_json.contains("api_key") and not kimi_json.contains("secret") and not kimi_json.contains("authorization"), "Kimi composite settings save model identity without credentials")
	set_node("text_to_image", "", "fixture prompt; do not submit")
	check(panel.parameter_form.parameters().get("width") == 1024 and panel.parameter_form.parameters().get("height") == 1024 and not panel.parameter_form.rows.seed.visible, "Kimi Work images expose effective default dimensions and hide unsupported sampling")
	panel.parameter_form.controls.width.value = 1536
	check(panel.apply_fields() and panel.nodes[0].parameters.width == 1536 and panel.parameter_form.controls.width.custom_arrow_step == 16, "Kimi Work image widths use real 16-pixel controls beyond the legacy 1024 limit")
	panel.path_edit.text = state_path.path_join("kimi-composite-workflow.json")
	panel.save_graph()
	var workflow_text = FileAccess.get_file_as_string(panel.path_edit.text)
	check(not workflow_text.contains("fixture-only") and not workflow_text.contains("generation-service.json"), "machine image-tool paths never enter workflow serialization")
	panel.queue_free()
	await settle()
	await new_panel()
	check(panel.service_saved == kimi_draft and panel.kimi_model_edit.text == "k3-256k" and panel._service_mode() == "kimi_native" and panel.kimi_image_tool_edit.text == kimi_draft.image_tool_path and panel.kimi_image_pythonw_edit.text == kimi_draft.image_pythonw_path, "Kimi composite settings restore through a fresh Workbench")
	# Switching to offline remains usable for real local-copy preview/publication.
	mode("offline")
	panel.save_service_settings()
	check(JSON.parse_string(FileAccess.get_file_as_string(panel.service_config_path)).mode == "offline", "GUI can save and restore offline mode explicitly")
	panel.show_native_section("mesh")
	var source = ProjectSettings.globalize_path("res://fixtures/sample.png")
	var source_hash = FileAccess.get_sha256(source)
	set_node("copy", source)
	panel.run_node_preview("fixture")
	await idle()
	check(panel.current.get("state") == "succeeded" and panel.preview_resource is ImageTexture, "offline copy still runs and previews actual image bytes using the managed configuration")
	check(panel.preview_artifact.is_empty(), "ordinary single-image preview retains implicit primary publication identity")
	panel.target_edit.text = state_path.path_join("copied-image.tres")
	panel.review_publish()
	check(not FileAccess.file_exists(panel.target_edit.text) and not panel.confirmation.is_empty(), "offline publication still waits for its explicit confirmation")
	panel.confirm_publish()
	panel.dialog.hide()
	await idle()
	check(ResourceLoader.load(panel.target_edit.text,"",ResourceLoader.CACHE_MODE_IGNORE) is Texture2D, "confirmed copied image reloads as a Godot resource")
	check(FileAccess.get_sha256(source) == source_hash, "service configuration and copy publication preserve source bytes")
	var calls = traffic()
	check(calls.size() >= 10 and calls.all(func(call): return call.method == "GET"), "all fixture traffic is read-only discovery; no prompt submission or uploads occur")
	check(calls.all(func(call): return call.path in ["/object_info","/system_stats"]), "GUI detection uses only the documented discovery endpoints")
	await finish()

func finish():
	var receipt = {"ok":failures == 0,"checks":checks,"failures":failures,"scope":"HTTP fixture configuration and offline copy only; no real generation models are installed or executed"}
	var report = OS.get_environment("AINATIVE_SERVICE_GUI_REPORT")
	if not report.is_empty():
		var output = FileAccess.open(report,FileAccess.WRITE)
		if output: output.store_string(JSON.stringify(receipt,"  ")); output.close()
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	print("AINATIVE_SERVICE_GUI failures="+str(failures))
	quit(0 if failures == 0 else 1)
