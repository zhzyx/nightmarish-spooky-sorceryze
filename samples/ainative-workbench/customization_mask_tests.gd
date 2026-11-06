extends SceneTree
const I = preload('res://addons/ainative/interop.gd')
const A = preload('res://customization_assemble.gd')
func _initialize(): run.call_deferred()
func run():
 var config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
 var native = I.load_scene(config.body).scene
 var assembled = I.load_scene(config.output).scene
 root.add_child(native); root.add_child(assembled)
 var mask = JSON.parse_string(FileAccess.get_file_as_string(config.head_mask))
 assert(A.validate_mask(native,mask,FileAccess.get_sha256(config.body))=='')
 var bad = mask.duplicate(true); bad.source_sha256 = 'wrong'
 assert(A.validate_mask(native,bad,FileAccess.get_sha256(config.body))!='')
 bad = mask.duplicate(true); bad.surfaces[0].triangles.append(-1)
 assert(A.validate_mask(native,bad,FileAccess.get_sha256(config.body))!='')
 bad = mask.duplicate(true); bad.surfaces[0].triangles.append(bad.surfaces[0].triangles[0])
 assert(A.validate_mask(native,bad,FileAccess.get_sha256(config.body))!='')
 var sk = I.skeleton(native); var target_sk = I.skeleton(assembled)
 assert(sk.get_bone_count()==target_sk.get_bone_count())
 for b in sk.get_bone_count():
  assert(sk.get_bone_name(b)==target_sk.get_bone_name(b))
  assert(sk.get_bone_parent(b)==target_sk.get_bone_parent(b))
  assert(sk.get_bone_rest(b)==target_sk.get_bone_rest(b))
 var removed = 0; var kept = 0; var normal_error = 0.0; var tangent_error = 0.0
 for mi in native.find_children('*','MeshInstance3D',true,false):
  var target = assembled.get_node(native.get_path_to(mi))
  assert(mi.skin.get_bind_count()==target.skin.get_bind_count())
  for b in mi.skin.get_bind_count():
   assert(mi.skin.get_bind_bone(b)==target.skin.get_bind_bone(b))
   assert(mi.skin.get_bind_pose(b)==target.skin.get_bind_pose(b))
  for surface in mi.mesh.get_surface_count():
   var a = mi.mesh.surface_get_arrays(surface); var t = target.mesh.surface_get_arrays(surface)
   for slot in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_BONES,Mesh.ARRAY_WEIGHTS]: assert(a[slot]==t[slot])
   for v in a[Mesh.ARRAY_NORMAL].size(): normal_error = maxf(normal_error,a[Mesh.ARRAY_NORMAL][v].distance_to(t[Mesh.ARRAY_NORMAL][v]))
   for v in a[Mesh.ARRAY_TANGENT].size(): tangent_error = maxf(tangent_error,absf(a[Mesh.ARRAY_TANGENT][v]-t[Mesh.ARRAY_TANGENT][v]))
   var hide = {}
   for e in mask.surfaces:
    if e.mesh_path==str(native.get_path_to(mi)) and int(e.surface)==surface:
     for id in e.triangles: hide[int(id)]=true
   var expected = PackedInt32Array()
   for i in range(0,a[Mesh.ARRAY_INDEX].size(),3):
    if hide.has(i/3):
     removed += 1
     for k in 3:
      var v = a[Mesh.ARRAY_INDEX][i+k]
      for w in 4:
       if a[Mesh.ARRAY_WEIGHTS][v*4+w]>0: assert(sk.get_bone_name(a[Mesh.ARRAY_BONES][v*4+w])=='head')
    else:
     kept += 1
     expected.append_array(a[Mesh.ARRAY_INDEX].slice(i,i+3))
   assert(expected==t[Mesh.ARRAY_INDEX])
 var report = {'removed_head_only_triangles':removed,'preserved_original_triangles':kept,'original_skeleton_skin_positions_weights_bone_indices_equal':true,'normal_reencoding_max_error':normal_error,'tangent_reencoding_max_error':tangent_error,'invalid_source_range_duplicate_masks_rejected':true,'asset_sha256':FileAccess.get_sha256(config.output)}
 var f=FileAccess.open(OS.get_cmdline_user_args()[1],FileAccess.WRITE); f.store_string(JSON.stringify(report,'\t')); f.close()
 print(JSON.stringify(report)); quit()
