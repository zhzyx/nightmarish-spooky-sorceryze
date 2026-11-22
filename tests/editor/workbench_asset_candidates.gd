extends "res://workbench_issue_detail.gd"


func run() -> void:
	var dock := await open_workbench()
	if dock == null:
		return
	var session := dock.find_child("WorkbenchBusinessSession", true, false)
	if not require(await wait_for(func(): return not session.get_identity().is_empty()), "session missing"):
		return
	var detail := dock.find_child("WorkbenchIssueDetail", true, false)
	var fixture: Dictionary = JSON.parse_string(OS.get_environment("E09_FIXTURE"))
	await detail.open_issue(int(fixture.number))
	var assets := detail.get_node("WorkbenchIssueArtifacts")
	var local := detail.get_node("asset_candidates")
	if not require(await wait_for(func(): return assets._versions.item_count == 2), "server candidates not loaded"):
		return
	var reports := []
	for test: Dictionary in fixture.cases:
		var row := -1
		for index in assets._versions.item_count:
			if assets._versions.get_item_metadata(index).path == test.name:
				row = index
		if not require(row != -1, "missing artifact"):
			return
		assets._versions.select(row)
		assets._versions.item_selected.emit(row)
		var ref: Dictionary = assets._versions.get_item_metadata(row)
		var picker: FileDialog = assets._picker
		if test.kind == "model":
			assets.compare.pressed.emit()
			var selector: OptionButton = assets.selectors[0]
			selector.select(row)
			selector.item_selected.emit(row)
			assets.sides.get_child(0).get_child(3).pressed.emit()
			picker = assets.destinations[0]
		else:
			assets._save.pressed.emit()
		if not require(picker.visible, "save picker did not open"):
			return
		picker.file_selected.emit(test.original)
		picker.hide()
		if not require(await wait_for(func(): return local.dialog.visible), "candidate comparison missing: " + assets._status.text):
			return
		var pair: Dictionary = local.pairs[local.current]
		if not require(pair.original_digest == test.human_digest and pair.ref.digest == test.candidate_digest and pair.selected.is_empty(), "wrong pair or implicit selection"):
			return
		var observations := []
		for index in 2:
			var card: Node = local.columns.get_child(index)
			var result := {}
			if test.kind == "concept":
				var texture := card.get_child(1) as TextureRect
				if not require(texture != null and texture.texture != null, "PNG preview missing"):
					return
				result.pixel = texture.texture.get_image().get_pixel(0, 0).to_html(false)
			else:
				var view := card.get_child(1) as SubViewportContainer
				if not require(view != null, "mesh preview missing"):
					return
				var mesh := view.find_children("*", "MeshInstance3D", true, false).front() as MeshInstance3D
				if not require(mesh != null and mesh.mesh.get_surface_count() > 0, "no geometry"):
					return
				result.mesh_scale = mesh.transform.basis.get_scale().x
			var action := card.get_child(-1) as Button
			action.pressed.emit()
			var selected: Dictionary = local.pairs[local.current].selected
			if not require(selected.digest == [test.human_digest, test.candidate_digest][index] and FileAccess.get_sha256(selected.path) == selected.digest, "wrong selection"):
				return
			result.selection = selected.digest
			observations.append(result)
		var id: String = local.current
		local.dialog.hide()
		assets.comparison.hide()
		await detail.open_issue(int(fixture.number))
		if not require(await wait_for(func(): return assets._versions.item_count == 2), "reopen failed"):
			return
		for i in local.entries.item_count:
			if local.entries.get_item_metadata(i) == id:
				local.entries.select(i)
		local.reopen.pressed.emit()
		if not require(local.dialog.visible and local.pairs[id].selected.digest == test.candidate_digest, "selection lost after reopen"):
			return
		var original_after_choices := FileAccess.get_sha256(test.original)
		var stale_rejected := false
		if test.kind == "concept":
			var before := FileAccess.get_file_as_bytes(test.original)
			var file := FileAccess.open(test.original, FileAccess.WRITE)
			file.store_buffer([1, 2, 3])
			file.close()
			local.columns.get_child(0).get_child(-1).pressed.emit()
			if not require("已变化" in local.status.text and local.pairs[id].selected.digest == test.candidate_digest, "stale choice accepted"):
				return
			stale_rejected = true
			if fixture.get("reopen", false):
				file = FileAccess.open(test.original, FileAccess.WRITE)
				file.store_buffer(before)
				file.close()
		reports.append({"name": test.name, "revision": ref.revision, "original_sha256": original_after_choices,
			"stale_rejection_exercised": stale_rejected,
			"candidate_sha256": FileAccess.get_sha256(pair.candidate), "candidate_filename": str(pair.candidate).get_file(),
			"previews_and_choices": observations, "reopened_choice": local.pairs[id].selected.digest})
		local.dialog.hide()
	var invalid_card := VBoxContainer.new()
	var accepted: bool = local._model_preview(invalid_card, FileAccess.get_file_as_bytes(fixture.malformed))
	invalid_card.free()
	if not require(not accepted, "invalid geometry metadata accepted"):
		return
	print("WORKBENCH_REPORT=", JSON.stringify(reports))
	quit(0)
