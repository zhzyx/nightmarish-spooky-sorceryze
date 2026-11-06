/**************************************************************************/
/*  gameplay_relevancy.cpp                                                */
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

#include "gameplay_relevancy.h"

#include "core/math/math_funcs.h"
#include "core/object/class_db.h"

void GameplayConnectionView::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_peer_id", "peer_id"), &GameplayConnectionView::set_peer_id);
	ClassDB::bind_method(D_METHOD("get_peer_id"), &GameplayConnectionView::get_peer_id);
	ClassDB::bind_method(D_METHOD("set_position", "position"), &GameplayConnectionView::set_position);
	ClassDB::bind_method(D_METHOD("get_position"), &GameplayConnectionView::get_position);
	ClassDB::bind_method(D_METHOD("set_team_id", "team_id"), &GameplayConnectionView::set_team_id);
	ClassDB::bind_method(D_METHOD("get_team_id"), &GameplayConnectionView::get_team_id);
	ClassDB::bind_method(D_METHOD("set_bandwidth_budget_bytes", "bytes"), &GameplayConnectionView::set_bandwidth_budget_bytes);
	ClassDB::bind_method(D_METHOD("get_bandwidth_budget_bytes"), &GameplayConnectionView::get_bandwidth_budget_bytes);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "peer_id"), "set_peer_id", "get_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "position"), "set_position", "get_position");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "team_id"), "set_team_id", "get_team_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "bandwidth_budget_bytes", PROPERTY_HINT_RANGE, "1,16777216,1,or_greater"), "set_bandwidth_budget_bytes", "get_bandwidth_budget_bytes");
}

void GameplayConnectionView::set_peer_id(int p_peer_id) {
	ERR_FAIL_COND_MSG(p_peer_id < 0, "Peer ID cannot be negative.");
	peer_id = p_peer_id;
}

int GameplayConnectionView::get_peer_id() const {
	return peer_id;
}

void GameplayConnectionView::set_position(const Vector3 &p_position) {
	ERR_FAIL_COND_MSG(!p_position.is_finite(), "Connection view position must be finite.");
	position = p_position;
}

Vector3 GameplayConnectionView::get_position() const {
	return position;
}

void GameplayConnectionView::set_team_id(int p_team_id) {
	ERR_FAIL_COND_MSG(p_team_id < 0, "Team ID cannot be negative.");
	team_id = p_team_id;
}

int GameplayConnectionView::get_team_id() const {
	return team_id;
}

void GameplayConnectionView::set_bandwidth_budget_bytes(int p_bytes) {
	ERR_FAIL_COND_MSG(p_bytes < 1, "A connection bandwidth budget must be positive.");
	bandwidth_budget_bytes = p_bytes;
}

int GameplayConnectionView::get_bandwidth_budget_bytes() const {
	return bandwidth_budget_bytes;
}

void GameplayRelevancyObject::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_object_id", "object_id"), &GameplayRelevancyObject::set_object_id);
	ClassDB::bind_method(D_METHOD("get_object_id"), &GameplayRelevancyObject::get_object_id);
	ClassDB::bind_method(D_METHOD("set_position", "position"), &GameplayRelevancyObject::set_position);
	ClassDB::bind_method(D_METHOD("get_position"), &GameplayRelevancyObject::get_position);
	ClassDB::bind_method(D_METHOD("set_owner_peer_id", "peer_id"), &GameplayRelevancyObject::set_owner_peer_id);
	ClassDB::bind_method(D_METHOD("get_owner_peer_id"), &GameplayRelevancyObject::get_owner_peer_id);
	ClassDB::bind_method(D_METHOD("set_team_id", "team_id"), &GameplayRelevancyObject::set_team_id);
	ClassDB::bind_method(D_METHOD("get_team_id"), &GameplayRelevancyObject::get_team_id);
	ClassDB::bind_method(D_METHOD("set_policy", "policy"), &GameplayRelevancyObject::set_policy);
	ClassDB::bind_method(D_METHOD("get_policy"), &GameplayRelevancyObject::get_policy);
	ClassDB::bind_method(D_METHOD("set_cull_distance", "distance"), &GameplayRelevancyObject::set_cull_distance);
	ClassDB::bind_method(D_METHOD("get_cull_distance"), &GameplayRelevancyObject::get_cull_distance);
	ClassDB::bind_method(D_METHOD("set_priority", "priority"), &GameplayRelevancyObject::set_priority);
	ClassDB::bind_method(D_METHOD("get_priority"), &GameplayRelevancyObject::get_priority);
	ClassDB::bind_method(D_METHOD("set_update_interval_msec", "interval_msec"), &GameplayRelevancyObject::set_update_interval_msec);
	ClassDB::bind_method(D_METHOD("get_update_interval_msec"), &GameplayRelevancyObject::get_update_interval_msec);
	ClassDB::bind_method(D_METHOD("set_estimated_update_bytes", "bytes"), &GameplayRelevancyObject::set_estimated_update_bytes);
	ClassDB::bind_method(D_METHOD("get_estimated_update_bytes"), &GameplayRelevancyObject::get_estimated_update_bytes);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "object_id"), "set_object_id", "get_object_id");
	ADD_PROPERTY(PropertyInfo(Variant::VECTOR3, "position"), "set_position", "get_position");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "owner_peer_id"), "set_owner_peer_id", "get_owner_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "team_id"), "set_team_id", "get_team_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "policy", PROPERTY_HINT_ENUM, "Distance,Owner Only,Team Only,Owner Or Team,Always"), "set_policy", "get_policy");
	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "cull_distance", PROPERTY_HINT_RANGE, "0.001,1000000,0.001,or_greater,suffix:m"), "set_cull_distance", "get_cull_distance");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "priority", PROPERTY_HINT_RANGE, "0,1000,1"), "set_priority", "get_priority");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "update_interval_msec", PROPERTY_HINT_RANGE, "0,60000,1,or_greater"), "set_update_interval_msec", "get_update_interval_msec");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "estimated_update_bytes", PROPERTY_HINT_RANGE, "1,16777216,1,or_greater"), "set_estimated_update_bytes", "get_estimated_update_bytes");

	BIND_ENUM_CONSTANT(POLICY_DISTANCE);
	BIND_ENUM_CONSTANT(POLICY_OWNER_ONLY);
	BIND_ENUM_CONSTANT(POLICY_TEAM_ONLY);
	BIND_ENUM_CONSTANT(POLICY_OWNER_OR_TEAM);
	BIND_ENUM_CONSTANT(POLICY_ALWAYS);
}

void GameplayRelevancyObject::set_object_id(int p_object_id) {
	ERR_FAIL_COND_MSG(p_object_id < 0, "Object ID cannot be negative.");
	object_id = p_object_id;
}

int GameplayRelevancyObject::get_object_id() const {
	return object_id;
}

void GameplayRelevancyObject::set_position(const Vector3 &p_position) {
	ERR_FAIL_COND_MSG(!p_position.is_finite(), "Relevancy object position must be finite.");
	position = p_position;
}

Vector3 GameplayRelevancyObject::get_position() const {
	return position;
}

void GameplayRelevancyObject::set_owner_peer_id(int p_peer_id) {
	ERR_FAIL_COND_MSG(p_peer_id < 0, "Owner peer ID cannot be negative.");
	owner_peer_id = p_peer_id;
}

int GameplayRelevancyObject::get_owner_peer_id() const {
	return owner_peer_id;
}

void GameplayRelevancyObject::set_team_id(int p_team_id) {
	ERR_FAIL_COND_MSG(p_team_id < 0, "Team ID cannot be negative.");
	team_id = p_team_id;
}

int GameplayRelevancyObject::get_team_id() const {
	return team_id;
}

void GameplayRelevancyObject::set_policy(Policy p_policy) {
	ERR_FAIL_INDEX_MSG(p_policy, 5, "Invalid relevancy policy.");
	policy = p_policy;
}

GameplayRelevancyObject::Policy GameplayRelevancyObject::get_policy() const {
	return policy;
}

void GameplayRelevancyObject::set_cull_distance(float p_distance) {
	ERR_FAIL_COND_MSG(!Math::is_finite(p_distance) || p_distance <= 0.0f, "Cull distance must be finite and positive.");
	cull_distance = p_distance;
}

float GameplayRelevancyObject::get_cull_distance() const {
	return cull_distance;
}

void GameplayRelevancyObject::set_priority(int p_priority) {
	ERR_FAIL_COND_MSG(p_priority < 0 || p_priority > 1000, "Priority must be between 0 and 1000.");
	priority = p_priority;
}

int GameplayRelevancyObject::get_priority() const {
	return priority;
}

void GameplayRelevancyObject::set_update_interval_msec(uint64_t p_interval_msec) {
	update_interval_msec = p_interval_msec;
}

uint64_t GameplayRelevancyObject::get_update_interval_msec() const {
	return update_interval_msec;
}

void GameplayRelevancyObject::set_estimated_update_bytes(int p_bytes) {
	ERR_FAIL_COND_MSG(p_bytes < 1, "Estimated update size must be positive.");
	estimated_update_bytes = p_bytes;
}

int GameplayRelevancyObject::get_estimated_update_bytes() const {
	return estimated_update_bytes;
}

Vector3i GameplayReplicationGraph::_cell_for_position(const Vector3 &p_position) const {
	return Vector3i(Math::floor(p_position.x / cell_size), Math::floor(p_position.y / cell_size), Math::floor(p_position.z / cell_size));
}

void GameplayReplicationGraph::_add_to_index(int p_object_id, const ObjectRuntime &p_object) {
	if (p_object.policy != GameplayRelevancyObject::POLICY_DISTANCE) {
		non_spatial_objects.insert(p_object_id);
		return;
	}
	const Vector3i cell = _cell_for_position(p_object.position);
	HashSet<int> *bucket = spatial_grid.getptr(cell);
	if (!bucket) {
		spatial_grid.insert(cell, HashSet<int>());
		bucket = spatial_grid.getptr(cell);
	}
	bucket->insert(p_object_id);
}

void GameplayReplicationGraph::_remove_from_index(int p_object_id, const ObjectRuntime &p_object) {
	if (p_object.policy != GameplayRelevancyObject::POLICY_DISTANCE) {
		non_spatial_objects.erase(p_object_id);
		return;
	}
	const Vector3i cell = _cell_for_position(p_object.position);
	HashSet<int> *bucket = spatial_grid.getptr(cell);
	if (!bucket) {
		return;
	}
	bucket->erase(p_object_id);
	if (bucket->is_empty()) {
		spatial_grid.erase(cell);
	}
}

void GameplayReplicationGraph::_rebuild_index() {
	spatial_grid.clear();
	non_spatial_objects.clear();
	for (const KeyValue<int, ObjectRuntime> &entry : objects) {
		_add_to_index(entry.key, entry.value);
	}
}

bool GameplayReplicationGraph::_is_relevant(const ObjectRuntime &p_object, int p_peer_id, const ConnectionRuntime &p_connection) const {
	switch (p_object.policy) {
		case GameplayRelevancyObject::POLICY_DISTANCE:
			return p_connection.position.distance_squared_to(p_object.position) <= p_object.cull_distance * p_object.cull_distance;
		case GameplayRelevancyObject::POLICY_OWNER_ONLY:
			return p_object.owner_peer_id > 0 && p_object.owner_peer_id == p_peer_id;
		case GameplayRelevancyObject::POLICY_TEAM_ONLY:
			return p_object.team_id > 0 && p_object.team_id == p_connection.team_id;
		case GameplayRelevancyObject::POLICY_OWNER_OR_TEAM:
			return (p_object.owner_peer_id > 0 && p_object.owner_peer_id == p_peer_id) || (p_object.team_id > 0 && p_object.team_id == p_connection.team_id);
		case GameplayRelevancyObject::POLICY_ALWAYS:
			return true;
	}
	return false;
}

HashSet<int> GameplayReplicationGraph::_collect_candidates(const ConnectionRuntime &p_connection) const {
	HashSet<int> candidates;
	for (const int object_id : non_spatial_objects) {
		candidates.insert(object_id);
	}
	const Vector3i center = _cell_for_position(p_connection.position);
	const int radius = int(Math::ceil(max_spatial_distance / cell_size));
	for (int x = center.x - radius; x <= center.x + radius; x++) {
		for (int y = center.y - radius; y <= center.y + radius; y++) {
			for (int z = center.z - radius; z <= center.z + radius; z++) {
				const HashSet<int> *bucket = spatial_grid.getptr(Vector3i(x, y, z));
				if (!bucket) {
					continue;
				}
				for (const int object_id : *bucket) {
					candidates.insert(object_id);
				}
			}
		}
	}
	return candidates;
}

Dictionary GameplayReplicationGraph::_refresh_relevance(int p_peer_id, ConnectionRuntime &p_connection) {
	const HashSet<int> candidates = _collect_candidates(p_connection);
	HashSet<int> current;
	Array entered;
	Array left;
	for (const int object_id : candidates) {
		const ObjectRuntime *object = objects.getptr(object_id);
		if (object && _is_relevant(*object, p_peer_id, p_connection)) {
			current.insert(object_id);
			if (!p_connection.relevant_objects.has(object_id)) {
				entered.push_back(object_id);
			}
		}
	}
	for (const int object_id : p_connection.relevant_objects) {
		if (!current.has(object_id)) {
			left.push_back(object_id);
			p_connection.schedule.erase(object_id);
		}
	}
	p_connection.relevant_objects = current;
	entered.sort();
	left.sort();
	Dictionary result;
	result["candidate_count"] = candidates.size();
	result["entered"] = entered;
	result["left"] = left;
	return result;
}

void GameplayReplicationGraph::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_cell_size", "cell_size"), &GameplayReplicationGraph::set_cell_size);
	ClassDB::bind_method(D_METHOD("get_cell_size"), &GameplayReplicationGraph::get_cell_size);
	ClassDB::bind_method(D_METHOD("set_max_spatial_distance", "distance"), &GameplayReplicationGraph::set_max_spatial_distance);
	ClassDB::bind_method(D_METHOD("get_max_spatial_distance"), &GameplayReplicationGraph::get_max_spatial_distance);
	ClassDB::bind_method(D_METHOD("add_connection", "view"), &GameplayReplicationGraph::add_connection);
	ClassDB::bind_method(D_METHOD("update_connection", "view"), &GameplayReplicationGraph::update_connection);
	ClassDB::bind_method(D_METHOD("remove_connection", "peer_id"), &GameplayReplicationGraph::remove_connection);
	ClassDB::bind_method(D_METHOD("has_connection", "peer_id"), &GameplayReplicationGraph::has_connection);
	ClassDB::bind_method(D_METHOD("get_connection_peer_ids"), &GameplayReplicationGraph::get_connection_peer_ids);
	ClassDB::bind_method(D_METHOD("add_object", "object"), &GameplayReplicationGraph::add_object);
	ClassDB::bind_method(D_METHOD("update_object", "object"), &GameplayReplicationGraph::update_object);
	ClassDB::bind_method(D_METHOD("remove_object", "object_id"), &GameplayReplicationGraph::remove_object);
	ClassDB::bind_method(D_METHOD("has_object", "object_id"), &GameplayReplicationGraph::has_object);
	ClassDB::bind_method(D_METHOD("set_object_owner_peer_id", "object_id", "owner_peer_id"), &GameplayReplicationGraph::set_object_owner_peer_id);
	ClassDB::bind_method(D_METHOD("set_object_dormant", "object_id", "dormant", "change_serial"), &GameplayReplicationGraph::set_object_dormant, DEFVAL(uint64_t(0)));
	ClassDB::bind_method(D_METHOD("notify_object_dirty", "object_id", "change_serial"), &GameplayReplicationGraph::notify_object_dirty);
	ClassDB::bind_method(D_METHOD("wake_object", "object_id"), &GameplayReplicationGraph::wake_object);
	ClassDB::bind_method(D_METHOD("is_object_dormant", "object_id"), &GameplayReplicationGraph::is_object_dormant);
	ClassDB::bind_method(D_METHOD("plan_connection", "peer_id", "now_msec"), &GameplayReplicationGraph::plan_connection);
	ClassDB::bind_method(D_METHOD("record_send_result", "peer_id", "object_id", "now_msec", "actual_bytes", "success"), &GameplayReplicationGraph::record_send_result);
	ClassDB::bind_method(D_METHOD("get_relevant_object_ids", "peer_id"), &GameplayReplicationGraph::get_relevant_object_ids);
	ClassDB::bind_method(D_METHOD("get_last_plan_stats", "peer_id"), &GameplayReplicationGraph::get_last_plan_stats);
	ClassDB::bind_method(D_METHOD("clear"), &GameplayReplicationGraph::clear);

	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "cell_size", PROPERTY_HINT_RANGE, "0.001,1000000,0.001,or_greater,suffix:m"), "set_cell_size", "get_cell_size");
	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "max_spatial_distance", PROPERTY_HINT_RANGE, "0.001,1000000,0.001,or_greater,suffix:m"), "set_max_spatial_distance", "get_max_spatial_distance");
}

void GameplayReplicationGraph::set_cell_size(float p_cell_size) {
	ERR_FAIL_COND_MSG(!Math::is_finite(p_cell_size) || p_cell_size <= 0.0f, "Cell size must be finite and positive.");
	if (cell_size == p_cell_size) {
		return;
	}
	cell_size = p_cell_size;
	_rebuild_index();
}

float GameplayReplicationGraph::get_cell_size() const {
	return cell_size;
}

void GameplayReplicationGraph::set_max_spatial_distance(float p_distance) {
	ERR_FAIL_COND_MSG(!Math::is_finite(p_distance) || p_distance <= 0.0f, "Maximum spatial distance must be finite and positive.");
	for (const KeyValue<int, ObjectRuntime> &entry : objects) {
		ERR_FAIL_COND_MSG(entry.value.policy == GameplayRelevancyObject::POLICY_DISTANCE && entry.value.cull_distance > p_distance, "Maximum spatial distance cannot be smaller than an indexed object's cull distance.");
	}
	max_spatial_distance = p_distance;
}

float GameplayReplicationGraph::get_max_spatial_distance() const {
	return max_spatial_distance;
}

Error GameplayReplicationGraph::add_connection(const Ref<GameplayConnectionView> &p_view) {
	ERR_FAIL_COND_V(p_view.is_null() || p_view->get_peer_id() <= 1 || p_view->get_team_id() < 0 || p_view->get_bandwidth_budget_bytes() < 1 || !p_view->get_position().is_finite(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V_MSG(connections.has(p_view->get_peer_id()), ERR_ALREADY_EXISTS, "Connection view is already registered.");
	ConnectionRuntime connection;
	connection.position = p_view->get_position();
	connection.team_id = p_view->get_team_id();
	connection.bandwidth_budget_bytes = p_view->get_bandwidth_budget_bytes();
	connections.insert(p_view->get_peer_id(), connection);
	return OK;
}

Error GameplayReplicationGraph::update_connection(const Ref<GameplayConnectionView> &p_view) {
	ERR_FAIL_COND_V(p_view.is_null() || p_view->get_peer_id() <= 1 || p_view->get_team_id() < 0 || p_view->get_bandwidth_budget_bytes() < 1 || !p_view->get_position().is_finite(), ERR_INVALID_PARAMETER);
	ConnectionRuntime *connection = connections.getptr(p_view->get_peer_id());
	ERR_FAIL_NULL_V(connection, ERR_DOES_NOT_EXIST);
	connection->position = p_view->get_position();
	connection->team_id = p_view->get_team_id();
	connection->bandwidth_budget_bytes = p_view->get_bandwidth_budget_bytes();
	return OK;
}

bool GameplayReplicationGraph::remove_connection(int p_peer_id) {
	return connections.erase(p_peer_id);
}

bool GameplayReplicationGraph::has_connection(int p_peer_id) const {
	return connections.has(p_peer_id);
}

Array GameplayReplicationGraph::get_connection_peer_ids() const {
	Array result;
	for (const KeyValue<int, ConnectionRuntime> &entry : connections) {
		result.push_back(entry.key);
	}
	result.sort();
	return result;
}

static Error _gameplay_validate_relevancy_object(const Ref<GameplayRelevancyObject> &p_object, float p_max_spatial_distance) {
	ERR_FAIL_COND_V(p_object.is_null() || p_object->get_object_id() <= 0 || !p_object->get_position().is_finite(), ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(p_object->get_owner_peer_id() < 0 || p_object->get_team_id() < 0 || p_object->get_priority() < 0 || p_object->get_priority() > 1000 || p_object->get_estimated_update_bytes() < 1, ERR_INVALID_PARAMETER);
	ERR_FAIL_COND_V(p_object->get_policy() < GameplayRelevancyObject::POLICY_DISTANCE || p_object->get_policy() > GameplayRelevancyObject::POLICY_ALWAYS, ERR_INVALID_PARAMETER);
	if (p_object->get_policy() == GameplayRelevancyObject::POLICY_DISTANCE) {
		ERR_FAIL_COND_V(!Math::is_finite(p_object->get_cull_distance()) || p_object->get_cull_distance() <= 0.0f || p_object->get_cull_distance() > p_max_spatial_distance, ERR_INVALID_PARAMETER);
	}
	return OK;
}

Error GameplayReplicationGraph::add_object(const Ref<GameplayRelevancyObject> &p_object) {
	ERR_FAIL_COND_V(_gameplay_validate_relevancy_object(p_object, max_spatial_distance) != OK, ERR_INVALID_PARAMETER);
	const int object_id = p_object->get_object_id();
	ERR_FAIL_COND_V_MSG(objects.has(object_id), ERR_ALREADY_EXISTS, "Relevancy object is already registered.");
	ObjectRuntime object;
	object.position = p_object->get_position();
	object.owner_peer_id = p_object->get_owner_peer_id();
	object.team_id = p_object->get_team_id();
	object.policy = p_object->get_policy();
	object.cull_distance = p_object->get_cull_distance();
	object.priority = p_object->get_priority();
	object.update_interval_msec = p_object->get_update_interval_msec();
	object.estimated_update_bytes = p_object->get_estimated_update_bytes();
	objects.insert(object_id, object);
	_add_to_index(object_id, object);
	return OK;
}

Error GameplayReplicationGraph::update_object(const Ref<GameplayRelevancyObject> &p_object) {
	ERR_FAIL_COND_V(_gameplay_validate_relevancy_object(p_object, max_spatial_distance) != OK, ERR_INVALID_PARAMETER);
	ObjectRuntime *existing = objects.getptr(p_object->get_object_id());
	ERR_FAIL_NULL_V(existing, ERR_DOES_NOT_EXIST);
	const bool was_dormant = existing->dormant;
	const uint64_t dormancy_serial = existing->dormancy_change_serial;
	_remove_from_index(p_object->get_object_id(), *existing);
	existing->position = p_object->get_position();
	existing->owner_peer_id = p_object->get_owner_peer_id();
	existing->team_id = p_object->get_team_id();
	existing->policy = p_object->get_policy();
	existing->cull_distance = p_object->get_cull_distance();
	existing->priority = p_object->get_priority();
	existing->update_interval_msec = p_object->get_update_interval_msec();
	existing->estimated_update_bytes = p_object->get_estimated_update_bytes();
	existing->dormant = was_dormant;
	existing->dormancy_change_serial = dormancy_serial;
	_add_to_index(p_object->get_object_id(), *existing);
	return OK;
}

bool GameplayReplicationGraph::remove_object(int p_object_id) {
	ObjectRuntime *object = objects.getptr(p_object_id);
	if (!object) {
		return false;
	}
	_remove_from_index(p_object_id, *object);
	objects.erase(p_object_id);
	for (KeyValue<int, ConnectionRuntime> &entry : connections) {
		entry.value.relevant_objects.erase(p_object_id);
		entry.value.schedule.erase(p_object_id);
	}
	return true;
}

bool GameplayReplicationGraph::has_object(int p_object_id) const {
	return objects.has(p_object_id);
}

Error GameplayReplicationGraph::set_object_owner_peer_id(int p_object_id, int p_owner_peer_id) {
	ERR_FAIL_COND_V(p_owner_peer_id < 0, ERR_INVALID_PARAMETER);
	ObjectRuntime *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	object->owner_peer_id = p_owner_peer_id;
	return OK;
}

Error GameplayReplicationGraph::set_object_dormant(int p_object_id, bool p_dormant, uint64_t p_change_serial) {
	ObjectRuntime *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	object->dormant = p_dormant;
	if (p_dormant) {
		object->dormancy_change_serial = p_change_serial;
	}
	return OK;
}

Error GameplayReplicationGraph::notify_object_dirty(int p_object_id, uint64_t p_change_serial) {
	ObjectRuntime *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	if (object->dormant && p_change_serial > object->dormancy_change_serial) {
		object->dormant = false;
	}
	return OK;
}

Error GameplayReplicationGraph::wake_object(int p_object_id) {
	ObjectRuntime *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, ERR_DOES_NOT_EXIST);
	object->dormant = false;
	return OK;
}

bool GameplayReplicationGraph::is_object_dormant(int p_object_id) const {
	const ObjectRuntime *object = objects.getptr(p_object_id);
	ERR_FAIL_NULL_V(object, false);
	return object->dormant;
}

Dictionary GameplayReplicationGraph::plan_connection(int p_peer_id, uint64_t p_now_msec) {
	Dictionary empty;
	ConnectionRuntime *connection = connections.getptr(p_peer_id);
	ERR_FAIL_NULL_V(connection, empty);
	Dictionary relevance = _refresh_relevance(p_peer_id, *connection);
	Vector<Candidate> due;
	for (const int object_id : connection->relevant_objects) {
		const ObjectRuntime *object = objects.getptr(object_id);
		if (!object || object->dormant) {
			continue;
		}
		ScheduleRuntime &schedule = connection->schedule[object_id];
		if (schedule.has_sent && p_now_msec < schedule.last_sent_msec + object->update_interval_msec) {
			continue;
		}
		Candidate candidate;
		candidate.object_id = object_id;
		candidate.priority = object->priority;
		candidate.score = uint64_t(object->priority) + schedule.starvation;
		candidate.estimated_bytes = object->estimated_update_bytes;
		due.push_back(candidate);
	}
	due.sort_custom<CandidateComparator>();

	Array selected;
	int estimated_bytes = 0;
	for (const Candidate &candidate : due) {
		ScheduleRuntime &schedule = connection->schedule[candidate.object_id];
		if (candidate.estimated_bytes <= connection->bandwidth_budget_bytes - estimated_bytes) {
			selected.push_back(candidate.object_id);
			estimated_bytes += candidate.estimated_bytes;
		} else {
			schedule.starvation++;
		}
	}
	Dictionary stats;
	stats["peer_id"] = p_peer_id;
	stats["candidate_count"] = relevance.get("candidate_count", 0);
	stats["relevant_count"] = connection->relevant_objects.size();
	stats["due_count"] = due.size();
	stats["selected_count"] = selected.size();
	stats["bandwidth_budget_bytes"] = connection->bandwidth_budget_bytes;
	stats["estimated_bytes"] = estimated_bytes;
	stats["actual_bytes"] = 0;
	stats["total_estimated_bytes"] = int64_t(connection->total_estimated_bytes);
	stats["total_actual_bytes"] = int64_t(connection->total_actual_bytes);
	stats["entered"] = relevance.get("entered", Array());
	stats["left"] = relevance.get("left", Array());
	stats["selected"] = selected;
	connection->last_stats = stats;
	return stats;
}

Error GameplayReplicationGraph::record_send_result(int p_peer_id, int p_object_id, uint64_t p_now_msec, int p_actual_bytes, bool p_success) {
	ERR_FAIL_COND_V(p_actual_bytes < 0, ERR_INVALID_PARAMETER);
	ConnectionRuntime *connection = connections.getptr(p_peer_id);
	ERR_FAIL_NULL_V(connection, ERR_DOES_NOT_EXIST);
	ERR_FAIL_COND_V(!objects.has(p_object_id) || !connection->relevant_objects.has(p_object_id), ERR_DOES_NOT_EXIST);
	ScheduleRuntime &schedule = connection->schedule[p_object_id];
	if (p_success) {
		schedule.has_sent = true;
		schedule.last_sent_msec = p_now_msec;
		schedule.starvation = 0;
		connection->last_stats["actual_bytes"] = int(connection->last_stats.get("actual_bytes", 0)) + p_actual_bytes;
		if (p_actual_bytes > 0) {
			const ObjectRuntime *object = objects.getptr(p_object_id);
			if (object) {
				connection->total_estimated_bytes += object->estimated_update_bytes;
			}
		}
		connection->total_actual_bytes += p_actual_bytes;
		connection->last_stats["total_estimated_bytes"] = int64_t(connection->total_estimated_bytes);
		connection->last_stats["total_actual_bytes"] = int64_t(connection->total_actual_bytes);
	} else {
		schedule.starvation++;
	}
	return OK;
}

Array GameplayReplicationGraph::get_relevant_object_ids(int p_peer_id) const {
	Array result;
	const ConnectionRuntime *connection = connections.getptr(p_peer_id);
	ERR_FAIL_NULL_V(connection, result);
	for (const int object_id : connection->relevant_objects) {
		result.push_back(object_id);
	}
	result.sort();
	return result;
}

Dictionary GameplayReplicationGraph::get_last_plan_stats(int p_peer_id) const {
	const ConnectionRuntime *connection = connections.getptr(p_peer_id);
	ERR_FAIL_NULL_V(connection, Dictionary());
	return connection->last_stats;
}

void GameplayReplicationGraph::clear() {
	objects.clear();
	connections.clear();
	spatial_grid.clear();
	non_spatial_objects.clear();
}
