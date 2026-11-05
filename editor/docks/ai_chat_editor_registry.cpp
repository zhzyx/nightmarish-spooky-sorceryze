/**************************************************************************/
/*  ai_chat_editor_registry.cpp                                              */
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
#include "scene/gui/base_button.h"
#include "scene/gui/button.h"
#include "scene/gui/foldable_container.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/option_button.h"
#include "scene/gui/scroll_container.h"
#include "scene/gui/slider.h"
#include "scene/gui/spin_box.h"
#include "scene/gui/tab_container.h"
#include "scene/gui/text_edit.h"
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

String control_name(Control *p_control) {
	if (Button *button = Object::cast_to<Button>(p_control); button && !button->get_text().is_empty()) {
		return button->get_text().left(120);
	}
	if (EditorDock *dock = Object::cast_to<EditorDock>(p_control)) {
		return dock->get_display_title().left(120);
	}
	return String(p_control->get_name()).left(120);
}

Variant control_value(Control *p_control) {
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
	if (bool(p_node->get_meta("ai_control_exclude", false)) || p_node->get_name() == StringName("AIEditorHighlight")) {
		return true;
	}
	if (LineEdit *line = Object::cast_to<LineEdit>(p_node); line && line->is_secret()) {
		return true;
	}
	EditorInterface *editor = EditorInterface::get_singleton();
	return editor && editor->get_edited_scene_root() == p_node;
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
	int visited = 0;
	while (!stack.is_empty() && visited++ < 50000 && found.size() < 8192) {
		const Entry entry = stack[stack.size() - 1];
		stack.remove_at(stack.size() - 1);
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
		if (dock_page || tab_page || window_page || (control && node->has_meta("ai_control_page"))) {
			page = control;
			if (EditorDock *dock = Object::cast_to<EditorDock>(control)) {
				key = "dock/" + dock->get_effective_layout_key();
			} else {
				key = entry.key + "/" + (entry.page ? String(entry.page->get_path_to(node)) : String(editor->get_path_to(node)));
			}
		}
		if (control && page && (control == page || Object::cast_to<BaseButton>(control) || Object::cast_to<LineEdit>(control) || Object::cast_to<TextEdit>(control) || Object::cast_to<SpinBox>(control) || Object::cast_to<Slider>(control))) {
			const String identity = key + "/" + String(page->get_path_to(control));
			String id = "editor." + identity.sha256_text().left(32);
			if (const String *previous = identities.getptr(control->get_instance_id())) {
				id = *previous;
			}
			if (control->has_meta("ai_control_id")) {
				const String alias = control->get_meta("ai_control_id");
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
				found[id] = { control->get_instance_id(), control_name(control), control_name(page) };
				found_identities[control->get_instance_id()] = id;
			}
		}
		// Chat's authorization/composer controls are host state, not AI inputs.
		if (control && bool(control->get_meta("ai_control_page_only", false))) {
			continue;
		}
		for (int i = node->get_child_count() - 1; i >= 0; i--) {
			stack.push_back({ node->get_child(i), page, key });
		}
	}
	truncated = !stack.is_empty();
	targets = found;
	identities = found_identities;
}

Control *AIChatEditorRegistry::resolve(const String &p_id) const {
	_refresh();
	const Target *target = targets.getptr(p_id);
	Control *control = target ? ObjectDB::get_instance<Control>(target->control) : nullptr;
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
	Array result;
	for (const char *action : { "open_target", "reveal_target", "highlight" }) {
		result.push_back(action);
	}
	if (p_control->get_focus_mode() != Control::FOCUS_NONE) {
		result.push_back("focus");
	}
	if (LineEdit *line = Object::cast_to<LineEdit>(p_control); line && line->is_editable() && !line->is_secret()) {
		result.push_back("set_text");
	} else if (TextEdit *text = Object::cast_to<TextEdit>(p_control); text && text->is_editable()) {
		result.push_back("set_text");
	}
	if (OptionButton *option = Object::cast_to<OptionButton>(p_control); option && !option->is_disabled()) {
		result.push_back("select_option");
	} else if (BaseButton *button = Object::cast_to<BaseButton>(p_control); button && !button->is_disabled()) {
		result.push_back("press");
	}
	if ((Object::cast_to<SpinBox>(p_control) && Object::cast_to<SpinBox>(p_control)->is_editable()) || (Object::cast_to<Slider>(p_control) && Object::cast_to<Slider>(p_control)->is_editable())) {
		result.push_back("set_value");
	}
	return result;
}

Dictionary AIChatEditorRegistry::describe(const String &p_id) const {
	Control *control = resolve(p_id);
	if (!control) {
		return registry_result(false, "target_unavailable");
	}
	const Target &target = targets[p_id];
	Dictionary result = registry_result(true);
	result["id"] = p_id;
	result["display_name"] = control_name(control);
	result["owner_screen"] = target.page;
	result["automatic"] = true;
	result["available"] = true;
	result["visible"] = control->is_visible_in_tree() && control->get_window()->is_visible();
	result["actions"] = actions(control);
	return result;
}

Array AIChatEditorRegistry::find(const String &p_query, int p_limit) const {
	_refresh();
	Array result;
	const String query = p_query.strip_edges().to_lower().left(128);
	if (targets.has(p_query)) {
		const Dictionary description = describe(p_query);
		if (bool(description.get("ok", false))) {
			result.push_back(description);
		}
		return result;
	}
	// Sort IDs to make bounded results deterministic across map rehashes.
	Vector<String> ids;
	for (const KeyValue<String, Target> &entry : targets) {
		ids.push_back(entry.key);
	}
	ids.sort();
	for (const String &id : ids) {
		const Target &entry = targets[id];
		Control *control = resolve(id);
		if (control && (query.is_empty() || id.contains(query) || control_name(control).to_lower().contains(query) || entry.page.to_lower().contains(query))) {
			const Dictionary description = describe(id);
			if (bool(description.get("ok", false))) {
				result.push_back(description);
				if (result.size() >= CLAMP(p_limit, 1, 20)) {
					break;
				}
			}
		}
	}
	return result;
}

Dictionary AIChatEditorRegistry::status() const {
	_refresh();
	Dictionary result;
	result["automatic_targets"] = targets.size();
	result["revision"] = revision;
	result["truncated"] = truncated;
	return result;
}

bool AIChatEditorRegistry::supported(const String &p_action) {
	return p_action == "open_target" || p_action == "focus" || p_action == "set_text" || p_action == "set_value" || p_action == "select_option" || p_action == "press";
}

Dictionary AIChatEditorRegistry::perform(Control *p_control, const String &p_id, const Dictionary &p_args, bool p_confirmed) {
	Control *control = p_control;
	if (!control || !control->is_inside_tree()) {
		return registry_result(false, "target_unavailable");
	}
	for (Node *node = control; node; node = node->get_parent()) {
		if (_excluded(node) || (node != control && bool(node->get_meta("ai_control_page_only", false)))) {
			return registry_result(false, "protected_target");
		}
	}
	const String action = p_args.get("action", "");
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
			if (ScrollContainer *scroll = Object::cast_to<ScrollContainer>(node)) {
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
	const Variant old_value = control_value(control);
	const Variant value = p_args.get("value", Variant());
	if (JSON::stringify(old_value).utf8().length() > 16384) {
		return registry_result(false, "input_value_too_large");
	}
	if (action == "set_text" && (value.get_type() != Variant::STRING || String(value).utf8().length() > 8192)) {
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
	if (action == "set_text") {
		if (LineEdit *line = Object::cast_to<LineEdit>(control)) {
			line->set_text(value);
			line->emit_signal("text_changed", value);
		} else {
			Object::cast_to<TextEdit>(control)->set_text(value);
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
