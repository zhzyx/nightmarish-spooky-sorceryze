/**************************************************************************/
/*  gameplay_session.h                                                    */
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

#include "gameplay_match.h"

#include "core/templates/hash_map.h"
#include "core/variant/typed_array.h"

class GameplayUserSession;

class GameplayConnection : public RefCounted {
	GDCLASS(GameplayConnection, RefCounted);

public:
	enum State {
		STATE_TRANSPORT_CONNECTED,
		STATE_VERSION_VERIFIED,
		STATE_AUTHENTICATED,
		STATE_ADMITTED,
		STATE_PLAYER_CREATED,
		STATE_SPAWNED,
		STATE_DISCONNECTED,
		STATE_REJECTED,
	};

private:
	friend class GameplaySessionManager;

	int peer_id = 0;
	State state = STATE_TRANSPORT_CONNECTED;
	ObjectID session_id;
	String rejection_reason;

	void _set_state(State p_state);
	void _set_session(GameplayUserSession *p_session);
	void _reject(const String &p_reason);

protected:
	static void _bind_methods();

public:
	int get_peer_id() const;
	State get_state() const;
	GameplayUserSession *get_session() const;
	String get_rejection_reason() const;
};

VARIANT_ENUM_CAST(GameplayConnection::State);

class GameplayUserSession : public Node {
	GDCLASS(GameplayUserSession, Node);

	friend class GameplaySessionManager;

	String user_id;
	String stable_session_id;
	String reconnect_token;
	int peer_id = 0;
	bool active = false;
	uint64_t disconnected_at_msec = 0;
	ObjectID player_state_id;
	ObjectID controller_id;

	void _set_identity(const String &p_user_id, const String &p_session_id, const String &p_reconnect_token);
	void _bind_peer(int p_peer_id);
	void _deactivate(uint64_t p_now_msec);
	void _set_player_state(GameplayPlayerState *p_player_state);
	void _set_controller(GameplayController *p_controller);

protected:
	static void _bind_methods();

public:
	String get_user_id() const;
	String get_session_id() const;
	String get_reconnect_token() const;
	int get_peer_id() const;
	bool is_active() const;
	uint64_t get_disconnected_at_msec() const;
	GameplayPlayerState *get_player_state() const;
	GameplayController *get_controller() const;
};

class GameplaySessionManager : public Node {
	GDCLASS(GameplaySessionManager, Node);

	String protocol_version = "1";
	uint64_t disconnect_grace_period_msec = 30000;
	bool accepting_connections = true;
	ObjectID game_mode_id;
	HashMap<int, Ref<GameplayConnection>> connections;
	Vector<ObjectID> session_ids;

	uint64_t _resolve_time(uint64_t p_now_msec) const;
	void _destroy_session(GameplayUserSession *p_session, bool p_emit_signal);
	GameplayUserSession *_find_session_for_user(const String &p_user_id) const;

protected:
	static void _bind_methods();

public:
	void set_protocol_version(const String &p_version);
	String get_protocol_version() const;
	void set_disconnect_grace_period_msec(uint64_t p_grace_period_msec);
	uint64_t get_disconnect_grace_period_msec() const;
	void set_accepting_connections(bool p_accepting);
	bool is_accepting_connections() const;
	void set_game_mode(GameplayGameMode *p_game_mode);
	GameplayGameMode *get_game_mode() const;

	Error transport_connected(int p_peer_id);
	Error verify_version(int p_peer_id, const String &p_version);
	Error authenticate(int p_peer_id, const String &p_user_id, const String &p_session_id, const String &p_reconnect_token);
	Error admit(int p_peer_id);
	Error create_player(int p_peer_id);
	Error spawn_player(int p_peer_id);
	Error reject(int p_peer_id, const String &p_reason);
	void transport_disconnected(int p_peer_id, uint64_t p_now_msec = UINT64_MAX);
	int expire_disconnected(uint64_t p_now_msec = UINT64_MAX);
	void shutdown();

	Ref<GameplayConnection> get_connection(int p_peer_id) const;
	GameplayUserSession *get_session_by_peer(int p_peer_id) const;
	GameplayUserSession *get_session(const String &p_session_id) const;
	TypedArray<GameplayUserSession> get_sessions() const;
	int get_active_session_count() const;

	~GameplaySessionManager();
};
