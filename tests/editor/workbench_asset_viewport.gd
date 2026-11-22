extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "session missing"):
		return
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("E09_FIXTURE"))
	var detail := session.get_node("WorkbenchIssueDetail")
	await detail.open_issue(int(fixture.number))
	var local := detail.get_node("asset_candidates")
	if not require(local.entries.item_count == fixture.cases.size(), "project reopen lost original asset references"):
		return
	var reports := []
	for index in local.entries.item_count:
		local.entries.select(index)
		local.reopen.pressed.emit()
		await process_frame
		var pair: Dictionary = local.pairs[local.current]
		var matched: Array = fixture.cases.filter(func(item): return item.original == pair.original)
		if not require(matched.size() == 1 and local.compare_bar.is_visible_in_tree(), "original reference or A/B controls missing"):
			return
		var item: Dictionary = matched[0]
		if not require(pair.original_digest == item.human_digest and pair.selected.digest == item.candidate_digest, "saved reference changed on reopen"):
			return
		var original: Control = local.original_preview
		var reference := pair.duplicate(true)
		var texture: Texture2D
		var camera: Camera3D
		var pose := Transform3D.IDENTITY
		var geometry: Node3D
		if original is TextureRect:
			texture = original.texture
		else:
			var viewport := original.get_node("MeshViewport") as SubViewport
			camera = viewport.get_camera_3d()
			geometry = viewport.get_node("Geometry")
			camera.position += Vector3(0.25, 0.1, -0.15)
			camera.fov = 53
			pose = camera.global_transform
		var rect := original.get_global_rect()
		var observations := []
		for side in ["B", "A", "B"]:
			var candidate: bool = side == "B"
			var button: Button = local.show_b if candidate else local.show_a
			if not require(not button.disabled and button.is_visible_in_tree(), "toggle inaccessible"):
				return
			button.pressed.emit()
			await process_frame
			if not require(local.original_preview == original and original.get_global_rect().is_equal_approx(rect) and local.pairs[local.current] == reference, "view geometry or persistent asset reference changed"):
				return
			if texture:
				if candidate:
					var framed := original.texture as AtlasTexture
					if not require(framed != null and framed.get_size() == texture.get_size() and framed.region == Rect2(4, 0, 8, 4) and framed.margin == Rect2(0, 2, 0, 4), "differently sized B was fitted independently"):
						return
				var pixel: String = original.texture.get_image().get_pixel(4, 3).to_html(false)
				if not require(pixel == ("0000ff" if candidate else "ff0000"), "wrong texture in original view"):
					return
				observations.append({"side": side, "pixel": pixel})
			else:
				var viewport := original.get_node("MeshViewport") as SubViewport
				if not require(viewport.get_camera_3d() == camera and camera.global_transform.is_equal_approx(pose) and camera.fov == 53, "camera or projection changed"):
					return
				var active := viewport.get_node("ComparisonGeometry") if candidate else geometry
				var mesh := active.get_child(0) as MeshInstance3D
				if not require(geometry.visible == (not candidate) and active.is_visible_in_tree() and mesh.mesh.get_surface_count() > 0 and mesh.transform.basis.get_scale().x == (2.0 if candidate else 1.0), "wrong visible geometry"):
					return
				observations.append({"side": side, "mesh_scale": mesh.transform.basis.get_scale().x, "fov": camera.fov, "camera_transform": str(camera.global_transform)})
		local.finish.pressed.emit()
		if not require(local.finish.disabled and (original.texture == texture if texture else geometry.visible and not geometry.get_parent().has_node("ComparisonGeometry")), "exit failed to restore original live resource"):
			return
		local.show_b.pressed.emit()
		local.dialog.hide()
		if not require(local.finish.disabled and (original.texture == texture if texture else geometry.visible) and local.pairs[local.current] == reference, "closing on B changed binding"):
			return
		if not require(FileAccess.get_sha256(pair.original) == item.human_digest and FileAccess.get_sha256(pair.candidate) == item.candidate_digest, "comparison modified asset bytes"):
			return
		if texture:
			local.reopen.pressed.emit()
			local.show_b.pressed.emit()
			var candidate_bytes := FileAccess.get_file_as_bytes(pair.candidate)
			var changed := FileAccess.open(pair.candidate, FileAccess.WRITE)
			changed.store_buffer([1])
			changed.close()
			local.show_a.pressed.emit()
			if not require(not local.compare_bar.visible and local.finish.disabled and "已变化" in local.status.text and local.pairs[local.current] == reference, "changed candidate still comparable"):
				return
			changed = FileAccess.open(pair.candidate, FileAccess.WRITE)
			changed.store_buffer(candidate_bytes)
			changed.close()
			local.dialog.hide()
		reports.append({"name": item.name, "revision": pair.ref.revision, "sequence": observations, "original": pair.original_digest,
			"candidate": pair.ref.digest, "selected": pair.selected.digest, "same_view_rect": str(rect), "restored_original_object": true})
	print("WORKBENCH_REPORT=", JSON.stringify({"pid": OS.get_process_id(), "display_server": DisplayServer.get_name(), "comparisons": reports}))
	quit(0)
