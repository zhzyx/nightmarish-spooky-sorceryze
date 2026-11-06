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

#include "../gameplay_entity.h"
#include "../gameplay_match.h"
#include "../gameplay_prediction.h"
#include "../gameplay_replication.h"
#include "../gameplay_server.h"
#include "../gameplay_session.h"
#include "../gameplay_subsystem.h"

#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/string/print_string.h"
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

static bool three_clients_joined(GameplaySessionClient *p_first, GameplaySessionClient *p_second, GameplaySessionClient *p_third) {
	return p_first->is_joined() && p_second->is_joined() && p_third->is_joined();
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

static bool gameplay_wait_full_duration() {
	return false;
}

static int server_rpc_count = 0;
static int server_multicast_count = 0;
static int alice_owner_rpc_count = 0;
static int alice_client_rpc_count = 0;
static int alice_multicast_count = 0;
static int bob_owner_rpc_count = 0;
static int bob_client_rpc_count = 0;
static int bob_multicast_count = 0;
static int alice_rep_notify_count = 0;
static int bob_rep_notify_count = 0;

static void record_server_rpc() {
	server_rpc_count++;
}
static void record_server_multicast() {
	server_multicast_count++;
}
static void record_alice_owner_rpc() {
	alice_owner_rpc_count++;
}
static void record_alice_client_rpc() {
	alice_client_rpc_count++;
}
static void record_alice_multicast() {
	alice_multicast_count++;
}
static void record_bob_owner_rpc() {
	bob_owner_rpc_count++;
}
static void record_bob_client_rpc() {
	bob_client_rpc_count++;
}
static void record_bob_multicast() {
	bob_multicast_count++;
}
static void record_alice_rep_notify(const StringName &, const Variant &, const Variant &) {
	alice_rep_notify_count++;
}
static void record_bob_rep_notify(const StringName &, const Variant &, const Variant &) {
	bob_rep_notify_count++;
}

static Ref<GameplayReplicationProperty> make_replication_property(const StringName &p_name, GameplayReplicationProperty::Condition p_condition = GameplayReplicationProperty::CONDITION_ALWAYS, bool p_rep_notify = false, uint64_t p_interval_msec = 0) {
	Ref<GameplayReplicationProperty> descriptor;
	descriptor.instantiate();
	descriptor->set_property_name(p_name);
	descriptor->set_condition(p_condition);
	descriptor->set_rep_notify(p_rep_notify);
	descriptor->set_update_interval_msec(p_interval_msec);
	return descriptor;
}

static Ref<GameplayRPCConfig> make_rpc_config(const StringName &p_name, GameplayRPCConfig::Direction p_direction, bool p_require_owner = false) {
	Ref<GameplayRPCConfig> config;
	config.instantiate();
	config->set_rpc_name(p_name);
	config->set_direction(p_direction);
	config->set_require_owner(p_require_owner);
	return config;
}

static Ref<GameplayConnectionView> make_connection_view(int p_peer_id, const Vector3 &p_position, int p_team_id, int p_budget_bytes = 4096) {
	Ref<GameplayConnectionView> view;
	view.instantiate();
	view->set_peer_id(p_peer_id);
	view->set_position(p_position);
	view->set_team_id(p_team_id);
	view->set_bandwidth_budget_bytes(p_budget_bytes);
	return view;
}

static Ref<GameplayRelevancyObject> make_relevancy_object(int p_object_id, GameplayRelevancyObject::Policy p_policy, const Vector3 &p_position = Vector3(), int p_owner_peer_id = 0, int p_team_id = 0, float p_cull_distance = 100.0f, int p_priority = 1, uint64_t p_interval_msec = 0, int p_estimated_bytes = 128) {
	Ref<GameplayRelevancyObject> object;
	object.instantiate();
	object->set_object_id(p_object_id);
	object->set_policy(p_policy);
	object->set_position(p_position);
	object->set_owner_peer_id(p_owner_peer_id);
	object->set_team_id(p_team_id);
	object->set_cull_distance(p_cull_distance);
	object->set_priority(p_priority);
	object->set_update_interval_msec(p_interval_msec);
	object->set_estimated_update_bytes(p_estimated_bytes);
	return object;
}

static Ref<GameplayPredictionState> make_prediction_state(const Vector3 &p_position, const Vector3 &p_velocity = Vector3(), uint64_t p_sequence = 0, uint64_t p_server_time_msec = 0) {
	Ref<GameplayPredictionState> state;
	state.instantiate();
	state->set_position(p_position);
	state->set_velocity(p_velocity);
	state->set_confirmed_sequence(p_sequence);
	state->set_server_time_msec(p_server_time_msec);
	return state;
}

static Ref<GameplayPredictionInput> make_prediction_input(uint64_t p_sequence, const Vector3 &p_input, uint32_t p_step_msec) {
	Ref<GameplayPredictionInput> input;
	input.instantiate();
	input->set_sequence(p_sequence);
	input->set_movement_input(p_input);
	input->set_step_msec(p_step_msec);
	return input;
}

static bool predictions_settled(GameplayNetworkPrediction *p_server_prediction, const Ref<GameplayClientPrediction> &p_first, int p_first_object, const Ref<GameplayClientPrediction> &p_second, int p_second_object) {
	const Ref<GameplayPredictionState> first_server = p_server_prediction->get_server_object_state(p_first_object);
	const Ref<GameplayPredictionState> second_server = p_server_prediction->get_server_object_state(p_second_object);
	return first_server.is_valid() && second_server.is_valid() && p_first->get_unconfirmed_input_count() == 0 && p_second->get_unconfirmed_input_count() == 0 && p_first->get_predicted_state()->get_position().is_equal_approx(first_server->get_position()) && p_second->get_predicted_state()->get_position().is_equal_approx(second_server->get_position());
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
	manager->transport_disconnected(90, 300);
	CHECK_EQ(manager->get_session("session-b"), nullptr);

	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][Replication] Conditions, dirty state, RepNotify, and frequency are transport independent") {
	Ref<GameplayReplicationState> authority;
	authority.instantiate();
	CHECK_EQ(authority->add_property(make_replication_property("initial", GameplayReplicationProperty::CONDITION_INITIAL_ONLY), 10), OK);
	CHECK_EQ(authority->add_property(make_replication_property("owner", GameplayReplicationProperty::CONDITION_OWNER_ONLY), 20), OK);
	CHECK_EQ(authority->add_property(make_replication_property("skip_owner", GameplayReplicationProperty::CONDITION_SKIP_OWNER), 30), OK);
	CHECK_EQ(authority->add_property(make_replication_property("notify", GameplayReplicationProperty::CONDITION_ALWAYS, true), 40), OK);
	CHECK_EQ(authority->add_property(make_replication_property("throttled", GameplayReplicationProperty::CONDITION_ALWAYS, false, 100), 50), OK);

	authority->register_peer(10);
	authority->register_peer(20);
	const Array owner_initial = authority->collect_updates(10, 10, 100);
	const Array other_initial = authority->collect_updates(20, 10, 100);
	CHECK_EQ(owner_initial.size(), 4);
	CHECK_EQ(other_initial.size(), 4);
	CHECK_FALSE(authority->is_property_dirty_for_peer("initial", 10));

	CHECK_EQ(authority->set_property_value("initial", 11), OK);
	CHECK_EQ(authority->set_property_value("owner", 21), OK);
	CHECK_EQ(authority->set_property_value("skip_owner", 31), OK);
	CHECK_EQ(authority->set_property_value("throttled", 51), OK);
	const Array owner_throttled = authority->collect_updates(10, 10, 150);
	const Array other_throttled = authority->collect_updates(20, 10, 150);
	REQUIRE_EQ(owner_throttled.size(), 1);
	CHECK_EQ(StringName(Dictionary(owner_throttled[0]).get("name", StringName())), StringName("owner"));
	REQUIRE_EQ(other_throttled.size(), 1);
	CHECK_EQ(StringName(Dictionary(other_throttled[0]).get("name", StringName())), StringName("skip_owner"));
	const Array owner_later = authority->collect_updates(10, 10, 200);
	CHECK_EQ(owner_later.size(), 1);
	CHECK_EQ(StringName(Dictionary(owner_later[0]).get("name", StringName())), StringName("throttled"));
	authority->reset_peer_updates(10, owner_later);
	CHECK(authority->is_property_dirty_for_peer("throttled", 10));
	CHECK_FALSE(authority->is_property_dirty_for_peer("initial", 10));

	Ref<GameplayReplicationState> client;
	client.instantiate();
	CHECK_EQ(client->add_property(make_replication_property("notify", GameplayReplicationProperty::CONDITION_ALWAYS, true), 0), OK);
	alice_rep_notify_count = 0;
	client->set_rep_notify_handler(callable_mp_static(record_alice_rep_notify));
	Array updates;
	Dictionary update;
	update["name"] = "notify";
	update["value"] = 99;
	update["revision"] = 2;
	updates.push_back(update);
	CHECK_EQ(client->apply_updates(updates), OK);
	CHECK_EQ(int(client->get_property_value("notify")), 99);
	CHECK_EQ(alice_rep_notify_count, 1);
	CHECK_EQ(client->apply_updates(updates), OK);
	CHECK_EQ(alice_rep_notify_count, 1);
}

TEST_CASE("[Gameplay][Replication] Fragmentation has bounded deterministic reassembly") {
	Ref<GameplayReplicationFragmenter> fragmenter;
	fragmenter.instantiate();
	fragmenter->set_chunk_payload_bytes(512);
	fragmenter->set_max_transfer_bytes(2048);
	fragmenter->set_max_pending_assemblies(2);
	fragmenter->set_assembly_timeout_msec(100);

	PackedByteArray payload;
	payload.resize(1500);
	for (int i = 0; i < payload.size(); i++) {
		payload.write[i] = uint8_t(i % 251);
	}
	const Array fragments = fragmenter->fragment(7, payload);
	REQUIRE_EQ(fragments.size(), 3);
	CHECK_EQ(String(fragmenter->accept_fragment(1, fragments[2], 10).get("status", String())), "pending");
	CHECK_EQ(String(fragmenter->accept_fragment(1, fragments[0], 11).get("status", String())), "pending");
	CHECK_EQ(String(fragmenter->accept_fragment(1, fragments[0], 12).get("status", String())), "duplicate");
	const Dictionary complete = fragmenter->accept_fragment(1, fragments[1], 13);
	CHECK_EQ(String(complete.get("status", String())), "complete");
	CHECK_EQ(PackedByteArray(complete.get("payload", PackedByteArray())), payload);
	CHECK_EQ(String(fragmenter->accept_fragment(1, fragments[1], 14).get("reason", String())), "stale_sequence");

	const Array conflicting = fragmenter->fragment(8, payload);
	REQUIRE_EQ(conflicting.size(), 3);
	CHECK_EQ(String(fragmenter->accept_fragment(1, conflicting[0], 20).get("status", String())), "pending");
	Dictionary changed = conflicting[0];
	PackedByteArray changed_payload = changed["payload"];
	changed_payload.write[0] ^= 1;
	changed["payload"] = changed_payload;
	CHECK_EQ(String(fragmenter->accept_fragment(1, changed, 21).get("reason", String())), "conflicting_duplicate_fragment");

	const Array missing = fragmenter->fragment(9, payload);
	CHECK_EQ(String(fragmenter->accept_fragment(1, missing[0], 30).get("status", String())), "pending");
	CHECK_EQ(fragmenter->expire_assemblies(131), 1);
	CHECK_EQ(fragmenter->get_last_error(), "missing_fragments");

	fragmenter->set_max_transfer_bytes(1024);
	CHECK(fragmenter->fragment(10, payload).is_empty());
	CHECK_EQ(fragmenter->get_last_error(), "transfer_too_large");
	Dictionary oversized;
	oversized["sequence"] = 10;
	oversized["chunk_index"] = 0;
	oversized["chunk_count"] = 3;
	oversized["total_size"] = 1500;
	oversized["payload"] = PackedByteArray();
	CHECK_EQ(String(fragmenter->accept_fragment(1, oversized, 140).get("reason", String())), "invalid_fragment_header");
}

TEST_CASE("[Gameplay][Relevancy] Connection views combine distance, owner, team, and always policies deterministically") {
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	graph->set_cell_size(100.0f);
	graph->set_max_spatial_distance(1000.0f);
	REQUIRE_EQ(graph->add_connection(make_connection_view(10, Vector3(0, 0, 0), 1)), OK);
	REQUIRE_EQ(graph->add_connection(make_connection_view(20, Vector3(1000, 0, 0), 1)), OK);
	REQUIRE_EQ(graph->add_connection(make_connection_view(30, Vector3(0, 0, 0), 2)), OK);

	REQUIRE_EQ(graph->add_object(make_relevancy_object(1, GameplayRelevancyObject::POLICY_DISTANCE, Vector3(0, 0, 0), 0, 0, 100.0f)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(2, GameplayRelevancyObject::POLICY_OWNER_ONLY, Vector3(), 20)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(3, GameplayRelevancyObject::POLICY_TEAM_ONLY, Vector3(), 0, 1)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(4, GameplayRelevancyObject::POLICY_OWNER_OR_TEAM, Vector3(), 30, 1)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(5, GameplayRelevancyObject::POLICY_ALWAYS)), OK);

	const Dictionary alice_plan = graph->plan_connection(10, 0);
	const Dictionary bob_plan = graph->plan_connection(20, 0);
	const Dictionary charlie_plan = graph->plan_connection(30, 0);
	const Array alice_relevant = graph->get_relevant_object_ids(10);
	const Array bob_relevant = graph->get_relevant_object_ids(20);
	const Array charlie_relevant = graph->get_relevant_object_ids(30);
	CHECK(alice_relevant.has(1));
	CHECK_FALSE(alice_relevant.has(2));
	CHECK(alice_relevant.has(3));
	CHECK(alice_relevant.has(4));
	CHECK(alice_relevant.has(5));
	CHECK_FALSE(bob_relevant.has(1));
	CHECK(bob_relevant.has(2));
	CHECK(bob_relevant.has(3));
	CHECK(bob_relevant.has(4));
	CHECK(bob_relevant.has(5));
	CHECK(charlie_relevant.has(1));
	CHECK_FALSE(charlie_relevant.has(2));
	CHECK_FALSE(charlie_relevant.has(3));
	CHECK(charlie_relevant.has(4));
	CHECK(charlie_relevant.has(5));
	CHECK_EQ(int(alice_plan.get("relevant_count", 0)), 4);
	CHECK_EQ(int(bob_plan.get("relevant_count", 0)), 4);
	CHECK_EQ(int(charlie_plan.get("relevant_count", 0)), 3);

	Ref<GameplayRelevancyObject> moved = make_relevancy_object(1, GameplayRelevancyObject::POLICY_DISTANCE, Vector3(1000, 0, 0), 0, 0, 100.0f);
	REQUIRE_EQ(graph->update_object(moved), OK);
	const Dictionary alice_after_object_move = graph->plan_connection(10, 1);
	const Dictionary bob_after_object_move = graph->plan_connection(20, 1);
	const Dictionary charlie_after_object_move = graph->plan_connection(30, 1);
	CHECK(Array(alice_after_object_move.get("left", Array())).has(1));
	CHECK(Array(bob_after_object_move.get("entered", Array())).has(1));
	CHECK(Array(charlie_after_object_move.get("left", Array())).has(1));
	CHECK_FALSE(graph->get_relevant_object_ids(10).has(1));
	CHECK(graph->get_relevant_object_ids(20).has(1));
	CHECK_FALSE(graph->get_relevant_object_ids(30).has(1));

	REQUIRE_EQ(graph->update_connection(make_connection_view(10, Vector3(1000, 0, 0), 1)), OK);
	const Dictionary alice_after_view_move = graph->plan_connection(10, 2);
	CHECK(Array(alice_after_view_move.get("entered", Array())).has(1));
	CHECK(graph->get_relevant_object_ids(10).has(1));
}

TEST_CASE("[Gameplay][Relevancy] Priority, frequency, and bandwidth scheduling is stable and starvation bounded") {
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	REQUIRE_EQ(graph->add_connection(make_connection_view(10, Vector3(), 1, 100)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(1, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), 0, 0, 100.0f, 10, 100, 100)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(2, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), 0, 0, 100.0f, 10, 0, 100)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(3, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), 0, 0, 100.0f, 0, 0, 100)), OK);

	Dictionary plan = graph->plan_connection(10, 0);
	Array selected = plan.get("selected", Array());
	REQUIRE_EQ(selected.size(), 1);
	CHECK_EQ(int(selected[0]), 1);
	CHECK_EQ(int(plan.get("estimated_bytes", 0)), 100);
	REQUIRE_EQ(graph->record_send_result(10, 1, 0, 92, true), OK);

	plan = graph->plan_connection(10, 50);
	selected = plan.get("selected", Array());
	CHECK_FALSE(selected.has(1));
	REQUIRE_EQ(selected.size(), 1);
	REQUIRE_EQ(graph->record_send_result(10, int(selected[0]), 50, 88, true), OK);

	bool low_priority_sent = false;
	for (uint64_t tick = 51; tick < 80; tick++) {
		plan = graph->plan_connection(10, tick);
		selected = plan.get("selected", Array());
		REQUIRE_EQ(selected.size(), 1);
		const int object_id = selected[0];
		if (object_id == 3) {
			low_priority_sent = true;
		}
		REQUIRE_EQ(graph->record_send_result(10, object_id, tick, 90, true), OK);
		if (low_priority_sent) {
			break;
		}
	}
	CHECK(low_priority_sent);

	REQUIRE_EQ(graph->update_connection(make_connection_view(10, Vector3(), 1, 200)), OK);
	plan = graph->plan_connection(10, 100);
	selected = plan.get("selected", Array());
	CHECK(selected.has(1));
	CHECK_LE(int(plan.get("estimated_bytes", 0)), int(plan.get("bandwidth_budget_bytes", 0)));
}

TEST_CASE("[Gameplay][Relevancy] Dormancy stops scheduling and wakes on dirty serial or explicit request") {
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	REQUIRE_EQ(graph->add_connection(make_connection_view(10, Vector3(), 1, 128)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(1, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), 0, 0, 100.0f, 1, 0, 128)), OK);
	Dictionary plan = graph->plan_connection(10, 0);
	REQUIRE(Array(plan.get("selected", Array())).has(1));
	REQUIRE_EQ(graph->record_send_result(10, 1, 0, 100, true), OK);

	REQUIRE_EQ(graph->set_object_dormant(1, true, 7), OK);
	CHECK(graph->is_object_dormant(1));
	plan = graph->plan_connection(10, 1);
	CHECK(Array(plan.get("selected", Array())).is_empty());
	REQUIRE_EQ(graph->notify_object_dirty(1, 7), OK);
	CHECK(graph->is_object_dormant(1));
	REQUIRE_EQ(graph->notify_object_dirty(1, 8), OK);
	CHECK_FALSE(graph->is_object_dormant(1));
	plan = graph->plan_connection(10, 2);
	CHECK(Array(plan.get("selected", Array())).has(1));

	REQUIRE_EQ(graph->set_object_dormant(1, true, 8), OK);
	REQUIRE_EQ(graph->wake_object(1), OK);
	CHECK_FALSE(graph->is_object_dormant(1));
	plan = graph->plan_connection(10, 3);
	CHECK(Array(plan.get("selected", Array())).has(1));
}

TEST_CASE("[Gameplay][Relevancy][Benchmark] Spatial candidate planning records representative CPU and byte estimates") {
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	graph->set_cell_size(100.0f);
	graph->set_max_spatial_distance(300.0f);
	constexpr int object_count = 4096;
	constexpr int connection_count = 32;
	for (int i = 0; i < object_count; i++) {
		const Vector3 position(float(i % 64) * 25.0f, 0.0f, float(i / 64) * 25.0f);
		REQUIRE_EQ(graph->add_object(make_relevancy_object(i + 1, GameplayRelevancyObject::POLICY_DISTANCE, position, 0, 0, 150.0f, i % 8, 0, 128)), OK);
	}
	for (int i = 0; i < connection_count; i++) {
		const Vector3 position(float((i * 7) % 64) * 25.0f, 0.0f, float((i * 13) % 64) * 25.0f);
		REQUIRE_EQ(graph->add_connection(make_connection_view(i + 2, position, (i % 2) + 1, 8192)), OK);
	}
	const uint64_t started_usec = OS::get_singleton()->get_ticks_usec();
	int total_candidates = 0;
	int total_relevant = 0;
	int total_selected = 0;
	int total_estimated_bytes = 0;
	for (int i = 0; i < connection_count; i++) {
		const Dictionary plan = graph->plan_connection(i + 2, 1000);
		total_candidates += int(plan.get("candidate_count", 0));
		total_relevant += int(plan.get("relevant_count", 0));
		total_selected += int(plan.get("selected_count", 0));
		total_estimated_bytes += int(plan.get("estimated_bytes", 0));
	}
	const uint64_t elapsed_usec = OS::get_singleton()->get_ticks_usec() - started_usec;
	CHECK_GT(total_candidates, 0);
	CHECK_GT(total_relevant, 0);
	CHECK_GT(total_selected, 0);
	CHECK_LE(total_estimated_bytes, connection_count * 8192);
	print_line(vformat("GAMEPLAY_RELEVANCY_BENCHMARK objects=%d connections=%d cpu_usec=%d candidates=%d relevant=%d selected=%d estimated_bytes=%d", object_count, connection_count, elapsed_usec, total_candidates, total_relevant, total_selected, total_estimated_bytes));
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

	server->refuse_new_connections();
	CHECK(server->is_refusing_new_connections());
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
	memdelete(reconnected_alice);
	memdelete(bob);
	memdelete(alice);
	memdelete(server);
	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][Replication] ENet server and two clients enforce RPC authority and replication policy") {
	server_rpc_count = 0;
	server_multicast_count = 0;
	alice_owner_rpc_count = 0;
	alice_client_rpc_count = 0;
	alice_multicast_count = 0;
	bob_owner_rpc_count = 0;
	bob_client_rpc_count = 0;
	bob_multicast_count = 0;
	alice_rep_notify_count = 0;
	bob_rep_notify_count = 0;

	GameplayGameState *game_state = memnew(GameplayGameState);
	GameplayGameMode *game_mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	GameplayDedicatedServer *server = memnew(GameplayDedicatedServer);
	GameplayMultiplayerReplication *server_replication = memnew(GameplayMultiplayerReplication);
	game_mode->set_game_state(game_state);
	manager->set_game_mode(game_mode);
	server->set_authenticator(callable_mp_static(authenticate_test_user));
	server->set_replication(server_replication);

	Ref<GameplayServerConfig> config;
	config.instantiate();
	config->set_bind_address("127.0.0.1");
	config->set_port(0);
	config->set_protocol_version("replication-1");
	REQUIRE_EQ(server->start(config, manager), OK);

	GameplaySessionClient *alice = memnew(GameplaySessionClient);
	GameplaySessionClient *bob = memnew(GameplaySessionClient);
	GameplayMultiplayerReplication *alice_replication = memnew(GameplayMultiplayerReplication);
	GameplayMultiplayerReplication *bob_replication = memnew(GameplayMultiplayerReplication);
	alice->set_replication(alice_replication);
	bob->set_replication(bob_replication);
	REQUIRE_EQ(alice->connect_to_server("127.0.0.1", server->get_bound_port(), "replication-1", "alice"), OK);
	REQUIRE_EQ(bob->connect_to_server("127.0.0.1", server->get_bound_port(), "replication-1", "bob"), OK);
	Vector<GameplaySessionClient *> clients = { alice, bob };
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(clients_joined).bind(alice, bob)));
	const int alice_peer_id = alice->get_peer_id();
	const int bob_peer_id = bob->get_peer_id();
	REQUIRE(alice_peer_id > 1);
	REQUIRE(bob_peer_id > 1);
	REQUIRE_NE(alice_peer_id, bob_peer_id);

	Ref<GameplayReplicationState> server_state;
	Ref<GameplayReplicationState> alice_state;
	Ref<GameplayReplicationState> bob_state;
	server_state.instantiate();
	alice_state.instantiate();
	bob_state.instantiate();
	const Ref<GameplayReplicationProperty> initial_property = make_replication_property("initial", GameplayReplicationProperty::CONDITION_INITIAL_ONLY);
	const Ref<GameplayReplicationProperty> owner_property = make_replication_property("owner", GameplayReplicationProperty::CONDITION_OWNER_ONLY);
	const Ref<GameplayReplicationProperty> skip_owner_property = make_replication_property("skip_owner", GameplayReplicationProperty::CONDITION_SKIP_OWNER);
	const Ref<GameplayReplicationProperty> notify_property = make_replication_property("notify", GameplayReplicationProperty::CONDITION_ALWAYS, true);
	const Ref<GameplayReplicationProperty> throttled_property = make_replication_property("throttled", GameplayReplicationProperty::CONDITION_ALWAYS, false, 1000);
	const Ref<GameplayReplicationProperty> large_property = make_replication_property("large");
	const Vector<Ref<GameplayReplicationProperty>> descriptors = { initial_property, owner_property, skip_owner_property, notify_property, throttled_property, large_property };
	const Array server_initial_values = { 10, 20, 30, 40, 50, PackedByteArray() };
	const Array client_initial_values = { 0, 0, 0, 0, 0, PackedByteArray() };
	for (int i = 0; i < descriptors.size(); i++) {
		REQUIRE_EQ(server_state->add_property(descriptors[i], server_initial_values[i]), OK);
		REQUIRE_EQ(alice_state->add_property(descriptors[i], client_initial_values[i]), OK);
		REQUIRE_EQ(bob_state->add_property(descriptors[i], client_initial_values[i]), OK);
	}
	alice_state->set_rep_notify_handler(callable_mp_static(record_alice_rep_notify));
	bob_state->set_rep_notify_handler(callable_mp_static(record_bob_rep_notify));
	REQUIRE_EQ(server_replication->register_object(100, alice_peer_id, server_state), OK);
	REQUIRE_EQ(alice_replication->register_object(100, alice_peer_id, alice_state), OK);
	REQUIRE_EQ(bob_replication->register_object(100, alice_peer_id, bob_state), OK);

	pump_gameplay_network(server, clients, 250, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_state->get_property_value("initial")), 10);
	CHECK_EQ(int(bob_state->get_property_value("initial")), 10);
	CHECK_EQ(int(alice_state->get_property_value("owner")), 20);
	CHECK_EQ(int(bob_state->get_property_value("owner")), 0);
	CHECK_EQ(int(alice_state->get_property_value("skip_owner")), 0);
	CHECK_EQ(int(bob_state->get_property_value("skip_owner")), 30);
	alice_rep_notify_count = 0;
	bob_rep_notify_count = 0;

	PackedByteArray large_value;
	large_value.resize(4096);
	for (int i = 0; i < large_value.size(); i++) {
		large_value.write[i] = uint8_t(i % 239);
	}
	CHECK_EQ(server_state->set_property_value("initial", 11), OK);
	CHECK_EQ(server_state->set_property_value("owner", 21), OK);
	CHECK_EQ(server_state->set_property_value("skip_owner", 31), OK);
	CHECK_EQ(server_state->set_property_value("notify", 41), OK);
	CHECK_EQ(server_state->set_property_value("throttled", 51), OK);
	CHECK_EQ(server_state->set_property_value("large", large_value), OK);
	pump_gameplay_network(server, clients, 300, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_state->get_property_value("initial")), 10);
	CHECK_EQ(int(bob_state->get_property_value("initial")), 10);
	CHECK_EQ(int(alice_state->get_property_value("owner")), 21);
	CHECK_EQ(int(bob_state->get_property_value("owner")), 0);
	CHECK_EQ(int(alice_state->get_property_value("skip_owner")), 0);
	CHECK_EQ(int(bob_state->get_property_value("skip_owner")), 31);
	CHECK_EQ(int(alice_state->get_property_value("notify")), 41);
	CHECK_EQ(int(bob_state->get_property_value("notify")), 41);
	CHECK_EQ(alice_rep_notify_count, 1);
	CHECK_EQ(bob_rep_notify_count, 1);
	CHECK_EQ(int(alice_state->get_property_value("throttled")), 50);
	CHECK_EQ(int(bob_state->get_property_value("throttled")), 50);
	CHECK_EQ(PackedByteArray(alice_state->get_property_value("large")), large_value);
	CHECK_EQ(PackedByteArray(bob_state->get_property_value("large")), large_value);
	CHECK_EQ(alice_replication->get_fragmenter()->get_pending_assembly_count(), 0);
	CHECK_EQ(bob_replication->get_fragmenter()->get_pending_assembly_count(), 0);

	CHECK_EQ(server_replication->replicate(OS::get_singleton()->get_ticks_msec() + 2000), OK);
	pump_gameplay_network(server, clients, 100, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_state->get_property_value("throttled")), 51);
	CHECK_EQ(int(bob_state->get_property_value("throttled")), 51);

	const Ref<GameplayRPCConfig> server_action = make_rpc_config("server_action", GameplayRPCConfig::DIRECTION_SERVER, true);
	const Ref<GameplayRPCConfig> owner_notice = make_rpc_config("owner_notice", GameplayRPCConfig::DIRECTION_OWNER);
	const Ref<GameplayRPCConfig> client_notice = make_rpc_config("client_notice", GameplayRPCConfig::DIRECTION_CLIENT);
	const Ref<GameplayRPCConfig> multicast_notice = make_rpc_config("multicast_notice", GameplayRPCConfig::DIRECTION_MULTICAST);
	REQUIRE_EQ(server_replication->register_rpc(100, server_action, callable_mp_static(record_server_rpc)), OK);
	REQUIRE_EQ(server_replication->register_rpc(100, owner_notice, callable_mp_static(record_server_multicast)), OK);
	REQUIRE_EQ(server_replication->register_rpc(100, client_notice, callable_mp_static(record_server_multicast)), OK);
	REQUIRE_EQ(server_replication->register_rpc(100, multicast_notice, callable_mp_static(record_server_multicast)), OK);
	REQUIRE_EQ(alice_replication->register_rpc(100, server_action, callable_mp_static(record_alice_client_rpc)), OK);
	REQUIRE_EQ(alice_replication->register_rpc(100, owner_notice, callable_mp_static(record_alice_owner_rpc)), OK);
	REQUIRE_EQ(alice_replication->register_rpc(100, client_notice, callable_mp_static(record_alice_client_rpc)), OK);
	REQUIRE_EQ(alice_replication->register_rpc(100, multicast_notice, callable_mp_static(record_alice_multicast)), OK);
	REQUIRE_EQ(bob_replication->register_rpc(100, server_action, callable_mp_static(record_bob_client_rpc)), OK);
	REQUIRE_EQ(bob_replication->register_rpc(100, owner_notice, callable_mp_static(record_bob_owner_rpc)), OK);
	REQUIRE_EQ(bob_replication->register_rpc(100, client_notice, callable_mp_static(record_bob_client_rpc)), OK);
	REQUIRE_EQ(bob_replication->register_rpc(100, multicast_notice, callable_mp_static(record_bob_multicast)), OK);

	CHECK_EQ(alice_replication->invoke_rpc(100, "server_action"), OK);
	pump_gameplay_network(server, clients, 100, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(server_rpc_count, 1);
	CHECK_EQ(bob_replication->invoke_rpc(100, "server_action"), OK);
	pump_gameplay_network(server, clients, 100, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(server_rpc_count, 1);
	CHECK_EQ(server_replication->get_last_rejection_reason(), "gameplay_owner_mismatch");

	Dictionary forged;
	forged["type"] = "gameplay_rpc";
	forged["sender_peer_id"] = bob_peer_id;
	forged["object_id"] = 100;
	forged["rpc_name"] = "server_action";
	CHECK_EQ(server_replication->receive_packet(alice_peer_id, forged, OS::get_singleton()->get_ticks_msec()), ERR_UNAUTHORIZED);
	CHECK_EQ(server_replication->get_last_rejection_reason(), "sender_mismatch");
	CHECK_EQ(alice_replication->invoke_rpc(100, "multicast_notice"), ERR_UNAUTHORIZED);
	CHECK_EQ(alice_replication->get_last_rejection_reason(), "client_cannot_send_authority_rpc");

	CHECK_EQ(server_replication->invoke_rpc(100, "owner_notice"), OK);
	CHECK_EQ(server_replication->invoke_rpc(100, "client_notice", Array(), bob_peer_id), OK);
	CHECK_EQ(server_replication->invoke_rpc(100, "multicast_notice"), OK);
	pump_gameplay_network(server, clients, 150, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(alice_owner_rpc_count, 1);
	CHECK_EQ(bob_owner_rpc_count, 0);
	CHECK_EQ(alice_client_rpc_count, 0);
	CHECK_EQ(bob_client_rpc_count, 1);
	CHECK_EQ(server_multicast_count, 1);
	CHECK_EQ(alice_multicast_count, 1);
	CHECK_EQ(bob_multicast_count, 1);

	alice->disconnect_from_server();
	bob->disconnect_from_server();
	server->stop_now();
	memdelete(bob);
	memdelete(alice);
	memdelete(bob_replication);
	memdelete(alice_replication);
	memdelete(server);
	memdelete(server_replication);
	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][Relevancy] ENet synchronizes only server-selected objects for three distinct connection views") {
	GameplayGameState *game_state = memnew(GameplayGameState);
	GameplayGameMode *game_mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	GameplayDedicatedServer *server = memnew(GameplayDedicatedServer);
	GameplayMultiplayerReplication *server_replication = memnew(GameplayMultiplayerReplication);
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	game_mode->set_game_state(game_state);
	manager->set_game_mode(game_mode);
	server->set_authenticator(callable_mp_static(authenticate_test_user));
	REQUIRE_EQ(server_replication->set_replication_graph(graph), OK);
	server->set_replication(server_replication);

	Ref<GameplayServerConfig> config;
	config.instantiate();
	config->set_bind_address("127.0.0.1");
	config->set_port(0);
	config->set_protocol_version("relevancy-1");
	REQUIRE_EQ(server->start(config, manager), OK);

	GameplaySessionClient *alice = memnew(GameplaySessionClient);
	GameplaySessionClient *bob = memnew(GameplaySessionClient);
	GameplaySessionClient *charlie = memnew(GameplaySessionClient);
	GameplayMultiplayerReplication *alice_replication = memnew(GameplayMultiplayerReplication);
	GameplayMultiplayerReplication *bob_replication = memnew(GameplayMultiplayerReplication);
	GameplayMultiplayerReplication *charlie_replication = memnew(GameplayMultiplayerReplication);
	alice->set_replication(alice_replication);
	bob->set_replication(bob_replication);
	charlie->set_replication(charlie_replication);
	REQUIRE_EQ(alice->connect_to_server("127.0.0.1", server->get_bound_port(), "relevancy-1", "alice"), OK);
	REQUIRE_EQ(bob->connect_to_server("127.0.0.1", server->get_bound_port(), "relevancy-1", "bob"), OK);
	REQUIRE_EQ(charlie->connect_to_server("127.0.0.1", server->get_bound_port(), "relevancy-1", "charlie"), OK);
	Vector<GameplaySessionClient *> clients = { alice, bob, charlie };
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(three_clients_joined).bind(alice, bob, charlie)));
	const int alice_peer_id = alice->get_peer_id();
	const int bob_peer_id = bob->get_peer_id();
	const int charlie_peer_id = charlie->get_peer_id();
	REQUIRE(alice_peer_id > 1);
	REQUIRE(bob_peer_id > 1);
	REQUIRE(charlie_peer_id > 1);
	REQUIRE_NE(alice_peer_id, bob_peer_id);
	REQUIRE_NE(alice_peer_id, charlie_peer_id);
	REQUIRE_NE(bob_peer_id, charlie_peer_id);

	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(alice_peer_id, Vector3(0, 0, 0), 1)), OK);
	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(bob_peer_id, Vector3(1000, 0, 0), 1)), OK);
	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(charlie_peer_id, Vector3(0, 0, 0), 2)), OK);
	ERR_PRINT_OFF;
	CHECK_EQ(alice_replication->set_replication_graph(graph), ERR_UNAUTHORIZED);
	ERR_PRINT_ON;

	const int object_ids[] = { 100, 200, 300, 400 };
	const int initial_values[] = { 10, 20, 30, 40 };
	Vector<Ref<GameplayReplicationState>> server_states;
	Vector<Ref<GameplayReplicationState>> alice_states;
	Vector<Ref<GameplayReplicationState>> bob_states;
	Vector<Ref<GameplayReplicationState>> charlie_states;
	for (int i = 0; i < 4; i++) {
		Ref<GameplayReplicationState> authority;
		Ref<GameplayReplicationState> alice_state;
		Ref<GameplayReplicationState> bob_state;
		Ref<GameplayReplicationState> charlie_state;
		authority.instantiate();
		alice_state.instantiate();
		bob_state.instantiate();
		charlie_state.instantiate();
		const Ref<GameplayReplicationProperty> descriptor = make_replication_property("value");
		REQUIRE_EQ(authority->add_property(descriptor, initial_values[i]), OK);
		REQUIRE_EQ(alice_state->add_property(descriptor, 0), OK);
		REQUIRE_EQ(bob_state->add_property(descriptor, 0), OK);
		REQUIRE_EQ(charlie_state->add_property(descriptor, 0), OK);
		const int owner_peer_id = i == 0 ? alice_peer_id : 0;
		REQUIRE_EQ(server_replication->register_object(object_ids[i], owner_peer_id, authority), OK);
		REQUIRE_EQ(alice_replication->register_object(object_ids[i], owner_peer_id, alice_state), OK);
		REQUIRE_EQ(bob_replication->register_object(object_ids[i], owner_peer_id, bob_state), OK);
		REQUIRE_EQ(charlie_replication->register_object(object_ids[i], owner_peer_id, charlie_state), OK);
		server_states.push_back(authority);
		alice_states.push_back(alice_state);
		bob_states.push_back(bob_state);
		charlie_states.push_back(charlie_state);
	}
	REQUIRE_EQ(graph->add_object(make_relevancy_object(100, GameplayRelevancyObject::POLICY_OWNER_ONLY, Vector3(), alice_peer_id, 0, 100.0f, 4, 0, 200)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(200, GameplayRelevancyObject::POLICY_TEAM_ONLY, Vector3(), 0, 1, 100.0f, 3, 0, 200)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(300, GameplayRelevancyObject::POLICY_DISTANCE, Vector3(0, 0, 0), 0, 0, 100.0f, 2, 0, 200)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(400, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), 0, 0, 100.0f, 1, 0, 200)), OK);

	pump_gameplay_network(server, clients, 300, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[0]->get_property_value("value")), 10);
	CHECK_EQ(int(bob_states[0]->get_property_value("value")), 0);
	CHECK_EQ(int(charlie_states[0]->get_property_value("value")), 0);
	CHECK_EQ(int(alice_states[1]->get_property_value("value")), 20);
	CHECK_EQ(int(bob_states[1]->get_property_value("value")), 20);
	CHECK_EQ(int(charlie_states[1]->get_property_value("value")), 0);
	CHECK_EQ(int(alice_states[2]->get_property_value("value")), 30);
	CHECK_EQ(int(bob_states[2]->get_property_value("value")), 0);
	CHECK_EQ(int(charlie_states[2]->get_property_value("value")), 30);
	CHECK_EQ(int(alice_states[3]->get_property_value("value")), 40);
	CHECK_EQ(int(bob_states[3]->get_property_value("value")), 40);
	CHECK_EQ(int(charlie_states[3]->get_property_value("value")), 40);

	Ref<GameplayRelevancyObject> moved = make_relevancy_object(300, GameplayRelevancyObject::POLICY_DISTANCE, Vector3(1000, 0, 0), 0, 0, 100.0f, 2, 0, 200);
	REQUIRE_EQ(graph->update_object(moved), OK);
	REQUIRE_EQ(server_states[2]->set_property_value("value", 31), OK);
	pump_gameplay_network(server, clients, 250, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[2]->get_property_value("value")), 30);
	CHECK_EQ(int(bob_states[2]->get_property_value("value")), 31);
	CHECK_EQ(int(charlie_states[2]->get_property_value("value")), 30);
	CHECK_FALSE(graph->get_relevant_object_ids(alice_peer_id).has(300));
	CHECK(graph->get_relevant_object_ids(bob_peer_id).has(300));
	CHECK_FALSE(graph->get_relevant_object_ids(charlie_peer_id).has(300));

	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(alice_peer_id, Vector3(1000, 0, 0), 1)), OK);
	REQUIRE_EQ(server_states[2]->set_property_value("value", 32), OK);
	pump_gameplay_network(server, clients, 250, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[2]->get_property_value("value")), 32);
	CHECK_EQ(int(bob_states[2]->get_property_value("value")), 32);
	CHECK_EQ(int(charlie_states[2]->get_property_value("value")), 30);

	REQUIRE_EQ(server_states[3]->set_property_value("value", 41), OK);
	REQUIRE_EQ(server_replication->set_object_dormant(400, true), OK);
	const int64_t bytes_before_dormant = int64_t(graph->get_last_plan_stats(alice_peer_id).get("total_actual_bytes", int64_t(0)));
	pump_gameplay_network(server, clients, 150, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[3]->get_property_value("value")), 40);
	CHECK_EQ(int64_t(graph->get_last_plan_stats(alice_peer_id).get("total_actual_bytes", int64_t(0))), bytes_before_dormant);
	REQUIRE_EQ(server_replication->wake_object(400), OK);
	pump_gameplay_network(server, clients, 150, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[3]->get_property_value("value")), 41);

	REQUIRE_EQ(server_replication->set_object_dormant(400, true), OK);
	REQUIRE_EQ(server_states[3]->set_property_value("value", 42), OK);
	pump_gameplay_network(server, clients, 150, callable_mp_static(gameplay_wait_full_duration));
	CHECK_EQ(int(alice_states[3]->get_property_value("value")), 42);
	CHECK_FALSE(graph->is_object_dormant(400));

	Dictionary forged_relevancy;
	forged_relevancy["type"] = "gameplay_relevancy_control";
	forged_relevancy["position"] = Vector3(1000, 0, 0);
	CHECK_EQ(server_replication->receive_packet(alice_peer_id, forged_relevancy, OS::get_singleton()->get_ticks_msec()), ERR_UNAUTHORIZED);
	CHECK_EQ(server_replication->get_last_rejection_reason(), "client_cannot_control_relevancy");
	const Dictionary alice_stats = graph->get_last_plan_stats(alice_peer_id);
	CHECK_GT(int64_t(alice_stats.get("total_actual_bytes", int64_t(0))), int64_t(0));
	print_line(vformat("GAMEPLAY_RELEVANCY_ENET peers=3 objects=4 alice_candidates=%d alice_total_estimated_bytes=%d alice_measured_transport_bytes=%d", int(alice_stats.get("candidate_count", 0)), int64_t(alice_stats.get("total_estimated_bytes", int64_t(0))), int64_t(alice_stats.get("total_actual_bytes", int64_t(0)))));

	alice->disconnect_from_server();
	bob->disconnect_from_server();
	charlie->disconnect_from_server();
	server->stop_now();
	memdelete(charlie);
	memdelete(bob);
	memdelete(alice);
	memdelete(charlie_replication);
	memdelete(bob_replication);
	memdelete(alice_replication);
	memdelete(server);
	memdelete(server_replication);
	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

TEST_CASE("[Gameplay][Prediction] Deterministic movement matches authority and correction replays only unconfirmed inputs") {
	Ref<GameplayPredictionModel> model;
	model.instantiate();
	model->set_max_speed(10.0f);
	model->set_fixed_step_msec(100);

	Ref<GameplayClientPrediction> client;
	client.instantiate();
	client->set_model(model);
	client->set_correction_threshold(0.01f);
	const Ref<GameplayPredictionInput> first = client->predict_input(Vector3(1, 0, 0), 100);
	const Ref<GameplayPredictionInput> second = client->predict_input(Vector3(1, 0, 0), 200);
	const Ref<GameplayPredictionInput> third = client->predict_input(Vector3(1, 0, 0), 300);
	REQUIRE(first.is_valid());
	REQUIRE(second.is_valid());
	REQUIRE(third.is_valid());
	CHECK(client->get_predicted_state()->get_position().is_equal_approx(Vector3(3, 0, 0)));

	Ref<GameplayServerPrediction> authority;
	authority.instantiate();
	REQUIRE_EQ(authority->register_object(10, 2, model), OK);
	CHECK(bool(authority->consume_input(2, 10, first, 100).get("accepted", false)));
	CHECK(bool(authority->consume_input(2, 10, second, 200).get("accepted", false)));
	Ref<GameplayPredictionState> corrected = authority->get_object_state(10)->duplicate_state();
	corrected->set_position(Vector3(3, 0, 0));
	const Dictionary correction = client->apply_authoritative_state(corrected);
	CHECK(bool(correction.get("accepted", false)));
	CHECK(bool(correction.get("corrected", false)));
	CHECK_EQ(client->get_last_replayed_input_count(), 1);
	CHECK_EQ(client->get_unconfirmed_input_count(), 1);
	CHECK(client->get_predicted_state()->get_position().is_equal_approx(Vector3(4, 0, 0)));

	CHECK(bool(authority->consume_input(2, 10, third, 300).get("accepted", false)));
	const Dictionary final_reconciliation = client->apply_authoritative_state(authority->get_object_state(10));
	CHECK(bool(final_reconciliation.get("accepted", false)));
	CHECK_EQ(client->get_last_replayed_input_count(), 0);
	CHECK_EQ(client->get_unconfirmed_input_count(), 0);
	CHECK(client->get_predicted_state()->get_position().is_equal_approx(authority->get_object_state(10)->get_position()));

	CHECK_EQ(String(authority->consume_input(2, 10, third, 301).get("reason", String())), "duplicate_sequence");
	CHECK_EQ(String(authority->consume_input(2, 10, second, 302).get("reason", String())), "sequence_too_old");
	CHECK_EQ(String(authority->consume_input(2, 10, make_prediction_input(100, Vector3(1, 0, 0), 100), 303).get("reason", String())), "sequence_gap_too_large");
	CHECK_EQ(String(authority->consume_input(3, 10, make_prediction_input(4, Vector3(1, 0, 0), 100), 304).get("reason", String())), "gameplay_owner_mismatch");
}

TEST_CASE("[Gameplay][Prediction] Input history and rates are bounded on client and server") {
	Ref<GameplayPredictionModel> model;
	model.instantiate();
	model->set_fixed_step_msec(16);
	Ref<GameplayClientPrediction> client;
	client.instantiate();
	client->set_model(model);
	client->set_max_history(2);
	client->set_max_inputs_per_second(2);
	CHECK(client->predict_input(Vector3(1, 0, 0), 100).is_valid());
	CHECK(client->predict_input(Vector3(1, 0, 0), 100).is_valid());
	CHECK(client->predict_input(Vector3(1, 0, 0), 100).is_null());
	CHECK_EQ(client->get_last_rejection_reason(), "history_limit_reached");
	CHECK_EQ(client->get_unconfirmed_input_count(), 2);

	Ref<GameplayServerPrediction> authority;
	authority.instantiate();
	authority->set_max_inputs_per_second(2);
	REQUIRE_EQ(authority->register_object(20, 2, model), OK);
	CHECK(bool(authority->consume_input(2, 20, make_prediction_input(1, Vector3(1, 0, 0), 16), 100).get("accepted", false)));
	CHECK(bool(authority->consume_input(2, 20, make_prediction_input(2, Vector3(1, 0, 0), 16), 100).get("accepted", false)));
	CHECK_EQ(String(authority->consume_input(2, 20, make_prediction_input(3, Vector3(1, 0, 0), 16), 100).get("reason", String())), "input_rate_limit");
}

TEST_CASE("[Gameplay][Prediction] Interpolation and controlled network conditions remain deterministic and bounded") {
	Ref<GameplayInterpolationBuffer> buffer;
	buffer.instantiate();
	buffer->set_max_samples(3);
	buffer->set_interpolation_delay_msec(100);
	buffer->set_stale_after_msec(250);
	CHECK_EQ(buffer->add_sample(make_prediction_state(Vector3(20, 0, 0), Vector3(10, 0, 0), 2, 300)), OK);
	CHECK_EQ(buffer->add_sample(make_prediction_state(Vector3(0, 0, 0), Vector3(10, 0, 0), 1, 100)), OK);
	const Dictionary interpolated = buffer->sample(300);
	CHECK_EQ(String(interpolated.get("status", String())), "interpolated");
	const Ref<GameplayPredictionState> interpolated_state = interpolated["state"];
	CHECK(interpolated_state->get_position().is_equal_approx(Vector3(10, 0, 0)));
	CHECK_EQ(buffer->add_sample(make_prediction_state(Vector3(30, 0, 0), Vector3(), 3, 400)), OK);
	CHECK_EQ(buffer->add_sample(make_prediction_state(Vector3(40, 0, 0), Vector3(), 4, 500)), OK);
	CHECK_EQ(buffer->get_sample_count(), 3);
	CHECK_EQ(buffer->add_sample(make_prediction_state(Vector3(41, 0, 0), Vector3(), 4, 500)), ERR_ALREADY_EXISTS);
	const Dictionary stale = buffer->sample(1000);
	CHECK_EQ(String(stale.get("status", String())), "stale_held");
	const Ref<GameplayPredictionState> stale_state = stale["state"];
	CHECK(stale_state->get_position().is_equal_approx(Vector3(40, 0, 0)));

	Ref<GameplayInterpolationBuffer> empty;
	empty.instantiate();
	CHECK_EQ(String(empty->sample(100).get("status", String())), "empty");
	CHECK_EQ(empty->add_sample(make_prediction_state(Vector3(5, 0, 0), Vector3(), 1, 50)), OK);
	CHECK_EQ(String(empty->sample(100).get("status", String())), "single_sample");

	Ref<GameplayNetworkSimulator> simulator;
	simulator.instantiate();
	simulator->set_seed(7);
	simulator->set_loss_permyriad(10000);
	Dictionary message;
	message["type"] = "test";
	CHECK_EQ(String(simulator->enqueue(1, message, 100).get("reason", String())), "simulated_loss");
	CHECK_EQ(simulator->get_dropped_packet_count(), 1);
	simulator->set_loss_permyriad(0);
	simulator->set_latency_msec(100);
	simulator->set_jitter_msec(10);
	simulator->set_max_queued_packets(2);
	CHECK(bool(simulator->enqueue(1, message, 100).get("queued", false)));
	CHECK(bool(simulator->enqueue(1, message, 100).get("queued", false)));
	CHECK_EQ(String(simulator->enqueue(1, message, 100).get("reason", String())), "queue_limit");
	CHECK_EQ(simulator->get_queued_packet_count(), 2);
	CHECK_EQ(simulator->get_overflow_packet_count(), 1);
	CHECK_EQ(simulator->drain(150).size(), 0);
	CHECK_EQ(simulator->drain(250).size(), 2);
}

TEST_CASE("[Gameplay][Prediction][Integration] ENet owner prediction and remote interpolation survive loss and reconnect with stable identity") {
	GameplayGameState *game_state = memnew(GameplayGameState);
	GameplayGameMode *game_mode = memnew(GameplayGameMode);
	GameplaySessionManager *manager = memnew(GameplaySessionManager);
	GameplayDedicatedServer *server = memnew(GameplayDedicatedServer);
	GameplayMultiplayerReplication *server_replication = memnew(GameplayMultiplayerReplication);
	GameplayNetworkPrediction *server_prediction = memnew(GameplayNetworkPrediction);
	Ref<GameplayReplicationGraph> graph;
	graph.instantiate();
	game_mode->set_game_state(game_state);
	manager->set_game_mode(game_mode);
	server->set_authenticator(callable_mp_static(authenticate_test_user));
	REQUIRE_EQ(server_replication->set_replication_graph(graph), OK);
	server_prediction->set_replication_graph(graph);
	Ref<GameplayNetworkSimulator> server_conditions;
	server_conditions.instantiate();
	server_conditions->set_seed(101);
	server_conditions->set_latency_msec(18);
	server_conditions->set_jitter_msec(7);
	server_conditions->set_loss_permyriad(1500);
	server_prediction->set_network_simulator(server_conditions);
	server->set_replication(server_replication);
	server->set_prediction(server_prediction);

	Ref<GameplayServerConfig> config;
	config.instantiate();
	config->set_bind_address("127.0.0.1");
	config->set_port(0);
	config->set_protocol_version("prediction-1");
	config->set_disconnect_grace_period_msec(5000);
	REQUIRE_EQ(server->start(config, manager), OK);

	GameplaySessionClient *alice = memnew(GameplaySessionClient);
	GameplaySessionClient *bob = memnew(GameplaySessionClient);
	GameplayMultiplayerReplication *alice_replication = memnew(GameplayMultiplayerReplication);
	GameplayMultiplayerReplication *bob_replication = memnew(GameplayMultiplayerReplication);
	GameplayNetworkPrediction *alice_network_prediction = memnew(GameplayNetworkPrediction);
	GameplayNetworkPrediction *bob_network_prediction = memnew(GameplayNetworkPrediction);
	Ref<GameplayNetworkSimulator> alice_conditions;
	Ref<GameplayNetworkSimulator> bob_conditions;
	alice_conditions.instantiate();
	bob_conditions.instantiate();
	alice_conditions->set_seed(202);
	bob_conditions->set_seed(303);
	alice_conditions->set_latency_msec(18);
	bob_conditions->set_latency_msec(18);
	alice_conditions->set_jitter_msec(7);
	bob_conditions->set_jitter_msec(7);
	alice_conditions->set_loss_permyriad(1500);
	bob_conditions->set_loss_permyriad(1500);
	alice_network_prediction->set_network_simulator(alice_conditions);
	bob_network_prediction->set_network_simulator(bob_conditions);
	alice->set_replication(alice_replication);
	bob->set_replication(bob_replication);
	alice->set_prediction(alice_network_prediction);
	bob->set_prediction(bob_network_prediction);
	REQUIRE_EQ(alice->connect_to_server("127.0.0.1", server->get_bound_port(), "prediction-1", "alice"), OK);
	REQUIRE_EQ(bob->connect_to_server("127.0.0.1", server->get_bound_port(), "prediction-1", "bob"), OK);
	Vector<GameplaySessionClient *> clients = { alice, bob };
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(clients_joined).bind(alice, bob)));
	const int alice_peer_id = alice->get_peer_id();
	const int bob_peer_id = bob->get_peer_id();
	REQUIRE(alice_peer_id > 1);
	REQUIRE(bob_peer_id > 1);

	Ref<GameplayPredictionModel> movement_model;
	movement_model.instantiate();
	movement_model->set_max_speed(8.0f);
	movement_model->set_fixed_step_msec(16);
	REQUIRE_EQ(server_prediction->register_server_object(100, alice_peer_id, movement_model), OK);
	REQUIRE_EQ(server_prediction->register_server_object(200, bob_peer_id, movement_model), OK);
	Ref<GameplayClientPrediction> alice_prediction;
	Ref<GameplayClientPrediction> bob_prediction;
	Ref<GameplayInterpolationBuffer> alice_remote_bob;
	Ref<GameplayInterpolationBuffer> bob_remote_alice;
	alice_prediction.instantiate();
	bob_prediction.instantiate();
	alice_remote_bob.instantiate();
	bob_remote_alice.instantiate();
	alice_prediction->set_model(movement_model);
	bob_prediction->set_model(movement_model);
	REQUIRE_EQ(alice_network_prediction->register_owned_client_object(100, alice_prediction), OK);
	REQUIRE_EQ(alice_network_prediction->register_remote_client_object(200, alice_remote_bob), OK);
	REQUIRE_EQ(bob_network_prediction->register_owned_client_object(200, bob_prediction), OK);
	REQUIRE_EQ(bob_network_prediction->register_remote_client_object(100, bob_remote_alice), OK);

	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(alice_peer_id, Vector3(), 1)), OK);
	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(bob_peer_id, Vector3(), 2)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(100, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), alice_peer_id)), OK);
	REQUIRE_EQ(graph->add_object(make_relevancy_object(200, GameplayRelevancyObject::POLICY_ALWAYS, Vector3(), bob_peer_id)), OK);
	Ref<GameplayReplicationState> server_alice_state;
	Ref<GameplayReplicationState> server_bob_state;
	Ref<GameplayReplicationState> alice_alice_state;
	Ref<GameplayReplicationState> alice_bob_state;
	Ref<GameplayReplicationState> bob_alice_state;
	Ref<GameplayReplicationState> bob_bob_state;
	server_alice_state.instantiate();
	server_bob_state.instantiate();
	alice_alice_state.instantiate();
	alice_bob_state.instantiate();
	bob_alice_state.instantiate();
	bob_bob_state.instantiate();
	const Ref<GameplayReplicationProperty> position_property = make_replication_property("position");
	for (const Ref<GameplayReplicationState> &state : { server_alice_state, server_bob_state, alice_alice_state, alice_bob_state, bob_alice_state, bob_bob_state }) {
		REQUIRE_EQ(state->add_property(position_property, Vector3()), OK);
	}
	REQUIRE_EQ(server_replication->register_object(100, alice_peer_id, server_alice_state), OK);
	REQUIRE_EQ(server_replication->register_object(200, bob_peer_id, server_bob_state), OK);
	REQUIRE_EQ(alice_replication->register_object(100, alice_peer_id, alice_alice_state), OK);
	REQUIRE_EQ(alice_replication->register_object(200, bob_peer_id, alice_bob_state), OK);
	REQUIRE_EQ(bob_replication->register_object(100, alice_peer_id, bob_alice_state), OK);
	REQUIRE_EQ(bob_replication->register_object(200, bob_peer_id, bob_bob_state), OK);
	pump_gameplay_network(server, clients, 150, callable_mp_static(gameplay_wait_full_duration));

	Dictionary forged;
	forged["type"] = "gameplay_prediction_input";
	forged["object_id"] = 100;
	forged["position"] = Dictionary();
	forged["command"] = make_prediction_input(1, Vector3(1, 0, 0), 16)->to_dictionary();
	CHECK_EQ(server_prediction->receive_packet(alice_peer_id, forged, OS::get_singleton()->get_ticks_msec()), ERR_UNAUTHORIZED);
	CHECK_EQ(server_prediction->get_last_rejection_reason(), "forged_authoritative_state");

	for (int i = 0; i < 24; i++) {
		const uint64_t now = OS::get_singleton()->get_ticks_msec();
		REQUIRE(alice_network_prediction->submit_local_input(100, Vector3(1, 0, 0), now).is_valid());
		if (i < 12) {
			REQUIRE(bob_network_prediction->submit_local_input(200, Vector3(-1, 0, 0), now).is_valid());
		}
		pump_gameplay_network(server, clients, 20, callable_mp_static(gameplay_wait_full_duration));
	}
	REQUIRE(pump_gameplay_network(server, clients, 5000, callable_mp_static(predictions_settled).bind(server_prediction, alice_prediction, 100, bob_prediction, 200)));
	CHECK_GT(alice_conditions->get_dropped_packet_count() + bob_conditions->get_dropped_packet_count() + server_conditions->get_dropped_packet_count(), uint64_t(0));
	CHECK_GT(bob_remote_alice->get_sample_count(), 0);
	CHECK_GT(alice_remote_bob->get_sample_count(), 0);
	const Dictionary remote_sample = bob_remote_alice->sample(OS::get_singleton()->get_ticks_msec());
	CHECK_NE(String(remote_sample.get("status", String())), "empty");

	REQUIRE_EQ(server_alice_state->set_property_value("position", server_prediction->get_server_object_state(100)->get_position()), OK);
	REQUIRE_EQ(server_bob_state->set_property_value("position", server_prediction->get_server_object_state(200)->get_position()), OK);
	pump_gameplay_network(server, clients, 300, callable_mp_static(gameplay_wait_full_duration));
	CHECK(Vector3(bob_alice_state->get_property_value("position")).is_equal_approx(server_prediction->get_server_object_state(100)->get_position()));
	CHECK(Vector3(alice_bob_state->get_property_value("position")).is_equal_approx(server_prediction->get_server_object_state(200)->get_position()));

	GameplayUserSession *alice_session = manager->get_session("session-alice");
	REQUIRE(alice_session != nullptr);
	GameplayPlayerState *stable_player_state = alice_session->get_player_state();
	const String reconnect_token = alice->get_reconnect_token();
	alice->disconnect_from_server();
	Vector<GameplaySessionClient *> bob_only = { bob };
	REQUIRE(pump_gameplay_network(server, bob_only, 5000, callable_mp_static(session_inactive).bind(manager, String("session-alice"))));

	GameplaySessionClient *reconnected_alice = memnew(GameplaySessionClient);
	GameplayMultiplayerReplication *reconnected_replication = memnew(GameplayMultiplayerReplication);
	GameplayNetworkPrediction *reconnected_network_prediction = memnew(GameplayNetworkPrediction);
	Ref<GameplayNetworkSimulator> reconnect_conditions;
	reconnect_conditions.instantiate();
	reconnect_conditions->set_seed(404);
	reconnect_conditions->set_latency_msec(18);
	reconnect_conditions->set_jitter_msec(7);
	reconnect_conditions->set_loss_permyriad(1500);
	reconnected_network_prediction->set_network_simulator(reconnect_conditions);
	reconnected_alice->set_replication(reconnected_replication);
	reconnected_alice->set_prediction(reconnected_network_prediction);
	REQUIRE_EQ(reconnected_alice->connect_to_server("127.0.0.1", server->get_bound_port(), "prediction-1", "alice", reconnect_token), OK);
	Vector<GameplaySessionClient *> reconnected_clients = { bob, reconnected_alice };
	REQUIRE(pump_gameplay_network(server, reconnected_clients, 5000, callable_mp_static(client_joined).bind(reconnected_alice)));
	const int reconnected_peer_id = reconnected_alice->get_peer_id();
	CHECK_NE(reconnected_peer_id, alice_peer_id);
	CHECK_EQ(manager->get_session("session-alice"), alice_session);
	CHECK_EQ(alice_session->get_player_state(), stable_player_state);
	CHECK_EQ(stable_player_state->get_peer_id(), reconnected_peer_id);
	REQUIRE_EQ(server_prediction->set_server_object_owner_peer_id(100, reconnected_peer_id), OK);
	REQUIRE_EQ(server_replication->set_object_owner_peer_id(100, reconnected_peer_id), OK);
	REQUIRE_EQ(graph->set_object_owner_peer_id(100, reconnected_peer_id), OK);
	graph->remove_connection(alice_peer_id);
	REQUIRE_EQ(server_replication->update_server_connection_view(make_connection_view(reconnected_peer_id, Vector3(), 1)), OK);
	Ref<GameplayClientPrediction> reconnected_prediction;
	reconnected_prediction.instantiate();
	reconnected_prediction->set_model(movement_model);
	reconnected_prediction->set_initial_state(server_prediction->get_server_object_state(100));
	REQUIRE_EQ(reconnected_network_prediction->register_owned_client_object(100, reconnected_prediction), OK);
	Ref<GameplayInterpolationBuffer> reconnected_remote_bob;
	reconnected_remote_bob.instantiate();
	REQUIRE_EQ(reconnected_network_prediction->register_remote_client_object(200, reconnected_remote_bob), OK);
	for (int i = 0; i < 5; i++) {
		REQUIRE(reconnected_network_prediction->submit_local_input(100, Vector3(1, 0, 0), OS::get_singleton()->get_ticks_msec()).is_valid());
		pump_gameplay_network(server, reconnected_clients, 20, callable_mp_static(gameplay_wait_full_duration));
	}
	REQUIRE(pump_gameplay_network(server, reconnected_clients, 5000, callable_mp_static(predictions_settled).bind(server_prediction, reconnected_prediction, 100, bob_prediction, 200)));
	print_line(vformat("GAMEPLAY_PREDICTION_ENET latency_ms=18 jitter_ms=7 loss_permyriad=1500 alice_confirmed=%d alice_corrections=%d server_rejections=%d remote_samples=%d", reconnected_prediction->get_last_confirmed_sequence(), reconnected_prediction->get_correction_count(), server_prediction->get_rejected_packet_count(), bob_remote_alice->get_sample_count()));

	reconnected_alice->disconnect_from_server();
	bob->disconnect_from_server();
	server->stop_now();
	memdelete(reconnected_alice);
	memdelete(reconnected_network_prediction);
	memdelete(reconnected_replication);
	memdelete(bob);
	memdelete(alice);
	memdelete(bob_network_prediction);
	memdelete(alice_network_prediction);
	memdelete(bob_replication);
	memdelete(alice_replication);
	memdelete(server);
	memdelete(server_prediction);
	memdelete(server_replication);
	memdelete(manager);
	memdelete(game_mode);
	memdelete(game_state);
}

} // namespace TestGameplayFramework
