extends SceneTree
## Node-adapter checks use a synthetic T-pose fixture, not production visual acceptance.
const HumanoidRigNode = preload("res://addons/ainative/humanoid_rig_node.gd")
var panel
var failures = 0
var checks: Array = []

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ")+label)
	checks.append({"passed":ok,"label":label})
	if not ok: failures += 1

func double_click(control: Control):
	var event = InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.double_click = true
	control.gui_input.emit(event)

func drag_connection(source: GraphNode, target: GraphNode):
	for index in 4: await process_frame
	var from = source.get_global_transform()*source.get_output_port_position(0)
	var to = target.get_global_transform()*target.get_input_port_position(0)
	var press = InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = from
	press.global_position = from
	Input.parse_input_event(press)
	await process_frame
	var motion = InputEventMouseMotion.new()
	motion.position = to
	motion.global_position = to
	motion.relative = to-from
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(motion)
	await process_frame
	var release = InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = to
	release.global_position = to
	Input.parse_input_event(release)
	await process_frame

func wait_thumbnails():
	var deadline = Time.get_ticks_msec() + 10000
	var loading = true
	while loading and Time.get_ticks_msec() < deadline:
		loading = false
		for thumbnail in panel.graph.find_children("*", "SubViewportContainer", true, false):
			if thumbnail.has_method("is_loading") and thumbnail.is_loading(): loading = true
		if loading: await process_frame
	check(not loading, "asynchronous character thumbnails complete")

func human_node(source: String) -> Dictionary:
	return {"id":"rig","type":"humanoid_rig","version":"1","provider":"local-humanoid-rig","source":source,"image_context":"","text":"","parameters":{"height_m":1.8,"max_repair_attempts":3},"x":30.0,"y":40.0}

func glb_json(path: String) -> Dictionary:
	var bytes = FileAccess.get_file_as_bytes(path)
	if bytes.size() < 28: return {}
	var json_length = bytes.decode_u32(12)
	if json_length <= 0 or 20 + json_length > bytes.size(): return {}
	var document = JSON.parse_string(bytes.slice(20,20+json_length).get_string_from_utf8())
	return document if document is Dictionary else {}

func accepted_ai_receipt(source_sha: String) -> Dictionary:
	return {
		"passed":true,
		"source_sha256":source_sha,
		"head_review":{
			"schema_version":2,"mode":"automatic","ai_reviewed":true,"passed":true,
			"geometry_sha256":source_sha,"source_sha256":source_sha,"head_geometry_mode":"integrated",
			"head_gate":{"applicable":true,"complete_face":true,"neck_join_pass":true,"identity_pass":true,"face_proportions_pass":true,"animation_geometry_pass":true,"observation":"synthetic AI adapter receipt"},
			"head_views":{"head_front":true,"head_three_quarter":true,"head_side":true},
			"acceptance":{"top_view":"approximate_allowed","face":"recognizable_identity_normal_proportions","animation":"geometry_readiness_only_rig_unverified"},
			"animation_geometry_ready":true,"rigging_verified":false,"animation_verified":false
		}
	}

func accepted_text_receipt() -> Dictionary:
	return {
		"schema_version":1,"text_only":true,"synthetic":true,"passed":true,"local_passed":true,
		"summary":"合成文本回执：本地实测证据完整。","issues":[],"feedback":[],
		"repair":{"command":"none","parameters":{}},"retry_count":1,"max_retries":3,
		"review_document":{"schema_version":1,"passed":true},"api_receipt":{"provider":"synthetic_fixture"}
	}

func _initialize():
	call_deferred("run")

func run():
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin",true)
	root.size = Vector2i(1440,1000)
	root.add_child(panel)
	panel.humanoid_text_review_fixture = accepted_text_receipt()
	await process_frame
	panel.state_dir = ProjectSettings.globalize_path("user://humanoid-node-"+str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db = panel.state_dir.path_join("jobs.sqlite")
	var unreviewed = ProjectSettings.globalize_path("res://fixtures/humanoid_no_review.glb")
	var unreviewed_sha = FileAccess.get_sha256(unreviewed)
	panel.nodes = [human_node(unreviewed)]
	panel.edges = []
	panel.rebuild()
	panel.select_node("rig")
	check(panel.has_method("_start_humanoid_ai_review") and not panel.has_method("_confirm_head_review"),"missing review uses AI-only entry with no manual confirmation callback")
	var ai_input = panel._direct_humanoid_input("rig")
	panel.humanoid_review_node = "rig"
	panel.humanoid_review_source = unreviewed
	panel.humanoid_review_directory = "synthetic-ai-review"
	panel.humanoid_review_input = ai_input.duplicate(true)
	panel._complete_humanoid_ai_review(accepted_ai_receipt(unreviewed_sha),{"directory":"synthetic-ai-review"})
	var ai_entry = panel._latest_character_entry("rig")
	check(not ai_entry.is_empty() and not ai_entry.get("provenance",{}).get("capability_limited",true),"accepted synthetic AI receipt continues through fitting and ROM")
	var ai_data: Dictionary = panel.nodes[0]
	check(ai_data.get("parameters",{}).get("head_review",{}).get("source_sha256","")==unreviewed_sha and ai_data.parameters.head_review.get("mode","")=="automatic","AI review is automatic and bound to the exact source digest")
	check(FileAccess.get_sha256(unreviewed)==unreviewed_sha,"AI review never modifies the source GLB")
	panel.path_edit.text = panel.state_dir.path_join("ai-review.json")
	panel.save_graph()
	panel.open_graph()
	ai_data = panel.nodes[0]
	check(ai_data.get("parameters",{}).get("head_review",{}).get("source_sha256","")==unreviewed_sha,"AI review survives workflow save and reopen")
	var ai_history = panel.preview_history.get("rig",[]).size()
	ai_data.parameters = {"height_m":1.8,"head_review":{"passed":false}}
	panel.select_node("rig")
	panel._execute_humanoid("rig",panel._direct_humanoid_input("rig"))
	check(panel.failure_dialog.visible,"an existing failed review is rejected rather than replaced by a synthetic AI receipt")
	check(panel.preview_history.get("rig",[]).size()==ai_history,"failed existing review cannot create a character")
	panel.failure_dialog.hide()
	panel.controller.reset()
	panel.preview_history.clear()
	var source = ProjectSettings.globalize_path("res://fixtures/humanoid_t_pose.glb")
	if OS.has_environment("AINATIVE_HUMANOID_SOURCE"): source = OS.get_environment("AINATIVE_HUMANOID_SOURCE")
	var source_sha = FileAccess.get_sha256(source)
	panel.nodes = [human_node(source)]
	panel.edges = []
	panel.rebuild()
	panel.select_node("rig")
	var data: Dictionary = panel.nodes[0]
	check(panel.input_kind(data)==panel.PORT_MESH and panel.output_kind(data)==panel.PORT_CHARACTER,"humanoid node declares Mesh input and character output")
	check(panel.node_label("humanoid_rig")=="创建人形17根骨骼" and panel._generator_provider("humanoid_rig")=="local-humanoid-rig","humanoid node has Chinese label and local provider")
	check(panel.node_run_blocker("rig").is_empty(),"local rig does not require an AI service")
	check(panel.graph.get_node("rig/PortTypes/OutputType").text=="输出：人形角色（17骨＋root）","node explains seventeen anatomical bones plus root")
	check(panel.parameter_form.rows.max_repair_attempts.visible and HumanoidRigNode.MAX_ATTEMPTS==12,"humanoid node exposes a bounded configurable repair count")
	panel.parameter_form._set_parameter("max_repair_attempts",6)
	check(panel.parameter_form.parameters().get("max_repair_attempts",0)==6,"repair count edits are preserved as an integer parameter")
	panel.parameter_form._set_parameter("max_repair_attempts",3)
	var invalid_attempts = HumanoidRigNode.run(source,{"height_m":1.8,"max_repair_attempts":0},root,panel.state_dir.path_join("invalid-attempts.tscn"))
	check(invalid_attempts.get("code","")=="invalid_repair_attempts","repair count rejects zero instead of silently retrying")
	panel.run_node_preview("rig")
	print(panel.status.text)
	var entry: Dictionary = panel._latest_character_entry("rig")
	check(not entry.is_empty(),"local run records a character artifact")
	if entry.is_empty():
		print(panel.failure_text.text)
		await finish()
		return
	print(JSON.stringify(entry.get("provenance",{})))
	check(entry.get("provenance",{}).get("capability_limited",true)==false,"fixture passes the complete ROM validation")
	check(entry.get("provenance",{}).get("review_mode","")=="text_only" and entry.get("provenance",{}).get("text_review",{}).get("text_only",false),"post-rigging acceptance uses the text-only review flow")
	check(entry.get("provenance",{}).get("text_review",{}).get("synthetic",false),"offline text receipt is explicitly marked synthetic")
	check(entry.get("provenance",{}).get("validation",{}).get("bone_count",0)==18 and entry.get("provenance",{}).get("anatomical_bone_count",0)==17,"saved receipt distinguishes anatomical bones and root")
	check(FileAccess.file_exists(entry.path) and FileAccess.get_sha256(entry.path)==entry.artifact.revision,"character file exists with matching digest")
	check(FileAccess.get_sha256(source)==source_sha,"source GLB bytes are preserved")
	check(is_instance_valid(panel.preview_scene) and panel.preview_scene.get_node("Skeleton3D").get_bone_count()==18,"preview contains the actual Skeleton3D")
	var pose_player = panel.preview_scene.get_node("AnimationPlayer")
	var pose_skeleton = panel.preview_scene.get_node("Skeleton3D")
	pose_player.play("raise_arms")
	pose_player.advance(1.0)
	var forearm_rotation = pose_skeleton.get_bone_pose(pose_skeleton.find_bone("forearm_l")).basis.get_rotation_quaternion()
	var wrist_rotation = pose_skeleton.get_bone_pose(pose_skeleton.find_bone("hand_l")).basis.get_rotation_quaternion()
	check(forearm_rotation.is_equal_approx(Quaternion.from_euler(Vector3(0,0,.18))) and wrist_rotation.is_equal_approx(Quaternion.from_euler(Vector3(0,0,-.12))),"raise_arms retains elbow follow-through and wrist compensation tracks")
	pose_player.stop()
	pose_skeleton.reset_bone_poses()
	var character_key = ""
	for key in panel.artifact_nodes:
		if panel.artifact_nodes[key].get("kind","")=="character": character_key = key
	check(not character_key.is_empty(),"dynamic character preview card is created")
	if not character_key.is_empty():
		await wait_thumbnails()
		var card = panel.graph.get_node(panel.artifact_nodes[character_key].id)
		check(card.get_node("ArtifactCharacterPreview").mesh_count>0,"character card renders actual mesh and skeleton")
		check(card.get_input_port_count()==1 and card.get_input_port_type(0)==panel.PORT_CHARACTER and card.get_output_port_count()==1 and card.get_output_port_type(0)==panel.PORT_MESH,"character card adapts character input to an explicit Mesh output")
	var mesh_path = str(entry.get("mesh_path",""))
	var mesh_document = glb_json(mesh_path)
	check(FileAccess.file_exists(mesh_path) and FileAccess.get_sha256(mesh_path)==entry.get("mesh_snapshot",{}).get("content_sha256",""),"character stores an immutable rigged GLB snapshot")
	check(not mesh_document.get("skins",[]).is_empty() and '"JOINTS_0"' in JSON.stringify(mesh_document) and '"WEIGHTS_0"' in JSON.stringify(mesh_document),"exported garment input retains skins and vertex weights")
	var mesh_node_index = 0
	for index in mesh_document.get("nodes",[]).size():
		if mesh_document.nodes[index].has("mesh"):
			mesh_node_index = index
			break
	var split = {"id":"split","type":"garment_split","version":"1","provider":"garment-split","source":"","image_context":"","text":"","parameters":{"items":[{"id":"fixture","label":"夹具衣服","category":"garment","slot":"other","behavior":"skinned","confidence":1.0,"review_state":"confirmed","selection":{"mode":"reviewed_triangles","primitives":[{"node":mesh_node_index,"primitive":0,"triangles":[0]}]}}]},"x":800.0,"y":40.0}
	panel.nodes.append(split)
	var legacy_entry = entry.duplicate(true)
	legacy_entry.erase("mesh_path")
	legacy_entry.erase("mesh_snapshot")
	panel.preview_history["rig"] = [legacy_entry]
	root.size = Vector2i(2200,1200)
	panel.size = Vector2(2200,1200)
	panel.rebuild()
	var prepare_before: int = panel.character_mesh_prepare_count
	if not character_key.is_empty(): await drag_connection(panel.graph.get_node(panel.artifact_nodes[character_key].id),panel.graph.get_node("split"))
	check(panel.edges.size()==1 and panel.edges[0].get("artifact",{})==entry.artifact,"native mouse drag connects the explicit Mesh output to garment split")
	if panel.edges.is_empty() and not character_key.is_empty(): panel.connect_nodes(str(panel.artifact_nodes[character_key].id),0,"split",0)
	var prepare_frame = Engine.get_process_frames()
	await create_timer(0.02).timeout
	check(Engine.get_process_frames()>prepare_frame,"legacy character preparation keeps the main frame loop advancing")
	var prepare_deadline = Time.get_ticks_msec()+30000
	while panel.is_character_mesh_preparing() and Time.get_ticks_msec()<prepare_deadline: await process_frame
	check(panel.character_mesh_prepare_count==prepare_before+1 and not panel.is_character_mesh_preparing(),"legacy TSCN is backfilled once by the background worker")
	mesh_path = str(panel.artifact_nodes[character_key].entry.get("mesh_path","")) if not character_key.is_empty() else ""
	var recovered_document = glb_json(mesh_path)
	mesh_node_index = 0
	for index in recovered_document.get("nodes",[]).size():
		if recovered_document.nodes[index].has("mesh"):
			mesh_node_index = index
			break
	split.parameters.items[0].selection.primitives[0].node = mesh_node_index
	check(not mesh_path.is_empty() and not recovered_document.get("skins",[]).is_empty() and not legacy_entry.get("mesh_snapshot",{}).is_empty(),"legacy TSCN is backfilled with a rigged GLB during connection without rerunning")
	check(panel.edges.size()==1 and panel.edges[0].get("artifact",{})==entry.artifact,"character artifact connects to garment split as a fixed artifact")
	check(panel.graph.get_connection_list().any(func(edge): return str(edge.to_node)=="split"),"native graph renders the character-to-garment wire")
	var by_id = {}
	for node_data in panel.nodes: by_id[node_data.id] = node_data
	check(not panel.edges.is_empty() and panel._valid_workflow_edge(panel.edges[0],by_id),"character garment edge passes saved workflow validation")
	var executable = panel.execution_model()
	check(not executable.is_empty() and executable.nodes.all(func(data): return data.type!="humanoid_rig"),"garment execution reuses the local character instead of submitting the rig node")
	check(not executable.is_empty() and executable.edges.size()==1 and executable.edges[0].get("artifact_snapshot",{}).get("content_sha256","")==FileAccess.get_sha256(mesh_path) and executable.edges[0].get("artifact_snapshot",{}).get("extension","")==".glb","garment execution receives the exact rigged GLB bytes")
	double_click(panel.mesh_container)
	check(panel.rigging_panel.visible and not panel.graph.visible and is_instance_valid(panel.rigging_panel.built),"double-clicking the right preview opens rigging tab")
	check(panel.rigging_panel.built.get_node("Skeleton3D").get_bone_count()==18 and panel.rigging_panel.source==source,"binding tab reopens the character and matching source")
	panel.show_native_section("mesh")
	var downloaded = panel.state_dir.path_join("downloaded.tscn")
	panel.save_preview_to(downloaded)
	check(FileAccess.get_sha256(downloaded)==entry.artifact.revision,"character download preserves the TSCN bytes")
	panel.path_edit.text = panel.state_dir.path_join("workflow.json")
	panel.save_graph()
	check(FileAccess.file_exists(panel.path_edit.text),"workflow with character output saves")
	panel.open_graph()
	entry = panel._latest_character_entry("rig")
	check(not entry.is_empty() and FileAccess.file_exists(entry.path),"workflow reopen restores the character")
	check(not entry.is_empty() and FileAccess.file_exists(entry.get("source_path","")) and FileAccess.get_sha256(entry.get("source_path",""))==source_sha,"workflow reopen materializes the matching source GLB")
	check(not entry.is_empty() and FileAccess.file_exists(entry.get("mesh_path","")) and FileAccess.get_sha256(entry.mesh_path)==entry.get("mesh_snapshot",{}).get("content_sha256",""),"workflow reopen materializes the rigged GLB snapshot")
	check(panel.edges.size()==1 and panel.edges[0].get("to","")=="split" and panel._valid_workflow_edge(panel.edges[0],by_id),"workflow reopen preserves the character-to-garment connection")
	if not entry.is_empty():
		panel.load_preview(entry,"rig",entry.run)
		double_click(panel.mesh_container)
		check(panel.rigging_panel.visible and is_instance_valid(panel.rigging_panel.built),"restored character still opens in binding tab")
		panel.show_native_section("mesh")
		if not character_key.is_empty(): panel.rebuild()
	var restored_key = ""
	for key in panel.artifact_nodes:
		if panel.artifact_nodes[key].get("kind","")=="character": restored_key = key
	if not restored_key.is_empty():
		panel._open_character_artifact(restored_key)
		check(panel.rigging_panel.visible and is_instance_valid(panel.rigging_panel.built),"double-click action on the dynamic card opens binding tab")
		panel.show_native_section("mesh")
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	panel.run_node_preview("split")
	var garment_deadline = Time.get_ticks_msec()+30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec()<garment_deadline: await process_frame
	check(panel.current.get("nodes",{}).get("split",{}).get("state","")=="succeeded","reopened character connection executes the real garment split node")
	var split_entry = panel._latest_mesh_entry("split")
	var split_document = glb_json(str(split_entry.get("path","")))
	check(not split_entry.is_empty() and not split_document.get("skins",[]).is_empty() and '"JOINTS_0"' in JSON.stringify(split_document) and '"WEIGHTS_0"' in JSON.stringify(split_document),"real garment output preserves the character skeleton and skin weights")
	if split_entry.is_empty(): print(panel.status.text+"\n"+panel.failure_text.text)
	var missing = panel.state_dir.path_join("deleted.glb")
	data = panel.nodes.filter(func(node): return node.id=="rig")[0]
	data.source = missing
	data.source_paths = [missing]
	data.source_snapshots = [panel._snapshot_file(source)]
	panel.select_node("rig")
	var history_count = panel.preview_history.get("rig",[]).size()
	panel.run_node_preview("rig")
	check(panel.failure_dialog.visible and panel.failure_text.text.contains(missing),"deleted persisted source opens a native error dialog")
	check(data.source.is_empty() and data.source_paths==[""] and panel.preview_history.get("rig",[]).size()==history_count,"missing source is cleared without replacing valid history")
	panel.failure_dialog.hide()
	var triangle = ProjectSettings.globalize_path("res://fixtures/sample.glb")
	data.source = triangle
	data.source_paths = [triangle]
	data.source_snapshots = [panel._snapshot_file(triangle)]
	panel.select_node("rig")
	var rejected_input = panel._direct_humanoid_input("rig")
	panel.humanoid_review_node = "rig"
	panel.humanoid_review_source = triangle
	panel.humanoid_review_directory = "synthetic-ai-rejection"
	panel.humanoid_review_input = rejected_input.duplicate(true)
	panel._complete_humanoid_ai_review({"passed":false,"source_sha256":FileAccess.get_sha256(triangle),"issues":["Not a complete humanoid"]},{"directory":"synthetic-ai-rejection"})
	check(panel.failure_dialog.visible and panel.preview_history.get("rig",[]).size()==history_count,"AI-rejected non-human input cannot create an artifact")
	panel.failure_dialog.hide()
	# A formal upstream edge must execute only that upstream, then rig its real GLB.
	panel.python_edit.text = OS.get_environment("AINATIVE_PYTHON")
	panel.factory_edit.text = "editor_demo:factory"
	panel.host_edit.text = ProjectSettings.globalize_path("res://../../tools/ainative/editor_host.py")
	check(not panel.python_edit.text.is_empty(),"upstream acceptance has a Python runtime")
	if panel.python_edit.text.is_empty():
		await finish()
		return
	panel.controller.reset()
	panel.preview_history.clear()
	var upstream = {"id":"upstream","type":"copy","version":"1","provider":"local-copy","source":source,"image_context":"","text":"","parameters":{"delay":0,"fail":false},"x":30.0,"y":40.0}
	panel.nodes = [upstream,human_node("")]
	panel.edges = [{"from":"upstream","to":"rig","input":"source","output":"result"}]
	panel.rebuild()
	panel.select_node("rig")
	panel.run_node_preview("rig")
	var deadline = Time.get_ticks_msec()+30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec()<deadline: await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating,"upstream-driven local rig finishes")
	check(panel.current.get("state","")=="succeeded" and panel.current.get("nodes",{}).has("upstream") and not panel.current.get("nodes",{}).has("rig"),"executor runs the Mesh upstream but not the local-only rig")
	var upstream_entry = panel._latest_character_entry("rig")
	check(not upstream_entry.is_empty() and upstream_entry.get("provenance",{}).get("source_sha256","")==source_sha,"upstream GLB feeds the same validated rig output")
	check(not panel.preview_history.get("upstream",[]).is_empty(),"upstream preview remains independently available")
	panel.preview_history.clear()
	panel.start_run()
	deadline = Time.get_ticks_msec()+30000
	while (not panel.jobs.is_empty() or panel.auto_step or panel.creating) and Time.get_ticks_msec()<deadline: await process_frame
	check(panel.jobs.is_empty() and not panel.auto_step and not panel.creating,"whole-workflow run finishes with a local terminal node")
	check(not panel._latest_character_entry("rig").is_empty(),"whole-workflow run continues from upstream preview to local rig")
	# Persistent bone asymmetry exercises bounded repair and blocks normal delivery.
	panel.controller.reset()
	panel.preview_history.clear()
	var limited_source = ProjectSettings.globalize_path("res://fixtures/humanoid_limited.glb")
	panel.nodes = [human_node(limited_source)]
	panel.edges = []
	panel.rebuild()
	panel.select_node("rig")
	panel.run_node_preview("rig")
	var limited_entry = panel._latest_character_entry("rig")
	check(limited_entry.is_empty(),"unresolved local ROM issues cannot create a normal character artifact")
	check(panel.failure_dialog.visible and panel.failure_text.text.contains("已阻断正常角色交付"),"local ROM rejection opens an explicit blocking failure")
	check(panel.failure_text.text.contains("失败草稿"),"rejected candidate is retained only as a labeled manual draft")
	check(not panel.capability_notice_dialog.visible,"rejected local candidate does not reuse the capability-limited success dialog")
	panel.failure_dialog.hide()
	# A language-model rejection is blocked even when every local numeric gate passed.
	panel.controller.reset()
	panel.preview_history.clear()
	panel.humanoid_text_review_fixture = accepted_text_receipt()
	panel.humanoid_text_review_fixture.passed = false
	panel.humanoid_text_review_fixture.summary = "合成文本回执：仍有未解决问题。"
	panel.humanoid_text_review_fixture.issues = [{"code":"synthetic_text_rejection","stage":"capability","check":"text_review","message":"合成文本审核未通过。","actual":null,"threshold":null,"target":"rigging_node"}]
	panel.humanoid_text_review_fixture.feedback = [{"node":"humanoid_rig","control":"fit","code":"synthetic_text_rejection"}]
	panel.nodes = [human_node(source)]
	panel.edges = []
	panel.rebuild()
	panel.select_node("rig")
	panel.run_node_preview("rig")
	var text_rejected = panel._latest_character_entry("rig")
	check(text_rejected.is_empty(),"text rejection cannot create a normal character artifact")
	check(panel.failure_dialog.visible and panel.failure_text.text.contains("合成文本回执"),"text-only rejection reaches the blocking failure dialog")
	check(not panel.capability_notice_dialog.visible,"text rejection does not reuse the capability-limited success dialog")
	panel.failure_dialog.hide()
	await finish()

func finish():
	print("AINATIVE_HUMANOID_NODE failures="+str(failures))
	if OS.has_environment("AINATIVE_HUMANOID_REPORT"):
		var file = FileAccess.open(OS.get_environment("AINATIVE_HUMANOID_REPORT"),FileAccess.WRITE)
		file.store_string(JSON.stringify({"passed":failures==0,"failures":failures,"checks":checks},"  "))
		file.close()
	panel.queue_free()
	await process_frame
	quit(1 if failures else 0)
