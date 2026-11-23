@tool
extends RefCounted
## Semantic visual tokens, scoped to Tianxuan. Never modifies the global editor theme.


static func palette(dark: bool) -> Dictionary:
	if dark:
		return {"canvas": Color("151a23"), "sidebar": Color("11161e"), "surface": Color("1e2632"), "inset": Color("181f29"), "hover": Color("2b3747"), "line": Color("334155"), "text": Color("e7edf5"), "muted": Color("a7b5c9"), "accent": Color("7ed9c3"), "accent_fill": Color("1c6c60"), "accent_soft": Color("233e3e"), "warning": Color("f3ce85"), "error": Color("ffa1a1")}
	return {"canvas": Color("f5f7fa"), "sidebar": Color("edf1f6"), "surface": Color("ffffff"), "inset": Color("f0f3f7"), "hover": Color("e5ebf2"), "line": Color("d5dee9"), "text": Color("19283b"), "muted": Color("52657d"), "accent": Color("17695e"), "accent_fill": Color("17695e"), "accent_soft": Color("dfefea"), "warning": Color("805b15"), "error": Color("b83246")}


static func prepare_layout(node: Node) -> void:
	if node is OptionButton:
		node.fit_to_longest_item = false
		node.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	elif node is Button and node.get_parent() is VBoxContainer:
		node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	elif node is Label and node.theme_type_variation in [&"TianxuanTitle", &"TianxuanHeading"]:
		node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if node is TabContainer:
		node.clip_tabs = true
	for child in node.get_children():
		prepare_layout(child)


static func box(color: Color, border: Color, radius: float, padding: float, scale: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(maxi(1, roundi(scale)))
	style.set_corner_radius_all(roundi(radius * scale))
	style.set_content_margin_all(padding * scale)
	return style


static func build(base: Theme, scale: float, dark: bool) -> Theme:
	# EditorTheme is internal and cannot be instantiated by Resource.duplicate().
	# Copy its entries into a plain Theme, then replace only Tianxuan's own styles.
	var theme := Theme.new()
	if base:
		theme.merge_with(base)
		theme.default_font = base.default_font
	var p := palette(dark)
	theme.default_font_size = roundi(14 * scale)
	for control in ["Label", "Button", "LineEdit", "TextEdit", "RichTextLabel", "Tree", "ItemList", "OptionButton", "CheckBox", "PopupMenu", "TabBar", "TabContainer"]:
		theme.set_color("font_color", control, p.text)
		theme.set_color("font_hover_color", control, p.text)
		theme.set_color("font_disabled_color", control, p.muted)
		theme.set_color("font_focus_color", control, p.text)
		theme.set_color("font_pressed_color", control, p.text)
		theme.set_color("font_hover_pressed_color", control, p.text)
		theme.set_color("font_selected_color", control, p.text)
		theme.set_color("font_unselected_color", control, p.muted)
	theme.set_color("default_color", "RichTextLabel", p.text)
	theme.set_color("font_readonly_color", "TextEdit", p.muted)
	theme.set_color("font_uneditable_color", "LineEdit", p.muted)
	for kind in ["VBoxContainer", "HBoxContainer"]:
		theme.set_constant("separation", kind, roundi(10 * scale))
	for variant in ["TianxuanTitle", "TianxuanHeading", "TianxuanMuted", "TianxuanCaption"]:
		theme.set_type_variation(variant, "Label")
	theme.set_font_size("font_size", "TianxuanTitle", roundi(27 * scale))
	theme.set_font_size("font_size", "TianxuanHeading", roundi(18 * scale))
	if base and base.has_font("bold", "EditorFonts"):
		for variant in ["TianxuanTitle", "TianxuanHeading"]:
			theme.set_font("font", variant, base.get_font("bold", "EditorFonts"))
	theme.set_font_size("font_size", "TianxuanCaption", roundi(12 * scale))
	theme.set_color("font_color", "TianxuanCaption", p.muted)
	theme.set_color("font_color", "TianxuanMuted", p.muted)
	for variant in ["TianxuanCanvas", "TianxuanSidebar", "TianxuanCard", "TianxuanInset"]:
		theme.set_type_variation(variant, "PanelContainer")
	theme.set_stylebox("panel", "TianxuanCanvas", box(p.canvas, p.canvas, 0, 20, scale))
	theme.set_stylebox("panel", "TianxuanSidebar", box(p.sidebar, p.line, 12, 12, scale))
	theme.set_stylebox("panel", "TianxuanCard", box(p.surface, p.line, 12, 18, scale))
	theme.set_stylebox("panel", "TianxuanInset", box(p.inset, p.line, 8, 12, scale))
	for variant in ["TianxuanPrimaryButton", "TianxuanNavigationButton"]:
		theme.set_type_variation(variant, "Button")
	for state in ["normal", "hover", "pressed", "disabled"]:
		var background: Color = p.surface
		if state in ["hover", "pressed"]:
			background = p.hover
		theme.set_stylebox(state, "Button", box(background, p.line, 7, 9, scale))
		theme.set_stylebox(state, "OptionButton", box(background, p.line, 7, 9, scale))
		theme.set_stylebox(state, "TianxuanPrimaryButton", box(p.hover if state == "disabled" else p.accent_fill.lightened(0.08) if state == "hover" else p.accent_fill, p.line if state == "disabled" else p.accent_fill, 7, 10, scale))
		theme.set_color("font_" + state + "_color", "TianxuanPrimaryButton", Color.WHITE)
		theme.set_stylebox(state, "TianxuanNavigationButton", box(p.accent_soft if state == "pressed" else p.hover if state == "hover" else p.sidebar, p.sidebar, 7, 10, scale))
	theme.set_color("font_color", "TianxuanPrimaryButton", Color.WHITE)
	theme.set_color("font_focus_color", "TianxuanPrimaryButton", Color.WHITE)
	theme.set_color("font_disabled_color", "TianxuanPrimaryButton", p.muted)
	theme.set_color("font_pressed_color", "TianxuanNavigationButton", p.accent)
	var focus := box(Color.TRANSPARENT, p.accent, 7, 0, scale)
	focus.set_border_width_all(maxi(2, roundi(2 * scale)))
	for kind in ["Button", "OptionButton", "LineEdit", "TextEdit", "Tree", "ItemList"]:
		theme.set_stylebox("focus", kind, focus)
	for kind in ["LineEdit", "TextEdit", "Tree", "ItemList"]:
		theme.set_stylebox("normal" if kind in ["LineEdit", "TextEdit"] else "panel", kind, box(p.inset, p.line, 7, 10, scale))
		theme.set_color("selection_color", kind, p.accent_soft)
		theme.set_color("font_selected_color", kind, p.text)
		theme.set_color("caret_color", kind, p.accent)
	for kind in ["LineEdit", "TextEdit"]:
		theme.set_stylebox("read_only", kind, box(p.canvas, p.line, 7, 10, scale))
	for kind in ["Tree", "ItemList"]:
		for state in ["selected", "selected_focus"]:
			theme.set_stylebox(state, kind, box(p.accent_soft, p.accent_soft, 4, 4, scale))
	theme.set_stylebox("panel", "PopupMenu", box(p.surface, p.line, 8, 8, scale))
	theme.set_stylebox("hover", "PopupMenu", box(p.accent_soft, p.accent_soft, 4, 6, scale))
	theme.set_color("font_hover_color", "PopupMenu", p.accent)
	theme.set_stylebox("panel", "TabContainer", box(p.canvas, p.line, 8, 14, scale))
	for kind in ["TabContainer", "TabBar"]:
		for state in ["tab_selected", "tab_unselected", "tab_hovered", "tab_disabled"]:
			theme.set_stylebox(state, kind, box(p.accent_soft if state == "tab_selected" else p.canvas, p.canvas, 6, 10, scale))
		theme.set_color("font_selected_color", kind, p.accent)
	var separator := StyleBoxLine.new()
	separator.color = p.line
	separator.thickness = maxi(1, roundi(scale))
	theme.set_stylebox("separator", "HSeparator", separator)
	theme.set_color("font_placeholder_color", "LineEdit", p.muted)
	theme.set_color("font_placeholder_color", "TextEdit", p.muted)
	theme.set_constant("line_spacing", "TextEdit", roundi(5 * scale))
	theme.set_constant("line_separation", "RichTextLabel", roundi(5 * scale))
	theme.set_constant("v_separation", "Tree", roundi(8 * scale))
	return theme
