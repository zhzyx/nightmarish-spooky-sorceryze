/**************************************************************************/
/*  ai_chat_editor_scene_actions.cpp                                      */
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
#include "core/io/resource_loader.h"
#include "core/io/resource_uid.h"
#include "core/math/math_funcs.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/script_language.h"
#include "core/object/undo_redo.h"
#include "editor/docks/ai_chat_editor_scene_completion.h"
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

// UndoRedo skips callables without an associated ObjectID. A private,
// reference-counted receiver keeps the fixed native setter alive in history;
// its API is deliberately never registered or exposed to scripts/tools.
class NativePropertySetter : public RefCounted {
	ObjectID target;

public:
	bool succeeded = false;
	explicit NativePropertySetter(ObjectID p_target) : target(p_target) {}
	void apply(StringName p_property, Variant p_value) {
		succeeded = false;
		Object *object = ObjectDB::get_instance(target);
		ERR_FAIL_NULL(object);
		bool valid = false;
		object->set_native(p_property, p_value, &valid);
		ERR_FAIL_COND(!valid);
		object = ObjectDB::get_instance(target);
		if (!object) {
			return;
		}
		Variant actual;
		succeeded = object->get_native(p_property, actual) && actual == p_value;
		ERR_FAIL_COND(!succeeded);
		object->set_edited(true);
	}
};

// One closed receiver per native operation. UndoRedo retains it strongly and
// resolves every scene object from ObjectID again on do, undo and redo.
class NativeSceneMutation : public RefCounted {
public:
	enum Kind { NAME,
		REPARENT,
		ADD_CHILD,
		REMOVE_CHILD,
		MOVE_CHILD,
		OWNER,
		CONNECT,
		DISCONNECT,
		SELECTION_CLEAR,
		SELECTION_ADD,
		SELECTION_REMOVE };
	Kind kind;
	ObjectID target, other;
	Variant value;
	Callable connection;
	uint32_t flags = 0;
	bool succeeded = false;
	NativeSceneMutation(Kind p_kind, Object *p_target, Object *p_other = nullptr, Variant p_value = Variant(), Callable p_connection = Callable(), uint32_t p_flags = 0) : kind(p_kind), target(p_target->get_instance_id()), other(p_other ? p_other->get_instance_id() : ObjectID()), value(p_value), connection(p_connection), flags(p_flags) {}
	void apply() {
		succeeded = false;
		Object *object = ObjectDB::get_instance(target);
		if (!object) {
			return;
		}
		if (kind >= SELECTION_CLEAR) {
			EditorSelection *selection = Object::cast_to<EditorSelection>(object);
			Node *node = Object::cast_to<Node>(ObjectDB::get_instance(other));
			if (!selection) {
				return;
			}
			if (kind == SELECTION_CLEAR) {
				selection->clear();
				succeeded = selection->get_full_selected_node_list().is_empty();
			} else if (node && kind == SELECTION_ADD) {
				selection->add_node(node);
				succeeded = selection->is_selected(node);
			} else if (node) {
				selection->remove_node(node);
				succeeded = !selection->is_selected(node);
			}
			return;
		}
		Node *node = Object::cast_to<Node>(object);
		Node *peer = Object::cast_to<Node>(ObjectDB::get_instance(other));
		if (!node) {
			return;
		}
		switch (kind) {
			case NAME:
				node->set_name(value);
				break;
			case REPARENT:
				if (peer) {
					node->reparent(peer, false);
				}
				break;
			case ADD_CHILD:
				if (peer) {
					node->add_child(peer, true);
				}
				break;
			case REMOVE_CHILD:
				if (peer) {
					node->remove_child(peer);
				}
				break;
			case MOVE_CHILD:
				if (peer) {
					node->move_child(peer, int(value));
				}
				break;
			case OWNER:
				node->set_owner(peer);
				break;
			case CONNECT:
				node->connect(StringName(String(value)), connection, flags);
				break;
			case DISCONNECT:
				node->disconnect(StringName(String(value)), connection);
				break;
			default:
				return;
		}
		// Notifications may run tool scripts and destroy or change either object.
		node = Object::cast_to<Node>(ObjectDB::get_instance(target));
		peer = Object::cast_to<Node>(ObjectDB::get_instance(other));
		if (!node) {
			return;
		}
		switch (kind) {
			case NAME:
				succeeded = node->get_name() == StringName(String(value));
				break;
			case REPARENT:
				succeeded = peer && node->get_parent() == peer;
				break;
			case ADD_CHILD:
				succeeded = peer && peer->get_parent() == node;
				break;
			case REMOVE_CHILD:
				succeeded = peer && peer->get_parent() != node;
				break;
			case MOVE_CHILD:
				succeeded = peer && peer->get_parent() == node && peer->get_index() == int(value);
				break;
			case OWNER:
				succeeded = node->get_owner() == peer;
				break;
			case CONNECT:
				succeeded = node->is_connected(StringName(String(value)), connection);
				break;
			case DISCONNECT:
				succeeded = !node->is_connected(StringName(String(value)), connection);
				break;
			default:
				break;
		}
	}
};

class NativeHistoryEpoch : public RefCounted {
public:
	uint64_t epoch = 0;
	void changed() { ++epoch; }
};

bool editable(Node *p_root, Node *p_node, bool p_structure) {
	if (p_node->is_internal() || ClassDB::is_gdextension(p_node->get_class()) || p_node->is_extension_placeholder() || ClassDB::get_api_type(p_node->get_class()) != ClassDB::API_CORE) {
		return false;
	}
	if (p_node != p_root && p_node->get_owner() != p_root) {
		if (p_structure || !p_root->is_editable_instance(p_node->get_owner())) {
			return false;
		}
	}
	return !p_structure || p_node == p_root || p_root->get_scene_inherited_state().is_null() || p_root->get_scene_inherited_state()->find_node_by_path(p_root->get_path_to(p_node)) < 0;
}

// Script storage references cannot be traversed through Object::get/set without
// running user getters/setters. Inspect only native script declaration metadata
// and reject this entire structural scope before constructing any transaction.
bool script_reference_scope(Node *p_root) {
	LocalVector<Node *> pending;
	pending.push_back(p_root);
	int count = 0;
	while (!pending.is_empty()) {
		Node *node = pending[pending.size() - 1];
		pending.remove_at(pending.size() - 1);
		if (++count > 100) {
			return false;
		}
		Ref<Script> script = node->get_script();
		if (script.is_valid()) {
			if (script->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(script->get_class()) || script->is_extension_placeholder() || ClassDB::get_api_type(script->get_class()) != ClassDB::API_CORE) {
				return false;
			}
			List<PropertyInfo> properties;
			script->get_script_property_list(&properties);
			if (properties.size() > 256) {
				return false;
			}
			for (const PropertyInfo &property : properties) {
				if (!(property.usage & PROPERTY_USAGE_STORAGE)) {
					continue;
				}
				if (property.type == Variant::NODE_PATH || property.type == Variant::ARRAY || property.type == Variant::DICTIONARY || property.type == Variant::OBJECT || property.type == Variant::NIL) {
					return false;
				}
			}
		}
		for (int i = 0; i < node->get_child_count(); i++) {
			pending.push_back(node->get_child(i));
		}
	}
	return true;
}

bool metadata_without_references(const Variant &p_value, int &r_count, int p_depth = 0) {
	if (p_depth > 12 || ++r_count > 1024) {
		return false;
	}
	switch (p_value.get_type()) {
		case Variant::NODE_PATH:
		case Variant::CALLABLE:
		case Variant::SIGNAL:
			return false;
		case Variant::OBJECT:
			return p_value.get_validated_object() == nullptr;
		case Variant::ARRAY: {
			const Array array = p_value;
			if (array.size() > 256) {
				return false;
			}
			for (const Variant &item : array) {
				if (!metadata_without_references(item, r_count, p_depth + 1)) {
					return false;
				}
			}
		} break;
		case Variant::DICTIONARY: {
			const Dictionary dictionary = p_value;
			if (dictionary.size() > 256) {
				return false;
			}
			for (int i = 0; i < dictionary.size(); i++) {
				if (!metadata_without_references(dictionary.get_key_at_index(i), r_count, p_depth + 1) || !metadata_without_references(dictionary.get_value_at_index(i), r_count, p_depth + 1)) {
					return false;
				}
			}
		} break;
		default:
			break;
	}
	return true;
}

// Native metadata is not in ClassDB's property list. Do not silently leave its
// dynamic references stale, or route it through generic Object::get/set.
bool metadata_reference_scope(Node *p_root) {
	LocalVector<Node *> pending;
	pending.push_back(p_root);
	int nodes = 0, values = 0;
	while (!pending.is_empty()) {
		Node *node = pending[pending.size() - 1];
		pending.remove_at(pending.size() - 1);
		if (++nodes > 100) {
			return false;
		}
		List<StringName> metadata;
		node->get_meta_list(&metadata);
		if (metadata.size() > 256) {
			return false;
		}
		for (const StringName &key : metadata) {
			if (!metadata_without_references(node->get_meta(key), values)) {
				return false;
			}
		}
		for (int i = 0; i < node->get_child_count(); i++) {
			pending.push_back(node->get_child(i));
		}
	}
	return true;
}

bool source_state(const String &p_path, Dictionary &r_state) {
	if (p_path.is_empty()) {
		return true;
	}
	const String file = p_path.get_slice("::", 0);
	if (!AIChatEditorSceneActions::valid_project_path(file) || !AIChatEditorSceneCompletion::unlinked(file) || !FileAccess::exists(file)) {
		return false;
	}
	r_state[file] = FileAccess::get_sha256(file);
	return true;
}

bool scene_snapshot(Node *p_root, Array &r_nodes, bool p_for_run = false) {
	LocalVector<Node *> pending;
	pending.push_back(p_root);
	while (!pending.is_empty()) {
		Node *n = pending[pending.size() - 1];
		pending.remove_at(pending.size() - 1);
		// Native classes with attached scripts remain editable; previews never
		// invoke script getters, property-list callbacks, loaders or methods.
		if (r_nodes.size() >= 100 || (!p_for_run && (ClassDB::is_gdextension(n->get_class()) || n->is_extension_placeholder() || ClassDB::get_api_type(n->get_class()) != ClassDB::API_CORE || n->get_child_count(true) != n->get_child_count(false)))) {
			return false;
		}
		Dictionary entry;
		entry["instance"] = int64_t(n->get_instance_id());
		entry["path"] = String(p_root->get_path_to(n));
		entry["class"] = n->get_class();
		entry["parent"] = n->get_parent() ? int64_t(n->get_parent()->get_instance_id()) : 0;
		entry["owner"] = n->get_owner() ? int64_t(n->get_owner()->get_instance_id()) : 0;
		entry["index"] = n->get_index();
		Dictionary sources;
		if (!source_state(n->get_scene_file_path(), sources)) {
			return false;
		}
		Ref<Script> script = n->get_script();
		int depth = 0;
		Array scripts;
		while (script.is_valid()) {
			if (++depth > 16 || script->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(script->get_class()) || script->is_extension_placeholder() || ClassDB::get_api_type(script->get_class()) != ClassDB::API_CORE || !source_state(script->get_path(), sources)) {
				return false;
			}
			Dictionary script_state;
			script_state["instance"] = String::num_uint64(uint64_t(script->get_instance_id()));
			script_state["version"] = int64_t(script->get_edited_version());
			scripts.push_back(script_state);
			script = script->get_base_script();
		}
		Ref<SceneState> inherited = n->get_scene_inherited_state();
		if (inherited.is_valid() && !source_state(inherited->get_path(), sources)) {
			return false;
		}
		entry["scripts"] = scripts;
		entry["sources"] = sources;
		entry["editable_instance"] = n != p_root && p_root->is_editable_instance(n);
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

Dictionary AIChatEditorSceneActions::history_state(Node *p_root) {
	Dictionary state;
	EditorUndoRedoManager *manager = EditorUndoRedoManager::get_singleton();
	if (!p_root || !manager) {
		return state;
	}
	const int id = manager->get_history_id_for_object(p_root);
	UndoRedo *history = manager->has_history(id) ? manager->get_history_undo_redo(id) : nullptr;
	if (!history) {
		return state;
	}
	// Histories own their observers through native metadata; the static map
	// holds only weak IDs and never destroys RefCounteds after ObjectDB teardown.
	static HashMap<ObjectID, ObjectID> observers;
	Vector<ObjectID> dead;
	for (const KeyValue<ObjectID, ObjectID> &entry : observers) {
		if (!ObjectDB::get_instance(entry.key) || !ObjectDB::get_instance(entry.value)) {
			dead.push_back(entry.key);
		}
	}
	for (const ObjectID &object : dead) {
		observers.erase(object);
	}
	const ObjectID object = history->get_instance_id();
	if (!observers.has(object)) {
		if (observers.size() >= 128) {
			state["unavailable"] = true;
			return state;
		}
		Ref<NativeHistoryEpoch> observer;
		observer.instantiate();
		history->connect(SNAME("version_changed"), callable_mp(observer.ptr(), &NativeHistoryEpoch::changed));
		history->set_meta(SNAME("_ai_chat_native_history_epoch"), observer);
		observers[object] = observer->get_instance_id();
	}
	state["instance"] = String::num_uint64(uint64_t(object));
	NativeHistoryEpoch *observer = static_cast<NativeHistoryEpoch *>(ObjectDB::get_instance(observers[object]));
	state["observer"] = String::num_uint64(uint64_t(observers[object]));
	state["epoch"] = String::num_uint64(observer->epoch);
	state["version"] = String::num_uint64(history->get_version());
	return state;
}

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
	return AIChatEditorSceneCompletion::supports(p_action) || p_action == "scene_disconnect_signal" || p_action == "scene_create_node" || p_action == "scene_delete_node" || p_action == "scene_rename_node" || p_action == "scene_reparent_node" || p_action == "scene_select_nodes" || p_action == "scene_set_property" || p_action == "scene_assign_resource" || p_action == "scene_connect_signal" || p_action == "run_project" || p_action == "run_scene" || p_action == "stop_project";
}

Dictionary AIChatEditorSceneActions::perform(const Dictionary &p_args, bool p_confirmed) {
	if (!json_value(p_args) || JSON::stringify(p_args).utf8().length() > 32768 || p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return outcome(false, "invalid_scene_arguments");
	}
	const String action = p_args["action"];
	if (!supports(action)) {
		return outcome(false, "unknown_action");
	}
	if (AIChatEditorSceneCompletion::supports(action)) {
		return AIChatEditorSceneCompletion::perform(p_args, p_confirmed);
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
	const Variant target_arg = p_args.get("target", ".");
	if (action != "run_scene" && !node_path(target_arg)) {
		return outcome(false, "invalid_node_path");
	}
	const String target = target_arg;
	const bool resource = action == "scene_assign_resource", signal = action == "scene_connect_signal" || action == "scene_disconnect_signal";
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
	if (signal && (!node_path(p_args.get("receiver", Variant())) || p_args.get("signal", Variant()).get_type() != Variant::STRING || p_args.get("method", Variant()).get_type() != Variant::STRING)) {
		return outcome(false, "invalid_signal_arguments");
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
		state["history"] = history_state(root);
		if (Dictionary(state["history"]).has("unavailable")) {
			return outcome(false, "history_snapshot_capacity");
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
	state["history"] = history_state(root);
	if (Dictionary(state["history"]).has("unavailable")) {
		return outcome(false, "history_snapshot_capacity");
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
	if ((action == "scene_delete_node" || reparent || action == "scene_rename_node") && node == root) {
		return outcome(false, "protected_scene_root");
	}
	if ((action == "scene_rename_node" || reparent || action == "scene_delete_node") && !SceneTreeDock::get_singleton()) {
		return outcome(false, "scene_tree_unavailable");
	}
	const bool structure = action == "scene_delete_node" || reparent || action == "scene_rename_node";
	if (structure && !script_reference_scope(root)) {
		return outcome(false, "unsafe_script_reference_scope");
	}
	if (structure && !metadata_reference_scope(root)) {
		return outcome(false, "unsafe_metadata_reference_scope");
	}
	if (!stop && !select && (!editable(root, node, structure) || (reparent && !editable(root, new_parent, false)))) {
		return outcome(false, structure ? "inherited_or_foreign_structure" : "instance_children_not_editable");
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
		ClassDB::get_property_list(node->get_class(), &properties);
		bool found = false;
		for (const PropertyInfo &info : properties) {
			if (info.name == property_name && (info.usage & PROPERTY_USAGE_EDITOR) && !(info.usage & PROPERTY_USAGE_READ_ONLY)) {
				bool valid = false;
				node->get_native(property_name, previous, &valid);
				if (!valid) {
					return outcome(false, "property_unavailable");
				}
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
	Ref<Resource> assigned;
	Dictionary assigned_content;
	if (resource) {
		property_name = p_args.get("property", "");
		const bool allowed = (property_name == "texture" && (node->is_class("Sprite2D") || node->is_class("TextureRect"))) || (property_name == "material_override" && node->is_class("GeometryInstance3D")) || (property_name == "mesh" && node->is_class("MeshInstance3D")) || (property_name == "gradient" && node->is_class("Line2D"));
		if (!allowed || !node->get_native(property_name, previous)) {
			return outcome(false, "unsupported_resource_property");
		}
		Ref<Resource> old = previous;
		Dictionary old_resource;
		old_resource["instance"] = old.is_valid() ? String::num_uint64(uint64_t(old->get_instance_id())) : String();
		old_resource["version"] = old.is_valid() ? int64_t(old->get_edited_version()) : 0;
		if (old.is_valid() && !source_state(old->get_path(), old_resource)) {
			return outcome(false, "invalid_resource_source");
		}
		if (!AIChatEditorSceneCompletion::resource_snapshot(old, old_resource)) {
			return outcome(false, "unsupported_old_resource_snapshot");
		}
		state["resource"] = old_resource;
		Dictionary input;
		const String path = p_args["resource_path"];
		if (!AIChatEditorSceneCompletion::resource_input(path, input)) {
			return outcome(false, "unsupported_resource_input");
		}
		Ref<Resource> cached = ResourceCache::get_ref(path);
		if (cached.is_valid()) {
			Dictionary cached_content;
			if (!AIChatEditorSceneCompletion::resource_snapshot(cached, cached_content)) {
				return outcome(false, "unsupported_cached_resource_snapshot");
			}
			state["cached_resource_content"] = cached_content;
		}
		state["resource_input"] = input;
	}
	Node *receiver = nullptr;
	Callable connection;
	uint32_t connection_flags = 0;
	if (signal) {
		if (!node_path(p_args.get("receiver", Variant())) || p_args.get("signal", Variant()).get_type() != Variant::STRING || p_args.get("method", Variant()).get_type() != Variant::STRING) {
			return outcome(false, "invalid_signal_arguments");
		}
		receiver = root->get_node_or_null(NodePath(String(p_args["receiver"])));
		const StringName signal_name = String(p_args["signal"]), method = String(p_args["method"]);
		if (!receiver || !editable(root, receiver, false) || !node->has_signal(signal_name) || !receiver->has_method(method)) {
			return outcome(false, "signal_or_receiver_unavailable");
		}
		connection = Callable(receiver, method);
		List<Object::Connection> connections;
		node->get_signal_connection_list(signal_name, &connections);
		for (const Object::Connection &existing : connections) {
			if (existing.callable == connection) {
				connection_flags = existing.flags;
			}
		}
		const bool connected = node->is_connected(signal_name, connection);
		if ((action == "scene_connect_signal" && connected) || (action == "scene_disconnect_signal" && (!connected || !(connection_flags & Object::CONNECT_PERSIST) || (connection_flags & Object::CONNECT_INHERITED)))) {
			return outcome(false, "connection_exists_or_not_editable");
		}
		state["receiver_instance"] = int64_t(receiver->get_instance_id());
		state["connected"] = connected;
		state["connection_flags"] = int64_t(connection_flags);
	}
	if (JSON::stringify(state).utf8().length() > 16384 || !json_value(state)) {
		return outcome(false, "scene_snapshot_capacity");
	}
	Dictionary r = outcome(false);
	r["action"] = action;
	r["target"] = target;
	r["target_instance"] = instance;
	r["old_value"] = state;
	r["manual_confirmation_required"] = true;
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
		// Resource loading can have importer/loader side effects. It is never
		// performed while proposing or before the exact snapshot is confirmed.
		if (resource) {
			Error error = OK;
			assigned = ResourceLoader::load(p_args["resource_path"], "", ResourceFormatLoader::CACHE_MODE_REUSE, &error);
			const bool type_ok = assigned.is_valid() && ((property_name == "texture" && assigned->is_class("Texture2D")) || (property_name == "gradient" && assigned->is_class("Gradient")) || (property_name == "material_override" && assigned->is_class("Material")) || (property_name == "mesh" && assigned->is_class("Mesh")));
			if (error != OK || !type_ok || assigned->get_script().get_type() != Variant::NIL || ClassDB::is_gdextension(assigned->get_class()) || assigned->is_extension_placeholder() || ClassDB::get_api_type(assigned->get_class()) != ClassDB::API_CORE) {
				return outcome(false, "resource_load_or_type_failed");
			}
			if (!AIChatEditorSceneCompletion::resource_snapshot(assigned, assigned_content)) {
				return outcome(false, "unsupported_loaded_resource_snapshot");
			}
			// A custom loader may synchronously edit or destroy scene objects.
			// Resolve identities again before touching any pre-load raw pointer,
			// then rebuild the same pure proposal (including hashes and history).
			EditorInterface *current_editor = EditorInterface::get_singleton();
			Node *current_root = current_editor ? current_editor->get_edited_scene_root() : nullptr;
			Node *current_node = Object::cast_to<Node>(ObjectDB::get_instance(ObjectID(uint64_t(instance))));
			if (!current_root || int64_t(current_root->get_instance_id()) != int64_t(state["root"]) || !current_node || current_root->get_node_or_null(NodePath(target)) != current_node) {
				return outcome(false, "scene_changed_during_resource_load");
			}
			const Dictionary refreshed = perform(p_args, false);
			Dictionary refreshed_state = refreshed.get("old_value", Dictionary());
			if (!state.has("cached_resource_content")) {
				refreshed_state.erase("cached_resource_content");
			}
			if (!refreshed.get("confirmation_required", false) || !same_json(refreshed_state, state) || EditorUndoRedoManager::get_singleton() != undo || undo->is_committing_action()) {
				return outcome(false, "scene_changed_during_resource_load");
			}
			editor = current_editor;
			root = current_root;
			node = current_node;
			value = assigned;
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
		UndoRedo *native_history = undo->get_history_undo_redo(undo->get_history_id_for_object(root));
		Vector<Ref<NativeSceneMutation>> mutations;
		Ref<NativePropertySetter> property_setter;
		auto native = [&](bool p_do, NativeSceneMutation::Kind p_kind, Object *p_target, Object *p_other = nullptr, Variant p_value = Variant(), Callable p_connection = Callable(), uint32_t p_flags = 0) {
			Ref<NativeSceneMutation> receiver = memnew(NativeSceneMutation(p_kind, p_target, p_other, p_value, p_connection, p_flags));
			Callable callable = callable_mp(receiver.ptr(), &NativeSceneMutation::apply);
			if (p_do) {
				native_history->add_do_method(callable);
				mutations.push_back(receiver);
			} else {
				native_history->add_undo_method(callable);
			}
		};

		if (select) {
			EditorSelection *selection = editor->get_selection();
			native(true, NativeSceneMutation::SELECTION_CLEAR, selection);
			native(false, NativeSceneMutation::SELECTION_CLEAR, selection);
			for (Node *selected : selected_nodes) {
				native(true, NativeSceneMutation::SELECTION_ADD, selection, selected);
			}
			for (Node *selected : selection->get_full_selected_node_list()) {
				native(false, NativeSceneMutation::SELECTION_ADD, selection, selected);
			}
		} else if (create) {
			native(true, NativeSceneMutation::ADD_CHILD, node, created);
			native(true, NativeSceneMutation::OWNER, created, root);
			native(false, NativeSceneMutation::REMOVE_CHILD, node, created);
			undo->add_do_reference(created);
		} else if (property || resource) {
			UndoRedo *history = undo->get_history_undo_redo(undo->get_history_id_for_object(root));
			Ref<NativePropertySetter> setter = memnew(NativePropertySetter(node->get_instance_id()));
			property_setter = setter;
			history->add_do_method(callable_mp(setter.ptr(), &NativePropertySetter::apply).bind(StringName(property_name), value));
			history->add_undo_method(callable_mp(setter.ptr(), &NativePropertySetter::apply).bind(StringName(property_name), previous));
		} else if (signal) {
			const StringName name = String(p_args["signal"]);
			if (action == "scene_connect_signal") {
				native(true, NativeSceneMutation::CONNECT, node, nullptr, String(name), connection, Object::CONNECT_PERSIST);
				native(false, NativeSceneMutation::DISCONNECT, node, nullptr, String(name), connection);
			} else {
				native(true, NativeSceneMutation::DISCONNECT, node, nullptr, String(name), connection);
				native(false, NativeSceneMutation::CONNECT, node, nullptr, String(name), connection, connection_flags);
			}
		} else if (action == "scene_rename_node") {
			native(true, NativeSceneMutation::NAME, node, nullptr, p_args["name"]);
			native(false, NativeSceneMutation::NAME, node, nullptr, String(node->get_name()));
		} else if (reparent) {
			native(true, NativeSceneMutation::REPARENT, node, new_parent);
			native(false, NativeSceneMutation::REPARENT, node, node->get_parent());
			native(false, NativeSceneMutation::MOVE_CHILD, node->get_parent(), node, node->get_index());
		} else if (action == "scene_delete_node") {
			native(true, NativeSceneMutation::SELECTION_REMOVE, editor->get_selection(), node);
			native(true, NativeSceneMutation::REMOVE_CHILD, node->get_parent(), node);
			native(false, NativeSceneMutation::ADD_CHILD, node->get_parent(), node);
			native(false, NativeSceneMutation::MOVE_CHILD, node->get_parent(), node, node->get_index());
			for (Node *selected : editor->get_selection()->get_full_selected_node_list()) {
				native(false, NativeSceneMutation::SELECTION_ADD, editor->get_selection(), selected);
			}
			undo->add_undo_reference(node);
		}
		if (reparent || action == "scene_delete_node") {
			LocalVector<Node *> descendants;
			descendants.push_back(node);
			while (!descendants.is_empty()) {
				Node *child = descendants[descendants.size() - 1];
				descendants.remove_at(descendants.size() - 1);
				Node *owner = child->get_owner();
				if (owner) {
					if (reparent) {
						native(true, NativeSceneMutation::OWNER, child, owner);
					}
					native(false, NativeSceneMutation::OWNER, child, owner);
				}
				for (int i = 0; i < child->get_child_count(); i++) {
					descendants.push_back(child->get_child(i));
				}
			}
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
			tree_dock->perform_node_renames(root, &path_renames, nullptr, nullptr, true);
		}
		undo->commit_action();
		if (resource) {
			Dictionary actual_content;
			if (!AIChatEditorSceneCompletion::resource_snapshot(assigned, actual_content) || !same_json(assigned_content, actual_content)) {
				return outcome(false, "resource_changed_during_assignment");
			}
		}
		if (property_setter.is_valid() && !property_setter->succeeded) {
			return outcome(false, "native_mutation_result_mismatch");
		}
		for (const Ref<NativeSceneMutation> &mutation : mutations) {
			if (!mutation->succeeded) {
				return outcome(false, "native_mutation_result_mismatch");
			}
		}
	}
	r["ok"] = true;
	r["saved"] = false;
	return r;
}
