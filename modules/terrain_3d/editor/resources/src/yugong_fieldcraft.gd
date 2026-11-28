@tool
extends RefCounted

# Operations are deliberately independent of the spatial layout. Old layouts omit them.
const DEFAULTS := {"river_width":100.0, "road_width":100.0, "plateau_rise":100.0, "sightline":true}
const COMPASS := {"西北":Vector2(-1,-1), "东北":Vector2(1,-1), "西南":Vector2(-1,1), "东南":Vector2(1,1),
	"北":Vector2.UP, "南":Vector2.DOWN, "西":Vector2.LEFT, "东":Vector2.RIGHT}
const MODEL_BRIEF := """把地形描述转为一个 JSON 对象。只给 JSON，无需代码块或坐标。
spawn 和 goal 选不同方位 N/S/E/W/NE/NW/SE/SW；landmark 选 ruin/tree/cairn；flow 表示河流从哪流向哪，选 NS/SN/WE/EW；bridge 是过桥古道，选 east/west。
可选 operations 内 river_width、road_width、plateau_rise 为 60 到 160 的百分数（默认 100），sightline 为布尔值（默认 true）。
示例 {"spawn":"S","goal":"NW","landmark":"ruin","flow":"NS","bridge":"east"}"""
const DIRECTIONS := "(西北|东北|西南|东南|北|南|西|东)"

static func matches(text:String, pattern:String) -> bool:
	var re:=RegEx.create_from_string(pattern)
	return re.search(text)!=null

static func direction_for(text:String, role:String, fallback:Vector2) -> Vector2:
	var place:="(?:上|部|侧|面|边|方|角|岸|坡|肩|端|的|高地|台地|山上|山坡|山脚|有|设|是|建|设立|有一座|放置|设置|设在|为|作为|处){0,5}"
	for pattern:String in [DIRECTIONS+place+role,role+"(?:点|在|位于|设在|放在|建在|位于地图|朝向|于){0,4}"+DIRECTIONS]:
		var hit:=RegEx.create_from_string(pattern).search(text)
		if hit:return COMPASS[hit.get_string(1)]
	return fallback

# Binary fractions round-trip exactly through the editor's JSON reader.
# At the largest supported map size the coordinate rounding is at most 3.125 cm.
static func coordinate(value:float) -> float:
	return roundf(value*32768.0)/32768.0

static func point(p:Vector2) -> Dictionary:
	return {"x":coordinate(p.x),"z":coordinate(p.y)}

static func cross_coords(along:float, across:float, horizontal:bool) -> Vector2:
	return Vector2(along,across) if horizontal else Vector2(across,along)

static func operation_error(ops:Variant) -> String:
	if not ops is Dictionary or not ops.get("sightline") is bool:
		return "缺少有效的地标通视设置。"
	for key in ["river_width","road_width","plateau_rise"]:
		var v:Variant=ops.get(key)
		if not (v is float or v is int) or not is_finite(float(v)) or v<60 or v>160:
			return "整形参数须在 60% 至 160% 之间。"
	return ""

static func text_intent(description:String) -> Dictionary:
	var text:=description.replace(" ","")
	if matches(text,"(?:无|没有|不要|不需要)(?:任何)?(?:河|水系|道路|桥)") or matches(text,"(?:只要|仅有|只有)一条路"):
		return {"error":"当前离线布局支持一条河和两条古道。可用高度草案制作无河或无路的地貌。"}
	var home:=direction_for(text,"(?:出生|出发|起点)",Vector2.ZERO)
	var dest:=direction_for(text,"(?:残堡|古堡|城堡|堡垒|石冢|石堆|古树|金树|神树|目标台地)",Vector2.ZERO)
	if home==Vector2.ZERO:
		home=Vector2.UP if dest==Vector2.DOWN else Vector2.DOWN
	if dest==Vector2.ZERO:
		dest=Vector2(-1,-1) if home!=Vector2(-1,-1) else Vector2(1,1)
	if home==dest:
		return {"error":"出生点与目标位于同一方位，请给两者指定不同的方位。"}
	var landmark:="ruin"
	if not matches(text,"城堡|残堡|古堡|堡垒|遗迹"):
		if matches(text,"石冢|石堆|石碑"):landmark="cairn"
		elif matches(text,"古树|金树|神树|金梣"):landmark="tree"
	var horizontal:=matches(text,"东西向|东西走向|自西向东|从西向东|自东向西|从东向西|东西流|东西贯穿|横向河")
	var reverse:=matches(text,"自东向西|从东向西|自南向北|从南向北")
	var west_crosses:=matches(text,"西(?:线|路|侧古道|侧道路|边的路)(?:经|走|穿|跨|过|上|有|沿着|一座|石|拱|旧){0,5}桥")
	var ops:=DEFAULTS.duplicate()
	if matches(text,"宽河|宽阔的河|开阔河"):ops.river_width=140.0
	elif matches(text,"窄河|溪流|小溪"):ops.river_width=70.0
	if matches(text,"宽路|大道|宽阔的路"):ops.road_width=135.0
	elif matches(text,"小径|小路|窄路"):ops.road_width=75.0
	if matches(text,"高台地|高耸|陡峭台地"):ops.plateau_rise=130.0
	elif matches(text,"低台地|低缓"):ops.plateau_rise=70.0
	var meander:=.024 if matches(text,"直河|笔直|平直河") else (.09 if matches(text,"蜿蜒|曲折|弯曲") else .055)
	var radius:=.12 if matches(text,"小台地|窄台地") else (.23 if matches(text,"宽台地|大台地") else .165)
	var count:=9 if matches(text,"群山|高山|山脊") else 6
	return {"home":home,"dest":dest,"landmark":landmark,"horizontal":horizontal,"reverse":reverse,
		"west":west_crosses,"meander":meander,"radius":radius,"count":count,"ops":ops}

# A small model or a form can describe five roles without synthesizing any control points.
static func structured_intent(text:String) -> Dictionary:
	var decoder:=JSON.new()
	if decoder.parse(text)!=OK or not decoder.data is Dictionary:
		return {"error":"意图 JSON 格式无效。"}
	var data:Dictionary=decoder.data
	for key in data:
		if key not in ["spawn","goal","landmark","flow","bridge","operations"]:
			return {"error":"未知的意图字段："+str(key)}
	var dirs:={"N":Vector2.UP,"S":Vector2.DOWN,"E":Vector2.RIGHT,"W":Vector2.LEFT,
		"NW":Vector2(-1,-1),"NE":Vector2(1,-1),"SW":Vector2(-1,1),"SE":Vector2(1,1)}
	if not dirs.has(data.get("spawn")) or not dirs.has(data.get("goal")) or data.spawn==data.goal:
		return {"error":"spawn 和 goal 需要不同的罗盘方位，例如 S、NW。"}
	if data.get("landmark") not in ["ruin","tree","cairn"] or data.get("flow") not in ["NS","SN","WE","EW"] or data.get("bridge") not in ["east","west"]:
		return {"error":"请填写 landmark（ruin/tree/cairn）、flow（NS/SN/WE/EW）及 bridge（east/west）。"}
	var ops:=DEFAULTS.duplicate()
	var overrides:Variant=data.get("operations",{})
	if not overrides is Dictionary:return {"error":"operations 需要是参数对象。"}
	for key in overrides:
		if not ops.has(key):return {"error":"未知的整形参数："+str(key)}
		ops[key]=overrides[key]
	var issue:=operation_error(ops)
	if not issue.is_empty():return {"error":issue}
	return {"home":dirs[data.spawn],"dest":dirs[data.goal],"landmark":data.landmark,
		"horizontal":data.flow in ["WE","EW"],"reverse":data.flow in ["SN","EW"],
		"west":data.bridge=="west","meander":.055,"radius":.165,"count":6,"ops":ops}

static func compile_layout(description:String, seed_value:int) -> Dictionary:
	var intent:=structured_intent(description) if description.strip_edges().begins_with("{") else text_intent(description)
	if intent.has("error"):return intent
	var home:Vector2=intent.home
	var dest:Vector2=intent.dest
	var horizontal:bool=intent.horizontal
	var west_crosses:bool=intent.west
	var meander:float=intent.meander
	var radius:float=intent.radius
	var rng:=RandomNumberGenerator.new()
	rng.seed=seed_value
	var spawn:=home.normalized()*.55+Vector2(-home.y,home.x)*rng.randf_range(-.065,.065)
	var target:=dest.normalized()*.48
	var target_side:=Vector2(-dest.y,dest.x).normalized()
	target+=target_side*rng.randf_range(-.045,.045)
	var across:=Vector2.DOWN if horizontal else Vector2.RIGHT
	var along:=Vector2.RIGHT if horizontal else Vector2.DOWN
	var bank:=.25 if not west_crosses else -.25
	# Choose an offset that leaves BOTH endpoints on dry ground, including the widest supported channel.
	var offsets:Array[float]=[bank,bank*1.65,-bank,-bank*1.65]
	var preferred:=bank
	var best:=-INF
	for offset in offsets:
		var clearance:=minf(absf(spawn.dot(across)-offset),absf(target.dot(across)-offset))
		var score:=minf(.23,clearance)-absf(offset-preferred)*.06
		if score>best:
			best=score
			bank=offset
	var phase:=rng.randf_range(-PI,PI)
	var river:Array=[]
	for i in 11:
		var a:=-.995+i*.199
		river.append(point(cross_coords(a,bank+meander*sin(4.2*a+phase),horizontal)))
	if intent.reverse:river.reverse()
	var plateau:Array=[]
	for i in 6:
		var angle:=TAU*i/6
		plateau.append(point(target+Vector2(cos(angle)*radius,sin(angle)*radius*.82)))
	var east:Array=[]
	var west:Array=[]
	var home_bank:=signf(spawn.dot(across)-bank)
	for u:float in [.12,.30,.49,.70,.87]:
		var mid:=spawn.lerp(target,u)
		var weight:=sin(PI*u)
		var edge:=bank+meander*sin(4.2*mid.dot(along)+phase)
		var near_lane:=edge+home_bank*(.32+.10*weight)
		var far_lane:=edge-home_bank*(.19+.09*weight)
		var inland:=mid+across*(near_lane-mid.dot(across))*minf(1,weight*1.45)
		var crossing:=mid+across*(far_lane-mid.dot(across))*minf(1,weight*1.65)
		# When the river follows the journey crosswise, separate the routes along its banks as well.
		if absf((target-spawn).normalized().dot(along))<.45:
			inland-=along*.30*weight
			crossing+=along*.28*weight
		east.append(point((inland if west_crosses else crossing).clamp(Vector2(-.90,-.90),Vector2(.90,.90))))
		west.append(point((crossing if west_crosses else inland).clamp(Vector2(-.90,-.90),Vector2(.90,.90))))
	var hills:Array=[]
	var count:int=intent.count
	for i in count:
		var angle:=TAU*(i+rng.randf_range(-.21,.21))/count
		var center:=Vector2.from_angle(angle)*rng.randf_range(.61,.86)
		var ridge:=point(center)
		ridge.radius=coordinate(rng.randf_range(.17,.33))
		ridge.height=coordinate(rng.randf_range(.42,.83))
		hills.append(ridge)
	return {"spawn":point(spawn),"plateau":plateau,"river":river,"west_road":west,"east_road":east,
		"ridge_road":"east_road" if west_crosses else "west_road",
		"ridges":hills,"landmark":intent.landmark,"operations":intent.ops}
