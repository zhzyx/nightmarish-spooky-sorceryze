extends SceneTree
func _initialize(): run.call_deferred()
func press(panel, text):
	for button in panel.find_children('*','Button',true,false):
		if button.text==text: button.pressed.emit(); return
	assert(false,'Missing normal UI control: '+text)
func run():
	var args = OS.get_cmdline_user_args()
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	host.python_edit.text = args[2]
	var panel = host.find_child('CharacterWorkbench',true,false)
	assert(panel!=null)
	panel.source.text = args[0]
	press(panel,'Choose character')
	assert(is_instance_valid(panel.session.live),panel.message.text)
	print('LOAD: '+panel.message.text)
	panel.body.value = 1.05
	panel.face.value = .15
	press(panel,'Apply body and face')
	assert(panel.session.recipe.body.chest==1.05,panel.message.text)
	panel.wardrobe.select(1)
	press(panel,'Change clothes')
	assert(panel.session.live.has_node('Garment'),panel.message.text)
	panel.hair_enabled.button_pressed = true
	assert(panel.session.live.has_node('IndependentHair'),panel.message.text)
	print('HAIR: '+panel.message.text)
	panel.wardrobe.select(3)
	press(panel,'Change clothes')
	assert(panel.session.recipe.garment.spec.id=='skirt',panel.message.text)
	print('SKIRT: '+panel.message.text)
	panel.cloth_enabled.button_pressed = true
	assert(panel.session.live.has_node('ClothSolver'),panel.message.text)
	print('CLOTH: '+panel.message.text)
	var hair_revision = panel.session.live.get_node('IndependentHair').config.binding_digest
	for frame in 4:
		panel.session.clock_seconds = frame/60.0
		panel.session.evaluate(1.0/60.0)
		assert(not panel.session.live.get_node('ClothSolver').result.has('error'))
	assert(panel.session.live.get_node('IndependentHair').config.binding_digest==hair_revision)
	panel.session.clock_seconds = .5
	panel.session.evaluate(0.0)
	var before = panel.session.live
	var invalid = panel.session.recipe.duplicate(true)
	invalid.source_sha256 = '0'.repeat(64)
	assert(not panel.session.rebuild(invalid).is_empty())
	assert(panel.session.live==before)
	# Actual host-provider import failure must not displace the shared character.
	host.factory_edit.text = 'missing_integration_provider:factory'
	host.start_run()
	while not host.jobs.is_empty(): await process_frame
	assert(panel.session.live==before)
	panel.destination.text = args[1]
	press(panel,'Save character version')
	assert(FileAccess.file_exists(args[1]),panel.message.text)
	print('SAVE: '+panel.message.text)
	var saved_sha = FileAccess.get_sha256(args[1])
	press(panel,'Save character version')
	assert(FileAccess.get_sha256(args[1])==saved_sha and panel.session.live==before)
	press(panel,'Reopen character version')
	assert(panel.session.live!=before,panel.message.text)
	print('REOPEN: '+panel.message.text)
	assert(panel.session.live.has_node('Garment'))
	assert(panel.session.live.has_node('IndependentHair'))
	assert(panel.session.live.has_node('ClothSolver'))
	assert(panel.session.clock_seconds==.5)
	panel.wardrobe.select(2)
	press(panel,'Change clothes')
	assert(panel.session.recipe.garment.spec.id=='armor',panel.message.text)
	print(JSON.stringify({'ok':true,'generation':panel.session.generation,'frame_cpu_usec':panel.session.frame_usec,'saved_sha256':FileAccess.get_sha256(args[1]),'scope':'Same-character UI body/face/clothes/MDM/layers/hair/cloth/save/reopen; external target validation separate'}))
	host.free()
	quit()
