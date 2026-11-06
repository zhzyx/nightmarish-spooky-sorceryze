extends SceneTree
const Customization = preload('res://addons/ainative/customization.gd')
func _initialize():
	var dna = Customization.dna('a'.repeat(64),{'chest':1.0},{'face_width':.5})
	assert(Customization.validate(dna)=='')
	for invalid in [NAN,INF,-.501,.501,'0.2',true]:
		assert(Customization.validate(Customization.dna('a'.repeat(64),{}, {'face_width':invalid}))!='')
	assert(Customization.validate(Customization.dna('a'.repeat(64),{'chest':1.21},{}))!='')
	assert(Customization.validate(Customization.dna('a'.repeat(64),{}, {'unknown':0}))!='')
	var mixed = Customization.arbitrate([{'id':'expression','priority':0,'channels':{'jawOpen':.7,'mouthFrown':.5}}, {'id':'viseme-manual','priority':10,'channels':{'jawOpen':.2}}])
	assert(is_equal_approx(mixed.channels.jawOpen,.2))
	assert(mixed.owners.jawOpen=='viseme-manual' and mixed.head_neck_writes==0)
	assert(Customization.arbitrate([null]).has('error'))
	assert(Customization.arbitrate([{'channels':{'head':1}}]).has('error'))
	assert(Customization.arbitrate([{'channels':{'jawOpen':INF}}]).has('error'))
	var profile = {'revision':'profile-v1'}
	var first = Customization.garment_cache_key(dna,profile,{'version':'v1'})
	assert(first!=Customization.garment_cache_key(Customization.dna('a'.repeat(64),{'chest':1.1},{}),profile,{'version':'v1'}))
	assert(first!=Customization.garment_cache_key(dna,profile,{'version':'v2'}))
	print('CharacterDNA and face arbitration contracts passed')
	quit()
