/**************************************************************************/
/*  ai_chat_editor_registry.cpp                                           */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "ai_chat_editor_registry.h"

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/object/callable_mp.h"
#include "core/templates/hash_set.h"
#include "editor/docks/editor_dock.h"
#include "editor/editor_interface.h"
#include "editor/editor_node.h"
#include "editor/inspector/editor_inspector.h"
#include "scene/gui/base_button.h"
#include "scene/gui/button.h"
#include "scene/gui/color_picker.h"
#include "scene/gui/foldable_container.h"
#include "scene/gui/item_list.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/gui/popup_menu.h"
#include "scene/gui/scroll_bar.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/slider.h"
#include "scene/gui/spin_box.h"
#include "scene/gui/tab_bar.h"
#include "scene/gui/tab_container.h"
#include "scene/gui/text_edit.h"
#include "scene/gui/tree.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace {
Dictionary registry_result(bool p_ok, const String &p_error = String()) {
	Dictionary result;
	result["ok"] = p_ok;
	if (!p_error.is_empty()) {
		result["error"] = p_error;
	}
	return result;
}

void bound_items(Array &r_items) {
	while (!r_items.is_empty() && JSON::stringify(r_items).utf8().length() > 8192) {
		r_items.resize(r_items.size() - 1);
	}
}

bool registry_integer(const Variant &p_value, int64_t p_min, int64_t p_max, int64_t &r_value) {
	if (p_value.get_type() != Variant::INT && p_value.get_type() != Variant::FLOAT) {
		return false;
	}
	const double number = p_value;
	if (!Math::is_finite(number) || number < p_min || number > p_max || number != Math::floor(number)) {
		return false;
	}
	r_value = int64_t(number);
	return true;
}

String control_name(Node *p_control) {
	if (Button *button = Object::cast_to<Button>(p_control); button && !button->get_text().is_empty()) {
		return button->get_text().left(120);
	}
	if (EditorDock *dock = Object::cast_to<EditorDock>(p_control)) {
		return dock->get_display_title().left(120);
	}
	return String(p_control->get_name()).left(120);
}

TreeItem *tree_item_at(Tree *p_tree, int p_index) {
	TreeItem *item = p_tree->get_root();
	for (int i = 0; item && i < p_index && i < 4096; i++) {
		item = item->get_next_in_tree();
	}
	return p_index >= 0 && p_index < 4096 ? item : nullptr;
}

int text_offset(TextEdit *p_text, int p_line, int p_column) {
	int offset = p_column;
	for (int i = 0; i < p_line; i++) {
		offset += p_text->get_line(i).length() + 1;
	}
	return offset;
}

Dictionary text_selection(Control *p_control) {
	Dictionary result;
	if (LineEdit *line = Object::cast_to<LineEdit>(p_control)) {
		result["cursor"] = line->get_caret_column();
		result["start"] = line->has_selection() ? line->get_selection_from_column() : line->get_caret_column();
		result["end"] = line->has_selection() ? line->get_selection_to_column() : line->get_caret_column();
		result["caret_count"] = 1;
	} else if (TextEdit *text = Object::cast_to<TextEdit>(p_control)) {
		const int cursor = text_offset(text, text->get_caret_line(), text->get_caret_column());
		result["cursor"] = cursor;
		result["start"] = text->has_selection() ? text_offset(text, text->get_selection_from_line(), text->get_selection_from_column()) : cursor;
		result["end"] = text->has_selection() ? text_offset(text, text->get_selection_to_line(), text->get_selection_to_column()) : cursor;
		result["caret_count"] = text->get_caret_count();
	}
	return result;
}

Dictionary item_page(Control *p_control, int p_limit, int p_offset) {
	Dictionary result = registry_result(true);
	Array entries;
	int total = 0;
	bool lower_bound = false;
	if (Tree *tree = Object::cast_to<Tree>(p_control)) {
		TreeItem *item = tree->get_root();
		for (; item && total < 4096; total++, item = item->get_next_in_tree()) {
			if (total >= p_offset && entries.size() < p_limit) {
				Dictionary entry;
				entry["index"] = total;
				entry["instance"] = int64_t(item->get_instance_id());
				entry["text"] = item->get_text(0).left(120);
				entry["selected"] = item->is_selected(0);
				entry["selectable"] = item->is_selectable(0);
				entry["collapsed"] = item->is_collapsed();
				entries.push_back(entry);
			}
		}
		lower_bound = item != nullptr;
	} else {
		ItemList *items = Object::cast_to<ItemList>(p_control);
		TabBar *tabs = Object::cast_to<TabBar>(p_control);
		OptionButton *options = Object::cast_to<OptionButton>(p_control);
		total = items ? items->get_item_count() : tabs ? tabs->get_tab_count()
													   : options->get_item_count();
		for (int i = p_offset; i < MIN(total, p_offset + p_limit) && i < 4096; i++) {
			Dictionary entry;
			entry["index"] = i;
			entry["text"] = (items ? items->get_item_text(i) : tabs ? tabs->get_tab_title(i)
																	: options->get_item_text(i))
									.left(120);
			entry["disabled"] = items ? items->is_item_disabled(i) : tabs ? tabs->is_tab_disabled(i)
																		  : options->is_item_disabled(i);
			entry["selected"] = items ? items->is_selected(i) : tabs ? tabs->get_current_tab() == i
																	 : options->get_selected() == i;
			if (items) {
				entry["selectable"] = items->is_item_selectable(i);
			}
			if (tabs) {
				entry["hidden"] = tabs->is_tab_hidden(i);
			}
			entries.push_back(entry);
		}
	}
	bound_items(entries);
	result["items"] = entries;
	result["total"] = total;
	result["offset"] = p_offset;
	result["limit"] = p_limit;
	result["next_offset"] = p_offset + entries.size() < MIN(total, 4096) ? p_offset + entries.size() : -1;
	result["total_is_lower_bound"] = lower_bound;
	result["truncated"] = lower_bound || p_offset + entries.size() < total;
	result["capacity"] = 4096;
	result["target_instance"] = int64_t(p_control->get_instance_id());
	return result;
}

Variant control_value(Control *p_control) {
	if (Tree *tree = Object::cast_to<Tree>(p_control)) {
		String content;
		TreeItem *item = tree->get_root();
		for (int i = 0; item && i < 4096; i++, item = item->get_next_in_tree()) {
			Dictionary entry;
			entry["instance"] = int64_t(item->get_instance_id());
			entry["text_hash"] = item->get_text(0).sha256_text();
			entry["collapsed"] = item->is_collapsed();
			entry["selected"] = item->is_selected(0);
			entry["selectable"] = item->is_selectable(0);
			content += JSON::stringify(entry);
		}
		Dictionary state;
		state["content_hash"] = content.sha256_text();
		state["truncated"] = item != nullptr;
		return state;
	}
	if (ItemList *items = Object::cast_to<ItemList>(p_control)) {
		Dictionary state;
		state["selected"] = items->get_selected_items();
		state["count"] = items->get_item_count();
		String content;
		for (int i = 0; i < MIN(items->get_item_count(), 4096); i++) {
			content += items->get_item_text(i).sha256_text() + String::num_int64(items->is_item_disabled(i)) + String::num_int64(items->is_item_selectable(i));
		}
		state["content_hash"] = content.sha256_text();
		return state;
	}
	if (TabBar *tabs = Object::cast_to<TabBar>(p_control)) {
		Dictionary state;
		state["selected"] = tabs->get_current_tab();
		state["count"] = tabs->get_tab_count();
		String content;
		for (int i = 0; i < MIN(tabs->get_tab_count(), 4096); i++) {
			content += tabs->get_tab_title(i).sha256_text() + String::num_int64(tabs->is_tab_disabled(i)) + String::num_int64(tabs->is_tab_hidden(i));
		}
		state["content_hash"] = content.sha256_text();
		return state;
	}
	if (ColorPicker *picker = Object::cast_to<ColorPicker>(p_control)) {
		const Color color = picker->get_pick_color();
		Array components;
		components.push_back(color.r);
		components.push_back(color.g);
		components.push_back(color.b);
		components.push_back(color.a);
		return components;
	}
	if (ScrollContainer *scroll = Object::cast_to<ScrollContainer>(p_control)) {
		Array position;
		position.push_back(scroll->get_h_scroll());
		position.push_back(scroll->get_v_scroll());
		return position;
	}
	if (LineEdit *line = Object::cast_to<LineEdit>(p_control)) {
		return line->get_text();
	}
	if (TextEdit *text = Object::cast_to<TextEdit>(p_control)) {
		return text->get_text();
	}
	if (OptionButton *option = Object::cast_to<OptionButton>(p_control)) {
		return option->get_selected();
	}
	if (Range *range = Object::cast_to<Range>(p_control)) {
		return range->get_value();
	}
	if (BaseButton *button = Object::cast_to<BaseButton>(p_control)) {
		return button->is_pressed();
	}
	return Variant();
}
} // namespace

bool AIChatEditorRegistry::_excluded(Node *p_node) {
	if (EditorProperty *property = Object::cast_to<EditorProperty>(p_node)) {
		const String key = String(property->get_edited_property()).to_lower();
		const String normalized = key.replace("_", "").replace("-", "").replace("/", "");
		// EditorSettings renders the same host authority fields outside AI Chat.
		// Protect that representation too; safe chat configuration has its own API.
		if (key.begins_with("ai_chat/") || key.begins_with("gonggong/") || normalized.contains("password") || normalized.contains("credential") || normalized.contains("apikey") || normalized.contains("accesstoken") || normalized.contains("bearertoken") || normalized.contains("secret") || normalized.contains("token") || normalized.contains("authorization")) {
			return true;
		}
	}
	const String sensitive_name = String(p_node->get_name()).to_lower().replace("_", "").replace("-", "");
	if (sensitive_name.contains("password") || sensitive_name.contains("credential") || sensitive_name.contains("apikey") || sensitive_name.contains("accesstoken") || sensitive_name.contains("bearertoken")) {
		return true;
	}
	if (bool(p_node->get_meta("ai_control_exclude", false)) || p_node->get_name() == StringName("AIEditorHighlight")) {
		return true;
	}
	if (LineEdit *line = Object::cast_to<LineEdit>(p_node); line && line->is_secret()) {
		return true;
	}
	EditorInterface *editor = EditorInterface::get_singleton();
	return EditorNode::get_singleton() && editor && editor->get_edited_scene_root() == p_node;
}

bool AIChatEditorRegistry::is_protected(Node *p_node) {
	for (Node *node = p_node; node; node = node->get_parent()) {
		if (_excluded(node) || (node != p_node && bool(node->get_meta("ai_control_page_only", false)))) {
			return true;
		}
	}
	return false;
}

void AIChatEditorRegistry::_tree_changed(Node *p_node) {
	// Ignore the overlay's own attach/detach; it is never a capability target.
	if (p_node->get_name() != StringName("AIEditorHighlight")) {
		dirty = true;
	}
}

void AIChatEditorRegistry::_refresh() const {
	EditorNode *editor = EditorNode::get_singleton();
	SceneTree *tree = editor ? editor->get_tree() : nullptr;
	if (!tree || !editor) {
		return;
	}
	if (scene_tree != tree->get_instance_id()) {
		AIChatEditorRegistry *self = const_cast<AIChatEditorRegistry *>(this);
		tree->connect("node_added", callable_mp(self, &AIChatEditorRegistry::_tree_changed));
		tree->connect("node_removed", callable_mp(self, &AIChatEditorRegistry::_tree_changed));
		tree->connect("node_renamed", callable_mp(self, &AIChatEditorRegistry::_tree_changed));
		scene_tree = tree->get_instance_id();
		dirty = true;
	}
	if (!dirty) {
		return;
	}
	dirty = false;
	truncated = false;
	revision++;
	HashMap<String, Target> found;
	HashSet<String> ambiguous;
	HashMap<ObjectID, String> found_identities;
	struct Entry {
		Node *node;
		Control *page;
		String key;
	};
	LocalVector<Entry> stack;
	stack.push_back({ editor, nullptr, String() });
	// Breadth first: shallow/new pages remain discoverable even when a deep
	// native dialog subtree consumes the bounded registry capacity.
	int visited = 0;
	uint32_t cursor = 0;
	bool queue_truncated = false;
	while (cursor < stack.size() && visited < 50000 && found.size() < 8192) {
		visited++;
		const Entry entry = stack[cursor++];
		Node *node = entry.node;
		if (_excluded(node)) {
			continue;
		}
		Control *page = entry.page;
		String key = entry.key;
		Control *control = Object::cast_to<Control>(node);
		const bool dock_page = Object::cast_to<EditorDock>(control);
		const bool tab_page = control && Object::cast_to<TabContainer>(node->get_parent());
		const bool window_page = control && Object::cast_to<Window>(node->get_parent()) && node->get_parent() != tree->get_root();
		if (dock_page || tab_page || window_page || (control && (node->has_meta("ai_control_page") || AIChatEditorComplexActions::target(control)))) {
			page = control;
			if (EditorDock *dock = Object::cast_to<EditorDock>(control)) {
				key = "dock/" + dock->get_effective_layout_key();
			} else {
				key = entry.key + "/" + (entry.page ? String(entry.page->get_path_to(node)) : String(editor->get_path_to(node)));
			}
		}
		if ((Object::cast_to<PopupMenu>(node) || (control && page && (AIChatEditorComplexActions::target(control) || control == page || Object::cast_to<BaseButton>(control) || Object::cast_to<LineEdit>(control) || Object::cast_to<TextEdit>(control) || Object::cast_to<SpinBox>(control) || Object::cast_to<Slider>(control) || Object::cast_to<Tree>(control) || Object::cast_to<ItemList>(control) || Object::cast_to<TabBar>(control) || Object::cast_to<ColorPicker>(control) || Object::cast_to<ScrollContainer>(control))))) {
			const String identity = key + "/" + (page ? String(page->get_path_to(node)) : String(editor->get_path_to(node)));
			String id = "editor." + identity.sha256_text().left(32);
			if (const String *previous = identities.getptr(node->get_instance_id())) {
				id = *previous;
			}
			if (node->has_meta("ai_control_id")) {
				const String alias = node->get_meta("ai_control_id");
				if (!alias.is_empty() && alias.length() <= 96 && alias.is_valid_ascii_identifier()) {
					id = "editor." + alias;
				}
			}
			if (found.has(id)) {
				found_identities.erase(found[id].control);
				found.erase(id);
				ambiguous.insert(id);
			}
			if (!ambiguous.has(id)) {
				found[id] = { node->get_instance_id(), control_name(node), page ? control_name(page) : String("PopupMenu") };
				found_identities[node->get_instance_id()] = id;
			}
		}
		// Chat's authorization/composer controls are host state, not AI inputs.
		if (bool(node->get_meta("ai_control_page_only", false))) {
			continue;
		}
		for (int i = 0; i < node->get_child_count(); i++) {
			if (stack.size() >= 50000) {
				queue_truncated = true;
				break;
			}
			stack.push_back({ node->get_child(i), page, key });
		}
	}
	truncated = queue_truncated || cursor < stack.size();
	scanned_nodes = visited;
	queued_nodes = stack.size();
	targets = found;
	identities = found_identities;
}

Control *AIChatEditorRegistry::resolve(const String &p_id) const {
	return Object::cast_to<Control>(resolve_node(p_id));
}

Node *AIChatEditorRegistry::resolve_node(const String &p_id) const {
	_refresh();
	const Target *target = targets.getptr(p_id);
	Node *control = target ? ObjectDB::get_instance<Node>(target->control) : nullptr;
	if (!control || !control->is_inside_tree()) {
		return nullptr;
	}
	// Secret/editable state and exclusion metadata can change without tree events.
	for (Node *node = control; node; node = node->get_parent()) {
		if (_excluded(node) || (node != control && bool(node->get_meta("ai_control_page_only", false)))) {
			return nullptr;
		}
	}
	return control;
}

Array AIChatEditorRegistry::actions(Control *p_control) {
	Array result = AIChatEditorComplexActions::actions(p_control);
	for (const char *action : { "open_target", "reveal_target", "highlight" }) {
		result.push_back(action);
	}
	if (p_control->get_focus_mode() != Control::FOCUS_NONE) {
		result.push_back("focus");
	}
	if (LineEdit *line = Object::cast_to<LineEdit>(p_control); line && line->is_editable() && !line->is_secret()) {
		for (const char *action : { "read_text", "set_text", "append_text", "replace_text_range", "submit_text", "undo_text" }) {
			result.push_back(action);
		}
	} else if (TextEdit *text = Object::cast_to<TextEdit>(p_control); text && text->is_editable()) {
		for (const char *action : { "read_text", "set_text", "append_text", "replace_text_range", "undo_text" }) {
			result.push_back(action);
		}
	}
	if (OptionButton *option = Object::cast_to<OptionButton>(p_control); option && !option->is_disabled()) {
		result.push_back("select_option");
	} else if (BaseButton *button = Object::cast_to<BaseButton>(p_control); button && !button->is_disabled()) {
		result.push_back("press");
	}
	if ((Object::cast_to<SpinBox>(p_control) && Object::cast_to<SpinBox>(p_control)->is_editable()) || (Object::cast_to<Slider>(p_control) && Object::cast_to<Slider>(p_control)->is_editable())) {
		result.push_back("set_value");
	}
	if ((Object::cast_to<LineEdit>(p_control) && !Object::cast_to<LineEdit>(p_control)->is_secret()) || Object::cast_to<TextEdit>(p_control)) {
		if (!result.has("read_text")) {
			result.push_back("read_text");
		}
		result.push_back("select_text_range");
	}
	if (Object::cast_to<Tree>(p_control) || Object::cast_to<ItemList>(p_control) || Object::cast_to<TabBar>(p_control) || Object::cast_to<OptionButton>(p_control)) {
		result.push_back("read_items");
	}
	if (Object::cast_to<Tree>(p_control)) {
		result.push_back("select_tree_item");
		result.push_back("expand_tree_item");
	}
	if (Object::cast_to<ItemList>(p_control)) {
		result.push_back("select_item");
	}
	if (Object::cast_to<TabBar>(p_control)) {
		result.push_back("select_tab");
	}
	if (Object::cast_to<ColorPicker>(p_control)) {
		result.push_back("set_color");
	}
	if (Object::cast_to<ScrollContainer>(p_control)) {
		result.push_back("scroll_to");
	}
	return result;
}

Dictionary AIChatEditorRegistry::describe(const String &p_id) const {
	Node *node = resolve_node(p_id);
	return describe_node(node, p_id, targets.has(p_id) ? targets[p_id].page : String());
}

Dictionary AIChatEditorRegistry::describe_node(Node *node, const String &p_id, const String &p_owner_screen) {
	if (!node || !node->is_inside_tree()) {
		return registry_result(false, "target_unavailable");
	}
	if (is_protected(node)) {
		return registry_result(false, "protected_target");
	}
	if (PopupMenu *menu = Object::cast_to<PopupMenu>(node)) {
		Dictionary result = registry_result(true);
		result["id"] = p_id;
		result["display_name"] = control_name(menu);
		result["owner_screen"] = p_owner_screen;
		result["class"] = menu->get_class();
		result["automatic"] = true;
		result["available"] = true;
		result["visible"] = menu->is_visible();
		result["target_instance"] = int64_t(menu->get_instance_id());
		result["window_instance"] = int64_t(menu->get_instance_id());
		Array position;
		position.push_back(menu->get_position().x);
		position.push_back(menu->get_position().y);
		Array size;
		size.push_back(menu->get_size().x);
		size.push_back(menu->get_size().y);
		result["position"] = position;
		result["size"] = size;
		result["focused"] = menu->has_focus();
		result["focusable"] = !menu->get_flag(Window::FLAG_NO_FOCUS);
		result["readonly"] = false;
		if (!menu->is_visible()) {
			result["unavailable_reason"] = "not_visible";
		}
		result["actions"] = AIChatEditorComplexActions::actions(menu);
		result["state"] = AIChatEditorComplexActions::state(menu);
		const Variant status_value = menu->get_meta("_ai_complex_submenu_status", "idle");
		const String submenu_status = status_value.get_type() == Variant::STRING ? String(status_value) : String("idle");
		result["submenu_request_status"] = submenu_status == "queued" || submenu_status == "opened" || submenu_status == "stale" || submenu_status == "not_visible" ? submenu_status : String("idle");
		return result;
	}
	Control *control = Object::cast_to<Control>(node);
	if (!control) {
		return registry_result(false, "target_unavailable");
	}
	Dictionary result = registry_result(true);
	result["id"] = p_id;
	result["display_name"] = control_name(control);
	result["owner_screen"] = p_owner_screen;
	result["automatic"] = true;
	result["available"] = true;
	result["visible"] = control->is_visible_in_tree() && control->get_window()->is_visible();
	result["actions"] = actions(control);
	if (AIChatEditorComplexActions::target(control)) {
		result["state"] = AIChatEditorComplexActions::state(control);
	}
	result["class"] = control->get_class();
	result["target_instance"] = int64_t(control->get_instance_id());
	const Rect2 rect = control->get_global_rect();
	Array position;
	position.push_back(rect.position.x);
	position.push_back(rect.position.y);
	Array size;
	size.push_back(rect.size.x);
	size.push_back(rect.size.y);
	result["position"] = position;
	result["size"] = size;
	result["window_instance"] = int64_t(control->get_window()->get_instance_id());
	result["focused"] = control->has_focus();
	result["focusable"] = control->get_focus_mode() != Control::FOCUS_NONE;
	if (BaseButton *button = Object::cast_to<BaseButton>(control)) {
		result["disabled"] = button->is_disabled();
		result["toggle_mode"] = button->is_toggle_mode();
		result["pressed"] = button->is_pressed();
		if (button->is_disabled()) {
			result["unavailable_reason"] = "disabled";
		}
	}
	const bool readonly = (Object::cast_to<LineEdit>(control) && !Object::cast_to<LineEdit>(control)->is_editable()) || (Object::cast_to<TextEdit>(control) && !Object::cast_to<TextEdit>(control)->is_editable());
	result["readonly"] = readonly;
	if (readonly) {
		result["unavailable_reason"] = "readonly";
	}
	Array entries;
	int total = 0;
	if (Tree *tree = Object::cast_to<Tree>(control)) {
		TreeItem *item = tree->get_root();
		for (; item && total < 4096; total++, item = item->get_next_in_tree()) {
			if (total < 100) {
				Dictionary entry;
				entry["index"] = total;
				entry["text"] = item->get_text(0).left(120);
				entry["collapsed"] = item->is_collapsed();
				entry["selectable"] = item->is_selectable(0);
				entry["selected"] = item->is_selected(0);
				entries.push_back(entry);
			}
		}
		result["total_is_lower_bound"] = item != nullptr;
	} else if (ItemList *items = Object::cast_to<ItemList>(control)) {
		total = items->get_item_count();
		for (int i = 0; i < MIN(total, 100); i++) {
			Dictionary entry;
			entry["index"] = i;
			entry["text"] = items->get_item_text(i).left(120);
			entry["disabled"] = items->is_item_disabled(i);
			entry["selectable"] = items->is_item_selectable(i);
			entry["selected"] = items->is_selected(i);
			entries.push_back(entry);
		}
	} else if (TabBar *tabs = Object::cast_to<TabBar>(control)) {
		total = tabs->get_tab_count();
		for (int i = 0; i < MIN(total, 100); i++) {
			Dictionary entry;
			entry["index"] = i;
			entry["text"] = tabs->get_tab_title(i).left(120);
			entry["disabled"] = tabs->is_tab_disabled(i);
			entry["hidden"] = tabs->is_tab_hidden(i);
			entries.push_back(entry);
		}
	}
	if (Object::cast_to<LineEdit>(control) || Object::cast_to<TextEdit>(control)) {
		const String text = control_value(control);
		result["value_omitted"] = text.utf8().length() > 8192 || JSON::stringify(text).utf8().length() > 8192;
		if (!bool(result["value_omitted"])) {
			result["selection"] = text_selection(control);
			result["value"] = text;
		}
	}
	if (OptionButton *option = Object::cast_to<OptionButton>(control)) {
		total = option->get_item_count();
		for (int i = 0; i < MIN(total, 100); i++) {
			Dictionary entry;
			entry["index"] = i;
			entry["text"] = option->get_item_text(i).left(120);
			entry["disabled"] = option->is_item_disabled(i);
			entries.push_back(entry);
		}
		result["selected"] = option->get_selected();
	}
	bound_items(entries);
	result["items"] = entries;
	result["total_items"] = total;
	result["items_truncated"] = total > entries.size();
	if (Object::cast_to<Range>(control) || Object::cast_to<ColorPicker>(control) || Object::cast_to<ScrollContainer>(control) || Object::cast_to<TabBar>(control)) {
		result["value"] = control_value(control);
	}
	if (Range *range = Object::cast_to<Range>(control)) {
		result["min"] = range->get_min();
		result["max"] = range->get_max();
		result["step"] = range->get_step();
	}
	return result;
}

Array AIChatEditorRegistry::find(const String &p_query, int p_limit) const {
	return find_page(p_query, p_limit, 0)["targets"];
}

Dictionary AIChatEditorRegistry::find_page(const String &p_query, int p_limit, int p_offset) const {
	_refresh();
	Dictionary result;
	Array matches;
	const String query = p_query.strip_edges().to_lower().left(128);
	Vector<String> ids;
	for (const KeyValue<String, Target> &entry : targets) {
		ids.push_back(entry.key);
	}
	ids.sort();
	const int offset = CLAMP(p_offset, 0, 8192);
	const int limit = CLAMP(p_limit, 1, 20);
	int total = 0, page_bytes = 0;
	bool byte_truncated = false;
	for (const String &id : ids) {
		Node *control = resolve_node(id);
		if (!control || (targets.has(p_query) ? id != p_query : !(query.is_empty() || id.contains(query) || control_name(control).to_lower().contains(query) || targets[id].page.to_lower().contains(query)))) {
			continue;
		}
		if (total >= offset && matches.size() < limit && !byte_truncated) {
			const Dictionary description = describe(id);
			const int bytes = JSON::stringify(description).utf8().length();
			if (!matches.is_empty() && page_bytes + bytes > 30 * 1024) {
				byte_truncated = true;
			} else {
				matches.push_back(description);
				page_bytes += bytes;
			}
		}
		total++;
	}
	result["targets"] = matches;
	result["total"] = total;
	result["offset"] = offset;
	result["next_offset"] = offset + matches.size() < total ? offset + matches.size() : -1;
	result["byte_truncated"] = byte_truncated;
	result["has_more"] = offset + matches.size() < total;
	result["scan_truncated"] = truncated;
	result["total_is_lower_bound"] = truncated;
	result["truncated"] = truncated || offset + matches.size() < total;
	result["revision"] = revision;
	result["limit"] = limit;
	return result;
}

Dictionary AIChatEditorRegistry::inspect_tree(int p_limit, int p_offset) const {
	if (p_limit < 1 || p_limit > 100 || p_offset < 0 || p_offset > 50000 || !EditorNode::get_singleton()) {
		return registry_result(false, "invalid_ui_page");
	}
	_refresh();
	EditorNode *editor = EditorNode::get_singleton();
	LocalVector<Node *> queue;
	queue.push_back(editor);
	Array nodes;
	int cursor = 0, total = 0, consumed = 0, omitted = 0, bytes = 0;
	bool scan_truncated = false;
	while (cursor < int(queue.size()) && cursor < 50000) {
		Node *node = queue[cursor++];
		if (_excluded(node)) {
			continue;
		}
		const int index = total++;
		if (index >= p_offset && consumed < p_limit) {
			Dictionary entry;
			const String path = String(editor->get_path_to(node));
			entry["index"] = index;
			entry["instance"] = int64_t(node->get_instance_id());
			entry["parent_instance"] = node == editor || !node->get_parent() ? Variant() : Variant(int64_t(node->get_parent()->get_instance_id()));
			entry["name"] = String(node->get_name()).left(120);
			entry["class"] = node->get_class();
			entry["path"] = path;
			if (const String *id = identities.getptr(node->get_instance_id())) {
				entry["target"] = *id;
			}
			if (Control *control = Object::cast_to<Control>(node)) {
				Array position, size;
				position.push_back(control->get_global_position().x);
				position.push_back(control->get_global_position().y);
				size.push_back(control->get_size().x);
				size.push_back(control->get_size().y);
				entry["position"] = position;
				entry["size"] = size;
				entry["visible"] = control->is_visible_in_tree() && control->get_window()->is_visible();
				entry["window_instance"] = int64_t(control->get_window()->get_instance_id());
			} else if (Window *window = Object::cast_to<Window>(node)) {
				entry["visible"] = window->is_visible();
			}
			const int size = JSON::stringify(entry).utf8().length();
			if (path.length() > 1024 || bytes + size > 14 * 1024) {
				omitted++;
			} else {
				nodes.push_back(entry);
				bytes += size;
			}
			consumed++;
		}
		if (bool(node->get_meta("ai_control_page_only", false))) {
			continue;
		}
		for (int i = 0; i < node->get_child_count(); i++) {
			if (queue.size() >= 50000) {
				scan_truncated = true;
				break;
			}
			queue.push_back(node->get_child(i));
		}
	}
	Dictionary result = registry_result(true);
	result["nodes"] = nodes;
	result["total"] = total;
	result["offset"] = p_offset;
	result["next_offset"] = p_offset + consumed < total ? Variant(p_offset + consumed) : Variant();
	result["total_is_lower_bound"] = scan_truncated || cursor < int(queue.size());
	result["truncated"] = scan_truncated || cursor < int(queue.size()) || omitted > 0;
	result["omitted_items"] = omitted;
	result["protected_subtrees_omitted"] = true;
	result["revision"] = revision;
	return result;
}

Dictionary AIChatEditorRegistry::status() const {
	_refresh();
	Dictionary result;
	result["automatic_targets"] = targets.size();
	result["scanned_nodes"] = scanned_nodes;
	result["queued_nodes"] = queued_nodes;
	result["node_capacity"] = 50000;
	result["target_capacity"] = 8192;
	result["revision"] = revision;
	result["truncated"] = truncated;
	result["target_capacity"] = 8192;
	result["node_capacity"] = 50000;
	return result;
}

bool AIChatEditorRegistry::supported(const String &p_action) {
	return AIChatEditorComplexActions::supports(p_action) || p_action == "read_items" || p_action == "select_text_range" || p_action == "read_text" || p_action == "append_text" || p_action == "replace_text_range" || p_action == "submit_text" || p_action == "undo_text" || p_action == "select_tree_item" || p_action == "expand_tree_item" || p_action == "select_item" || p_action == "select_tab" || p_action == "set_color" || p_action == "scroll_to" || p_action == "open_target" || p_action == "focus" || p_action == "set_text" || p_action == "set_value" || p_action == "select_option" || p_action == "press";
}

Dictionary AIChatEditorRegistry::perform(Node *p_node, const String &p_id, const Dictionary &p_args, bool p_confirmed) {
	Node *target_node = p_node;
	if (!target_node || !target_node->is_inside_tree()) {
		return registry_result(false, "target_unavailable");
	}
	for (Node *node = target_node; node; node = node->get_parent()) {
		if (_excluded(node) || (node != target_node && bool(node->get_meta("ai_control_page_only", false)))) {
			return registry_result(false, "protected_target");
		}
	}
	const String action = p_args.get("action", "");
	if (AIChatEditorComplexActions::supports(action)) {
		return complex_actions.perform(p_node, p_id, p_args, p_confirmed);
	}
	Control *control = Object::cast_to<Control>(p_node);
	if (!control) {
		return registry_result(false, "unsupported_target_action");
	}
	if (!actions(control).has(action)) {
		return registry_result(false, "unsupported_target_action");
	}
	if (action == "open_target" || action == "focus") {
		for (Node *node = control; node; node = node->get_parent()) {
			if (EditorDock *dock = Object::cast_to<EditorDock>(node)) {
				dock->make_visible();
			}
			if (FoldableContainer *foldable = Object::cast_to<FoldableContainer>(node)) {
				foldable->set_folded(false);
			}
			if (TabContainer *tabs = Object::cast_to<TabContainer>(node->get_parent())) {
				if (Control *tab = Object::cast_to<Control>(node)) {
					const int index = tabs->get_tab_idx_from_control(tab);
					if (index >= 0) {
						tabs->set_current_tab(index);
					}
				}
			}
			if (ScrollContainer *scroll = Object::cast_to<ScrollContainer>(node); scroll && scroll != control) {
				scroll->call_deferred("ensure_control_visible", control);
			}
		}
		Window *window = control->get_window();
		if (!window->is_visible()) {
			window->popup_centered();
		}
		if (!control->is_visible_in_tree() || !window->is_visible()) {
			return registry_result(false, "target_not_visible");
		}
		if (action == "focus") {
			if (control->get_focus_mode() == Control::FOCUS_NONE) {
				return registry_result(false, "target_not_focusable");
			}
			control->grab_focus();
		}
		Dictionary result = registry_result(true);
		result["target"] = p_id;
		result["visible"] = control->is_visible_in_tree() && window->is_visible();
		return result;
	}
	if (!control->is_visible_in_tree() || !control->get_window()->is_visible()) {
		return registry_result(false, "target_not_visible");
	}
	if (action == "read_items") {
		int64_t limit = 0;
		int64_t offset = 0;
		if (!registry_integer(p_args.get("limit", 100), 1, 100, limit) || !registry_integer(p_args.get("offset", 0), 0, 4096, offset)) {
			return registry_result(false, "invalid_item_page");
		}
		return item_page(control, limit, offset);
	}
	Variant old_value = control_value(control);
	Variant value = p_args.get("value", Variant());
	if (action == "read_text") {
		const String text = old_value;
		if (text.utf8().length() > 8192) {
			return registry_result(false, "input_value_too_large");
		}
		Dictionary result = registry_result(true);
		result["value"] = text;
		result["selection"] = text_selection(control);
		result["target_instance"] = int64_t(control->get_instance_id());
		return result;
	}
	const bool text_replace = action == "set_text" || action == "append_text" || action == "replace_text_range";
	int from = 0;
	int to = text_replace ? String(old_value).length() : 0;
	if (action == "select_text_range") {
		const String text = old_value;
		int64_t start = 0;
		int64_t end = 0;
		if (!registry_integer(p_args.get("start", Variant()), 0, text.length(), start) || !registry_integer(p_args.get("end", Variant()), start, text.length(), end)) {
			return registry_result(false, "invalid_text_range");
		}
		if (TextEdit *edit = Object::cast_to<TextEdit>(control); edit && edit->get_caret_count() != 1) {
			return registry_result(false, "multiple_carets_unsupported");
		}
		from = start;
		to = end;
		Dictionary state = text_selection(control);
		state["text"] = text;
		old_value = state;
		Dictionary selection;
		selection["start"] = from;
		selection["end"] = to;
		value = selection;
	}
	if (action == "append_text" || action == "replace_text_range") {
		const String text = old_value;
		from = text.length();
		to = from;
		if (action == "replace_text_range") {
			int64_t start = 0;
			int64_t end = 0;
			if (!registry_integer(p_args.get("start", Variant()), 0, text.length(), start) || !registry_integer(p_args.get("end", Variant()), start, text.length(), end)) {
				return registry_result(false, "invalid_text_range");
			}
			from = start;
			to = end;
		}
		if (value.get_type() != Variant::STRING || String(value).utf8().length() > 8192) {
			return registry_result(false, "invalid_input_value");
		}
		value = text.left(from) + String(value) + text.substr(to);
	}
	if (action == "submit_text" || action == "undo_text") {
		value = old_value;
	}
	if (action == "undo_text") {
		const TextUndo *undo = text_undo.getptr(control->get_instance_id());
		TextEdit *text = Object::cast_to<TextEdit>(control);
		if (!undo || undo->after != String(old_value) || (text && (!text->has_undo() || text->get_version() != undo->version))) {
			return registry_result(false, "undo_unavailable");
		}
		value = undo->before;
	}
	int index = -1;
	TreeItem *tree_item = nullptr;
	if (action == "select_item" || action == "select_tab" || action == "select_tree_item" || action == "expand_tree_item") {
		int64_t parsed_index = 0;
		if (!registry_integer(p_args.get("index", Variant()), 0, 4095, parsed_index)) {
			return registry_result(false, "invalid_item_index");
		}
		index = parsed_index;
		if ((Object::cast_to<Tree>(control) && bool(Dictionary(old_value).get("truncated", false))) || (Object::cast_to<ItemList>(control) && Object::cast_to<ItemList>(control)->get_item_count() > 4096) || (Object::cast_to<TabBar>(control) && Object::cast_to<TabBar>(control)->get_tab_count() > 4096)) {
			return registry_result(false, "item_capacity_exceeded");
		}
		if (ItemList *items = Object::cast_to<ItemList>(control); items && (index >= items->get_item_count() || items->is_item_disabled(index) || !items->is_item_selectable(index))) {
			return registry_result(false, "invalid_item_index");
		}
		if (TabBar *tabs = Object::cast_to<TabBar>(control); tabs && (index >= tabs->get_tab_count() || tabs->is_tab_disabled(index) || tabs->is_tab_hidden(index))) {
			return registry_result(false, "invalid_item_index");
		}
		if (Tree *tree = Object::cast_to<Tree>(control)) {
			tree_item = tree_item_at(tree, index);
			if (!tree_item || (action == "select_tree_item" && !tree_item->is_selectable(0))) {
				return registry_result(false, "invalid_item_index");
			}
		}
		value = index;
	}
	Color color;
	Vector2i position;
	if (action == "set_color" || action == "scroll_to") {
		if (value.get_type() != Variant::ARRAY) {
			return registry_result(false, "invalid_input_value");
		}
		const Array components = value;
		if (components.size() != (action == "set_color" ? 4 : 2)) {
			return registry_result(false, "invalid_input_value");
		}
		for (int i = 0; i < components.size(); i++) {
			const Variant component = components[i];
			if ((component.get_type() != Variant::INT && component.get_type() != Variant::FLOAT) || !Math::is_finite(double(component)) || double(component) < 0 || (action == "set_color" ? double(component) > 1 : (double(component) > INT32_MAX || double(component) != Math::floor(double(component))))) {
				return registry_result(false, "invalid_input_value");
			}
		}
		if (action == "set_color") {
			color = Color(components[0], components[1], components[2], components[3]);
		} else {
			position = Vector2i(int(components[0]), int(components[1]));
			ScrollContainer *scroll = Object::cast_to<ScrollContainer>(control);
			if (position.x > MAX(0.0, scroll->get_h_scroll_bar()->get_max() - scroll->get_h_scroll_bar()->get_page()) || position.y > MAX(0.0, scroll->get_v_scroll_bar()->get_max() - scroll->get_v_scroll_bar()->get_page())) {
				return registry_result(false, "input_out_of_range");
			}
		}
	}
	if (JSON::stringify(old_value).utf8().length() > 16384) {
		return registry_result(false, "input_value_too_large");
	}
	if (text_replace && (value.get_type() != Variant::STRING || String(value).utf8().length() > 8192)) {
		return registry_result(false, "invalid_input_value");
	}
	if ((action == "set_value" || action == "select_option") && ((value.get_type() != Variant::INT && value.get_type() != Variant::FLOAT) || !Math::is_finite(double(value)))) {
		return registry_result(false, "invalid_input_value");
	}
	if (action == "select_option") {
		OptionButton *option = Object::cast_to<OptionButton>(control);
		if (double(value) != Math::floor(double(value)) || double(value) < 0 || double(value) >= option->get_item_count() || option->is_item_disabled(int(value))) {
			return registry_result(false, "invalid_option");
		}
	}
	if (action == "set_value") {
		Range *range = Object::cast_to<Range>(control);
		if (double(value) < range->get_min() || double(value) > range->get_max()) {
			return registry_result(false, "input_out_of_range");
		}
	}
	if (text_replace) {
		if (LineEdit *line = Object::cast_to<LineEdit>(control); line && line->get_max_length() > 0 && String(value).length() > line->get_max_length()) {
			return registry_result(false, "input_out_of_range");
		}
	}
	Dictionary result = registry_result(false);
	result["action"] = action;
	result["target"] = p_id;
	result["old_value"] = old_value;
	result["new_value"] = value;
	result["target_instance"] = int64_t(control->get_instance_id());
	if (!p_confirmed) {
		result["confirmation_required"] = true;
		return result;
	}
	if (p_args.get("expected_target_instance", Variant()).get_type() != Variant::INT || int64_t(p_args["expected_target_instance"]) != int64_t(control->get_instance_id()) || !p_args.has("expected_old_value") || p_args["expected_old_value"] != old_value) {
		return registry_result(false, "target_changed_since_confirmation");
	}
	if (action == "select_text_range") {
		if (LineEdit *line = Object::cast_to<LineEdit>(control)) {
			line->deselect();
			line->set_caret_column(to);
			if (from != to) {
				line->select(from, to);
			}
		} else {
			TextEdit *text = Object::cast_to<TextEdit>(control);
			const String value_text = Dictionary(old_value)["text"];
			const int from_line = value_text.left(from).count("\n");
			const int from_column = from - (value_text.left(from).rfind("\n") + 1);
			const int to_line = value_text.left(to).count("\n");
			const int to_column = to - (value_text.left(to).rfind("\n") + 1);
			text->deselect();
			text->set_caret_line(to_line);
			text->set_caret_column(to_column);
			if (from != to) {
				text->select(from_line, from_column, to_line, to_column);
			}
		}
	} else if (action == "select_tree_item") {
		tree_item->select(0);
		control->emit_signal("item_selected");
	} else if (action == "expand_tree_item") {
		tree_item->set_collapsed(false);
	} else if (action == "select_item") {
		ItemList *items = Object::cast_to<ItemList>(control);
		items->deselect_all();
		items->select(index);
		items->emit_signal("item_selected", index);
	} else if (action == "select_tab") {
		Object::cast_to<TabBar>(control)->set_current_tab(index);
	} else if (action == "set_color") {
		Object::cast_to<ColorPicker>(control)->set_pick_color(color);
		control->emit_signal("color_changed", color);
	} else if (action == "scroll_to") {
		ScrollContainer *scroll = Object::cast_to<ScrollContainer>(control);
		scroll->set_h_scroll(position.x);
		scroll->set_v_scroll(position.y);
	} else if (action == "submit_text") {
		control->emit_signal("text_submitted", old_value);
	} else if (action == "undo_text") {
		if (LineEdit *line = Object::cast_to<LineEdit>(control)) {
			line->set_text(text_undo[control->get_instance_id()].before);
			text_undo.erase(control->get_instance_id());
			line->emit_signal("text_changed", line->get_text());
		} else {
			Object::cast_to<TextEdit>(control)->undo();
			text_undo.erase(control->get_instance_id());
		}
	} else if (text_replace) {
		if (text_undo.size() >= 128) {
			text_undo.clear();
		}
		text_undo[control->get_instance_id()] = { String(old_value), String(value), 0 };
		if (LineEdit *line = Object::cast_to<LineEdit>(control)) {
			line->set_text(value);
			line->emit_signal("text_changed", value);
		} else {
			TextEdit *text = Object::cast_to<TextEdit>(control);
			const String old_text = old_value;
			const int from_line = old_text.left(from).count("\n");
			const int from_column = from - (old_text.left(from).rfind("\n") + 1);
			const int to_line = old_text.left(to).count("\n");
			const int to_column = to - (old_text.left(to).rfind("\n") + 1);
			text->begin_complex_operation();
			text->remove_text(from_line, from_column, to_line, to_column);
			text->insert_text(String(value).substr(from, String(value).length() - from - (old_text.length() - to)), from_line, from_column);
			text->end_complex_operation();
			text_undo[control->get_instance_id()].version = text->get_version();
		}
	} else if (action == "set_value") {
		Object::cast_to<Range>(control)->set_value(value);
	} else if (action == "select_option") {
		OptionButton *option = Object::cast_to<OptionButton>(control);
		option->select(value);
		option->emit_signal("item_selected", int(value));
	} else if (action == "press") {
		// Native semantic activation executes the same virtual and signals as UI.
		Object::cast_to<BaseButton>(control)->press();
	}
	result["ok"] = true;
	result.erase("confirmation_required");
	return result;
}

AIChatEditorRegistry::~AIChatEditorRegistry() {
	if (SceneTree *tree = ObjectDB::get_instance<SceneTree>(scene_tree)) {
		tree->disconnect("node_added", callable_mp(this, &AIChatEditorRegistry::_tree_changed));
		tree->disconnect("node_removed", callable_mp(this, &AIChatEditorRegistry::_tree_changed));
		tree->disconnect("node_renamed", callable_mp(this, &AIChatEditorRegistry::_tree_changed));
	}
}
