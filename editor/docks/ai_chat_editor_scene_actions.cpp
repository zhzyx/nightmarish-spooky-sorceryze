/**************************************************************************/
/*  ai_chat_editor_scene_actions.cpp                                       */
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

#include "ai_chat_editor_scene_actions.h"

#include "core/config/project_settings.h"
#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/io/resource_uid.h"
#include "core/math/math_funcs.h"
#include "core/object/class_db.h"
#include "core/object/undo_redo.h"
#include "editor/docks/scene_tree_dock.h"
#include "editor/editor_data.h"
#include "editor/editor_interface.h"
#include "editor/editor_undo_redo_manager.h"
#include "scene/main/node.h"
#include "scene/resources/packed_scene.h"

namespace {
Dictionary outcome(bool p_ok, const String &p_error = String()) {
	Dictionary r;
	r["ok"] = p_ok;
	if (!p_error.is_empty()) {
		r["error"] = p_error;
	}
	return r;
}

bool integer(const Variant &p_value) {
	return p_value.is_num() && Math::is_finite(double(p_value)) && Math::floor(double(p_value)) == double(p_value) && Math::abs(double(p_value)) <= 9007199254740991.0;
}

bool json_value(const Variant &p_value, int p_depth = 0) {
	if (p_depth > 8) {
		return false;
	}
	switch (p_value.get_type()) {
		case Variant::NIL:
		case Variant::BOOL:
		case Variant::STRING:
			return true;
		case Variant::INT:
			return integer(p_value);
		case Variant::FLOAT:
			return Math::is_finite(double(p_value));
		case Variant::ARRAY: {
			const Array a = p_value;
			if (a.size() > 100) {
				return false;
			}
			for (const Variant &v : a) {
				if (!json_value(v, p_depth + 1)) {
					return false;
				}
			}
			return true;
		}
		case Variant::DICTIONARY: {
			const Dictionary d = p_value;
			if (d.size() > 100) {
				return false;
			}
			for (const Variant &k : d.keys()) {
				if (k.get_type() != Variant::STRING || !json_value(d[k], p_depth + 1)) {
					return false;
				}
			}
			return true;
		}
		default:
			return false;
	}
}

// JSON transports all numbers as doubles. Preserve exact identity only in the
// interoperable integer range; never coerce strings, bools or fractional IDs.
bool same_json(const Variant &p_a, const Variant &p_b) {
	if (p_a.is_num() && p_b.is_num()) {
		return Math::is_finite(double(p_a)) && Math::is_finite(double(p_b)) && double(p_a) == double(p_b);
	}
	if (p_a.get_type() != p_b.get_type()) {
		return false;
	}
	if (p_a.get_type() == Variant::DICTIONARY) {
		const Dictionary a = p_a, b = p_b;
		if (a.size() != b.size()) {
			return false;
		}
		for (const Variant &key : a.keys()) {
			if (!b.has(key) || !same_json(a[key], b[key])) {
				return false;
			}
		}
		return true;
	}
	if (p_a.get_type() == Variant::ARRAY) {
		const Array a = p_a, b = p_b;
		if (a.size() != b.size()) {
			return false;
		}
		for (int i = 0; i < a.size(); i++) {
			if (!same_json(a[i], b[i])) {
				return false;
			}
		}
		return true;
	}
	return p_a == p_b;
}

bool node_path(const Variant &p_value) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String s = p_value;
	if (s.is_empty() || s.length() > 1024 || s.contains("\\") || s.contains(":") || s.contains("//") || s.contains_char(0)) {
		return false;
	}
	const NodePath path(s);
	if (path.is_absolute() || path.get_subname_count()) {
		return false;
	}
	for (const String &part : s.split("/")) {
		if (part == ".." || (part == "." && s != ".") || part.is_empty()) {
			return false;
		}
	}
	return true;
}

bool node_name(const Variant &p_value) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String s = p_value;
	return !s.is_empty() && s.length() <= 128 && s != "." && s != ".." && !s.contains_char(0) && s.validate_node_name() == s;
}

bool builtin_node(const String &p_type) {
	// Explicit built-in constructors only: ClassDB also contains extension classes.
	return p_type == "Node" || p_type == "Node2D" || p_type == "Node3D" || p_type == "Control" || p_type == "Sprite2D" || p_type == "Camera2D" || p_type == "Marker2D" || p_type == "Marker3D" || p_type == "Label" || p_type == "Button" || p_type == "Panel" || p_type == "VBoxContainer" || p_type == "HBoxContainer" || p_type == "MarginContainer";
}

bool safe_property(const String &p_name) {
	// Excludes script, owner, paths, metadata and arbitrary resource/callable setters.
	return p_name == "position" || p_name == "rotation" || p_name == "rotation_degrees" || p_name == "scale" || p_name == "visible" || p_name == "modulate" || p_name == "self_modulate" || p_name == "text" || p_name == "size" || p_name == "custom_minimum_size" || p_name == "offset_left" || p_name == "offset_top" || p_name == "offset_right" || p_name == "offset_bottom";
}

Variant wire(const Variant &p_value) {
	Array a;
	switch (p_value.get_type()) {
		case Variant::VECTOR2: {
			const Vector2 v = p_value;
			a.push_back(v.x);
			a.push_back(v.y);
		} break;
		case Variant::VECTOR2I: {
			const Vector2i v = p_value;
			a.push_back(v.x);
			a.push_back(v.y);
		} break;
		case Variant::VECTOR3: {
			const Vector3 v = p_value;
			a.push_back(v.x);
			a.push_back(v.y);
			a.push_back(v.z);
		} break;
		case Variant::VECTOR3I: {
			const Vector3i v = p_value;
			a.push_back(v.x);
			a.push_back(v.y);
			a.push_back(v.z);
		} break;
		case Variant::COLOR: {
			const Color v = p_value;
			a.push_back(v.r);
			a.push_back(v.g);
			a.push_back(v.b);
			a.push_back(v.a);
		} break;
		default:
			return p_value;
	}
	return a;
}

bool scene_snapshot(Node *p_root, Array &r_nodes, bool p_for_run = false) {
	LocalVector<Node *> pending;
	pending.push_back(p_root);
	while (!pending.is_empty()) {
		Node *n = pending[pending.size() - 1];
		pending.remove_at(pending.size() - 1);
		// Conservative first implementation: no inherited/instanced/scripted scenes.
		if (r_nodes.size() >= 100 || (!p_for_run && (n->get_script().get_type() != Variant::NIL || ClassDB::get_api_type(n->get_class()) != ClassDB::API_CORE || n->get_scene_inherited_state().is_valid() || (n != p_root && (!n->get_scene_file_path().is_empty() || n->get_owner() != p_root)) || n->get_child_count(true) != n->get_child_count(false)))) {
			return false;
		}
		Dictionary entry;
		entry["instance"] = int64_t(n->get_instance_id());
		entry["path"] = String(p_root->get_path_to(n));
		entry["class"] = n->get_class();
		entry["parent"] = n->get_parent() ? int64_t(n->get_parent()->get_instance_id()) : 0;
		entry["owner"] = n->get_owner() ? int64_t(n->get_owner()->get_instance_id()) : 0;
		entry["index"] = n->get_index();
		r_nodes.push_back(entry);
		for (int i = n->get_child_count() - 1; i >= 0; i--) {
			pending.push_back(n->get_child(i));
		}
	}
	return JSON::stringify(r_nodes).utf8().length() <= 12000;
}

bool linked_path(const String &p_path) {
	ProjectSettings *settings = ProjectSettings::get_singleton();
	if (!settings) {
		return true;
	}
	Ref<DirAccess> dir = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
	String path = settings->get_resource_path();
	if (dir.is_null() || dir->is_link(path)) {
		return true;
	}
	for (const String &part : p_path.trim_prefix("res://").split("/")) {
		path = path.path_join(part);
		if (dir->is_link(path)) {
			return true;
		}
	}
	return false;
}
} // namespace

bool AIChatEditorSceneActions::valid_project_path(const String &p_path) {
	if (!p_path.begins_with("res://") || p_path.length() > 1024 || p_path.contains("\\") || p_path.contains_char(0)) {
		return false;
	}
	for (const String &part : p_path.trim_prefix("res://").split("/")) {
		if (part.is_empty() || part == "." || part == ".." || part.contains(":")) {
			return false;
		}
	}
	return true;
}

bool AIChatEditorSceneActions::convert_json_value(const Variant &p_value, Variant::Type p_type, Variant &r_value) {
	if (!json_value(p_value) || JSON::stringify(p_value).utf8().length() > 8192) {
		return false;
	}
	if (p_type == Variant::INT && integer(p_value)) {
		r_value = int64_t(p_value);
		return true;
	}
	if (p_type == Variant::FLOAT && p_value.is_num()) {
		r_value = double(p_value);
		return true;
	}
	if ((p_type == Variant::BOOL || p_type == Variant::STRING) && p_type == p_value.get_type()) {
		r_value = p_value;
		return true;
	}
	const int count = p_type == Variant::VECTOR2 || p_type == Variant::VECTOR2I ? 2 : p_type == Variant::VECTOR3 || p_type == Variant::VECTOR3I ? 3
			: p_type == Variant::COLOR																											? 4
																																				: 0;
	if (!count || p_value.get_type() != Variant::ARRAY || Array(p_value).size() != count) {
		return false;
	}
	const Array a = p_value;
	for (const Variant &v : a) {
		if (!v.is_num() || Math::abs(double(v)) > 1000000000.0 || ((p_type == Variant::VECTOR2I || p_type == Variant::VECTOR3I) && !integer(v))) {
			return false;
		}
	}
	switch (p_type) {
		case Variant::VECTOR2:
			r_value = Vector2(a[0], a[1]);
			break;
		case Variant::VECTOR2I:
			r_value = Vector2i(int(a[0]), int(a[1]));
			break;
		case Variant::VECTOR3:
			r_value = Vector3(a[0], a[1], a[2]);
			break;
		case Variant::VECTOR3I:
			r_value = Vector3i(int(a[0]), int(a[1]), int(a[2]));
			break;
		case Variant::COLOR:
			r_value = Color(a[0], a[1], a[2], a[3]);
			break;
		default:
			return false;
	}
	return true;
}

bool AIChatEditorSceneActions::supports(const String &p_action) {
	return p_action == "scene_create_node" || p_action == "scene_delete_node" || p_action == "scene_rename_node" || p_action == "scene_reparent_node" || p_action == "scene_select_nodes" || p_action == "scene_set_property" || p_action == "scene_assign_resource" || p_action == "scene_connect_signal" || p_action == "run_project" || p_action == "run_scene" || p_action == "stop_project";
}

Dictionary AIChatEditorSceneActions::perform(const Dictionary &p_args, bool p_confirmed) {
	if (!json_value(p_args) || JSON::stringify(p_args).utf8().length() > 32768 || p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return outcome(false, "invalid_scene_arguments");
	}
	const String action = p_args["action"];
	if (!supports(action)) {
		return outcome(false, "unknown_action");
	}
	if (action == "scene_assign_resource" || (action == "run_scene" && p_args.has("target") && p_args["target"] != Variant(String()))) {
		const Variant path = p_args.get(action == "run_scene" ? "target" : "resource_path", Variant());
		if (path.get_type() != Variant::STRING || !valid_project_path(path)) {
			return outcome(false, "invalid_project_path");
		}
		if (linked_path(path)) {
			return outcome(false, "linked_project_path");
		}
	}
	// ResourceLoader may run tool scripts/custom loaders. Signal targets can
	// invoke arbitrary methods. Keep these explicit failures until a safe path exists.
	if (action == "scene_assign_resource" || action == "scene_connect_signal") {
		return outcome(false, "script_capable_operation_not_supported");
	}
	const Variant target_arg = p_args.get("target", ".");
	if (action != "run_scene" && !node_path(target_arg)) {
		return outcome(false, "invalid_node_path");
	}
	const String target = target_arg;
	const bool create = action == "scene_create_node", select = action == "scene_select_nodes", property = action == "scene_set_property", reparent = action == "scene_reparent_node", stop = action == "stop_project";
	if ((create || action == "scene_rename_node") && !node_name(p_args.get("name", Variant()))) {
		return outcome(false, "invalid_node_name");
	}
	if (create && (p_args.get("type", Variant()).get_type() != Variant::STRING || !builtin_node(p_args["type"]))) {
		return outcome(false, "unsupported_node_type");
	}
	if (reparent && !node_path(p_args.get("parent", Variant()))) {
		return outcome(false, "invalid_parent_path");
	}
	if (property && (p_args.get("property", Variant()).get_type() != Variant::STRING || !safe_property(p_args["property"]))) {
		return outcome(false, "protected_property");
	}
	Array paths;
	if (select) {
		if (p_args.get("nodes", Variant()).get_type() != Variant::ARRAY) {
			return outcome(false, "invalid_selection");
		}
		paths = p_args["nodes"];
		if (paths.size() > 100) {
			return outcome(false, "selection_capacity");
		}
		for (int i = 0; i < paths.size(); i++) {
			if (!node_path(paths[i]) || paths.find(paths[i]) != i) {
				return outcome(false, "invalid_selection");
			}
		}
	}
	EditorInterface *editor = EditorInterface::get_singleton();
	if (!editor) {
		return outcome(false, "editor_unavailable");
	}
	Node *root = editor->get_edited_scene_root();
	if (action == "run_project" || action == "run_scene") {
		const String configured = action == "run_project" ? String(ProjectSettings::get_singleton()->get_setting("application/run/main_scene", "")) : String(p_args.get("target", root ? root->get_scene_file_path() : String()));
		const String path = ResourceUID::ensure_path(configured);
		if (!valid_project_path(path) || path.get_extension().to_lower() != "tscn" || !FileAccess::exists(path)) {
			return outcome(false, "invalid_run_scene");
		}
		if (linked_path(path)) {
			return outcome(false, "linked_project_path");
		}
		Dictionary state;
		Dictionary proposal = p_args.duplicate(true);
		proposal.erase("expected_old_value");
		proposal.erase("expected_target_instance");
		state["proposal"] = proposal;
		state["root"] = root ? int64_t(root->get_instance_id()) : 0;
		state["running"] = editor->is_playing_scene();
		state["playing_scene"] = editor->get_playing_scene();
		state["scene"] = path;
		state["scene_sha256"] = FileAccess::get_sha256(path);
		if (linked_path("res://project.godot")) {
			return outcome(false, "linked_project_path");
		}
		state["project_sha256"] = FileAccess::get_sha256("res://project.godot");
		EditorUndoRedoManager *undo = EditorUndoRedoManager::get_singleton();
		if (root && undo) {
			const int history_id = undo->get_history_id_for_object(root);
			UndoRedo *history = undo->has_history(history_id) ? undo->get_history_undo_redo(history_id) : nullptr;
			state["scene_version"] = history ? int64_t(history->get_version()) : 0;
		}
		Array scene_nodes;
		if (root && !scene_snapshot(root, scene_nodes, true)) {
			return outcome(false, "scene_snapshot_capacity");
		}
		state["nodes"] = scene_nodes;
		if (JSON::stringify(state).utf8().length() > 16384) {
			return outcome(false, "scene_snapshot_capacity");
		}
		Dictionary r = outcome(false);
		r["action"] = action;
		r["target"] = path;
		r["old_value"] = state;
		r["target_instance"] = int64_t(editor->get_instance_id());
		r["manual_confirmation_required"] = true;
		if (!p_confirmed) {
			r["confirmation_required"] = true;
			return r;
		}
		const Variant expected = p_args.get("expected_target_instance", Variant());
		if (!integer(expected) || int64_t(expected) != int64_t(editor->get_instance_id()) || !p_args.has("expected_old_value") || !same_json(p_args["expected_old_value"], state)) {
			return outcome(false, "scene_changed_since_confirmation");
		}
		// The caller must obtain an explicit human confirmation even under autoexec.
		// Use the normal editor save/run chain; do not invoke arbitrary methods.
		if (action == "run_project") {
			editor->play_main_scene();
		} else {
			editor->play_custom_scene(path);
		}
		r["ok"] = true;
		r["run_requested"] = true;
		return r;
	}
	Node *node = root ? root->get_node_or_null(NodePath(target)) : nullptr;
	if (!stop && (!node || (node != root && !root->is_ancestor_of(node)))) {
		return outcome(false, "node_not_found");
	}
	Dictionary state;
	Dictionary proposal = p_args.duplicate(true);
	proposal.erase("expected_old_value");
	proposal.erase("expected_target_instance");
	state["proposal"] = proposal;
	state["running"] = editor->is_playing_scene();
	state["playing_scene"] = editor->get_playing_scene();
	state["root"] = root ? int64_t(root->get_instance_id()) : 0;
	const int64_t instance = int64_t(stop ? editor->get_instance_id() : node->get_instance_id());
	Array nodes;
	if (!stop && !scene_snapshot(root, nodes)) {
		return outcome(false, "scene_requires_native_editor");
	}
	state["nodes"] = nodes;
	EditorUndoRedoManager *history_manager = EditorUndoRedoManager::get_singleton();
	if (root && history_manager) {
		const int history_id = history_manager->get_history_id_for_object(root);
		UndoRedo *history = history_manager->has_history(history_id) ? history_manager->get_history_undo_redo(history_id) : nullptr;
		state["scene_version"] = history ? int64_t(history->get_version()) : 0;
	}
	Array old_selection;
	if (!stop) {
		for (Node *selected : editor->get_selection()->get_full_selected_node_list()) {
			old_selection.push_back(int64_t(selected->get_instance_id()));
		}
	}
	state["selection"] = old_selection;
	LocalVector<Node *> selected_nodes;
	for (const Variant &path : paths) {
		Node *selected = root->get_node_or_null(NodePath(String(path)));
		if (!selected || (selected != root && !root->is_ancestor_of(selected))) {
			return outcome(false, "node_not_found");
		}
		selected_nodes.push_back(selected);
	}
	Node *new_parent = reparent ? root->get_node_or_null(NodePath(String(p_args["parent"]))) : nullptr;
	if (reparent && (!new_parent || new_parent == node || node->is_ancestor_of(new_parent))) {
		return outcome(false, "invalid_parent");
	}
	if (!stop && !select && !property && !create && node == root) {
		return outcome(false, "protected_scene_root");
	}
	if ((action == "scene_rename_node" || reparent || action == "scene_delete_node") && !SceneTreeDock::get_singleton()) {
		return outcome(false, "scene_tree_unavailable");
	}
	if ((action == "scene_delete_node" || reparent) && node->get_child_count() > 0) {
		return outcome(false, "subtree_requires_native_editor");
	}
	if ((create || action == "scene_rename_node" || reparent)) {
		Node *parent = create ? node : reparent ? new_parent
												: node->get_parent();
		const String name = reparent ? String(node->get_name()) : String(p_args["name"]);
		for (int i = 0; i < parent->get_child_count(); i++) {
			Node *sibling = parent->get_child(i);
			if ((create || sibling != node) && sibling->get_name() == name) {
				return outcome(false, "node_name_conflict");
			}
		}
	}
	Variant value, previous;
	String property_name;
	if (property) {
		property_name = p_args["property"];
		List<PropertyInfo> properties;
		node->get_property_list(&properties);
		bool found = false;
		for (const PropertyInfo &info : properties) {
			if (info.name == property_name && (info.usage & PROPERTY_USAGE_EDITOR) && !(info.usage & PROPERTY_USAGE_READ_ONLY)) {
				previous = node->get(property_name);
				if (previous.get_type() != info.type || !convert_json_value(p_args.get("value", Variant()), info.type, value)) {
					return outcome(false, "property_type_mismatch");
				}
				state["property_type"] = int(info.type);
				state["property_value"] = wire(previous);
				found = true;
				break;
			}
		}
		if (!found) {
			return outcome(false, "property_unavailable");
		}
	}
	if (JSON::stringify(state).utf8().length() > 16384 || !json_value(state)) {
		return outcome(false, "scene_snapshot_capacity");
	}
	Dictionary r = outcome(false);
	r["action"] = action;
	r["target"] = target;
	r["target_instance"] = instance;
	r["old_value"] = state;
	if (!p_confirmed) {
		r["confirmation_required"] = true;
		return r;
	}
	const Variant expected_instance = p_args.get("expected_target_instance", Variant());
	if (!integer(expected_instance) || int64_t(expected_instance) != instance || !p_args.has("expected_old_value") || !same_json(p_args["expected_old_value"], state)) {
		return outcome(false, "scene_changed_since_confirmation");
	}
	if (stop) {
		editor->stop_playing_scene();
	} else {
		EditorUndoRedoManager *undo = EditorUndoRedoManager::get_singleton();
		if (!undo || undo->is_committing_action()) {
			return outcome(false, "undo_unavailable");
		}
		Node *created = nullptr;
		if (create) {
			created = Object::cast_to<Node>(ClassDB::instantiate(p_args["type"]));
			if (!created) {
				return outcome(false, "node_creation_failed");
			}
			created->set_name(p_args["name"]);
		}
		undo->create_action("AI Chat: " + action, UndoRedo::MERGE_DISABLE, root, false, !select);
		if (select) {
			EditorSelection *selection = editor->get_selection();
			undo->add_do_method(selection, "clear");
			undo->add_undo_method(selection, "clear");
			for (Node *selected : selected_nodes) {
				undo->add_do_method(selection, "add_node", selected);
			}
			for (Node *selected : selection->get_full_selected_node_list()) {
				undo->add_undo_method(selection, "add_node", selected);
			}
		} else if (create) {
			undo->add_do_method(node, "add_child", created, true);
			undo->add_do_method(created, "set_owner", root);
			undo->add_undo_method(node, "remove_child", created);
			undo->add_do_reference(created);
		} else if (property) {
			undo->add_do_property(node, property_name, value);
			undo->add_undo_property(node, property_name, previous);
		} else if (action == "scene_rename_node") {
			undo->add_do_method(node, "set_name", p_args["name"]);
			undo->add_undo_method(node, "set_name", node->get_name());
		} else if (reparent) {
			undo->add_do_method(node, "reparent", new_parent, false);
			undo->add_do_method(node, "set_owner", root);
			undo->add_undo_method(node, "reparent", node->get_parent(), false);
			undo->add_undo_method(node->get_parent(), "move_child", node, node->get_index());
			undo->add_undo_method(node, "set_owner", root);
		} else if (action == "scene_delete_node") {
			undo->add_do_method(editor->get_selection(), "remove_node", node);
			undo->add_do_method(node->get_parent(), "remove_child", node);
			undo->add_undo_method(node->get_parent(), "add_child", node, true);
			undo->add_undo_method(node->get_parent(), "move_child", node, node->get_index());
			undo->add_undo_method(node, "set_owner", root);
			for (Node *selected : editor->get_selection()->get_full_selected_node_list()) {
				undo->add_undo_method(editor->get_selection(), "add_node", selected);
			}
			undo->add_undo_reference(node);
		}
		if (action == "scene_rename_node" || reparent || action == "scene_delete_node") {
			// Use the same NodePath and animation-track maintenance as the native
			// scene tree, in this exact undo transaction.
			HashMap<Node *, NodePath> path_renames;
			SceneTreeDock *tree_dock = SceneTreeDock::get_singleton();
			if (action == "scene_rename_node") {
				const String new_path = String(node->get_parent()->get_path()).path_join(String(p_args["name"]));
				LocalVector<Node *> descendants;
				descendants.push_back(node);
				while (!descendants.is_empty()) {
					Node *child = descendants[descendants.size() - 1];
					descendants.remove_at(descendants.size() - 1);
					path_renames[child] = child == node ? NodePath(new_path) : NodePath(new_path.path_join(String(node->get_path_to(child))));
					for (int i = 0; i < child->get_child_count(); i++) {
						descendants.push_back(child->get_child(i));
					}
				}
			} else {
				tree_dock->fill_path_renames(node, reparent ? new_parent : nullptr, &path_renames);
			}
			tree_dock->perform_node_renames(root, &path_renames);
		}
		undo->commit_action();
	}
	r["ok"] = true;
	r["saved"] = false;
	return r;
}
