@tool
extends RefCounted

## Graphs are versioned plans. Execution state and protected relations are supplied
## by the bound host. The editor only submits the editable part (nodes and edges).
const KINDS := ["text", "image", "question", "task", "join"]
const EDIT_FIELDS := ["kind", "title", "value", "model", "caption"]
const ACTIVE := ["running", "completed", "dispatched", "reserved", "reconcile_required", "failed", "cancelled","answered"]


static func new_plan() -> Dictionary:
	return {"nodes": {}, "edges": []}


## Reapply local edits made while the authoritative graph was loading.
## An overlapping source change leaves the entire draft at its original revision.
static func reconcile_snapshot(base: Dictionary, draft: Dictionary, live: Dictionary) -> Dictionary:
	var merged := live.duplicate(true)
	var keys: Dictionary = base.nodes.duplicate()
	keys.merge(draft.nodes)
	for key in keys:
		var before = base.nodes.get(key)
		var local = draft.nodes.get(key)
		if local == before:
			continue
		var remote = live.nodes.get(key)
		if remote != before and remote != local:
			return {"error": "节点 %s 在来源和草稿中同时变更" % key}
		if local == null:
			merged.nodes.erase(key)
		else:
			merged.nodes[key] = local.duplicate(true)
	for edge in base.edges:
		if edge not in draft.edges:
			merged.edges.erase(edge)
	for edge in draft.edges:
		if edge not in base.edges and edge not in merged.edges:
			merged.edges.append(edge.duplicate())
	for edge in merged.edges:
		if not merged.nodes.has(edge.from) or not merged.nodes.has(edge.to):
			return {"error": "流程端点已变更"}
	return {"plan": merged}


static func output_type(kind: String) -> String:
	return {"image": "image", "text": "text", "question": "text"}.get(kind, "result")


static func edge_error(plan: Dictionary, edge: Dictionary, context: Dictionary) -> String:
	var source: String = edge.get("from", "")
	var target: String = edge.get("to", "")
	var relation: String = edge.get("kind", "")
	if source == target:
		return "节点不能连接自身"
	if not plan.nodes.has(source) or not plan.nodes.has(target):
		return "两个端点必须属于当前 Issue"
	if relation not in ["data", "after"]:
		return "端口类型不匹配"
	if edge in plan.edges:
		return "已存在相同连线"
	var receiver: Dictionary = plan.nodes[target]
	if relation == "data":
		if receiver.kind not in ["task", "join"]:
			return "该节点不接收数据输入"
		var model: String = receiver.get("model", "")
		var needed := output_type(plan.nodes[source].kind)
		if receiver.kind == "task" and model != "":
			if not context.get("models", {}).has(model):
				return "指定模型缺少已核实的能力目录"
			if needed == "image" and "image" not in context.models[model]:
				return "此模型不接收图片"
	# Both kinds of edge require the upstream result to exist.
	var outgoing := {}
	for link in plan.edges:
		if not outgoing.has(link.from):
			outgoing[link.from] = []
		outgoing[link.from].append(link.to)
	var frontier := [target]
	var seen := {}
	while not frontier.is_empty():
		var current: String = frontier.pop_back()
		if current == source:
			return "这条连线会形成循环等待"
		if seen.has(current):
			continue
		seen[current] = true
		frontier.append_array(outgoing.get(current, []))
	return ""


static func changes_error(before: Dictionary, draft: Dictionary, context: Dictionary, require_inputs := true) -> String:
	if not draft.get("nodes") is Dictionary or not draft.get("edges") is Array:
		return "图数据格式无效"
	var nodes: Dictionary = draft.nodes
	for id in nodes:
		var node = nodes[id]
		if not (id is String or id is StringName) or not String(id).is_valid_ascii_identifier() or not node is Dictionary:
			return "节点标识无效"
		var original: Dictionary = before.nodes.get(id, {})
		var protected_node: bool = id in context.get("protected_nodes", [])
		if original != node and (protected_node or context.get("states", {}).get(id, "") in ACTIVE):
			return "节点 %s 已锁定，请保留本次执行的输入" % id
		if not protected_node:
			if node.get("kind") not in KINDS:
				return "节点类型无效"
			for field in node:
				if field not in EDIT_FIELDS or not node[field] is String:
					return "不允许修改节点字段 %s" % field
			if not original.is_empty() and original.kind != node.kind:
				return "已有节点不能改变类型"
			if String(node.get("title", "")).strip_edges().is_empty():
				return "节点缺少名称"
		if node.get("model", "") != "" and not context.get("models", {}).has(node.model) and node != original:
			return "手选型号缺少已核实的能力目录"
	for id in before.nodes:
		if not nodes.has(id) and (id in context.get("protected_nodes", []) or context.get("states", {}).get(id, "") in ACTIVE):
			return "不能移除已锁定的节点 %s" % id
	for required in context.get("protected_edges", []):
		if required not in draft.edges:
			return "不能断开框架要求的连线"
	for previous in before.edges:
		if previous not in draft.edges and context.get("states", {}).get(previous.to, "") in ACTIVE:
			return "不能改变已启动节点 %s 的输入" % previous.to
	var checked := {"nodes": nodes, "edges": []}
	var inputs := {}
	for link in draft.edges:
		if not link is Dictionary or link.size() != 3 or not (link.get("from") is String or link.get("from") is StringName) or not (link.get("to") is String or link.get("to") is StringName) or not link.get("kind") is String:
			return "连线格式无效"
		if link not in before.edges and context.get("states", {}).get(link.to, "") in ACTIVE:
			return "不能改变已启动节点 %s 的输入" % link.to
		var reason := edge_error(checked, link, context)
		if reason != "":
			return reason
		checked.edges.append(link)
		if link.kind == "data":
			inputs[link.to] = true
	if require_inputs:
		for id in nodes:
			var node: Dictionary = nodes[id]
			if node.kind == "join" and not inputs.has(id) and id not in context.get("protected_nodes", []):
				return "汇总节点 %s 缺少结果输入" % node.title
			if node.kind in ["task", "text", "image"] and String(node.get("value", "")).strip_edges().is_empty() and not inputs.has(id) and not context.get("questions",{}).has(id):
				return "节点 %s 缺少输入" % node.title
	return ""
