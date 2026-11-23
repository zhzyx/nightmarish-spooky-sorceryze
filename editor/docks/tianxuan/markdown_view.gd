@tool
extends RichTextLabel
## Render document text through native text shaping; no HTML engine or BBCode injection.

var ui_scale := 1.0
var _markdown := ""
var _has_markdown := false
var _patterns := {}


func _init() -> void:
	auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	var expressions := {
		"heading": r"^(#{1,6})\s+(.+)$",
		"fence": r"^(`{3,}|~{3,})(.*)$",
		"list": r"^(\s*)([-+*]|[0-9]+\.)\s+(.*)$",
		"task": r"^\[([ xX])\]\s+(.*)$",
		"rule": r"^([-*_])(?:\s*\1){2,}\s*$",
		"separator": r"^:?-{3,}:?$",
		"inline": r"(\\[\\`*_{}\[\]()#+.!|>~-]|`+[^`]+`+|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\n]+\*|_[^_\n]+_|!?\[[^\]]*\]\([^\s)]+\))"
	}
	for key in expressions:
		var pattern := RegEx.new()
		pattern.compile(expressions[key])
		_patterns[key] = pattern
func _ready() -> void:
	fit_content = true
	scroll_active = false
	selection_enabled = true
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	context_menu_enabled = true
	meta_clicked.connect(_open_link)
	theme_changed.connect(func():
		if _has_markdown:
			_has_markdown = false
			set_markdown(_markdown)
	)


func _open_link(value: Variant) -> void:
	var target := str(value)
	var controller: Node = get_meta("controller", null)
	if controller and target.begins_with("/docs/"):
		controller.documents.open(target.trim_prefix("/docs/").get_slice("?", 0).get_slice("#", 0).uri_decode())
		controller.navigate("documents")
	elif controller and target.begins_with("/issues/"):
		controller.navigate("issues", target.trim_prefix("/issues/").get_slice("?", 0).get_slice("#", 0).uri_decode())
	elif target.begins_with("https://") or target.begins_with("http://") or target.begins_with("mailto:"):
		OS.shell_open(target)


func _match(key: String, value: String) -> RegExMatch:
	return _patterns[key].search(value)


func _cells(line: String) -> Array[String]:
	var value := line.strip_edges().trim_prefix("|").trim_suffix("|")
	var cells: Array[String] = []
	var cell := ""
	var escaped := false
	var code := false
	for character in value:
		if character == "|" and not escaped and not code:
			cells.append(cell.strip_edges())
			cell = ""
		else:
			cell += character
		if character == "`" and not escaped:
			code = not code
		escaped = character == "\\" and not escaped
	cells.append(cell.strip_edges())
	return cells


func _table_separator(value: String, count: int) -> bool:
	var cells := _cells(value)
	if count < 2 or count > 32 or cells.size() != count:
		return false
	for cell in cells:
		if _match("separator", cell) == null:
			return false
	return true


func _table(rows: Array, separators: Array[String]) -> void:
	var columns := separators.size()
	push_table(columns)
	for column in columns:
		set_table_column_expand(column, true)
	for row_index in rows.size():
		for column in columns:
			push_cell()
			set_cell_padding(Rect2(Vector2(9, 6) * ui_scale, Vector2(9, 6) * ui_scale))
			var color := get_theme_color("default_color", "RichTextLabel")
			set_cell_border_color(Color(color, 0.15))
			set_cell_row_background_color(Color(color, 0.05), Color.TRANSPARENT)
			var separator := separators[column]
			var align := HORIZONTAL_ALIGNMENT_LEFT
			if separator.ends_with(":"):
				align = HORIZONTAL_ALIGNMENT_CENTER if separator.begins_with(":") else HORIZONTAL_ALIGNMENT_RIGHT
			push_paragraph(align)
			if row_index == 0:
				push_bold()
			_inline(rows[row_index][column] if column < rows[row_index].size() else "")
			if row_index == 0:
				pop()
			pop()
			pop()
	pop()


func set_markdown(markdown: String) -> void:
	if _has_markdown and markdown == _markdown:
		return
	_markdown = markdown
	_has_markdown = true
	clear()
	var lines := markdown.replace("\r\n", "\n").split("\n")
	var index := 0
	while index < lines.size():
		var line: String = lines[index]
		var trimmed := line.strip_edges()
		var fence := _match("fence", trimmed)
		if fence:
			var delimiter := fence.get_string(1)
			var language := fence.get_string(2).strip_edges()
			if not language.is_empty():
				push_font_size(roundi(12 * ui_scale))
				add_text(language + "\n")
				pop()
			push_indent(1)
			push_mono()
			index += 1
			while index < lines.size():
				var closing := _match("fence", lines[index].strip_edges())
				if closing and closing.get_string(1).begins_with(delimiter[0]) and closing.get_string(1).length() >= delimiter.length() and closing.get_string(2).strip_edges().is_empty():
					index += 1
					break
				add_text(lines[index] + "\n")
				index += 1
			pop()
			pop()
			add_text("\n")
			continue
		var cells := _cells(trimmed)
		if "|" in trimmed and index + 1 < lines.size() and _table_separator(lines[index + 1], cells.size()):
			var rows: Array = [cells]
			var separators := _cells(lines[index + 1])
			index += 2
			while index < lines.size() and "|" in lines[index] and not lines[index].strip_edges().is_empty():
				rows.append(_cells(lines[index]))
				index += 1
			_table(rows, separators)
			add_text("\n\n")
			continue
		var heading := _match("heading", trimmed)
		var listing := _match("list", line)
		if heading:
			push_font_size(roundi((29 - heading.get_string(1).length() * 2) * ui_scale))
			push_bold()
			_inline(heading.get_string(2))
			pop()
			pop()
		elif _match("rule", trimmed):
			push_color(Color(get_theme_color("default_color", "RichTextLabel"), 0.3))
			add_text("────────────────────────")
			pop()
		elif listing:
			push_indent(1 + mini(8, floori(listing.get_string(1).replace("\t", "    ").length() / 2.0)))
			var body := listing.get_string(3)
			var task := _match("task", body)
			if task:
				add_text("☐  " if task.get_string(1) == " " else "☑  ")
				_inline(task.get_string(2))
			else:
				add_text(listing.get_string(2) + "  " if listing.get_string(2).ends_with(".") else "•  ")
				_inline(body)
			pop()
		elif trimmed.begins_with(">"):
			push_indent(1)
			push_italics()
			_inline(trimmed.trim_prefix(">").strip_edges())
			pop()
			pop()
		else:
			_inline(line)
		if index < lines.size() - 1:
			add_text("\n")
		index += 1


func _inline(value: String, depth := 0) -> void:
	if depth > 8:
		add_text(value)
		return
	var cursor := 0
	for part in _patterns.inline.search_all(value):
		add_text(value.substr(cursor, part.get_start() - cursor))
		var content: String = part.get_string()
		if content.begins_with("\\"):
			add_text(content.substr(1))
		elif content.begins_with("`"):
			push_mono()
			add_text(content.trim_prefix("`").trim_suffix("`"))
			pop()
		elif content.begins_with("**") or content.begins_with("__"):
			push_bold()
			_inline(content.substr(2, content.length() - 4), depth + 1)
			pop()
		elif content.begins_with("~~"):
			push_strikethrough()
			_inline(content.substr(2, content.length() - 4), depth + 1)
			pop()
		elif content.begins_with("*") or content.begins_with("_"):
			push_italics()
			_inline(content.substr(1, content.length() - 2), depth + 1)
			pop()
		else:
			var boundary := content.find("](")
			push_meta(content.substr(boundary + 2, content.length() - boundary - 3))
			add_text(content.substr(2 if content.begins_with("!") else 1, boundary - (2 if content.begins_with("!") else 1)))
			pop()
		cursor = part.get_end()
	add_text(value.substr(cursor))
