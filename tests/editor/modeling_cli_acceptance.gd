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
	print("MODELING_CLI_ACCEPTANCE_OK" if ok else "MODELING_CLI_ACCEPTANCE_FAILED")
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
func idle(seconds: float = 900.0) -> bool:
	var deadline=Time.get_ticks_msec()+int(seconds*1000)
	while panel.is_graph_busy() and Time.get_ticks_msec()<deadline: await create_timer(.1).timeout
	return verify(not panel.is_graph_busy(),"native host operation completed")
func run():
	var value=JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("MALIANG_MODELING_ACCEPTANCE")))
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
	var mode_index=-1
	for i in panel.service_choice.item_count:
		if panel.service_choice.get_item_metadata(i)=="codex_modeling": mode_index=i
	if not verify(mode_index>=0,"GPT instruction modeling mode available"): return
	panel.service_choice.select(mode_index); panel._service_settings_changed(); panel.save_service_settings()
	if not verify(panel.service_saved.get("mode")=="codex_modeling","dedicated CLI modeling config saved"): return
	if not verify(not panel.managed_comfy_panel.visible and panel.managed_comfy_panel.lease_path.is_empty(),"ComfyUI runtime is neither visible nor started"): return
	panel.check_service()
	if not await idle(60): return
	if not verify(panel.service_report.get("capabilities",{}).get("text_to_mesh",{}).get("ready",false),"CLI modeling capability ready without mesh server"): return
	panel.nodes.clear(); panel.edges.clear(); panel.rebuild()
	for i in panel.generator_choice.item_count:
		if panel.generator_choice.get_item_metadata(i)=="text_to_mesh": panel.generator_choice.select(i)
	panel.add_generator()
	var mesh_id=panel.selected_id
	panel.parameter_form.configure("text_to_mesh",{"prompt":"A small friendly toy robot built from simple shapes, blue torso, silver spherical head, two arms and two legs, orange eyes. Standing upright on the ground. Keep the parts visually connected and proportional. No ground plane."})
	if not verify(panel.apply_fields(),"node modeling prompt accepted"): return
	panel.add_node()
	var copy_id=panel.selected_id
	panel.edges=[{"from":mesh_id,"to":copy_id}]; panel.rebuild(); panel.select_node(copy_id)
	panel.path_edit.text=config.output.path_join("workflow.json"); panel.save_graph()
	if not verify(FileAccess.file_exists(panel.path_edit.text),"linked node workflow saved"): return
	panel.run_node_preview(copy_id)
	if not await idle(): return
	result["run_id"]=panel.run_id
	result["state"]=panel.current
	if not verify(panel.current.get("state")=="succeeded","real CLI modeling and connected copy nodes succeed"): return
	if not verify(panel.preview_scene!=null and panel.preview_node==copy_id,"generated GLB loaded in downstream node preview"): return
	var history: Array=panel.preview_history.get(copy_id,[])
	if not verify(not history.is_empty(),"node result retained in preview history"): return
	result["preview"]=history.back()
	DirAccess.copy_absolute(history.back().path,config.output.path_join("robot.glb"))
	var vertices=0
	for mesh in panel.preview_scene.find_children("*","MeshInstance3D",true,false):
		if mesh.mesh!=null:
			for surface in mesh.mesh.get_surface_count(): vertices+=mesh.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX].size()
	result["vertices"]=vertices
	if not verify(vertices>0,"generated Mesh contains actual vertices"): return
	panel.target_edit.text=config.output.path_join("robot.tscn"); panel.review_publish()
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
