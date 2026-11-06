extends SceneTree
const I=preload('res://addons/ainative/interop.gd')
const L=preload('res://addons/ainative/layering.gd')
var failures=[]
func check(ok,label):
	if not ok: failures.append(label)
func globals(sk):
	sk.force_update_all_bone_transforms()
	var out=[]
	for i in sk.get_bone_count():out.append(sk.get_bone_global_pose(i))
	return out
func _initialize():call_deferred('run')
func run():
	var scene=I.load_scene(OS.get_cmdline_user_args()[0]).scene
	root.add_child(scene)
	var runner=scene.get_node('LayeringPlayer')
	runner.playing=false
	var sk=I.skeleton(scene)
	var config=runner.config.duplicate(true)
	runner.sample(.5)
	var gripping=globals(sk)
	var base=L.capture(sk)
	runner.config.fingers={}
	runner.sample(.5)
	var released=globals(sk)
	var finger_weights={}
	var weighted=0
	var max_delta=0.0
	for mi in scene.find_children('*','MeshInstance3D',true,false):
		if mi.skin==null:continue
		for si in mi.mesh.get_surface_count():
			var a=mi.mesh.surface_get_arrays(si)
			var n=a[Mesh.ARRAY_VERTEX].size()
			var stride=int(a[Mesh.ARRAY_WEIGHTS].size()/n)
			for vi in n:
				var delta=Vector3.ZERO
				var has_finger=false
				for k in stride:
					var off=vi*stride+k
					var w=a[Mesh.ARRAY_WEIGHTS][off]
					if w<=0:continue
					var bid=a[Mesh.ARRAY_BONES][off]
					var bi=mi.skin.get_bind_bone(bid)
					if mi.skin.get_bind_name(bid)!='':bi=sk.find_bone(mi.skin.get_bind_name(bid))
					if str(sk.get_bone_name(bi)) in config.fingers:
						has_finger=true
						finger_weights[str(sk.get_bone_name(bi))]=true
					var p=mi.skin.get_bind_pose(bid)*a[Mesh.ARRAY_VERTEX][vi]
					delta+=(gripping[bi]*p-released[bi]*p)*w
				if has_finger:
					weighted+=1
					max_delta=maxf(max_delta,delta.length())
	check(finger_weights.size()==30 and weighted>0 and max_delta>.001,'actual fingers deform weighted mesh')
	var bads=[]
	for field in ['layers','equipment','fingers']:
		var c=config.duplicate(true)
		c[field]=1
		bads.append(c)
	for field in ['priority','weight']:
		var c=config.duplicate(true)
		c.layers[0][field]='invalid'
		bads.append(c)
	var c=config.duplicate(true)
	c.fingers[config.fingers.keys()[0]]=[0,0,0,0]
	bads.append(c)
	c=config.duplicate(true)
	c.equipment.main_hand=c.equipment.off_hand
	bads.append(c)
	for bad in bads:
		var before=L.capture(sk)
		var r=L.evaluate(sk,base,bad,.5)
		check(r.has('error'),'bad config rejected')
		check(L.capture(sk)==before,'invalid input atomic')
	c=config.duplicate(true)
	c.layers=[{'id':'no-mask','priority':10,'pose':{}}]
	var before_missing = L.capture(sk)
	var missing_result = L.evaluate(sk,base,c,.5)
	check(missing_result.has('error') and L.capture(sk)==before_missing,'missing mask rejected atomically')
	c=config.duplicate(true)
	c.layers[0].mask.append(c.layers[0].mask[0])
	check(L.evaluate(sk,base,c,.5).has('error') and L.capture(sk)==before_missing,'duplicate mask rejected atomically')
	check(L.evaluate(sk,base,config,NAN).has('error') and L.capture(sk)==before_missing,'nonfinite time rejected atomically')
	var full=config.duplicate(true)
	var mask=[]
	for i in sk.get_bone_count():mask.append(str(sk.get_bone_name(i)))
	full.layers.append({'id':'full','priority':100,'weight':1,'full_body':true,'mask':mask,'pose':{}})
	var result=L.evaluate(sk,base,full,.5)
	check(not result.has('error') and result.ik.is_empty(),'full priority suppresses IK')
	for i in sk.get_bone_count():check(sk.get_bone_pose(i).is_equal_approx(base[i]),'full restores base')
	print(JSON.stringify({'finger_bones_with_weights':finger_weights.size(),'finger_weighted_vertices':weighted,'finger_only_deformation_m':max_delta,'negative_cases':bads.size(),'failures':failures}))
	scene.free()
	quit(0 if failures.is_empty() else 1)
