/**************************************************************************/
/*  gameplay_prediction.h                                                 */
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

#pragma once

#include "adapters/GameplayPredictionCore.h"
#include "gameplay_relevancy.h"
#include "gameplay_session.h"

#include "core/io/resource.h"
#include "core/templates/hash_map.h"
#include "scene/main/multiplayer_peer.h"

class GameplayClientPrediction : public RefCounted {
	GDCLASS(GameplayClientPrediction, RefCounted);

	struct HistoryEntry {
		Ref<GameplayPredictionInput> input;
		Ref<GameplayPredictionState> predicted_state;
	};

	Ref<GameplayPredictionModel> model;
	Ref<GameplayPredictionState> predicted_state;
	Vector<HistoryEntry> history;
	uint64_t next_sequence = 1;
	uint64_t last_confirmed_sequence = 0;
	uint64_t rate_window_started_msec = 0;
	int inputs_in_rate_window = 0;
	int max_history = 256;
	int max_inputs_per_second = 120;
	float correction_threshold = 0.001f;
	int correction_count = 0;
	int last_replayed_input_count = 0;
	String last_rejection_reason;

protected:
	static void _bind_methods();

public:
	GameplayClientPrediction();

	void set_model(const Ref<GameplayPredictionModel> &p_model);
	Ref<GameplayPredictionModel> get_model() const;
	void set_initial_state(const Ref<GameplayPredictionState> &p_state);
	Ref<GameplayPredictionState> get_predicted_state() const;
	void set_max_history(int p_max_history);
	int get_max_history() const;
	void set_max_inputs_per_second(int p_max_inputs);
	int get_max_inputs_per_second() const;
	void set_correction_threshold(float p_threshold);
	float get_correction_threshold() const;
	Ref<GameplayPredictionInput> predict_input(const Vector3 &p_input, uint64_t p_now_msec);
	Dictionary apply_authoritative_state(const Ref<GameplayPredictionState> &p_state);
	Array get_unconfirmed_inputs() const;
	int get_unconfirmed_input_count() const;
	uint64_t get_last_confirmed_sequence() const;
	int get_correction_count() const;
	int get_last_replayed_input_count() const;
	String get_last_rejection_reason() const;
	void clear();
};

class GameplayServerPrediction : public RefCounted {
	GDCLASS(GameplayServerPrediction, RefCounted);

	struct ObjectRuntime {
		int owner_peer_id = 0;
		Ref<GameplayPredictionModel> model;
		Ref<GameplayPredictionState> state;
		uint64_t rate_window_started_msec = 0;
		int inputs_in_rate_window = 0;
	};

	HashMap<int, ObjectRuntime> objects;
	int max_sequence_gap = 32;
	int max_inputs_per_second = 120;
	String last_rejection_reason;
	int rejected_input_count = 0;

	Dictionary _reject(const String &p_reason);

protected:
	static void _bind_methods();

public:
	void set_max_sequence_gap(int p_gap);
	int get_max_sequence_gap() const;
	void set_max_inputs_per_second(int p_max_inputs);
	int get_max_inputs_per_second() const;
	Error register_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayPredictionModel> &p_model, const Ref<GameplayPredictionState> &p_initial_state = Ref<GameplayPredictionState>());
	bool unregister_object(int p_object_id);
	Error set_object_owner_peer_id(int p_object_id, int p_owner_peer_id);
	int get_object_owner_peer_id(int p_object_id) const;
	Ref<GameplayPredictionState> get_object_state(int p_object_id) const;
	Dictionary consume_input(int p_transport_sender_peer_id, int p_object_id, const Ref<GameplayPredictionInput> &p_input, uint64_t p_now_msec);
	String get_last_rejection_reason() const;
	int get_rejected_input_count() const;
	void clear();
};

class GameplayNetworkSimulator : public RefCounted {
	GDCLASS(GameplayNetworkSimulator, RefCounted);

	struct QueuedPacket {
		int target_peer_id = 0;
		Dictionary message;
		uint64_t delivery_time_msec = 0;
	};

	uint64_t latency_msec = 0;
	uint64_t jitter_msec = 0;
	int loss_permyriad = 0;
	int max_queued_packets = 1024;
	uint64_t random_state = 1;
	Vector<QueuedPacket> queue;
	uint64_t dropped_packet_count = 0;
	uint64_t overflow_packet_count = 0;

	uint64_t _next_random();

protected:
	static void _bind_methods();

public:
	void set_latency_msec(uint64_t p_latency_msec);
	uint64_t get_latency_msec() const;
	void set_jitter_msec(uint64_t p_jitter_msec);
	uint64_t get_jitter_msec() const;
	void set_loss_permyriad(int p_loss_permyriad);
	int get_loss_permyriad() const;
	void set_max_queued_packets(int p_max_packets);
	int get_max_queued_packets() const;
	void set_seed(uint64_t p_seed);
	uint64_t get_seed() const;
	Dictionary enqueue(int p_target_peer_id, const Dictionary &p_message, uint64_t p_now_msec);
	Array drain(uint64_t p_now_msec);
	int discard_target(int p_target_peer_id);
	int get_queued_packet_count() const;
	uint64_t get_dropped_packet_count() const;
	uint64_t get_overflow_packet_count() const;
	void clear();
};

class GameplayNetworkPrediction : public Node {
	GDCLASS(GameplayNetworkPrediction, Node);

	bool server = false;
	Ref<MultiplayerPeer> multiplayer_peer;
	ObjectID session_manager_id;
	Ref<GameplayServerPrediction> authority;
	Ref<GameplayReplicationGraph> replication_graph;
	Ref<GameplayNetworkSimulator> network_simulator;
	HashMap<int, Ref<GameplayClientPrediction>> owned_objects;
	HashMap<int, Ref<GameplayInterpolationBuffer>> remote_objects;
	uint64_t resend_interval_msec = 50;
	HashMap<int, uint64_t> last_resend_msec;
	String last_rejection_reason;
	int rejected_packet_count = 0;

	Error _send_dictionary(int p_target_peer_id, const Dictionary &p_message);
	Error _queue_snapshot(int p_target_peer_id, int p_object_id, const Ref<GameplayPredictionState> &p_state, uint64_t p_now_msec);
	Error _reject(const String &p_reason);
	bool _is_joined_peer(int p_peer_id) const;

protected:
	static void _bind_methods();

public:
	GameplayNetworkPrediction();

	void configure_server(const Ref<MultiplayerPeer> &p_peer, GameplaySessionManager *p_session_manager);
	void configure_client(const Ref<MultiplayerPeer> &p_peer);
	void clear_transport();
	void peer_disconnected(int p_peer_id);
	bool is_server() const;
	void set_network_simulator(const Ref<GameplayNetworkSimulator> &p_simulator);
	Ref<GameplayNetworkSimulator> get_network_simulator() const;
	void set_replication_graph(const Ref<GameplayReplicationGraph> &p_graph);
	Ref<GameplayReplicationGraph> get_replication_graph() const;
	void set_resend_interval_msec(uint64_t p_interval_msec);
	uint64_t get_resend_interval_msec() const;
	Error register_server_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayPredictionModel> &p_model, const Ref<GameplayPredictionState> &p_initial_state = Ref<GameplayPredictionState>());
	Error set_server_object_owner_peer_id(int p_object_id, int p_owner_peer_id);
	Error register_owned_client_object(int p_object_id, const Ref<GameplayClientPrediction> &p_prediction);
	Error register_remote_client_object(int p_object_id, const Ref<GameplayInterpolationBuffer> &p_buffer);
	Ref<GameplayClientPrediction> get_owned_client_object(int p_object_id) const;
	Ref<GameplayInterpolationBuffer> get_remote_client_object(int p_object_id) const;
	Ref<GameplayPredictionState> get_server_object_state(int p_object_id) const;
	Ref<GameplayPredictionInput> submit_local_input(int p_object_id, const Vector3 &p_input, uint64_t p_now_msec);
	Error receive_packet(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec);
	bool handles_message(const Dictionary &p_message) const;
	Error poll(uint64_t p_now_msec);
	String get_last_rejection_reason() const;
	int get_rejected_packet_count() const;
};
