extends SceneTree
# Replays a real generated source through the character panel; performs no inference.
var panel
var failures=0
func check(ok: bool, label: String):
	print(('PASS ' if ok else 'FAIL ')+label)
	if not ok: failures+=1
func idle():
	var deadline=Time.get_ticks_msec()+60000
	while not panel.jobs.is_empty() and Time.get_ticks_msec()<deadline: await process_frame
	check(panel.jobs.is_empty(),'background host returned')
func _initialize(): call_deferred('run')
func run():
	var args=OS.get_cmdline_user_args()
	if args.size()!=4:
		printerr('Expected live-runs.json params.json NEW-screenshot.png NEW-receipt.json')
		quit(2); return
	if FileAccess.file_exists(args[2]) or FileAccess.file_exists(args[3]):
		printerr('Choose new screenshot and receipt destinations')
		quit(2); return
	var records=JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not records is Array: quit(2); return
	var record: Dictionary={}
	for r in records:
		if r.kind=='image_to_mesh': record=r
	var p=JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	if record.is_empty() or not p is Dictionary: quit(2); return
	panel=load('res://addons/ainative/workbench.gd').new()
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	await process_frame
	panel.python_edit.text=OS.get_environment('AINATIVE_PYTHON')
	panel.host_edit.text=ProjectSettings.globalize_path('res://../../tools/ainative/editor_host.py')
	panel.factory_edit.text='comfy_provider:factory'
	panel.state_dir=ProjectSettings.globalize_path('user://rig-ui-'+str(Time.get_ticks_usec()))
	DirAccess.make_dir_recursive_absolute(panel.state_dir)
	panel.db=record.db
	panel.run_id=record.run_id
	panel.selected_id='generate'
	panel.launch('status',{'run':record.run_id})
	await idle()
	var valid_run=panel.current.get('state')=='succeeded' and panel.current.get('id')==record.run_id
	check(valid_run,'actual generated source run identity')
	if not valid_run: quit(1); return
	var node=panel.current.nodes.generate
	var valid_node=node.get('provider')=='comfy' and node.get('request',{}).get('node')=='image_to_mesh'
	check(valid_node,'actual source provider and node capability')
	if not valid_node: quit(1); return
	panel.nodes=[{'id':'generate','type':'image_to_mesh','version':node.request.version,'provider':'comfy','source':'','image_context':'','text':'','parameters':node.request.parameters,'x':40,'y':60}]
	panel.edges=[]
	panel.rebuild()
	panel.select_node('generate')
	panel.request_preview()
	await idle()
	var rig=panel.rigging_panel
	var before=FileAccess.get_sha256(rig.source)
	check(before==p.source_sha256,'rig source matches actual generated artifact')
	rig.route.select(1)
	rig.height.value=p.height_m
	rig.crop.value=p.crop_below_y
	rig.clean.button_pressed=p.clean_faces
	rig.confirm.button_pressed=true
	rig.corrections.text=JSON.stringify({'joints':p.joints,'weights':p.weights,'reference_pose':p.reference_pose,'yaw_degrees':p.yaw_degrees})
	rig.fit()
	var applied_params=rig.params.duplicate(true)
	check(is_instance_valid(rig.built) and rig.built.get_meta('rigging').status=='reviewed_template','actual panel fitting and diagnostics')
	check(panel.preview_token.is_empty(),'derived rig cannot use original mesh publication approval')
	rig.play('squat')
	rig.built.get_node('AnimationPlayer').advance(1.0)
	rig.built.get_node('AnimationPlayer').pause()
	rig.target.text=panel.state_dir.path_join('robot.tscn')
	rig.save_version()
	check(FileAccess.file_exists(rig.target.text),'panel publishes immutable rig scene')
	var saved_hash=FileAccess.get_sha256(rig.target.text)
	rig.save_version()
	check(saved_hash==FileAccess.get_sha256(rig.target.text),'repeat publication preserves destination')
	rig.reopen()
	check(rig.params.joints==applied_params.joints and rig.params.reference_pose==applied_params.reference_pose,'reopen preserves applied marked pose and corrections')
	var sk=rig.built.get_node('Skeleton3D')
	var rest_error=0.0
	var rest_basis=true
	for i in sk.get_bone_count():
		rest_error=maxf(rest_error,sk.get_bone_pose(i).origin.distance_to(sk.get_bone_rest(i).origin))
		rest_basis=rest_basis and sk.get_bone_pose(i).basis.is_equal_approx(sk.get_bone_rest(i).basis)
	check(rest_error<0.00001 and rest_basis,'published playing character reopens in full reference transform')
	check(FileAccess.get_sha256(rig.source)==before,'source bytes preserved')
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(args[2])
	var result={'failures':failures,'source_run':record.run_id,'source_sha256':before,'scene_sha256':saved_hash,'scene':rig.target.text,'parameters':rig.params}
	var file=FileAccess.open(args[3],FileAccess.WRITE)
	file.store_string(JSON.stringify(result,'\t'))
	file.close()
	print('AINATIVE_RIG_UI failures='+str(failures))
	quit(1 if failures else 0)
