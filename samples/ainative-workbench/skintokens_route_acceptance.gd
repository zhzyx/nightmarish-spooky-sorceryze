extends SceneTree
# Contract checks for the independent SkinTokens route. Run without
# AINATIVE_SKINTOKENS_CONFIG set. These checks do not prove inference quality.
const SkinRoute = preload('res://addons/ainative/skintokens_route.gd')
var failures = []

func check(ok: bool, description: String):
	if not ok: failures.append(description)

func _initialize():
	run.call_deferred()

func run():
	if not OS.get_environment('AINATIVE_SKINTOKENS_CONFIG').is_empty():
		push_error('Run this acceptance without AINATIVE_SKINTOKENS_CONFIG set.')
		quit(2)
		return
	var result = SkinRoute.run(null,'')
	check(result.has('error'),'unconfigured route must fail explicitly with a configuration hint')
	var node = Node3D.new()
	var target = 'user://skintokens-route-acceptance.tscn'
	check(SkinRoute.stage(node,target) != '','stage must reject scenes from other routes')
	node.free()
	if failures.is_empty():
		print('SKINTOKENS_ROUTE_ACCEPTANCE_OK')
		quit(0)
	else:
		for failure in failures: push_error(failure)
		quit(1)
