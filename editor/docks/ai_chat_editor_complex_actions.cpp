/**************************************************************************/
/*  ai_chat_editor_complex_actions.cpp                                    */
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

#include "ai_chat_editor_complex_actions.h"

#include "core/input/input_event.h"
#include "core/input/shortcut.h"
#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "editor/docks/ai_chat_editor_registry.h"
#include "editor/editor_data.h"
#include "editor/editor_interface.h"
#include "editor/editor_node.h"
#include "editor/editor_undo_redo_manager.h"
#include "editor/scene/curve_editor_plugin.h"
#include "editor/scene/gradient_editor_plugin.h"
#include "editor/scene/scene_tree_editor.h"
#include "scene/gui/graph_edit.h"
#include "scene/gui/graph_node.h"
#include "scene/gui/item_list.h"
#include "scene/gui/menu_bar.h"
#include "scene/gui/popup_menu.h"
#include "scene/gui/rich_text_label.h"
#include "scene/gui/tree.h"
#include "scene/main/scene_tree.h"

namespace {
Dictionary result(bool p_ok, const String &p_error = String()) {
	Dictionary d;
	d["ok"] = p_ok;
	if (!p_error.is_empty()) {
		d["error"] = p_error;
	}
	return d;
}
bool integer(const Variant &p_value, int p_min, int p_max, int &r_value) {
	if (p_value.get_type() != Variant::INT && p_value.get_type() != Variant::FLOAT) {
		return false;
	}
	double v = p_value;
	if (!Math::is_finite(v) || v < p_min || v > p_max || v != Math::floor(v)) {
		return false;
	}
	r_value = int(v);
	return true;
}
bool number(const Variant &p_value, double p_min, double p_max) {
	return (p_value.get_type() == Variant::INT || p_value.get_type() == Variant::FLOAT) && Math::is_finite(double(p_value)) && double(p_value) >= p_min && double(p_value) <= p_max;
}
// Scene writes use their dedicated owner/history-aware route and fresh human
// confirmation. A generic editable Tree cell must not create a second route.
bool scene_tree_context(Tree *p_tree) {
	if (!p_tree) {
		return false;
	}
	for (Node *ancestor = p_tree; ancestor; ancestor = ancestor->get_parent()) {
		if (Object::cast_to<SceneTreeEditor>(ancestor)) {
			return true;
		}
	}
	// Keep this boundary if a plugin reparents the real widget: the native
	// scene editor still owns its business callback even outside its subtree.
	List<Object::Connection> connections;
	p_tree->get_signal_connection_list(SNAME("item_edited"), &connections);
	for (const Object::Connection &connection : connections) {
		if (Object::cast_to<SceneTreeEditor>(ObjectDB::get_instance(connection.callable.get_object_id()))) {
			return true;
		}
	}
	return false;
}

bool graph_name(const Variant &p_value) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String name = p_value;
	return !name.is_empty() && name.length() <= 128 && name != "." && name != ".." && !name.contains_char(0) && name.validate_node_name() == name;
}
Array vec(Vector2 p_v) {
	Array a;
	a.push_back(p_v.x);
	a.push_back(p_v.y);
	return a;
}
Array rgba(Color p_color) {
	Array a;
	a.push_back(p_color.r);
	a.push_back(p_color.g);
	a.push_back(p_color.b);
	a.push_back(p_color.a);
	return a;
}
Ref<Resource> resource(Node *p_node) {
	if (CurveEdit *edit = Object::cast_to<CurveEdit>(p_node)) {
		return edit->get_curve();
	}
	if (GradientEdit *edit = Object::cast_to<GradientEdit>(p_node)) {
		return edit->get_gradient();
	}
	return Ref<Resource>();
}
bool native_resource(const Ref<Resource> &p_resource) {
	return p_resource.is_valid() && p_resource->get_script().get_type() == Variant::NIL && !p_resource->is_extension_placeholder() && !ClassDB::is_gdextension(p_resource->get_class_name());
}
void apply_curve_data(Ref<Curve> p_curve, Array p_data) {
	if (native_resource(p_curve)) {
		p_curve->set_data(p_data);
	}
}
void apply_gradient_offset(Ref<Gradient> p_gradient, int p_index, float p_offset) {
	if (native_resource(p_gradient) && p_index >= 0 && p_index < p_gradient->get_point_count()) {
		p_gradient->set_offset(p_index, p_offset);
	}
}

// UndoRedo skips callables with no ObjectID. This private, unregistered native
// receiver is strongly retained by each history operation and has no script API.
class ComplexHistoryFence : public RefCounted {
public:
	uint64_t epoch = 0;
	void changed() { epoch++; }
	void observe(UndoRedo *p_history) {
		const Callable callback = callable_mp(this, &ComplexHistoryFence::changed);
		if (p_history && !p_history->is_connected("version_changed", callback)) {
			p_history->connect("version_changed", callback);
		}
	}
};

ComplexHistoryFence *menu_history_fence(EditorUndoRedoManager *p_manager) {
	// Ownership stays with the native editor lifetime, never a function-static Ref.
	static ObjectID known_fence;
	Variant stored = p_manager->has_meta("_ai_complex_menu_history_fence") ? p_manager->get_meta("_ai_complex_menu_history_fence") : Variant();
	Object *object = stored.get_type() == Variant::OBJECT ? stored.get_validated_object() : nullptr;
	if (!object || object->get_instance_id() != known_fence) {
		Ref<ComplexHistoryFence> created;
		created.instantiate();
		known_fence = created->get_instance_id();
		p_manager->connect("history_changed", callable_mp(created.ptr(), &ComplexHistoryFence::changed));
		p_manager->connect("version_changed", callable_mp(created.ptr(), &ComplexHistoryFence::changed));
		p_manager->set_meta("_ai_complex_menu_history_fence", created);
		object = created.ptr();
	}
	return static_cast<ComplexHistoryFence *>(object);
}

class ComplexResourceAction : public RefCounted {
public:
	void curve_data(Ref<Curve> p_curve, Array p_data) { apply_curve_data(p_curve, p_data); }
	void gradient_offset(Ref<Gradient> p_gradient, int p_index, float p_offset) { apply_gradient_offset(p_gradient, p_index, p_offset); }
};

class ComplexSubmenuRequest : public Node {
public:
	ObjectID parent;
	ObjectID child;
	int index = -1;
	Dictionary expected;

	PopupMenu *resolve() const {
		PopupMenu *menu = ObjectDB::get_instance<PopupMenu>(parent);
		PopupMenu *submenu = ObjectDB::get_instance<PopupMenu>(child);
		if (!menu || !menu->is_inside_tree()) {
			return nullptr;
		}
		if (!submenu || index < 0 || index >= menu->get_item_count() || menu->get_item_submenu_node(index) != submenu || AIChatEditorRegistry::is_protected(menu) || AIChatEditorRegistry::is_protected(submenu) || bool(submenu->get_meta("ai_control_page_only", false)) || AIChatEditorComplexActions::state(menu) != expected) {
			menu->set_meta("_ai_complex_submenu_status", "stale");
			return nullptr;
		}
		return menu;
	}
	void prepare() {
		PopupMenu *menu = resolve();
		if (!menu) {
			queue_free();
			return;
		}
		const ObjectID self_id = get_instance_id();
		if (!menu->is_visible()) {
			menu->popup();
			if (ObjectDB::get_instance<Node>(self_id) != this) {
				return;
			}
		}
		if (!resolve()) {
			queue_free();
			return;
		}
		// Host confirmation changes native focus and can queue Popup::hide.
		// Let those native events settle before entering the submenu state machine.
		get_tree()->create_timer(0.05, true)->connect("timeout", callable_mp(this, &ComplexSubmenuRequest::open), Object::CONNECT_ONE_SHOT);
	}
	void open() {
		PopupMenu *menu = resolve();
		if (!menu) {
			queue_free();
			return;
		}
		const ObjectID self_id = get_instance_id();
		const ObjectID parent_id = parent;
		const bool opened = menu->open_submenu(index);
		if (ObjectDB::get_instance<Node>(self_id) != this) {
			return;
		}
		menu = ObjectDB::get_instance<PopupMenu>(parent_id);
		if (menu) {
			menu->set_meta("_ai_complex_submenu_status", opened ? "opened" : "not_visible");
		}
		queue_free();
	}
};

TreeItem *tree_item(Tree *p_tree, int p_index) {
	TreeItem *item = p_tree->get_root();
	for (int i = 0; item && i < p_index; i++) {
		item = item->get_next_in_tree();
	}
	return item;
}
// Metadata never crosses the wire. Object identities are encoded without invoking
// Object::to_string() or a script callback. Oversized compound metadata is refused.
String metadata_identity(const Variant &p_value, int p_depth, int &r_budget) {
	if (p_depth > 8 || --r_budget < 0) {
		return String();
	}
	String encoded = String::num_int64(p_value.get_type()) + ":";
	if (p_value.get_type() == Variant::OBJECT) {
		Object *object = p_value;
		return encoded + (object ? String::num_uint64(uint64_t(object->get_instance_id())) : String("null"));
	}
	if (p_value.get_type() == Variant::ARRAY || p_value.get_type() == Variant::DICTIONARY) {
		Array values;
		if (p_value.get_type() == Variant::ARRAY) {
			values = p_value;
		} else {
			Dictionary dictionary = p_value;
			if (dictionary.size() > 256) {
				return String();
			}
			for (const Variant &key : dictionary.keys()) {
				values.push_back(key);
				values.push_back(dictionary[key]);
			}
		}
		if (values.size() > 512) {
			return String();
		}
		for (const Variant &value : values) {
			String child = metadata_identity(value, p_depth + 1, r_budget);
			if (child.is_empty()) {
				return String();
			}
			encoded += child.sha256_text();
		}
		return encoded;
	}
	return encoded + JSON::stringify(p_value);
}

// Full bounded state is hashed for confirmation; only requested pages are exposed.
Array entries(Node *p_node) {
	Array a;
	if (MenuBar *bar = Object::cast_to<MenuBar>(p_node)) {
		for (int i = 0; i < MIN(bar->get_menu_count(), 4096); i++) {
			Dictionary d;
			d["index"] = i;
			d["title"] = bar->get_menu_title(i).left(120);
			d["title_hash"] = bar->get_menu_title(i).sha256_text();
			d["disabled"] = bar->is_menu_disabled(i);
			d["hidden"] = bar->is_menu_hidden(i);
			PopupMenu *popup = bar->get_menu_popup(i);
			d["popup_instance"] = popup ? int64_t(popup->get_instance_id()) : 0;
			d["popup_visible"] = popup && popup->is_visible();
			a.push_back(d);
		}
		return a;
	}
	if (RichTextLabel *label = Object::cast_to<RichTextLabel>(p_node)) {
		Array metadata = label->get_semantic_meta_links();
		for (int i = 0; i < MIN(metadata.size(), 4096); i++) {
			Dictionary d;
			d["index"] = i;
			int budget = 512;
			String identity = metadata_identity(metadata[i], 0, budget);
			d["metadata_hash"] = identity.sha256_text();
			d["metadata_unavailable"] = identity.is_empty();
			if (metadata[i].get_type() == Variant::STRING) {
				d["text"] = String(metadata[i]).left(256);
			}
			a.push_back(d);
		}
		return a;
	}
	if (PopupMenu *menu = Object::cast_to<PopupMenu>(p_node)) {
		for (int i = 0; i < MIN(menu->get_item_count(), 4096); i++) {
			Dictionary d;
			d["index"] = i;
			d["id"] = menu->get_item_id(i);
			d["text"] = menu->get_item_text(i).left(120);
			d["text_hash"] = menu->get_item_text(i).sha256_text();
			d["disabled"] = menu->is_item_disabled(i);
			d["separator"] = menu->is_item_separator(i);
			d["checked"] = menu->is_item_checked(i);
			d["checkable"] = menu->is_item_checkable(i);
			d["radio"] = menu->is_item_radio_checkable(i);
			d["accelerator"] = int64_t(menu->get_item_accelerator(i));
			d["shortcut_disabled"] = menu->is_item_shortcut_disabled(i);
			d["state"] = menu->get_item_state(i);
			d["max_states"] = menu->get_item_max_states(i);
			int budget = 512;
			String metadata = metadata_identity(menu->get_item_metadata(i), 0, budget);
			d["metadata_hash"] = metadata.sha256_text();
			d["metadata_unavailable"] = metadata.is_empty();
			Ref<Shortcut> shortcut = menu->get_item_shortcut(i);
			if (shortcut.is_valid()) {
				String events;
				for (const Variant &input_event : shortcut->get_events()) {
					Ref<InputEvent> event = input_event;
					events += event.is_valid() ? event->as_text() : String("null");
				}
				d["shortcut_hash"] = (String::num_uint64(uint64_t(shortcut->get_instance_id())) + events).sha256_text();
			}
			d["submenu"] = menu->get_item_submenu(i).left(120);
			d["submenu_hash"] = menu->get_item_submenu(i).sha256_text();
			PopupMenu *submenu = menu->get_item_submenu_node(i);
			d["submenu_instance"] = submenu ? int64_t(submenu->get_instance_id()) : 0;
			a.push_back(d);
		}
	} else if (CurveEdit *edit = Object::cast_to<CurveEdit>(p_node); edit && edit->get_curve().is_valid()) {
		Ref<Curve> curve = edit->get_curve();
		for (int i = 0; i < MIN(curve->get_point_count(), 4096); i++) {
			Dictionary d;
			d["index"] = i;
			d["position"] = vec(curve->get_point_position(i));
			d["left_tangent"] = curve->get_point_left_tangent(i);
			d["right_tangent"] = curve->get_point_right_tangent(i);
			d["left_mode"] = curve->get_point_left_mode(i);
			d["right_mode"] = curve->get_point_right_mode(i);
			a.push_back(d);
		}
	} else if (GradientEdit *gradient_edit = Object::cast_to<GradientEdit>(p_node); gradient_edit && gradient_edit->get_gradient().is_valid()) {
		Ref<Gradient> gradient = gradient_edit->get_gradient();
		for (int i = 0; i < MIN(gradient->get_point_count(), 4096); i++) {
			Dictionary d;
			d["index"] = i;
			d["offset"] = gradient->get_offset(i);
			d["color"] = rgba(gradient->get_color(i));
			a.push_back(d);
		}
	} else if (GraphEdit *graph = Object::cast_to<GraphEdit>(p_node)) {
		for (int i = 0; i < graph->get_child_count() && a.size() < 4096; i++) {
			GraphNode *node = Object::cast_to<GraphNode>(graph->get_child(i));
			if (!node || AIChatEditorRegistry::is_protected(node) || bool(node->get_meta("ai_control_page_only", false))) {
				continue;
			}
			Dictionary d;
			d["name"] = String(node->get_name());
			d["instance"] = int64_t(node->get_instance_id());
			d["position"] = vec(node->get_position_offset());
			d["selected"] = node->is_selected();
			d["draggable"] = node->is_draggable();
			d["inputs"] = node->get_input_port_count();
			d["outputs"] = node->get_output_port_count();
			Array ports;
			for (int direction = 0; direction < 2; direction++) {
				int count = direction ? node->get_output_port_count() : node->get_input_port_count();
				for (int port = 0; port < MIN(count, 100); port++) {
					Dictionary p;
					p["direction"] = direction ? "output" : "input";
					p["index"] = port;
					p["type"] = direction ? node->get_output_port_type(port) : node->get_input_port_type(port);
					p["slot"] = direction ? node->get_output_port_slot(port) : node->get_input_port_slot(port);
					ports.push_back(p);
				}
			}
			d["ports"] = ports;
			d["ports_truncated"] = node->get_input_port_count() > 100 || node->get_output_port_count() > 100;
			a.push_back(d);
		}
	} else if (Tree *tree = Object::cast_to<Tree>(p_node)) {
		TreeItem *item = tree->get_root();
		for (int i = 0; item && i < 4096; i++, item = item->get_next_in_tree()) {
			Dictionary d;
			d["instance"] = int64_t(item->get_instance_id());
			d["text_hash"] = item->get_text(0).sha256_text();
			int budget = 512;
			String metadata = metadata_identity(item->get_metadata(0), 0, budget);
			d["metadata_hash"] = metadata.sha256_text();
			d["metadata_unavailable"] = metadata.is_empty();
			d["selected"] = item->is_selected(0);
			d["selectable"] = item->is_selectable(0);
			d["collapsed"] = item->is_collapsed();
			Array cells;
			for (int col = 0; col < MIN(tree->get_columns(), 64); col++) {
				Dictionary cell;
				cell["column"] = col;
				cell["mode"] = item->get_cell_mode(col);
				cell["editable"] = item->is_editable(col);
				cell["text_hash"] = item->get_text(col).sha256_text();
				cell["text"] = item->get_text(col).left(256);
				double minimum, maximum, step;
				item->get_range_config(col, minimum, maximum, step);
				cell["minimum"] = minimum;
				cell["maximum"] = maximum;
				cell["step"] = step;
				cell["checked"] = item->is_checked(col);
				cell["range"] = item->get_range(col);
				int cell_budget = 512;
				String cell_metadata = metadata_identity(item->get_metadata(col), 0, cell_budget);
				cell["metadata_hash"] = cell_metadata.sha256_text();
				cell["metadata_unavailable"] = cell_metadata.is_empty();
				cells.push_back(cell);
			}
			d["cells"] = cells;
			d["columns_truncated"] = tree->get_columns() > 64;
			a.push_back(d);
		}
	} else if (ItemList *items = Object::cast_to<ItemList>(p_node)) {
		for (int i = 0; i < MIN(items->get_item_count(), 4096); i++) {
			Dictionary d;
			d["text_hash"] = items->get_item_text(i).sha256_text();
			int budget = 512;
			String metadata = metadata_identity(items->get_item_metadata(i), 0, budget);
			d["metadata_hash"] = metadata.sha256_text();
			d["metadata_unavailable"] = metadata.is_empty();
			d["disabled"] = items->is_item_disabled(i);
			d["selectable"] = items->is_item_selectable(i);
			d["selected"] = items->is_selected(i);
			a.push_back(d);
		}
	}
	return a;
}
Array connections(GraphEdit *p_graph) {
	Array a;
	for (const Ref<GraphEdit::Connection> &c : p_graph->get_connections()) {
		if (a.size() >= 4096) {
			break;
		}
		Node *from = p_graph->get_node_or_null(NodePath(c->from_node));
		Node *to = p_graph->get_node_or_null(NodePath(c->to_node));
		if (!Object::cast_to<GraphNode>(from) || !Object::cast_to<GraphNode>(to) || from->get_parent() != p_graph || to->get_parent() != p_graph || AIChatEditorRegistry::is_protected(from) || AIChatEditorRegistry::is_protected(to) || bool(from->get_meta("ai_control_page_only", false)) || bool(to->get_meta("ai_control_page_only", false))) {
			continue;
		}
		Dictionary d;
		d["from"] = String(c->from_node);
		d["from_port"] = c->from_port;
		d["to"] = String(c->to_node);
		d["to_port"] = c->to_port;
		a.push_back(d);
	}
	return a;
}
int count(Node *p_node, const Array &p_entries) {
	if (MenuBar *bar = Object::cast_to<MenuBar>(p_node)) {
		return bar->get_menu_count();
	}
	if (RichTextLabel *label = Object::cast_to<RichTextLabel>(p_node)) {
		return label->get_semantic_meta_links().size();
	}
	if (PopupMenu *menu = Object::cast_to<PopupMenu>(p_node)) {
		return menu->get_item_count();
	}
	if (Ref<Curve> curve = resource(p_node); curve.is_valid()) {
		return curve->get_point_count();
	}
	if (Ref<Gradient> gradient = resource(p_node); gradient.is_valid()) {
		return gradient->get_point_count();
	}
	if (ItemList *items = Object::cast_to<ItemList>(p_node)) {
		return items->get_item_count();
	}
	if (Tree *tree = Object::cast_to<Tree>(p_node)) {
		return p_entries.size() == 4096 && tree_item(tree, 4096) ? 4097 : p_entries.size();
	}
	return p_entries.size();
}
Dictionary page(const Array &p_entries, int p_total, int p_limit, int p_offset) {
	Dictionary d = result(true);
	Array a;
	for (int i = p_offset; i < MIN(p_entries.size(), p_offset + p_limit); i++) {
		a.push_back(p_entries[i]);
		if (JSON::stringify(a).utf8().length() > 8192) {
			a.resize(a.size() - 1);
			break;
		}
	}
	d["items"] = a;
	d["total"] = p_total;
	d["offset"] = p_offset;
	d["limit"] = p_limit;
	d["next_offset"] = p_offset + a.size() < MIN(4096, p_total) ? p_offset + a.size() : -1;
	d["capacity"] = 4096;
	d["truncated"] = p_total > 4096 || p_offset + a.size() < p_total;
	d["total_is_lower_bound"] = p_total > 4096;
	return d;
}
} // namespace

bool AIChatEditorComplexActions::target(Node *p_node) {
	return Object::cast_to<Tree>(p_node) || Object::cast_to<MenuBar>(p_node) || Object::cast_to<RichTextLabel>(p_node) || Object::cast_to<PopupMenu>(p_node) || Object::cast_to<CurveEdit>(p_node) || Object::cast_to<GradientEdit>(p_node) || Object::cast_to<GraphEdit>(p_node);
}

bool AIChatEditorComplexActions::supports(const String &p_action) {
	return p_action == "read_menubar_menus" || p_action == "open_menubar_menu" || p_action == "read_tree_cells" || p_action == "edit_tree_cell" || p_action == "read_richtext_links" || p_action == "activate_richtext_link" || p_action == "read_menu_items" || p_action == "activate_menu_item" || p_action == "open_menu_submenu" || p_action == "read_curve" || p_action == "curve_preset" || p_action == "curve_add_point" || p_action == "curve_remove_point" || p_action == "curve_set_point" || p_action == "curve_set_tangents" || p_action == "curve_set_tangent_modes" || p_action == "read_gradient" || p_action == "gradient_add_point" || p_action == "gradient_remove_point" || p_action == "gradient_set_color" || p_action == "gradient_reverse" || p_action == "gradient_set_offset" || p_action == "undo_resource_edit" || p_action == "redo_resource_edit" || p_action == "read_graph_nodes" || p_action == "read_graph_ports" || p_action == "read_graph_connections" || p_action == "graph_connect" || p_action == "graph_disconnect" || p_action == "graph_move_node" || p_action == "activate_tree_item" || p_action == "tree_context_menu" || p_action == "activate_item" || p_action == "item_context_menu";
}

Array AIChatEditorComplexActions::actions(Node *p_node) {
	Array a;
	Ref<Resource> bound = resource(p_node);
	if (bound.is_valid() && !native_resource(bound)) {
		return a;
	}
	if (Object::cast_to<MenuBar>(p_node)) {
		a.push_back("read_menubar_menus");
		a.push_back("open_menubar_menu");
	} else if (Object::cast_to<RichTextLabel>(p_node)) {
		a.push_back("read_richtext_links");
		a.push_back("activate_richtext_link");
	} else if (Object::cast_to<PopupMenu>(p_node)) {
		a.push_back("read_menu_items");
		a.push_back("activate_menu_item");
		a.push_back("open_menu_submenu");
	} else if (Object::cast_to<CurveEdit>(p_node)) {
		for (const char *s : { "read_curve", "curve_preset", "curve_add_point", "curve_remove_point", "curve_set_point", "curve_set_tangents", "curve_set_tangent_modes", "undo_resource_edit", "redo_resource_edit" }) {
			a.push_back(s);
		}
	} else if (Object::cast_to<GradientEdit>(p_node)) {
		for (const char *s : { "read_gradient", "gradient_add_point", "gradient_remove_point", "gradient_set_color", "gradient_reverse", "gradient_set_offset", "undo_resource_edit", "redo_resource_edit" }) {
			a.push_back(s);
		}
	} else if (Object::cast_to<GraphEdit>(p_node)) {
		for (const char *s : { "read_graph_nodes", "read_graph_ports", "read_graph_connections", "graph_connect", "graph_disconnect", "graph_move_node" }) {
			a.push_back(s);
		}
	} else if (Object::cast_to<Tree>(p_node)) {
		a.push_back("read_tree_cells");
		if (!scene_tree_context(Object::cast_to<Tree>(p_node))) {
			a.push_back("edit_tree_cell");
		}
		a.push_back("activate_tree_item");
		a.push_back("tree_context_menu");
	} else if (Object::cast_to<ItemList>(p_node)) {
		a.push_back("activate_item");
		a.push_back("item_context_menu");
	}
	return a;
}

Dictionary AIChatEditorComplexActions::state(Node *p_node) {
	Dictionary d;
	Ref<Resource> bound = resource(p_node);
	if (bound.is_valid() && !native_resource(bound)) {
		d["unavailable_reason"] = "script_or_extension_resource_not_supported";
		return d;
	}
	const Array all = entries(p_node);
	d["content_hash"] = JSON::stringify(all).sha256_text();
	d["count"] = count(p_node, all);
	d["capacity_exceeded"] = int(d["count"]) > 4096;
	Ref<Resource> res = resource(p_node);
	if (res.is_valid()) {
		d["resource_instance"] = String::num_uint64(uint64_t(res->get_instance_id()));
		if (Ref<Curve> curve = res; curve.is_valid()) {
			d["min_domain"] = curve->get_min_domain();
			d["max_domain"] = curve->get_max_domain();
			d["min_value"] = curve->get_min_value();
			d["max_value"] = curve->get_max_value();
		}
		if (Ref<Gradient> gradient = res; gradient.is_valid()) {
			d["interpolation_mode"] = gradient->get_interpolation_mode();
			d["interpolation_color_space"] = gradient->get_interpolation_color_space();
		}
	} else if (Object::cast_to<PopupMenu>(p_node) && EditorNode::get_singleton()) {
		Node *scene = EditorNode::get_singleton()->get_edited_scene();
		d["scene_instance"] = scene ? String::num_uint64(uint64_t(scene->get_instance_id())) : String();
		Array selection;
		for (Node *node : EditorInterface::get_singleton()->get_selection()->get_full_selected_node_list()) {
			selection.push_back(String::num_uint64(uint64_t(node->get_instance_id())));
		}
		d["selection_hash"] = JSON::stringify(selection).sha256_text();
		EditorUndoRedoManager *manager = EditorUndoRedoManager::get_singleton();
		ComplexHistoryFence *fence = menu_history_fence(manager);
		const int scene_history = EditorNode::get_editor_data().get_current_edited_scene_history_id();
		const int history_id = manager->get_current_action_history_id();
		Dictionary histories;
		for (int id : { int(EditorUndoRedoManager::GLOBAL_HISTORY), int(EditorUndoRedoManager::REMOTE_HISTORY), scene_history }) {
			UndoRedo *native = manager->has_history(id) ? manager->get_history_undo_redo(id) : nullptr;
			fence->observe(native);
			histories[String::num_int64(id)] = native ? String::num_uint64(native->get_version()) : String("absent");
		}
		UndoRedo *history = manager->has_history(history_id) ? manager->get_history_undo_redo(history_id) : nullptr;
		d["history_id"] = history_id;
		d["history_version"] = history ? String::num_uint64(history->get_version()) : String();
		d["scene_history_id"] = scene_history;
		d["history_versions"] = histories;
		d["history_fence_instance"] = String::num_uint64(uint64_t(fence->get_instance_id()));
		d["history_epoch"] = String::num_uint64(fence->epoch);
	} else if (GraphEdit *graph = Object::cast_to<GraphEdit>(p_node)) {
		d["connections_hash"] = JSON::stringify(connections(graph)).sha256_text();
		d["connection_count"] = graph->get_connections().size();
		d["capacity_exceeded"] = graph->get_child_count() > 4096 || graph->get_connections().size() > 4096;
	}
	return d;
}

Dictionary AIChatEditorComplexActions::perform(Node *p_node, const String &p_id, const Dictionary &p_args, bool p_confirmed) {
	if (!p_node || !p_node->is_inside_tree()) {
		return result(false, "target_unavailable");
	}
	if (AIChatEditorRegistry::is_protected(p_node)) {
		return result(false, "protected_target");
	}
	Ref<Resource> bound = resource(p_node);
	if (bound.is_valid() && !native_resource(bound)) {
		return result(false, "script_or_extension_resource_not_supported");
	}
	const String action = p_args.get("action", "");
	const bool resource_history = action == "undo_resource_edit" || action == "redo_resource_edit";
	if (action == "edit_tree_cell" && scene_tree_context(Object::cast_to<Tree>(p_node))) {
		Dictionary denied = result(false, "scene_action_required");
		denied["required_action"] = "scene_rename_node";
		return denied;
	}

	if (!actions(p_node).has(action)) {
		return result(false, "unsupported_target_action");
	}
	PopupMenu *menu = Object::cast_to<PopupMenu>(p_node);
	Control *control = Object::cast_to<Control>(p_node);
	if ((menu && !menu->is_visible() && !p_confirmed) || (control && (!control->is_visible_in_tree() || !control->get_window()->is_visible()))) {
		return result(false, "target_not_visible");
	}
	const Dictionary before = state(p_node);
	if (action == "open_menubar_menu" || action == "edit_tree_cell" || action == "activate_richtext_link") {
		if (bool(before.get("capacity_exceeded", false))) {
			return result(false, "item_capacity_exceeded");
		}
		int selected = -1;
		if (!integer(p_args.get("index", Variant()), 0, int(before["count"]) - 1, selected)) {
			return result(false, "invalid_item_index");
		}
		MenuBar *bar = Object::cast_to<MenuBar>(p_node);
		Tree *tree = Object::cast_to<Tree>(p_node);
		TreeItem *cell_item = tree ? tree_item(tree, selected) : nullptr;
		int column = 0;
		Variant value = p_args.get("value", Variant());
		if (bar && (bar->is_menu_disabled(selected) || bar->is_menu_hidden(selected) || !bar->get_menu_popup(selected) || AIChatEditorRegistry::is_protected(bar->get_menu_popup(selected)) || bool(bar->get_menu_popup(selected)->get_meta("ai_control_page_only", false)))) {
			return result(false, "menu_unavailable");
		}
		if (tree) {
			if (!cell_item || tree->get_columns() > 64 || !integer(p_args.get("column", Variant()), 0, tree->get_columns() - 1, column) || !cell_item->is_editable(column)) {
				return result(false, "tree_cell_not_editable");
			}
			int metadata_budget = 512;
			if (metadata_identity(cell_item->get_metadata(column), 0, metadata_budget).is_empty()) {
				return result(false, "item_metadata_capacity_exceeded");
			}
			const TreeItem::TreeCellMode mode = cell_item->get_cell_mode(column);
			if ((mode == TreeItem::CELL_MODE_CHECK && value.get_type() != Variant::BOOL) || (mode == TreeItem::CELL_MODE_STRING && (value.get_type() != Variant::STRING || String(value).length() > 8192)) || (mode != TreeItem::CELL_MODE_CHECK && mode != TreeItem::CELL_MODE_STRING && mode != TreeItem::CELL_MODE_RANGE)) {
				return result(false, "invalid_tree_cell_value");
			}
			if (mode == TreeItem::CELL_MODE_RANGE) {
				double min, max, step;
				cell_item->get_range_config(column, min, max, step);
				if (!number(value, min, max)) {
					return result(false, "invalid_tree_cell_value");
				}
			}
		}
		if (RichTextLabel *label = Object::cast_to<RichTextLabel>(p_node)) {
			const Array metadata = label->get_semantic_meta_links();
			int budget = 512;
			if (selected >= metadata.size() || metadata_identity(metadata[selected], 0, budget).is_empty()) {
				return result(false, "link_metadata_unavailable");
			}
		}
		Dictionary d = result(false);
		d["target"] = p_id;
		d["target_instance"] = int64_t(p_node->get_instance_id());
		d["old_value"] = before;
		d["new_value"] = p_args;
		if (!p_confirmed) {
			d["confirmation_required"] = true;
			return d;
		}
		const Variant expected_instance = p_args.get("expected_target_instance", Variant());
		if (!number(expected_instance, 1, 9007199254740991.0) || double(expected_instance) != Math::floor(double(expected_instance)) || int64_t(expected_instance) != int64_t(p_node->get_instance_id()) || p_args.get("expected_old_value", Variant()).get_type() != Variant::DICTIONARY || JSON::parse_string(JSON::stringify(p_args["expected_old_value"])) != JSON::parse_string(JSON::stringify(before))) {
			return result(false, "target_changed_since_confirmation");
		}
		const ObjectID object = p_node->get_instance_id();
		bool applied = bar ? bar->open_menu(selected) : tree ? tree->edit_cell(cell_item, column, value)
															 : Object::cast_to<RichTextLabel>(p_node)->activate_meta(selected);
		Node *current = ObjectDB::get_instance<Node>(object);
		bool available = current && current->is_inside_tree() && !AIChatEditorRegistry::is_protected(current);
		d["ok"] = applied;
		d["requested"] = applied;
		d["business_completed"] = false;
		d["target_available"] = available;
		d["readback"] = available ? state(current) : Dictionary();
		if (!applied) {
			d["error"] = "native_action_unavailable";
		}
		return d;
	}
	if (action.begins_with("read_")) {
		int limit = 0, offset = 0;
		if (!integer(p_args.get("limit", 100), 1, 100, limit) || !integer(p_args.get("offset", 0), 0, 4096, offset)) {
			return result(false, "invalid_item_page");
		}
		if (action == "read_graph_ports") {
			GraphEdit *graph = Object::cast_to<GraphEdit>(p_node);
			const Variant input = p_args.get("value", Variant());
			if (input.get_type() != Variant::DICTIONARY) {
				return result(false, "invalid_graph_port_page");
			}
			Dictionary value = input;
			Variant name = value.get("node", Variant());
			const Variant direction = value.get("direction", Variant());
			if (!graph_name(name) || direction.get_type() != Variant::STRING || (direction != Variant("input") && direction != Variant("output"))) {
				return result(false, "invalid_graph_port_page");
			}
			GraphNode *node = Object::cast_to<GraphNode>(graph->get_node_or_null(NodePath(name)));
			if (!node || node->get_parent() != graph || AIChatEditorRegistry::is_protected(node) || bool(node->get_meta("ai_control_page_only", false))) {
				return result(false, "invalid_graph_node");
			}
			const bool output = direction == Variant("output");
			const int total = output ? node->get_output_port_count() : node->get_input_port_count();
			Array ports;
			for (int i = 0; i < MIN(total, 4096); i++) {
				Dictionary port;
				port["index"] = i;
				port["type"] = output ? node->get_output_port_type(i) : node->get_input_port_type(i);
				port["slot"] = output ? node->get_output_port_slot(i) : node->get_input_port_slot(i);
				port["position"] = vec(output ? node->get_output_port_position(i) : node->get_input_port_position(i));
				ports.push_back(port);
			}
			Dictionary d = page(ports, total, limit, offset);
			d["target_instance"] = int64_t(p_node->get_instance_id());
			d["node_instance"] = int64_t(node->get_instance_id());
			d["direction"] = direction;
			d["state"] = before;
			d["port_action_capacity"] = 100;
			return d;
		}
		Array all = action == "read_graph_connections" ? connections(Object::cast_to<GraphEdit>(p_node)) : entries(p_node);
		int total = action == "read_graph_connections" ? Object::cast_to<GraphEdit>(p_node)->get_connections().size() : int(before["count"]);
		Dictionary d = page(all, total, limit, offset);
		d["state"] = before;
		d["target_instance"] = int64_t(p_node->get_instance_id());
		return d;
	}
	if (bool(before.get("capacity_exceeded", false))) {
		return result(false, "item_capacity_exceeded");
	}
	Ref<Resource> res = resource(p_node);
	EditorUndoRedoManager *manager = EditorUndoRedoManager::get_singleton();
	if ((Object::cast_to<CurveEdit>(p_node) || Object::cast_to<GradientEdit>(p_node)) && (res.is_null() || !manager)) {
		return result(false, "resource_unavailable");
	}
	ComplexHistoryFence *fence = nullptr;
	if (res.is_valid() && manager) {
		if (history_manager != manager->get_instance_id()) {
			Ref<ComplexHistoryFence> new_fence;
			new_fence.instantiate();
			history_fence = new_fence;
			history_manager = manager->get_instance_id();
			manager->connect("version_changed", callable_mp(new_fence.ptr(), &ComplexHistoryFence::changed));
			resource_undo.clear();
		}
		fence = static_cast<ComplexHistoryFence *>(history_fence.ptr());
		const int id = manager->get_history_id_for_object(res.ptr());
		if (manager->has_history(id)) {
			fence->observe(manager->get_history_undo_redo(id));
		}
	}
	int index = -1;
	if (action == "activate_menu_item" || action == "open_menu_submenu" || action == "gradient_remove_point" || action == "gradient_set_color" || action == "gradient_set_offset" || action == "curve_remove_point" || action == "curve_set_point" || action == "curve_set_tangents" || action == "curve_set_tangent_modes" || action == "activate_tree_item" || action == "tree_context_menu" || action == "activate_item" || action == "item_context_menu") {
		if (!integer(p_args.get("index", Variant()), 0, int(before["count"]) - 1, index)) {
			return result(false, "invalid_item_index");
		}
	}
	if (menu && bool(Dictionary(entries(menu)[index]).get("metadata_unavailable", false))) {
		return result(false, "menu_metadata_capacity_exceeded");
	}
	if (menu && (menu->is_item_disabled(index) || menu->is_item_separator(index) || (action == "activate_menu_item" && menu->get_item_submenu_node(index)) || (action == "open_menu_submenu" && !menu->get_item_submenu_node(index)))) {
		return result(false, "menu_item_not_activatable");
	}
	if (menu && action == "open_menu_submenu" && (AIChatEditorRegistry::is_protected(menu->get_item_submenu_node(index)) || bool(menu->get_item_submenu_node(index)->get_meta("ai_control_page_only", false)))) {
		return result(false, "protected_target");
	}
	int preset = -1;
	if (action == "curve_preset" && !integer(p_args.get("value", Variant()), 0, CurveEdit::PRESET_COUNT - 1, preset)) {
		return result(false, "invalid_curve_preset");
	}
	Color color;
	double offset = 0;
	if (action == "gradient_add_point" || action == "gradient_set_color") {
		Variant input = p_args.get("value", Variant());
		if (input.get_type() != Variant::ARRAY) {
			return result(false, "invalid_input_value");
		}
		Array values = input;
		int base = action == "gradient_add_point" ? 1 : 0;
		if (values.size() != 4 + base) {
			return result(false, "invalid_input_value");
		}
		for (const Variant &v : values) {
			if (!number(v, 0, 1)) {
				return result(false, "invalid_input_value");
			}
		}
		color = Color(values[base], values[base + 1], values[base + 2], values[base + 3]);
		if (base) {
			offset = values[0];
			if (int(before["count"]) >= 4096) {
				return result(false, "item_capacity_exceeded");
			}
		}
	}
	if (action == "gradient_remove_point" && int(before["count"]) <= 2) {
		return result(false, "minimum_gradient_points");
	}
	Array curve_after;
	Ref<Curve> curve = res;
	const bool curve_points = action.begins_with("curve_") && action != "curve_preset";
	if (curve_points) {
		if (curve.is_null() || !Math::is_finite(curve->get_min_domain()) || !Math::is_finite(curve->get_max_domain()) || !Math::is_finite(curve->get_min_value()) || !Math::is_finite(curve->get_max_value())) {
			return result(false, "invalid_curve_bounds");
		}
		Ref<Curve> copy;
		copy.instantiate();
		copy->set_limits(curve->get_limits());
		copy->set_data(curve->get_data());
		for (int i = 0; i < curve->get_point_count(); i++) {
			Vector2 point = curve->get_point_position(i);
			if (!point.is_finite() || !Math::is_finite(curve->get_point_left_tangent(i)) || !Math::is_finite(curve->get_point_right_tangent(i)) || (i > 0 && point.x <= curve->get_point_position(i - 1).x)) {
				return result(false, "invalid_curve_point_order");
			}
		}
		Array values;
		if (action != "curve_remove_point") {
			if (p_args.get("value", Variant()).get_type() != Variant::ARRAY || Array(p_args["value"]).size() != 2) {
				return result(false, "invalid_curve_value");
			}
			values = p_args["value"];
		}
		if (action == "curve_add_point" || action == "curve_set_point") {
			if (!number(values[0], curve->get_min_domain(), curve->get_max_domain()) || !number(values[1], curve->get_min_value(), curve->get_max_value())) {
				return result(false, "curve_point_out_of_range");
			}
			if (action == "curve_add_point" && curve->get_point_count() >= 4096) {
				return result(false, "item_capacity_exceeded");
			}
			const Vector2 point(values[0], values[1]);
			for (int i = 0; i < curve->get_point_count(); i++) {
				if ((action == "curve_add_point" || i != index) && Math::is_equal_approx(curve->get_point_position(i).x, point.x)) {
					return result(false, "curve_duplicate_offset");
				}
			}
			if (action == "curve_add_point") {
				copy->add_point(point);
			} else {
				copy->set_point_value(index, point.y);
				copy->set_point_offset(index, point.x);
			}
		} else if (action == "curve_remove_point") {
			copy->remove_point(index);
		} else if (action == "curve_set_tangents") {
			if (!number(values[0], -1000000, 1000000) || !number(values[1], -1000000, 1000000)) {
				return result(false, "invalid_curve_tangent");
			}
			if (curve->get_point_left_mode(index) != Curve::TANGENT_FREE || curve->get_point_right_mode(index) != Curve::TANGENT_FREE) {
				return result(false, "curve_tangent_mode_not_free");
			}
			copy->set_point_left_tangent(index, values[0]);
			copy->set_point_right_tangent(index, values[1]);
		} else if (action == "curve_set_tangent_modes") {
			int left = 0, right = 0;
			if (!integer(values[0], 0, Curve::TANGENT_MODE_COUNT - 1, left) || !integer(values[1], 0, Curve::TANGENT_MODE_COUNT - 1, right)) {
				return result(false, "invalid_curve_tangent_mode");
			}
			copy->set_point_left_mode(index, Curve::TangentMode(left));
			copy->set_point_right_mode(index, Curve::TangentMode(right));
		}
		for (int i = 0; i < copy->get_point_count(); i++) {
			if (!copy->get_point_position(i).is_finite() || !Math::is_finite(copy->get_point_left_tangent(i)) || !Math::is_finite(copy->get_point_right_tangent(i))) {
				return result(false, "nonfinite_curve_result");
			}
		}
		curve_after = copy->get_data();
	}
	Ref<Gradient> offset_gradient = res;
	int offset_after_index = index;
	float old_offset = 0;
	Vector<float> expected_offsets;
	Vector<Color> expected_colors;
	if (action == "gradient_set_offset") {
		if (!number(p_args.get("value", Variant()), 0, 1)) {
			return result(false, "invalid_gradient_offset");
		}
		offset = p_args["value"];
		old_offset = offset_gradient->get_offset(index);
		offset_after_index = 0;
		for (int i = 0; i < offset_gradient->get_point_count(); i++) {
			const float current = offset_gradient->get_offset(i);
			if (!Math::is_finite(current) || (i && current <= offset_gradient->get_offset(i - 1))) {
				return result(false, "ambiguous_gradient_point_order");
			}
			if (i != index && Math::is_equal_approx(current, float(offset))) {
				return result(false, "gradient_duplicate_offset");
			}
			if (i != index && current < float(offset)) {
				offset_after_index++;
			}
		}
	}
	if (action == "gradient_set_offset") {
		Ref<Gradient> copy;
		copy.instantiate();
		copy->set_offsets(offset_gradient->get_offsets());
		copy->set_colors(offset_gradient->get_colors());
		copy->set_offset(index, float(offset));
		if (copy->get_point_count()) {
			copy->get_offset(0); // Force native sorting before retaining paired arrays.
		}
		expected_offsets = copy->get_offsets();
		expected_colors = copy->get_colors();
	}
	TreeItem *item = nullptr;
	if (Tree *tree = Object::cast_to<Tree>(p_node)) {
		item = tree_item(tree, index);
		if (!item || !item->is_selectable(0) || (action == "tree_context_menu" && !tree->get_allow_rmb_select())) {
			return result(false, "invalid_item_index");
		}
	}
	if (ItemList *items = Object::cast_to<ItemList>(p_node)) {
		if (items->is_item_disabled(index) || !items->is_item_selectable(index) || (action == "item_context_menu" && !items->get_allow_rmb_select())) {
			return result(false, "invalid_item_index");
		}
	}
	if (item || Object::cast_to<ItemList>(p_node)) {
		int budget = 512;
		Variant metadata = item ? item->get_metadata(0) : Object::cast_to<ItemList>(p_node)->get_item_metadata(index);
		if (metadata_identity(metadata, 0, budget).is_empty()) {
			return result(false, "item_metadata_capacity_exceeded");
		}
	}
	GraphEdit *graph = Object::cast_to<GraphEdit>(p_node);
	GraphNode *from = nullptr;
	GraphNode *to = nullptr;
	int from_port = 0, to_port = 0;
	Vector2 position;
	if (graph) {
		Variant input = p_args.get("value", Variant());
		if (input.get_type() != Variant::DICTIONARY) {
			return result(false, "invalid_graph_operation");
		}
		Dictionary v = input;
		const Variant from_name = v.get(action == "graph_move_node" ? "node" : "from", Variant());
		const Variant to_name = v.get("to", Variant());
		if (!graph_name(from_name) || (action != "graph_move_node" && !graph_name(to_name))) {
			return result(false, "invalid_graph_node");
		}
		from = Object::cast_to<GraphNode>(graph->get_node_or_null(NodePath(from_name)));
		to = action == "graph_move_node" ? nullptr : Object::cast_to<GraphNode>(graph->get_node_or_null(NodePath(to_name)));
		for (GraphNode *node : { from, to }) {
			if (node && (AIChatEditorRegistry::is_protected(node) || bool(node->get_meta("ai_control_page_only", false)))) {
				return result(false, "protected_target");
			}
		}
		if (!from || from->get_parent() != graph || (action != "graph_move_node" && (!to || to->get_parent() != graph))) {
			return result(false, "invalid_graph_node");
		}
		if (action == "graph_move_node") {
			Variant input_position = v.get("position", Variant());
			if (!from->is_draggable() || input_position.get_type() != Variant::ARRAY || Array(input_position).size() != 2) {
				return result(false, "invalid_graph_position");
			}
			Array a = input_position;
			if (!number(a[0], -1000000, 1000000) || !number(a[1], -1000000, 1000000)) {
				return result(false, "invalid_graph_position");
			}
			position = Vector2(a[0], a[1]);
		} else {
			if (!integer(v.get("from_port", Variant()), 0, MIN(99, from->get_output_port_count() - 1), from_port) || !integer(v.get("to_port", Variant()), 0, MIN(99, to->get_input_port_count() - 1), to_port)) {
				return result(false, "invalid_graph_port");
			}
			if (action == "graph_connect" && from->get_output_port_type(from_port) != to->get_input_port_type(to_port) && !to->is_ignoring_valid_connection_type() && !graph->is_valid_connection_type(from->get_output_port_type(from_port), to->get_input_port_type(to_port))) {
				return result(false, "incompatible_graph_ports");
			}
			bool connected = graph->is_node_connected(from->get_name(), from_port, to->get_name(), to_port);
			if (connected == (action == "graph_connect")) {
				return result(false, "graph_connection_state_mismatch");
			}
		}
	}
	ResourceUndo *undo = res.is_valid() ? resource_undo.getptr(res->get_instance_id()) : nullptr;
	if (resource_history) {
		UndoRedo *history = undo && manager && manager->has_history(undo->history) ? manager->get_history_undo_redo(undo->history) : nullptr;
		const bool redo = action == "redo_resource_edit";
		if (!undo || res.is_null() || undo->resource != res->get_instance_id() || undo->epoch != fence->epoch || undo->undone != redo || (redo ? undo->before : undo->after) != before || !history || (redo ? !history->has_redo() : !history->has_undo()) || history->get_version() != undo->version) {
			return result(false, redo ? "redo_unavailable" : "undo_unavailable");
		}
	}
	Dictionary d = result(false);
	d["action"] = action;
	d["target"] = p_id;
	d["target_instance"] = int64_t(p_node->get_instance_id());
	d["old_value"] = before;
	d["new_value"] = resource_history ? Variant(action == "undo_resource_edit" ? undo->before : undo->after) : p_args.get("value", index);
	if (!p_confirmed) {
		d["confirmation_required"] = true;
		return d;
	}
	const Variant expected_instance = p_args.get("expected_target_instance", Variant());
	if (!number(expected_instance, 1, 9007199254740991.0) || double(expected_instance) != Math::floor(double(expected_instance)) || int64_t(expected_instance) != int64_t(p_node->get_instance_id()) || p_args.get("expected_old_value", Variant()).get_type() != Variant::DICTIONARY || JSON::parse_string(JSON::stringify(p_args["expected_old_value"])) != JSON::parse_string(JSON::stringify(before))) {
		return result(false, "target_changed_since_confirmation");
	}
	const Dictionary expected_undo = resource_history ? (action == "undo_resource_edit" ? undo->before : undo->after) : Dictionary();
	const ObjectID node_id = p_node->get_instance_id();
	auto interrupted = [&]() {
		Dictionary halted = result(true);
		halted["requested"] = true;
		halted["business_completed"] = false;
		halted["halted_reason"] = "target_unavailable_during_native_callback";
		halted["target_available"] = ObjectDB::get_instance<Node>(node_id) != nullptr;
		return halted;
	};
	if (res.is_valid() && !resource_history) {
		// A non-merging outer transaction prevents native MERGE_ENDS edits from
		// absorbing an earlier user action into this command's undo.
		manager->create_action("Controlled resource edit", UndoRedo::MERGE_DISABLE, res.ptr());
		fence->observe(manager->get_history_for_object(res.ptr()).undo_redo);
	}
	ObjectID opened_submenu;
	if (menu) {
		if (action == "open_menu_submenu") {
			opened_submenu = menu->get_item_submenu_node(index)->get_instance_id();
			ComplexSubmenuRequest *request = memnew(ComplexSubmenuRequest);
			request->set_meta("ai_control_exclude", true);
			menu->get_tree()->get_root()->add_child(request);
			request->parent = node_id;
			request->child = opened_submenu;
			request->index = index;
			request->expected = before;
			menu->set_meta("_ai_complex_submenu_status", "queued");
			menu->get_tree()->create_timer(0.05, true)->connect("timeout", callable_mp(request, &ComplexSubmenuRequest::prepare), Object::CONNECT_ONE_SHOT);
		} else {
			menu->activate_item(index);
		}
	} else if (curve_points || action == "gradient_set_offset") {
		UndoRedo *native_history = manager->get_history_for_object(res.ptr()).undo_redo;
		Ref<ComplexResourceAction> receiver;
		receiver.instantiate();
		if (curve_points) {
			native_history->add_do_method(callable_mp(receiver.ptr(), &ComplexResourceAction::curve_data).bind(curve, curve_after));
			native_history->add_undo_method(callable_mp(receiver.ptr(), &ComplexResourceAction::curve_data).bind(curve, curve->get_data()));
		} else {
			native_history->add_do_method(callable_mp(receiver.ptr(), &ComplexResourceAction::gradient_offset).bind(offset_gradient, index, float(offset)));
			native_history->add_undo_method(callable_mp(receiver.ptr(), &ComplexResourceAction::gradient_offset).bind(offset_gradient, offset_after_index, old_offset));
		}
	} else if (CurveEdit *edit = Object::cast_to<CurveEdit>(p_node); edit && action == "curve_preset") {
		edit->use_preset(preset);
	} else if (GradientEdit *gradient_edit = Object::cast_to<GradientEdit>(p_node); gradient_edit && !resource_history) {
		if (action == "gradient_add_point") {
			gradient_edit->add_point(offset, color);
		} else if (action == "gradient_remove_point") {
			gradient_edit->remove_point(index);
		} else if (action == "gradient_set_color") {
			gradient_edit->set_color(index, color);
		} else {
			gradient_edit->reverse_gradient();
		}
	} else if (resource_history) {
		if (action == "undo_resource_edit") {
			manager->undo_history(undo->history);
		} else {
			manager->redo_history(undo->history);
		}
		undo->undone = action == "undo_resource_edit";
		undo->version = manager->get_history_undo_redo(undo->history)->get_version();
		undo->epoch = fence->epoch;
	} else if (graph) {
		const ObjectID from_id = from->get_instance_id();
		auto refresh_graph = [&]() {
			graph = ObjectDB::get_instance<GraphEdit>(node_id);
			from = ObjectDB::get_instance<GraphNode>(from_id);
			return graph && graph->is_inside_tree() && from && from->get_parent() == graph && !AIChatEditorRegistry::is_protected(from);
		};
		if (action == "graph_move_node") {
			graph->emit_signal("begin_node_move");
			if (!refresh_graph()) {
				return interrupted();
			}
			from->set_drag(true);
			from->set_position_offset(position);
			if (!refresh_graph()) {
				return interrupted();
			}
			from->set_drag(false);
			if (!refresh_graph()) {
				return interrupted();
			}
			graph->emit_signal("end_node_move");
		} else {
			// These fixed native requests reach each GraphEdit owner's real handlers.
			// Deferred handlers are intentionally reported only as requested.
			graph->emit_signal(action == "graph_connect" ? "connection_request" : "disconnection_request", from->get_name(), from_port, to->get_name(), to_port);
		}
	} else {
		if (Tree *tree = Object::cast_to<Tree>(p_node)) {
			tree->set_selected(item, 0);
		} else {
			ItemList *items = Object::cast_to<ItemList>(p_node);
			items->set_current(index);
			items = ObjectDB::get_instance<ItemList>(node_id);
			if (!items || !items->is_inside_tree() || AIChatEditorRegistry::is_protected(items) || index >= items->get_item_count()) {
				return interrupted();
			}
			items->select(index);
		}
		control = ObjectDB::get_instance<Control>(node_id);
		if (!control || !control->is_inside_tree() || AIChatEditorRegistry::is_protected(control)) {
			return interrupted();
		}
		Ref<InputEventAction> event;
		event.instantiate();
		event->set_action(action == "tree_context_menu" || action == "item_context_menu" ? "ui_menu" : "ui_accept");
		event->set_pressed(true);
		control->gui_input(event);
	}
	if (res.is_valid() && !resource_history) {
		manager->commit_action();
	}
	Node *current = ObjectDB::get_instance<Node>(node_id);
	if (current && (!current->is_inside_tree() || AIChatEditorRegistry::is_protected(current))) {
		current = nullptr;
	}
	Dictionary after = current ? state(current) : Dictionary();
	bool resource_readback_matches = true;
	if (curve_points) {
		resource_readback_matches = native_resource(res) && curve->get_data() == curve_after;
	} else if (action == "gradient_set_offset") {
		resource_readback_matches = native_resource(res) && offset_gradient->get_offsets() == expected_offsets && offset_gradient->get_colors() == expected_colors;
	}
	if (res.is_valid() && !resource_history && current && resource(current) == res && resource_readback_matches) {
		int history_id = manager->get_history_id_for_object(res.ptr());
		UndoRedo *history = manager->has_history(history_id) ? manager->get_history_undo_redo(history_id) : nullptr;
		if (history && after != before) {
			if (resource_undo.size() >= 128) {
				resource_undo.clear();
			}
			resource_undo[res->get_instance_id()] = { res->get_instance_id(), history_id, history->get_version(), before, after, false, fence->epoch };
		}
	}
	d["ok"] = resource_readback_matches && (!resource_history || after == expected_undo);
	if (!bool(d["ok"])) {
		d["error"] = resource_history ? "resource_history_readback_mismatch" : "resource_write_readback_mismatch";
	}
	d["requested"] = true;
	d["business_completed"] = bool(d["ok"]) && res.is_valid() && current && resource(current) == res && after != before;
	d["state_changed"] = after != before;
	d["readback"] = after;
	d["target_available"] = current != nullptr;
	if (opened_submenu.is_valid()) {
		PopupMenu *submenu = ObjectDB::get_instance<PopupMenu>(opened_submenu);
		d["submenu_instance"] = int64_t(opened_submenu);
		d["submenu_request_status"] = "queued";
		d["submenu_visible"] = submenu && submenu->is_visible();
	}
	// Graph UI state can change independently of the owner's resource/business data.
	// A graph/list/menu request never claims business completion from UI state alone.
	d.erase("confirmation_required");
	return d;
}
