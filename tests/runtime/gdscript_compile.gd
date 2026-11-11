extends SceneTree

var failures: Array[String] = []

func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)

func _initialize() -> void:
	var first := GDScript.compile_source("extends RefCounted\nfunc value() -> int:\n\treturn 41\n")
	check(first.error == OK and first.script is GDScript and first.diagnostics.is_empty(), "successful compilation")
	if first.error != OK:
		quit(1)
		return
	var instance = first.script.new()
	check(instance.value() == 41, "compiled script executes")
	var syntax := GDScript.compile_source("extends RefCounted\nfunc broken(\n", "res://candidate.gd")
	check(syntax.error == ERR_PARSE_ERROR and syntax.script == null, "syntax failure returns no script")
	check(not syntax.diagnostics.is_empty(), "syntax diagnostics present")
	if not syntax.diagnostics.is_empty():
		check(syntax.diagnostics[0].line > 0 and syntax.diagnostics[0].path == "res://candidate.gd", "diagnostic location")
	var typed := GDScript.compile_source('extends RefCounted\nfunc value() -> int:\n\treturn "wrong"\n')
	check(typed.error == ERR_PARSE_ERROR and typed.script == null, "type failure returns no script")
	check(not typed.diagnostics.is_empty(), "type diagnostics present")
	check(instance.value() == 41 and instance.get_script() == first.script, "failed compile preserves live script")
	var second := GDScript.compile_source("extends RefCounted\nfunc value() -> int:\n\treturn 42\n", "res://candidate.gd")
	check(second.error == OK and second.script != first.script, "repeat compilation creates independent script")
	if second.error == OK:
		instance.set_script(second.script)
		check(instance.value() == 42, "explicit live script replacement executes")
		check(first.script.new().value() == 41, "old script remains usable")
	var initialized := GDScript.compile_source("extends RefCounted\nstatic var result: int = 20\nstatic func _static_init():\n\tresult += 22\nclass Inner:\n\tstatic var answer: int = 7\nfunc value():\n\treturn result + Inner.answer\n")
	check(initialized.error == OK, "static data and nested class compile")
	if initialized.error == OK:
		check(initialized.script.new().value() == 49, "static initializer and nested class execute")
	# Release VM omits some runtime error checks; initialization diagnostics
	# are only asserted when the VM reports those errors.
	if OS.is_debug_build():
		var printing_errors := Engine.print_error_messages
		Engine.print_error_messages = false
		var broken_init := GDScript.compile_source("extends RefCounted\nstatic func _static_init():\n\tvar missing: Variant = null\n\tmissing.no_such_method()\n", "res://bad_init.gd")
		Engine.print_error_messages = printing_errors
		check(broken_init.error == ERR_CANT_CREATE and broken_init.script == null, "static initialization failure returns no script")
		check(not broken_init.diagnostics.is_empty(), "static initialization diagnostic present")
		if not broken_init.diagnostics.is_empty():
			check(broken_init.diagnostics[0].stage == "initialize" and broken_init.diagnostics[0].path == "res://bad_init.gd", "static initialization diagnostic location")
		Engine.print_error_messages = false
		var child_source := "extends RefCounted\nstatic func _static_init():\n\tvar missing: Variant = null\n\tmissing.no_such_method()\n"
		var parent_source := "extends RefCounted\nstatic var result: int = -1\nstatic func _static_init():\n\tresult = GDScript.compile_source(%s).error\n" % JSON.stringify(child_source)
		var handled := GDScript.compile_source(parent_source)
		Engine.print_error_messages = printing_errors
		check(handled.error == OK, "handled nested compile failure does not fail outer initialization")
		if handled.error == OK:
			check(handled.script.get("result") == ERR_CANT_CREATE, "outer initializer receives child error")

	for iteration in 32:
		var transient := GDScript.compile_source("extends RefCounted\nstatic var value: int = 42\n")
		check(transient.error == OK, "repeated static compile")
		var weak: WeakRef = weakref(transient.script)
		transient.clear()
		check(weak.get_ref() == null, "runtime static scripts are not retained by global cache")

	# Fixtures are created only inside the runner's isolated project.
	var dependency_path := "res://runtime_compile_dependency.gd"
	var file := FileAccess.open(dependency_path, FileAccess.WRITE)
	check(file != null, "relative dependency fixture writable")
	if file != null:
		file.store_string("extends RefCounted\nfunc value() -> int:\n\treturn 73\n")
		file.close()
		var existing = load(dependency_path)
		var relative := GDScript.compile_source('extends "runtime_compile_dependency.gd"\nfunc other() -> int:\n\treturn value() + 1\n', "res://runtime_compile_dependency.gd")
		check(relative.error == OK, "relative extends resolves from source directory")
		if relative.error == OK:
			check(relative.script.new().other() == 74, "relative base executes")
		check(load(dependency_path) == existing and existing.new().value() == 73, "compile path does not replace cached dependency")
		var preloaded := GDScript.compile_source('extends RefCounted\nconst Dependency = preload("runtime_compile_dependency.gd")\nfunc value() -> int:\n\treturn Dependency.new().value()\n', "res://candidate.gd")
		check(preloaded.error == OK, "relative preload resolves")
		if preloaded.error == OK:
			check(preloaded.script.new().value() == 73, "relative preload executes")
		DirAccess.remove_absolute(dependency_path)
	print(JSON.stringify({"test": "gdscript_compile", "initialization_diagnostics_checked": OS.is_debug_build(), "passed": failures.is_empty(), "failures": failures}))
	if failures.is_empty():
		print("RUNTIME_GDSCRIPT_COMPILE_OK")
	quit(0 if failures.is_empty() else 1)
