extends SceneTree
const Session = preload('res://addons/ainative/character_session.gd')
func _initialize(): run.call_deferred()
func run():
	var args = OS.get_cmdline_user_args()
	var host = load('res://addons/ainative/workbench.gd').new()
	root.add_child(host)
	var panel = host.find_child('CharacterWorkbench',true,false)
	panel.local_config = Session.read_object(args[0])
	panel.destination.text = args[1]
	panel.reopen()
	assert(is_instance_valid(panel.session.live),panel.last_error)
	var hair = panel.session.live.get_node('IndependentHair')
	var digest = hair.config.binding_digest
	panel.mouth.value = .6
	panel.gaze.value = -.4
	panel.apply_expression()
	assert(panel.last_error.is_empty(),panel.last_error)
	assert(hair.config.binding_digest==digest)
	panel.hair_lod.select(2)
	panel.hat.button_pressed = true
	panel.hair_options()
	assert(hair.config.lod==2 and hair.config.hat)
	var previous = panel.session.live
	panel.body.value = .95
	panel.apply_shape()
	assert(panel.last_error.is_empty(),panel.last_error)
	assert(panel.session.live!=previous)
	var cloth = panel.session.live.get_node('ClothSolver')
	assert(cloth.cache.is_empty() and cloth.mode=='realtime')
	hair = panel.session.live.get_node('IndependentHair')
	assert(hair.config.lod==2 and hair.config.hat)
	assert(hair.config.binding_digest!=digest)
	assert(panel.session.recipe.face_layers[0].channels.jawOpen==.6)
	print(JSON.stringify({'ok':true,'expression_keeps_hair_binding':true,'shape_invalidates_cloth_cache':true,'hair_display_survives_shape':true,'manual_expression_survives_shape':true}))
	host.free()
	quit()
