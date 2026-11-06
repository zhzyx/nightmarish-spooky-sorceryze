/**************************************************************************/
/*  test_gameplay_framework.h                                             */
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

#include "../gameplay_entity.h"
#include "../gameplay_match.h"
#include "../gameplay_server.h"
#include "../gameplay_session.h"
#include "../gameplay_subsystem.h"

#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "tests/test_macros.h"

namespace TestGameplayFramework {

class RecordingSubsystem : public GameplaySubsystem {
	Vector<String> *events = nullptr;
	String label;

protected:
	void on_initialize() override {
		events->push_back(label + ":initialize");
	}

	void on_deinitialize() override {
		events->push_back(label + ":deinitialize");
	}

public:
	RecordingSubsystem(Vector<String> *p_events, const String &p_label) {
		events = p_events;
		label = p_label;
		set_subsystem_id(label);
		set_scope(SCOPE_WORLD);
	}
};

class MutatingSubsystem : public RecordingSubsystem {
	GameplaySubsystemRegistry *registry = nullptr;
	GameplaySubsystem *added = nullptr;
	GameplaySubsystem *removed = nullptr;
	bool reregister_on_initialize = false;

protected:
	void on_initialize() override {
		RecordingSubsystem::on_initialize();
		if (added) {
			if (reregister_on_initialize) {
				registry->remove_subsystem(added);
			}
			registry->add_subsystem(added);
		}
	}

	void on_deinitialize() override {
		RecordingSubsystem::on_deinitialize();
		if (removed) {
			registry->remove_subsystem(removed);
		}
	}

public:
	MutatingSubsystem(Vector<String> *p_events, const String &p_label, GameplaySubsystemRegistry *p_registry, GameplaySubsystem *p_added, GameplaySubsystem *p_removed, bool p_reregister_on_initialize = false) :
			RecordingSubsystem(p_events, p_label), registry(p_registry), added(p_added), removed(p_removed), reregister_on_initialize(p_reregister_on_initialize) {}
};

class NestedLifecycleSubsystem : public RecordingSubsystem {
	GameplaySubsystemRegistry *registry = nullptr;

protected:
	void on_initialize() override {
		RecordingSubsystem::on_initialize();
		registry->deinitialize_subsystems();
	}

	void on_deinitialize() override {
		RecordingSubsystem::on_deinitialize();
		nested_initialize_error = registry->initialize_subsystems();
	}

public:
	Error nested_initialize_error = OK;

	NestedLifecycleSubsystem(Vector<String> *p_events, GameplaySubsystemRegistry *p_registry) :
			RecordingSubsystem(p_events, "nested"), registry(p_registry) {}
};

static Dictionary authenticate_test_user(const String &p_token, const String &p_reconnect_token) {
	Dictionary result;
	if (p_token != "alice" && p_token != "bob" && p_token != "charlie") {
		result["accepted"] = false;
		result["reason"] = "unknown_user";
		return result;
	}
	const String expected_reconnect_token = "resume-" + p_token;
	if (!p_reconnect_token.is_empty() && p_reconnect_token != expected_reconnect_token) {
		result["accepted"] = false;
		result["reason"] = "invalid_token";
		return result;
	}
	result["accepted"] = true;
	result["user_id"] = "user-" + p_token;
	result["session_id"] = "session-" + p_token;
	result["reconnect_token"] = expected_reconnect_token;
	return result;
}

class RecordingSessionChecks : public RefCounted {
public:
	int authentication_calls = 0;
	int admission_calls = 0;

	Dictionary authenticate(const String &p_token, const String &p_reconnect_token) {
		authentication_calls++;
		return authenticate_test_user(p_token, p_reconnect_token);
	}

	bool admit(const String &p_user_id, const String &p_session_id) {
		admission_calls++;
		return true;
	}
};

static bool pump_gameplay_network(GameplayDedicatedServer *p_server, const Vector<GameplaySessionClient *> &p_clients, uint64_t p_timeout_msec, const Callable &p_until) {
	const uint64_t deadline = OS::get_singleton()->get_ticks_msec() + p_timeout_msec;
	while (OS::get_singleton()->get_ticks_msec() < deadline) {
		if (p_server->is_running()) {
			p_server->poll();
		}
		for (GameplaySessionClient *client : p_clients) {
			Ref<MultiplayerPeer> peer = client->get_multiplayer_peer();
			if (peer.is_valid() && peer->get_connection_status() != MultiplayerPeer::CONNECTION_DISCONNECTED) {
				client->poll();
			}
		}
		if (bool(p_until.call())) {
			return true;
		}
		OS::get_singleton()->delay_usec(1000);
	}
	return bool(p_until.call());
}

static bool clients_joined(GameplaySessionClient *p_first, GameplaySessionClient *p_second) {
	return p_first->is_joined() && p_second->is_joined();
}

static bool session_inactive(GameplaySessionManager *p_manager, const String &p_session_id) {
	GameplayUserSession *session = p_manager->get_session(p_session_id);
	return session && !session->is_active();
}

static bool client_joined(GameplaySessionClient *p_client) {
	return p_client->is_joined();
}

static bool server_stopped(GameplayDedicatedServer *p_server) {
	return !p_server->is_running();
}

static bool client_transport_connected(GameplayDedicatedServer *p_server, GameplaySessionClient *p_client) {
	Ref<MultiplayerPeer> peer = p_client->get_multiplayer_peer();
	peer->poll();
	return peer->get_connection_status() == MultiplayerPeer::CONNECTION_CONNECTED && p_server->get_session_manager()->get_connection(p_client->get_peer_id()).is_valid();
}

static bool client_transport_closed(GameplaySessionClient *p_client) {
	Ref<MultiplayerPeer> peer = p_client->get_multiplayer_peer();
	peer->poll();
	return peer->get_connection_status() == MultiplayerPeer::CONNECTION_DISCONNECTED;
}

static bool client_rejected_or_disconnected(GameplaySessionClient *p_client) {
	return p_client->get_state() == GameplayConnection::STATE_REJECTED || p_client->get_state() == GameplayConnection::STATE_DISCONNECTED;
}

static Error send_gameplay_message(GameplaySessionClient *p_client, const Dictionary &p_message) {
	Ref<MultiplayerPeer> peer = p_client->get_multiplayer_peer();
	peer->set_target_peer(MultiplayerPeer::TARGET_PEER_SERVER);
	const CharString payload = JSON::stringify(p_message).utf8();
	return peer->put_packet(reinterpret_cast<const uint8_t *>(payload.get_data()), payload.length());
}

TEST_CASE("[Gameplay] Components keep gameplay ownership separate from scene and network ownership") {
	GameplayComponent *component = memnew(GameplayComponent);
	Node *owner = memnew(Node);

	component->set_multiplayer_authority(1);
	component->set_component_name("health");
	component->set_gameplay_owner(owner);
	component->activate();
	component->activate();

	CHECK_EQ(component->get_component_name(), StringName("health"));
	CHECK_EQ(component->get_gameplay_owner(), owner);
	CHECK(component->is_active());
	CHECK_EQ(component->get_multiplayer_authority(), 1);

	component->deactivate();
	component->deactivate();
	CHECK_FALSE(component->is_active());

	memdelete(owner);
	CHECK_EQ(component->get_gameplay_owner(), nullptr);
	memdelete(component);
}

TEST_CASE("[Gameplay] Possession remains bidirectional and keeps network authority separate") {
	GameplayController *first = memnew(GameplayController);
	GameplayController *second = memnew(GameplayController);
	GameplayPawn *pawn = memnew(GameplayPawn);

	pawn->set_multiplayer_authority(1);
	first->set_owner_peer_id(42);
	CHECK_EQ(first->possess(pawn), OK);
	CHECK_EQ(first->get_pawn(), pawn);
	CHECK_EQ(pawn->get_controller(), first);
	CHECK_EQ(pawn->get_owner_peer_id(), 42);
	CHECK_EQ(pawn->get_multiplayer_authority(), 1);

	second->set_owner_peer_id(77);
	CHECK_EQ(second->possess(pawn), OK);
	CHECK_EQ(first->get_pawn(), nullptr);
	CHECK_EQ(second->get_pawn(), pawn);
	CHECK_EQ(pawn->get_controller(), second);
	CHECK_EQ(pawn->get_owner_peer_id(), 77);
	CHECK_EQ(pawn->get_multiplayer_authority(), 1);

	second->unpossess();
	CHECK_EQ(second->get_pawn(), nullptr);
	CHECK_EQ(pawn->get_controller(), nullptr);
	CHECK_EQ(pawn->get_owner_peer_id(), 0);

	GameplayPawn *replacement = memnew(GameplayPawn);
	CHECK_EQ(first->possess(pawn), OK);
	CHECK_EQ(first->possess(replacement), OK);
	CHECK_EQ(pawn->get_controller(), nullptr);
	CHECK_EQ(pawn->get_owner_peer_id(), 0);
	CHECK_EQ(replacement->get_controller(), first);
	CHECK_EQ(replacement->get_owner_peer_id(), 42);
	memdelete(replacement);
	memdelete(pawn);
	memdelete(second);
	memdelete(first);
}

TEST_CASE("[Gameplay] Player state survives pawn replacement and can rebind controllers") {
	GameplayController *first = memnew(GameplayController);
	GameplayController *second = memnew(GameplayController);
	GameplayPlayerState *state = memnew(GameplayPlayerState);
	GameplayPawn *first_pawn = memnew(GameplayPawn);
	GameplayPawn *second_pawn = memnew(GameplayPawn);

	state->set_user_id("user-1");
	state->activate(10, "session-a");
	GameplayPlayerState *copy = memnew(GameplayPlayerState);
	state->copy_identity_to(copy);
	CHECK_EQ(copy->get_user_id(), "user-1");
	CHECK_EQ(copy->get_session_id(), "session-a");
	CHECK_EQ(copy->get_peer_id(), 10);
	CHECK(copy->is_active());
	CHECK_EQ(copy->get_controller(), nullptr);
	first->set_player_state(state);
	first->possess(first_pawn);
	first->unpossess();
	first->possess(second_pawn);

	CHECK_EQ(first->get_player_state(), state);
	CHECK_EQ(state->get_controller(), first);
	CHECK_EQ(state->get_user_id(), "user-1");
	CHECK_EQ(state->get_peer_id(), 10);

	second->set_player_state(state);
	CHECK_EQ(first->get_player_state(), nullptr);
	CHECK_EQ(second->get_player_state(), state);
	CHECK_EQ(state->get_controller(), second);

	state->deactivate();
	CHECK_FALSE(state->is_active());
	CHECK_EQ(state->get_peer_id(), 0);
	CHECK_EQ(state->get_user_id(), "user-1");

	memdelete(second_pawn);
	memdelete(first_pawn);
	memdelete(second);
	memdelete(first);
	memdelete(copy);
	memdelete(state);
}

TEST_CASE("[Gameplay] Game mode owns admission while game state owns observable player state") {
	GameplayGameMode *mode = memnew(GameplayGameMode);
	GameplayGameState *state = memnew(GameplayGameState);
	GameplayController *controller = memnew(GameplayController);
	GameplayPlayerState *player_state = memnew(GameplayPlayerState);
	GameplayPawn *pawn = memnew(GameplayPawn);

	player_state->activate(12, "session-a");
	mode->set_game_state(state);
	CHECK(mode->is_authority_context());
	CHECK_EQ(mode->admit_player(controller, player_state), OK);
	CHECK_EQ(mode->get_player_count(), 1);
	CHECK_EQ(state->get_player_count(), 1);
	CHECK_EQ(controller->get_game_mode(), mode);
	CHECK_EQ(controller->get_player_state(), player_state);
	CHECK_EQ(player_state->get_game_state(), state);

	controller->possess(pawn);
	CHECK_EQ(mode->start_match(), OK);
	CHECK(mode->is_match_running());
	CHECK_EQ(state->get_match_phase(), StringName("in_progress"));
	CHECK_EQ(mode->end_match(), OK);
	CHECK_FALSE(mode->is_match_running());
	CHECK_EQ(state->get_match_phase(), StringName("ended"));

	CHECK_EQ(mode->remove_player(controller, true), OK);
	CHECK_EQ(mode->get_player_count(), 0);
	CHECK_EQ(state->get_player_count(), 1);
	CHECK_EQ(controller->get_player_state(), nullptr);
	CHECK_EQ(controller->get_pawn(), nullptr);
	CHECK_FALSE(player_state->is_active());
	CHECK_EQ(player_state->get_peer_id(), 0);

	CHECK(state->remove_player_state(player_state));
	CHECK_EQ(state->get_player_count(), 0);

	memdelete(pawn);
	memdelete(controller);
	memdelete(player_state);
	memdelete(mode);
	memdelete(state);
}

TEST_CASE("[Gameplay] Subsystems initialize in registration order and deinitialize in reverse") {
	Vector<String> events;
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);
	RecordingSubsystem *first = memnew(RecordingSubsystem(&events, "first"));
	RecordingSubsystem *second = memnew(RecordingSubsystem(&events, "second"));

	CHECK_EQ(registry->add_subsystem(first), OK);
	CHECK_EQ(registry->add_subsystem(second), OK);
	CHECK_EQ(registry->get_subsystem("first"), first);
	CHECK_EQ(registry->get_subsystems().size(), 2);

	CHECK_EQ(registry->initialize_subsystems(), OK);
	CHECK_EQ(registry->initialize_subsystems(), OK);
	REQUIRE_EQ(events.size(), 2);
	CHECK_EQ(events[0], "first:initialize");
	CHECK_EQ(events[1], "second:initialize");

	registry->deinitialize_subsystems();
	registry->deinitialize_subsystems();
	REQUIRE_EQ(events.size(), 4);
	CHECK_EQ(events[2], "second:deinitialize");
	CHECK_EQ(events[3], "first:deinitialize");

	CHECK(registry->remove_subsystem(second));
	CHECK(registry->remove_subsystem(first));
	memdelete(second);
	memdelete(first);
	memdelete(registry);
}

TEST_CASE("[Gameplay] Gameplay world supports server and client compositions") {
	GameplayWorld *server_world = memnew(GameplayWorld);
	GameplayGameMode *mode = memnew(GameplayGameMode);
	GameplayGameState *server_state = memnew(GameplayGameState);
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);

	registry->set_scope(GameplaySubsystem::SCOPE_CONNECTION);
	ERR_PRINT_OFF;
	CHECK_EQ(server_world->initialize_world(server_state, mode, registry), ERR_INVALID_PARAMETER);
	ERR_PRINT_ON;
	CHECK_FALSE(server_world->is_initialized());
	registry->set_scope(GameplaySubsystem::SCOPE_WORLD);
	CHECK_EQ(server_world->initialize_world(server_state, mode, registry), OK);
	CHECK(server_world->is_initialized());
	CHECK_EQ(server_world->get_game_mode(), mode);
	CHECK_EQ(server_world->get_game_state(), server_state);
	CHECK_EQ(mode->get_game_state(), server_state);
	CHECK(registry->is_initialized());

	server_world->shutdown_world();
	server_world->shutdown_world();
	CHECK_FALSE(server_world->is_initialized());
	CHECK_FALSE(registry->is_initialized());

	GameplayWorld *client_world = memnew(GameplayWorld);
	GameplayGameState *client_state = memnew(GameplayGameState);
	CHECK_EQ(client_world->initialize_world(client_state), OK);
	CHECK_EQ(client_world->get_game_mode(), nullptr);
	CHECK_EQ(client_world->get_game_state(), client_state);

	memdelete(client_world);
	memdelete(client_state);
	memdelete(server_world);
	memdelete(registry);
	memdelete(mode);
	memdelete(server_state);
}

TEST_CASE("[Gameplay] Implicit teardown deinitializes owned and individually freed subsystems") {
	Vector<String> events;
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);
	RecordingSubsystem *first = memnew(RecordingSubsystem(&events, "first"));
	RecordingSubsystem *second = memnew(RecordingSubsystem(&events, "second"));
	REQUIRE_EQ(registry->add_subsystem(first), OK);
	REQUIRE_EQ(registry->add_subsystem(second), OK);
	REQUIRE_EQ(registry->initialize_subsystems(), OK);
	memdelete(registry);
	REQUIRE_EQ(events.size(), 4);
	CHECK_EQ(events[2], "second:deinitialize");
	CHECK_EQ(events[3], "first:deinitialize");

	events.clear();
	registry = memnew(GameplaySubsystemRegistry);
	first = memnew(RecordingSubsystem(&events, "single"));
	REQUIRE_EQ(registry->add_subsystem(first), OK);
	REQUIRE_EQ(registry->initialize_subsystems(), OK);
	memdelete(first);
	REQUIRE_EQ(events.size(), 2);
	CHECK_EQ(events[1], "single:deinitialize");
	CHECK_EQ(registry->get_subsystems().size(), 0);
	memdelete(registry);
}

TEST_CASE("[Gameplay] Subsystem callbacks can add and remove services without invalidating lifecycle traversal") {
	Vector<String> events;
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);
	RecordingSubsystem *second = memnew(RecordingSubsystem(&events, "second"));
	MutatingSubsystem *added = memnew(MutatingSubsystem(&events, "added", registry, nullptr, second));
	MutatingSubsystem *first = memnew(MutatingSubsystem(&events, "first", registry, added, nullptr));
	REQUIRE_EQ(registry->add_subsystem(first), OK);
	REQUIRE_EQ(registry->add_subsystem(second), OK);
	REQUIRE_EQ(registry->initialize_subsystems(), OK);
	CHECK(first->is_initialized());
	CHECK(second->is_initialized());
	CHECK(added->is_initialized());
	CHECK_EQ(registry->get_subsystems().size(), 3);
	registry->deinitialize_subsystems();
	REQUIRE_EQ(events.size(), 6);
	CHECK_EQ(events[0], "first:initialize");
	CHECK_EQ(events[1], "second:initialize");
	CHECK_EQ(events[2], "added:initialize");
	CHECK_EQ(events[3], "added:deinitialize");
	CHECK_EQ(events[4], "second:deinitialize");
	CHECK_EQ(events[5], "first:deinitialize");
	CHECK_EQ(second->get_registry(), nullptr);
	memdelete(second);
	memdelete(registry);
}

TEST_CASE("[Gameplay] Nested subsystem lifecycle requests cannot leave registry and service state inconsistent") {
	Vector<String> events;
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);
	NestedLifecycleSubsystem *first = memnew(NestedLifecycleSubsystem(&events, registry));
	RecordingSubsystem *second = memnew(RecordingSubsystem(&events, "second"));
	REQUIRE_EQ(registry->add_subsystem(first), OK);
	REQUIRE_EQ(registry->add_subsystem(second), OK);
	ERR_PRINT_OFF;
	CHECK_EQ(registry->initialize_subsystems(), OK);
	ERR_PRINT_ON;
	CHECK(registry->is_initialized());
	CHECK(first->is_initialized());
	CHECK(second->is_initialized());
	ERR_PRINT_OFF;
	registry->deinitialize_subsystems();
	ERR_PRINT_ON;
	CHECK_FALSE(registry->is_initialized());
	CHECK_FALSE(first->is_initialized());
	CHECK_FALSE(second->is_initialized());
	CHECK_EQ(first->nested_initialize_error, ERR_BUSY);
	REQUIRE_EQ(events.size(), 4);
	CHECK_EQ(events[0], "nested:initialize");
	CHECK_EQ(events[1], "second:initialize");
	CHECK_EQ(events[2], "second:deinitialize");
	CHECK_EQ(events[3], "nested:deinitialize");
	memdelete(registry);
}

TEST_CASE("[Gameplay] Re-registration during initialization preserves current order and reverse teardown") {
	Vector<String> events;
	GameplaySubsystemRegistry *registry = memnew(GameplaySubsystemRegistry);
	RecordingSubsystem *second = memnew(RecordingSubsystem(&events, "second"));
	RecordingSubsystem *third = memnew(RecordingSubsystem(&events, "third"));
	MutatingSubsystem *first = memnew(MutatingSubsystem(&events, "first", registry, second, nullptr, true));
	REQUIRE_EQ(registry->add_subsystem(first), OK);
	REQUIRE_EQ(registry->add_subsystem(second), OK);
	REQUIRE_EQ(registry->add_subsystem(third), OK);
	REQUIRE_EQ(registry->initialize_subsystems(), OK);
	registry->deinitialize_subsystems();
	REQUIRE_EQ(events.size(), 6);
	CHECK_EQ(events[0], "first:initialize");
	CHECK_EQ(events[1], "third:initialize");
	CHECK_EQ(events[2], "second:initialize");
	CHECK_EQ(events[3], "second:deinitialize");
	CHECK_EQ(events[4], "third:deinitialize");
	CHECK_EQ(events[5], "first:deinitialize");
	memdelete(registry);
}

TEST_CASE("[Gameplay][Session] Connection phases are ordered and disconnected identities survive the grace period") {
	GameplayGameState *game_state = memnew(GameplayGameState);
	GameplayGameMode *game_mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	game_mode->set_game_state(game_state);
	manager->set_game_mode(game_mode);
	manager->set_protocol_version("test-1");
	manager->set_disconnect_grace_period_msec(50);

	CHECK_EQ(manager->transport_connected(20), OK);
	ERR_PRINT_OFF;
	CHECK_EQ(manager->authenticate(20, "user-a", "session-a", "resume-a"), ERR_INVALID_DATA);
	ERR_PRINT_ON;
	CHECK_EQ(manager->verify_version(20, "test-1"), OK);
	CHECK_EQ(manager->authenticate(20, "user-a", "session-a", "resume-a"), OK);
	CHECK_EQ(manager->admit(20), OK);
	CHECK_EQ(manager->create_player(20), OK);
	CHECK_EQ(manager->spawn_player(20), OK);

	GameplayUserSession *session = manager->get_session("session-a");
	REQUIRE(session != nullptr);
	GameplayPlayerState *player_state = session->get_player_state();
	GameplayController *controller = session->get_controller();
	REQUIRE(player_state != nullptr);
	REQUIRE(controller != nullptr);
	CHECK_EQ(player_state->get_user_id(), "user-a");
	CHECK_EQ(player_state->get_peer_id(), 20);
	CHECK(controller->has_pawn());

	manager->transport_disconnected(20, 100);
	CHECK_FALSE(session->is_active());
	CHECK_EQ(player_state->get_peer_id(), 0);
	CHECK_FALSE(controller->has_pawn());
	CHECK_EQ(manager->expire_disconnected(149), 0);

	CHECK_EQ(manager->transport_connected(84), OK);
	CHECK_EQ(manager->verify_version(84, "test-1"), OK);
	CHECK_EQ(manager->authenticate(84, "user-a", "session-a", "resume-a"), OK);
	CHECK_FALSE(player_state->is_active());
	CHECK_EQ(player_state->get_peer_id(), 0);
	CHECK_EQ(controller->get_owner_peer_id(), 0);
	CHECK_EQ(manager->admit(84), OK);
	CHECK_EQ(manager->create_player(84), OK);
	CHECK_EQ(manager->spawn_player(84), OK);
	CHECK_EQ(manager->get_session("session-a"), session);
	CHECK_EQ(session->get_player_state(), player_state);
	CHECK_EQ(session->get_controller(), controller);
	CHECK_EQ(player_state->get_peer_id(), 84);
	CHECK_EQ(controller->get_owner_peer_id(), 84);

	manager->transport_disconnected(84, 200);
	CHECK_EQ(manager->expire_disconnected(250), 1);
	CHECK_EQ(manager->get_session("session-a"), nullptr);
	CHECK_EQ(game_mode->get_player_count(), 0);

	CHECK_EQ(manager->transport_connected(90), OK);
	CHECK_EQ(manager->verify_version(90, "test-1"), OK);
	CHECK_EQ(manager->authenticate(90, "user-b", "session-b", "resume-b"), OK);
	manager->set_accepting_connections(false);
	ERR_PRINT_OFF;
	CHECK_EQ(manager->admit(90), ERR_UNAVAILABLE);
	ERR_PRINT_ON;
	CHECK_EQ(manager->get_connection(90)->get_state(), GameplayConnection::STATE_AUTHENTICATED);
	manager->transport_disconnected(90, 300);
	CHECK_EQ(manager->get_session("session-b"), nullptr);

	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][DedicatedServer] ENet authenticates two clients, rebinds a changed peer, refuses joins, and drains") {
	Ref<GameplayServerConfig> parsed_config;
	parsed_config.instantiate();
	PackedStringArray arguments;
	arguments.push_back("--gameplay-bind=127.0.0.1");
	arguments.push_back("--gameplay-port");
	arguments.push_back("0");
	arguments.push_back("--gameplay-max-clients=8");
	arguments.push_back("--gameplay-protocol=integration-1");
	arguments.push_back("--gameplay-grace-msec=5000");
	arguments.push_back("--gameplay-shutdown-msec=2000");
	REQUIRE_EQ(parsed_config->apply_command_line(arguments), OK);
	CHECK_EQ(parsed_config->get_bind_address(), "127.0.0.1");
	CHECK_EQ(parsed_config->get_port(), 0);
	CHECK_EQ(parsed_config->get_max_clients(), 8);
	CHECK_EQ(parsed_config->get_protocol_version(), "integration-1");
	CHECK_EQ(parsed_config->get_disconnect_grace_period_msec(), 5000);
	CHECK_EQ(parsed_config->get_shutdown_timeout_msec(), 2000);

	GameplayGameState *game_state = memnew(GameplayGameState);
	GameplayGameMode *game_mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	GameplayDedicatedServer *server = memnew(GameplayDedicatedServer);
	game_mode->set_game_state(game_state);
	manager->set_game_mode(game_mode);
	server->set_authenticator(callable_mp_static(authenticate_test_user));
	REQUIRE_EQ(server->start(parsed_config, manager), OK);
	REQUIRE(server->get_bound_port() > 0);

	GameplaySessionClient *alice = memnew(GameplaySessionClient);
	GameplaySessionClient *bob = memnew(GameplaySessionClient);
	REQUIRE_EQ(alice->connect_to_server("127.0.0.1", server->get_bound_port(), "integration-1", "alice"), OK);
	REQUIRE_EQ(bob->connect_to_server("127.0.0.1", server->get_bound_port(), "integration-1", "bob"), OK);
	Vector<GameplaySessionClient *> initial_clients = { alice, bob };
	REQUIRE(pump_gameplay_network(server, initial_clients, 5000, callable_mp_static(clients_joined).bind(alice, bob)));
	CHECK_EQ(manager->get_active_session_count(), 2);
	CHECK_EQ(game_mode->get_player_count(), 2);

	const int old_alice_peer_id = alice->get_peer_id();
	const String alice_reconnect_token = alice->get_reconnect_token();
	GameplayUserSession *alice_session = manager->get_session("session-alice");
	REQUIRE(alice_session != nullptr);
	GameplayPlayerState *alice_player_state = alice_session->get_player_state();
	GameplayController *alice_controller = alice_session->get_controller();
	alice->disconnect_from_server();
	Vector<GameplaySessionClient *> bob_only = { bob };
	REQUIRE(pump_gameplay_network(server, bob_only, 5000, callable_mp_static(session_inactive).bind(manager, String("session-alice"))));

	GameplaySessionClient *reconnected_alice = memnew(GameplaySessionClient);
	REQUIRE_EQ(reconnected_alice->connect_to_server("127.0.0.1", server->get_bound_port(), "integration-1", "alice", alice_reconnect_token), OK);
	Vector<GameplaySessionClient *> reconnecting_clients = { bob, reconnected_alice };
	REQUIRE(pump_gameplay_network(server, reconnecting_clients, 5000, callable_mp_static(client_joined).bind(reconnected_alice)));
	CHECK_NE(reconnected_alice->get_peer_id(), old_alice_peer_id);
	CHECK_EQ(manager->get_session("session-alice"), alice_session);
	CHECK_EQ(alice_session->get_player_state(), alice_player_state);
	CHECK_EQ(alice_session->get_controller(), alice_controller);
	CHECK_EQ(alice_player_state->get_user_id(), "user-alice");
	CHECK_EQ(alice_player_state->get_peer_id(), reconnected_alice->get_peer_id());

	GameplaySessionClient *pending = memnew(GameplaySessionClient);
	REQUIRE_EQ(pending->connect_to_server("127.0.0.1", server->get_bound_port(), "integration-1", "charlie"), OK);
	REQUIRE(pump_gameplay_network(server, reconnecting_clients, 5000, callable_mp_static(client_transport_connected).bind(server, pending)));
	CHECK_EQ(server->get_transport_peer_count(), 3);
	CHECK_EQ(pending->get_state(), GameplayConnection::STATE_DISCONNECTED);
	server->refuse_new_connections();
	CHECK(server->is_refusing_new_connections());
	Vector<GameplaySessionClient *> with_pending = { bob, reconnected_alice, pending };
	pump_gameplay_network(server, with_pending, 250, callable_mp_static(client_joined).bind(pending));
	CHECK_FALSE(pending->is_joined());
	CHECK_EQ(manager->get_session("session-charlie"), nullptr);
	CHECK_EQ(game_mode->get_player_count(), 2);
	pending->disconnect_from_server();
	GameplaySessionClient *refused = memnew(GameplaySessionClient);
	REQUIRE_EQ(refused->connect_to_server("127.0.0.1", server->get_bound_port(), "integration-1", "charlie"), OK);
	Vector<GameplaySessionClient *> with_refused = { bob, reconnected_alice, refused };
	pump_gameplay_network(server, with_refused, 250, callable_mp_static(client_joined).bind(refused));
	CHECK_FALSE(refused->is_joined());
	CHECK_EQ(manager->get_active_session_count(), 2);

	server->begin_shutdown(2000);
	CHECK(server->is_shutting_down());
	bob->disconnect_from_server();
	reconnected_alice->disconnect_from_server();
	Vector<GameplaySessionClient *> no_clients;
	REQUIRE(pump_gameplay_network(server, no_clients, 2000, callable_mp_static(server_stopped).bind(server)));
	CHECK_FALSE(server->is_running());
	CHECK_EQ(manager->get_sessions().size(), 0);

	memdelete(refused);
	memdelete(pending);
	memdelete(reconnected_alice);
	memdelete(bob);
	memdelete(alice);
	memdelete(server);
	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][DedicatedServer] Out of order packets do not invoke external authentication or admission") {
	Ref<GameplayServerConfig> config;
	config.instantiate();
	config->set_bind_address("127.0.0.1");
	config->set_port(0);
	Ref<RecordingSessionChecks> checks;
	checks.instantiate();
	GameplayGameState *state = memnew(GameplayGameState);
	GameplayGameMode *mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	GameplayDedicatedServer *server = memnew(GameplayDedicatedServer);
	mode->set_game_state(state);
	manager->set_game_mode(mode);
	server->set_authenticator(callable_mp(checks.ptr(), &RecordingSessionChecks::authenticate));
	server->set_admission_check(callable_mp(checks.ptr(), &RecordingSessionChecks::admit));
	REQUIRE_EQ(server->start(config, manager), OK);
	GameplaySessionClient *early = memnew(GameplaySessionClient);
	REQUIRE_EQ(early->connect_to_server("127.0.0.1", server->get_bound_port(), "1", "alice"), OK);
	Vector<GameplaySessionClient *> no_clients;
	REQUIRE(pump_gameplay_network(server, no_clients, 5000, callable_mp_static(client_transport_connected).bind(server, early)));
	Dictionary request;
	request["type"] = "authenticate";
	request["auth_token"] = "alice";
	REQUIRE_EQ(send_gameplay_message(early, request), OK);
	REQUIRE(pump_gameplay_network(server, no_clients, 5000, callable_mp_static(client_transport_closed).bind(early)));
	CHECK_EQ(checks->authentication_calls, 0);
	CHECK_EQ(manager->get_sessions().size(), 0);

	GameplaySessionClient *joined = memnew(GameplaySessionClient);
	REQUIRE_EQ(joined->connect_to_server("127.0.0.1", server->get_bound_port(), "1", "bob"), OK);
	Vector<GameplaySessionClient *> clients = { joined };
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(client_joined).bind(joined)));
	CHECK_EQ(checks->authentication_calls, 1);
	CHECK_EQ(checks->admission_calls, 1);
	request.clear();
	request["type"] = "join";
	REQUIRE_EQ(send_gameplay_message(joined, request), OK);
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(client_rejected_or_disconnected).bind(joined)));
	CHECK_FALSE(joined->is_joined());
	CHECK_EQ(checks->admission_calls, 1);
	server->stop_now();
	memdelete(joined);
	memdelete(early);
	memdelete(server);
	memdelete(manager);
	memdelete(mode);
	memdelete(state);
}

} // namespace TestGameplayFramework
