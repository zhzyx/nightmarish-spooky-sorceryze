extends SceneTree
# Typed workflow ports; real Godot controls, no model inference.
var panel
var failures = 0

func check(ok: bool, label: String):
	print(("PASS " if ok else "FAIL ") + label)
	if not ok: failures += 1

func _initialize():
	run.call_deferred()

func make_node(kind: String) -> Dictionary:
	var data = {"id":kind, "type":kind, "source":"", "image_context":"", "text":"", "parameters":{}, "x":0.0, "y":0.0}
	data.version = panel._new_node_version(kind)
	return data

func run():
	root.size = Vector2i(1440, 1000)
	panel = load("res://addons/ainative/workbench.gd").new()
	panel.set_meta("ainative_builtin", true)
	root.add_child(panel)
	await process_frame
	panel.nodes = []
	for kind in panel.NODE_KINDS: panel.nodes.append(make_node(kind))
	panel.edges = []
	panel.rebuild()
	await process_frame
	var expected = {
		"generate_image":[panel.PORT_IMAGE, panel.PORT_IMAGE_SET, "输入：图片 / 图片列表（可选）＋文本（参数）", "输出：图片队列"],
		"text_to_image":[panel.PORT_TEXT, panel.PORT_IMAGE_SET, "输入：文本（参数）", "输出：图片队列"],
		"image_to_image":[panel.PORT_IMAGE, panel.PORT_IMAGE_SET, "输入：图片 / 图片列表", "输出：图片队列"],
		"image_to_mesh":[panel.PORT_IMAGE, panel.PORT_MESH, "输入：图片 / 图片列表", "输出：Mesh"],
		"text_to_mesh":[panel.PORT_TEXT, panel.PORT_MESH, "输入：文本（参数）", "输出：Mesh"],
		"model_adjust":[panel.PORT_MESH, panel.PORT_MESH, "输入：Mesh", "输出：Mesh"],
		"human_shape_adjust":[panel.PORT_MESH, panel.PORT_MESH, "输入：Mesh", "输出：Mesh"],
		"humanoid_rig":[panel.PORT_MESH, panel.PORT_CHARACTER, "输入：Mesh", "输出：人形角色（17骨＋root）"],
		"garment_split":[panel.PORT_MESH, panel.PORT_MESH, "输入：Mesh", "输出：Mesh"],
		"copy":[panel.PORT_DYNAMIC, panel.PORT_DYNAMIC, "输入：图片 / Mesh", "输出：图片 / Mesh"],
	}
	for kind in expected:
		var data = panel.nodes.filter(func(item): return item.type == kind)[0]
		var types = expected[kind]
		var node = panel.graph.get_node(kind)
		check(panel.input_kind(data) == types[0] and panel.output_kind(data) == types[1], kind + " declares its input and output types")
		check(node.get_output_port_type(0) == types[1] and node.get_output_port_color(0) == panel.PORT_COLORS[types[1]], kind + " renders a typed main output")
		var input_label = node.get_node("PortTypes/InputType")
		var output_label = node.get_node("PortTypes/OutputType")
		check(input_label.text == types[2] and output_label.text == types[3], kind + " shows readable input and output type names")
		if types[0] == panel.PORT_TEXT:
			check(node.get_input_port_count() == 0 and input_label.tooltip_text.contains("参数"), kind + " keeps parameter-only text input without a misleading connection")
		else:
			check(node.get_input_port_count() == 1 and node.get_input_port_type(0) == types[0] and node.get_input_port_color(0) == panel.PORT_COLORS[types[0]], kind + " renders a typed input")
		check(node.get_output_port_count() == 1, kind + " exposes exactly one output")
	panel.connect_nodes("text_to_mesh", 0, "image_to_mesh", 0)
	check(panel.edges.is_empty() and panel.status.text.contains("类型不匹配"), "Mesh cannot silently feed an image input")
	panel.connect_nodes("text_to_mesh", 0, "generate_image", 0)
	check(panel.edges.is_empty() and panel.status.text.contains("类型不匹配"), "combined image/list input still rejects Mesh")
	panel.connect_nodes("text_to_image", 0, "model_adjust", 0)
	check(panel.edges.is_empty() and panel.status.text.contains("不支持图片列表"), "image queue cannot silently feed a Mesh adjustment input")
	check(panel.graph.is_valid_connection_type(panel.PORT_IMAGE_SET, panel.PORT_IMAGE), "image lists can be dragged onto the single-image compatible input")
	panel.connect_nodes("text_to_image", 0, "generate_image", 0)
	panel.connect_nodes("text_to_image", 0, "image_to_mesh", 0)
	panel.connect_nodes("text_to_mesh", 0, "model_adjust", 0)
	check(panel.edges.size() == 3 and panel.edges[0].output == "image_set" and panel.edges[1].output == "image_set" and panel.edges[2].output == "result", "image queues feed both unified image generation and image-to-Mesh while Mesh keeps its output contract")
	var legacy = make_node("text_to_image")
	legacy.id = "legacy_image"
	legacy.version = "1"
	panel.nodes.append(legacy)
	var single_input = make_node("generate_image")
	single_input.id = "single_image_input"
	single_input.version = "1"
	panel.nodes.append(single_input)
	panel.rebuild()
	check(panel.output_kind(legacy) == panel.PORT_IMAGE and panel.graph.get_node(legacy.id).get_output_port_count() == 1, "version 1 keeps its legacy single-image output")
	panel.connect_nodes(legacy.id, 0, single_input.id, 0)
	check(panel.edges.size() == 4 and panel.edges[3].output == "result", "a single image can feed the same image/list input as a queue")
	var by_id = {}
	for data in panel.nodes: by_id[data.id] = data
	check(panel._valid_workflow_edge(panel.edges[3], by_id), "single-image input also passes saved workflow validation")
	var legacy_batch = make_node("text_to_image")
	legacy_batch.id = "legacy_batch"
	legacy_batch.version = "2"
	panel.nodes.append(legacy_batch)
	panel.rebuild()
	check(panel.output_kind(legacy_batch) == panel.PORT_IMAGE and panel.graph.get_node(legacy_batch.id).get_output_port_count() == 2, "version 2 keeps its legacy primary image and queue outputs")
	var queue_v3 = make_node("text_to_image")
	queue_v3.id = "queue_v3"
	queue_v3.version = "3"
	panel.nodes.append(queue_v3)
	panel.rebuild()
	check(panel.output_kind(queue_v3) == panel.PORT_IMAGE_SET and panel.graph.get_node(queue_v3.id).get_output_port_count() == 1, "version 3 keeps its queue-only output")
	var legacy_mesh = make_node("image_to_mesh")
	legacy_mesh.id = "legacy_mesh"
	legacy_mesh.version = "1"
	panel.nodes.append(legacy_mesh)
	panel.rebuild()
	check(not panel._accepts_image_set(legacy_mesh) and panel.input_type_name(legacy_mesh) == "图片", "version 1 image-to-Mesh keeps its single-image input contract")
	print("AINATIVE_PORT_TYPE failures=" + str(failures))
	panel.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
