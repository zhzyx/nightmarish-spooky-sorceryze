/**************************************************************************/
/*  ai_chat_editor_spatial_actions.cpp                                    */
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

#include "ai_chat_editor_spatial_actions.h"

#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/object/undo_redo.h"
#include "editor/animation/animation_player_editor_plugin.h"
#include "editor/animation/animation_track_editor.h"
#include "editor/docks/ai_chat_editor_scene_actions.h"
#include "editor/editor_data.h"
#include "editor/editor_interface.h"
#include "editor/editor_undo_redo_manager.h"
#include "editor/scene/3d/node_3d_editor_plugin.h"
#include "editor/scene/3d/node_3d_editor_viewport.h"
#include "editor/scene/canvas_item_editor_plugin.h"
#include "scene/2d/physics/collision_polygon_2d.h"
#include "scene/2d/polygon_2d.h"
#include "scene/3d/camera_3d.h"
#include "scene/3d/mesh_instance_3d.h"
#include "scene/animation/animation_player.h"
#include "scene/resources/animation.h"
#include "scene/resources/packed_scene.h"

#include "modules/modules_enabled.gen.h"
#ifdef MODULE_TILEMAP_ENABLED
#include "modules/tilemap/tile_map_layer.h"
#include "modules/tilemap/tile_set.h"
#endif

namespace {
Dictionary failure(const String &p_error) {
	Dictionary result;
	result["ok"] = false;
	result["error"] = p_error;
	return result;
}
bool number(const Variant &p_value, double p_min = -1000000.0, double p_max = 1000000.0) {
	return p_value.is_num() && Math::is_finite(double(p_value)) && double(p_value) >= p_min && double(p_value) <= p_max;
}
bool integer(const Variant &p_value, int p_min, int p_max) {
	return number(p_value, p_min, p_max) && double(p_value) == Math::floor(double(p_value));
}
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
// Camera setters store real_t. Quantization is tolerated only in the result
// check; the confirmation snapshot above remains an exact JSON comparison.
bool same_camera_value(const Variant &p_a, const Variant &p_b) {
	if (p_a.is_num() && p_b.is_num()) {
		return Math::is_finite(double(p_a)) && Math::is_finite(double(p_b)) && Math::is_equal_approx(double(p_a), double(p_b));
	}
	if (p_a.get_type() == Variant::ARRAY && p_b.get_type() == Variant::ARRAY) {
		const Array a = p_a, b = p_b;
		if (a.size() != b.size()) {
			return false;
		}
		for (int i = 0; i < a.size(); i++) {
			if (!same_camera_value(a[i], b[i])) {
				return false;
			}
		}
		return true;
	}
	return p_a == p_b;
}
bool native(Object *p_object) {
	return p_object && p_object->get_script().get_type() == Variant::NIL && !p_object->is_extension_placeholder() && !ClassDB::is_gdextension(p_object->get_class()) && ClassDB::get_api_type(p_object->get_class()) == ClassDB::API_CORE;
}
// No relative traversal, subnames or external resources. The host supplies the
// edited scene root; absolute paths and arbitrary ObjectIDs cannot select data.
bool node_path(const Variant &p_value) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String path = p_value;
	if (path.is_empty() || path.length() > 1024 || path.contains(":") || path.contains("\\") || path.contains_char(0) || path.begins_with("/")) {
		return false;
	}
	for (const String &part : path.split("/")) {
		if (part.is_empty() || part == ".." || (part == "." && path != ".")) {
			return false;
		}
	}
	return true;
}
bool local_node(Node *p_root, Node *p_node) {
	if (!p_root || !p_node || (p_node != p_root && (p_node->get_owner() != p_root || !p_root->is_ancestor_of(p_node)))) {
		return false;
	}
	for (Node *node = p_node; node; node = node->get_parent()) {
		if (!native(node) || node->is_internal()) {
			return false;
		}
		if (node == p_root) {
			return true;
		}
	}
	return false;
}
Variant wire(const Variant &p_value) {
	Array result;
	if (p_value.get_type() == Variant::VECTOR2) {
		Vector2 value = p_value;
		result.push_back(value.x);
		result.push_back(value.y);
	} else if (p_value.get_type() == Variant::VECTOR2I) {
		Vector2i value = p_value;
		result.push_back(value.x);
		result.push_back(value.y);
	} else if (p_value.get_type() == Variant::VECTOR3) {
		Vector3 value = p_value;
		result.push_back(value.x);
		result.push_back(value.y);
		result.push_back(value.z);
	} else if (p_value.get_type() == Variant::QUATERNION) {
		Quaternion value = p_value;
		result.push_back(value.x);
		result.push_back(value.y);
		result.push_back(value.z);
		result.push_back(value.w);
	} else if (p_value.get_type() == Variant::TRANSFORM3D) {
		Transform3D transform = p_value;
		for (int i = 0; i < 3; i++) {
			result.push_back(wire(transform.basis.get_column(i)));
		}
		result.push_back(wire(transform.origin));
	} else if (p_value.get_type() == Variant::PACKED_VECTOR2_ARRAY) {
		PackedVector2Array points = p_value;
		for (const Vector2 &point : points) {
			result.push_back(wire(point));
		}
	} else {
		return p_value;
	}
	return result;
}
bool scalar(const Variant &p_value) {
	return p_value.get_type() == Variant::BOOL || number(p_value);
}
bool key_value(Animation::TrackType p_type, const Variant &p_value, Variant &r_value) {
	if (p_type == Animation::TYPE_VALUE || p_type == Animation::TYPE_BLEND_SHAPE) {
		if (!scalar(p_value) || (p_type == Animation::TYPE_BLEND_SHAPE && !number(p_value))) {
			return false;
		}
		r_value = p_value;
		return true;
	}
	if (p_type == Animation::TYPE_ROTATION_3D) {
		if (p_value.get_type() != Variant::ARRAY || Array(p_value).size() != 4) {
			return false;
		}
		Array components = p_value;
		for (const Variant &component : components) {
			if (!number(component, -1, 1)) {
				return false;
			}
		}
		Quaternion quaternion(components[0], components[1], components[2], components[3]);
		if (!quaternion.is_normalized()) {
			return false;
		}
		r_value = quaternion;
		return true;
	}
	return AIChatEditorSceneActions::convert_json_value(p_value, Variant::VECTOR3, r_value);
}
bool animation_snapshot(const Ref<Animation> &p_animation, Dictionary &r_state) {
	if (!native(p_animation.ptr()) || p_animation->get_track_count() > 64 || !number(p_animation->get_length(), 0.001, 1000000) || !number(p_animation->get_step(), 0, 1000000)) {
		return false;
	}
	r_state["resource_instance"] = String::num_uint64(uint64_t(p_animation->get_instance_id()));
	r_state["length"] = p_animation->get_length();
	r_state["loop"] = p_animation->get_loop_mode();
	r_state["step"] = p_animation->get_step();
	Array tracks;
	int total_keys = 0;
	for (int track = 0; track < p_animation->get_track_count(); track++) {
		const Animation::TrackType type = p_animation->track_get_type(track);
		if (p_animation->track_is_compressed(track) || type > Animation::TYPE_BLEND_SHAPE || (total_keys += p_animation->track_get_key_count(track)) > 256) {
			return false;
		}
		Dictionary row;
		row["type"] = int(type);
		row["path"] = String(p_animation->track_get_path(track));
		row["enabled"] = p_animation->track_is_enabled(track);
		row["imported"] = p_animation->track_is_imported(track);
		row["interpolation"] = int(p_animation->track_get_interpolation_type(track));
		row["wrap"] = p_animation->track_get_interpolation_loop_wrap(track);
		if (type == Animation::TYPE_VALUE) {
			row["update_mode"] = int(p_animation->value_track_get_update_mode(track));
		}
		Array keys;
		for (int key = 0; key < p_animation->track_get_key_count(track); key++) {
			const Variant value = p_animation->track_get_key_value(track, key);
			if ((type == Animation::TYPE_VALUE && !scalar(value)) || !number(p_animation->track_get_key_time(track, key), -1000000, 1000000) || !number(p_animation->track_get_key_transition(track, key))) {
				return false;
			}
			Dictionary entry;
			entry["time"] = p_animation->track_get_key_time(track, key);
			entry["transition"] = p_animation->track_get_key_transition(track, key);
			entry["value"] = wire(value);
			keys.push_back(entry);
		}
		row["keys"] = keys;
		tracks.push_back(row);
	}
	r_state["tracks"] = tracks;
	return JSON::stringify(r_state).utf8().length() <= 32768;
}
Ref<Animation> copy_animation(const Ref<Animation> &p_animation) {
	Ref<Animation> result;
	result.instantiate();
	result->set_length(p_animation->get_length());
	result->set_loop_mode(p_animation->get_loop_mode());
	result->set_step(p_animation->get_step());
	for (int track = 0; track < p_animation->get_track_count(); track++) {
		p_animation->copy_track(track, result);
	}
	return result;
}
class NativeSpatialResourceEpoch : public RefCounted {
public:
	uint64_t epoch = 0;
	void changed() { epoch++; }
};
Dictionary resource_identity(const Ref<Resource> &p_resource) {
	Dictionary result;
	EditorUndoRedoManager *manager = EditorUndoRedoManager::get_singleton();
	if (!manager) {
		result["unavailable"] = true;
		return result;
	}
	// Observers belong to the editor host, never to serializable scene data.
	// The weak identity map is pruned without static Ref teardown after ObjectDB.
	Dictionary retained = manager->get_meta(SNAME("_ai_chat_spatial_resource_observers"), Dictionary());
	static HashMap<ObjectID, ObjectID> observers;
	Vector<ObjectID> dead;
	for (const KeyValue<ObjectID, ObjectID> &entry : observers) {
		if (!ObjectDB::get_instance(entry.key) || !ObjectDB::get_instance(entry.value)) {
			dead.push_back(entry.key);
		}
	}
	for (ObjectID id : dead) {
		observers.erase(id);
		retained.erase(String::num_uint64(uint64_t(id)));
	}
	ObjectID id = p_resource->get_instance_id();
	if (!observers.has(id)) {
		if (observers.size() >= 256) {
			result["unavailable"] = true;
			return result;
		}
		Ref<NativeSpatialResourceEpoch> observer;
		observer.instantiate();
		p_resource->connect(SNAME("changed"), callable_mp(observer.ptr(), &NativeSpatialResourceEpoch::changed));
		retained[String::num_uint64(uint64_t(id))] = observer;
		observers[id] = observer->get_instance_id();
	}
	manager->set_meta(SNAME("_ai_chat_spatial_resource_observers"), retained);
	NativeSpatialResourceEpoch *observer = static_cast<NativeSpatialResourceEpoch *>(ObjectDB::get_instance(observers[id]));
	result["instance"] = String::num_uint64(uint64_t(id));
	result["observer"] = String::num_uint64(uint64_t(observers[id]));
	result["epoch"] = String::num_uint64(observer->epoch);
	return result;
}
class NativeSpatialEdit : public RefCounted {
	ObjectID target;

public:
	bool succeeded = false;
	explicit NativeSpatialEdit(ObjectID p_target) : target(p_target) {}
	void transform(Transform3D p_transform) {
		succeeded = false;
		Node3D *node = ObjectDB::get_instance<Node3D>(target);
		if (!native(node)) {
			return;
		}
		node->set_global_transform(p_transform);
		node = ObjectDB::get_instance<Node3D>(target);
		succeeded = node && node->get_global_transform().is_equal_approx(p_transform);
	}
	void polygon(PackedVector2Array p_points) {
		Object *object = ObjectDB::get_instance(target);
		succeeded = false;
		if (Polygon2D *node = Object::cast_to<Polygon2D>(object)) {
			node->set_polygon(p_points);
			node = ObjectDB::get_instance<Polygon2D>(target);
			succeeded = node && node->get_polygon() == p_points;
		} else if (CollisionPolygon2D *collision_node = Object::cast_to<CollisionPolygon2D>(object)) {
			collision_node->set_polygon(p_points);
			collision_node = ObjectDB::get_instance<CollisionPolygon2D>(target);
			succeeded = collision_node && collision_node->get_polygon() == p_points;
		}
	}
	void animation(Ref<Animation> p_snapshot) {
		// Resource signals may synchronously release its last scene owner.
		// Keep the actual native target alive through every setter and readback.
		Ref<Animation> animation = Object::cast_to<Animation>(ObjectDB::get_instance(target));
		succeeded = false;
		if (animation.is_null() || !native(animation.ptr())) {
			return;
		}
		animation->clear();
		animation->set_length(p_snapshot->get_length());
		animation->set_loop_mode(p_snapshot->get_loop_mode());
		animation->set_step(p_snapshot->get_step());
		for (int track = 0; track < p_snapshot->get_track_count(); track++) {
			p_snapshot->copy_track(track, Ref<Animation>(animation));
		}
		Dictionary actual, expected;
		succeeded = animation_snapshot(Ref<Animation>(animation), actual) && animation_snapshot(p_snapshot, expected);
		actual.erase("resource_instance");
		expected.erase("resource_instance");
		succeeded = succeeded && same_json(actual, expected);
	}
#ifdef MODULE_TILEMAP_ENABLED
	void cells(Array p_cells) {
		TileMapLayer *layer = Object::cast_to<TileMapLayer>(ObjectDB::get_instance(target));
		succeeded = false;
		if (!layer || !native(layer)) {
			return;
		}
		for (const Variant &value : p_cells) {
			Dictionary cell = value;
			layer->set_cell(cell["coords"], cell["source_id"], cell["atlas_coords"], cell["alternative"]);
		}
		succeeded = true;
	}
#endif
};
Dictionary proposal(const Dictionary &p_args, Object *p_target, const Dictionary &p_state, bool p_confirmed, bool p_write) {
	Dictionary result;
	result["ok"] = !p_write;
	result["action"] = p_args["action"];
	result["target_instance"] = int64_t(p_target->get_instance_id());
	result["old_value"] = p_state;
	if (!p_write) {
		result["state"] = p_state;
		return result;
	}
	result["manual_confirmation_required"] = true;
	Dictionary requested = p_args.duplicate(true);
	requested.erase("expected_old_value");
	requested.erase("expected_target_instance");
	result["new_value"] = requested;
	if (!p_confirmed) {
		result["confirmation_required"] = true;
		return result;
	}
	// JSON transports numbers as doubles: compare numeric values and unordered keys, never coerce
	// string/bool/fractional instance IDs. The exact content binds the proposal.
	const Variant instance = p_args.get("expected_target_instance", Variant());
	if (!number(instance, 0, 9007199254740991.0) || double(instance) != Math::floor(double(instance)) || uint64_t(int64_t(instance)) != uint64_t(p_target->get_instance_id()) || p_args.get("expected_old_value", Variant()).get_type() != Variant::DICTIONARY || !same_json(p_args["expected_old_value"], p_state)) {
		return failure("spatial_changed_since_confirmation");
	}
	result["ok"] = true;
	return result;
}
} // namespace

bool AIChatEditorSpatialActions::supports(const String &p_action) {
	return p_action == "viewport_pick" || p_action == "viewport_selection_state" || p_action == "viewport_transform_selection" || p_action == "viewport_state" || p_action == "viewport_set_view" || p_action == "animation_state" || p_action == "animation_add_track" || p_action == "animation_remove_track" || p_action == "animation_insert_key" || p_action == "animation_remove_key" || p_action == "animation_move_key" || p_action == "animation_select_keys" || p_action == "animation_copy_keys" || p_action == "animation_cut_keys" || p_action == "animation_paste_keys" || p_action == "polygon_state" || p_action == "polygon_set_points" || p_action == "tilemap_state" || p_action == "tilemap_set_cells";
}

Dictionary AIChatEditorSpatialActions::perform(const Dictionary &p_args, bool p_confirmed) {
	if (p_args.get("action", Variant()).get_type() != Variant::STRING) {
		return failure("invalid_spatial_arguments");
	}
	const String action = p_args["action"];
	if (!supports(action) || JSON::stringify(p_args).utf8().length() > 65536) {
		return failure("invalid_spatial_arguments");
	}
	EditorInterface *editor = EditorInterface::get_singleton();
	Node *root = editor ? editor->get_edited_scene_root() : nullptr;
	if (!root) {
		return failure("no_edited_scene");
	}
	Dictionary state;
	state["scene_instance"] = String::num_uint64(uint64_t(root->get_instance_id()));
	state["scene_path"] = root->get_scene_file_path();
	state["history"] = AIChatEditorSceneActions::history_state(root);
	if (Dictionary(state["history"]).has("unavailable")) {
		return failure("history_snapshot_capacity");
	}
	if (action == "viewport_pick") {
		const Variant index = p_args.get("index", 0);
		Node3DEditor *spatial = Node3DEditor::get_singleton();
		if (!spatial || !integer(index, 0, 3) || p_args.get("value", Variant()).get_type() != Variant::DICTIONARY) {
			return failure("invalid_viewport_pick");
		}
		Node3DEditorViewport *viewport = spatial->get_editor_viewport(index);
		Dictionary value = p_args["value"];
		Variant converted_origin, converted_direction;
		const Variant distance = value.get("max_distance", 10000.0);
		if (!viewport || !AIChatEditorSceneActions::convert_json_value(value.get("origin", Variant()), Variant::VECTOR3, converted_origin) || !AIChatEditorSceneActions::convert_json_value(value.get("direction", Variant()), Variant::VECTOR3, converted_direction) || !number(distance, 0.001, 1000000)) {
			return failure("invalid_viewport_pick_ray");
		}
		const Vector3 origin = converted_origin, direction = converted_direction;
		if (!direction.is_normalized()) {
			return failure("pick_direction_must_be_normalized");
		}
		Vector<Node *> pending;
		pending.push_back(root);
		int examined = 0, triangles = 0;
		double nearest = distance;
		Dictionary hit;
		while (!pending.is_empty()) {
			Node *node = pending[pending.size() - 1];
			pending.remove_at(pending.size() - 1);
			if (++examined > 256 || !local_node(root, node)) {
				return failure("unsupported_pick_scene_or_capacity");
			}
			for (int i = 0; i < node->get_child_count(); i++) {
				pending.push_back(node->get_child(i));
			}
			MeshInstance3D *mesh_node = Object::cast_to<MeshInstance3D>(node);
			if (!mesh_node || !mesh_node->is_visible_in_tree()) {
				continue;
			}
			Ref<Mesh> mesh = mesh_node->get_mesh();
			if (!native(mesh.ptr()) || mesh_node->get_skin_reference().is_valid() || mesh_node->get_blend_shape_count() > 0 || mesh->get_surface_count() > 64) {
				return failure("unsupported_pick_mesh");
			}
			// Built-in triangle geometry only. No EditorNode3DGizmo virtual
			// intersection, plugin callback, physics world, or InputEvent.
			for (int surface = 0; surface < mesh->get_surface_count(); surface++) {
				if (mesh->surface_get_primitive_type(surface) != Mesh::PRIMITIVE_TRIANGLES || (triangles += MAX(mesh->surface_get_array_len(surface), mesh->surface_get_array_index_len(surface)) / 3) > 20000) {
					return failure("unsupported_pick_geometry_or_capacity");
				}
			}
			const Transform3D transform = mesh_node->get_global_transform();
			if (!transform.is_finite() || Math::is_zero_approx(transform.basis.determinant())) {
				return failure("invalid_pick_transform");
			}
			Ref<TriangleMesh> geometry = mesh->generate_triangle_mesh();
			if (geometry.is_null()) {
				return failure("pick_geometry_unavailable");
			}
			Transform3D inverse = transform.affine_inverse();
			Vector3 point, normal;
			int32_t surface = -1, face = -1;
			if (geometry->intersect_segment(inverse.xform(origin), inverse.xform(origin + direction * double(distance)), point, normal, &surface, &face)) {
				Vector3 world_point = transform.xform(point);
				const double hit_distance = origin.distance_to(world_point);
				if (hit_distance < nearest) {
					nearest = hit_distance;
					hit["target"] = String(root->get_path_to(node));
					hit["instance"] = String::num_uint64(uint64_t(node->get_instance_id()));
					hit["position"] = wire(world_point);
					hit["normal"] = wire(transform.basis.inverse().transposed().xform(normal).normalized());
					hit["distance"] = hit_distance;
					hit["surface"] = surface;
					hit["face"] = face;
				}
			}
		}
		state["camera"] = wire(viewport->get_camera_3d()->get_global_transform());
		state["viewport_instance"] = String::num_uint64(uint64_t(viewport->get_instance_id()));
		Dictionary result = proposal(p_args, viewport, state, false, false);
		result["hit"] = hit;
		result["hit_found"] = !hit.is_empty();
		result["scope"] = "edited_scene_native_visible_mesh_triangles";
		result["nodes_examined"] = examined;
		return result;
	}
	if (action == "viewport_selection_state" || action == "viewport_transform_selection") {
		const Variant index = p_args.get("index", 0);
		const Variant target_path = p_args.get("target", Variant());
		Node3DEditor *spatial = Node3DEditor::get_singleton();
		if (!spatial || !integer(index, 0, 3) || !node_path(target_path)) {
			return failure("invalid_viewport_selection_target");
		}
		Node3DEditorViewport *viewport = spatial->get_editor_viewport(index);
		Node3D *target = Object::cast_to<Node3D>(root->get_node_or_null(NodePath(target_path)));
		EditorSelection *selection = editor->get_selection();
		if (!viewport || !local_node(root, target) || !selection || selection->get_full_selected_node_list().size() != 1 || !selection->is_selected(target)) {
			return failure("viewport_requires_actual_single_selection");
		}
		state["target"] = target_path;
		state["parent_instance"] = target->get_parent() ? String::num_uint64(uint64_t(target->get_parent()->get_instance_id())) : String();
		state["owner_instance"] = target->get_owner() ? String::num_uint64(uint64_t(target->get_owner()->get_instance_id())) : String();
		state["viewport_instance"] = String::num_uint64(uint64_t(viewport->get_instance_id()));
		state["viewport_index"] = index;
		// Bind the logical native editor camera, not its interpolating visual
		// camera, so ordinary smoothing cannot invalidate every approval.
		const Transform3D camera = viewport->get_controller()->to_camera_transform();
		state["camera_source"] = "logical_editor_view";
		const Transform3D old_transform = target->get_global_transform();
		state["camera"] = wire(camera);
		state["transform"] = wire(old_transform);
		if (action == "viewport_selection_state") {
			return proposal(p_args, target, state, false, false);
		}
		if (root->get_scene_inherited_state().is_valid() || p_args.get("value", Variant()).get_type() != Variant::DICTIONARY) {
			return failure("unsupported_viewport_transform");
		}
		Dictionary value = p_args["value"];
		const String mode = value.get("mode", ""), space = value.get("space", "");
		Variant converted;
		if ((space != "world" && space != "local" && space != "view") || !AIChatEditorSceneActions::convert_json_value(value.get("delta", Variant()), Variant::VECTOR3, converted) || !camera.is_finite() || !old_transform.is_finite() || Math::is_zero_approx(old_transform.basis.determinant())) {
			return failure("invalid_viewport_transform_delta");
		}
		const Vector3 delta = converted;
		Transform3D transform = old_transform;
		if (mode == "translate") {
			transform.origin += space == "world" ? delta : (space == "local" ? old_transform.basis : camera.basis).xform(delta);
		} else if (mode == "rotate" || mode == "scale") {
			Basis change;
			if (mode == "rotate") {
				if (delta.abs()[delta.abs().max_axis_index()] > Math::TAU) {
					return failure("invalid_viewport_rotation");
				}
				change = Basis::from_euler(delta);
			} else {
				if (delta.x < 0.001 || delta.y < 0.001 || delta.z < 0.001 || delta.x > 100 || delta.y > 100 || delta.z > 100) {
					return failure("invalid_viewport_scale");
				}
				change = Basis::from_scale(delta);
			}
			transform.basis = space == "local" ? old_transform.basis * change : (space == "world" ? change : camera.basis * change * camera.basis.inverse()) * old_transform.basis;
		} else {
			return failure("invalid_viewport_transform_mode");
		}
		if (!transform.is_finite() || !Math::is_finite(transform.basis.determinant()) || Math::is_zero_approx(transform.basis.determinant())) {
			return failure("invalid_resulting_viewport_transform");
		}
		Dictionary result = proposal(p_args, target, state, p_confirmed, true);
		if (!bool(result["ok"])) {
			return result;
		}
		EditorUndoRedoManager *undo = EditorUndoRedoManager::get_singleton();
		if (!undo || undo->is_committing_action()) {
			return failure("undo_unavailable");
		}
		Ref<NativeSpatialEdit> receiver = memnew(NativeSpatialEdit(target->get_instance_id()));
		undo->create_action("AI Chat: viewport transform selection", UndoRedo::MERGE_DISABLE, root);
		UndoRedo *history = undo->get_history_undo_redo(undo->get_history_id_for_object(root));
		history->add_do_method(callable_mp(receiver.ptr(), &NativeSpatialEdit::transform).bind(transform));
		history->add_undo_method(callable_mp(receiver.ptr(), &NativeSpatialEdit::transform).bind(old_transform));
		undo->commit_action();
		if (!receiver->succeeded) {
			return failure("viewport_transform_readback_failed");
		}
		Dictionary read_args = p_args.duplicate(true);
		read_args["action"] = "viewport_selection_state";
		const Dictionary readback = perform(read_args, false);
		result["readback"] = readback;
		if (!bool(readback.get("ok", false))) {
			result["ok"] = false;
			result["error"] = "viewport_selection_readback_failed";
		}
		result["undoable"] = true;
		return result;
	}
	if (action.begins_with("viewport_")) {
		const String dimension = p_args.get("dimension", "");
		Dictionary camera, update;
		Object *target = nullptr;
		CanvasItemEditor *canvas = nullptr;
		Node3DEditorViewport *viewport = nullptr;
		if (dimension == "2d") {
			canvas = CanvasItemEditor::get_singleton();
			if (!canvas) {
				return failure("viewport_unavailable");
			}
			target = canvas;
			const Dictionary native_state = canvas->get_state();
			camera["offset"] = wire(native_state["ofs"]);
			camera["zoom"] = native_state["zoom"];
		} else if (dimension == "3d") {
			const Variant index = p_args.get("index", 0);
			Node3DEditor *spatial = Node3DEditor::get_singleton();
			if (!spatial || !integer(index, 0, 3) || !(viewport = spatial->get_editor_viewport(int(index)))) {
				return failure("invalid_viewport_index");
			}
			target = viewport;
			const Dictionary native_state = viewport->get_state();
			camera["position"] = wire(native_state["position"]);
			camera["x_rotation"] = native_state["x_rotation"];
			camera["y_rotation"] = native_state["y_rotation"];
			camera["distance"] = native_state["distance"];
			camera["orthogonal"] = native_state["orthogonal"];
			state["viewport_index"] = index;
		} else {
			return failure("invalid_viewport_dimension");
		}
		state["camera"] = camera;
		state["dimension"] = dimension;
		if (action == "viewport_set_view") {
			if (p_args.get("value", Variant()).get_type() != Variant::DICTIONARY) {
				return failure("invalid_camera_value");
			}
			const Dictionary value = p_args["value"];
			if (value.is_empty()) {
				return failure("empty_camera_value");
			}
			for (const Variant &key : value.keys()) {
				if (!camera.has(key)) {
					return failure("unsupported_camera_field");
				}
				Variant converted;
				if ((key == Variant(String("offset")) && canvas) || (key == Variant(String("position")) && viewport)) {
					if (!AIChatEditorSceneActions::convert_json_value(value[key], canvas ? Variant::VECTOR2 : Variant::VECTOR3, converted)) {
						return failure("invalid_camera_vector");
					}
					update[canvas ? "ofs" : "position"] = converted;
				} else if (key == Variant(String("orthogonal"))) {
					if (value[key].get_type() != Variant::BOOL) {
						return failure("invalid_camera_projection");
					}
					update[key] = value[key];
				} else {
					const bool positive = key == Variant(String("zoom")) || key == Variant(String("distance"));
					if (!number(value[key], positive ? 0.001 : -Math::TAU, positive ? 10000.0 : Math::TAU)) {
						return failure("invalid_camera_number");
					}
					update[key] = value[key];
				}
			}
		}
		Dictionary result = proposal(p_args, target, state, p_confirmed, action == "viewport_set_view");
		if (!bool(result["ok"]) || action == "viewport_state") {
			return result;
		}
		if (canvas) {
			canvas->set_state(update);
		} else {
			viewport->set_state(update);
		}
		Dictionary read_args = p_args.duplicate(true);
		read_args["action"] = "viewport_state";
		const Dictionary readback = perform(read_args, false);
		result["readback"] = readback;
		if (!bool(readback.get("ok", false))) {
			result["ok"] = false;
			result["error"] = "viewport_camera_readback_failed";
		} else {
			const Dictionary actual_camera = Dictionary(readback["state"])["camera"];
			const Dictionary requested_camera = p_args["value"];
			for (const Variant &key : requested_camera.keys()) {
				if (!same_camera_value(requested_camera[key], actual_camera.get(key, Variant()))) {
					result["ok"] = false;
					result["error"] = "viewport_camera_result_mismatch";
				}
			}
		}
		result["undoable"] = false;
		return result;
	}
	const Variant path = p_args.get("target", ".");
	if (!node_path(path)) {
		return failure("invalid_node_path");
	}
	Node *node = root->get_node_or_null(NodePath(path));
	if (!local_node(root, node)) {
		return failure("unsupported_scene_target");
	}
	const bool write = !action.ends_with("_state") && action != "animation_copy_keys";
	if (write && root->get_scene_inherited_state().is_valid()) {
		return failure("inherited_scene_edit_unsupported");
	}
	state["node_path"] = path;
	state["node_instance"] = String::num_uint64(uint64_t(node->get_instance_id()));
	state["parent_instance"] = node->get_parent() ? String::num_uint64(uint64_t(node->get_parent()->get_instance_id())) : String();
	state["owner_instance"] = node->get_owner() ? String::num_uint64(uint64_t(node->get_owner()->get_instance_id())) : String();
	Ref<NativeSpatialEdit> receiver;
	Callable apply, reverse;
	if (action.begins_with("polygon_")) {
		Polygon2D *polygon = Object::cast_to<Polygon2D>(node);
		CollisionPolygon2D *collision = Object::cast_to<CollisionPolygon2D>(node);
		if (!polygon && !collision) {
			return failure("unsupported_polygon_target");
		}
		const PackedVector2Array old_points = polygon ? polygon->get_polygon() : collision->get_polygon();
		if (old_points.size() > 256) {
			return failure("polygon_capacity");
		}
		state["points"] = wire(old_points);
		if (write) {
			if (p_args.get("value", Variant()).get_type() != Variant::ARRAY || Array(p_args["value"]).size() > 256) {
				return failure("invalid_polygon_points");
			}
			PackedVector2Array points;
			for (const Variant &point : Array(p_args["value"])) {
				Variant converted;
				if (!AIChatEditorSceneActions::convert_json_value(point, Variant::VECTOR2, converted)) {
					return failure("invalid_polygon_point");
				}
				points.push_back(converted);
			}
			receiver = memnew(NativeSpatialEdit(node->get_instance_id()));
			apply = callable_mp(receiver.ptr(), &NativeSpatialEdit::polygon).bind(points);
			reverse = callable_mp(receiver.ptr(), &NativeSpatialEdit::polygon).bind(old_points);
		}
	} else if (action.begins_with("animation_")) {
		AnimationPlayer *player = Object::cast_to<AnimationPlayer>(node);
		const Variant animation_name = p_args.get("animation", Variant());
		if (!player || player->is_playing() || animation_name.get_type() != Variant::STRING || String(animation_name).length() > 256 || !player->has_animation(animation_name)) {
			return failure("animation_unavailable_or_playing");
		}
		Node *animation_root = player->get_node_or_null(player->get_root_node());
		if (!local_node(root, animation_root)) {
			return failure("animation_root_outside_edited_scene");
		}
		state["animation_root_instance"] = String::num_uint64(uint64_t(animation_root->get_instance_id()));
		state["animation_root_path"] = String(root->get_path_to(animation_root));
		Ref<Animation> animation = player->get_animation(animation_name);
		Dictionary animation_state;
		if (!animation_snapshot(animation, animation_state)) {
			return failure("unsupported_animation_or_capacity");
		}
		AnimationPlayerEditor *animation_editor = AnimationPlayerEditor::get_singleton();
		AnimationTrackEditor *timeline = animation_editor && animation_editor->get_player() == player ? animation_editor->get_track_editor() : nullptr;
		if (timeline && timeline->get_current_animation() != animation) {
			timeline = nullptr;
		}
		state["timeline_instance"] = timeline ? String::num_uint64(uint64_t(timeline->get_instance_id())) : String();
		Array selected_keys;
		if (timeline) {
			for (int t = 0; t < animation->get_track_count(); t++) {
				for (int k = 0; k < animation->track_get_key_count(t); k++) {
					if (timeline->is_key_selected(t, k)) {
						Dictionary selected;
						selected["track"] = t;
						selected["key"] = k;
						selected_keys.push_back(selected);
					}
				}
			}
		}
		state["selected_keys"] = selected_keys;
		state["animation"] = animation_name;
		state["animation_data"] = animation_state;
		state["animation_identity"] = resource_identity(animation);
		if (Dictionary(state["animation_identity"]).has("unavailable")) {
			return failure("resource_observer_capacity");
		}
		Array clipboard, key_selection;
		if (action == "animation_copy_keys" || action == "animation_cut_keys") {
			if (p_args.get("keys", Variant()).get_type() != Variant::ARRAY || Array(p_args["keys"]).is_empty() || Array(p_args["keys"]).size() > 100) {
				return failure("invalid_animation_clipboard_selection");
			}
			Array seen;
			for (const Variant &raw : Array(p_args["keys"])) {
				if (raw.get_type() != Variant::DICTIONARY) {
					return failure("invalid_animation_clipboard_selection");
				}
				Dictionary selected = raw;
				Variant track = selected.get("track", Variant()), key = selected.get("key", Variant());
				if (!integer(track, 0, animation->get_track_count() - 1) || !integer(key, 0, animation->track_get_key_count(track) - 1)) {
					return failure("invalid_animation_clipboard_key");
				}
				String identity = itos(int(track)) + ":" + itos(int(key));
				if (seen.has(identity)) {
					return failure("duplicate_animation_clipboard_key");
				}
				seen.push_back(identity);
				Dictionary entry;
				entry["track"] = int(track);
				entry["key"] = int(key);
				key_selection.push_back(entry.duplicate());
				entry["track_type"] = int(animation->track_get_type(track));
				entry["path"] = String(animation->track_get_path(track));
				entry["time"] = animation->track_get_key_time(track, key);
				entry["transition"] = animation->track_get_key_transition(track, key);
				entry["value"] = wire(animation->track_get_key_value(track, key));
				clipboard.push_back(entry);
			}
			state["clipboard"] = clipboard;
			if (action == "animation_copy_keys") {
				Dictionary result = proposal(p_args, node, state, false, false);
				result["clipboard"] = clipboard;
				return result;
			}
		}
		if (action == "animation_select_keys") {
			if (!timeline || timeline->is_moving_selection() || p_args.get("keys", Variant()).get_type() != Variant::ARRAY || Array(p_args["keys"]).size() > 100) {
				return failure("animation_timeline_unavailable_or_invalid_keys");
			}
			const Array keys = p_args["keys"];
			Array seen;
			for (const Variant &raw : keys) {
				if (raw.get_type() != Variant::DICTIONARY) {
					return failure("invalid_animation_selection_key");
				}
				Dictionary key = raw;
				const Variant track = key.get("track", Variant());
				const Variant index = key.get("key", Variant());
				if (!integer(track, 0, animation->get_track_count() - 1) || !integer(index, 0, animation->track_get_key_count(track) - 1)) {
					return failure("invalid_animation_selection_key");
				}
				String identity = itos(int(track)) + ":" + itos(int(index));
				if (seen.has(identity)) {
					return failure("duplicate_animation_selection_key");
				}
				seen.push_back(identity);
			}
			Dictionary result = proposal(p_args, node, state, p_confirmed, true);
			if (!bool(result["ok"])) {
				return result;
			}
			timeline->_clear_selection(true);
			for (const Variant &raw : keys) {
				Dictionary key = raw;
				timeline->_key_selected(key["key"], false, key["track"]);
			}
			Dictionary read_args = p_args.duplicate(true);
			read_args["action"] = "animation_state";
			result["readback"] = perform(read_args, false);
			result["undoable"] = false;
			return result;
		}
		if (write) {
			if (animation->get_path().begins_with("res://.godot/")) {
				return failure("imported_animation_resource");
			}
			Array animated_targets;
			for (int t = 0; t < animation->get_track_count(); t++) {
				const NodePath animated_path = animation->track_get_path(t);
				Node *animated_node = animation_root->get_node_or_null(NodePath(animated_path.get_concatenated_names()));
				if (animated_path.is_absolute() || !local_node(root, animated_node) || animated_path.get_subname_count() > 1) {
					return failure("unsupported_animation_path");
				}
				Dictionary target_state;
				target_state["track"] = t;
				target_state["instance"] = String::num_uint64(uint64_t(animated_node->get_instance_id()));
				target_state["parent"] = animated_node->get_parent() ? String::num_uint64(uint64_t(animated_node->get_parent()->get_instance_id())) : String();
				const Animation::TrackType type = animation->track_get_type(t);
				if (type == Animation::TYPE_VALUE) {
					const String property = animated_path.get_subname_count() == 1 ? String(animated_path.get_subname(0)) : String();
					if (property != "visible" && property != "rotation" && property != "rotation_degrees" && property != "offset_left" && property != "offset_right" && property != "offset_top" && property != "offset_bottom") {
						return failure("unsupported_animation_property");
					}
					Variant actual;
					if (!animated_node->get_native(property, actual) || !scalar(actual)) {
						return failure("animation_property_unavailable_or_not_scalar");
					}
					target_state["property_type"] = int(actual.get_type());
				} else if (type != Animation::TYPE_BLEND_SHAPE && (animated_path.get_subname_count() != 0 || !Object::cast_to<Node3D>(animated_node))) {
					return failure("unsupported_animation_transform_target");
				} else if (type == Animation::TYPE_BLEND_SHAPE && !Object::cast_to<MeshInstance3D>(animated_node)) {
					return failure("unsupported_animation_blend_target");
				}
				animated_targets.push_back(target_state);
			}
			state["animated_targets"] = animated_targets;
			const Variant track_arg = p_args.get("track", Variant());
			if (action != "animation_add_track" && action != "animation_cut_keys" && action != "animation_paste_keys" && !integer(track_arg, 0, animation->get_track_count() - 1)) {
				return failure("invalid_animation_track");
			}
			const int track = action == "animation_add_track" || action == "animation_cut_keys" || action == "animation_paste_keys" ? -1 : int(track_arg);
			if (track >= 0 && animation->track_is_imported(track)) {
				return failure("imported_animation_track");
			}
			Ref<Animation> modified = copy_animation(animation);
			if (action == "animation_cut_keys") {
				// Remove descending indices on each track, preserving every other
				// key and committing the entire cut as one native undo action.
				for (int t = 0; t < modified->get_track_count(); t++) {
					for (int k = modified->track_get_key_count(t) - 1; k >= 0; k--) {
						for (const Variant &raw : key_selection) {
							Dictionary selected = raw;
							if (int(selected["track"]) == t && int(selected["key"]) == k) {
								if (modified->track_is_imported(t)) {
									return failure("imported_animation_track");
								}
								modified->track_remove_key(t, k);
							}
						}
					}
				}
			} else if (action == "animation_paste_keys") {
				if (p_args.get("value", Variant()).get_type() != Variant::DICTIONARY) {
					return failure("invalid_animation_clipboard");
				}
				const Dictionary value = p_args["value"];
				const Variant offset = value.get("offset", 0);
				if (!number(offset) || value.get("keys", Variant()).get_type() != Variant::ARRAY || Array(value["keys"]).is_empty() || Array(value["keys"]).size() > 100) {
					return failure("invalid_animation_clipboard");
				}
				for (const Variant &raw : Array(value["keys"])) {
					if (raw.get_type() != Variant::DICTIONARY) {
						return failure("invalid_animation_clipboard_entry");
					}
					const Dictionary entry = raw;
					const Variant destination = entry.get("track", Variant()), time = entry.get("time", Variant()), type = entry.get("track_type", Variant()), transition = entry.get("transition", 1.0);
					if (!integer(destination, 0, modified->get_track_count() - 1) || !integer(type, Animation::TYPE_VALUE, Animation::TYPE_BLEND_SHAPE) || !number(time) || !number(transition, 0, 1000000)) {
						return failure("invalid_animation_clipboard_entry");
					}
					const int t = destination;
					const double at = double(time) + double(offset);
					if (modified->track_is_imported(t) || int(modified->track_get_type(t)) != int(type) || entry.get("path", Variant()) != Variant(String(modified->track_get_path(t))) || !number(at, 0, modified->get_length())) {
						return failure("animation_clipboard_target_mismatch");
					}
					for (int k = 0; k < modified->track_get_key_count(t); k++) {
						if (Math::is_equal_approx(modified->track_get_key_time(t, k), at)) {
							return failure("animation_time_occupied");
						}
					}
					Variant converted;
					if (!key_value(Animation::TrackType(int(type)), entry.get("value", Variant()), converted)) {
						return failure("invalid_animation_clipboard_value");
					}
					if (int(type) == Animation::TYPE_VALUE) {
						const Dictionary target_state = animated_targets[t];
						if (!AIChatEditorSceneActions::convert_json_value(entry.get("value", Variant()), Variant::Type(int(target_state["property_type"])), converted)) {
							return failure("animation_property_type_mismatch");
						}
					}
					modified->track_insert_key(t, at, converted, transition);
				}
			} else if (action == "animation_add_track") {
				const Variant type = p_args.get("track_type", Variant());
				const Variant track_path = p_args.get("path", Variant());
				if (!integer(type, Animation::TYPE_VALUE, Animation::TYPE_SCALE_3D) || !node_path(track_path) || animation->get_track_count() >= 64) {
					return failure("invalid_animation_track_definition");
				}
				// New property tracks target the node itself via an explicit safe
				// property; never methods, scripts, resource paths or event tracks.
				Node *animated = root->get_node_or_null(NodePath(track_path));
				if (!local_node(root, animated)) {
					return failure("unsupported_animated_node");
				}
				if (animated != animation_root && !animation_root->is_ancestor_of(animated)) {
					return failure("animated_node_outside_animation_root");
				}
				if (int(type) != Animation::TYPE_VALUE && !Object::cast_to<Node3D>(animated)) {
					return failure("unsupported_animation_transform_target");
				}
				String native_path = String(animation_root->get_path_to(animated));
				if (int(type) == Animation::TYPE_VALUE) {
					const String property = p_args.get("property", "");
					if (property != "visible" && property != "rotation" && property != "rotation_degrees" && property != "offset_left" && property != "offset_right" && property != "offset_top" && property != "offset_bottom") {
						return failure("unsupported_animation_property");
					}
					Variant actual;
					if (!animated->get_native(property, actual) || !scalar(actual)) {
						return failure("animation_property_unavailable_or_not_scalar");
					}
					native_path += ":" + property;
				}
				Dictionary added_target;
				added_target["instance"] = String::num_uint64(uint64_t(animated->get_instance_id()));
				added_target["parent"] = animated->get_parent() ? String::num_uint64(uint64_t(animated->get_parent()->get_instance_id())) : String();
				state["new_animated_target"] = added_target;
				const int added = modified->add_track(Animation::TrackType(int(type)));
				modified->track_set_path(added, NodePath(native_path));
			} else if (action == "animation_remove_track") {
				modified->remove_track(track);
			} else {
				const Variant key_arg = p_args.get("key", Variant());
				if (action != "animation_insert_key" && !integer(key_arg, 0, animation->track_get_key_count(track) - 1)) {
					return failure("invalid_animation_key");
				}
				const int key = action == "animation_insert_key" ? -1 : int(key_arg);
				if (action == "animation_remove_key") {
					modified->track_remove_key(track, key);
				} else {
					const Variant time = p_args.get("time", Variant());
					if (!number(time, 0, animation->get_length())) {
						return failure("invalid_animation_time");
					}
					for (int i = 0; i < animation->track_get_key_count(track); i++) {
						if (i != key && Math::is_equal_approx(animation->track_get_key_time(track, i), double(time))) {
							return failure("animation_time_occupied");
						}
					}
					if (action == "animation_move_key") {
						modified->track_set_key_time(track, key, time);
					} else {
						const Animation::TrackType type = animation->track_get_type(track);
						const Variant input = p_args.get("value", Variant());
						Variant converted;
						if (type == Animation::TYPE_VALUE || type == Animation::TYPE_BLEND_SHAPE) {
							if (!scalar(input) || (type == Animation::TYPE_BLEND_SHAPE && !number(input))) {
								return failure("invalid_animation_value");
							}
							converted = input;
							if (type == Animation::TYPE_VALUE) {
								const Dictionary target_state = animated_targets[track];
								if (!AIChatEditorSceneActions::convert_json_value(input, Variant::Type(int(target_state["property_type"])), converted)) {
									return failure("animation_property_type_mismatch");
								}
							}
						} else if (type == Animation::TYPE_ROTATION_3D) {
							if (input.get_type() != Variant::ARRAY || Array(input).size() != 4) {
								return failure("invalid_animation_quaternion");
							}
							Array values = input;
							for (const Variant &component : values) {
								if (!number(component, -1, 1)) {
									return failure("invalid_animation_quaternion");
								}
							}
							Quaternion quaternion(values[0], values[1], values[2], values[3]);
							if (!quaternion.is_normalized()) {
								return failure("invalid_animation_quaternion");
							}
							converted = quaternion;
						} else if (!AIChatEditorSceneActions::convert_json_value(input, Variant::VECTOR3, converted)) {
							return failure("invalid_animation_vector");
						}
						modified->track_insert_key(track, time, converted);
					}
				}
			}
			Dictionary modified_state;
			if (!animation_snapshot(modified, modified_state)) {
				return failure("animation_capacity");
			}
			receiver = memnew(NativeSpatialEdit(animation->get_instance_id()));
			apply = callable_mp(receiver.ptr(), &NativeSpatialEdit::animation).bind(modified);
			reverse = callable_mp(receiver.ptr(), &NativeSpatialEdit::animation).bind(copy_animation(animation));
		}
	} else {
#ifdef MODULE_TILEMAP_ENABLED
		TileMapLayer *layer = Object::cast_to<TileMapLayer>(node);
		if (!layer || !native(layer->get_tile_set().ptr())) {
			return failure("unsupported_tilemap_target");
		}
		const Variant cells_arg = p_args.get("cells", Variant());
		if (cells_arg.get_type() != Variant::ARRAY || Array(cells_arg).is_empty() || Array(cells_arg).size() > 100) {
			return failure("invalid_tilemap_cells");
		}
		Array before, after, observed, seen;
		for (const Variant &raw : Array(cells_arg)) {
			if (raw.get_type() != Variant::DICTIONARY) {
				return failure("invalid_tilemap_cell");
			}
			const Dictionary cell = raw;
			Variant coords;
			if (!AIChatEditorSceneActions::convert_json_value(cell.get("coords", Variant()), Variant::VECTOR2I, coords) || seen.has(coords)) {
				return failure("invalid_or_duplicate_tilemap_coords");
			}
			seen.push_back(coords);
			Dictionary old;
			old["coords"] = coords;
			old["source_id"] = layer->get_cell_source_id(coords);
			old["atlas_coords"] = layer->get_cell_atlas_coords(coords);
			old["alternative"] = layer->get_cell_alternative_tile(coords);
			if (write && int(old["source_id"]) >= 0) {
				const Ref<TileSet> tileset = layer->get_tile_set();
				if (!tileset->has_source(old["source_id"])) {
					return failure("old_tile_source_unavailable");
				}
				Ref<TileSetAtlasSource> atlas = tileset->get_source(old["source_id"]);
				if (!native(atlas.ptr())) {
					return failure("unsupported_existing_tile_source");
				}
			}
			before.push_back(old);
			Dictionary row = old.duplicate();
			row["coords"] = wire(coords);
			row["atlas_coords"] = wire(old["atlas_coords"]);
			observed.push_back(row);
			if (!write) {
				continue;
			}
			const Variant source = cell.get("source_id", Variant());
			if (!integer(source, -1, 2147483647)) {
				return failure("invalid_tile_source");
			}
			Dictionary next;
			next["coords"] = coords;
			next["source_id"] = source;
			Variant atlas_coords = Vector2i(-1, -1);
			int alternative = 0;
			if (int(source) >= 0) {
				Ref<TileSet> tileset = layer->get_tile_set();
				if (!tileset->has_source(source) || !AIChatEditorSceneActions::convert_json_value(cell.get("atlas_coords", Variant()), Variant::VECTOR2I, atlas_coords) || !integer(cell.get("alternative", 0), 0, 2147483647)) {
					return failure("invalid_tile_definition");
				}
				Ref<TileSetAtlasSource> atlas = tileset->get_source(source);
				alternative = cell.get("alternative", 0);
				// Scene collection cells may instantiate arbitrary scripts. This
				// channel intentionally accepts native atlas sources only.
				if (!native(atlas.ptr()) || !atlas->has_tile(atlas_coords) || !atlas->has_alternative_tile(atlas_coords, alternative)) {
					return failure("unsupported_tile_atlas_or_alternative");
				}
			}
			next["atlas_coords"] = atlas_coords;
			next["alternative"] = alternative;
			after.push_back(next);
		}
		state["tileset_identity"] = resource_identity(layer->get_tile_set());
		if (Dictionary(state["tileset_identity"]).has("unavailable")) {
			return failure("resource_observer_capacity");
		}
		state["cells"] = observed;
		if (write) {
			receiver = memnew(NativeSpatialEdit(layer->get_instance_id()));
			apply = callable_mp(receiver.ptr(), &NativeSpatialEdit::cells).bind(after);
			reverse = callable_mp(receiver.ptr(), &NativeSpatialEdit::cells).bind(before);
		}
#else
		return failure("tilemap_module_disabled");
#endif
	}
	if (JSON::stringify(state).utf8().length() > 32768) {
		return failure("spatial_snapshot_capacity");
	}
	Dictionary result = proposal(p_args, node, state, p_confirmed, write);
	if (!write || !bool(result["ok"])) {
		return result;
	}
	EditorUndoRedoManager *undo = EditorUndoRedoManager::get_singleton();
	if (!undo || undo->is_committing_action()) {
		return failure("undo_unavailable");
	}
	undo->create_action("AI Chat: " + action, UndoRedo::MERGE_DISABLE, root);
	UndoRedo *history = undo->get_history_undo_redo(undo->get_history_id_for_object(root));
	history->add_do_method(apply);
	history->add_undo_method(reverse);
	undo->commit_action();
	if (!receiver->succeeded) {
		return failure("spatial_native_mutation_failed");
	}
	Dictionary read_args = p_args.duplicate(true);
	read_args["action"] = action.begins_with("animation_") ? "animation_state" : action.begins_with("polygon_") ? "polygon_state"
																												: "tilemap_state";
	const Dictionary readback = perform(read_args, false);
	result["readback"] = readback;
	if (action == "animation_cut_keys") {
		result["clipboard"] = state["clipboard"];
	}
	if (!bool(readback.get("ok", false))) {
		result["ok"] = false;
		result["error"] = "spatial_readback_failed";
	}
	result["undoable"] = true;
	return result;
}
