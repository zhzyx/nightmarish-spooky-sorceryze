/**************************************************************************/
/*  gameplay_session.cpp                                                  */
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

#include "gameplay_session.h"

#include "core/object/class_db.h"
#include "core/os/os.h"

template <typename T>
static T *_gameplay_session_object(ObjectID p_id) {
	return Object::cast_to<T>(ObjectDB::get_instance(p_id));
}

void GameplayConnection::_bind_methods() {
	ClassDB::bind_method(D_METHOD("get_peer_id"), &GameplayConnection::get_peer_id);
	ClassDB::bind_method(D_METHOD("get_state"), &GameplayConnection::get_state);
	ClassDB::bind_method(D_METHOD("get_session"), &GameplayConnection::get_session);
	ClassDB::bind_method(D_METHOD("get_rejection_reason"), &GameplayConnection::get_rejection_reason);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "peer_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "state", PROPERTY_HINT_ENUM, "Transport Connected,Version Verified,Authenticated,Admitted,Player Created,Spawned,Disconnected,Rejected", PROPERTY_USAGE_NONE), "", "get_state");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "session", PROPERTY_HINT_RESOURCE_TYPE, "GameplayUserSession", PROPERTY_USAGE_NONE), "", "get_session");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "rejection_reason", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_rejection_reason");

	BIND_ENUM_CONSTANT(STATE_TRANSPORT_CONNECTED);
	BIND_ENUM_CONSTANT(STATE_VERSION_VERIFIED);
	BIND_ENUM_CONSTANT(STATE_AUTHENTICATED);
	BIND_ENUM_CONSTANT(STATE_ADMITTED);
	BIND_ENUM_CONSTANT(STATE_PLAYER_CREATED);
	BIND_ENUM_CONSTANT(STATE_SPAWNED);
	BIND_ENUM_CONSTANT(STATE_DISCONNECTED);
	BIND_ENUM_CONSTANT(STATE_REJECTED);
}

void GameplayConnection::_set_state(State p_state) {
	state = p_state;
}

void GameplayConnection::_set_session(GameplayUserSession *p_session) {
	session_id = p_session ? p_session->get_instance_id() : ObjectID();
}

void GameplayConnection::_reject(const String &p_reason) {
	rejection_reason = p_reason;
	state = STATE_REJECTED;
}

int GameplayConnection::get_peer_id() const {
	return peer_id;
}

GameplayConnection::State GameplayConnection::get_state() const {
	return state;
}

GameplayUserSession *GameplayConnection::get_session() const {
	return _gameplay_session_object<GameplayUserSession>(session_id);
}

String GameplayConnection::get_rejection_reason() const {
	return rejection_reason;
}

void GameplayUserSession::_bind_methods() {
	ClassDB::bind_method(D_METHOD("get_user_id"), &GameplayUserSession::get_user_id);
	ClassDB::bind_method(D_METHOD("get_session_id"), &GameplayUserSession::get_session_id);
	ClassDB::bind_method(D_METHOD("get_reconnect_token"), &GameplayUserSession::get_reconnect_token);
	ClassDB::bind_method(D_METHOD("get_peer_id"), &GameplayUserSession::get_peer_id);
	ClassDB::bind_method(D_METHOD("is_active"), &GameplayUserSession::is_active);
	ClassDB::bind_method(D_METHOD("get_disconnected_at_msec"), &GameplayUserSession::get_disconnected_at_msec);
	ClassDB::bind_method(D_METHOD("get_player_state"), &GameplayUserSession::get_player_state);
	ClassDB::bind_method(D_METHOD("get_controller"), &GameplayUserSession::get_controller);

	ADD_PROPERTY(PropertyInfo(Variant::STRING, "user_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_user_id");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "session_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_session_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "peer_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_peer_id");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "active", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_active");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "player_state", PROPERTY_HINT_RESOURCE_TYPE, "GameplayPlayerState", PROPERTY_USAGE_NONE), "", "get_player_state");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "controller", PROPERTY_HINT_RESOURCE_TYPE, "GameplayController", PROPERTY_USAGE_NONE), "", "get_controller");

	ADD_SIGNAL(MethodInfo("peer_bound", PropertyInfo(Variant::INT, "peer_id")));
	ADD_SIGNAL(MethodInfo("deactivated", PropertyInfo(Variant::INT, "previous_peer_id")));
}

void GameplayUserSession::_set_identity(const String &p_user_id, const String &p_session_id, const String &p_reconnect_token) {
	user_id = p_user_id;
	stable_session_id = p_session_id;
	reconnect_token = p_reconnect_token;
}

void GameplayUserSession::_bind_peer(int p_peer_id) {
	peer_id = p_peer_id;
	active = true;
	disconnected_at_msec = 0;
	emit_signal(SNAME("peer_bound"), peer_id);
}

void GameplayUserSession::_deactivate(uint64_t p_now_msec) {
	const int previous_peer_id = peer_id;
	peer_id = 0;
	active = false;
	disconnected_at_msec = p_now_msec;
	emit_signal(SNAME("deactivated"), previous_peer_id);
}

void GameplayUserSession::_set_player_state(GameplayPlayerState *p_player_state) {
	player_state_id = p_player_state ? p_player_state->get_instance_id() : ObjectID();
}

void GameplayUserSession::_set_controller(GameplayController *p_controller) {
	controller_id = p_controller ? p_controller->get_instance_id() : ObjectID();
}

String GameplayUserSession::get_user_id() const {
	return user_id;
}

String GameplayUserSession::get_session_id() const {
	return stable_session_id;
}

String GameplayUserSession::get_reconnect_token() const {
	return reconnect_token;
}

int GameplayUserSession::get_peer_id() const {
	return peer_id;
}

bool GameplayUserSession::is_active() const {
	return active;
}

uint64_t GameplayUserSession::get_disconnected_at_msec() const {
	return disconnected_at_msec;
}

GameplayPlayerState *GameplayUserSession::get_player_state() const {
	return _gameplay_session_object<GameplayPlayerState>(player_state_id);
}

GameplayController *GameplayUserSession::get_controller() const {
	return _gameplay_session_object<GameplayController>(controller_id);
}

void GameplaySessionManager::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_protocol_version", "version"), &GameplaySessionManager::set_protocol_version);
	ClassDB::bind_method(D_METHOD("get_protocol_version"), &GameplaySessionManager::get_protocol_version);
	ClassDB::bind_method(D_METHOD("set_disconnect_grace_period_msec", "grace_period_msec"), &GameplaySessionManager::set_disconnect_grace_period_msec);
	ClassDB::bind_method(D_METHOD("get_disconnect_grace_period_msec"), &GameplaySessionManager::get_disconnect_grace_period_msec);
	ClassDB::bind_method(D_METHOD("set_accepting_connections", "accepting"), &GameplaySessionManager::set_accepting_connections);
	ClassDB::bind_method(D_METHOD("is_accepting_connections"), &GameplaySessionManager::is_accepting_connections);
	ClassDB::bind_method(D_METHOD("set_game_mode", "game_mode"), &GameplaySessionManager::set_game_mode);
	ClassDB::bind_method(D_METHOD("get_game_mode"), &GameplaySessionManager::get_game_mode);
	ClassDB::bind_method(D_METHOD("transport_connected", "peer_id"), &GameplaySessionManager::transport_connected);
	ClassDB::bind_method(D_METHOD("verify_version", "peer_id", "version"), &GameplaySessionManager::verify_version);
	ClassDB::bind_method(D_METHOD("authenticate", "peer_id", "user_id", "session_id", "reconnect_token"), &GameplaySessionManager::authenticate);
	ClassDB::bind_method(D_METHOD("admit", "peer_id"), &GameplaySessionManager::admit);
	ClassDB::bind_method(D_METHOD("create_player", "peer_id"), &GameplaySessionManager::create_player);
	ClassDB::bind_method(D_METHOD("spawn_player", "peer_id"), &GameplaySessionManager::spawn_player);
	ClassDB::bind_method(D_METHOD("reject", "peer_id", "reason"), &GameplaySessionManager::reject);
	ClassDB::bind_method(D_METHOD("transport_disconnected", "peer_id", "now_msec"), &GameplaySessionManager::transport_disconnected, DEFVAL(UINT64_MAX));
	ClassDB::bind_method(D_METHOD("expire_disconnected", "now_msec"), &GameplaySessionManager::expire_disconnected, DEFVAL(UINT64_MAX));
	ClassDB::bind_method(D_METHOD("shutdown"), &GameplaySessionManager::shutdown);
	ClassDB::bind_method(D_METHOD("get_connection", "peer_id"), &GameplaySessionManager::get_connection);
	ClassDB::bind_method(D_METHOD("get_session_by_peer", "peer_id"), &GameplaySessionManager::get_session_by_peer);
	ClassDB::bind_method(D_METHOD("get_session", "session_id"), &GameplaySessionManager::get_session);
	ClassDB::bind_method(D_METHOD("get_sessions"), &GameplaySessionManager::get_sessions);
	ClassDB::bind_method(D_METHOD("get_active_session_count"), &GameplaySessionManager::get_active_session_count);

	ADD_PROPERTY(PropertyInfo(Variant::STRING, "protocol_version"), "set_protocol_version", "get_protocol_version");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "disconnect_grace_period_msec", PROPERTY_HINT_RANGE, "0,3600000,1,or_greater"), "set_disconnect_grace_period_msec", "get_disconnect_grace_period_msec");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "accepting_connections"), "set_accepting_connections", "is_accepting_connections");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "game_mode", PROPERTY_HINT_RESOURCE_TYPE, "GameplayGameMode"), "set_game_mode", "get_game_mode");

	ADD_SIGNAL(MethodInfo("connection_state_changed", PropertyInfo(Variant::INT, "peer_id"), PropertyInfo(Variant::INT, "state")));
	ADD_SIGNAL(MethodInfo("session_created", PropertyInfo(Variant::OBJECT, "session", PROPERTY_HINT_RESOURCE_TYPE, "GameplayUserSession")));
	ADD_SIGNAL(MethodInfo("session_rebound", PropertyInfo(Variant::OBJECT, "session", PROPERTY_HINT_RESOURCE_TYPE, "GameplayUserSession"), PropertyInfo(Variant::INT, "peer_id")));
	ADD_SIGNAL(MethodInfo("session_deactivated", PropertyInfo(Variant::OBJECT, "session", PROPERTY_HINT_RESOURCE_TYPE, "GameplayUserSession")));
	ADD_SIGNAL(MethodInfo("session_expired", PropertyInfo(Variant::OBJECT, "session", PROPERTY_HINT_RESOURCE_TYPE, "GameplayUserSession")));
}

uint64_t GameplaySessionManager::_resolve_time(uint64_t p_now_msec) const {
	return p_now_msec == UINT64_MAX ? OS::get_singleton()->get_ticks_msec() : p_now_msec;
}

void GameplaySessionManager::set_protocol_version(const String &p_version) {
	ERR_FAIL_COND_MSG(p_version.is_empty(), "The gameplay protocol version cannot be empty.");
	protocol_version = p_version;
}

String GameplaySessionManager::get_protocol_version() const {
	return protocol_version;
}

void GameplaySessionManager::set_disconnect_grace_period_msec(uint64_t p_grace_period_msec) {
	disconnect_grace_period_msec = p_grace_period_msec;
}

uint64_t GameplaySessionManager::get_disconnect_grace_period_msec() const {
	return disconnect_grace_period_msec;
}

void GameplaySessionManager::set_accepting_connections(bool p_accepting) {
	accepting_connections = p_accepting;
}

bool GameplaySessionManager::is_accepting_connections() const {
	return accepting_connections;
}

void GameplaySessionManager::set_game_mode(GameplayGameMode *p_game_mode) {
	ERR_FAIL_COND_MSG(!connections.is_empty() || !session_ids.is_empty(), "The game mode cannot change while sessions exist.");
	game_mode_id = p_game_mode ? p_game_mode->get_instance_id() : ObjectID();
}

GameplayGameMode *GameplaySessionManager::get_game_mode() const {
	return _gameplay_session_object<GameplayGameMode>(game_mode_id);
}

Error GameplaySessionManager::transport_connected(int p_peer_id) {
	ERR_FAIL_COND_V_MSG(!accepting_connections, ERR_UNAVAILABLE, "The session manager is not accepting connections.");
	ERR_FAIL_COND_V_MSG(p_peer_id <= 1, ERR_INVALID_PARAMETER, "A client peer ID must be greater than one.");
	ERR_FAIL_COND_V_MSG(connections.has(p_peer_id), ERR_ALREADY_EXISTS, "The transport peer is already connected.");

	Ref<GameplayConnection> connection;
	connection.instantiate();
	connection->peer_id = p_peer_id;
	connections.insert(p_peer_id, connection);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_TRANSPORT_CONNECTED);
	return OK;
}

Error GameplaySessionManager::verify_version(int p_peer_id, const String &p_version) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	ERR_FAIL_COND_V_MSG(connection->get_state() != GameplayConnection::STATE_TRANSPORT_CONNECTED, ERR_INVALID_DATA, "Version verification is out of order.");
	if (p_version != protocol_version) {
		reject(p_peer_id, "protocol_version_mismatch");
		return ERR_INVALID_DATA;
	}
	connection->_set_state(GameplayConnection::STATE_VERSION_VERIFIED);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_VERSION_VERIFIED);
	return OK;
}

GameplayUserSession *GameplaySessionManager::_find_session_for_user(const String &p_user_id) const {
	for (const ObjectID &id : session_ids) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(id);
		if (session && session->get_user_id() == p_user_id) {
			return session;
		}
	}
	return nullptr;
}

Error GameplaySessionManager::authenticate(int p_peer_id, const String &p_user_id, const String &p_session_id, const String &p_reconnect_token) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	ERR_FAIL_COND_V_MSG(connection->get_state() != GameplayConnection::STATE_VERSION_VERIFIED, ERR_INVALID_DATA, "Authentication is out of order.");
	ERR_FAIL_COND_V_MSG(p_user_id.is_empty() || p_session_id.is_empty() || p_reconnect_token.is_empty(), ERR_INVALID_PARAMETER, "Authentication requires stable user, session, and reconnect identities.");

	GameplayUserSession *session = get_session(p_session_id);
	if (session) {
		if (session->get_user_id() != p_user_id || session->get_reconnect_token() != p_reconnect_token) {
			reject(p_peer_id, "invalid_reconnect_identity");
			return ERR_UNAUTHORIZED;
		}
		if (session->is_active()) {
			reject(p_peer_id, "session_already_active");
			return ERR_ALREADY_IN_USE;
		}
		session->_bind_peer(p_peer_id);
		GameplayPlayerState *player_state = session->get_player_state();
		if (player_state) {
			player_state->activate(p_peer_id, session->get_session_id());
		}
		GameplayController *controller = session->get_controller();
		if (controller) {
			controller->set_owner_peer_id(p_peer_id);
		}
		emit_signal(SNAME("session_rebound"), session, p_peer_id);
	} else {
		GameplayUserSession *other_session = _find_session_for_user(p_user_id);
		if (other_session) {
			reject(p_peer_id, "user_session_conflict");
			return ERR_ALREADY_EXISTS;
		}
		session = memnew(GameplayUserSession);
		session->_set_identity(p_user_id, p_session_id, p_reconnect_token);
		session->_bind_peer(p_peer_id);
		add_child(session);
		session_ids.push_back(session->get_instance_id());
		emit_signal(SNAME("session_created"), session);
	}

	connection->_set_session(session);
	connection->_set_state(GameplayConnection::STATE_AUTHENTICATED);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_AUTHENTICATED);
	return OK;
}

Error GameplaySessionManager::admit(int p_peer_id) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	ERR_FAIL_COND_V_MSG(connection->get_state() != GameplayConnection::STATE_AUTHENTICATED, ERR_INVALID_DATA, "Business admission is out of order.");
	ERR_FAIL_NULL_V_MSG(connection->get_session(), ERR_BUG, "An authenticated connection must have a session.");
	connection->_set_state(GameplayConnection::STATE_ADMITTED);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_ADMITTED);
	return OK;
}

Error GameplaySessionManager::create_player(int p_peer_id) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	ERR_FAIL_COND_V_MSG(connection->get_state() != GameplayConnection::STATE_ADMITTED, ERR_INVALID_DATA, "Player creation is out of order.");
	GameplayUserSession *session = connection->get_session();
	ERR_FAIL_NULL_V(session, ERR_BUG);
	GameplayGameMode *game_mode = get_game_mode();
	ERR_FAIL_NULL_V_MSG(game_mode, ERR_UNCONFIGURED, "Player creation requires a game mode.");

	GameplayController *controller = session->get_controller();
	GameplayPlayerState *player_state = session->get_player_state();
	if (!controller && !player_state) {
		controller = memnew(GameplayController);
		player_state = memnew(GameplayPlayerState);
		session->add_child(player_state);
		session->add_child(controller);
		session->_set_player_state(player_state);
		session->_set_controller(controller);
		player_state->set_user_id(session->get_user_id());
		player_state->activate(p_peer_id, session->get_session_id());
		controller->set_owner_peer_id(p_peer_id);
		const Error admit_error = game_mode->admit_player(controller, player_state);
		if (admit_error != OK) {
			session->_set_controller(nullptr);
			session->_set_player_state(nullptr);
			session->remove_child(controller);
			session->remove_child(player_state);
			memdelete(controller);
			memdelete(player_state);
			return admit_error;
		}
	} else {
		ERR_FAIL_NULL_V_MSG(controller, ERR_BUG, "A preserved session has no controller.");
		ERR_FAIL_NULL_V_MSG(player_state, ERR_BUG, "A preserved session has no player state.");
		controller->set_owner_peer_id(p_peer_id);
		player_state->activate(p_peer_id, session->get_session_id());
		if (controller->get_game_mode() != game_mode || controller->get_player_state() != player_state) {
			const Error admit_error = game_mode->admit_player(controller, player_state);
			ERR_FAIL_COND_V(admit_error != OK, admit_error);
		}
	}

	connection->_set_state(GameplayConnection::STATE_PLAYER_CREATED);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_PLAYER_CREATED);
	return OK;
}

Error GameplaySessionManager::spawn_player(int p_peer_id) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	ERR_FAIL_COND_V_MSG(connection->get_state() != GameplayConnection::STATE_PLAYER_CREATED, ERR_INVALID_DATA, "Player spawning is out of order.");
	GameplayUserSession *session = connection->get_session();
	ERR_FAIL_NULL_V(session, ERR_BUG);
	GameplayController *controller = session->get_controller();
	ERR_FAIL_NULL_V(controller, ERR_BUG);
	if (!controller->has_pawn()) {
		GameplayPawn *pawn = memnew(GameplayPawn);
		session->add_child(pawn);
		const Error possess_error = controller->possess(pawn);
		if (possess_error != OK) {
			session->remove_child(pawn);
			memdelete(pawn);
			return possess_error;
		}
	}
	connection->_set_state(GameplayConnection::STATE_SPAWNED);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_SPAWNED);
	return OK;
}

Error GameplaySessionManager::reject(int p_peer_id, const String &p_reason) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	ERR_FAIL_COND_V_MSG(connection.is_null(), ERR_DOES_NOT_EXIST, "The transport peer is not connected.");
	connection->_reject(p_reason.is_empty() ? String("rejected") : p_reason);
	emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_REJECTED);
	return OK;
}

void GameplaySessionManager::transport_disconnected(int p_peer_id, uint64_t p_now_msec) {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	if (connection.is_null()) {
		return;
	}
	if (connection->get_state() != GameplayConnection::STATE_REJECTED) {
		connection->_set_state(GameplayConnection::STATE_DISCONNECTED);
		emit_signal(SNAME("connection_state_changed"), p_peer_id, GameplayConnection::STATE_DISCONNECTED);
	}
	GameplayUserSession *session = connection->get_session();
	const bool discard_unadmitted_session = session && !session->get_controller();
	if (session && session->is_active() && session->get_peer_id() == p_peer_id) {
		GameplayController *controller = session->get_controller();
		if (controller) {
			GameplayPawn *pawn = controller->get_pawn();
			controller->unpossess();
			controller->set_owner_peer_id(0);
			if (pawn) {
				if (pawn->get_parent() == session) {
					session->remove_child(pawn);
				}
				memdelete(pawn);
			}
		}
		GameplayPlayerState *player_state = session->get_player_state();
		if (player_state) {
			player_state->deactivate();
		}
		session->_deactivate(_resolve_time(p_now_msec));
		emit_signal(SNAME("session_deactivated"), session);
	}
	connections.erase(p_peer_id);
	if (discard_unadmitted_session) {
		_destroy_session(session, false);
	}
}

void GameplaySessionManager::_destroy_session(GameplayUserSession *p_session, bool p_emit_signal) {
	if (!p_session) {
		return;
	}
	const int index = session_ids.find(p_session->get_instance_id());
	if (index < 0) {
		return;
	}
	GameplayController *controller = p_session->get_controller();
	GameplayGameMode *game_mode = get_game_mode();
	if (controller && game_mode && controller->get_game_mode() == game_mode) {
		game_mode->remove_player(controller, false);
	}
	session_ids.remove_at(index);
	if (p_emit_signal) {
		emit_signal(SNAME("session_expired"), p_session);
	}
	if (p_session->get_parent() == this) {
		remove_child(p_session);
	}
	memdelete(p_session);
}

int GameplaySessionManager::expire_disconnected(uint64_t p_now_msec) {
	const uint64_t now = _resolve_time(p_now_msec);
	Vector<ObjectID> expired;
	for (const ObjectID &id : session_ids) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(id);
		if (session && !session->is_active() && now >= session->get_disconnected_at_msec() && now - session->get_disconnected_at_msec() >= disconnect_grace_period_msec) {
			expired.push_back(id);
		}
	}
	for (const ObjectID &id : expired) {
		_destroy_session(_gameplay_session_object<GameplayUserSession>(id), true);
	}
	return expired.size();
}

void GameplaySessionManager::shutdown() {
	accepting_connections = false;
	connections.clear();
	while (!session_ids.is_empty()) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(session_ids[session_ids.size() - 1]);
		if (session) {
			_destroy_session(session, false);
		} else {
			session_ids.remove_at(session_ids.size() - 1);
		}
	}
}

Ref<GameplayConnection> GameplaySessionManager::get_connection(int p_peer_id) const {
	const Ref<GameplayConnection> *connection = connections.getptr(p_peer_id);
	return connection ? *connection : Ref<GameplayConnection>();
}

GameplayUserSession *GameplaySessionManager::get_session_by_peer(int p_peer_id) const {
	Ref<GameplayConnection> connection = get_connection(p_peer_id);
	return connection.is_valid() ? connection->get_session() : nullptr;
}

GameplayUserSession *GameplaySessionManager::get_session(const String &p_session_id) const {
	for (const ObjectID &id : session_ids) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(id);
		if (session && session->get_session_id() == p_session_id) {
			return session;
		}
	}
	return nullptr;
}

TypedArray<GameplayUserSession> GameplaySessionManager::get_sessions() const {
	TypedArray<GameplayUserSession> sessions;
	for (const ObjectID &id : session_ids) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(id);
		if (session) {
			sessions.push_back(session);
		}
	}
	return sessions;
}

int GameplaySessionManager::get_active_session_count() const {
	int count = 0;
	for (const ObjectID &id : session_ids) {
		GameplayUserSession *session = _gameplay_session_object<GameplayUserSession>(id);
		if (session && session->is_active()) {
			count++;
		}
	}
	return count;
}

GameplaySessionManager::~GameplaySessionManager() {
	shutdown();
}
