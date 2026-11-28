@tool
extends RefCounted

const SAMPLES := 256
const SHAPES := ["valley", "mountains", "island", "plains", "plateau"]
const TITLES := ["河谷", "山脉", "海岛", "丘陵平原", "台地"]
enum Guide { LAYOUT, HEIGHT, REFERENCE }

static func contains_any(text: String, words: Array) -> bool:
	for word in words:
		if text.contains(word):
			return true
	return false

static func local_recipe(description: String) -> Dictionary:
	var text := description.to_lower()
	var shape := "mountains"
	if contains_any(text, ["谷", "河", "通道", "峡", "valley", "canyon", "river"]):
		shape = "valley"
	elif contains_any(text, ["岛", "海岸", "island", "coast"]):
		shape = "island"
	elif contains_any(text, ["高原", "台地", "平台", "plateau", "mesa"]):
		shape = "plateau"
	elif contains_any(text, ["平原", "草原", "丘陵", "平地", "plain", "hill"]):
		shape = "plains"
	var width := 0.28
	if contains_any(text, ["宽", "宽阔", "wide", "broad"]):
		width = 0.48
	elif contains_any(text, ["窄", "狭", "narrow"]):
		width = 0.13
	var roughness := 0.32
	if contains_any(text, ["平缓", "低缓", "平滑", "柔", "smooth", "gentle"]):
		roughness = 0.12
	elif contains_any(text, ["陡", "险", "崎岖", "峻", "rugged", "steep"]):
		roughness = 0.64
	var angle := 90.0 if contains_any(text, ["东西", "东向西", "西向东", "east-west"]) else 0.0
	return {"shape": shape, "width": width, "roughness": roughness, "angle": angle, "features": []}

static func validate_recipe(value: Variant) -> bool:
	if not value is Dictionary or not SHAPES.has(value.get("shape")):
		return false
	for key in ["width", "roughness", "angle"]:
		if not numeric(value.get(key)):
			return false
	if value.width < 0.05 or value.width > 0.85 or value.roughness < 0 or value.roughness > 1 or absf(value.angle) > 360:
		return false
	var details: Variant = value.get("features")
	if not details is Array or details.size() > 8:
		return false
	for point in details:
		if not point is Dictionary:
			return false
		for key in ["x", "z", "radius", "amount"]:
			if not numeric(point.get(key)):
				return false
		if absf(point.x) > 1 or absf(point.z) > 1 or point.radius < 0.08 or point.radius > 1.5 or absf(point.amount) > 1:
			return false
	return true

static func numeric(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))

static func build(recipe: Dictionary, seed_value: int, relief: float, guide: Image, mode: int) -> Image:
	var source: Image
	if guide != null and mode != Guide.REFERENCE:
		source = guide.duplicate()
		source.convert(Image.FORMAT_RGBAF)
		source.resize(SAMPLES, SAMPLES, Image.INTERPOLATE_BILINEAR)
	var noise := FastNoiseLite.new()
	noise.seed = seed_value
	noise.frequency = 1.75
	noise.fractal_octaves = 4
	var heading := deg_to_rad(float(recipe.angle))
	var axis := Vector2(cos(heading), sin(heading))
	var width: float = recipe.width
	var roughness: float = recipe.roughness
	var heights := PackedFloat32Array()
	heights.resize(SAMPLES * SAMPLES)
	for z in SAMPLES:
		for x in SAMPLES:
			var pos := Vector2(x, z) * (2.0 / (SAMPLES - 1)) - Vector2.ONE
			var pixel := z * SAMPLES + x
			if source != null and mode == Guide.HEIGHT:
				var lum := source.get_pixel(x, z).get_luminance()
				heights[pixel] = clampf(lum, 0, 1) * relief if is_finite(lum) else 0.0
				continue
			var cross_slope := pos.dot(axis)
			var along := pos.dot(axis.orthogonal())
			var n := noise.get_noise_2dv(pos)
			var warp := noise.get_noise_2d(along * 0.7, 8.75) * 0.24
			var distance := absf(cross_slope - warp)
			var h: float
			match recipe.shape:
				"valley":
					var wall := smoothstep(width * 0.55, width + 0.58, distance)
					h = 0.07 + wall * (0.66 + 0.20 * n)
				"island":
					h = maxf(0.0, 0.86 - smoothstep(0.12, 1.0, pos.length() + 0.22 * n))
				"plains":
					h = 0.18 + 0.12 * n + 0.08 * sin(along * 2.4 + warp)
				"plateau":
					h = 0.12 + 0.65 * (1.0 - smoothstep(0.42, 0.68, pos.length() + n * 0.20))
				_:
					var ridge := maxf(0.0, 1.0 - distance / (0.42 + width))
					h = 0.10 + ridge * (0.64 + 0.28 * n) + 0.10 * n
			h += roughness * n * (0.30 if recipe.shape == "plains" else 0.65)
			for point in recipe.features:
				var dist := pos.distance_to(Vector2(point.x, point.z)) / float(point.radius)
				h += float(point.amount) * (1.0 - smoothstep(0.0, 1.0, dist))
			if source != null:
				var c := source.get_pixel(x, z)
				var ridge_ink := clampf(c.r - maxf(c.g, c.b), 0.0, 1.0) * c.a
				var water_ink := clampf(c.b - maxf(c.r, c.g), 0.0, 1.0) * c.a
				var flat_ink := clampf(c.g - maxf(c.r, c.b), 0.0, 1.0) * c.a
				h = lerpf(h, 0.84 + 0.10 * n, ridge_ink)
				h = lerpf(h, 0.03, water_ink)
				h = lerpf(h, 0.16, flat_ink)
			heights[pixel] = clampf(h, 0.0, 1.0) * relief
	return Image.create_from_data(SAMPLES, SAMPLES, false, Image.FORMAT_RF, heights.to_byte_array())
