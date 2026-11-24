extends SceneTree

var failures: Array[String] = []
var samples: Array[Dictionary] = []

func check(condition: bool, detail: String) -> void:
	if not condition:
		failures.append(detail)

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	var stack := VBoxContainer.new()
	stack.size = Vector2(320, 600)
	root.add_child(stack)
	var fold := FoldableContainer.new()
	fold.title = "显示与适配 Display"
	fold.add_theme_constant_override("folding_duration", 180)
	stack.add_child(fold)
	var content := Button.new()
	content.text = "可交互内容"
	content.custom_minimum_size = Vector2(240, 160)
	fold.add_child(content)
	await create_timer(0.1).timeout
	var expanded := fold.get_minimum_size().y
	fold.fold()
	await create_timer(0.06).timeout
	var middle := fold.get_minimum_size().y
	check(middle < expanded and middle > expanded - 160, "collapse must enter an intermediate frame")
	check(not content.is_visible_in_tree(), "collapsing content must not remain interactive")
	fold.expand()
	var reversal := fold.get_minimum_size().y
	check(absf(reversal - middle) < 1.0, "reversal must continue from current height")
	await create_timer(0.25).timeout
	check(absf(fold.get_minimum_size().y - expanded) < 1.0, "expansion must restore full minimum height")
	check(content.is_visible_in_tree(), "expanded content must be visible")
	check(not fold.is_clipping_contents(), "animation must restore original clipping")
	fold.add_theme_constant_override("folding_duration", 0)
	await process_frame
	fold.fold()
	await process_frame
	var reduced := fold.get_minimum_size().y
	check(reduced < middle, "reduced motion must settle immediately")
	await create_timer(0.25).timeout
	check(is_equal_approx(reduced, fold.get_minimum_size().y), "reduced motion must not keep animating")
	fold.expand()
	await process_frame
	check(absf(fold.get_minimum_size().y - expanded) < 1.0, "reduced motion expansion must restore content")
	fold.set_clip_contents(true)
	fold.add_theme_constant_override("folding_duration", 180)
	await process_frame
	for cycle in range(3):
		fold.fold()
		await create_timer(0.03).timeout
		fold.expand()
		await create_timer(0.03).timeout
	fold.fold()
	await create_timer(0.25).timeout
	check(fold.is_clipping_contents(), "existing clipping must survive repeated reversals")
	check(not content.is_visible_in_tree(), "final collapsed content must be hidden")
	fold.expand()
	await create_timer(0.03).timeout
	fold.add_theme_constant_override("folding_duration", 0)
	await process_frame
	await process_frame
	check(absf(fold.get_minimum_size().y - expanded) < 1.0, "reducing motion during animation must settle")
	fold.add_theme_constant_override("folding_duration", 180)
	await process_frame
	fold.fold()
	await create_timer(0.03).timeout
	fold.add_theme_constant_override("folding_duration", 0)
	await process_frame
	fold.expand()
	check(absf(fold.get_minimum_size().y - expanded) < 1.0, "zero-duration reversal must settle synchronously")
	samples.append({"expanded": expanded, "middle": middle, "reversal": reversal, "collapsed": reduced})
	print(JSON.stringify({"failures": failures, "samples": samples}))
	quit(0 if failures.is_empty() else 1)
