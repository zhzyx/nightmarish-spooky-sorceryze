@tool
extends SceneTree
# Explicit real-CLI acceptance. Native controls, no ComfyUI, isolated project.
var panel
var checks: Array = []
var config: Dictionary
var result: Dictionary = {}
func _initialize(): run.call_deferred()
func finish(ok: bool):
	var output = FileAccess.open(config.output.path_join("acceptance.json"), FileAccess.WRITE)
	output.store_string(JSON.stringify({"ok":ok,"checks":checks,"result":result},"  ")); output.close()
	print("SCULPT_CLI_ACCEPTANCE_OK" if ok else "SCULPT_CLI_ACCEPTANCE_FAILED")
	if is_instance_valid(panel): panel.queue_free()
	await process_frame
	quit(0 if ok else 1)
func verify(value: bool, label: String) -> bool:
	checks.append({"passed":value,"label":label})
	print(("PASS " if value else "FAIL ")+label)
	if not value:
		if panel!=null: result["status"]=panel.status.text
		finish(false)
	return value
func idle(seconds: float = 1300.0) -> bool:
	var deadline=Time.get_ticks_msec()+int(seconds*1000)
	while panel.is_graph_busy() and Time.get_ticks_msec()<deadline: await create_timer(.1).timeout
	return verify(not panel.is_graph_busy(),"native host operation completed")
func run():
	var value=JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("MALIANG_SCULPT_ACCEPTANCE")))
	if not value is Dictionary or value.get("real_cli_authorized")!=true:
		push_error("Explicit real CLI config required"); quit(2); return
	config=value
	DirAccess.make_dir_recursive_absolute(config.output)
	var deadline=Time.get_ticks_msec()+30000
	var dock
	while dock==null and Time.get_ticks_msec()<deadline:
		dock=root.find_child("AINative",true,false); await process_frame
	if not verify(dock!=null,"native Maliang entry exists"): return
	var tabs: TabContainer=dock.get_parent()
	tabs.current_tab=tabs.get_tab_idx_from_control(dock)
	deadline=Time.get_ticks_msec()+30000
	while panel==null and Time.get_ticks_msec()<deadline:
		panel=dock.find_child("AINativeWorkbench",true,false); await process_frame
	if not verify(panel!=null,"native bundled workbench loaded"): return
	panel.python_edit.text=config.python
	panel.cli_path_edit.text=config.cli
	panel.blender_path_edit.text=config.blender
	var mode_index=-1
	for i in panel.service_choice.item_count:
		if panel.service_choice.get_item_metadata(i)=="codex_sculpt": mode_index=i
	if not verify(mode_index>=0,"GPT complex modeling mode available"): return
	panel.service_choice.select(mode_index); panel._service_settings_changed(); panel.save_service_settings()
	if not verify(panel.service_saved.get("mode")=="codex_sculpt","dedicated CLI sculpt config saved"): return
	if not verify(not panel.managed_comfy_panel.visible and panel.managed_comfy_panel.lease_path.is_empty(),"ComfyUI runtime is neither visible nor started"): return
	panel.check_service()
	if not await idle(60): return
	if not verify(panel.service_report.get("capabilities",{}).get("text_to_mesh",{}).get("ready",false),"CLI modeling capability ready without mesh server"): return
	panel.nodes.clear(); panel.edges.clear(); panel.rebuild()
	var kind="image_to_mesh" if not str(config.get("source", "")).is_empty() else "text_to_mesh"
	for i in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(i)==kind: panel.generator_choice.select(i)
	panel.add_generator()
	var mesh_id=panel.selected_id
	panel.source_edit.text=str(config.get("source", ""))
	panel.context_edit.text=str(config.get("reference", ""))
	panel.parameter_form.configure(kind,{"prompt":config.subject})
	if not verify(panel.apply_fields(),"node modeling prompt accepted"): return
	panel.add_node()
	var copy_id=panel.selected_id
	panel.nodes[0].x=80;panel.nodes[0].y=120;panel.nodes[1].x=480;panel.nodes[1].y=120
	panel.edges=[{"from":mesh_id,"to":copy_id}]; panel.rebuild(); panel.select_node(copy_id)
	panel.path_edit.text=config.output.path_join("workflow.json"); panel.save_graph()
	if not verify(FileAccess.file_exists(panel.path_edit.text),"linked node workflow saved"): return
	panel.run_node_preview(copy_id)
	if not await idle(): return
	result["run_id"]=panel.run_id
	result["visual_acceptance"]="pending_separate_multiview_inspection"
	result["node_states"]={}
	for node in panel.current.get("nodes",{}): result.node_states[node]=panel.current.nodes[node].get("state")
	for artifact in panel.current.get("manifest",{}).get("artifacts",[]):
		var provenance: Dictionary=artifact.get("payload",{}).get("provenance",{})
		if provenance.get("provider")=="codex-sculpt": result["provenance"]=provenance
	if not verify(panel.current.get("state")=="succeeded","real CLI sculpt and connected copy nodes succeed"): return
	var provenance: Dictionary=result.get("provenance",{})
	if not verify(provenance.get("provider")=="codex-sculpt" and not provenance.get("generated_code_executed",true),"output provenance binds fixed interpreter and data-only model response"): return
	var cli_receipt: Dictionary=provenance.get("instruction_receipt",{})
	if not str(config.get("reference", "")).is_empty():
		var reference_images: Array=cli_receipt.get("reference_images",[])
		if not verify(reference_images.size()==2 and cli_receipt.get("distinct_reference_images",0)==2,"both distinct reference sheets reached actual CLI request"): return
		if not verify(reference_images[0].get("reference_sha256","")==FileAccess.get_sha256(config.source) and reference_images[1].get("reference_sha256","")==FileAccess.get_sha256(config.reference),"source and reference ordering and exact reference digests retained"): return
		if not verify(reference_images[0].role=="source" and reference_images[1].role=="reference","source and reference semantic roles retained"): return
	if int(config.get("expect_sheet_directions", 0)) > 0:
		var images: Array = cli_receipt.get("reference_images", [])
		var sheet: Dictionary = cli_receipt.get("sheet_view_evidence", {})
		if not verify(cli_receipt.get("distinct_reference_images") == 1 and images.size() == 1 and images[0].get("reference_sha256") == FileAccess.get_sha256(config.source), "one original sheet reached CLI with its exact file bytes"): return
		if not verify(sheet.get("source_sha256") == FileAccess.get_sha256(config.source) and sheet.get("distinct_named_directions") == config.expect_sheet_directions, "reported panel directions agree with observed sheet and repeated views count once"): return
		if not verify(sheet.get("source") == "cli_observed_panels" and not provenance.get("exact_hidden_surface_recovery_claimed", true), "sheet evidence distinguishes model observations from hidden surface recovery"): return
	var calibration: Dictionary=cli_receipt.get("operator_calibration",{})
	if not verify(calibration.get("role")=="internal_fixed_operator_calibration" and calibration.get("user_reference",true)==false and calibration.get("image_sha256","")==config.get("expected_calibration_png_sha256","") and not str(config.get("expected_calibration_png_sha256","")).is_empty(),"actual CLI receipt binds the separate internal baseline purpose and exact PNG digest"): return
	var user_images: Array=cli_receipt.get("reference_images",[])
	if not verify(user_images.size()<=2 and calibration.get("attachment_index",0)==user_images.size()+1 and not calibration.has("content_base64") and not calibration.has("content_sha256"),"internal baseline follows user attachments without polluting target reference evidence or inline assets"): return
	if not verify(panel.preview_scene!=null and panel.preview_node==copy_id,"generated GLB loaded in downstream node preview"): return
	var history: Array=panel.preview_history.get(copy_id,[])
	if not verify(not history.is_empty(),"node result retained in preview history"): return
	result["preview"]=history.back()
	DirAccess.copy_absolute(history.back().path,config.output.path_join("asset.glb"))
	var vertices=0
	for mesh in panel.preview_scene.find_children("*","MeshInstance3D",true,false):
		if mesh.mesh!=null:
			for surface in mesh.mesh.get_surface_count(): vertices+=mesh.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX].size()
	result["vertices"]=vertices
	if config.get("expect_registered_surface", false):
		var builder: Dictionary = provenance.get("builder_receipt", {})
		if not verify(builder.get("construction_operator") == "registered_turnaround", "the registered surface operator built this GLB"): return
		var registered: Dictionary = builder.get("quality", {}).get("registered_surface", {})
		if not verify(registered.get("source_sha256") == FileAccess.get_sha256(config.source), "registered geometry and color bind the original user image"): return
		if config.get("expect_registered_face", false):
			if not verify(registered.get("face_geometry", {}).get("applied") == true, "the registered face was fitted in mesh geometry"): return
		var imported_colors := 0
		var varying_colors := false
		for item in panel.preview_scene.find_children("*", "MeshInstance3D", true, false):
			if item.mesh == null: continue
			for index in item.mesh.get_surface_count():
				var arrays: Array = item.mesh.surface_get_arrays(index)
				if arrays[Mesh.ARRAY_COLOR] is PackedColorArray:
					var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
					imported_colors += colors.size()
					for color in colors:
						if not color.is_equal_approx(colors[0]):
							varying_colors = true
							break
		if not verify(imported_colors == vertices and varying_colors, "Godot imported varying surface colors for every registered vertex"): return
		var camera := panel.preview_root.get_child(0) as Camera3D
		var initial := camera.transform
		var drag := InputEventMouseMotion.new()
		drag.button_mask = MOUSE_BUTTON_MASK_LEFT
		drag.relative = Vector2(210, 16)
		panel.mesh_container.gui_input.emit(drag)
		if not verify(not camera.transform.is_equal_approx(initial), "drag rotates the preview camera around the model"): return
		var before_zoom := camera.position.distance_to(panel.mesh_focus)
		var wheel := InputEventMouseButton.new()
		wheel.button_index = MOUSE_BUTTON_WHEEL_UP
		wheel.pressed = true
		panel.mesh_container.gui_input.emit(wheel)
		if not verify(camera.position.distance_to(panel.mesh_focus) < before_zoom, "wheel zooms in on the native mesh"): return
		var initial_focus: Vector3 = panel.mesh_focus
		drag.button_mask = MOUSE_BUTTON_MASK_MIDDLE
		drag.relative = Vector2(0, 65)
		panel.mesh_container.gui_input.emit(drag)
		if not verify(not initial_focus.is_equal_approx(panel.mesh_focus), "middle drag pans to inspect a model detail"): return
		var reset := InputEventMouseButton.new()
		reset.button_index = MOUSE_BUTTON_LEFT
		reset.pressed = true
		reset.double_click = true
		panel.mesh_container.gui_input.emit(reset)
		if not verify(camera.transform.is_equal_approx(initial), "double click restores the original camera frame"): return
	if not verify(vertices>0,"generated Mesh contains actual vertices"): return
	panel.target_edit.text=config.output.path_join("asset.tscn"); panel.review_publish()
	if not verify(not panel.confirmation.is_empty(),"mesh scene publication reviewed"): return
	panel.confirm_publish()
	if not await idle(45): return
	if not verify(FileAccess.file_exists(panel.target_edit.text),"generated scene published"): return
	panel.path_edit.text=config.output.path_join("workflow.json"); panel.open_graph()
	if not verify(panel.nodes.size()==2 and panel.edges.size()==1,"workflow reopen preserves both nodes and edge"): return
	panel.select_node(copy_id); panel.load_preview(result.preview,copy_id,result.run_id)
	if not verify(panel.preview_scene!=null,"saved output reopens without another CLI request"): return
	if config.get("capture",false):
		panel.show_native_section("mesh")
		await create_timer(.5).timeout
		await RenderingServer.frame_post_draw
		if not verify(root.get_texture().get_image().save_png(config.output.path_join("native-preview.png"))==OK,"native preview screenshot saved"): return
	finish(true)
