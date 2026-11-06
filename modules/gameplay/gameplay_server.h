/**************************************************************************/
/*  gameplay_server.h                                                     */
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

#include "gameplay_session.h"

#include "core/io/resource.h"
#include "core/templates/hash_set.h"
#include "scene/main/multiplayer_peer.h"

class GameplayServerConfig : public Resource {
	GDCLASS(GameplayServerConfig, Resource);

	String bind_address = "*";
	int port = 7000;
	int max_clients = 32;
	String protocol_version = "1";
	uint64_t disconnect_grace_period_msec = 30000;
	uint64_t shutdown_timeout_msec = 10000;

protected:
	static void _bind_methods();

public:
	void set_bind_address(const String &p_address);
	String get_bind_address() const;
	void set_port(int p_port);
	int get_port() const;
	void set_max_clients(int p_max_clients);
	int get_max_clients() const;
	void set_protocol_version(const String &p_version);
	String get_protocol_version() const;
	void set_disconnect_grace_period_msec(uint64_t p_msec);
	uint64_t get_disconnect_grace_period_msec() const;
	void set_shutdown_timeout_msec(uint64_t p_msec);
	uint64_t get_shutdown_timeout_msec() const;

	Error apply_command_line(const PackedStringArray &p_arguments);
};

class GameplayMultiplayerReplication;
class GameplayNetworkPrediction;

class GameplayDedicatedServer : public Node {
	GDCLASS(GameplayDedicatedServer, Node);

	Ref<GameplayServerConfig> config;
	Ref<MultiplayerPeer> multiplayer_peer;
	ObjectID session_manager_id;
	ObjectID replication_id;
	ObjectID prediction_id;
	Callable authenticator;
	Callable admission_check;
	HashSet<int> transport_peers;
	bool running = false;
	bool shutting_down = false;
	uint64_t shutdown_deadline_msec = 0;
	int bound_port = 0;

	void _peer_connected(int p_peer_id);
	void _peer_disconnected(int p_peer_id);
	void _handle_packet(int p_peer_id, const Dictionary &p_message);
	void _reject_peer(int p_peer_id, const String &p_reason);
	Error _send_message(int p_peer_id, const Dictionary &p_message);
	void _finish_shutdown();

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	void set_authenticator(const Callable &p_authenticator);
	Callable get_authenticator() const;
	void set_admission_check(const Callable &p_admission_check);
	Callable get_admission_check() const;

	Error start(const Ref<GameplayServerConfig> &p_config, GameplaySessionManager *p_session_manager);
	Error start_from_command_line(GameplaySessionManager *p_session_manager, const PackedStringArray &p_arguments = PackedStringArray());
	Error poll();
	void refuse_new_connections();
	void begin_shutdown(int64_t p_timeout_msec = -1);
	void stop_now();
	bool is_running() const;
	bool is_shutting_down() const;
	bool is_refusing_new_connections() const;
	int get_bound_port() const;
	int get_transport_peer_count() const;
	GameplaySessionManager *get_session_manager() const;
	Ref<MultiplayerPeer> get_multiplayer_peer() const;
	void set_replication(GameplayMultiplayerReplication *p_replication);
	GameplayMultiplayerReplication *get_replication() const;
	void set_prediction(GameplayNetworkPrediction *p_prediction);
	GameplayNetworkPrediction *get_prediction() const;

	~GameplayDedicatedServer();
};

class GameplaySessionClient : public Node {
	GDCLASS(GameplaySessionClient, Node);

	Ref<MultiplayerPeer> multiplayer_peer;
	ObjectID replication_id;
	ObjectID prediction_id;
	String protocol_version;
	String auth_token;
	String reconnect_token;
	String user_id;
	String stable_session_id;
	String rejection_reason;
	GameplayConnection::State state = GameplayConnection::STATE_DISCONNECTED;
	bool version_sent = false;

	Error _send_message(const Dictionary &p_message);
	void _handle_message(const Dictionary &p_message);
	void _set_state(GameplayConnection::State p_state);

protected:
	static void _bind_methods();

public:
	Error connect_to_server(const String &p_address, int p_port, const String &p_protocol_version, const String &p_auth_token, const String &p_reconnect_token = String());
	Error poll();
	void disconnect_from_server();
	GameplayConnection::State get_state() const;
	bool is_joined() const;
	int get_peer_id() const;
	String get_user_id() const;
	String get_session_id() const;
	String get_reconnect_token() const;
	String get_rejection_reason() const;
	Ref<MultiplayerPeer> get_multiplayer_peer() const;
	void set_replication(GameplayMultiplayerReplication *p_replication);
	GameplayMultiplayerReplication *get_replication() const;
	void set_prediction(GameplayNetworkPrediction *p_prediction);
	GameplayNetworkPrediction *get_prediction() const;

	~GameplaySessionClient();
};
