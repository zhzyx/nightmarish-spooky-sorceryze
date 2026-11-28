@tool
extends RefCounted

# Layout coordinates are fractions of the half width: +X east, +Z south.
const Fieldcraft = preload("@TERRAIN3D_EDITOR_ROOT@/src/yugong_fieldcraft.gd")
const VERSION := 2
const EXAMPLE := "金色丘陵，南坡出生，西北残堡立在台地上。曲折河谷从北向南，两条古道通向堡门，东线过桥，西线沿山脊。"
const GROUPS := ["spawn", "plateau", "river", "west_road", "east_road", "ridges"]
const LABELS := ["出生点", "台地轮廓", "河流", "西路", "东路", "山脊"]

static func obj(fields: Dictionary) -> Dictionary:
	return {"type":"object","properties":fields,"required":fields.keys(),"additionalProperties":false}

static func schema() -> Dictionary:
	var number := {"type":"number"}
	var point := obj({"x":number,"z":number})
	var line := {"type":"array","items":point}
	var ridge := obj({"x":number,"z":number,"radius":number,"height":number})
	return obj({"spawn":point,"plateau":line,"river":line,"west_road":line,"east_road":line,
		"ridges":{"type":"array","items":ridge},"landmark":{"type":"string","enum":["ruin","tree","cairn"]}})

static func pos(p: Dictionary) -> Vector2:
	return Vector2(p.x,p.z)

static func points(list: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in list:
		out.append(pos(p))
	return out

static func plateau_center(plan: Dictionary) -> Vector2:
	var polygon := points(plan.plateau)
	var center := Vector2.ZERO
	for point in polygon:
		center += point
	return center / polygon.size()

static func road(plan: Dictionary, key: String) -> PackedVector2Array:
	var line := points(plan[key])
	line.insert(0,pos(plan.spawn))
	line.append(plateau_center(plan))
	return smooth_line(line)

static func smooth_line(line: PackedVector2Array) -> PackedVector2Array:
	for pass_index in 2:
		var next := PackedVector2Array([line[0]])
		for i in line.size()-1:
			next.append(line[i].lerp(line[i+1],0.25))
			next.append(line[i].lerp(line[i+1],0.75))
		next.append(line[-1])
		line=next
	return line

static func finite_number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))

static func valid_point(p: Variant) -> bool:
	return p is Dictionary and finite_number(p.get("x")) and finite_number(p.get("z")) and absf(p.x)<=1 and absf(p.z)<=1

static func error(plan: Variant) -> String:
	if not plan is Dictionary or not valid_point(plan.get("spawn")) or not ["ruin","tree","cairn"].has(plan.get("landmark")):
		return "出生点或地标格式无效。"
	if plan.has("ridge_road") and plan.ridge_road not in ["east_road","west_road"]:
		return "沿脊线路需对应已有古道。"
	if plan.has("operations"):
		var issue:=Fieldcraft.operation_error(plan.operations)
		if not issue.is_empty():return issue
	for group in GROUPS.slice(1):
		var list: Variant=plan.get(group)
		var minimum := 3 if group=="plateau" else (0 if group=="ridges" else 2)
		if not list is Array or list.size()<minimum or list.size()>16:
			return "布局控制点数量无效（%s）。" % group
		for p in list:
			if not valid_point(p):
				return "控制点超出边界（%s）。" % group
			if group=="ridges" and (not finite_number(p.get("radius")) or not finite_number(p.get("height")) or p.radius<0.035 or p.radius>0.8 or p.height<0 or p.height>1):
				return "山脊半径或高度无效。"
		var line:=points(list)
		for i in line.size()-1:
			if line[i].distance_squared_to(line[i+1]) < 0.000025:
				return "相邻控制点过近（%s）。" % group
	var poly:=points(plan.plateau)
	if Geometry2D.triangulate_polygon(poly).is_empty() or not Geometry2D.is_point_in_polygon(plateau_center(plan),poly):
		return "台地需要围成一个含中心点的简单多边形。"
	for i in poly.size():
		for j in range(i+2,poly.size()):
			if (j+1)%poly.size()!=i and Geometry2D.segment_intersects_segment(poly[i],poly[(i+1)%poly.size()],poly[j],poly[(j+1)%poly.size()])!=null:
				return "台地边线不能交叉。"
	if pos(plan.spawn).distance_to(plateau_center(plan))<0.20:
		return "出生点距目标台地过近。"
	return ""

static func example() -> Dictionary:
	var file:=FileAccess.get_file_as_string("@TERRAIN3D_EDITOR_ROOT@/landscape/march-layout.json")
	return JSON.parse_string(file)
