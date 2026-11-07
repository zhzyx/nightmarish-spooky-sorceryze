@tool
extends RefCounted


# Only manual positions obstruct the automatic lanes. Move down to the first clear interval.
static func clear_pinned_space(rect: Rect2, obstacles: Array[Rect2], gap: float) -> Vector2:
	for obstacle in obstacles:
		if rect.intersects(obstacle.grow(gap)):
			rect.position.y = obstacle.end.y + gap
	return rect.position


static func arrange_flow(canvas: GraphEdit, layout_columns: Array, positions: Dictionary) -> void:
	if layout_columns.is_empty():
		return
	var scale_factor := canvas.get_theme_default_base_scale()
	var gap := Vector2(88, 36) * scale_factor
	var obstacles: Array[Rect2] = []
	for id in positions:
		var card := canvas.get_node_or_null(NodePath(str(id))) as GraphNode
		if card:
			obstacles.append(Rect2(positions[id], card.size.max(card.get_combined_minimum_size())))
	obstacles.sort_custom(func(a: Rect2, b: Rect2): return a.position.y < b.position.y)
	var x := 48.0 * scale_factor
	var center_y := 64.0 * scale_factor
	for level in layout_columns.size():
		var column: Array = layout_columns[level]
		var height := -gap.y
		var width := 0.0
		for card: GraphNode in column:
			var extent := card.size.max(card.get_combined_minimum_size())
			width = maxf(width, extent.x)
			height += extent.y + gap.y
		if level == 0:
			center_y += height / 2.0
		var y := center_y - height / 2.0
		for card: GraphNode in column:
			var extent := card.size.max(card.get_combined_minimum_size())
			if not positions.has(String(card.name)):
				card.position_offset = clear_pinned_space(Rect2(Vector2(x, y), extent), obstacles, gap.y)
				y = card.position_offset.y
			y += extent.y + gap.y
		x += width + gap.x



static func arrange_personal(overview: GraphEdit, board_cards: Array[GraphNode], pinned: Dictionary) -> void:
	var scale_factor := overview.get_theme_default_base_scale()
	var gap := Vector2(56, 36) * scale_factor
	var origin := Vector2(38, 75) * scale_factor
	var obstacles: Array[Rect2] = []
	var widths := PackedFloat32Array()
	widths.resize(clampi(floori((overview.size.x / scale_factor - 20) / 336.0), 1, 5))
	for i in board_cards.size():
		var card := board_cards[i]
		var extent := card.size.max(card.get_combined_minimum_size())
		var url: String = card.get_meta("issue_url")
		if pinned.has(url):
			card.position_offset = pinned[url]
			obstacles.append(Rect2(card.position_offset, extent))
		widths[i % widths.size()] = maxf(widths[i % widths.size()], extent.x)
	obstacles.sort_custom(func(a: Rect2, b: Rect2): return a.position.y < b.position.y)
	var y := origin.y
	for start in range(0, board_cards.size(), widths.size()):
		var x := origin.x
		var bottom := y
		for i in range(start, mini(start + widths.size(), board_cards.size())):
			var card := board_cards[i]
			var extent := card.size.max(card.get_combined_minimum_size())
			if not pinned.has(card.get_meta("issue_url")):
				card.position_offset = clear_pinned_space(Rect2(Vector2(x, y), extent), obstacles, gap.y)
				bottom = maxf(bottom, card.position_offset.y + extent.y)
			x += widths[i - start] + gap.x
		y = bottom + gap.y


static func arrange_creators(overview: GraphEdit, board_cards: Array[GraphNode], creator_sections: Dictionary) -> void:
	var scale_factor := overview.get_theme_default_base_scale()
	var gap := Vector2(56, 36) * scale_factor
	var origin := Vector2(38, 75) * scale_factor
	var groups := {}
	for card in board_cards:
		if card.visible:
			var creator: String = card.get_meta("creator_region")
			if not groups.has(creator):
				groups[creator] = []
			groups[creator].append(card)
	var x := origin.x
	var y := origin.y
	var bottom := y
	for creator: String in creator_sections:
		var frame: GraphFrame = creator_sections[creator]
		if not frame.visible:
			continue
		var pad := 16 * scale_factor
		var extent := Vector2(280 * scale_factor, 50 * scale_factor)
		for card: GraphNode in groups.get(creator, []):
			card.position_offset = Vector2(x + pad, y + extent.y)
			extent.y += card.size.y + pad
			extent.x = maxf(extent.x, card.size.x)
		frame.position_offset = Vector2(x, y)
		frame.size = Vector2(extent.x + 2 * pad, extent.y)
		bottom = maxf(bottom, y + frame.size.y)
		x += frame.size.x + gap.x
		if x + 312 * scale_factor > overview.size.x:
			x = origin.x
			y = bottom + gap.y


static func nearest_card(cards: Array[GraphNode], point: Vector2, region := "") -> GraphNode:
	var nearest: GraphNode
	var distance := INF
	for card in cards:
		if not card.visible or (not region.is_empty() and card.get_meta("creator_region") != region):
			continue
		if Rect2(card.position_offset, card.size).has_point(point):
			return card
		var squared := point.distance_squared_to(card.position_offset + card.size * 0.5)
		if squared < distance:
			distance = squared
			nearest = card
	return nearest
