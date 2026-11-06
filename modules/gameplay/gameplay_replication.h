/**************************************************************************/
/*  gameplay_replication.h                                                */
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

#include "gameplay_relevancy.h"
#include "gameplay_session.h"

#include "core/io/resource.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"
#include "scene/main/multiplayer_peer.h"

class GameplayReplicationProperty : public Resource {
	GDCLASS(GameplayReplicationProperty, Resource);

public:
	enum Condition {
		CONDITION_ALWAYS,
		CONDITION_INITIAL_ONLY,
		CONDITION_OWNER_ONLY,
		CONDITION_SKIP_OWNER,
	};

private:
	StringName property_name;
	Condition condition = CONDITION_ALWAYS;
	bool rep_notify = false;
	uint64_t update_interval_msec = 0;

protected:
	static void _bind_methods();

public:
	void set_property_name(const StringName &p_name);
	StringName get_property_name() const;
	void set_condition(Condition p_condition);
	Condition get_condition() const;
	void set_rep_notify(bool p_enabled);
	bool is_rep_notify() const;
	void set_update_interval_msec(uint64_t p_interval_msec);
	uint64_t get_update_interval_msec() const;
};

VARIANT_ENUM_CAST(GameplayReplicationProperty::Condition);

class GameplayRPCConfig : public Resource {
	GDCLASS(GameplayRPCConfig, Resource);

public:
	enum Direction {
		DIRECTION_SERVER,
		DIRECTION_OWNER,
		DIRECTION_CLIENT,
		DIRECTION_MULTICAST,
	};

private:
	StringName rpc_name;
	Direction direction = DIRECTION_SERVER;
	bool require_owner = false;
	int max_payload_bytes = 4096;

protected:
	static void _bind_methods();

public:
	void set_rpc_name(const StringName &p_name);
	StringName get_rpc_name() const;
	void set_direction(Direction p_direction);
	Direction get_direction() const;
	void set_require_owner(bool p_require_owner);
	bool is_owner_required() const;
	void set_max_payload_bytes(int p_max_payload_bytes);
	int get_max_payload_bytes() const;
};

VARIANT_ENUM_CAST(GameplayRPCConfig::Direction);

class GameplayReplicationState : public RefCounted {
	GDCLASS(GameplayReplicationState, RefCounted);

	struct PropertyRuntime {
		Ref<GameplayReplicationProperty> descriptor;
		Variant value;
		uint64_t revision = 1;
		uint64_t received_revision = 0;
		HashMap<int, uint64_t> sent_revisions;
		HashMap<int, uint64_t> last_sent_msec;
		HashSet<int> initial_sent;
	};

	HashMap<StringName, PropertyRuntime> properties;
	HashSet<int> registered_peers;
	Callable rep_notify_handler;
	uint64_t change_serial = 1;

protected:
	static void _bind_methods();

public:
	Error add_property(const Ref<GameplayReplicationProperty> &p_descriptor, const Variant &p_initial_value = Variant());
	bool remove_property(const StringName &p_name);
	bool has_property(const StringName &p_name) const;
	Array get_property_descriptors() const;
	Error set_property_value(const StringName &p_name, const Variant &p_value);
	Variant get_property_value(const StringName &p_name) const;
	Error mark_property_dirty(const StringName &p_name);
	bool is_property_dirty(const StringName &p_name) const;
	bool is_property_dirty_for_peer(const StringName &p_name, int p_peer_id) const;
	void register_peer(int p_peer_id);
	void unregister_peer(int p_peer_id);
	Array collect_updates(int p_peer_id, int p_owner_peer_id, uint64_t p_now_msec);
	void reset_peer_updates(int p_peer_id, const Array &p_updates);
	Error apply_updates(const Array &p_updates);
	uint64_t get_change_serial() const;
	void set_rep_notify_handler(const Callable &p_handler);
	Callable get_rep_notify_handler() const;
};

class GameplayReplicationFragmenter : public RefCounted {
	GDCLASS(GameplayReplicationFragmenter, RefCounted);

	struct Assembly {
		uint64_t created_msec = 0;
		int chunk_count = 0;
		int total_size = 0;
		int received_size = 0;
		Vector<PackedByteArray> chunks;
		Vector<uint8_t> received;
	};

	int chunk_payload_bytes = 512;
	int max_transfer_bytes = 1024 * 1024;
	int max_chunks = 2048;
	int max_pending_assemblies = 16;
	uint64_t assembly_timeout_msec = 5000;
	HashMap<String, Assembly> assemblies;
	HashMap<int, uint64_t> last_completed_sequence;
	String last_error;

	Dictionary _reject(const String &p_reason);

protected:
	static void _bind_methods();

public:
	void set_chunk_payload_bytes(int p_bytes);
	int get_chunk_payload_bytes() const;
	void set_max_transfer_bytes(int p_bytes);
	int get_max_transfer_bytes() const;
	void set_max_chunks(int p_chunks);
	int get_max_chunks() const;
	void set_max_pending_assemblies(int p_count);
	int get_max_pending_assemblies() const;
	void set_assembly_timeout_msec(uint64_t p_timeout_msec);
	uint64_t get_assembly_timeout_msec() const;
	String get_last_error() const;
	int get_pending_assembly_count() const;
	Array fragment(uint64_t p_sequence, const PackedByteArray &p_payload);
	Dictionary accept_fragment(int p_sender_peer_id, const Dictionary &p_fragment, uint64_t p_now_msec);
	int expire_assemblies(uint64_t p_now_msec);
	void clear();
};

class GameplayMultiplayerReplication : public Node {
	GDCLASS(GameplayMultiplayerReplication, Node);

	struct RPCBinding {
		Ref<GameplayRPCConfig> config;
		Callable handler;
	};

	struct ObjectBinding {
		int owner_peer_id = 0;
		Ref<GameplayReplicationState> state;
		HashMap<StringName, RPCBinding> rpcs;
	};

	bool server = false;
	Ref<MultiplayerPeer> multiplayer_peer;
	ObjectID session_manager_id;
	HashMap<int, ObjectBinding> objects;
	Ref<GameplayReplicationFragmenter> fragmenter;
	Ref<GameplayReplicationGraph> replication_graph;
	uint64_t next_transfer_sequence = 1;
	String last_rejection_reason;
	int rejected_packet_count = 0;

	Error _reject_rpc(int p_sender_peer_id, const StringName &p_rpc_name, const String &p_reason);
	Error _reject_replication(const String &p_reason);
	bool _is_joined_peer(int p_peer_id) const;
	Error _send_dictionary(int p_target_peer_id, const Dictionary &p_message, int *r_sent_bytes = nullptr);
	Error _handle_rpc(int p_transport_sender_peer_id, const Dictionary &p_message);
	Error _handle_replication_chunk(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec);
	Error _send_replication_payload(int p_peer_id, const Dictionary &p_payload, int *r_sent_bytes = nullptr);
	Error _reject_relevancy(int p_sender_peer_id, const String &p_reason);

protected:
	static void _bind_methods();

public:
	void configure_server(const Ref<MultiplayerPeer> &p_peer, GameplaySessionManager *p_session_manager);
	void configure_client(const Ref<MultiplayerPeer> &p_peer);
	void clear_transport();
	bool is_server() const;
	Error register_object(int p_object_id, int p_owner_peer_id, const Ref<GameplayReplicationState> &p_state = Ref<GameplayReplicationState>());
	bool unregister_object(int p_object_id);
	Error set_object_owner_peer_id(int p_object_id, int p_owner_peer_id);
	int get_object_owner_peer_id(int p_object_id) const;
	Error register_rpc(int p_object_id, const Ref<GameplayRPCConfig> &p_config, const Callable &p_handler);
	Error invoke_rpc(int p_object_id, const StringName &p_rpc_name, const Array &p_arguments = Array(), int p_target_peer_id = 0);
	Error replicate(uint64_t p_now_msec);
	Error receive_packet(int p_transport_sender_peer_id, const Dictionary &p_message, uint64_t p_now_msec);
	bool handles_message(const Dictionary &p_message) const;
	void expire_reassemblies(uint64_t p_now_msec);
	void set_fragmenter(const Ref<GameplayReplicationFragmenter> &p_fragmenter);
	Ref<GameplayReplicationFragmenter> get_fragmenter() const;
	Error set_replication_graph(const Ref<GameplayReplicationGraph> &p_graph);
	Ref<GameplayReplicationGraph> get_replication_graph() const;
	Error update_server_connection_view(const Ref<GameplayConnectionView> &p_view);
	Error set_object_dormant(int p_object_id, bool p_dormant);
	Error wake_object(int p_object_id);
	String get_last_rejection_reason() const;
	int get_rejected_packet_count() const;
};
