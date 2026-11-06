/**************************************************************************/
/*  gameplay_server.cpp                                                   */
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

#include "gameplay_server.h"

#include "gameplay_prediction.h"
#include "gameplay_replication.h"

#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/class_db.h"
#include "core/os/os.h"

static bool _gameplay_parse_u32(const String &p_value, uint32_t &r_value) {
	if (!p_value.is_valid_int()) {
		return false;
	}
	const int64_t value = p_value.to_int();
	if (value < 0 || value > UINT32_MAX) {
		return false;
	}
	r_value = uint32_t(value);
	return true;
}

void GameplayServerConfig::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_bind_address", "address"), &GameplayServerConfig::set_bind_address);
	ClassDB::bind_method(D_METHOD("get_bind_address"), &GameplayServerConfig::get_bind_address);
	ClassDB::bind_method(D_METHOD("set_port", "port"), &GameplayServerConfig::set_port);
	ClassDB::bind_method(D_METHOD("get_port"), &GameplayServerConfig::get_port);
	ClassDB::bind_method(D_METHOD("set_max_clients", "max_clients"), &GameplayServerConfig::set_max_clients);
	ClassDB::bind_method(D_METHOD("get_max_clients"), &GameplayServerConfig::get_max_clients);
	ClassDB::bind_method(D_METHOD("set_protocol_version", "version"), &GameplayServerConfig::set_protocol_version);
	ClassDB::bind_method(D_METHOD("get_protocol_version"), &GameplayServerConfig::get_protocol_version);
	ClassDB::bind_method(D_METHOD("set_disconnect_grace_period_msec", "msec"), &GameplayServerConfig::set_disconnect_grace_period_msec);
	ClassDB::bind_method(D_METHOD("get_disconnect_grace_period_msec"), &GameplayServerConfig::get_disconnect_grace_period_msec);
	ClassDB::bind_method(D_METHOD("set_shutdown_timeout_msec", "msec"), &GameplayServerConfig::set_shutdown_timeout_msec);
	ClassDB::bind_method(D_METHOD("get_shutdown_timeout_msec"), &GameplayServerConfig::get_shutdown_timeout_msec);
	ClassDB::bind_method(D_METHOD("apply_command_line", "arguments"), &GameplayServerConfig::apply_command_line);

	ADD_PROPERTY(PropertyInfo(Variant::STRING, "bind_address"), "set_bind_address", "get_bind_address");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "port", PROPERTY_HINT_RANGE, "0,65535,1"), "set_port", "get_port");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_clients", PROPERTY_HINT_RANGE, "1,4095,1"), "set_max_clients", "get_max_clients");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "protocol_version"), "set_protocol_version", "get_protocol_version");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "disconnect_grace_period_msec", PROPERTY_HINT_RANGE, "0,3600000,1,or_greater"), "set_disconnect_grace_period_msec", "get_disconnect_grace_period_msec");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "shutdown_timeout_msec", PROPERTY_HINT_RANGE, "0,3600000,1,or_greater"), "set_shutdown_timeout_msec", "get_shutdown_timeout_msec");
}

void GameplayServerConfig::set_bind_address(const String &p_address) {
	ERR_FAIL_COND_MSG(p_address.is_empty(), "The bind address cannot be empty.");
	bind_address = p_address;
}

String GameplayServerConfig::get_bind_address() const {
	return bind_address;
}

void GameplayServerConfig::set_port(int p_port) {
	ERR_FAIL_COND_MSG(p_port < 0 || p_port > 65535, "The server port must be between 0 and 65535.");
	port = p_port;
}

int GameplayServerConfig::get_port() const {
	return port;
}

void GameplayServerConfig::set_max_clients(int p_max_clients) {
	ERR_FAIL_COND_MSG(p_max_clients < 1 || p_max_clients > 4095, "The maximum client count must be between 1 and 4095.");
	max_clients = p_max_clients;
}

int GameplayServerConfig::get_max_clients() const {
	return max_clients;
}

void GameplayServerConfig::set_protocol_version(const String &p_version) {
	ERR_FAIL_COND_MSG(p_version.is_empty(), "The protocol version cannot be empty.");
	protocol_version = p_version;
}

String GameplayServerConfig::get_protocol_version() const {
	return protocol_version;
}

void GameplayServerConfig::set_disconnect_grace_period_msec(uint64_t p_msec) {
	disconnect_grace_period_msec = p_msec;
}

uint64_t GameplayServerConfig::get_disconnect_grace_period_msec() const {
	return disconnect_grace_period_msec;
}

void GameplayServerConfig::set_shutdown_timeout_msec(uint64_t p_msec) {
	shutdown_timeout_msec = p_msec;
}

uint64_t GameplayServerConfig::get_shutdown_timeout_msec() const {
	return shutdown_timeout_msec;
}

Error GameplayServerConfig::apply_command_line(const PackedStringArray &p_arguments) {
	for (int i = 0; i < p_arguments.size(); i++) {
		const String argument = p_arguments[i];
		const int separator = argument.find_char('=');
		String key = separator >= 0 ? argument.left(separator) : argument;
		String value;
		if (separator >= 0) {
			value = argument.substr(separator + 1);
		} else if (key.begins_with("--gameplay-") && i + 1 < p_arguments.size()) {
			value = p_arguments[++i];
		} else {
			continue;
		}

		uint32_t parsed = 0;
		if (key == "--gameplay-bind") {
			ERR_FAIL_COND_V(value.is_empty(), ERR_INVALID_PARAMETER);
			bind_address = value;
		} else if (key == "--gameplay-port") {
			ERR_FAIL_COND_V(!_gameplay_parse_u32(value, parsed) || parsed > 65535, ERR_INVALID_PARAMETER);
			port = int(parsed);
		} else if (key == "--gameplay-max-clients") {
			ERR_FAIL_COND_V(!_gameplay_parse_u32(value, parsed) || parsed < 1 || parsed > 4095, ERR_INVALID_PARAMETER);
			max_clients = int(parsed);
		} else if (key == "--gameplay-protocol") {
			ERR_FAIL_COND_V(value.is_empty(), ERR_INVALID_PARAMETER);
			protocol_version = value;
		} else if (key == "--gameplay-grace-msec") {
			ERR_FAIL_COND_V(!_gameplay_parse_u32(value, parsed), ERR_INVALID_PARAMETER);
			disconnect_grace_period_msec = parsed;
		} else if (key == "--gameplay-shutdown-msec") {
			ERR_FAIL_COND_V(!_gameplay_parse_u32(value, parsed), ERR_INVALID_PARAMETER);
			shutdown_timeout_msec = parsed;
		}
	}
	return OK;
}

void GameplayDedicatedServer::_bind_methods() {
	ClassDB::bind_method(D_METHOD("set_authenticator", "authenticator"), &GameplayDedicatedServer::set_authenticator);
	ClassDB::bind_method(D_METHOD("get_authenticator"), &GameplayDedicatedServer::get_authenticator);
	ClassDB::bind_method(D_METHOD("set_admission_check", "admission_check"), &GameplayDedicatedServer::set_admission_check);
	ClassDB::bind_method(D_METHOD("get_admission_check"), &GameplayDedicatedServer::get_admission_check);
	ClassDB::bind_method(D_METHOD("start", "config", "session_manager"), &GameplayDedicatedServer::start);
	ClassDB::bind_method(D_METHOD("start_from_command_line", "session_manager", "arguments"), &GameplayDedicatedServer::start_from_command_line, DEFVAL(PackedStringArray()));
	ClassDB::bind_method(D_METHOD("poll"), &GameplayDedicatedServer::poll);
	ClassDB::bind_method(D_METHOD("refuse_new_connections"), &GameplayDedicatedServer::refuse_new_connections);
	ClassDB::bind_method(D_METHOD("begin_shutdown", "timeout_msec"), &GameplayDedicatedServer::begin_shutdown, DEFVAL(-1));
	ClassDB::bind_method(D_METHOD("stop_now"), &GameplayDedicatedServer::stop_now);
	ClassDB::bind_method(D_METHOD("is_running"), &GameplayDedicatedServer::is_running);
	ClassDB::bind_method(D_METHOD("is_shutting_down"), &GameplayDedicatedServer::is_shutting_down);
	ClassDB::bind_method(D_METHOD("is_refusing_new_connections"), &GameplayDedicatedServer::is_refusing_new_connections);
	ClassDB::bind_method(D_METHOD("get_bound_port"), &GameplayDedicatedServer::get_bound_port);
	ClassDB::bind_method(D_METHOD("get_transport_peer_count"), &GameplayDedicatedServer::get_transport_peer_count);
	ClassDB::bind_method(D_METHOD("get_session_manager"), &GameplayDedicatedServer::get_session_manager);
	ClassDB::bind_method(D_METHOD("get_multiplayer_peer"), &GameplayDedicatedServer::get_multiplayer_peer);
	ClassDB::bind_method(D_METHOD("set_replication", "replication"), &GameplayDedicatedServer::set_replication);
	ClassDB::bind_method(D_METHOD("get_replication"), &GameplayDedicatedServer::get_replication);
	ClassDB::bind_method(D_METHOD("set_prediction", "prediction"), &GameplayDedicatedServer::set_prediction);
	ClassDB::bind_method(D_METHOD("get_prediction"), &GameplayDedicatedServer::get_prediction);

	ADD_PROPERTY(PropertyInfo(Variant::CALLABLE, "authenticator"), "set_authenticator", "get_authenticator");
	ADD_PROPERTY(PropertyInfo(Variant::CALLABLE, "admission_check"), "set_admission_check", "get_admission_check");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "running", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "is_running");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "replication", PROPERTY_HINT_NODE_TYPE, "GameplayMultiplayerReplication"), "set_replication", "get_replication");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "prediction", PROPERTY_HINT_NODE_TYPE, "GameplayNetworkPrediction"), "set_prediction", "get_prediction");

	ADD_SIGNAL(MethodInfo("server_started", PropertyInfo(Variant::INT, "port")));
	ADD_SIGNAL(MethodInfo("server_stopping"));
	ADD_SIGNAL(MethodInfo("server_stopped"));
	ADD_SIGNAL(MethodInfo("peer_rejected", PropertyInfo(Variant::INT, "peer_id"), PropertyInfo(Variant::STRING, "reason")));
}

void GameplayDedicatedServer::_notification(int p_what) {
	if (p_what == NOTIFICATION_PROCESS && running) {
		poll();
	}
}

void GameplayDedicatedServer::set_authenticator(const Callable &p_authenticator) {
	authenticator = p_authenticator;
}

Callable GameplayDedicatedServer::get_authenticator() const {
	return authenticator;
}

void GameplayDedicatedServer::set_admission_check(const Callable &p_admission_check) {
	admission_check = p_admission_check;
}

Callable GameplayDedicatedServer::get_admission_check() const {
	return admission_check;
}

Error GameplayDedicatedServer::start(const Ref<GameplayServerConfig> &p_config, GameplaySessionManager *p_session_manager) {
	ERR_FAIL_COND_V_MSG(running, ERR_ALREADY_IN_USE, "The dedicated server is already running.");
	ERR_FAIL_COND_V_MSG(p_config.is_null(), ERR_INVALID_PARAMETER, "A server configuration is required.");
	ERR_FAIL_NULL_V(p_session_manager, ERR_INVALID_PARAMETER);
	ERR_FAIL_NULL_V_MSG(p_session_manager->get_game_mode(), ERR_UNCONFIGURED, "The session manager requires a game mode before the server starts.");
	ERR_FAIL_COND_V_MSG(!ClassDB::class_exists(SNAME("ENetMultiplayerPeer")), ERR_UNAVAILABLE, "The ENet module is not available in this build.");

	Ref<MultiplayerPeer> peer = Object::cast_to<MultiplayerPeer>(ClassDB::instantiate(SNAME("ENetMultiplayerPeer")));
	ERR_FAIL_COND_V_MSG(peer.is_null(), ERR_CANT_CREATE, "Unable to create an ENet multiplayer peer.");
	peer->call("set_bind_ip", p_config->get_bind_address());
	const Error create_error = Error(int(peer->call("create_server", p_config->get_port(), p_config->get_max_clients())));
	ERR_FAIL_COND_V(create_error != OK, create_error);

	config = p_config;
	multiplayer_peer = peer;
	session_manager_id = p_session_manager->get_instance_id();
	p_session_manager->set_protocol_version(config->get_protocol_version());
	p_session_manager->set_disconnect_grace_period_msec(config->get_disconnect_grace_period_msec());
	p_session_manager->set_accepting_connections(true);
	multiplayer_peer->connect(SNAME("peer_connected"), callable_mp(this, &GameplayDedicatedServer::_peer_connected));
	multiplayer_peer->connect(SNAME("peer_disconnected"), callable_mp(this, &GameplayDedicatedServer::_peer_disconnected));
	if (GameplayMultiplayerReplication *replication = get_replication()) {
		replication->configure_server(multiplayer_peer, p_session_manager);
	}
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->configure_server(multiplayer_peer, p_session_manager);
	}

	Object *host = multiplayer_peer->call("get_host");
	bound_port = host ? int(host->call("get_local_port")) : p_config->get_port();
	running = true;
	shutting_down = false;
	set_process(true);
	emit_signal(SNAME("server_started"), bound_port);
	return OK;
}

Error GameplayDedicatedServer::start_from_command_line(GameplaySessionManager *p_session_manager, const PackedStringArray &p_arguments) {
	Ref<GameplayServerConfig> command_line_config;
	command_line_config.instantiate();
	PackedStringArray arguments = p_arguments;
	if (arguments.is_empty()) {
		for (const String &argument : OS::get_singleton()->get_cmdline_user_args()) {
			arguments.push_back(argument);
		}
	}
	const Error parse_error = command_line_config->apply_command_line(arguments);
	ERR_FAIL_COND_V(parse_error != OK, parse_error);
	return start(command_line_config, p_session_manager);
}

void GameplayDedicatedServer::_peer_connected(int p_peer_id) {
	GameplaySessionManager *manager = get_session_manager();
	if (!running || shutting_down || !manager || manager->transport_connected(p_peer_id) != OK) {
		if (multiplayer_peer.is_valid()) {
			multiplayer_peer->disconnect_peer(p_peer_id, true);
		}
		return;
	}
	transport_peers.insert(p_peer_id);
}

void GameplayDedicatedServer::_peer_disconnected(int p_peer_id) {
	transport_peers.erase(p_peer_id);
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->peer_disconnected(p_peer_id);
	}
	GameplaySessionManager *manager = get_session_manager();
	if (manager) {
		manager->transport_disconnected(p_peer_id);
	}
}

Error GameplayDedicatedServer::_send_message(int p_peer_id, const Dictionary &p_message) {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	const CharString payload = JSON::stringify(p_message).utf8();
	multiplayer_peer->set_target_peer(p_peer_id);
	return multiplayer_peer->put_packet(reinterpret_cast<const uint8_t *>(payload.get_data()), payload.length());
}

void GameplayDedicatedServer::_reject_peer(int p_peer_id, const String &p_reason) {
	GameplaySessionManager *manager = get_session_manager();
	if (manager && manager->get_connection(p_peer_id).is_valid()) {
		manager->reject(p_peer_id, p_reason);
	}
	Dictionary response;
	response["type"] = "rejected";
	response["reason"] = p_reason;
	_send_message(p_peer_id, response);
	emit_signal(SNAME("peer_rejected"), p_peer_id, p_reason);
	if (multiplayer_peer.is_valid()) {
		multiplayer_peer->disconnect_peer(p_peer_id, false);
	}
}

void GameplayDedicatedServer::_handle_packet(int p_peer_id, const Dictionary &p_message) {
	GameplaySessionManager *manager = get_session_manager();
	if (!manager) {
		_reject_peer(p_peer_id, "server_unconfigured");
		return;
	}
	GameplayMultiplayerReplication *replication = get_replication();
	if (replication && replication->handles_message(p_message)) {
		replication->receive_packet(p_peer_id, p_message, OS::get_singleton()->get_ticks_msec());
		return;
	}
	GameplayNetworkPrediction *prediction = get_prediction();
	if (prediction && prediction->handles_message(p_message)) {
		prediction->receive_packet(p_peer_id, p_message, OS::get_singleton()->get_ticks_msec());
		return;
	}
	const String type = p_message.get("type", String());
	if (type == "version") {
		if (manager->verify_version(p_peer_id, p_message.get("protocol_version", String())) != OK) {
			_reject_peer(p_peer_id, "protocol_version_mismatch");
			return;
		}
		Dictionary response;
		response["type"] = "version_accepted";
		_send_message(p_peer_id, response);
		return;
	}
	if (type == "authenticate") {
		if (!authenticator.is_valid()) {
			_reject_peer(p_peer_id, "authentication_unavailable");
			return;
		}
		const String token = p_message.get("auth_token", String());
		const String reconnect = p_message.get("reconnect_token", String());
		const Variant result_variant = authenticator.call(token, reconnect);
		if (result_variant.get_type() != Variant::DICTIONARY) {
			_reject_peer(p_peer_id, "authentication_invalid_response");
			return;
		}
		const Dictionary result = result_variant;
		if (!bool(result.get("accepted", false))) {
			_reject_peer(p_peer_id, result.get("reason", String("authentication_failed")));
			return;
		}
		const String user_id = result.get("user_id", String());
		const String session_id = result.get("session_id", String());
		const String reconnect_token = result.get("reconnect_token", String());
		if (manager->authenticate(p_peer_id, user_id, session_id, reconnect_token) != OK) {
			Ref<GameplayConnection> connection = manager->get_connection(p_peer_id);
			_reject_peer(p_peer_id, connection.is_valid() ? connection->get_rejection_reason() : String("authentication_failed"));
			return;
		}
		Dictionary response;
		response["type"] = "authenticated";
		response["user_id"] = user_id;
		response["session_id"] = session_id;
		response["reconnect_token"] = reconnect_token;
		_send_message(p_peer_id, response);
		return;
	}
	if (type == "join") {
		GameplayUserSession *session = manager->get_session_by_peer(p_peer_id);
		if (!session) {
			_reject_peer(p_peer_id, "not_authenticated");
			return;
		}
		if (admission_check.is_valid() && !bool(admission_check.call(session->get_user_id(), session->get_session_id()))) {
			_reject_peer(p_peer_id, "admission_denied");
			return;
		}
		Error error = manager->admit(p_peer_id);
		if (error == OK) {
			error = manager->create_player(p_peer_id);
		}
		if (error == OK) {
			error = manager->spawn_player(p_peer_id);
		}
		if (error != OK) {
			_reject_peer(p_peer_id, "player_creation_failed");
			return;
		}
		Dictionary response;
		response["type"] = "joined";
		_send_message(p_peer_id, response);
		return;
	}
	_reject_peer(p_peer_id, "unexpected_handshake_message");
}

Error GameplayDedicatedServer::poll() {
	ERR_FAIL_COND_V_MSG(!running || multiplayer_peer.is_null(), ERR_UNCONFIGURED, "The dedicated server is not running.");
	multiplayer_peer->poll();
	GameplaySessionManager *manager = get_session_manager();
	if (manager) {
		// Expire preserved identities before accepting reconnect packets in this tick.
		manager->expire_disconnected();
	}
	while (multiplayer_peer.is_valid() && multiplayer_peer->get_available_packet_count() > 0) {
		const int peer_id = multiplayer_peer->get_packet_peer();
		const uint8_t *buffer = nullptr;
		int size = 0;
		if (multiplayer_peer->get_packet(&buffer, size) != OK) {
			continue;
		}
		if (size > 4096) {
			_reject_peer(peer_id, "handshake_packet_too_large");
			continue;
		}
		const Variant parsed = JSON::parse_string(String::utf8(reinterpret_cast<const char *>(buffer), size));
		if (parsed.get_type() != Variant::DICTIONARY) {
			_reject_peer(peer_id, "invalid_handshake_packet");
			continue;
		}
		_handle_packet(peer_id, parsed);
	}
	if (GameplayMultiplayerReplication *replication = get_replication()) {
		const uint64_t now = OS::get_singleton()->get_ticks_msec();
		replication->expire_reassemblies(now);
		replication->replicate(now);
	}
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->poll(OS::get_singleton()->get_ticks_msec());
	}
	if (shutting_down && (transport_peers.is_empty() || OS::get_singleton()->get_ticks_msec() >= shutdown_deadline_msec)) {
		_finish_shutdown();
	}
	return OK;
}

void GameplayDedicatedServer::refuse_new_connections() {
	if (!running) {
		return;
	}
	GameplaySessionManager *manager = get_session_manager();
	if (manager) {
		manager->set_accepting_connections(false);
	}
	if (multiplayer_peer.is_valid()) {
		multiplayer_peer->set_refuse_new_connections(true);
	}
}

void GameplayDedicatedServer::begin_shutdown(int64_t p_timeout_msec) {
	if (!running || shutting_down) {
		return;
	}
	refuse_new_connections();
	shutting_down = true;
	const uint64_t timeout = p_timeout_msec >= 0 ? uint64_t(p_timeout_msec) : (config.is_valid() ? config->get_shutdown_timeout_msec() : 0);
	shutdown_deadline_msec = OS::get_singleton()->get_ticks_msec() + timeout;
	emit_signal(SNAME("server_stopping"));
	if (transport_peers.is_empty() || timeout == 0) {
		_finish_shutdown();
	}
}

void GameplayDedicatedServer::_finish_shutdown() {
	if (!running) {
		return;
	}
	if (multiplayer_peer.is_valid()) {
		multiplayer_peer->close();
	}
	if (GameplayMultiplayerReplication *replication = get_replication()) {
		replication->clear_transport();
	}
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->clear_transport();
	}
	GameplaySessionManager *manager = get_session_manager();
	if (manager) {
		manager->shutdown();
	}
	transport_peers.clear();
	multiplayer_peer.unref();
	config.unref();
	session_manager_id = ObjectID();
	bound_port = 0;
	running = false;
	shutting_down = false;
	set_process(false);
	emit_signal(SNAME("server_stopped"));
}

void GameplayDedicatedServer::stop_now() {
	if (!running) {
		return;
	}
	refuse_new_connections();
	_finish_shutdown();
}

bool GameplayDedicatedServer::is_running() const {
	return running;
}

bool GameplayDedicatedServer::is_shutting_down() const {
	return shutting_down;
}

bool GameplayDedicatedServer::is_refusing_new_connections() const {
	return running && multiplayer_peer.is_valid() && multiplayer_peer->is_refusing_new_connections();
}

int GameplayDedicatedServer::get_bound_port() const {
	return bound_port;
}

int GameplayDedicatedServer::get_transport_peer_count() const {
	return transport_peers.size();
}

GameplaySessionManager *GameplayDedicatedServer::get_session_manager() const {
	return Object::cast_to<GameplaySessionManager>(ObjectDB::get_instance(session_manager_id));
}

Ref<MultiplayerPeer> GameplayDedicatedServer::get_multiplayer_peer() const {
	return multiplayer_peer;
}

void GameplayDedicatedServer::set_replication(GameplayMultiplayerReplication *p_replication) {
	replication_id = p_replication ? p_replication->get_instance_id() : ObjectID();
	if (p_replication && running && multiplayer_peer.is_valid()) {
		p_replication->configure_server(multiplayer_peer, get_session_manager());
	}
}

GameplayMultiplayerReplication *GameplayDedicatedServer::get_replication() const {
	return Object::cast_to<GameplayMultiplayerReplication>(ObjectDB::get_instance(replication_id));
}

void GameplayDedicatedServer::set_prediction(GameplayNetworkPrediction *p_prediction) {
	prediction_id = p_prediction ? p_prediction->get_instance_id() : ObjectID();
	if (p_prediction && running && multiplayer_peer.is_valid()) {
		p_prediction->configure_server(multiplayer_peer, get_session_manager());
	}
}

GameplayNetworkPrediction *GameplayDedicatedServer::get_prediction() const {
	return Object::cast_to<GameplayNetworkPrediction>(ObjectDB::get_instance(prediction_id));
}

GameplayDedicatedServer::~GameplayDedicatedServer() {
	stop_now();
}

void GameplaySessionClient::_bind_methods() {
	ClassDB::bind_method(D_METHOD("connect_to_server", "address", "port", "protocol_version", "auth_token", "reconnect_token"), &GameplaySessionClient::connect_to_server, DEFVAL(String()));
	ClassDB::bind_method(D_METHOD("poll"), &GameplaySessionClient::poll);
	ClassDB::bind_method(D_METHOD("disconnect_from_server"), &GameplaySessionClient::disconnect_from_server);
	ClassDB::bind_method(D_METHOD("get_state"), &GameplaySessionClient::get_state);
	ClassDB::bind_method(D_METHOD("is_joined"), &GameplaySessionClient::is_joined);
	ClassDB::bind_method(D_METHOD("get_peer_id"), &GameplaySessionClient::get_peer_id);
	ClassDB::bind_method(D_METHOD("get_user_id"), &GameplaySessionClient::get_user_id);
	ClassDB::bind_method(D_METHOD("get_session_id"), &GameplaySessionClient::get_session_id);
	ClassDB::bind_method(D_METHOD("get_reconnect_token"), &GameplaySessionClient::get_reconnect_token);
	ClassDB::bind_method(D_METHOD("get_rejection_reason"), &GameplaySessionClient::get_rejection_reason);
	ClassDB::bind_method(D_METHOD("get_multiplayer_peer"), &GameplaySessionClient::get_multiplayer_peer);
	ClassDB::bind_method(D_METHOD("set_replication", "replication"), &GameplaySessionClient::set_replication);
	ClassDB::bind_method(D_METHOD("get_replication"), &GameplaySessionClient::get_replication);
	ClassDB::bind_method(D_METHOD("set_prediction", "prediction"), &GameplaySessionClient::set_prediction);
	ClassDB::bind_method(D_METHOD("get_prediction"), &GameplaySessionClient::get_prediction);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "state", PROPERTY_HINT_ENUM, "Transport Connected,Version Verified,Authenticated,Admitted,Player Created,Spawned,Disconnected,Rejected", PROPERTY_USAGE_NONE), "", "get_state");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "user_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_user_id");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "session_id", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_session_id");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "rejection_reason", PROPERTY_HINT_NONE, "", PROPERTY_USAGE_NONE), "", "get_rejection_reason");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "replication", PROPERTY_HINT_NODE_TYPE, "GameplayMultiplayerReplication"), "set_replication", "get_replication");
	ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "prediction", PROPERTY_HINT_NODE_TYPE, "GameplayNetworkPrediction"), "set_prediction", "get_prediction");

	ADD_SIGNAL(MethodInfo("state_changed", PropertyInfo(Variant::INT, "state")));
}

void GameplaySessionClient::_set_state(GameplayConnection::State p_state) {
	if (state == p_state) {
		return;
	}
	state = p_state;
	emit_signal(SNAME("state_changed"), state);
}

Error GameplaySessionClient::connect_to_server(const String &p_address, int p_port, const String &p_protocol_version, const String &p_auth_token, const String &p_reconnect_token) {
	ERR_FAIL_COND_V_MSG(multiplayer_peer.is_valid(), ERR_ALREADY_IN_USE, "The session client is already in use.");
	ERR_FAIL_COND_V_MSG(p_address.is_empty() || p_port < 1 || p_port > 65535 || p_protocol_version.is_empty() || p_auth_token.is_empty(), ERR_INVALID_PARAMETER, "The client connection parameters are invalid.");
	ERR_FAIL_COND_V_MSG(!ClassDB::class_exists(SNAME("ENetMultiplayerPeer")), ERR_UNAVAILABLE, "The ENet module is not available in this build.");

	multiplayer_peer = Object::cast_to<MultiplayerPeer>(ClassDB::instantiate(SNAME("ENetMultiplayerPeer")));
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_CANT_CREATE);
	const Error create_error = Error(int(multiplayer_peer->call("create_client", p_address, p_port)));
	if (create_error != OK) {
		multiplayer_peer.unref();
		return create_error;
	}
	protocol_version = p_protocol_version;
	auth_token = p_auth_token;
	reconnect_token = p_reconnect_token;
	user_id.clear();
	stable_session_id.clear();
	rejection_reason.clear();
	state = GameplayConnection::STATE_DISCONNECTED;
	version_sent = false;
	if (GameplayMultiplayerReplication *replication = get_replication()) {
		replication->configure_client(multiplayer_peer);
	}
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->configure_client(multiplayer_peer);
	}
	return OK;
}

Error GameplaySessionClient::_send_message(const Dictionary &p_message) {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	const CharString payload = JSON::stringify(p_message).utf8();
	multiplayer_peer->set_target_peer(MultiplayerPeer::TARGET_PEER_SERVER);
	return multiplayer_peer->put_packet(reinterpret_cast<const uint8_t *>(payload.get_data()), payload.length());
}

void GameplaySessionClient::_handle_message(const Dictionary &p_message) {
	const String type = p_message.get("type", String());
	if (type == "version_accepted") {
		_set_state(GameplayConnection::STATE_VERSION_VERIFIED);
		Dictionary request;
		request["type"] = "authenticate";
		request["auth_token"] = auth_token;
		request["reconnect_token"] = reconnect_token;
		_send_message(request);
	} else if (type == "authenticated") {
		user_id = p_message.get("user_id", String());
		stable_session_id = p_message.get("session_id", String());
		reconnect_token = p_message.get("reconnect_token", String());
		_set_state(GameplayConnection::STATE_AUTHENTICATED);
		Dictionary request;
		request["type"] = "join";
		_send_message(request);
	} else if (type == "joined") {
		_set_state(GameplayConnection::STATE_SPAWNED);
	} else if (type == "rejected") {
		rejection_reason = p_message.get("reason", String("rejected"));
		_set_state(GameplayConnection::STATE_REJECTED);
	}
}

Error GameplaySessionClient::poll() {
	ERR_FAIL_COND_V(multiplayer_peer.is_null(), ERR_UNCONFIGURED);
	const MultiplayerPeer::ConnectionStatus before = multiplayer_peer->get_connection_status();
	if (before == MultiplayerPeer::CONNECTION_DISCONNECTED) {
		if (state != GameplayConnection::STATE_REJECTED) {
			_set_state(GameplayConnection::STATE_DISCONNECTED);
		}
		return ERR_CONNECTION_ERROR;
	}
	multiplayer_peer->poll();
	const MultiplayerPeer::ConnectionStatus status = multiplayer_peer->get_connection_status();
	if (status == MultiplayerPeer::CONNECTION_CONNECTED && !version_sent) {
		version_sent = true;
		_set_state(GameplayConnection::STATE_TRANSPORT_CONNECTED);
		Dictionary request;
		request["type"] = "version";
		request["protocol_version"] = protocol_version;
		_send_message(request);
	}
	while (multiplayer_peer.is_valid() && multiplayer_peer->get_available_packet_count() > 0) {
		const int sender_peer_id = multiplayer_peer->get_packet_peer();
		const uint8_t *buffer = nullptr;
		int size = 0;
		if (multiplayer_peer->get_packet(&buffer, size) != OK) {
			continue;
		}
		if (size > 4096) {
			continue;
		}
		const Variant parsed = JSON::parse_string(String::utf8(reinterpret_cast<const char *>(buffer), size));
		if (parsed.get_type() == Variant::DICTIONARY) {
			const Dictionary message = parsed;
			GameplayMultiplayerReplication *replication = get_replication();
			if (replication && replication->handles_message(message)) {
				replication->receive_packet(sender_peer_id, message, OS::get_singleton()->get_ticks_msec());
			} else if (GameplayNetworkPrediction *prediction = get_prediction(); prediction && prediction->handles_message(message)) {
				prediction->receive_packet(sender_peer_id, message, OS::get_singleton()->get_ticks_msec());
			} else {
				_handle_message(message);
			}
		}
	}
	if (GameplayMultiplayerReplication *replication = get_replication()) {
		replication->expire_reassemblies(OS::get_singleton()->get_ticks_msec());
	}
	if (GameplayNetworkPrediction *prediction = get_prediction()) {
		prediction->poll(OS::get_singleton()->get_ticks_msec());
	}
	if (multiplayer_peer.is_valid() && multiplayer_peer->get_connection_status() == MultiplayerPeer::CONNECTION_DISCONNECTED && state != GameplayConnection::STATE_REJECTED) {
		_set_state(GameplayConnection::STATE_DISCONNECTED);
	}
	return OK;
}

void GameplaySessionClient::disconnect_from_server() {
	if (multiplayer_peer.is_valid()) {
		if (GameplayMultiplayerReplication *replication = get_replication()) {
			replication->clear_transport();
		}
		if (GameplayNetworkPrediction *prediction = get_prediction()) {
			prediction->clear_transport();
		}
		multiplayer_peer->close();
		multiplayer_peer.unref();
	}
	if (state != GameplayConnection::STATE_REJECTED) {
		_set_state(GameplayConnection::STATE_DISCONNECTED);
	}
	version_sent = false;
}

GameplayConnection::State GameplaySessionClient::get_state() const {
	return state;
}

bool GameplaySessionClient::is_joined() const {
	return state == GameplayConnection::STATE_SPAWNED;
}

int GameplaySessionClient::get_peer_id() const {
	return multiplayer_peer.is_valid() ? multiplayer_peer->get_unique_id() : 0;
}

String GameplaySessionClient::get_user_id() const {
	return user_id;
}

String GameplaySessionClient::get_session_id() const {
	return stable_session_id;
}

String GameplaySessionClient::get_reconnect_token() const {
	return reconnect_token;
}

String GameplaySessionClient::get_rejection_reason() const {
	return rejection_reason;
}

Ref<MultiplayerPeer> GameplaySessionClient::get_multiplayer_peer() const {
	return multiplayer_peer;
}

void GameplaySessionClient::set_replication(GameplayMultiplayerReplication *p_replication) {
	replication_id = p_replication ? p_replication->get_instance_id() : ObjectID();
	if (p_replication && multiplayer_peer.is_valid()) {
		p_replication->configure_client(multiplayer_peer);
	}
}

GameplayMultiplayerReplication *GameplaySessionClient::get_replication() const {
	return Object::cast_to<GameplayMultiplayerReplication>(ObjectDB::get_instance(replication_id));
}

void GameplaySessionClient::set_prediction(GameplayNetworkPrediction *p_prediction) {
	prediction_id = p_prediction ? p_prediction->get_instance_id() : ObjectID();
	if (p_prediction && multiplayer_peer.is_valid()) {
		p_prediction->configure_client(multiplayer_peer);
	}
}

GameplayNetworkPrediction *GameplaySessionClient::get_prediction() const {
	return Object::cast_to<GameplayNetworkPrediction>(ObjectDB::get_instance(prediction_id));
}

GameplaySessionClient::~GameplaySessionClient() {
	disconnect_from_server();
}
