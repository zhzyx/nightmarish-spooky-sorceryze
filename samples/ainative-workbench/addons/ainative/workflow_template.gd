@tool
extends RefCounted
## Reusable workflow definitions and their executable graph expansion.

const CUSTOM_TEMPLATE = "custom_template"
const TEMPLATE_INPUT = "template_input"
const TEMPLATE_OUTPUT = "template_output"
const INPUT_ID = "template_input"
const OUTPUT_ID = "template_output"

static func is_boundary_kind(kind: String) -> bool:
	return kind in [TEMPLATE_INPUT, TEMPLATE_OUTPUT]

static func is_fixed_node(data: Dictionary) -> bool:
	return str(data.get("id", "")) in [INPUT_ID, OUTPUT_ID] and is_boundary_kind(str(data.get("type", "")))

static func make_node(id: String, kind: String, position: Vector2) -> Dictionary:
	return {
		"id": id,
		"type": kind,
		"version": "1",
		"provider": "workflow-template",
		"source": "",
		"image_context": "",
		"text": "",
		"parameters": {},
		"x": position.x,
		"y": position.y
	}

static func create_definition(id: String, name: String) -> Dictionary:
	return {
		"id": id,
		"name": name.strip_edges(),
		"nodes": [
			make_node(INPUT_ID, TEMPLATE_INPUT, Vector2(40, 160)),
			make_node(OUTPUT_ID, TEMPLATE_OUTPUT, Vector2(640, 160))
		],
		"edges": []
	}

static func has_valid_boundaries(definition: Dictionary) -> bool:
	if not definition.get("nodes", null) is Array: return false
	var input_count = 0
	var output_count = 0
	for node in definition.nodes:
		if not node is Dictionary: return false
		if node.get("id", "") == INPUT_ID and node.get("type", "") == TEMPLATE_INPUT: input_count += 1
		if node.get("id", "") == OUTPUT_ID and node.get("type", "") == TEMPLATE_OUTPUT: output_count += 1
		if is_boundary_kind(str(node.get("type", ""))) and not is_fixed_node(node): return false
	return input_count == 1 and output_count == 1

static func expand(graph: Dictionary, definitions: Dictionary) -> Dictionary:
	return _expand_graph(graph, definitions, [])

static func _error(message: String) -> Dictionary:
	return {"nodes": [], "edges": [], "target_aliases": {}, "error": message}

static func _expand_graph(graph: Dictionary, definitions: Dictionary, stack: Array) -> Dictionary:
	var result = {
		"nodes": graph.get("nodes", []).duplicate(true),
		"edges": graph.get("edges", []).duplicate(true),
		"target_aliases": {},
		"error": ""
	}
	while true:
		var instances = result.nodes.filter(func(node): return node.get("type", "") == CUSTOM_TEMPLATE)
		if instances.is_empty(): return result
		var instance: Dictionary = instances[0]
		var template_id = str(instance.get("template_id", ""))
		if template_id.is_empty() or not definitions.has(template_id): return _error("模板实例引用了不存在的自定义流程模板")
		if template_id in stack: return _error("自定义流程模板存在循环引用")
		var definition: Dictionary = definitions[template_id]
		if not has_valid_boundaries(definition): return _error("模板“%s”缺少有效的固定输入输出节点" % definition.get("name", template_id))
		var inner = _expand_graph({"nodes": definition.nodes, "edges": definition.edges}, definitions, stack + [template_id])
		if not inner.error.is_empty(): return inner
		var replacement = _replace_instance(result, instance, inner, template_id)
		if not replacement.is_empty(): return replacement
	return result

static func _replace_instance(result: Dictionary, instance: Dictionary, inner: Dictionary, template_id: String) -> Dictionary:
	var instance_id = str(instance.id)
	var prefix = instance_id + "__"
	var incoming = result.edges.filter(func(edge): return edge.to == instance_id)
	var outgoing = result.edges.filter(func(edge): return edge.from == instance_id)
	var input_targets = inner.edges.filter(func(edge): return edge.from == INPUT_ID)
	var output_sources = inner.edges.filter(func(edge): return edge.to == OUTPUT_ID)
	if output_sources.size() != 1: return _error("模板“%s”的固定流程输出必须连接一个内部结果" % template_id)
	if output_sources[0].from == INPUT_ID: return _error("模板“%s”不能将流程输入直接连接到流程输出，请接入内部处理节点" % template_id)
	for edge in inner.edges:
		if edge.to == INPUT_ID or edge.from == OUTPUT_ID: return _error("模板“%s”的固定输入输出方向无效" % template_id)
	var output_source = prefix + str(output_sources[0].from)
	result.nodes = result.nodes.filter(func(node): return node.id != instance_id)
	result.edges = result.edges.filter(func(edge): return edge.from != instance_id and edge.to != instance_id)
	for node in inner.nodes:
		if is_boundary_kind(str(node.get("type", ""))): continue
		var copy: Dictionary = node.duplicate(true)
		copy.id = prefix + str(node.id)
		if result.nodes.any(func(existing): return existing.id == copy.id): return _error("模板展开后产生重复节点标识")
		result.nodes.append(copy)
	for edge in inner.edges:
		if edge.from == INPUT_ID: continue
		if edge.to == OUTPUT_ID: continue
		var copy: Dictionary = edge.duplicate(true)
		copy.from = prefix + str(edge.from)
		copy.to = prefix + str(edge.to)
		result.edges.append(copy)
	for target_edge in input_targets:
		for external in incoming:
			var copy: Dictionary = external.duplicate(true)
			copy.to = prefix + str(target_edge.to)
			result.edges.append(copy)
	for external in outgoing:
		var copy: Dictionary = external.duplicate(true)
		copy.from = output_source
		copy.output = "result"
		result.edges.append(copy)
	result.target_aliases[instance_id] = output_source
	return {}
