extends SceneTree
# Deterministic geometry and validation checks; no CLI or model calls.

const Builder = preload("res://addons/ainative/modeling_builder.gd")
var failures: Array = []
var checks = 0

func _initialize():
	run.call_deferred()

func check(value: bool, label: String):
	checks += 1
	print(("PASS " if value else "FAIL ") + label)
	if not value: failures.append(label)

func part(primitive: String, index: int) -> Dictionary:
	return {"name":"Part" + str(index), "primitive":primitive, "position":[index * 2.0, 0, 0], "rotation_degrees":[0, 15, 0], "size":[1, 2, 0.5], "color":[0.2, 0.6, 0.8, 1]}

func run():
	var plan = {"version":1, "name":"五种原语", "parts":[]}
	for primitive in Builder.PRIMITIVES: plan.parts.append(part(primitive, plan.parts.size()))
	check(Builder.validate_plan(plan).is_empty(), "all five primitive types accept the bounded declarative plan")
	var scene = Builder.create_scene(plan)
	root.add_child(scene)
	var summary = Builder.geometry_summary(scene)
	check(summary.ok and summary.parts == 5 and summary.vertices > 100 and summary.triangles > 100, "fixed builder constructs five nonempty meshes with finite geometry")
	check(scene.get_child(0).owner == scene and scene.get_child(0).scale == Vector3(1, 2, 0.5), "ownership and size transforms are retained")
	check(scene.get_child(0).mesh.material.albedo_color.is_equal_approx(Color(0.2, 0.6, 0.8, 1)), "plan colors are converted to native materials")
	scene.free()
	var destination = ProjectSettings.globalize_path("user://modeling-acceptance-" + str(Time.get_ticks_usec()) + ".glb")
	var exported = Builder.export_plan(plan, destination, root)
	check(exported.ok and exported.parts == 5 and exported.bytes > 20, "real Godot GLB export succeeds without external tools")
	check(not Builder.export_plan(plan, destination, root).ok, "existing GLB is never overwritten")
	var document = GLTFDocument.new()
	var state = GLTFState.new()
	check(document.append_from_file(destination, state) == OK, "the exported GLB can be decoded by Godot")
	var restored = document.generate_scene(state)
	if restored != null:
		root.add_child(restored)
		var restored_summary = Builder.geometry_summary(restored)
		check(restored_summary.ok and restored_summary.parts == 5 and restored_summary.vertices == exported.vertices, "round trip retains mesh count and vertices")
		restored.free()
	else: check(false, "round trip scene can be generated")
	DirAccess.remove_absolute(destination)
	for mutation in ["extra", "version_bool", "empty", "too_many", "unknown_primitive", "script", "path_name", "control_name", "leading_name", "trailing_name", "duplicate", "bool_number", "nan", "huge", "zero_size", "alpha", "wrong_vector"]:
		var invalid = plan.duplicate(true)
		match mutation:
			"extra": invalid["script"] = "print('do not execute')"
			"version_bool": invalid.version = true
			"empty": invalid.parts = []
			"too_many":
				invalid.parts = []
				for index in 65: invalid.parts.append(part("box", index))
			"unknown_primitive": invalid.parts[0].primitive = "run_script"
			"script": invalid.parts[0]["code"] = "OS.execute('bad')"
			"path_name": invalid.parts[0].name = "../outside"
			"control_name": invalid.name = "bad\nname"
			"leading_name": invalid.parts[0].name = " leading"
			"trailing_name": invalid.name = "trailing "
			"duplicate": invalid.parts[1].name = invalid.parts[0].name
			"bool_number": invalid.parts[0].position[0] = true
			"nan": invalid.parts[0].rotation_degrees[0] = NAN
			"huge": invalid.parts[0].position[0] = 100.01
			"zero_size": invalid.parts[0].size[0] = 0
			"alpha": invalid.parts[0].color[3] = -0.1
			"wrong_vector": invalid.parts[0].size = [1, 2]
		check(not Builder.validate_plan(invalid).is_empty(), "invalid plan rejected: " + mutation)
	print("MODELING_BUILDER_ACCEPTANCE " + JSON.stringify({"ok":failures.is_empty(), "checks":checks, "failures":failures}))
	quit(0 if failures.is_empty() else 1)
