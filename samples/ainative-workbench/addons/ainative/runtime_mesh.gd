@tool
extends RefCounted
# GLTFDocument intentionally retains ImporterMesh nodes in editor mode. Convert
# only this pipeline's scene, leaving the editor's global import extensions alone.

static func generate(document, state) -> Node3D:
	return convert_scene(document.generate_scene(state))

static func convert_scene(node: Node) -> Node3D:
	if node==null: return null
	var current = node
	if node is ImporterMeshInstance3D:
		var mesh = MeshInstance3D.new()
		mesh.name = node.name
		mesh.transform = node.transform
		mesh.skin = node.skin
		mesh.skeleton = node.skeleton_path
		mesh.visible = node.visible
		mesh.layers = node.layer_mask
		for property in ['cast_shadow','visibility_range_begin','visibility_range_begin_margin','visibility_range_end','visibility_range_end_margin','visibility_range_fade_mode']:
			mesh.set(property,node.get(property))
		for key in node.get_meta_list(): mesh.set_meta(key,node.get_meta(key))
		if node.mesh:
			mesh.mesh = node.mesh.get_mesh()
			if mesh.mesh:
				for key in node.mesh.get_meta_list(): mesh.mesh.set_meta(key,node.mesh.get_meta(key))
		node.replace_by(mesh,true)
		node.free()
		current = mesh
	for child in current.get_children():
		if child is Node3D: convert_scene(child)
	return current as Node3D
