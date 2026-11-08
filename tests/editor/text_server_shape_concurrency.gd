extends SceneTree

const SHAPE_COUNT := 10000


class StableReader:
	extends RefCounted

	var server: TextServer
	var stable: RID
	var ready := Semaphore.new()
	var mutex := Mutex.new()
	var stopping := false
	var completed_reads := 0

	func request_stop() -> void:
		mutex.lock()
		stopping = true
		mutex.unlock()

	func get_completed_reads() -> int:
		mutex.lock()
		var value := completed_reads
		mutex.unlock()
		return value

	func run() -> Dictionary:
		var reads := 0
		var mismatches := 0
		while true:
			mutex.lock()
			var done := stopping
			mutex.unlock()
			if done:
				break
			for _i in 128:
				if server.shaped_text_get_orientation(stable) != TextServer.ORIENTATION_VERTICAL:
					mismatches += 1
				reads += 1
			mutex.lock()
			completed_reads = reads
			mutex.unlock()
			if reads == 128:
				ready.post()
		return {"reads": reads, "mismatches": mismatches}


func _initialize() -> void:
	run.call_deferred()


func check_interface(interface_class: String) -> Dictionary:
	# An unregistered instance starts with an empty owner; no singleton state or
	# primary interface is changed. These are ordinary independent text buffers.
	var server: TextServer = ClassDB.instantiate(interface_class)
	var errors: Array[String] = []
	var shapes: Array[RID] = []
	var stable := server.create_shaped_text(TextServer.DIRECTION_AUTO, TextServer.ORIENTATION_VERTICAL)
	if not stable.is_valid():
		return {"class": interface_class, "ok": false, "errors": ["stable_shape_creation_failed"]}
	var reader := StableReader.new()
	reader.server = server
	reader.stable = stable
	var thread := Thread.new()
	var start := thread.start(reader.run)
	var result := {}
	var allocation_phase_reads := 0
	if start != OK:
		errors.append("reader_start_failed")
	else:
		var deadline := Time.get_ticks_msec() + 10000
		var ready := reader.ready.try_wait()
		while not ready and Time.get_ticks_msec() < deadline:
			OS.delay_usec(1000)
			ready = reader.ready.try_wait()
		if not ready:
			errors.append("reader_not_ready")
		else:
			var reads_before_allocation := reader.get_completed_reads()
			for _i in SHAPE_COUNT:
				var shape := server.create_shaped_text(TextServer.DIRECTION_AUTO, TextServer.ORIENTATION_HORIZONTAL)
				if not shape.is_valid():
					errors.append("independent_shape_creation_failed")
					break
				shapes.append(shape)
			allocation_phase_reads = reader.get_completed_reads() - reads_before_allocation
			if allocation_phase_reads <= 0:
				errors.append("no_queries_during_independent_shape_creation")
		# The query RID and every independent buffer remain owned until join.
		reader.request_stop()
		result = thread.wait_to_finish()
		if result.get("reads", 0) < 128 or result.get("mismatches", -1) != 0:
			errors.append("stable_orientation_query_failed")
	if shapes.size() != SHAPE_COUNT:
		errors.append("independent_shape_count_mismatch")
	var count := shapes.size()
	for shape in shapes:
		server.free_rid(shape)
	server.free_rid(stable)
	return {
		"class": interface_class, "ok": errors.is_empty(), "errors": errors,
		"independent_shapes": count, "reader": result, "allocation_phase_reads": allocation_phase_reads,
		"stable_rid_released_after_join": true,
		"scope": "Concurrent orientation metadata queries and independent shape creation; no font or vertical layout assertion",
	}


func run() -> void:
	var cases := []
	var unavailable: Array[String] = []
	var ok := true
	for interface_class in ["TextServerAdvanced", "TextServerFallback"]:
		if not ClassDB.class_exists(interface_class) or not ClassDB.can_instantiate(interface_class):
			unavailable.append(interface_class)
			continue
		var result := check_interface(interface_class)
		cases.append(result)
		ok = ok and result.ok
	ok = ok and not cases.is_empty()
	var report := {"ok": ok, "cases": cases, "unavailable_interfaces": unavailable}
	var file := FileAccess.open(OS.get_environment("TEXT_SERVER_RESULT"), FileAccess.WRITE)
	if file == null or not file.store_string(JSON.stringify(report)):
		quit(2)
		return
	file.close()
	quit(0 if ok else 1)
