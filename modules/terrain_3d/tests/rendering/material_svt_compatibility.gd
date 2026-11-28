@tool
extends Node3D
## Launched by material_svt_compatibility.py in the real editor and the exported game.

const STREAM := "res://compat.svt"
var failures := 0


func _ready() -> void:
	if not OS.get_environment("T3D_COMPAT_STAGE").is_empty():
		run.call_deferred()


func check(condition: bool, message: String) -> void:
	if not condition:
		push_error(message)
		failures += 1


func wait_frames(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw


func run() -> void:
	var stage := OS.get_environment("T3D_COMPAT_STAGE")
	var baking := stage == "bake"
	check(Engine.is_editor_hint() == baking, "Expected an editing session for bake and an exported game for the reads")
	var c := Camera3D.new()
	add_child(c)
	c.position = Vector3(32, 50, 32)
	c.look_at(Vector3(32, 0, 32), Vector3.FORWARD)
	c.make_current()
	var t := Terrain3D.new()
	t.region_size = Terrain3D.SIZE_64
	t.free_editor_textures = true
	t.material = Terrain3DMaterial.new()
	t.material.world_background = Terrain3DMaterial.NONE
	t.assets = load("res://changed.tres" if stage == "changed" else "res://assets.tres")
	add_child(t)
	t.set_camera(c)
	t.set_clipmap_target(c)
	t.data.add_region_blank(Vector2i.ZERO)
	CVars.set_value("r.Terrain3D.Mode", 1)
	CVars.set_value("r.Terrain3D.VTHeight", 1)
	t.material.material_rvt_enabled = true
	await wait_frames(120)
	check(t.assets.get_texture_count() == (2 if baking else 0), "Runtime must release its CPU-side asset list")
	var original := (load("res://source.png") as Texture2D).get_image()
	check(original.get_format() == Image.FORMAT_BPTC_RGBA, "This fixture requires a BC7 import")
	var material_rid := t.material.get_material_rid()
	var albedo: RID = RenderingServer.material_get_param(material_rid, "_texture_array_albedo")
	var normal: RID = RenderingServer.material_get_param(material_rid, "_texture_array_normal")
	var checker := RenderingServer.texture_2d_layer_get(albedo, 1)
	var flat := RenderingServer.texture_2d_layer_get(normal, 0)
	check(checker != null and flat != null, "Missing texture slots must produce complete resident arrays")
	if checker and flat:
		check(checker.get_size() == original.get_size() and checker.get_mipmap_count() == original.get_mipmap_count(),
				"Checker must preserve texture dimensions and mipmaps")
		check(flat.get_size() == original.get_size() and flat.get_mipmap_count() == original.get_mipmap_count(),
				"Normal placeholder must preserve texture dimensions and mipmaps")
		if checker.is_compressed():
			checker.decompress()
		if flat.is_compressed():
			flat.decompress()
		check(absf(checker.get_pixel(4,4).r - 0.8) < 0.015 and absf(checker.get_pixel(36,4).r - 0.5) < 0.015,
				"Missing albedo did not use the two checker colors")
		var n := flat.get_pixel(4,4)
		check(absf(n.r - 0.5) < 0.015 and absf(n.g - 0.5) < 0.015 and n.b > 0.99,
				"Missing normal did not use a flat tangent-space normal")
	if baking:
		check(t.material.bake_material_svt(STREAM, 1) == OK, "Editor failed to bake the file")
	t.material.material_rvt_stream_file = STREAM
	await wait_frames(100)
	var stats := RenderingServer.runtime_virtual_texture_get_stats(t.material.get_material_rvt_rid())
	print("T3D_COMPAT ", stage, " first=",stats.stream_first_mip," disk=",stats.disk_pages)
	if stage == "changed":
		check(int(stats.stream_first_mip) == -1, "Changed albedo pixels must reject the old file")
	else:
		check(int(stats.stream_first_mip) >= 0 and int(stats.disk_pages) > 0, "The baked file must supply a visible disk page")
	print("T3D_COMPAT ",stage," failures=",failures)
	get_tree().quit(1 if failures else 0)
