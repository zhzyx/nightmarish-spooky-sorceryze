/**************************************************************************/
/*  gameplay_relevancy.h                                                  */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including  */
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

#pragma once

#include "core/io/resource.h"
#include "core/math/vector3.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"

class GameplayConnectionView : public RefCounted {
	GDCLASS(GameplayConnectionView, RefCounted);

	int peer_id = 0;
	Vector3 position;
	int team_id = 0;
	int bandwidth_budget_bytes = 4096;

protected:
	static void _bind_methods();

public:
	void set_peer_id(int p_peer_id);
	int get_peer_id() const;
	void set_position(const Vector3 &p_position);
	Vector3 get_position() const;
	void set_team_id(int p_team_id);
	int get_team_id() const;
	void set_bandwidth_budget_bytes(int p_bytes);
	int get_bandwidth_budget_bytes() const;
};

class GameplayRelevancyObject : public RefCounted {
	GDCLASS(GameplayRelevancyObject, RefCounted);

public:
	enum Policy {
		POLICY_DISTANCE,
		POLICY_OWNER_ONLY,
		POLICY_TEAM_ONLY,
		POLICY_OWNER_OR_TEAM,
		POLICY_ALWAYS,
	};

private:
	int object_id = 0;
	Vector3 position;
	int owner_peer_id = 0;
	int team_id = 0;
	Policy policy = POLICY_DISTANCE;
	float cull_distance = 100.0f;
	int priority = 1;
	uint64_t update_interval_msec = 0;
	int estimated_update_bytes = 256;

protected:
	static void _bind_methods();

public:
	void set_object_id(int p_object_id);
	int get_object_id() const;
	void set_position(const Vector3 &p_position);
	Vector3 get_position() const;
	void set_owner_peer_id(int p_peer_id);
	int get_owner_peer_id() const;
	void set_team_id(int p_team_id);
	int get_team_id() const;
	void set_policy(Policy p_policy);
	Policy get_policy() const;
	void set_cull_distance(float p_distance);
	float get_cull_distance() const;
	void set_priority(int p_priority);
	int get_priority() const;
	void set_update_interval_msec(uint64_t p_interval_msec);
	uint64_t get_update_interval_msec() const;
	void set_estimated_update_bytes(int p_bytes);
	int get_estimated_update_bytes() const;
};

VARIANT_ENUM_CAST(GameplayRelevancyObject::Policy);

class GameplayReplicationGraph : public RefCounted {
	GDCLASS(GameplayReplicationGraph, RefCounted);

	struct ObjectRuntime {
		Vector3 position;
		int owner_peer_id = 0;
		int team_id = 0;
		GameplayRelevancyObject::Policy policy = GameplayRelevancyObject::POLICY_DISTANCE;
		float cull_distance = 100.0f;
		int priority = 1;
		uint64_t update_interval_msec = 0;
		int estimated_update_bytes = 256;
		bool dormant = false;
		uint64_t dormancy_change_serial = 0;
	};

	struct ScheduleRuntime {
		bool has_sent = false;
		uint64_t last_sent_msec = 0;
		uint64_t starvation = 0;
	};

	struct ConnectionRuntime {
		Vector3 position;
		int team_id = 0;
		int bandwidth_budget_bytes = 4096;
		HashSet<int> relevant_objects;
		HashMap<int, ScheduleRuntime> schedule;
		Dictionary last_stats;
		uint64_t total_estimated_bytes = 0;
		uint64_t total_actual_bytes = 0;
	};

	struct Candidate {
		int object_id = 0;
		uint64_t score = 0;
		int priority = 0;
		int estimated_bytes = 0;
	};

	struct CandidateComparator {
		_FORCE_INLINE_ bool operator()(const Candidate &p_left, const Candidate &p_right) const {
			if (p_left.score != p_right.score) {
				return p_left.score > p_right.score;
			}
			if (p_left.priority != p_right.priority) {
				return p_left.priority > p_right.priority;
			}
			return p_left.object_id < p_right.object_id;
		}
	};

	float cell_size = 100.0f;
	float max_spatial_distance = 1000.0f;
	HashMap<int, ObjectRuntime> objects;
	HashMap<int, ConnectionRuntime> connections;
	HashMap<Vector3i, HashSet<int>> spatial_grid;
	HashSet<int> non_spatial_objects;

	Vector3i _cell_for_position(const Vector3 &p_position) const;
	void _add_to_index(int p_object_id, const ObjectRuntime &p_object);
	void _remove_from_index(int p_object_id, const ObjectRuntime &p_object);
	void _rebuild_index();
	bool _is_relevant(const ObjectRuntime &p_object, int p_peer_id, const ConnectionRuntime &p_connection) const;
	HashSet<int> _collect_candidates(const ConnectionRuntime &p_connection) const;
	Dictionary _refresh_relevance(int p_peer_id, ConnectionRuntime &p_connection);

protected:
	static void _bind_methods();

public:
	void set_cell_size(float p_cell_size);
	float get_cell_size() const;
	void set_max_spatial_distance(float p_distance);
	float get_max_spatial_distance() const;

	Error add_connection(const Ref<GameplayConnectionView> &p_view);
	Error update_connection(const Ref<GameplayConnectionView> &p_view);
	bool remove_connection(int p_peer_id);
	bool has_connection(int p_peer_id) const;
	Array get_connection_peer_ids() const;

	Error add_object(const Ref<GameplayRelevancyObject> &p_object);
	Error update_object(const Ref<GameplayRelevancyObject> &p_object);
	bool remove_object(int p_object_id);
	bool has_object(int p_object_id) const;
	Error set_object_owner_peer_id(int p_object_id, int p_owner_peer_id);
	Error set_object_dormant(int p_object_id, bool p_dormant, uint64_t p_change_serial = 0);
	Error notify_object_dirty(int p_object_id, uint64_t p_change_serial);
	Error wake_object(int p_object_id);
	bool is_object_dormant(int p_object_id) const;

	Dictionary plan_connection(int p_peer_id, uint64_t p_now_msec);
	Error record_send_result(int p_peer_id, int p_object_id, uint64_t p_now_msec, int p_actual_bytes, bool p_success);
	Array get_relevant_object_ids(int p_peer_id) const;
	Dictionary get_last_plan_stats(int p_peer_id) const;
	void clear();
};
